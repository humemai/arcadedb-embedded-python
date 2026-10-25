"""
ArcadeDB Python Bindings - DataFrame and Arrow ingest

Loads a pandas or Polars DataFrame, or an Arrow table, into a type in batches
(``Database.insert_dataframe`` and ``Database.insert_arrow``). Arrow is the one
internal form: a pandas frame becomes an Arrow table, a Polars frame is already
one, and each Arrow column becomes the typed array ``Database.insert_columns``
sends across the bridge (a document type), or the property rows
``GraphBatch.create_vertices`` takes (a vertex type). No Java was added: both
paths use the existing glue (``DocumentBatcher.insertColumns`` and the
``GraphBatch`` vertex batcher).

The native backend (``arcadedb-embedded-native``) shares everything but the
last step: the checks, the type mapping, the batching and the error wording are
the same code. A document batch goes over as one JSON text through
``Database.insert_many`` (one crossing per 10,000 rows), a vertex batch through
``GraphBatch.create_vertices``, and a value JSON cannot carry (a date-time, a
decimal, bytes) travels as a tagged value the image decodes.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import jpype

from .exceptions import ArcadeDBError

_PYARROW_HINT = (
    "pyarrow is required for {what}. Install with: pip install pyarrow "
    "(or pip install 'arcadedb-embedded[arrow]')"
)

# Declared property types (the engine's Type names) that an Arrow column kind
# loads into. The engine converts the value (an integer into a LONG or a
# DECIMAL, a list into an ARRAY_OF_FLOATS) and refuses what does not fit (a
# LONG past INTEGER's range). What it also does, silently, is truncate a float
# into an integer property and parse a string into a number, so the kinds that
# would lose or guess are refused here, before anything is written.
_DATETIMES = {"DATETIME", "DATETIME_SECOND", "DATETIME_MICROS", "DATETIME_NANOS"}
_ARRAYS = {
    "ARRAY_OF_SHORTS",
    "ARRAY_OF_INTEGERS",
    "ARRAY_OF_LONGS",
    "ARRAY_OF_FLOATS",
    "ARRAY_OF_DOUBLES",
}
_ALLOWED = {
    "integer": {
        "BYTE",
        "SHORT",
        "INTEGER",
        "LONG",
        "FLOAT",
        "DOUBLE",
        "DECIMAL",
        "STRING",
    },
    "floating": {"FLOAT", "DOUBLE", "DECIMAL", "STRING"},
    "bool": {"BOOLEAN", "STRING"},
    "string": {"STRING", "LINK"},
    "binary": {"BINARY"},
    "timestamp": _DATETIMES | {"STRING"},
    "date": {"DATE"} | _DATETIMES | {"STRING"},
    "decimal": {"DECIMAL", "DOUBLE", "FLOAT", "STRING"},
    "list": {"LIST"} | _ARRAYS,
    "struct": {"MAP", "EMBEDDED"},
}

# Python values per cross-bridge call. A batch is converted whole before it is written, so this bounds the extra
# memory a very large frame needs (10,000 matches insert_columns' commit_every).
DEFAULT_BATCH_SIZE = 10_000


def _import_pyarrow(what: str):
    try:
        import pyarrow as pa
    except ImportError as exc:
        raise ImportError(_PYARROW_HINT.format(what=what)) from exc
    return pa


def _kind(pa, arrow_type) -> Optional[str]:
    """The mapping family of an Arrow type, or None when it has no ArcadeDB mapping."""
    types = pa.types
    if types.is_dictionary(arrow_type):
        return _kind(pa, arrow_type.value_type)
    if types.is_integer(arrow_type):
        return "integer"
    if types.is_floating(arrow_type):
        return "floating"
    if types.is_boolean(arrow_type):
        return "bool"
    if (
        types.is_string(arrow_type)
        or types.is_large_string(arrow_type)
        or (hasattr(types, "is_string_view") and types.is_string_view(arrow_type))
    ):
        return "string"
    if types.is_binary(arrow_type) or types.is_large_binary(arrow_type):
        return "binary"
    if types.is_timestamp(arrow_type):
        return "timestamp"
    if types.is_date(arrow_type):
        return "date"
    if types.is_decimal(arrow_type):
        return "decimal"
    if (
        types.is_list(arrow_type)
        or types.is_large_list(arrow_type)
        or types.is_fixed_size_list(arrow_type)
    ):
        return "list"
    if types.is_struct(arrow_type):
        return "struct"
    if types.is_null(arrow_type):
        return "null"
    return None


def to_arrow_table(data, *, what: str):
    """Normalize a pandas or Polars DataFrame, or anything Arrow can read, to a ``pyarrow.Table``."""
    pa = _import_pyarrow(what)
    module = type(data).__module__.split(".")[0]
    if isinstance(data, pa.Table):
        return data
    if isinstance(data, pa.RecordBatch):
        return pa.Table.from_batches([data])
    if isinstance(data, pa.RecordBatchReader):
        return data.read_all()
    if module == "pandas" and hasattr(data, "columns"):
        names = list(data.columns)
        bad = [n for n in names if not isinstance(n, str)]
        if bad:
            raise ValueError(
                f"column names must be strings, got {bad[0]!r}; rename the columns first"
            )
        if len(set(names)) != len(names):
            raise ValueError("a DataFrame with duplicate column names cannot be loaded")
        # NaN in a float column is pandas' missing value: Arrow stores it as a null.
        return pa.Table.from_pandas(data, preserve_index=False)
    if module == "polars":
        if hasattr(data, "collect") and not hasattr(data, "to_arrow"):
            raise TypeError(
                "a Polars LazyFrame is not loaded as it is; call .collect() first"
            )
        return data.to_arrow()
    if hasattr(data, "__arrow_c_stream__") or hasattr(data, "__arrow_c_array__"):
        return pa.table(data)  # any library that speaks the Arrow PyCapsule interface
    raise TypeError(
        f"{what} takes a pandas or Polars DataFrame or an Arrow table, "
        f"not {type(data).__name__}"
    )


def _is_native(db) -> bool:
    """True for the native backend's database (no JVM: schema reads are SQL, values cross as tagged JSON)."""
    return not hasattr(db, "_java_db")


