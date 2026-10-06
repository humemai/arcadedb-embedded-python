"""The sparse lane's ArcadeDB arms return ids (CAMPAIGN section 7 row 62, DECISIONS #153 item 1).

Run with `python -m pytest test_sparse_rows.py -q -rs` from this directory.

ArcadeDB's timed sparse search returned each hit's whole record (about 46 KB of JSON per query) and mapped record ids to
ordinals in an untimed pass, while every comparator returns ids. Both adapters now run
`SELECT id, score FROM (SELECT expand(vector.sparseNeighbors(...)))`, `resolve()` is the identity as it is for every
comparator, and every ArcadeDB row (the lane's and the multipass driver's) records `sparse_result`.

No engine runs here: the adapters are exercised against stand-ins that record the statement they are given.
"""
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import l3_sparse as S  # noqa: E402
import sparse_multipass_driver as D  # noqa: E402  (the pass records are stamped there too)

ROWS = [{"id": 41, "score": 0.9}, {"id": 7, "score": 0.8}, {"id": 1_000_003, "score": 0.1}]


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def to_json_list(self):
        return self._rows


class _FakeDb:
    def __init__(self):
        self.calls = []

    def query(self, language, sql, *args):
        self.calls.append((language, sql, args))
        return _Result(ROWS)


@pytest.fixture
def fake_jpype(monkeypatch):
    jp = types.SimpleNamespace(JInt=int, JFloat=float, JArray=lambda t: (lambda v: list(v)))
    monkeypatch.setitem(sys.modules, "jpype", jp)


def _embedded(cls):
    a = object.__new__(cls)
    a.db = _FakeDb()
    a.idx_name = "Doc[tokens,weights]"
    return a


@pytest.mark.parametrize("cls", [S.ArcadeEmbedded, S.ArcadeEmbeddedFP32, S.ArcadeEmbeddedNoCompact])
def test_embedded_search_projects_ids_inside_the_timed_query(cls, fake_jpype):
    a = _embedded(cls)
    got = a.search([3, 9], [0.5, 0.25], 10)
    assert got == [41, 7, 1_000_003]                      # ids, in the engine's order, no record ids
    _lang, sql, _args = a.db.calls[0]
    assert sql == "SELECT id, score FROM (SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?)))"


@pytest.mark.parametrize("cls", [S.ArcadeServer, S.ArcadeServerFP32])
def test_served_search_projects_ids_inside_the_timed_query(cls):
    a = object.__new__(cls)
    a.idx_name = "Doc[tokens,weights]"
    seen = []

    def _query(command, params=None):
        seen.append((command, params))
        return ROWS
    a._query = _query
    assert a.search([3, 9], [0.5, 0.25], 10) == [41, 7, 1_000_003]
    assert seen[0][0] == "SELECT id, score FROM (SELECT expand(`vector.sparseNeighbors`(:i, :t, :w, :k)))"
    assert seen[0][1] == {"i": "Doc[tokens,weights]", "t": [3, 9], "w": [0.5, 0.25], "k": 10}


@pytest.mark.parametrize("name", sorted(S.BACKENDS))
def test_resolve_is_the_identity_on_every_arm(name):
    """ArcadeDB's mapped record ids to ordinals until the re-pin; every comparator already returned the id."""
    cls = S.BACKENDS[name]
    a = object.__new__(cls)
    assert a.resolve([5, 1, 9]) == [5, 1, 9]


def test_only_the_arcadedb_arms_declare_what_they_return():
    for name, cls in S.BACKENDS.items():
        want = "id" if name.startswith("arcadedb") else None
        assert getattr(cls, "SPARSE_RESULT", None) == want, name


def test_the_lane_stamps_sparse_result_before_the_build():
    src = (HERE / "l3_sparse.py").read_text()
    main = src[src.index("def main():"):]
    assert main.index('out["sparse_result"] = b.SPARSE_RESULT') < main.index("b.build(n_docs)")




def test_the_multipass_driver_stamps_sparse_result_on_every_arcadedb_pass():
    src = (HERE / "sparse_multipass_driver.py").read_text()
    assert '**({"sparse_result": b.SPARSE_RESULT} if getattr(b, "SPARSE_RESULT", None) else {})' in src
