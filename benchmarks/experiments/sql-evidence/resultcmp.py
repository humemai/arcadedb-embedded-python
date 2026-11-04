"""Result-set comparison, query extraction and Wilson intervals shared by gold_check.py and score.py.

Comparison rule (pre-registered, README "Scoring"):
  * rows are compared by column POSITION (names are ignored); the column count must match;
  * order-insensitive unless the question sets `ordered: true`;
  * integers and floats compare numerically; a float pair matches when |a-b| <= float_abs or |a-b| <= float_rel*max(|a|,|b|)
    (float_abs 0.01, float_rel 1e-6, from questions.yaml);
  * strings compare exactly; None only equals None; a truncated result never matches.
"""
import hashlib
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ("sql", "cypher", "pgq", "arcadedb_sql")
ENGINE_OF_ARM = {"sql": "duckdb", "pgq": "duckdb", "cypher": "arcadedb", "arcadedb_sql": "arcadedb"}


def _canon(v):
    if isinstance(v, bool):
        return int(v)
    return v


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sort_key(row):
    out = []
    for v in row:
        v = _canon(v)
        if v is None:
            out.append((0, 0.0, ""))
        elif _is_num(v):
            out.append((1, round(float(v), 2), ""))
        else:
            out.append((2, 0.0, str(v)))
    return tuple(out)


def _val_equal(a, b, atol, rtol):
    a, b = _canon(a), _canon(b)
    if a is None or b is None:
        return a is None and b is None
    if _is_num(a) and _is_num(b):
        if isinstance(a, int) and isinstance(b, int):
            return a == b
        d = abs(float(a) - float(b))
        return d <= atol or d <= rtol * max(abs(float(a)), abs(float(b)))
    return a == b


def rows_equal(gold, got, ordered, atol=0.01, rtol=1e-6, truncated=False):
    if truncated:
        return False
    if len(gold) != len(got):
        return False
    if gold and len(gold[0]) != len(got[0]):
        return False
    if not ordered:
        gold = sorted(gold, key=_sort_key)
        got = sorted(got, key=_sort_key)
    for gr, rr in zip(gold, got):
        if len(gr) != len(rr):
            return False
        for a, b in zip(gr, rr):
            if not _val_equal(a, b, atol, rtol):
                return False
    return True


_FENCE = re.compile(r"\A```[^\n]*\n(.*?)\n?```\Z", re.S)


def extract_query(text):
    """Pre-registered extraction: trim, strip ONE surrounding markdown code fence if present, trim again."""
    t = (text or "").strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1)
    return t.strip()


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def frozen_files():
    out = ["questions.yaml"]
    pdir = os.path.join(HERE, "prompts")
    out += sorted(os.path.join("prompts", n) for n in os.listdir(pdir) if n.endswith(".txt"))
    return out


def frozen_hashes():
    return {rel: sha256_file(os.path.join(HERE, rel)) for rel in frozen_files()}
