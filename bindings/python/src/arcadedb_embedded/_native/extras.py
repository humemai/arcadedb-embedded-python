"""Native backend coverage beyond the DSL core: GraphBatch, the async executor, database settings, import/export and Python
functions in SQL, over the ``arcadedb_n_gb*``, ``arcadedb_n_async``, ``arcadedb_n_dbset``, ``arcadedb_n_import``,
``arcadedb_n_export`` and ``arcadedb_n_udf_register`` entry points (``NativeExtras.java``).

Callbacks (async completions, error handlers, Python functions called from SQL) go through ONE ctypes function pointer that
``_ensure_upcall`` registers with the library: the engine thread (or an async writer thread) calls ``_dispatch(id, json)``,
ctypes takes the GIL for the call, and the reply is JSON (see the header of ``NativeExtras.java`` for GIL and exception rules).
"""

import ctypes
import itertools
import json
import threading
from collections.abc import Mapping
from typing import Any, Callable, Iterable, Optional

from ..exceptions import ArcadeDBError
from ..graph_batch import GraphBatch as _BaseGraphBatch
from . import lib, not_yet
from .codec import _PLAIN, _default, _prep, loads

# -------------------------------------------------------------------------------------------------------- upcall

_UPCALL_TYPE = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_long, ctypes.c_char_p)
_callbacks: dict = {}
_callback_ids = itertools.count(1)
_callbacks_lock = threading.Lock()
_reply = threading.local()
_upcall_ref = None


def _enc(value) -> str:
    """JSON text of a value with the tagged encoding of query parameters."""
    return json.dumps(_prep(value), default=_default)


def _dispatch(cid, raw):
    try:
        fn = _callbacks.get(cid)
        message = loads(raw.decode("utf-8")) if raw else {}
        reply = fn(message) if fn is not None else None
        data = None if reply is None else _enc(reply).encode("utf-8")
    except BaseException as exc:  # nosec B110 - an exception must not cross the C frame
        data = json.dumps({"error": f"{type(exc).__name__}: {exc}"}).encode("utf-8")
    if data is None:
        return None
    # kept alive until this thread's next callback: Java copies the text before it returns
    buf = ctypes.create_string_buffer(data)
    _reply.buf = buf
    return ctypes.addressof(buf)


def _ensure_upcall() -> None:
    global _upcall_ref
    if _upcall_ref is not None:
        return
    lib.call_void(
        "arcadedb_n_set_upcall", ctypes.cast(_make_pointer(), ctypes.c_void_p)
    )


def _make_pointer():
    global _upcall_ref
    _upcall_ref = _UPCALL_TYPE(_dispatch)
    return _upcall_ref


def _register(fn: Callable) -> int:
    _ensure_upcall()
    with _callbacks_lock:
        cid = next(_callback_ids)
        _callbacks[cid] = fn
    return cid


def _error_from(message: dict) -> ArcadeDBError:
    reply = message.get("err") or {}
    exc = ArcadeDBError(f"{reply.get('cls')}: {reply.get('error')}")
    exc.native = reply
    exc.java_chain = reply.get("chain") or []
    return exc


def _call(prefix: str, name: str, *args) -> dict:
    from .database import _call as call

    return call(prefix, name, *args)


# -------------------------------------------------------------------------------------------------------- GraphBatch


