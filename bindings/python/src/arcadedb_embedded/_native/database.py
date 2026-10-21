"""NativeDatabase, NativeDatabaseFactory, NativeResultSet and NativeResult: the DSL-first core over libarcadedb."""

import json
import os
import time as _time
from collections import deque
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from ..exceptions import ArcadeDBError
from ..transactions import TransactionContext
from . import lib, not_yet
from .codec import encode_params, json_native, loads

_LAZY_COMMAND_ROWS = os.environ.get("ARCADEDB_NATIVE_LAZY_CMD", "1") != "0"
_BINARY_REPLY = os.environ.get("ARCADEDB_NATIVE_BIN_REPLY", "1") != "0"
_FIRST_BATCH = 256
_NEXT_BATCH = 2048
_KIND = {"v": "v", "e": "e", "d": "d"}


def _error(prefix: str, reply: dict) -> ArcadeDBError:
    """The ArcadeDBError for a failed reply, worded like the JPype path (``prefix: java.class: message``)."""
    chain = reply.get("chain") or []
    head = f"{reply.get('cls')}: {reply.get('error')}"
    exc = ArcadeDBError(f"{prefix}: {head}" if prefix else head)
    exc.native = reply
    exc.java_chain = chain
    return exc


def _read_error(reply: dict) -> ArcadeDBError:
    exc = ArcadeDBError(
        f"Reading the result set failed: {reply.get('cls')}: {reply.get('error')}"
    )
    exc.native = reply
    exc.java_chain = reply.get("chain") or []
    return exc


def _call(prefix: str, name: str, *args) -> dict:
    reply = json.loads(lib.call(name, *args))
    if not reply.get("ok"):
        raise _error(prefix, reply)
    return reply


class NativeResult:
    """One row. Values are already Python types (datetime, Decimal, lists, dicts, RID text)."""

    __slots__ = ("_props", "_meta", "_database")

    def __init__(self, props: Dict[str, Any], meta, database=None):
        self._props = props
        self._meta = meta or None
        self._database = database

    def _check_open(self) -> None:
        database = self._database
        if database is not None and database._closed and self._meta is not None:
            raise ArcadeDBError(
                "Database is closed: a record row cannot be read after its database was closed. "
                "Read what you need before closing it."
            )

    def has_property(self, name: str) -> bool:
        self._check_open()
        return name in self._props

    def get(self, name: str, convert_types: bool = True) -> Any:
        self._check_open()
        return self._props.get(name)

    def get_raw(self, name: str) -> Any:
        return self.get(name)

    def get_rid(self) -> Optional[str]:
        return self._meta[0] if self._meta else None

    def _record(self, kinds):
        from .records import _wrap

        self._check_open()
        if not self._meta or self._meta[2] not in kinds:
            return None
        return _wrap(self._database, self)

    def get_vertex(self):
        return self._record("v")

    def get_edge(self):
        return self._record("e")

    def get_element(self):
        return self._record("vde")

    def get_property_names(self) -> List[str]:
        self._check_open()
        return list(self._props)

    @property
    def property_names(self) -> List[str]:
        return self.get_property_names()

    def to_dict(self, convert_types: bool = True) -> Dict[str, Any]:
        self._check_open()
        return dict(self._props)

    def to_json(self) -> str:
        self._check_open()
        out = json_native(self._props)
        if self._meta:
            rid, type_name, kind = self._meta
            out = dict(out)
            out["@cat"] = kind
            out["@type"] = type_name
            out["@rid"] = rid
        return json.dumps(out, default=str, separators=(",", ":"))

    def __repr__(self) -> str:
        names = list(self._props)
        preview = ", ".join(repr(n) for n in names[:3]) + (
            ", ..." if len(names) > 3 else ""
        )
        rid = self.get_rid()
        return (
            f"Result(rid={rid!r}, properties=[{preview}])"
            if rid
            else f"Result(properties=[{preview}])"
        )


