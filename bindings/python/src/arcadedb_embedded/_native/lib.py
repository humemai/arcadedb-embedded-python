"""ctypes loader and call layer for ``libarcadedb`` (native-image shared library)."""

import ctypes
import json
import os
import sys
import threading
from pathlib import Path

from ..exceptions import ArcadeDBError

_LIB_NAMES = {
    "linux": "libarcadedb.so",
    "darwin": "libarcadedb.dylib",
    "win32": "arcadedb.dll",
}

# ARCADEDB_NATIVE_BINARY=0 turns off the float32 side buffer for numpy float parameters (phase 6: on by default when the library has it)
BINARY_PARAMS = os.environ.get("ARCADEDB_NATIVE_BINARY", "1") != "0"

# phase 8 switches (each defaults on when the library has the entry point; 0 turns one off, for A/B runs in one image):
# ARCADEDB_NATIVE_CMD: commands go through arcadedb_n_cmd (cursor id back as a long: no reply text, no free, no JSON decode)
# ARCADEDB_NATIVE_CLOSE_BATCH: result sets closed by Python are closed 64 at a time in one crossing (0: one crossing each)
# ARCADEDB_NATIVE_FASTENC: positional parameters of plain scalars are encoded by the cached json encoder, no default hook
CMD_PATH = os.environ.get("ARCADEDB_NATIVE_CMD", "1") != "0"
CLOSE_BATCH = int(os.environ.get("ARCADEDB_NATIVE_CLOSE_BATCH", "64"))
FAST_ENCODE = os.environ.get("ARCADEDB_NATIVE_FASTENC", "1") != "0"
INSERT_ROWS = os.environ.get("ARCADEDB_NATIVE_INSERT_ROWS", "1") != "0"

_lock = threading.Lock()
_lib = None
_isolate = None
_main_thread = None
_creator = None
_local = threading.local()


def library_path() -> Path:
    """``ARCADEDB_NATIVE_LIB`` if set, else the library next to this module."""
    env = os.environ.get("ARCADEDB_NATIVE_LIB")
    if env:
        return Path(env)
    name = _LIB_NAMES.get(sys.platform, "libarcadedb.so")
    return Path(__file__).with_name(name)


class _Thread:
    """The isolate thread of one Python thread; detached when the Python thread ends."""

    def __init__(self, handle, owned):
        self.handle = handle
        self.owned = owned

    def __del__(self):
        if self.owned and _lib is not None:
            try:
                _lib.graal_detach_thread(self.handle)
            except Exception:  # nosec B110 - interpreter shutdown
                pass


def _check_cpu() -> None:
    """The image is built for x86-64-v3 (AVX2, BMI2, FMA): fail with a clear error instead of SIGILL on an older CPU."""
    if sys.platform != "linux" or os.environ.get("ARCADEDB_NATIVE_SKIP_CPU_CHECK"):
        return
    import platform

    if platform.machine() not in ("x86_64", "AMD64"):
        return
    try:
        with open("/proc/cpuinfo") as f:
            flags = next((ln for ln in f if ln.startswith("flags")), "").split()
    except OSError:
        return
    missing = [x for x in ("avx2", "bmi2", "fma") if flags and x not in flags]
    if missing:
        raise ArcadeDBError(
            f"The native library needs an x86-64-v3 CPU (AVX2, BMI2, FMA); this CPU lacks {', '.join(missing)}. "
            "Use the arcadedb-embedded (JVM) package instead, or set ARCADEDB_NATIVE_SKIP_CPU_CHECK=1 at your own risk."
        )


