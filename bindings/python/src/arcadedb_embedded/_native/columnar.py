"""Packing of whole columns for ``arcadedb_n_insert_colp``: the columnar bulk insert of the native backend.

A column crosses as raw memory, not as JSON text: the image reads each buffer in place and builds the documents without a parser. This
module only decides how a column is laid out and hands the addresses over; it needs no native library, so the layouts are unit-tested
without one. A column that cannot be laid out (a nested value, a mixed-type column, a date-time, an integer past 64 bits, a string with
a lone surrogate) makes :func:`pack` return ``None`` and the caller uses the JSON path for that call; nothing is half sent.

Kinds (the image's, ``BulkOps.insertColumns``): ``q`` int64, ``d`` float64, ``b`` bool byte, ``i`` int32, ``e`` float32, ``f`` float32
matrix (``dim`` per row), ``s`` UTF-8 string (``int32 offsets[n+1]`` and the bytes they index: Arrow's string layout). A column may
carry a null bitmap (Arrow's: bit ``i`` of byte ``i // 8``, least significant first, 1 = present).

``i`` and ``e`` and the float matrix from a list of lists are chosen only for a property declared ``INTEGER``, ``FLOAT`` and
``ARRAY_OF_FLOATS``: the engine would convert to those types anyway, so the stored value is the one the JSON path stores. For an
undeclared property an ``int32`` column crosses as ``q`` (a Long) and a ``float32`` column as ``d`` (a Double), as the JSON path stores
them.
"""

import re

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

_INT64_MAX = 2**63 - 1
_INT32_MAX = 2**31 - 1
_NoneType = type(None)
_PROPERTY = re.compile(r"name: (.+?), type: ([A-Z_]+)")


class Packed:
    """One column laid out for the image: ``data``, ``aux`` and ``nulls`` are ``(address, bytes)``; ``keep`` holds what the addresses point into."""

    __slots__ = ("name", "kind", "dim", "n", "data", "aux", "nulls", "keep")

    def __init__(self, name, kind, dim, array, aux=None, nulls=None, keep=()):
        self.name = name
        self.kind = kind
        self.dim = dim
        self.n = int(array.shape[0]) - (
            1 if kind == "s" else 0
        )  # a string column's array is its n + 1 offsets
        self.data = (array.ctypes.data, array.nbytes)
        self.aux = aux or (0, 0)
        self.nulls = (nulls.ctypes.data, nulls.nbytes) if nulls is not None else (0, 0)
        self.keep = (array, nulls, *keep)


class Declared:
    """The declared property types of a type, read once and only when a column needs them (``INTEGER``, ``FLOAT``, ``ARRAY_OF_FLOATS``).

    ``known`` (a dict) is used as it is; otherwise ``db`` is asked for ``schema:types`` the first time :meth:`get` is called.
    """

    def __init__(self, db=None, type_name=None, known=None):
        self._db, self._type, self._known = db, type_name, known

    def get(self, name):
        if self._known is None:
            self._known = _declared_types(self._db, self._type)
        return self._known.get(name)


def _declared_types(db, type_name):
    """``{property: TYPE}`` of ``type_name`` and its parent types (the nearest declaration wins); ``{}`` when it cannot be read."""
    try:
        rows = {
            r["name"]: r for r in db.query("sql", "SELECT FROM schema:types").to_list()
        }
    except Exception:  # nosec B110 - the insert reports the real error
        return {}
    out, seen, queue = {}, set(), [type_name]
    while queue:
        current = queue.pop(0)
        if current in seen or current not in rows:
            continue
        seen.add(current)
        for text in rows[current].get("properties") or []:
            m = _PROPERTY.search(text)
            if m:
                out.setdefault(m.group(1), m.group(2))
        queue.extend(rows[current].get("parentTypes") or [])
    return out


def _bitmap(present):
    """Arrow validity bitmap of a bool array (True = present)."""
    return _np.packbits(present, bitorder="little")


