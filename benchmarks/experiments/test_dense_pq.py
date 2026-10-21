"""The dense lane's PQ arms (QUANTIZATION.md): registered only under BENCH_DENSE_PQ=1, refused on an engine whose SQL
does not know `rerank`, and kept as their own row family on the page.

Run with `python -m pytest test_dense_pq.py -q` from this directory (needs numpy: the lane imports it).
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PQ_ARMS = ["arcadedb_dense_embedded_pq", "arcadedb_dense_server_pq", "qdrant_dense_pq",
           "milvus_dense_pq", "arangodb_dense_pq"]

_REGISTRY_CODE = """
import json, l3d_dense, runner
print(json.dumps({
  "lane": sorted(a for a in l3d_dense.BACKENDS if a.endswith("_pq")),
  "runner": sorted(a for a in runner.BACKENDS if a.endswith("_pq")),
  "roster": sorted(a for a in runner.LANES["l3d"][1] if a.endswith("_pq")),
}))
"""


def _registered(instrument, pq):
    env = dict(os.environ)
    env.pop("BENCH_INSTRUMENT", None)
    env.pop("BENCH_DENSE_PQ", None)
    if instrument is not None:
        env["BENCH_INSTRUMENT"] = instrument
    if pq is not None:
        env["BENCH_DENSE_PQ"] = pq
    r = subprocess.run([sys.executable, "-c", _REGISTRY_CODE], cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("instrument,pq", [(None, None), (None, "0"), (None, "yes"), ("2026-11", None)])
def test_no_pq_arm_unless_the_switch_is_set(instrument, pq):
    got = _registered(instrument, pq)
    assert got == {"lane": [], "runner": [], "roster": []}


@pytest.mark.parametrize("instrument", [None, "2026-11"])
def test_every_pq_arm_is_registered_when_the_switch_is_set(instrument):
    got = _registered(instrument, "1")
    assert got["lane"] == sorted(PQ_ARMS)
    assert got["runner"] == sorted(PQ_ARMS)
    assert got["roster"] == sorted(PQ_ARMS)


def test_pq_arms_clone_their_sibling_entry():
    code = ("import json, runner;"
            "import bench_common as b;"
            "print(json.dumps({a: runner.BACKENDS[a] == runner.BACKENDS[s] for a, s in b.DENSE_PQ_ARMS.items()}))")
    env = dict(os.environ, BENCH_INSTRUMENT="2026-11", BENCH_DENSE_PQ="1")
    r = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    assert all(json.loads(r.stdout.strip().splitlines()[-1]).values())


import l3d_dense  # noqa: E402  (after the path is set; its own registry is gated at import, which this process does not open)

OLD_ENGINE_ERROR = ("Unknown option 'rerank' for function 'vector.neighbors'. "
                    "Allowed: [efSearch, filter, groupBy, groupSize, maxDistance, where]")


def test_rerank_refusal_on_an_old_engine():
    def probe(sql):
        raise RuntimeError(OLD_ENGINE_ERROR)
    with pytest.raises(SystemExit) as e:
        l3d_dense.require_rerank_option(probe)
    assert "rerank" in str(e.value) and "exact search" in str(e.value)


def test_rerank_refusal_when_the_client_returns_the_error_text():
    with pytest.raises(SystemExit):
        l3d_dense.require_rerank_option(lambda sql: OLD_ENGINE_ERROR)


@pytest.mark.parametrize("outcome", ["no such index Article[embedding]", "", None])
def test_a_build_that_knows_rerank_passes(outcome):
    """On a build with the option, the probe fails later (no index yet) or answers: neither refuses."""
    def probe(sql):
        if outcome is None:
            return []
        if outcome:
            raise RuntimeError(outcome)
        return outcome
    l3d_dense.require_rerank_option(probe)


def test_embedded_pq_connect_refuses_an_old_engine(monkeypatch):
    class FakeDb:
        def query(self, lang, sql):
            raise RuntimeError(OLD_ENGINE_ERROR)

    def fake_connect(self):
        self.db = FakeDb()
    monkeypatch.setattr(l3d_dense.ArcadeEmbedded, "connect", fake_connect)
    with pytest.raises(SystemExit):
        l3d_dense.ArcadeEmbeddedPQ().connect()


def test_served_pq_connect_refuses_an_old_engine(monkeypatch):
    class Resp:
        status_code = 500
        text = OLD_ENGINE_ERROR

    class Rq:
        def post(self, *a, **k):
            return Resp()

    def fake_connect(self):
        self.rq, self.base = Rq(), "http://x/api/v1"
    monkeypatch.setattr(l3d_dense.ArcadeServer, "connect", fake_connect)
    with pytest.raises(SystemExit):
        l3d_dense.ArcadeServerPQ().connect()


def test_embedded_pq_connect_records_the_setting_on_a_new_engine(monkeypatch):
    class FakeDb:
        def query(self, lang, sql):
            raise RuntimeError("Type 'Article' not found")

    def fake_connect(self):
        self.db = FakeDb()
    monkeypatch.setattr(l3d_dense.ArcadeEmbedded, "connect", fake_connect)
    a = l3d_dense.ArcadeEmbeddedPQ()
    a.connect()
    assert a.row_extra["pq_subspaces"] == l3d_dense.PQ_SUBSPACES == 32
    assert a.row_extra["pq_clusters"] == 256
    assert a.row_extra["pq_rerank_option_accepted"] is True


def test_the_arcadedb_ddl_names_product_and_the_matched_pq_setting():
    served = l3d_dense.ArcadeServerPQ()._quant_ddl
    for want in ('"quantization": "PRODUCT"', '"pqSubspaces": 32', '"pqClusters": 256'):
        assert want in served
    embedded = l3d_dense.ArcadeEmbeddedPQ()._quant_extra
    assert '"pqSubspaces": 32' in embedded and '"pqClusters": 256' in embedded
    # the plain arms keep their DDL: no PQ entries
    assert l3d_dense.ArcadeEmbedded._quant_extra == ""
    assert "pq" not in l3d_dense.ArcadeServer._quant_ddl.lower()


def test_every_pq_arm_declares_product():
    for cls in (l3d_dense.ArcadeEmbeddedPQ, l3d_dense.ArcadeServerPQ, l3d_dense.QdrantPQ,
                l3d_dense.MilvusPQ, l3d_dense.ArangoDensePQ):
        assert cls.quantization == "PRODUCT"
        assert l3d_dense.canonical_quant_label(cls.quantization) == "PRODUCT"
        assert cls.name in PQ_ARMS


def test_arangodb_factory_is_pq_at_the_matched_subspaces():
    assert l3d_dense.ArangoDensePQ.FACTORY.format(nlists=70) == "IVF70,PQ32x8"


def test_qdrant_ratio_is_the_matched_subspace_count():
    assert l3d_dense.QdrantPQ()._compression() == 16        # 128 x 4 bytes to 32 bytes: 32 subspaces


def test_subspaces_must_divide_the_dimension():
    assert l3d_dense.pq_check(128, 32) == 32
    with pytest.raises(SystemExit):
        l3d_dense.pq_check(128, 30)


def test_a_pq_index_does_not_claim_the_int8_build_cache_policy():
    _, why = l3d_dense.effective_build_cache(0, "PRODUCT")
    assert "PRODUCT" in why


# ---- the page: PQ is its own row family on the next instrument only
import bench_common  # noqa: E402


def _row(backend, instrument):
    return {"lane": "l3d", "backend": backend, "scale": "small", "instrument": instrument}


def test_only_2026_11_pq_rows_reach_the_page():
    rows = [_row("qdrant_dense", "2026-10"), _row("qdrant_dense_pq", "2026-11"),
            _row("milvus_dense_pq", "2026-10"), _row("arangodb_dense_pq", ""), _row("arcadedb_dense_server_pq", None)]
    kept = [r["backend"] for r in bench_common.drop_unstamped_pq_rows(rows)]
    assert kept == ["qdrant_dense", "qdrant_dense_pq"]


@pytest.fixture(scope="module")
def export_web():
    """export_web, imported once (it refuses to import without a pin in the environment)."""
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        try:
            import export_web as ew
        except SystemExit as e:                      # the artifacts are not in this checkout
            pytest.skip(f"export_web does not import here: {e}")
    finally:
        mp.undo()
    return ew


def test_pq_arms_are_a_separate_precision_family_with_a_name(export_web):
    for arm in PQ_ARMS:
        assert export_web.DENSE_PRECISION[arm] == "pq"
        assert bench_common.row_family(arm) == "pq"
        assert export_web.DISPLAY_NAMES[arm]
    assert bench_common.row_family("qdrant_dense_int8") is None
    assert export_web.DENSE_PRECISION["qdrant_dense_int8"] == "int8"
    assert export_web.DENSE_PRECISION["qdrant_dense"] == "fp32"


def test_pq_rows_do_not_make_the_dense_lane_a_mixed_instrument(export_web):
    saved = export_web._FROZEN_ROWS
    try:
        export_web._FROZEN_ROWS = [_row("qdrant_dense", "2026-10"), _row("qdrant_dense_pq", "2026-11")]
        assert export_web._instrument_of("l3d") == "2026-10"
        export_web._FROZEN_ROWS = [_row("qdrant_dense", "2026-10"), _row("qdrant_dense_int8", "2026-11")]
        with pytest.raises(SystemExit):
            export_web._instrument_of("l3d")
    finally:
        export_web._FROZEN_ROWS = saved
