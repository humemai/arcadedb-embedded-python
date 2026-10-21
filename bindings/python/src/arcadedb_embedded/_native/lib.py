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
            "arcadedb_n_next": [P, L, I],
            "arcadedb_n_rs_close": [P, L],
            "arcadedb_n_server_start": [P, S],
            "arcadedb_n_server_stop": [P, L],
            "arcadedb_n_server_db": [P, L, S, I],
            "arcadedb_n_diag": [P],
            "arcadedb_n_sample_dump": [P],
            "arcadedb_free": [P, P],
        }
        for name, argtypes in sigs.items():
            fn = getattr(lib, name, None)
            if fn is None:  # a library built before this entry point existed
                continue
            fn.argtypes = argtypes
            fn.restype = None if name == "arcadedb_free" else ctypes.c_void_p
        global BINARY_PARAMS
        if not hasattr(
            lib, "arcadedb_n_exec_bin"
        ):  # a library built before the binary path
            BINARY_PARAMS = False
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


def b(value) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


def diag() -> dict:
    """Runtime facts of the image: Java version, jdk.incubator.vector present, CPUs, max heap, jvector provider classes."""
    return json.loads(call("arcadedb_n_diag"))