class NativeResultSet:
    """Cursor over a statement's rows, fetched in batches through ``arcadedb_n_next``."""

    def __init__(self, database, reply: dict):
        self._database = database  # strong reference: a result keeps its database alive
        self._rs = reply["rs"]
        self._buf = deque(zip(reply["rows"], reply["meta"]))
        self._more = not reply["drained"]
        self._closed = False
        self._exhausted = False
        # the engine computes lazily: an error met while the first rows were read is raised when the rows before it
        # have been consumed, as it is on the JPype path (the cursor is already finished on the Java side)
        self._pending_error = reply.get("rerr")

    # -- state

    def _readable(self) -> bool:
        database = self._database
        if database is not None and database._closed and not self._exhausted:
            raise ArcadeDBError(
                "Database is closed: the rows of this result set cannot be read after their database was closed. "
                "Read them before closing the database."
            )
        if not self._closed:
            return True
        if self._exhausted:
            return False
        raise ArcadeDBError(
            "This result set was closed before all its rows were read (by first(), one(), close(), or leaving its "
            "with block), so the rows it had not returned are gone. Run the query again to read them."
        )

    def _fill(self) -> bool:
        """Fetch the next batch into the buffer; False once the cursor is drained."""
        if self._pending_error is not None:
            err, self._pending_error = self._pending_error, None
            self._more = False
            self._closed = True
            self._exhausted = True
            raise _read_error(err)
        if not self._more:
            return False
        try:
            reply = loads(lib.call("arcadedb_n_next", self._rs, _NEXT_BATCH))
        except ArcadeDBError:
            raise
        if not reply.get("ok"):
            self._more = False
            self._closed = True
            self._exhausted = True
            self._rs = 0
            raise ArcadeDBError(
                f"Reading the result set failed: {reply.get('cls')}: {reply.get('error')}"
            )
        self._buf.extend(zip(reply["rows"], reply["meta"]))
        self._more = not reply["drained"]
        self._pending_error = reply.get("rerr")
        return bool(self._buf) or self._pending_error is not None

    def _finish(self) -> None:
        self._exhausted = True
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._more and self._rs:
            try:
                lib.call("arcadedb_n_rs_close", self._rs)
            except Exception:  # nosec B110 - best effort
                pass
        self._more = False
        self._buf.clear()

    # -- reading

    def __iter__(self) -> Iterator[NativeResult]:
        return self

    def __next__(self) -> NativeResult:
        if self._readable():
            while True:
                if self._buf:
                    props, meta = self._buf.popleft()
                    return NativeResult(props, meta, self._database)
                if not self._fill():
                    break
        if not self._closed:
            self._finish()
        raise StopIteration

    def _drain_dicts(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not self._readable():
            return out
        while True:
            out.extend(p for p, _ in self._buf)
            self._buf.clear()
            if not self._fill():
                break
        self._finish()
        return out

    def to_list(self, convert_types: bool = True) -> List[Dict[str, Any]]:
        return self._drain_dicts()

    def iter_dicts(self, convert_types: bool = True) -> Iterator[Dict[str, Any]]:
        for row in self:
            yield row.to_dict()

    def to_json_list(self, batch_size: int = 10_000) -> List[Dict[str, Any]]:
        if int(batch_size) < 1:
            raise ValueError("batch_size must be at least 1")
        return [json_native(row) for row in self._drain_dicts()]

    def iter_json_batches(self, batch_size: int = 10_000, **kwargs):
        if int(batch_size) < 1:
            raise ValueError("batch_size must be at least 1")
        rows = self.to_json_list()
        for i in range(0, len(rows), batch_size):
            yield rows[i : i + batch_size]

    def to_dataframe(self, convert_types: bool = True):
        import pandas as pd

        return pd.DataFrame(self._drain_dicts())

    def to_columns(self, batch_size: int = 25_000, columns=None):
        """Columns as the JPype path returns them (numpy int64/float64/bool/datetime64[ms] arrays, lists for text and
        JSON-typed values, an object array of Decimal), built in Python from the rows: a columnar JSON path, no
        binary buffer. None when numpy is missing."""
        try:
            import numpy  # noqa: F401
        except ImportError:
            return None
        from .columns import to_columns

        return to_columns(self._drain_dicts(), columns)

    def to_arrow(self, batch_size: int = 25_000, columns=None):
        """A ``pyarrow.Table`` with the types of :meth:`to_columns` but nulls kept (None when pyarrow is missing)."""
        try:
            import numpy  # noqa: F401
            import pyarrow  # noqa: F401
        except ImportError:
            return None
        from .columns import to_arrow

        return to_arrow(self._drain_dicts(), columns)

    def to_polars(self, batch_size: int = 25_000, columns=None):
        try:
            import polars as pl
        except ImportError as exc:
            raise ImportError(
                "polars is required for to_polars(); install it with 'pip install polars pyarrow'"
            ) from exc
        table = self.to_arrow(batch_size, columns)
        if table is None:
            raise ImportError("pyarrow is required for to_polars()")
        return pl.from_arrow(table)

    def iter_chunks(self, size: int = 1000, convert_types: bool = True):
        chunk = []
        for row in self.iter_dicts(convert_types=convert_types):
            chunk.append(row)
            if len(chunk) >= size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def count(self) -> int:
        n = 0
        for _ in self:
            n += 1
        return n

    def first(self) -> Optional[NativeResult]:
        try:
            return next(iter(self))
        except StopIteration:
            return None
        finally:
            self.close()

    def one(self) -> NativeResult:
        iterator = iter(self)
        try:
            try:
                result = next(iterator)
            except StopIteration as exc:
                raise ValueError("Query returned no results") from exc
            try:
                next(iterator)
                raise ValueError("Query returned multiple results")
            except StopIteration:
                return result
        finally:
            self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:  # nosec B110
            pass


class NativeDatabase:
    """The DSL-first database handle: statements, transactions, lifecycle. See the package docstring for the rest."""

    def __init__(self, handle: int, owned_by_server: bool = False):
        self._h = handle
        self._closed = False
        self._server_owned = owned_by_server

    # -- lifecycle

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _check_not_closed(self):
        if self._closed:
            raise ArcadeDBError("Database is closed")

    def close(self):
        if self._closed:
            return
        if self._server_owned:
            # owned by the server: the engine refuses the close, and this handle is done either way
            self._closed = True
            return
        try:
            _call("Failed to close database", "arcadedb_n_close", self._h, 0)
        finally:
            self._closed = True

    def drop(self):
        self._check_not_closed()
        _call("Failed to drop database", "arcadedb_n_close", self._h, 1)
        self._closed = True

    def __del__(self):
        try:
            self.close()
        except Exception:  # nosec B110
            return

    def _info(self) -> dict:
        return _call("Failed to read the database", "arcadedb_n_info", self._h)

    def is_open(self) -> bool:
        return not self._closed and self._info()["open"]

    def get_name(self) -> str:
        self._check_not_closed()
        return self._info()["name"]

    def get_database_path(self) -> str:
        self._check_not_closed()
        return self._info()["path"]

    def is_read_only(self) -> bool:
        self._check_not_closed()
        return self._info()["mode"] == "READ_ONLY"

    # -- statements

    def _exec(
        self, flags: int, prefix: str, language: str, command: str, args
    ) -> NativeResultSet:
        self._check_not_closed()
        # phase 7 (arcadedb_n_exec flags): 2 = a command's rows are pulled but encoded only when read, 4 = float arrays come back as a float32 tail
        if flags & 1 and _LAZY_COMMAND_ROWS:
            flags |= 2
        if _BINARY_REPLY:
            flags |= 4
        if lib.BINARY_PARAMS:
            text, buf, count = encode_params(args, binary=True)
            if buf is not None:
                raw, floats = lib.call_bin(
                    "arcadedb_n_exec_bin",
                    self._h,
                    flags,
                    lib.b(language),
                    lib.b(command),
                    lib.b(text),
                    _FIRST_BATCH,
                    buf,
                    count,
                )
            else:
                raw, floats = lib.call_bin(
                    "arcadedb_n_exec",
                    self._h,
                    flags,
                    lib.b(language),
                    lib.b(command),
                    lib.b(text),
                    _FIRST_BATCH,
                )
        else:
            raw, floats = lib.call_bin(
                "arcadedb_n_exec",
                self._h,
                flags,
                lib.b(language),
                lib.b(command),
                lib.b(encode_params(args)),
                _FIRST_BATCH,
            )
        reply = loads(raw, floats)
        if not reply.get("ok"):
            raise _error(prefix, reply)
        return NativeResultSet(self, reply)

    def query(self, language: str, command: str, *args) -> NativeResultSet:
        """Run a read statement. Parameters bind as on the JPype path (``?`` positional, ``:name`` from one dict)."""
        return self._exec(0, "Query failed", language, command, args)

    def command(self, language: str, command: str, *args) -> NativeResultSet:
        """Run a statement that may write."""
        return self._exec(1, "Command failed", language, command, args)

    # -- transactions

    def _tx(self, op: int, prefix: str) -> dict:
        self._check_not_closed()
        return _call(prefix, "arcadedb_n_tx", self._h, op)

    def begin(self):
        self._tx(0, "Failed to begin transaction")

    def commit(self):
        self._tx(1, "Failed to commit transaction")

    def rollback(self):
        self._tx(2, "Failed to rollback transaction")

    def transaction(self) -> TransactionContext:
        return TransactionContext(self)

    def is_transaction_active(self) -> bool:
        return self._tx(3, "Failed to check transaction status")["active"]

    def _transaction_stack_mark(self):
        state = self._tx(3, "Failed to read the transaction state")
        return state["active"], state["depth"]

    def _end_transactions_opened_since(self, mark):
        was_active, depth_before = mark
        first_error = None
        state = self._tx(3, "Failed to read the transaction state")
        for _ in range(state["depth"] - depth_before):
            if not self.is_transaction_active():
                break
            try:
                self.rollback()
            except Exception as e:
                first_error = first_error or e
        if not was_active and self.is_transaction_active():
            try:
                self.rollback()
            except Exception as e:
                first_error = first_error or e
        if first_error is not None:
            raise first_error

    def run_in_transaction(self, fn, retries: int = 12, backoff_s: float = 0.005):
        """``fn`` inside a transaction, retried on NeedRetry conflicts (see the JPype ``Database.run_in_transaction``)."""
        duplicated_key_retried = False
        for attempt in range(retries + 1):
            mark = self._transaction_stack_mark()
            commits_at_start = None
            try:
                self.begin()
                commits_at_start = self._tx(3, "Failed to read the transaction state")[
                    "commits"
                ]
                result = fn()
                self.commit()
                return result
            except BaseException as e:
                try:
                    self._end_transactions_opened_since(mark)
                except Exception:  # nosec B110
                    pass
                if attempt >= retries or not isinstance(e, Exception):
                    raise
                reply = getattr(e, "native", None) or {}
                kind = reply.get("retry")
                if kind is None:
                    raise
                if kind == "duplicated_key":
                    if duplicated_key_retried:
                        raise
                    duplicated_key_retried = True
                if commits_at_start is not None:
                    try:
                        if (
                            self._tx(3, "Failed to read the transaction state")[
                                "commits"
                            ]
                            != commits_at_start
                        ):
                            raise
                    except ArcadeDBError:
                        pass
                _time.sleep(
                    max(backoff_s * (attempt + 1), reply.get("retry_ms", 0) / 1000.0)
                )

    # -- small helpers over statements (DSL-first: no Java record objects)

    def count_type(self, type_name: str) -> int:
        self._check_not_closed()
        try:
            row = self.query("sql", f"SELECT count(*) AS c FROM `{type_name}`").first()
        except ArcadeDBError as e:
            if "was not found" in str(e):
                return 0
            raise ArcadeDBError(f"Failed to count type '{type_name}': {e}") from e
        return int(row.get("c")) if row is not None else 0

    def lookup_by_rid(self, rid: str):
        """The record at ``rid`` as a Document, Vertex or Edge wrapper."""
        self._check_not_closed()
        row = self.query("sql", f"SELECT FROM {rid}").first()
        if row is None:
            raise ArcadeDBError(f"Failed to lookup RID '{rid}': record not found")
        return row.get_element()

    def lookup_by_key(self, type_name: str, keys: List[str], values: List[Any]):
        self._check_not_closed()
        where = " AND ".join(f"`{k}` = ?" for k in keys)
        try:
            row = self.query(
                "sql", f"SELECT FROM `{type_name}` WHERE {where} LIMIT 1", list(values)
            ).first()
            return row.get_element() if row is not None else None
        except ArcadeDBError as e:
            raise ArcadeDBError(f"Failed to lookup by key in '{type_name}': {e}") from e

    def insert_many(
        self, type_name: str, rows, commit_every: int = 10_000, parallel: bool = False
    ) -> int:
        """Bulk insert through ``INSERT INTO t CONTENT :row``. Inside the caller's transaction nothing is committed;
        otherwise every ``commit_every`` rows are one transaction (0: all rows in one).
        """
        self._check_not_closed()
        if parallel:
            not_yet("insert_many(parallel=True) (the async executor)")
        sql = f"INSERT INTO `{type_name}` CONTENT :row"
        total = 0
        if self.is_transaction_active():
            for row in rows:
                self.command("sql", sql, {"row": row}).close()
                total += 1
            return total
        every = int(commit_every)
        batch: List[dict] = []

        def flush():
            nonlocal total
            if batch:
                with self.transaction():
                    for row in batch:
                        self.command("sql", sql, {"row": row}).close()
                total += len(batch)
                batch.clear()

        for row in rows:
            batch.append(row)
            if every > 0 and len(batch) >= every:
                flush()
        flush()
        return total

    # -- not on native yet

    def get_java_database(self):
        not_yet("get_java_database")

    def new_vertex(self, type_name: str):
        """A vertex that is created by ``save()`` (``CREATE VERTEX .. CONTENT``)."""
        from .records import Vertex

        self._check_not_closed()
        return Vertex(self, type_name)

    def new_document(self, type_name: str):
        """A document that is created by ``save()`` (``INSERT INTO .. CONTENT``)."""
        from .records import Document

        self._check_not_closed()
        return Document(self, type_name)

    def graph_batch(self, *args, **kwargs):
        not_yet("GraphBatch")

    def async_executor(self, *args, **kwargs):
        not_yet("AsyncExecutor")

    @property
    def schema(self):
        """DDL helpers over SQL statements (the DSL-first subset); everything else is not on native yet."""
        self._check_not_closed()
        return NativeSchema(self)

    def create_vector_index(self, *args, **kwargs):
        not_yet("Database.create_vector_index (use CREATE INDEX ... LSM_VECTOR)")

    def import_documents(self, *args, **kwargs):
        not_yet("Database.import_documents")

    def export_database(self, *args, **kwargs):
        not_yet("Database.export_database (use EXPORT DATABASE)")

    def export_to_csv(self, *args, **kwargs):
        not_yet("Database.export_to_csv")

    def insert_columns(
        self, type_name, columns, commit_every: int = 10_000, parallel: bool = False
    ) -> int:
        """Bulk insert from whole columns (dict of name -> numpy array or list), as rows through :meth:`insert_many`."""
        names = list(columns)
        if not names:
            raise ValueError("insert_columns needs at least one column")
        if not all(isinstance(n, str) for n in names):
            raise ValueError("insert_columns: column names must be strings")
        if not parallel:
            from .bulk import insert_columns_fast

            done = insert_columns_fast(self, type_name, columns, commit_every)
            if done is not None:
                return done
        data = [
            c.tolist() if hasattr(c, "tolist") else list(c) for c in columns.values()
        ]
        lengths = {len(c) for c in data}
        if len(lengths) > 1:
            raise ValueError(
                f"insert_columns: columns differ in length: {sorted(lengths)}"
            )
        rows = (dict(zip(names, vals)) for vals in zip(*data))
        return self.insert_many(type_name, rows, commit_every, parallel)

    def insert_dataframe(
        self, type_name, df, *, batch_size: int = 10_000, parallel: bool = False
    ) -> int:
        """A pandas or Polars DataFrame as rows (NaN and NaT are nulls) through :meth:`insert_many`."""
        records = df.to_dicts() if hasattr(df, "to_dicts") else df.to_dict("records")
        rows = ({k: (None if v != v else v) for k, v in r.items()} for r in records)
        return self.insert_many(type_name, rows, batch_size, parallel)

    def insert_arrow(
        self, type_name, table, *, batch_size: int = 10_000, parallel: bool = False
    ) -> int:
        """An Arrow table as rows through :meth:`insert_many`."""
        return self.insert_many(type_name, table.to_pylist(), batch_size, parallel)

    def set_wal_flush(self, *args, **kwargs):
        not_yet("Database.set_wal_flush")

    def set_read_your_writes(self, *args, **kwargs):
        not_yet("Database.set_read_your_writes")

    def is_read_your_writes(self, *args, **kwargs):
        not_yet("Database.is_read_your_writes")

    def set_auto_transaction(self, *args, **kwargs):
        not_yet("Database.set_auto_transaction")


class _JavaObject:
    """What the JPype Schema returns where the native one has no Java object: any use says so."""

    def __bool__(self):
        return True

    def __getattr__(self, name):
        not_yet(f"the Java object a Schema method returns ({name})")


class NativeSchema:
    """Type, property and index creation as SQL statements. Returns None where the JPype Schema returns a Java object."""

    def __init__(self, db):
        self._db = db

    def _run(self, sql):
        self._db.command("sql", sql).close()

    def _type(self, kind, name, buckets, if_not_exists=False):
        ine = " IF NOT EXISTS" if if_not_exists else ""
        suffix = f" BUCKETS {int(buckets)}" if buckets else ""
        self._run(f"CREATE {kind} TYPE `{name}`{ine}{suffix}")
        return _JavaObject()

    def create_document_type(self, name, buckets=None):
        return self._type("DOCUMENT", name, buckets)

    def create_vertex_type(self, name, buckets=None):
        return self._type("VERTEX", name, buckets)

    def create_edge_type(self, name, buckets=None):
        return self._type("EDGE", name, buckets)

    def get_or_create_document_type(self, name, buckets=None):
        return self._type("DOCUMENT", name, buckets, True)

    def get_or_create_vertex_type(self, name, buckets=None):
        return self._type("VERTEX", name, buckets, True)

    def get_or_create_edge_type(self, name, buckets=None):
        return self._type("EDGE", name, buckets, True)

    def exists_type(self, name):
        rows = self._db.query(
            "sql", "SELECT FROM schema:types WHERE name = ?", name
        ).to_list()
        return bool(rows)

    def drop_type(self, name):
        self._run(f"DROP TYPE `{name}`")

    def create_property(self, type_name, property_name, property_type, of_type=None):
        t = getattr(property_type, "value", property_type)
        o = f" OF {getattr(of_type, 'value', of_type)}" if of_type else ""
        self._run(f"CREATE PROPERTY `{type_name}`.`{property_name}` {t}{o}")
        return _JavaObject()

    def get_or_create_property(
        self, type_name, property_name, property_type, of_type=None
    ):
        t = getattr(property_type, "value", property_type)
        o = f" OF {getattr(of_type, 'value', of_type)}" if of_type else ""
        self._run(
            f"CREATE PROPERTY `{type_name}`.`{property_name}` IF NOT EXISTS {t}{o}"
        )
        return _JavaObject()

    def drop_property(self, type_name, property_name):
        self._run(f"DROP PROPERTY `{type_name}`.`{property_name}`")

    _INDEX_KIND = {
        ("LSM_TREE", True): "UNIQUE",
        ("LSM_TREE", False): "NOTUNIQUE",
        ("HASH", True): "UNIQUE_HASH",
        ("HASH", False): "NOTUNIQUE_HASH",
    }

    def create_index(
        self, type_name, property_names, unique=False, index_type="LSM_TREE"
    ):
        kind = getattr(index_type, "value", index_type)
        kind = self._INDEX_KIND.get((kind, bool(unique)), kind)
        cols = ", ".join(f"`{p}`" for p in property_names)
        self._run(f"CREATE INDEX ON `{type_name}` ({cols}) {kind}")
        return _JavaObject()

    def exists_index(self, index_name):
        return bool(
            self._db.query(
                "sql", "SELECT FROM schema:indexes WHERE name = ?", index_name
            ).to_list()
        )

    def drop_index(self, index_name, force=False):
        self._run(f"DROP INDEX `{index_name}`")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        not_yet(f"Schema.{name} (returns Java objects)")


class NativeDatabaseFactory:
    """Create/open databases by path."""

    def __init__(self, path: str, jvm_kwargs: Optional[dict] = None):
        if jvm_kwargs:
            import logging

            logging.getLogger("arcadedb_embedded").warning(
                "jvm_kwargs %s ignored: the native backend has no JVM",
                sorted(jvm_kwargs),
            )
        self._path = os.fspath(path)

    def create(self) -> NativeDatabase:
        return NativeDatabase(
            _call("Failed to create database", "arcadedb_n_open", lib.b(self._path), 0)[
                "h"
            ]
        )

    def open(self, read_only: bool = False) -> NativeDatabase:
        mode = 2 if read_only else 1
        return NativeDatabase(
            _call(
                "Failed to open database", "arcadedb_n_open", lib.b(self._path), mode
            )["h"]
        )

    def exists(self) -> bool:
        return _call(
            "Failed to check if database exists",
            "arcadedb_n_open",
            lib.b(self._path),
            3,
        )["exists"]