class NativeGraphBatch(_BaseGraphBatch):
    """``GraphBatch`` over the engine's batch builder in the image (same names and behaviour as the JPype wrapper)."""

    def __init__(self, database, handle: int):
        self._db = database
        self._gb = handle
        self._closed = False

    @classmethod
    def create(cls, database, **options) -> "NativeGraphBatch":
        wal_flush = options.get("wal_flush")
        if wal_flush is not None:
            options["wal_flush"] = cls._to_java_wal_flush_name(wal_flush)
        given = {k: v for k, v in options.items() if v is not None}
        try:
            reply = _call(
                "Failed to create GraphBatch",
                "arcadedb_n_gb_create",
                database._h,
                lib.b(_enc(given)),
            )
        except ArcadeDBError:
            raise
        return cls(database, reply["h"])

    @classmethod
    def _to_java_wal_flush_name(cls, mode: str) -> str:
        normalized = mode.lower()
        if normalized not in cls._VALID_WAL_FLUSH_MODES:
            raise ValueError(
                f"Invalid wal_flush mode: {mode}. Must be one of: {list(cls._VALID_WAL_FLUSH_MODES.keys())}"
            )
        return cls._VALID_WAL_FLUSH_MODES[normalized]

    def _op(self, prefix: str, op: str, **args) -> dict:
        return _call(prefix, "arcadedb_n_gb", self._gb, lib.b(op), lib.b(_enc(args)))

    def new_vertex(self, type_name: str):
        from .records import Vertex

        self._check_not_closed()
        return Vertex(self._db, type_name)

    def create_vertex(self, type_name: str, **properties):
        from .records import Vertex

        self._check_not_closed()
        db = self._db
        started = False
        try:
            if not db.is_transaction_active():
                started = True
                db.begin()
            reply = self._op(
                f"Failed to create batch vertex of type '{type_name}'",
                "create_vertex",
                type=type_name,
                props=properties,
            )
            if started:
                db.commit()
            return Vertex(db, type_name, reply["rid"], properties)
        except BaseException:
            if started:
                try:
                    if db.is_transaction_active():
                        db.rollback()
                except (
                    Exception
                ):  # nosec B110 - the original error is the one to report
                    pass
            raise

    def create_vertices(self, type_name: str, count_or_properties) -> list:
        self._check_not_closed()
        db = self._db
        owns_transaction = not db.is_transaction_active()
        prefix = f"Failed to create batch vertices for type '{type_name}'"
        try:
            if isinstance(count_or_properties, int):
                return self._op(
                    prefix, "create_vertices", type=type_name, count=count_or_properties
                )["rids"]
            rows = list(count_or_properties)
            for row in rows:
                if row is not None and not isinstance(row, dict):
                    raise TypeError(
                        "create_vertices() property rows must be dicts or None"
                    )
            return self._op(
                prefix, "create_vertices", type=type_name, rows=[r or {} for r in rows]
            )["rids"]
        except BaseException as e:
            if owns_transaction:
                try:
                    if db.is_transaction_active():
                        db.rollback()
                except Exception:  # nosec B110
                    pass
            if isinstance(e, (TypeError, ArcadeDBError)) or not isinstance(
                e, Exception
            ):
                raise
            raise ArcadeDBError(f"{prefix}: {e}") from e

    @staticmethod
    def _rid_text(value) -> str:
        rid = getattr(value, "get_rid", None)
        if rid is not None:
            return rid()
        return str(value)

    def new_edge(
        self,
        source_vertex_or_rid,
        edge_type: str,
        destination_vertex_or_rid,
        **properties,
    ):
        self._check_not_closed()
        self._op(
            f"Failed to buffer batch edge '{edge_type}'",
            "new_edge",
            src=self._rid_text(source_vertex_or_rid),
            type=edge_type,
            dst=self._rid_text(destination_vertex_or_rid),
            props=properties,
        )
        return self

    def new_edges(self, source_rids, edge_type: str, destination_rids, properties=None):
        self._check_not_closed()
        source_rids = [self._rid_text(r) for r in source_rids]
        destination_rids = [self._rid_text(r) for r in destination_rids]
        if properties is not None:
            properties = list(properties)
        lengths = [len(source_rids), len(destination_rids)]
        if properties is not None:
            lengths.append(len(properties))
        if len(set(lengths)) != 1:
            names = ["source_rids", "destination_rids", "properties"]
            got = ", ".join(f"{n} {k}" for n, k in zip(names, lengths))
            raise ArcadeDBError(
                f"Failed to buffer batch edges '{edge_type}': source_rids, destination_rids and properties must have "
                f"the same length ({got})"
            )
        for p in properties or ():
            for key in p or ():
                if not isinstance(key, str):
                    raise ArcadeDBError(
                        f"Failed to buffer batch edges '{edge_type}': property names must be str, got {key!r}"
                    )
        chunk = self._BULK_CHUNK
        for start in range(0, len(source_rids), chunk):
            self._op(
                f"Failed to buffer batch edges '{edge_type}'",
                "new_edges",
                src=source_rids[start : start + chunk],
                type=edge_type,
                dst=destination_rids[start : start + chunk],
                props=(
                    None
                    if properties is None
                    else [p or {} for p in properties[start : start + chunk]]
                ),
            )
        return self

    def flush(self):
        self._check_not_closed()
        self._op("Failed to flush GraphBatch", "flush")
        return self

    def close(self):
        if self._closed:
            return
        refused = False
        try:
            self._op("Failed to close GraphBatch", "close")
        except ArcadeDBError as e:
            # an IllegalStateException while the caller has a transaction open: the batch is still open with its work pending
            refused = (getattr(e, "native", None) or {}).get(
                "cls"
            ) == "java.lang.IllegalStateException" and bool(
                self._db.is_transaction_active()
            )
            raise
        finally:
            if not refused:
                self._closed = True

    def get_total_edges_created(self) -> int:
        self._check_not_closed()
        return int(self._op("Failed to read GraphBatch", "stats")["total_edges"])

    def get_buffered_edge_count(self) -> int:
        self._check_not_closed()
        return int(self._op("Failed to read GraphBatch", "stats")["buffered"])

    def get_deferred_incoming_edge_count(self) -> int:
        self._check_not_closed()
        return int(self._op("Failed to read GraphBatch", "stats")["deferred"])


