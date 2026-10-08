"""The dense lane's id index for the delete, default OFF (humemai/arcadedb-embedded-python#291, CAMPAIGN section 7 row 84, DECISIONS #178).

Run with `python -m pytest test_dense_id_index.py -q -rs` from this directory. Needs numpy (the lane and export_web import it).

Index parity: when `BENCH_DENSE_ID_INDEX=1`, ArcadeDB and every comparator that stores the id as a plain property (pgvector, Neo4j,
Memgraph, FalkorDB, DuckDB, LanceDB) build an index on it, inside the load timer; the engines whose own key is the id stamp "key".
Unset, nothing is built and no row field appears. The /next page says ArcadeDB's delete ran without the index while the rows lack the
stamp, and the next-measurement list says those engines are measured again.
"""
import inspect
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

INDEXED_HERE = {"arcadedb_dense_embedded", "arcadedb_dense_server", "pgvector_dense", "neo4j_dense", "memgraph_dense",
                "falkordb_dense", "duckdb_vss_dense", "lancedb_dense"}


@pytest.fixture(scope="module")
def L():
    pytest.importorskip("numpy")
    import l3d_dense
    return l3d_dense


@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


def test_switch_is_off_unless_set_to_1(L, monkeypatch):
    monkeypatch.delenv("BENCH_DENSE_ID_INDEX", raising=False)
    assert L.id_index_enabled() is False
    monkeypatch.setenv("BENCH_DENSE_ID_INDEX", "1")
    assert L.id_index_enabled() is True
    monkeypatch.setenv("BENCH_DENSE_ID_INDEX", "yes")       # a typo must not run unindexed while the launcher believes otherwise
    with pytest.raises(SystemExit):
        L.id_index_enabled()


def test_every_plain_property_engine_builds_an_index_and_the_rest_use_their_key(L):
    for name, cls in L.BACKENDS.items():
        base = next((n for n in INDEXED_HERE if name.startswith(n)), None)   # int8 / fp32 arms inherit their parent's build
        if base:
            assert cls.ID_INDEX_DDL != "key", name
            src = inspect.getsource(cls.build)
            # the build asks the switch, or wraps a parent build that does (the int8 arms set the quantization and call super)
            assert "id_index_enabled()" in src or "super().build(" in src, name
        else:
            assert cls.ID_INDEX_DDL == "key", f"{name}: deletes by its own key, so it builds nothing"


def test_every_dense_arm_is_an_override_carrier():
    import overrides
    carriers = {be for _lane, be in overrides.DENSE_ID_INDEX_CARRIERS}
    pytest.importorskip("numpy")
    import l3d_dense
    assert set(l3d_dense.BACKENDS) == carriers


def test_runner_forwards_the_switch_into_the_container():
    assert '"BENCH_DENSE_ID_INDEX"' in (HERE / "runner.py").read_text()


class _FakeBatch:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        self.log.append("graph_batch")
        return self

    def __exit__(self, *a):
        return False

    def create_vertices(self, t, rows):
        self.log.append(f"vertices {len(rows)}")


class _FakeDb:
    def __init__(self):
        self.log = []

    def command(self, lang, text, *a):
        self.log.append(" ".join(text.split()))

    def graph_batch(self, **kw):
        return _FakeBatch(self.log)


class _FakeA:
    @staticmethod
    def to_java_float_array(v):
        return v


@pytest.mark.parametrize("on", [False, True])
def test_arcadedb_embedded_builds_the_index_before_the_load_only_when_on(L, monkeypatch, on):
    import numpy as np
    if on:
        monkeypatch.setenv("BENCH_DENSE_ID_INDEX", "1")
    else:
        monkeypatch.delenv("BENCH_DENSE_ID_INDEX", raising=False)
    monkeypatch.delenv("BENCH_DENSE_QUANT", raising=False)
    a = object.__new__(L.ArcadeEmbedded)
    a.db, a._a = _FakeDb(), _FakeA()
    a.build(np.zeros((3, L.DIM), dtype="float32"))
    ddl = "CREATE INDEX ON Article (vid) UNIQUE_HASH"
    if on:
        assert a.db.log.index(ddl) < a.db.log.index("graph_batch")
        assert a.id_index == ddl
    else:
        assert ddl not in a.db.log and a.id_index is None


def _row(**kw):
    r = {"lane": "l3d", "instrument": "2026-10", "backend": "arcadedb_dense_embedded", "mutate_delete_per_op_ms": 1.5}
    r.update(kw)
    return r


def test_page_sentence_while_an_arcadedb_delete_ran_without_the_index(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
    s = EW._dense_id_index_note("l3d", [_row()])
    assert s and "no index" in s and "measures all of them again" in s
    assert s in EW._NEXT_ITEM_SENTENCES["dense_id_index"]
    assert EW._dense_id_index_note("l3d", [_row(dense_id_index="CREATE INDEX ON Article (vid) UNIQUE_HASH")]) is None
    assert EW._dense_id_index_note("l3d", [_row(backend="pgvector_dense")]) is None
    assert EW._dense_id_index_note("l3d", [_row(mutate_delete_per_op_ms=None)]) is None   # no delete measured, nothing to say
    assert EW._dense_id_index_note("l3s", [_row()]) is None


def test_next_measurement_line_names_the_re_measured_engines(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "SKELETON", False)
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [{"backend": "arcadedb_embedded", "engine_version": "26.10.1"}])
    monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
    s = EW._dense_id_index_note("l3d", [_row()])
    out = EW._next_measurement_note([{"id": "l3d", "title": "Dense vectors", "conditions": [s]}])
    assert any("carry over unless a line below says they are measured again" in x for x in out)
    [line] = [x for x in out if "index on its id" in x]
    assert "Dense vectors" in line and "measured again" in line
