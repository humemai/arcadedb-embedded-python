"""The E2 recall rule (2026-10-25): one recall target, one search breadth per tier, clamps and calibrations that say so on the row."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e2_hybrid  # noqa: E402


def test_the_rule_is_a_recall_target_and_a_breadth_per_tier():
    assert e2_hybrid.RECALL_TARGET == 0.95
    assert e2_hybrid.SEARCH_EF == {"e2": 300, "e2_500k": 1200}


def test_search_ef_follows_the_tier_and_the_probe_override(monkeypatch):
    monkeypatch.delenv("BENCH_E2_SEARCH_EF", raising=False)
    monkeypatch.setattr(e2_hybrid, "PRODUCTS", e2_hybrid.SCALE_PRODUCTS["e2"])
    assert e2_hybrid.search_ef() == 300
    monkeypatch.setattr(e2_hybrid, "PRODUCTS", e2_hybrid.SCALE_PRODUCTS["e2_500k"])
    assert e2_hybrid.search_ef() == 1200
    monkeypatch.setenv("BENCH_E2_SEARCH_EF", "77")
    assert e2_hybrid.search_ef() == 77


def test_pgvector_is_clamped_to_its_documented_maximum_and_says_so(monkeypatch):
    monkeypatch.delenv("BENCH_E2_SEARCH_EF", raising=False)
    monkeypatch.setattr(e2_hybrid, "PRODUCTS", e2_hybrid.SCALE_PRODUCTS["e2_500k"])
    b = e2_hybrid.PgAgeE2.__new__(e2_hybrid.PgAgeE2)
    assert e2_hybrid.PGVECTOR_EF_MAX == 1000       # HNSW_MAX_EF_SEARCH, pgvector src/hnsw.h
    assert b.applied_ef() == 1000 < e2_hybrid.search_ef()
    monkeypatch.setattr(e2_hybrid, "PRODUCTS", e2_hybrid.SCALE_PRODUCTS["e2"])
    assert b.applied_ef() == 300


def test_arms_without_a_lane_ef_report_what_they_applied():
    assert e2_hybrid.ArangoE2.__new__(e2_hybrid.ArangoE2).applied_ef() is None    # IVF: nProbe is calibrated
    lance = e2_hybrid.ComposedEmbeddedE2.__new__(e2_hybrid.ComposedEmbeddedE2)
    lance.LANCE_EF = 400
    assert lance.applied_ef() == 400


def test_lancedb_target_and_ladder_reach_the_500k_rung():
    c = e2_hybrid.ComposedEmbeddedE2
    assert c.RECALL_TARGETS == {"e2": 0.95, "e2_500k": 0.95}
    assert max(c.LANCE_EF_LADDER) >= e2_hybrid.SEARCH_EF["e2_500k"]
    assert list(c.LANCE_EF_LADDER) == sorted(c.LANCE_EF_LADDER)
