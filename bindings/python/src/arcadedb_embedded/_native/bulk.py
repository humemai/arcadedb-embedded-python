"""Columnar bulk insert through one crossing (``arcadedb_n_insert_cols``): numpy int/float/bool columns and float32 vector
columns (a 2-D array or a list of equal-length 1-D float arrays) go over as one buffer; anything else returns None and the
caller falls back to the per-row path. The documents are built Java-side as ``DocumentBatcher.insertColumns`` builds them on JPype.
"""

import json
import os

from . import lib

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

_ENABLED = os.environ.get("ARCADEDB_NATIVE_BULK", "1") != "0"


def insert_columns_fast(db, type_name, columns, commit_every):
    if (
        not _ENABLED
        or _np is None
        or lib._lib is None
        or not hasattr(lib._lib, "arcadedb_n_insert_cols")
    ):
        return None
    cols, parts, n = [], [], None
    for name, values in columns.items():
        if hasattr(values, "to_numpy") and not isinstance(values, (list, tuple)):
            return None
        kind, dim = None, 0
        if isinstance(values, _np.ndarray):
            k = values.dtype.kind
            if (
                values.ndim == 1
                and k in "iu"
                and (
                    k == "i"
                    or not values.size
                    or int(values.max()) <= _np.iinfo(_np.int64).max
                )
            ):
                kind, arr = "q", _np.ascontiguousarray(values, dtype=_np.int64)
            elif values.ndim == 1 and k == "f":
                kind, arr = "d", _np.ascontiguousarray(values, dtype=_np.float64)
            elif values.ndim == 1 and k == "b":
                kind, arr = "b", _np.ascontiguousarray(values, dtype=_np.uint8)
            elif values.ndim == 2 and k == "f" and values.shape[1] > 0:
                kind, arr, dim = (
                    "f",
                    _np.ascontiguousarray(values, dtype=_np.float32),
                    int(values.shape[1]),
                )
        elif (
            isinstance(values, (list, tuple))
            and values
            and all(
                isinstance(v, _np.ndarray)
                and v.ndim == 1
                and v.dtype.kind == "f"
                and v.shape == values[0].shape
                for v in values
            )
            and values[0].shape[0] > 0
        ):
            kind, arr, dim = (
                "f",
                _np.ascontiguousarray(_np.stack(values), dtype=_np.float32),
                int(values[0].shape[0]),
            )
        if kind is None:
            return None
        rows = int(arr.shape[0])
        if n is not None and rows != n:
            return None  # the per-row path reports the ragged columns
        n = rows
        cols.append([name, kind, dim])
        parts.append(arr.tobytes())
    if not n:
        return None
    header = json.dumps(
        {"n": n, "commit": min(int(commit_every), 2**31 - 1), "cols": cols}
    )
    buf = b"".join(parts)
    from .database import _call

    reply = _call(
        "Failed to bulk-insert",
        "arcadedb_n_insert_cols",
        db._h,
        lib.b(type_name),
        lib.b(header),
        buf,
        len(buf),
    )
    return int(reply["n"])
