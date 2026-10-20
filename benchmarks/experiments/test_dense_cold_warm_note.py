"""export_web._dense_cold_warm_note skips a mark (issue #355).

A withdrawn row carries `{"text": "re-run"}` where the median would be. The note read `["median"]` from
every entry with a cold and a warm cell, so Neo4j's withdrawn dense row stopped the September build.
"""
import os

import pytest


@pytest.fixture(scope="module")
def EW():
    """export_web, imported once (it refuses to import without a pin in the environment)."""
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        try:
            import export_web
        except SystemExit as e:                      # the e4 artifacts are not in this checkout
            pytest.skip(f"export_web does not import here: {e}")
    finally:
        mp.undo()
    return export_web


def entry(backend, cold, warm, arcadedb=False, **extra):
    e = {"backend": backend, "scale": "small", "scale_label": "1M", "is_arcadedb": arcadedb,
         "metrics": {"cold p50 ms": {"median": cold}, "warm p50 ms": {"median": warm}}}
    e.update(extra)
    return e


def test_a_withdrawn_row_is_skipped_not_read(EW):
    withdrawn = entry("Neo4j (fp32)", 0, 0, outcome="withdrawn")
    withdrawn["metrics"] = {"cold p50 ms": {"text": "re-run"}, "warm p50 ms": {"text": "re-run"}}
    table = {"id": "l3d", "entries": [entry("ArcadeDB", 30.0, 10.0, arcadedb=True), entry("Qdrant", 2.2, 2.0),
                                      entry("Milvus", 4.0, 4.0), withdrawn]}
    note = EW._dense_cold_warm_note(table)
    assert note and "3.0x" in note and "Qdrant" in note and "Neo4j" not in note


def test_a_single_column_marked_re_run_is_skipped(EW):
    marked = entry("Milvus", 4.0, 4.0)
    marked["metrics"]["warm p50 ms"] = {"text": "re-run"}
    table = {"id": "l3d", "entries": [entry("ArcadeDB", 30.0, 10.0, arcadedb=True), entry("Qdrant", 2.2, 2.0), marked]}
    note = EW._dense_cold_warm_note(table)
    assert note and "Milvus" not in note