# -------------------------------------------------------------------------------------------------------- async


class NativeAsyncExecutor:
    """The database's async executor (one per database) with the JPype wrapper's names; callbacks run on the engine's writer
    threads and take the GIL, as the JPype proxies do."""

    def __init__(self, database):
        self._db = database
        self._closed = False
        self._owner = database
        self._cb_ids: list = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_closed(self) -> bool:
        return self._closed

    def _op(self, op: str, **args) -> dict:
        return _call(
            "Async executor failed",
            "arcadedb_n_async",
            self._db._h,
            lib.b(op),
            lib.b(_enc(args)),
        )

    def _settings(self) -> dict:
        return self._op("get")

    def _set(self, key, value):
        self._op("set", key=key, value=value)
        return self

    # configuration
    def set_parallel_level(self, level: int):
        if level < 1:
            raise ValueError("parallel_level must be at least 1")
        return self._set("parallel", level)

    def set_commit_every(self, count: int):
        if count < 1:
            raise ValueError(
                f"commit_every must be >= 1 (got {count}); the async executor always commits in batches"
            )
        return self._set("commit_every", count)

    def set_transaction_use_wal(self, use_wal: bool):
        return self._set("wal", bool(use_wal))

    def set_transaction_sync(self, sync_mode: str):
        valid = {"no": "NO", "yes_nometadata": "YES_NOMETADATA", "yes_full": "YES_FULL"}
        if sync_mode not in valid:
            raise ValueError(f"sync_mode must be one of {set(valid)}, got {sync_mode}")
        return self._set("sync", valid[sync_mode])

    def set_back_pressure(self, percentage: int):
        if percentage < 0 or percentage > 100:
            raise ValueError("back_pressure must be between 0 and 100")
        return self._set("back_pressure", percentage)

    def get_parallel_level(self) -> int:
        return int(self._settings()["parallel"])

    def get_back_pressure(self) -> int:
        return int(self._settings()["back_pressure"])

    def get_commit_every(self) -> int:
        return int(self._settings()["commit_every"])

    def is_transaction_use_wal(self) -> bool:
        return bool(self._settings()["wal"])

    def get_transaction_sync(self) -> str:
        return self._settings()["sync"].lower()

    def get_thread_count(self) -> int:
        return int(self._settings()["threads"])

    def is_processing(self) -> bool:
        return bool(self._settings()["processing"])

    def is_pending(self) -> bool:
        return self.is_processing()

    def kill(self):
        self._op("kill")

    # work
    def _record_callback(self, callback, kind="d"):
        from .records import _wrap_dict

        def handler(message):
            callback(_wrap_dict(self._db, message["rec"], kind))

        return _register(handler)

    def _error_callback(self, callback):
        return _register(lambda message: callback(_error_from(message)))

    def create_record(self, document, callback=None, error_callback=None):
        kind = "v" if hasattr(document, "get_out_edges") else "d"
        cb = self._record_callback(callback, kind) if callback is not None else 0
        err = self._error_callback(error_callback) if error_callback is not None else 0
        self._op(
            "create_record",
            type=document._type,
            kind=kind,
            props=document._props,
            cb=cb,
            err=err,
        )

    def _statement(self, op, language, text, callback, args, params, error_callback):
        from .database import NativeResultSet

        args = tuple(args or ())
        if args and params:
            raise ValueError("Use either positional args or named params, not both")
        cb = 0
        if callback is not None:

            def on_result(message):
                callback(NativeResultSet(self._db, message["reply"]))

            cb = _register(on_result)
        err = self._error_callback(error_callback) if error_callback is not None else 0
        if params:
            values = dict(params)
        elif args:
            values = (
                dict(args[0])
                if len(args) == 1 and isinstance(args[0], Mapping)
                else list(args)
            )
        else:
            values = None
        self._op(op, lang=language, text=text, params=values, cb=cb, err=err)

    def query(
        self, language, query_text, callback, args=None, error_callback=None, **params
    ):
        self._statement(
            "query", language, query_text, callback, args, params, error_callback
        )

    def command(
        self,
        language,
        command_text,
        callback=None,
        args=None,
        error_callback=None,
        **params,
    ):
        self._statement(
            "command", language, command_text, callback, args, params, error_callback
        )

    def append_samples(
        self, type_name, timestamps, *column_values, primitive: bool = False
    ):
        if primitive:
            not_yet("AsyncExecutor.append_samples(primitive=True)")

        def plain(values):
            return values.tolist() if hasattr(values, "tolist") else list(values)

        self._op(
            "append_samples",
            type=type_name,
            ts=[int(t) for t in plain(timestamps)],
            cols=[plain(c) for c in column_values],
        )

    def new_edge(self, *args, **kwargs):
        not_yet("AsyncExecutor.new_edge")

    def new_edge_by_keys(self, *args, **kwargs):
        not_yet("AsyncExecutor.new_edge_by_keys")

    def scan_type(self, *args, **kwargs):
        not_yet("AsyncExecutor.scan_type")

    def transaction(self, *args, **kwargs):
        not_yet("AsyncExecutor.transaction")

    def wait_completion(self, timeout_ms: Optional[int] = None):
        if timeout_ms is None:
            self._op("wait")
        elif timeout_ms < 0:
            raise ValueError(f"timeout_ms must be None or >= 0, got {timeout_ms}")
        elif timeout_ms == 0:
            if self.is_processing():
                raise TimeoutError("Async operations have not completed (0ms poll)")
        elif not self._op("wait", timeout_ms=timeout_ms)["done"]:
            raise TimeoutError(
                f"Async operations did not complete within {timeout_ms}ms"
            )

    def on_ok(self, callback: Callable[[], None]):
        self._op("on_ok", cb=_register(lambda message: callback()))
        return self

    def on_error(self, callback: Callable[[Exception], None]):
        self._op("on_error", cb=self._error_callback(callback))
        return self

    def close(self):
        if self._closed:
            return
        try:
            self._op("close")
        finally:
            self._closed = True
            owner, self._owner = self._owner, None
            if owner is not None:
                owner._discard_async_executor(self)


