"""Rows to columns for the native backend (the columnar path is Python over the rows; the JPype path decodes a Java buffer)."""

from datetime import date, datetime, timezone
from decimal import Decimal


def _names(rows, columns):
    if columns is not None:
        return list(columns)
    seen = {}
    for row in rows:
        for k in row:
            seen.setdefault(k, None)
    return list(seen)


def _kind(values):
    """'b', 'i', 'f', 'dt', 'dec', 'obj' for the non-null values of a column."""
    kinds = set()
    for v in values:
        if v is None:
            continue
        t = type(v)
        if t is bool:
            kinds.add("b")
        elif t is int:
            kinds.add("i")
        elif t is float:
            kinds.add("f")
        elif t is datetime or t is date:
            kinds.add("dt")
        elif t is Decimal:
            kinds.add("dec")
        else:
            kinds.add("obj")
    if not kinds:
        return "obj"
    if len(kinds) == 1:
        return kinds.pop()
    if kinds == {"i", "f"}:
        return "f"
    return "obj"


def _ms(v):
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v
    return datetime(v.year, v.month, v.day)


def to_columns(rows, columns=None):
    import numpy as np

    out = {}
    for name in _names(rows, columns):
        values = [row.get(name) for row in rows]
        has_null = any(v is None for v in values)
        kind = _kind(values)
        if kind == "i":
            out[name] = (
                np.array([np.nan if v is None else v for v in values], dtype=np.float64)
                if has_null
                else np.array(values, dtype=np.int64)
            )
        elif kind == "f":
            out[name] = np.array(
                [np.nan if v is None else v for v in values], dtype=np.float64
            )
        elif kind == "b":
            out[name] = values if has_null else np.array(values, dtype=bool)
        elif kind == "dt":
            out[name] = np.array(
                [
                    (
                        np.datetime64("NaT", "ms")
                        if v is None
                        else np.datetime64(_ms(v), "ms")
                    )
                    for v in values
                ],
                dtype="datetime64[ms]",
            )
        elif kind == "dec":
            arr = np.empty(len(values), dtype=object)
            arr[:] = values
            out[name] = arr
        else:
            out[name] = values
    return out


def to_arrow(rows, columns=None):
    import pyarrow as pa

    arrays = {}
    for name in _names(rows, columns):
        values = [row.get(name) for row in rows]
        kind = _kind(values)
        if kind == "i":
            arrays[name] = pa.array(values, type=pa.int64())
        elif kind == "f":
            arrays[name] = pa.array(values, type=pa.float64())
        elif kind == "b":
            arrays[name] = pa.array(values, type=pa.bool_())
        elif kind == "dt":
            arrays[name] = pa.array(
                [None if v is None else _ms(v) for v in values], type=pa.timestamp("ms")
            )
        elif kind == "dec":
            try:
                arrays[name] = pa.array(values)
            except (
                pa.ArrowInvalid
            ):  # wider than decimal256 (76 digits): an exact string
                arrays[name] = pa.array(
                    [None if v is None else str(v) for v in values], type=pa.string()
                )
        else:
            try:
                arrays[name] = pa.array([None if v is None else v for v in values])
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                arrays[name] = pa.array(
                    [None if v is None else str(v) for v in values], type=pa.string()
                )
    return pa.table(arrays)