def _load():
    global _lib, _isolate, _main_thread, _creator
    with _lock:
        if _lib is not None:
            return _lib
        path = library_path()
        if not path.exists():
            raise ArcadeDBError(
                f"Native library not found at {path}. Build it from the native-spike workflow or set "
                "ARCADEDB_NATIVE_LIB."
            )
        _check_cpu()
        # jvector's Highway library (libjvector-<arch>.so) is looked for next to the engine library
        os.environ.setdefault("ARCADEDB_NATIVE_LIBDIR", str(path.resolve().parent))
        lib = ctypes.CDLL(str(path))
        isolate = ctypes.c_void_p()
        thread = ctypes.c_void_p()
        lib.graal_create_isolate.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.graal_create_isolate.restype = ctypes.c_int
        params = None
        iso_args = os.environ.get("ARCADEDB_NATIVE_ISOLATE_ARGS", "").split()
        if iso_args:
            # run-time image options for the isolate (e.g. "-XX:InitialCollectionPolicy=Adaptive -XX:MaximumYoungGenerationSizePercent=20")
            class _Params(ctypes.Structure):
                _fields_ = [
                    ("version", ctypes.c_int),
                    ("reserved_address_space_size", ctypes.c_size_t),
                    ("auxiliary_image_path", ctypes.c_char_p),
                    ("auxiliary_image_reserved_space_size", ctypes.c_size_t),
                    ("argc", ctypes.c_int),
                    ("argv", ctypes.POINTER(ctypes.c_char_p)),
                    ("pkey", ctypes.c_int),
                    ("ignore_unrecognized_args", ctypes.c_char),
                    ("_reserved_4", ctypes.c_char),
                    ("_reserved_5", ctypes.c_char),
                ]

            argv = (ctypes.c_char_p * (len(iso_args) + 1))(
                b"arcadedb", *[a.encode() for a in iso_args]
            )
            params = _Params(version=5, argc=len(argv), argv=argv)
            lib.graal_create_isolate.argtypes[0] = ctypes.POINTER(_Params)
        rc = lib.graal_create_isolate(
            ctypes.byref(params) if params is not None else None,
            ctypes.byref(isolate),
            ctypes.byref(thread),
        )
        if rc != 0:
            raise ArcadeDBError(f"graal_create_isolate failed (rc={rc})")
        lib.graal_attach_thread.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.graal_attach_thread.restype = ctypes.c_int
        lib.graal_detach_thread.argtypes = [ctypes.c_void_p]
        lib.graal_detach_thread.restype = ctypes.c_int
        P, L, I, S = ctypes.c_void_p, ctypes.c_long, ctypes.c_int, ctypes.c_char_p
        sigs = {
            "arcadedb_n_open": [P, S, I],
            "arcadedb_n_close": [P, L, I],
            "arcadedb_n_info": [P, L],
            "arcadedb_n_tx": [P, L, I],
            "arcadedb_n_exec": [P, L, I, S, S, S, I],
            "arcadedb_n_exec_bin": [P, L, I, S, S, S, I, S, L],
            "arcadedb_n_insert_cols": [P, L, S, S, S, L],
            "arcadedb_n_next": [P, L, I],
            "arcadedb_n_rs_close": [P, L],
            "arcadedb_n_cmd": [P, L, I, S, S, S, S, L, I],
            "arcadedb_n_last_error": [P],
            "arcadedb_n_rs_close_many": [P, P, I],
            "arcadedb_n_exec_many": [P, L, S, S, S],
            "arcadedb_n_insert_rows": [P, L, S, S],
            "arcadedb_n_server_start": [P, S],
            "arcadedb_n_server_stop": [P, L],
            "arcadedb_n_server_db": [P, L, S, I],
            "arcadedb_n_diag": [P],
            "arcadedb_n_sample_dump": [P],
            "arcadedb_n_dbset": [P, L, S, S],
            "arcadedb_n_gb_create": [P, L, S],
            "arcadedb_n_gb": [P, L, S, S],
            "arcadedb_n_async": [P, L, S, S],
            "arcadedb_n_import": [P, L, S],
            "arcadedb_n_export": [P, L, S, S, I, S],
            "arcadedb_n_udf_register": [P, S, L, I, I],
            "arcadedb_n_set_upcall": [P, P],
            "arcadedb_free": [P, P],
        }
        for name, argtypes in sigs.items():
            fn = getattr(lib, name, None)
            if fn is None:  # a library built before this entry point existed
                continue
            fn.argtypes = argtypes
            fn.restype = (
                None
                if name
                in (
                    "arcadedb_free",
                    "arcadedb_n_rs_close_many",
                    "arcadedb_n_set_upcall",
                )
                else ctypes.c_long if name == "arcadedb_n_cmd" else ctypes.c_void_p
            )
        global BINARY_PARAMS, CMD_PATH, CLOSE_BATCH, INSERT_ROWS
        if not hasattr(
            lib, "arcadedb_n_exec_bin"
        ):  # a library built before the binary path
            BINARY_PARAMS = False
        if not hasattr(lib, "arcadedb_n_cmd"):  # a library built before phase 8
            CMD_PATH = False
        if not hasattr(lib, "arcadedb_n_rs_close_many"):
            CLOSE_BATCH = 0
        if not hasattr(lib, "arcadedb_n_insert_rows"):
            INSERT_ROWS = False
        _isolate = isolate
        _creator = threading.get_ident()
        _local.thread = _Thread(thread, owned=False)
        _lib = lib
        return lib


