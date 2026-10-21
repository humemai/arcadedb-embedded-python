"""Python <-> native JSON: query parameters out, typed rows in."""

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal

try:  # numpy is optional
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

TAG = "\u0001"
_EPOCH_NAIVE = datetime(1970, 1, 1)


def _default(value):
    """json.dumps hook: the values JSON cannot carry, as tagged objects (see Json.java)."""
    if isinstance(value, Decimal):
        return {TAG: ["n", str(value)]}
    if isinstance(value, datetime):
        utc = (
            value.astimezone(timezone.utc).replace(tzinfo=None)
            if value.utcoffset() is not None
            else value
        )
        return {TAG: ["T", utc.isoformat()]}
    if isinstance(value, date):
        return {TAG: ["D", value.isoformat()]}
    if isinstance(value, (set, frozenset)):
        return {TAG: ["s", list(value)]}
    if isinstance(value, (bytes, bytearray, memoryview)):
        import base64

        return {TAG: ["b", base64.b64encode(bytes(value)).decode("ascii")]}
    if _np is not None:
        if isinstance(value, _np.ndarray):
            if value.dtype.kind == "f":
                return {TAG: ["F", value.tolist()]}
            return value.tolist()
        if isinstance(value, _np.bool_):
            return bool(value)
        if isinstance(value, _np.integer):
            return int(value)
        if isinstance(value, _np.floating):
            return float(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(
        f"cannot pass {type(value).__name__} as a parameter on the native backend"
    )


def encode_params(args) -> str:
    """The ``params`` text for ``arcadedb_n_exec``: '' for none, else ``{"named":{..}}`` or ``{"pos":[..]}``.

    Same selection as the JPype path: a lone list/tuple is the positional list itself, a lone mapping (also alone in
    a list) is the named map, anything else is positional.
    """
    if not args:
        return ""
    values = args[0] if len(args) == 1 and isinstance(args[0], (list, tuple)) else args
    if len(values) == 1 and isinstance(values[0], Mapping):
        return json.dumps({"named": dict(values[0])}, default=_default)
    return json.dumps({"pos": list(values)}, default=_default)


def _restore_float(text):
    return float(text)


def _restore_map(pairs):
    return {k: v for k, v in pairs}


_SIMPLE = {
    "n": Decimal,
    "i": int,
    "D": date.fromisoformat,
    "T": datetime.fromisoformat,
    "Z": datetime.fromisoformat,
    "s": set,
    "f": _restore_float,
    "m": _restore_map,
}


def _hook(obj):
    tagged = obj.get(TAG)
    if tagged is None:
        return obj
    kind, payload = tagged
    return _SIMPLE[kind](payload)


def loads(text: str):
    """Decode a reply, restoring tagged values."""
    return json.loads(text, object_hook=_hook)


# --- JSON-native form of a row (ResultSet.to_json_list): DATE/DATETIME as epoch millis, DECIMAL as float.


def json_native(value):
    if isinstance(value, datetime):
        return (
            int((value.replace(tzinfo=None) - _EPOCH_NAIVE).total_seconds() * 1000)
            if value.tzinfo is None
            else int(value.timestamp() * 1000)
        )
    if isinstance(value, date):
        return int(
            (
                datetime.combine(value, datetime.min.time()) - _EPOCH_NAIVE
            ).total_seconds()
            * 1000
        )
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (set, frozenset)):
        return [json_native(v) for v in value]
    if isinstance(value, list):
        return [json_native(v) for v in value]
    if isinstance(value, dict):
        return {k: json_native(v) for k, v in value.items()}
    return value