_PROPERTY = re.compile(r"name: (.+?), type: ([A-Z_]+)")


def _declared_types_native(
    db, type_name: str, names: List[str]
) -> Tuple[bool, Dict[str, str]]:
    """:func:`_declared_types` for the native backend: the ``schema:types`` rows, walking the parent types."""
    rows = {r["name"]: r for r in db.query("sql", "SELECT FROM schema:types").to_list()}
    row = rows.get(type_name)
    if row is None:
        raise ArcadeDBError(
            f"Cannot load into '{type_name}': the type does not exist "
            f"(create it first, with or without declared properties)"
        )
    kind = row.get("type")
    if kind == "edge":
        raise ArcadeDBError(
            f"Cannot load into '{type_name}': it is an edge type. Load the vertices, "
            f"then buffer the edges with graph_batch().new_edges()"
        )
    declared: Dict[str, str] = {}
    seen, queue = set(), [type_name]
    while queue:  # the type first, then its parents: the nearest declaration wins
        current = queue.pop(0)
        if current in seen or current not in rows:
            continue
        seen.add(current)
        for text in rows[current].get("properties") or []:
            m = _PROPERTY.search(text)
            if m and m.group(1) in names:
                declared.setdefault(m.group(1), m.group(2))
        queue.extend(rows[current].get("parentTypes") or [])
    return kind == "vertex", declared