def loaded() -> bool:
    return _lib is not None


def _thread_handle():
    t = getattr(_local, "thread", None)
    if t is None:
        thread = ctypes.c_void_p()
        rc = _lib.graal_attach_thread(_isolate, ctypes.byref(thread))
        if rc != 0:
            raise ArcadeDBError(f"graal_attach_thread failed (rc={rc})")
        t = _local.thread = _Thread(thread, owned=True)
    return t.handle


def call(name: str, *args) -> dict:
    """Run one entry point; returns the decoded reply, raises ArcadeDBError-free (callers map errors)."""
    lib = _lib or _load()
    th = _thread_handle()
    ptr = getattr(lib, name)(th, *args)
    try:
        text = ctypes.string_at(ptr).decode("utf-8")
    finally:
        lib.arcadedb_free(th, ptr)
    return text


def call_bin(name: str, *args):
    """Like :func:`call` for a reply that may carry a float32 tail (``arcadedb_n_exec*`` with flag 4): returns ``(text, floats)``,
    floats a float32 numpy array or None. The JSON ends with ``,"bin":N}`` and the N floats follow its NUL, 4-byte aligned.
    """
    lib = _lib or _load()
    th = _thread_handle()
    ptr = getattr(lib, name)(th, *args)
    try:
        raw = ctypes.string_at(ptr)
        floats = None
        if raw.endswith(b"}"):
            i = raw.rfind(b',"bin":', max(0, len(raw) - 40))
            if i >= 0:
                n = int(raw[i + 7 : -1])
                import numpy as np

                off = (len(raw) + 1 + 3) & ~3
                floats = np.frombuffer(
                    ctypes.string_at(ptr + off, 4 * n), dtype=np.float32
                )
                raw = raw[:i] + b"}"
    finally:
        lib.arcadedb_free(th, ptr)
    return raw.decode("utf-8"), floats


def call_void(name: str, *args) -> None:
    """Run an entry point that returns nothing (``arcadedb_n_set_upcall``)."""
    lib = _lib or _load()
    getattr(lib, name)(_thread_handle(), *args)


def b(value) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


_bytes_cache = {}


def bc(value: str) -> bytes:
    """UTF-8 of a statement text or language name, remembered (the same few texts cross a million times in a load)."""
    r = _bytes_cache.get(value)
    if r is None:
        r = value.encode("utf-8")
        if len(_bytes_cache) < 4096:
            _bytes_cache[value] = r
    return r


def cmd(handle, flags, language, command, params, buf, count, first) -> int:
    """``arcadedb_n_cmd``: the cursor id (> 0), 0 for no cursor, -1 for an error (read it with :func:`last_error`)."""
    lib = _lib or _load()
    t = _local.__dict__.get("thread")
    th = t.handle if t is not None else _thread_handle()
    return lib.arcadedb_n_cmd(
        th, handle, flags, language, command, params, buf, count, first
    )


def last_error() -> str:
    return call("arcadedb_n_last_error")


# --- result sets closed in batches (one crossing for CLOSE_BATCH cursors)
_pending = []
_pending_lock = threading.Lock()


def close_rs(rs_id: int) -> None:
    if CLOSE_BATCH <= 0:
        call("arcadedb_n_rs_close", rs_id)
        return
    _pending.append(rs_id)
    if len(_pending) >= CLOSE_BATCH:
        flush_closes()


def flush_closes() -> None:
    """Close every cursor whose close is waiting; called before a commit, a rollback and a database close, and when the batch is full."""
    if not _pending or _lib is None:
        return
    with _pending_lock:
        ids = _pending[:]
        del _pending[: len(ids)]
        if ids:
            arr = (ctypes.c_long * len(ids))(*ids)
            _lib.arcadedb_n_rs_close_many(_thread_handle(), arr, len(ids))


def diag() -> dict:
    """Runtime facts of the image: Java version, jdk.incubator.vector present, CPUs, max heap, jvector provider classes."""
    return json.loads(call("arcadedb_n_diag"))
