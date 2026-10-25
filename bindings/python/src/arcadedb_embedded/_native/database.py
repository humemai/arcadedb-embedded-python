"""NativeDatabase, NativeDatabaseFactory, NativeResultSet and NativeResult: the DSL-first core over libarcadedb."""

import itertools
import json
import os
import re
import time as _time
from collections import deque
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional

from ..exceptions import ArcadeDBError
from ..transactions import TransactionContext
from ..type_conversion import json_bulk_dumps
from . import lib, not_yet
from .bulk import insert_rows_columnar
from .codec import _default as codec_default
from .codec import _prep as _prep_row
from .codec import encode_params, json_native, loads

_LAZY_COMMAND_ROWS = os.environ.get("ARCADEDB_NATIVE_LAZY_CMD", "1") != "0"
_BINARY_REPLY = os.environ.get("ARCADEDB_NATIVE_BIN_REPLY", "1") != "0"
_INSERT_MANY_CHUNK = 10_000
_RID_RE = re.compile(r"#?-?\d+:-?\d+")
_FIRST_BATCH = 256
_EPOCH_DAY_ORDINAL = date(1970, 1, 1).toordinal()
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
        for key, value in self._props.items():
            if isinstance(value, date) and not isinstance(value, datetime):
                out[key] = (
                    value.toordinal() - _EPOCH_DAY_ORDINAL
                )  # as the engine writes a DATE property: days since the epoch
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

    @classmethod
    def _lazy(cls, database, rs_id: int) -> "NativeResultSet":
        """The result of arcadedb_n_cmd: a cursor id and nothing read yet (id 0: no cursor)."""
        self = cls.__new__(cls)
        self._database = database
        self._rs = rs_id
        self._buf = deque()
        self._more = rs_id > 0
        self._closed = False
        self._exhausted = False
        self._pending_error = None
        return self

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
                lib.close_rs(self._rs)
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
                "polars is required for to_polars(). "
                "Install with: pip install 'arcadedb-embedded[polars]'"
            ) from exc
        table = self.to_arrow(batch_size, columns)
        if table is None:
            raise ImportError(
                "to_polars() reads through Arrow, which needs pyarrow and numpy. "
                "Install with: pip install 'arcadedb-embedded[polars]'"
            )
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
        self._async_executors: list = []
        self._vector_meta: dict = {}
        self._vector_dimensions: dict = {}
        self._vector_id_properties: dict = {}

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
        self._close_async_executors()
        if self._server_owned:
            # owned by the server: the engine refuses the close, and this handle is done either way
            self._closed = True
            return
        try:
            lib.flush_closes()
            _call("Failed to close database", "arcadedb_n_close", self._h, 0)
        finally:
            self._closed = True

    def _discard_async_executor(self, executor) -> None:
        try:
            self._async_executors.remove(executor)
        except ValueError:
            pass

    def _close_async_executors(self):
        first_error = None
        while self._async_executors:
            executor = self._async_executors.pop()
            try:
                executor.close()
            except Exception as e:
                first_error = first_error or ArcadeDBError(
                    f"Failed to close async executor: {e}"
                )
        if first_error is not None:
            raise first_error

    def drop(self):
        self._check_not_closed()
        lib.flush_closes()
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
        if flags & 1 and _LAZY_COMMAND_ROWS and lib.CMD_PATH:
            # phase 8: the cursor id comes back as a long (no reply text to free and decode); the rows are read late or never
            text, buf, count = encode_params(args, binary=True)
            rid = lib.cmd(
                self._h,
                1,
                lib.bc(language),
                lib.bc(command),
                lib.bc(text),
                buf,
                count,
                _FIRST_BATCH,
            )
            if rid < 0:
                raise _error(prefix, json.loads(lib.last_error()))
            return NativeResultSet._lazy(self, rid)
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
        if (op == 1 or op == 2) and lib.CLOSE_BATCH:
            lib.flush_closes()
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

    def _transaction_commit_mark(self):
        """The commit count of the current transaction (the witness that a BATCH boundary published part of its work)."""
        return self._tx(3, "Failed to read the transaction state")["commits"]

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
                commits_at_start = self._transaction_commit_mark()
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
                        if self._transaction_commit_mark() != commits_at_start:
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
            count_sql = f"SELECT count(*) AS c FROM `{type_name}`"  # nosec B608 - backtick-quoted schema identifier, no values
            row = self.query("sql", count_sql).first()
        except ArcadeDBError as e:
            if "was not found" in str(e):
                return 0
            raise ArcadeDBError(f"Failed to count type '{type_name}': {e}") from e
        return int(row.get("c")) if row is not None else 0

    def lookup_by_rid(self, rid: str):
        """The record at ``rid`` as a Document, Vertex or Edge wrapper."""
        self._check_not_closed()
        if not _RID_RE.fullmatch(str(rid)):
            raise ArcadeDBError(f"Failed to lookup RID '{rid}': not a record id")
        rid_sql = f"SELECT FROM {rid}"  # nosec B608 - rid matched _RID_RE above
        row = self.query("sql", rid_sql).first()
        if row is None:
            raise ArcadeDBError(f"Failed to lookup RID '{rid}': record not found")
        return row.get_element()

    def lookup_by_key(self, type_name: str, keys: List[str], values: List[Any]):
        self._check_not_closed()
        where = " AND ".join(f"`{k}` = ?" for k in keys)
        try:
            lookup_sql = f"SELECT FROM `{type_name}` WHERE {where} LIMIT 1"  # nosec B608 - backtick-quoted identifiers; values go through ? parameters
            row = self.query("sql", lookup_sql, list(values)).first()
            return row.get_element() if row is not None else None
        except ArcadeDBError as e:
            raise ArcadeDBError(f"Failed to lookup by key in '{type_name}': {e}") from e

    def insert_many(
        self, type_name: str, rows, commit_every: int = 10_000, parallel: bool = False
    ) -> int:
        """Bulk insert. Rows go in chunks of 10,000, one crossing per chunk. A chunk of rows with the same keys whose columns each hold one
        value type (ints, floats, bools, strings, equal-length float lists for an ``ARRAY_OF_FLOATS`` property; None is a null) goes as
        columns by address (``arcadedb_n_insert_colp``, no JSON text); any other chunk goes as one JSON text (``arcadedb_n_insert_rows``:
        a newDocument/set/save loop inside the image, as ``DocumentBatcher.insertManyJson`` on the JPype path); a chunk with a value the
        JSON text cannot carry unchanged goes through ``INSERT INTO t CONTENT :row`` for each row, in one crossing. Inside the caller's
        transaction nothing is committed; otherwise every ``commit_every`` rows are one transaction (0: all rows in one).
        """
        self._check_not_closed()
        if parallel:
            return self._insert_many_parallel(type_name, rows)
        sql = f"INSERT INTO `{type_name}` CONTENT :row"
        rows = iter(rows)
        was_active = self.is_transaction_active()
        every = int(commit_every)
        n = 0
        try:
            if not was_active:
                self.begin()
            while True:
                size = _INSERT_MANY_CHUNK
                if not was_active and every > 0:
                    size = min(size, every - n % every)
                chunk = list(itertools.islice(rows, size))
                if not chunk:
                    break
                self._insert_chunk(type_name, sql, chunk)
                n += len(chunk)
                if not was_active and every > 0 and n % every == 0:
                    self.commit()
                    self.begin()
            if not was_active:
                self.commit()
            return n
        except BaseException:
            if not was_active:
                try:
                    if self.is_transaction_active():
                        self.rollback()
                except Exception:  # nosec B110 - best-effort rollback
                    pass
            raise

    def _insert_chunk(self, type_name: str, sql: str, chunk) -> None:
        if lib.INSERT_ROWS:
            if insert_rows_columnar(self, type_name, chunk):
                return
            try:
                payload = json_bulk_dumps(chunk)
            except (TypeError, ValueError):
                payload = None
            if payload is not None:
                reply = json.loads(
                    lib.call(
                        "arcadedb_n_insert_rows",
                        self._h,
                        lib.b(type_name),
                        lib.b(payload),
                    )
                )
                if not reply.get("ok"):
                    raise _error(f"Failed to bulk-insert into '{type_name}'", reply)
                return
        if lib.EXEC_MANY:
            # values JSON text cannot carry unchanged (a date-time, a decimal, NaN, a big integer): the same statement per
            # row, but all rows of the chunk in one crossing (arcadedb_n_exec_many), not one call per row
            self._command_many("sql", sql, [{"row": row} for row in chunk])
            return
        for row in chunk:
            self.command("sql", sql, {"row": row}).close()

    def _command_many(self, language: str, command: str, rows) -> int:
        """Experimental (phase 8): the statement once per row of ``rows`` (each a list of positional values or a dict of named values),
        all in one crossing and in the open transaction; the cursors are drained and closed. Not part of the public API.
        """
        self._check_not_closed()
        payload = json.dumps([_prep_row(r) for r in rows], default=codec_default)
        reply = json.loads(
            lib.call(
                "arcadedb_n_exec_many",
                self._h,
                lib.b(language),
                lib.b(command),
                lib.b(payload),
            )
        )
        if not reply.get("ok"):
            raise _error("Command failed", reply)
        return reply["n"]

    def _parallel_load_failed(self, type_name, error) -> ArcadeDBError:
        """The error for a parallel load that failed while handing rows to the writers: waits for the queue to drain first, so
        the caller sees a final state, and says that the rows handed over before the failure may have been stored.
        """
        try:
            self._async().wait_completion()
        except Exception:  # nosec B110 - the original error is the one to report
            pass
        text = str(error)
        prefix = "Failed to bulk-insert: "
        if text.startswith(prefix):
            text = text[len(prefix) :]
        return ArcadeDBError(
            f"Failed to bulk-insert into '{type_name}': {text}; the rows handed to the "
            f"parallel writers before the failure may have been stored (the call waited "
            f"for them before raising)"
        )

    def _insert_many_parallel(self, type_name, rows) -> int:
        """insert_many(parallel=True): chunks go to the async writers; the failure count is read after the final wait."""
        import itertools

        from . import extras

        iterator = iter(rows)
        tokens, n = [], 0
        try:
            while True:
                chunk = list(itertools.islice(iterator, 10_000))
                if not chunk:
                    break
                try:
                    tokens.append(extras.insert_parallel(self, type_name, chunk)["fid"])
                except ArcadeDBError as e:
                    # as the JPype path: the rows handed to the writers before the failure are written whatever this call does
                    raise self._parallel_load_failed(type_name, e) from e
                n += len(chunk)
        except ArcadeDBError:
            raise
        except BaseException:
            try:
                self._async().wait_completion()
            except Exception:  # nosec B110 - the original error is the one to report
                pass
            raise
        try:
            self._async().wait_completion()
        except Exception as e:
            raise ArcadeDBError(f"Failed to bulk-insert into '{type_name}': {e}") from e
        n_failed, first = 0, None
        for token in tokens:
            result = extras.failures(self, token)
            if result["count"] and first is None:
                first = result["first"]
            n_failed += result["count"]
        if n_failed:
            raise ArcadeDBError(
                f"Failed to bulk-insert into '{type_name}': the parallel writers reported {n_failed} failed record(s) "
                f"of {n}; the rest may have been stored (first failure: {first})"
            )
        return n

    def _kind_of(self, type_name):
        """'v', 'e' or 'd' for a type (cached): which wrapper a record of that type gets."""
        kinds = self.__dict__.setdefault("_type_kinds", {})
        if type_name not in kinds:
            row = self.query(
                "sql", "SELECT type FROM schema:types WHERE name = ?", type_name
            ).first()
            kinds[type_name] = {"vertex": "v", "edge": "e"}.get(
                row.get("type") if row else None, "d"
            )
        return kinds[type_name]

    def _async(self):
        from .extras import NativeAsyncExecutor

        return NativeAsyncExecutor(self)

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

    def graph_batch(self, **options):
        """A GraphBatch for bulk graph loads (keywords as :meth:`Database.graph_batch`)."""
        from .extras import NativeGraphBatch

        self._check_not_closed()
        return NativeGraphBatch.create(self, **options)

    def async_executor(self):
        """The database's async executor."""
        from .extras import NativeAsyncExecutor

        self._check_not_closed()
        executor = NativeAsyncExecutor(self)
        self._async_executors.append(executor)
        return executor

    def register_function(self, name, fn, min_args=0, max_args=-1):
        """Make a Python callable available to SQL (process-wide, see ``extras.register_function``)."""
        from .extras import register_function

        register_function(name, fn, min_args, max_args)

    @property
    def schema(self):
        """DDL helpers over SQL statements (the DSL-first subset); everything else is not on native yet."""
        self._check_not_closed()
        return NativeSchema(self)

    def create_vector_index(
        self,
        vertex_type,
        vector_property,
        dimensions,
        id_property=None,
        distance_function="cosine",
        max_connections=32,
        beam_width=100,
        quantization="INT8",
        encoding=None,
        location_cache_size=None,
        graph_build_cache_size=None,
        mutations_before_rebuild=None,
        store_vectors_in_graph=False,
        add_hierarchy=True,
        pq_subspaces=None,
        pq_clusters=None,
        pq_center_globally=None,
        pq_training_limit=None,
        build_graph_now=True,
    ):
        """A vector index (``CREATE INDEX .. LSM_VECTOR``) and its :class:`VectorIndex` wrapper; arguments as the JPype path."""
        from .schema_objects import create_vector_index

        self._check_not_closed()
        if location_cache_size is not None:
            raise ValueError(
                "location_cache_size is no longer supported (ArcadeDB issues #5559 and #5568): a vector location is the only "
                "mapping from a vector id to its record, so capping the location index drops vectors from searches and from "
                "countEntries() instead of spilling them to disk. Remove the argument and size the heap for the live vector "
                "set instead."
            )
        return create_vector_index(
            self,
            vertex_type,
            vector_property,
            dimensions,
            id_property,
            distance_function,
            max_connections,
            beam_width,
            quantization,
            encoding,
            graph_build_cache_size,
            mutations_before_rebuild,
            store_vectors_in_graph,
            add_hierarchy,
            pq_subspaces,
            pq_clusters,
            pq_center_globally,
            pq_training_limit,
            build_graph_now,
        )

    def import_documents(
        self,
        source,
        document_type: str = "Document",
        *,
        file_type=None,
        delimiter=None,
        header=None,
        skip_entries=None,
        properties_include=None,
        commit_every=None,
        parallel=None,
        wal=None,
        verbose_level=None,
        probe_only=None,
        force_database_create=None,
        trim_text=None,
        on_row_error=None,
        extra_settings=None,
    ):
        """Import document-shaped files (CSV, JSON, ...) through the engine's importer; same arguments as the JPype path."""
        from ..importer import (
            ImportResult,
            _build_import_settings,
            normalize_import_source,
        )
        from . import extras

        self._check_not_closed()
        source_url = normalize_import_source(source)
        settings = _build_import_settings(
            source_url,
            document_type=document_type,
            file_type=file_type,
            delimiter=delimiter,
            header=header,
            skip_entries=skip_entries,
            properties_include=properties_include,
            commit_every=commit_every,
            parallel=parallel,
            wal=wal,
            verbose_level=verbose_level,
            probe_only=probe_only,
            force_database_create=force_database_create,
            trim_text=trim_text,
            on_row_error=on_row_error,
            extra_settings=extra_settings,
        )
        try:
            stats = extras.run_import(self, settings, parallel, commit_every, wal)
            return ImportResult(
                result="PROBE_ONLY" if probe_only and stats is None else "OK",
                operation="import documents",
                source_url=source_url,
                statistics=stats or {},
            )
        except Exception as e:
            raise ArcadeDBError(f"Document import failed: {e}") from e

    def export_database(
        self,
        file_path,
        format: str = "jsonl",
        overwrite: bool = False,
        include_types=None,
        exclude_types=None,
        verbose: int = 1,
    ) -> dict:
        self._check_not_closed()
        from ..exporter import export_database

        return export_database(
            self, file_path, format, overwrite, include_types, exclude_types, verbose
        )

    def export_to_csv(
        self, query: str, file_path: str, language: str = "sql", fieldnames=None
    ):
        self._check_not_closed()
        from ..exporter import export_to_csv

        export_to_csv(self.query(language, query), file_path, fieldnames)

    def insert_columns(
        self, type_name, columns, commit_every: int = 10_000, parallel: bool = False
    ) -> int:
        """Bulk insert from whole columns (dict of name -> numpy array or list), as rows through :meth:`insert_many`."""
        self._check_not_closed()
        items = list(columns.items()) if hasattr(columns, "items") else None
        if not items:
            raise ValueError("insert_columns needs at least one column")
        for name, values in items:
            if not isinstance(name, str):
                raise ValueError(f"column names must be strings, got {name!r}")
            if isinstance(values, (str, bytes, bytearray)):
                raise TypeError(
                    f"column {name!r} is a {type(values).__name__}, not a sequence of values; "
                    f"wrap a single value in a list"
                )
        known = {n: len(v) for n, v in items if hasattr(v, "__len__")}
        if len(set(known.values())) > 1:
            raise ValueError(f"columns differ in length: {known}")
        if not parallel:
            from .bulk import insert_columns_fast

            done = insert_columns_fast(self, type_name, columns, commit_every)
            if done is not None:
                return done
        names = [n for n, _ in items]
        data = [_column_values(n, v) for n, v in items]
        lengths = {n: len(c) for n, c in zip(names, data)}
        if len(set(lengths.values())) != 1:
            raise ValueError(f"columns differ in length: {lengths}")
        if not data[0]:
            return 0
        rows = (dict(zip(names, vals)) for vals in zip(*data))
        return self.insert_many(type_name, rows, commit_every, parallel)

    def insert_dataframe(
        self, type_name, df, *, batch_size: int = 10_000, parallel: bool = False
    ) -> int:
        """A pandas or Polars DataFrame into a type, in batches: the strict Arrow loading of ``Database.insert_dataframe``
        (dtype refusals, declared types, NaN rules, the committed-rows message), batches through :meth:`insert_many` for a
        document type and ``GraphBatch.create_vertices`` for a vertex type (``arcadedb_embedded/dataframe.py``).
        """
        from ..dataframe import insert_table, to_arrow_table

        self._check_not_closed()
        table = to_arrow_table(df, what="insert_dataframe()")
        return insert_table(
            self,
            type_name,
            table,
            batch_size=batch_size,
            parallel=parallel,
            what="insert_dataframe()",
        )

    def insert_arrow(
        self, type_name, table, *, batch_size: int = 10_000, parallel: bool = False
    ) -> int:
        """An Arrow table (or ``RecordBatch``, ``RecordBatchReader``, Arrow PyCapsule object) into a type, in batches; as
        :meth:`insert_dataframe`.
        """
        from ..dataframe import insert_table, to_arrow_table

        self._check_not_closed()
        arrow_table = to_arrow_table(table, what="insert_arrow()")
        return insert_table(
            self,
            type_name,
            arrow_table,
            batch_size=batch_size,
            parallel=parallel,
            what="insert_arrow()",
        )

    def set_wal_flush(self, mode: str):
        self._check_not_closed()
        valid = {"no": "NO", "yes_nometadata": "YES_NOMETADATA", "yes_full": "YES_FULL"}
        if mode not in valid:
            raise ValueError(
                f"Invalid WAL flush mode: {mode}. Must be one of: {list(valid)}"
            )
        from .extras import db_set

        try:
            db_set(self, "wal_flush", valid[mode])
        except ArcadeDBError as e:
            raise ArcadeDBError(f"Failed to set WAL flush mode: {e}") from e

    def set_read_your_writes(self, enabled: bool):
        self._check_not_closed()
        from .extras import db_set

        db_set(self, "read_your_writes", "true" if enabled else "false")

    def is_read_your_writes(self) -> bool:
        self._check_not_closed()
        from .extras import db_set

        return bool(db_set(self, "read_your_writes")["v"])

    def set_auto_transaction(self, enabled: bool):
        self._check_not_closed()
        from .extras import db_set

        db_set(self, "auto_transaction", "true" if enabled else "false")