def _declared_types(
    db, type_name: str, names: List[str]
) -> Tuple[bool, Dict[str, str]]:
    """``(is_vertex_type, {column: declared property type name})`` for the columns the type declares.

    Raises ArcadeDBError when the type does not exist or is an edge type.
    """
    if _is_native(db):
        return _declared_types_native(db, type_name, names)
    java_schema = db._java_db.getSchema()
    if not java_schema.existsType(type_name):
        raise ArcadeDBError(
            f"Cannot load into '{type_name}': the type does not exist "
            f"(create it first, with or without declared properties)"
        )
    java_type = java_schema.getType(type_name)
    if isinstance(java_type, jpype.JClass("com.arcadedb.schema.EdgeType")):
        raise ArcadeDBError(
            f"Cannot load into '{type_name}': it is an edge type. Load the vertices, "
            f"then buffer the edges with graph_batch().new_edges()"
        )
    is_vertex = isinstance(java_type, jpype.JClass("com.arcadedb.schema.VertexType"))
    declared = {}
    for name in names:
        prop = java_type.getPolymorphicPropertyIfExists(name)
        if prop is not None:
            declared[name] = str(prop.getType().name())
    return is_vertex, declared


def _check_declared(
    type_name: str, schema, kinds: Dict[str, str], declared: Dict[str, str]
):
    """Refuse a column whose Arrow kind does not load into the property type the type declares."""
    for name, declared_type in declared.items():
        kind = kinds[name]
        if kind == "null":
            continue  # nothing but nulls: any property accepts it
        if declared_type not in _ALLOWED[kind]:
            raise TypeError(
                f"column {name!r} has Arrow type {schema.field(name).type} but "
                f"'{type_name}.{name}' is declared {declared_type}; cast the column to a "
                f"matching type first (e.g. df[{name!r}].astype(...))"
            )


