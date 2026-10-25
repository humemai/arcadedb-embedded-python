"""Columnar query results of the native library (``arcadedb_n_exec_col`` / ``arcadedb_n_next_col``): a frame of per-column buffers
instead of JSON text. The layout is the one the columnar insert reads (int64 / float64 / bool bytes, UTF-8 strings as Arrow int32 offsets
plus a byte blob, float32 vectors, bitmaps with bit i of byte i/8 least significant first); see ``ColResult.java`` for the frame. The rows
come back as the same dicts the JSON reply gives, bit for bit, without parsing text.
"""

import json
import struct
from datetime import date, datetime, timedelta, timezone

from .codec import RID

MAGIC = 0x31524341  # b"ACR1"
_HDR = struct.Struct(
    "<IIQqII"
)  # magic, JSON header bytes, frame bytes, cursor id, rows, flags
_BASE = 32
_ORDINAL_1970 = date(1970, 1, 1).toordinal()
_EPOCH = datetime(1970, 1, 1)
_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
_US = timedelta(microseconds=1)

try:  # numpy is optional: it only speeds up big vector matrices
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None
_NUMPY_FROM = 4096  # floats in a matrix from which numpy's reshape().tolist() beats slicing in Python


def is_frame(first_byte: int) -> bool:
    """A reply starts with ``{`` (JSON) or with the frame magic (``A``)."""
    return first_byte == 0x41


def _strings(view, base, n, data, aux):
    offs = view[base + data : base + data + 4 * (n + 1)].cast("i").tolist()
    end = offs[n]
    blob = bytes(view[base + aux : base + aux + end])
    if blob.isascii():
        text = blob.decode("ascii")
        return [text[a:z] for a, z in zip(offs, offs[1:])]
    return [blob[a:z].decode("utf-8") for a, z in zip(offs, offs[1:])]


def _bitmap(view, base, off, n):
    return bytes(view[base + off : base + off + ((n + 7) >> 3)])


def _column(view, base, n, kind, dim, data, aux):
    """The n cells of one column (a placeholder where the row has no value)."""
    if kind == "q":
        return view[base + data : base + data + 8 * n].cast("q").tolist()
    if kind == "d":
        return view[base + data : base + data + 8 * n].cast("d").tolist()
    if kind == "s":
        return _strings(view, base, n, data, aux)
    if kind == "b":
        return view[base + data : base + data + n].cast("?").tolist()
    if kind == "f":
        flat = view[base + data : base + data + 4 * n * dim]
        if _np is not None and n * dim >= _NUMPY_FROM:
            return _np.frombuffer(flat, dtype=_np.float32).reshape(n, dim).tolist()
        flat = flat.cast("f").tolist()
        return [flat[i : i + dim] for i in range(0, n * dim, dim)]
    if kind == "v":
        offs = view[base + data : base + data + 4 * (n + 1)].cast("i").tolist()
        flat = view[base + aux : base + aux + 4 * offs[n]].cast("f").tolist()
        return [flat[a:z] for a, z in zip(offs, offs[1:])]
    if kind == "R":
        return [RID(t) for t in _strings(view, base, n, data, aux)]
    if kind == "D":
        ords = view[base + data : base + data + 8 * n].cast("q").tolist()
        return [date.fromordinal(x + _ORDINAL_1970) for x in ords]
    if kind == "T":
        us = view[base + data : base + data + 8 * n].cast("q").tolist()
        return [_EPOCH + x * _US for x in us]
    if kind == "Z":
        us = view[base + data : base + data + 8 * n].cast("q").tolist()
        return [_EPOCH_UTC + x * _US for x in us]
    if kind == "n":
        return [None] * n
    raise ValueError(f"unknown column kind {kind!r} in a columnar reply")


def decode(view) -> dict:
    """The reply dict (``ok``, ``rs``, ``rows``, ``meta``, ``drained``, maybe ``rerr``) of a frame; ``view`` is a byte memoryview of it.
    Nothing of ``view`` is kept: the buffer it points into is reused by the next call on the thread.
    """
    magic, hlen, total, rs, n, flags = _HDR.unpack_from(view, 0)
    if magic != MAGIC:
        raise ValueError("not a columnar reply")
    head = json.loads(bytes(view[_BASE : _BASE + hlen]))
    base = _BASE + hlen
    names, cols, sparse = [], [], []
    for name, kind, dim, data, aux, valid, present in head["c"]:
        vals = _column(view, base, n, kind, dim, data, aux)
        if valid:
            vb = _bitmap(view, base, valid, n)
            vals = [
                v if (vb[i >> 3] >> (i & 7)) & 1 else None for i, v in enumerate(vals)
            ]
        names.append(name)
        cols.append(vals)
        if present:
            sparse.append((name, vals, _bitmap(view, base, present, n)))
    orders = {r: o for r, o in head.get("o", ())}
    if not sparse and not orders:
        rows = (
            [dict(zip(names, r)) for r in zip(*cols)]
            if cols
            else [{} for _ in range(n)]
        )
    else:
        # some rows lack a property or list theirs in another order (record rows): build each row from the columns whose bit says the property exists
        present = {name: pb for name, _, pb in sparse}
        keep = [(name, vals, present.get(name)) for name, vals in zip(names, cols)]
        rows = []
        for i in range(n):
            row = {}
            o = orders.get(i)
            for name, vals, pb in keep if o is None else [keep[j] for j in o]:
                if pb is None or (pb[i >> 3] >> (i & 7)) & 1:
                    row[name] = vals[i]
            rows.append(row)
    m = head["m"]
    if not m:
        meta = [0] * n
    else:
        kinds = bytes(view[base + m[0] : base + m[0] + n])
        rids = _strings(view, base, n, m[1], m[2])
        types = _strings(view, base, n, m[3], m[4])
        meta = [[r, t, chr(k)] if k else 0 for r, t, k in zip(rids, types, kinds)]
    reply = {
        "ok": True,
        "rs": rs,
        "rows": rows,
        "meta": meta,
        "drained": bool(flags & 1),
    }
    if "rerr" in head:
        reply["rerr"] = head["rerr"]
    return reply