def _column_values(name, values):
    """One ``insert_columns`` column as a list of Python values, with the JPype path's refusals (a dtype that does not
    cross, a value beyond the 64-bit signed range, a column that is not one-dimensional).
    """
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None
    if hasattr(values, "to_numpy") and not isinstance(values, (list, tuple)):
        dtype = getattr(values, "dtype", None)
        if np is not None and isinstance(dtype, np.dtype):
            values = values.to_numpy()
        else:  # a pandas extension dtype (Int64, string, boolean, category): its <NA> is a null
            values = values.to_numpy(dtype=object, na_value=None)
    if np is not None and isinstance(values, np.ndarray):
        if values.ndim != 1:
            raise ValueError(
                f"column {name!r} is {values.ndim}-dimensional; a column is one-dimensional"
            )
        kind = values.dtype.kind
        if kind == "u" and values.size and int(values.max()) > np.iinfo(np.int64).max:
            raise ValueError(
                f"column {name!r} holds a value beyond the 64-bit signed range"
            )
        if kind in "MmcV":
            raise TypeError(
                f"column {name!r} has dtype {values.dtype}, which does not cross natively; "
                "convert it to Python values or use insert_many"
            )
        return values.tolist()
    return list(values)


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

    # -- reads, as small objects with the engine's accessors (schema_objects.py)

    def get_type(self, name):
        from .schema_objects import NativeType

        rows = self._db.query(
            "sql", "SELECT FROM schema:types WHERE name = ?", name
        ).to_list()
        return NativeType(rows[0]) if rows else None

    def get_types(self):
        from .schema_objects import NativeType

        return [
            NativeType(r)
            for r in self._db.query("sql", "SELECT FROM schema:types").to_list()
        ]

    def get_indexes(self):
        from .schema_objects import NativeIndex

        return [
            NativeIndex(r)
            for r in self._db.query("sql", "SELECT FROM schema:indexes").to_list()
        ]

    def get_index_by_name(self, index_name):
        from .schema_objects import NativeIndex

        rows = self._db.query(
            "sql", "SELECT FROM schema:indexes WHERE name = ?", index_name
        ).to_list()
        return NativeIndex(rows[0]) if rows else None

    def get_or_create_index(
        self, type_name, property_names, unique=False, index_type="LSM_TREE"
    ):
        kind = getattr(index_type, "value", index_type)
        kind = self._INDEX_KIND.get((kind, bool(unique)), kind)
        cols = ", ".join(f"`{p}`" for p in property_names)
        try:
            self._run(f"CREATE INDEX IF NOT EXISTS ON `{type_name}` ({cols}) {kind}")
        except ArcadeDBError as e:
            raise ArcadeDBError(
                f"Failed to get/create index on '{type_name}[{','.join(property_names)}]': {e}"
            ) from e
        name = f"{type_name}[{','.join(property_names)}]"
        return self.get_index_by_name(name) or _JavaObject()

    def _vector_rows(self):
        # the type-level rows (named Type[prop]); the per-bucket rows carry a file id
        return [
            r
            for r in self._db.query(
                "sql", "SELECT FROM schema:indexes WHERE indexType = 'LSM_VECTOR'"
            ).to_list()
            if "[" in r["name"] and "fileId" not in r
        ]

    def get_vector_index(self, vertex_type, vector_property):
        from .schema_objects import NativeVectorIndex

        for r in self._vector_rows():
            if r["typeName"] == vertex_type and r["properties"] == [[vector_property]]:
                return NativeVectorIndex(
                    self._db, vertex_type, vector_property, r["name"]
                )
        return None

    def list_vector_indexes(self):
        return [r["name"] for r in self._vector_rows()]

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