def _temporal_to_java(chunk, pa):
    """A timestamp or date chunk as a list of ``LocalDateTime``/``LocalDate``, keeping the unit's precision.

    DATETIME is a UTC wall clock: a timestamp with a zone is already UTC epoch time, and a timestamp without
    one is taken as the wall clock it shows (the same rule ``Document.set`` applies to a ``datetime``), so both
    are read from the integer epoch value. Going through ``datetime`` would cut a nanosecond value to microseconds.
    """
    import numpy as np

    types = pa.types
    mask = chunk.is_null().to_numpy(zero_copy_only=False)
    if types.is_date(chunk.type):
        local_date = jpype.JClass("java.time.LocalDate")
        raw = chunk.cast(pa.int64() if types.is_date64(chunk.type) else pa.int32())
        days = raw.fill_null(0).to_numpy(zero_copy_only=False).astype(np.int64)
        if types.is_date64(chunk.type):
            days = days // 86_400_000
        return [
            None if m else local_date.ofEpochDay(int(d)) for d, m in zip(days, mask)
        ]
    per_second = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}[
        chunk.type.unit
    ]
    values = chunk.cast(pa.int64()).fill_null(0).to_numpy(zero_copy_only=False)
    seconds, rest = np.divmod(values.astype(np.int64), per_second)
    nanos = rest * (1_000_000_000 // per_second)
    local_datetime = jpype.JClass("java.time.LocalDateTime")
    utc = jpype.JClass("java.time.ZoneOffset").UTC
    return [
        None if m else local_datetime.ofEpochSecond(int(s), int(n), utc)
        for s, n, m in zip(seconds, nanos, mask)
    ]


def _temporal_to_tagged(chunk, pa):
    """A timestamp or date chunk as tagged values (``T`` date-time, ``D`` date) for the native backend, with the same
    reading rules as :func:`_temporal_to_java`: ISO text of the integer epoch value, so a nanosecond value keeps its
    nanoseconds (a Python ``datetime`` would cut them to microseconds).
    """
    import numpy as np

    from ._native.codec import TAG

    types = pa.types
    mask = chunk.is_null().to_numpy(zero_copy_only=False)
    if types.is_date(chunk.type):
        raw = chunk.cast(pa.int64() if types.is_date64(chunk.type) else pa.int32())
        days = raw.fill_null(0).to_numpy(zero_copy_only=False).astype(np.int64)
        if types.is_date64(chunk.type):
            days = days // 86_400_000
        text = days.astype("datetime64[D]").astype(str).tolist()
        tag = "D"
    else:
        unit = chunk.type.unit
        values = chunk.cast(pa.int64()).fill_null(0).to_numpy(zero_copy_only=False)
        text = (
            values.astype(np.int64).astype(f"datetime64[{unit}]").astype(str).tolist()
        )
        tag = "T"
    return [None if m else {TAG: [tag, s]} for s, m in zip(text, mask)]


def _scalars_to_tagged(kind: str, chunk):
    """A decimal or binary chunk as tagged values (``n`` decimal text, ``b`` base64) for the native backend."""
    from ._native.codec import TAG

    values = chunk.to_pylist()
    if kind == "decimal":
        return [None if v is None else {TAG: ["n", str(v)]} for v in values]
    import base64

    return [
        None if v is None else {TAG: ["b", base64.b64encode(v).decode("ascii")]}
        for v in values
    ]


def _column_values(name: str, chunk, pa, native: bool = False, arrow: bool = False):
    """One Arrow array as what ``Database.insert_columns`` takes: a numpy array when the column crosses as one
    buffer (integers, floats and booleans without nulls), else a list of values (``None`` is a null).

    ``arrow`` (the native backend's document load): a string column, and a numeric one with nulls, stay Arrow arrays, which
    the columnar entry reads in place (the offsets, the bytes and the validity bitmap) instead of as Python values.
    """
    types = pa.types
    if types.is_dictionary(chunk.type):  # a pandas categorical or a Polars Categorical
        chunk = chunk.cast(chunk.type.value_type)
    kind = _kind(pa, chunk.type)
    if arrow and (
        (
            kind == "string"
            and (types.is_string(chunk.type) or types.is_large_string(chunk.type))
        )
        or (kind in ("integer", "floating", "bool") and chunk.null_count)
    ):
        if not (
            kind == "integer"
            and types.is_uint64(chunk.type)
            and len(chunk) > chunk.null_count
        ):  # uint64 keeps the range check below
            return chunk
    if kind in ("integer", "floating", "bool"):
        if native and types.is_uint64(chunk.type) and len(chunk) > chunk.null_count:
            import pyarrow.compute as pc

            if (
                pc.max(chunk).as_py() > 2**63 - 1
            ):  # insert_columns refuses it on the JPype path, with this text
                raise ValueError(
                    f"column {name!r} holds a value beyond the 64-bit signed range"
                )
        if chunk.null_count == 0:
            values = chunk.to_numpy(zero_copy_only=False)
            if values.dtype.kind == "f" and values.dtype.itemsize < 8:
                values = values.astype("float64")  # float16/32 widen exactly
            return values
        return chunk.to_pylist()
    if kind in ("timestamp", "date"):
        return (
            _temporal_to_tagged(chunk, pa) if native else _temporal_to_java(chunk, pa)
        )
    if native and kind in ("decimal", "binary"):
        return _scalars_to_tagged(kind, chunk)
    if kind == "null":
        return [None] * len(chunk)
    # strings, binary, decimal, list, struct: Python values, which insert_columns converts element by element
    # (str, bytes -> byte[], Decimal -> BigDecimal, list -> LIST, dict -> MAP)
    return chunk.to_pylist()


def insert_table(
    db,
    type_name: str,
    table,
    *,
    batch_size: int,
    parallel: bool,
    what: str,
) -> int:
    """Load a ``pyarrow.Table`` into ``type_name`` in batches of ``batch_size`` rows; see ``Database.insert_arrow``."""
    pa = _import_pyarrow(what)
    db._check_not_closed()
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    names = list(table.column_names)
    if not names:
        raise ValueError(f"{what} needs at least one column")
    if len(set(names)) != len(names):
        raise ValueError("a table with duplicate column names cannot be loaded")

    kinds = {}
    for field in table.schema:
        kind = _kind(pa, field.type)
        if kind is None:
            raise TypeError(
                f"column {field.name!r} has Arrow type {field.type}, which has no ArcadeDB "
                f"mapping; convert it first (supported: integers, floats, bool, string, "
                f"binary, timestamp, date, decimal, list, struct, null)"
            )
        kinds[field.name] = kind
    is_vertex, declared = _declared_types(db, type_name, names)
    _check_declared(type_name, table.schema, kinds, declared)
    if parallel and is_vertex:
        raise ValueError(
            "parallel=True writes documents through the async executor; "
            f"'{type_name}' is a vertex type, which loads through graph_batch()"
        )
    if table.num_rows == 0:
        return 0

    native = _is_native(db)
    written = 0
    # a document load inside the caller's own transaction joins it (insert_columns commits
    # nothing then); a vertex load refuses to run inside one
    in_caller_transaction = (not is_vertex) and bool(db.is_transaction_active())
    graph_batch = db.graph_batch() if is_vertex else None
    try:
        for batch in table.to_batches(max_chunksize=batch_size):
            if batch.num_rows == 0:
                continue
            columns = {
                name: _column_values(
                    name,
                    batch.column(i),
                    pa,
                    native,
                    arrow=native and not is_vertex and not parallel,
                )
                for i, name in enumerate(names)
            }
            try:
                if is_vertex:
                    _insert_vertices(
                        graph_batch, type_name, names, columns, batch.num_rows
                    )
                elif native:
                    _insert_documents_native(
                        db, type_name, names, columns, batch_size, parallel, declared
                    )
                else:
                    db.insert_columns(
                        type_name, columns, commit_every=batch_size, parallel=parallel
                    )
            except ArcadeDBError as exc:
                if written and in_caller_transaction:
                    # the batches joined the caller's transaction: nothing is committed
                    # until the caller commits, and a rollback removes them
                    raise ArcadeDBError(
                        f"{exc}; the {written} row(s) of the batches before this one "
                        f"were written in your transaction, not committed"
                    ) from exc
                if written:
                    raise ArcadeDBError(
                        f"{exc}; the {written} row(s) of the batches before this one "
                        f"were committed"
                    ) from exc
                raise
            written += batch.num_rows
    finally:
        if graph_batch is not None:
            graph_batch.close()
    return written


def _insert_vertices(
    graph_batch, type_name: str, names: List[str], columns: Dict[str, Any], n: int
):
    """One batch of vertices: the columns as one property dict per row, through ``GraphBatch.create_vertices``."""
    lists = []
    for name in names:
        values = columns[name]
        lists.append(values.tolist() if hasattr(values, "tolist") else values)
    graph_batch.create_vertices(
        type_name, [dict(zip(names, row)) for row in zip(*lists)]
    )


def _insert_documents_native(
    db,
    type_name: str,
    names: List[str],
    columns: Dict[str, Any],
    batch_size: int,
    parallel: bool,
    declared: Optional[Dict[str, str]] = None,
):
    """One batch of documents on the native backend. When every column can cross as memory (numbers, bools, strings, nulls,
    float vectors for an ``ARRAY_OF_FLOATS`` property) the batch goes through the columnar entry, no Python values and no JSON
    text; otherwise the columns become one dict per row and go to ``insert_many`` (one crossing per 10,000 rows). Either way
    the batch is one transaction, or joins the caller's.
    """
    if not parallel:
        from ._native.bulk import insert_columns_fast

        if (
            insert_columns_fast(
                db,
                type_name,
                columns,
                batch_size,
                declared={} if declared is None else declared,
                prefix=f"Failed to bulk-insert into '{type_name}'",
            )
            is not None
        ):
            return
    lists = []
    for name in names:
        col = columns[name]
        if hasattr(
            col, "to_pylist"
        ):  # a column kept as an Arrow array for the columnar entry
            lists.append(col.to_pylist())
        else:
            # jvm-payload: not-a-crossing -- no JVM here: insert_many serialises the rows to JSON text
            lists.append(col.tolist() if hasattr(col, "tolist") else col)
    db.insert_many(
        type_name,
        [dict(zip(names, row)) for row in zip(*lists)],
        commit_every=batch_size,
        parallel=parallel,
    )
