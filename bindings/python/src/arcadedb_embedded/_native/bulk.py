"""Columnar bulk insert through one crossing (``arcadedb_n_insert_colp``): whole columns go over by address, with no JSON text. Numpy
ints, floats and bools, lists of one value type (None is a null), strings (UTF-8 bytes plus offsets, as Arrow lays them out), float32
vector columns and Arrow arrays are laid out by :mod:`.columnar`; anything else (nested values, mixed-type columns, date-times,
decimals, integers past 64 bits) returns None and the caller uses the per-row JSON path. The documents are built image-side as
``DocumentBatcher.insertColumns`` builds them on JPype. ``ARCADEDB_NATIVE_BULK=0`` turns the columnar path off.
"""

import os

from . import columnar, lib

_ENABLED = os.environ.get("ARCADEDB_NATIVE_BULK", "1") != "0"


def _usable():
    return (
        _ENABLED
        and columnar._np is not None
        and lib._lib is not None
        and hasattr(lib._lib, "arcadedb_n_insert_colp")
    )


def _send(db, type_name, packed, rows, commit_every, prefix):
    from .database import _call

    spec = columnar.spec_of(packed)
    reply = _call(
        prefix,
        "arcadedb_n_insert_colp",
        db._h,
        lib.b(type_name),
        lib.b(columnar.header_of(rows, commit_every, packed)),
        spec,
        len(spec),
    )  # `packed` holds the arrays the addresses point into until the call returns
    return int(reply["n"])


def insert_columns_fast(
    db, type_name, columns, commit_every, declared=None, prefix="Failed to bulk-insert"
):
    """Insert ``columns`` (name -> column) in one crossing and return the row count, or None when a column cannot be sent this way.

    ``declared``: a dict of declared property types when the caller already knows them (the DataFrame path), else they are read from the
    schema if a column needs them.
    """
    if not _usable():
        return None
    packed = columnar.pack(columns, columnar.Declared(db, type_name, declared))
    if packed is None:
        return None
    rows, cols = packed
    return _send(db, type_name, cols, rows, commit_every, prefix)


def insert_rows_columnar(db, type_name, chunk):
    """One ``insert_many`` chunk (a list of dicts with the same keys) through the columnar entry inside the caller's transaction (no
    commit here). Returns True when it was sent, False when the chunk needs the JSON path.
    """
    if not _usable():
        return False
    columns = columnar.rows_to_columns(chunk)
    if columns is None:
        return False
    packed = columnar.pack(columns, columnar.Declared(db, type_name))
    if packed is None:
        return False
    rows, cols = packed
    _send(db, type_name, cols, rows, 0, f"Failed to bulk-insert into '{type_name}'")
    return True