def insert_parallel(database, type_name: str, rows) -> dict:
    """Hand ``rows`` (a list of dicts) to the async writers; returns the failure token for :func:`failures`."""
    return _call(
        "Failed to bulk-insert",
        "arcadedb_n_async",
        database._h,
        b"insert_parallel",
        lib.b(_enc({"type": type_name, "rows": rows})),
    )


def failures(database, token: int) -> dict:
    return _call(
        "Failed to read the parallel writers",
        "arcadedb_n_async",
        database._h,
        b"failures",
        lib.b(_enc({"fid": token})),
    )


# -------------------------------------------------------------------------------------------------------- settings


def db_set(database, op: str, value: str = "") -> dict:
    return _call(
        f"Failed to set {op}", "arcadedb_n_dbset", database._h, lib.b(op), lib.b(value)
    )


# -------------------------------------------------------------------------------------------------------- import / export


def import_documents(database, settings: dict) -> Optional[dict]:
    from ..importer import _stringify_import_setting

    text = json.dumps({k: _stringify_import_setting(v) for k, v in settings.items()})
    return _call("Failed to import", "arcadedb_n_import", database._h, lib.b(text))[
        "stats"
    ]


def run_import(database, settings: dict, parallel, commit_every, wal) -> Optional[dict]:
    """The importer with the async executor's settings overridden for the run and restored after it (as the JPype path does)."""
    executor = database._async()
    saved = executor._settings()
    saved_ryw = database.is_read_your_writes()
    try:
        database.set_read_your_writes(False)
        if parallel is not None:
            executor.set_parallel_level(parallel)
        if commit_every is not None:
            executor.set_commit_every(commit_every)
        if wal is not None:
            executor.set_transaction_use_wal(wal)
        return import_documents(database, settings)
    finally:
        try:
            executor.wait_completion()
        finally:
            database.set_read_your_writes(saved_ryw)
            executor._set("parallel", saved["parallel"])
            executor._set("commit_every", saved["commit_every"])
            executor._set("wal", saved["wal"])


def export_database(
    database, path: str, fmt: str, overwrite: bool, settings: dict
) -> dict:
    return _call(
        "Database export failed",
        "arcadedb_n_export",
        database._h,
        lib.b(path),
        lib.b(fmt),
        1 if overwrite else 0,
        lib.b(json.dumps(settings)),
    )["stats"]


# -------------------------------------------------------------------------------------------------------- Python functions in SQL


def register_function(
    name: str, fn: Callable, min_args: int = 0, max_args: int = -1
) -> None:
    """Make ``fn`` callable from SQL as ``name(..)``: ``SELECT name(a, b) FROM T``.

    ``fn`` receives the argument values as Python values and returns a value of a type a parameter can carry (str, int, float,
    bool, None, list, dict, Decimal, datetime). An exception raised by ``fn`` fails the statement with its text. Registration is
    process-wide (the engine's function factory), like any engine function; ``max_args`` < 0 means any number.
    """

    def handler(message):
        try:
            return {"v": fn(*message.get("args", []))}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    cid = _register(handler)
    _call(
        "Failed to register the function",
        "arcadedb_n_udf_register",
        lib.b(name),
        cid,
        int(min_args),
        int(max_args if max_args >= 0 else 2**31 - 1),
    )