def _numpy_column(name, values, declared, nulls=None):
    """A 1-D or 2-D numpy array as a column, or None."""
    k = values.dtype.kind
    if values.ndim == 2 and k == "f" and values.shape[1] > 0 and nulls is None:
        arr = _np.ascontiguousarray(values, dtype=_np.float32)
        return Packed(name, "f", int(values.shape[1]), arr)
    if values.ndim != 1:
        return None
    if k == "b":
        return Packed(
            name, "b", 0, _np.ascontiguousarray(values).view(_np.uint8), nulls=nulls
        )
    if k in "iu":
        if (
            k == "u"
            and values.dtype.itemsize == 8
            and values.size
            and int(values.max()) > _INT64_MAX
        ):
            return None
        if k == "i" and values.dtype.itemsize <= 4 and declared.get(name) == "INTEGER":
            return Packed(
                name,
                "i",
                0,
                _np.ascontiguousarray(values, dtype=_np.int32),
                nulls=nulls,
            )
        return Packed(
            name, "q", 0, _np.ascontiguousarray(values, dtype=_np.int64), nulls=nulls
        )
    if k == "f":
        if values.dtype.itemsize == 4 and declared.get(name) == "FLOAT":
            return Packed(
                name,
                "e",
                0,
                _np.ascontiguousarray(values, dtype=_np.float32),
                nulls=nulls,
            )
        return Packed(
            name, "d", 0, _np.ascontiguousarray(values, dtype=_np.float64), nulls=nulls
        )
    return None


def _string_column(name, texts, nulls=None):
    """A list of str (a null already replaced by '') as a string column, or None (a lone surrogate, or 2 GiB of text)."""
    n = len(texts)
    blob = "".join(texts)
    if blob.isascii():
        data = blob.encode("ascii")
        lengths = _np.fromiter(map(len, texts), dtype=_np.int64, count=n)
    else:
        try:
            encoded = [t.encode("utf-8") for t in texts]
        except UnicodeEncodeError:
            return None  # a lone surrogate: the JSON path decides what happens to it
        data = b"".join(encoded)
        lengths = _np.fromiter(map(len, encoded), dtype=_np.int64, count=n)
    if len(data) > _INT32_MAX:
        return None
    offsets = _np.zeros(n + 1, dtype=_np.int32)
    _np.cumsum(lengths, out=offsets[1:], dtype=_np.int32)
    blob_array = (
        _np.frombuffer(data, dtype=_np.uint8) if data else _np.zeros(0, dtype=_np.uint8)
    )
    aux = (blob_array.ctypes.data, blob_array.nbytes) if data else (0, 0)
    return Packed(name, "s", 0, offsets, aux=aux, nulls=nulls, keep=(blob_array, data))


def _list_column(name, values, declared):
    """A list or tuple of Python values as a column: one type (None allowed) or a list of equal-length float arrays; else None."""
    n = len(values)
    types = set(map(type, values))
    present = None
    if _NoneType in types:
        types.discard(_NoneType)
        present = _np.fromiter((v is not None for v in values), dtype=bool, count=n)
        nulls = _bitmap(present)
    else:
        nulls = None
    if not types:  # every value is None
        return _string_column(name, [""] * n, nulls)
    if len(types) != 1:
        return None
    (only,) = types
    if only is str:
        texts = (
            values if present is None else [v if v is not None else "" for v in values]
        )
        return _string_column(name, texts, nulls)
    if only is int or only is float or only is bool:
        filler = 0 if only is int else 0.0 if only is float else False
        vals = (
            values
            if present is None
            else [v if v is not None else filler for v in values]
        )
        dtype = (
            _np.int64 if only is int else _np.float64 if only is float else _np.uint8
        )
        try:
            arr = _np.array(vals, dtype=dtype)
        except OverflowError:
            return None  # an integer beyond 64 bits
        kind = "q" if only is int else "d" if only is float else "b"
        return Packed(name, kind, 0, arr, nulls=nulls)
    if only is list and declared.get(name) == "ARRAY_OF_FLOATS" and present is None:
        try:
            arr = _np.array(values, dtype=_np.float32)
        except (ValueError, TypeError):
            return None  # ragged, or not numbers
        if arr.ndim != 2 or arr.shape[1] == 0:
            return None
        return Packed(name, "f", int(arr.shape[1]), arr)
    if (
        only is _np.ndarray
        and present is None
        and all(
            v.ndim == 1 and v.dtype.kind == "f" and v.shape == values[0].shape
            for v in values
        )
        and values[0].shape[0] > 0
    ):
        return Packed(
            name,
            "f",
            int(values[0].shape[0]),
            _np.ascontiguousarray(_np.stack(values), dtype=_np.float32),
        )
    return None


