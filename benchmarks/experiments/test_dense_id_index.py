"""The dense lane's id index for the delete (humemai/arcadedb-embedded-python#291, CAMPAIGN section 7 row 84, DECISIONS #178).

Run with `python -m pytest test_dense_id_index.py -q -rs` from this directory. Needs numpy (the lane and export_web import it).

Index parity: ArcadeDB and every comparator that stores the id as a plain property (pgvector, Neo4j, Memgraph, FalkorDB, DuckDB, LanceDB)
build an index on it, inside the load timer; the engines whose own key is the id stamp "key". The page says ArcadeDB's delete ran without
the index while rows lack the stamp, and the list of coming measurements says those engines are measured again.
"""
import inspect
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

INDEXED_HERE = {"arcadedb_dense_embedded", "arcadedb_dense_server", "pgvector_dense", "neo4j_dense", "memgraph_dense",
                "falkordb_dense", "duckdb_vss_dense", "lancedb_dense", "cratedb_dense"}


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


def test_there_is_no_switch(L):
    assert not hasattr(L, "id_index_enabled") and not hasattr(L, "ID_INDEX_ENV")


def test_every_plain_property_engine_builds_an_index_and_the_rest_use_their_key(L):
    for name, cls in L.BACKENDS.items():
        base = next((n for n in INDEXED_HERE if name.startswith(n)), None)   # int8 / fp32 arms inherit their parent's build
        if base:
            assert cls.ID_INDEX_DDL != "key", name
            src = inspect.getsource(cls.build)
            # the build sets the index it made, or wraps a parent build that does (the int8 arms set the quantization and call super)
            assert "self.id_index = self.ID_INDEX_DDL" in src or "super().build(" in src, name
        else:
            assert cls.ID_INDEX_DDL == "key", f"{name}: deletes by its own key, so it builds nothing"


def test_every_dense_arm_is_an_override_carrier():
    import override_registry as overrides
    carriers = {be for _lane, be in overrides.DENSE_ID_INDEX_CARRIERS}
    pytest.importorskip("numpy")
    import l3d_dense
    assert set(l3d_dense.BACKENDS) == carriers


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


def test_arcadedb_embedded_builds_the_index_before_the_load(L, monkeypatch):
    import numpy as np
    monkeypatch.delenv("BENCH_DENSE_QUANT", raising=False)
    a = object.__new__(L.ArcadeEmbedded)
    a.db, a._a = _FakeDb(), _FakeA()
    a.build(np.zeros((3, L.DIM), dtype="float32"))
    ddl = "CREATE INDEX ON Article (vid) UNIQUE_HASH"
    assert a.db.log.index(ddl) < a.db.log.index("graph_batch")
    assert a.id_index == ddl


def _row(**kw):
    r = {"lane": "l3d", "instrument": "2026-11", "backend": "arcadedb_dense_embedded", "mutate_delete_per_op_ms": 1.5,
         "dense_id_index": "CREATE INDEX ON Article (vid) UNIQUE_HASH"}
    r.update(kw)
    return r


def test_page_sentence_names_the_engines_whose_rows_stamp_the_index(EW):
    s = EW._dense_id_index_note("l3d", [_row(), _row(backend="pgvector_dense", dense_id_index="key")])
    assert s and "ArcadeDB" in s and "pgvector" in s and "index on the vector id" in s and "ingest time" in s
    assert s in [g["text"] for g in EW._GENERATED]                       # registered as a generated sentence
    only = EW._dense_id_index_note("l3d", [_row(), _row(backend="pgvector_dense", dense_id_index="")])
    assert "ArcadeDB" in only and "pgvector" not in only                 # an unstamped engine is not named
    assert EW._dense_id_index_note("l3d", [_row(dense_id_index="")]) is None
    assert EW._dense_id_index_note("l3s", [_row()]) is None