def _arrow_column(name, arr, declared):
    """A ``pyarrow`` array as a column (strings in place), or None."""
    import pyarrow as pa

    types = pa.types
    if isinstance(arr, pa.ChunkedArray):
        arr = arr.combine_chunks()
        if isinstance(arr, pa.ChunkedArray):
            arr = arr.chunk(0) if arr.num_chunks == 1 else None
        if arr is None:
            return None
    if types.is_dictionary(arr.type):
        arr = arr.cast(arr.type.value_type)
    t, n = arr.type, len(arr)
    nulls = (
        _bitmap(arr.is_valid().to_numpy(zero_copy_only=False))
        if arr.null_count
        else None
    )
    if types.is_string(t) or types.is_large_string(t):
        bufs = arr.buffers()
        off_buf, data_buf = bufs[1], bufs[2]
        if types.is_string(t):
            offsets = _np.frombuffer(off_buf, dtype=_np.int32)[
                arr.offset : arr.offset + n + 1
            ]
        else:
            wide = _np.frombuffer(off_buf, dtype=_np.int64)[
                arr.offset : arr.offset + n + 1
            ]
            if len(wide) and int(wide[-1]) > _INT32_MAX:
                return None
            offsets = wide.astype(_np.int32)
        offsets = _np.ascontiguousarray(offsets)
        size = 0 if data_buf is None else min(data_buf.size, _INT32_MAX)
        aux = (data_buf.address, size) if size else (0, 0)
        return Packed(
            name, "s", 0, offsets, aux=aux, nulls=nulls, keep=(arr, off_buf, data_buf)
        )
    if types.is_integer(t) or types.is_floating(t) or types.is_boolean(t):
        if arr.null_count:
            arr = arr.fill_null(False if types.is_boolean(t) else 0)
        return _numpy_column(name, arr.to_numpy(zero_copy_only=False), declared, nulls)
    if (
        (types.is_list(t) or types.is_large_list(t) or types.is_fixed_size_list(t))
        and not arr.null_count
        and n
        and declared.get(name) == "ARRAY_OF_FLOATS"
        and (types.is_floating(t.value_type) or types.is_integer(t.value_type))
    ):
        flat = arr.flatten()
        if flat.null_count or len(flat) % n:
            return None
        dim = len(flat) // n
        if dim == 0:
            return None
        if not types.is_fixed_size_list(t):
            import pyarrow.compute as pc

            lengths = pc.list_value_length(arr)
            if pc.min(lengths).as_py() != dim or pc.max(lengths).as_py() != dim:
                return None
        values = flat.to_numpy(zero_copy_only=False).reshape(n, dim)
        return Packed(name, "f", dim, _np.ascontiguousarray(values, dtype=_np.float32))
    return None


def pack(columns, declared):
    """``(rows, [Packed])`` for a dict of name -> column, or None when any column cannot be laid out or the columns differ in length.

    A column is a numpy array (1-D ints, floats and bools, or a 2-D float matrix), a list or tuple of Python values of one type (None
    allowed), a list of equal-length 1-D float arrays, or a ``pyarrow`` array.
    """
    items = list(
        columns.items()
    )  # a dict, or a DataFrame (its columns are pandas Series: the row path takes those)
    if _np is None or not items:
        return None
    rows, packed = None, []
    for name, values in items:
        if type(values).__module__.split(".")[0] == "pyarrow":
            col = _arrow_column(name, values, declared)
        elif isinstance(values, _np.ndarray):
            if values.dtype.kind in "OUS":
                col = (
                    _list_column(name, values.tolist(), declared)
                    if values.ndim == 1
                    else None
                )
            else:
                col = _numpy_column(name, values, declared)
        elif isinstance(values, (list, tuple)) and values:
            col = _list_column(name, values, declared)
        else:
            col = None  # a pandas Series, a generator, an empty list: the row path handles them
        if col is None:
            return None
        if rows is not None and col.n != rows:
            return None  # the row path reports the ragged columns
        rows = col.n
        packed.append(col)
    return (rows, packed) if rows else None


def spec_of(packed):
    """The address table the image reads: six int64 per column (data, aux and null-bitmap address and byte count)."""
    import ctypes

    flat = []
    for col in packed:
        flat.extend((*col.data, *col.aux, *col.nulls))
    return (ctypes.c_int64 * len(flat))(*flat)


def header_of(rows, commit_every, packed):
    """The JSON header text: row count, commit interval and ``[name, kind, dim]`` per column."""
    import json

    return json.dumps(
        {
            "n": rows,
            "commit": min(int(commit_every), 2**31 - 1),
            "cols": [[c.name, c.kind, c.dim] for c in packed],
        }
    )


def rows_to_columns(rows):
    """A list of dicts with the same keys as a dict of name -> list of values, or None (no rows, different keys, a non-str key)."""
    if not rows:
        return None
    try:
        keys = list(rows[0])
        if any(type(key) is not str for key in keys):
            return None
        if set(map(len, rows)) != {len(keys)}:
            return None
        return {key: [row[key] for row in rows] for key in keys}
    except (
        KeyError,
        TypeError,
    ):  # same size but different keys, or a row that is not a dict
        return None
