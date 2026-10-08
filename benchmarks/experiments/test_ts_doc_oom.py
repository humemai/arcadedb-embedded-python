"""The time-series document load that ran out of memory in our Python bindings is a declared outcome on the /next page (CAMPAIGN section 7 row 86).

Run with `python -m pytest test_ts_doc_oom.py -q -rs` from this directory.

In the 26.10.1 campaign the l4 `arcadedb_ts_doc` ingest at ts1000 was OOM-killed at the tier's memory cap, because `Database.insert_many` held the whole
input three times at once (humemai/arcadedb-embedded-python#294, fixed by #295). The cell carries one plain sentence, keyed on the rows: lane l4, ts1000,
`arcadedb_ts_doc`, ingest, every row `oom_killed`, and an embedded bindings version below `_BINDINGS_FASTER_FROM`. A row that completes, or a failure from
a wheel at or above the cut, ends it. No other cell is touched.
"""
import collections
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


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


def _row(error="", version="26.10.1", **extra):
    killed = bool(error)
    r = {"lane": "l4", "backend": "arcadedb_ts_doc", "workload": "ingest", "scale": "ts1000", "instrument": "2026-10",
         "engine_commit": "d36b4ca3a", "ts_utc": "2026-10-07T00:26:27+00:00", "rep": 1, "rc": 137 if killed else 0,
         "error": error, "oom_killed": killed, "mem_cap": "32g", "engine_version": version if not killed or version else None}
    r.update(extra)
    return r


@pytest.fixture
def page(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "_SKELETON_ENV", False)

    def run(rows):
        monkeypatch.setattr(EW, "_run_log_rows", lambda: rows)
        monkeypatch.setattr(EW, "_TS_OOM_CACHE", None)
        monkeypatch.setattr(EW, "_REFUSAL_CACHE", None)
        monkeypatch.setattr(EW, "_CENSORED_CACHE", None)
        monkeypatch.setattr(EW, "_DECLARED_ABSENCES", collections.defaultdict(list))
        monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
        return EW._censored_notes("l4"), EW._censored_cells()
    return run


def test_the_oom_is_declared_with_one_plain_sentence(EW, page):
    notes, censored = page([_row("killed")])
    want = ("ArcadeDB's embedded time-series document load at 1,000 hosts ran out of memory because the Python bindings held the "
            "whole load in memory at once; the bindings are fixed and the next measurement runs it again.")
    assert notes == [want] == [EW._ts_doc_oom_note("l4")]
    assert censored == {}                                   # out of the unexplained-failure set
    [a] = EW._DECLARED_ABSENCES["l4"]
    assert a["kind"] == "envelope" and a["why"] == want and a["backend"] == EW.display_name("arcadedb_ts_doc")
    assert want in EW._NEXT_ITEM_SENTENCES["ts_doc_oom"]
    pinned = [g for g in EW._GENERATED if g["text"] == want][0]["values"]
    assert "1,000" in pinned
    assert EW._ts_doc_oom_note("docs_olap") is None


def test_the_version_is_read_from_a_sibling_row_when_the_failed_row_has_none(EW, page):
    notes, _ = page([_row("killed", version=None), _row("", scale="ts100", version="26.10.1")])
    assert len(notes) == 1


def test_it_retires_when_a_row_from_fixed_bindings_completes(EW, page):
    notes, censored = page([_row("killed"), _row("", version="26.11.1")])
    assert notes == [] and censored == {} and EW._ts_doc_oom_note("l4") is None


def test_a_completing_row_from_the_old_bindings_stands(EW, page):
    notes, censored = page([_row("killed"), _row("", version="26.10.1")])
    assert notes == [] and censored == {}


def test_a_failure_from_fixed_bindings_is_not_this_defect(EW, page):
    notes, censored = page([_row("killed", version="26.11.1")])
    assert not any("held the whole load" in n for n in notes)
    assert ("l4", "ts1000", "arcadedb_ts_doc", "ingest") in censored


def test_another_failure_or_cell_is_not_declared(EW, page):
    not_oom = _row("boom", oom_killed=False)
    notes, censored = page([not_oom])
    assert EW._ts_doc_oom_cells() == set() and ("l4", "ts1000", "arcadedb_ts_doc", "ingest") in censored
    other_scale = _row("killed", scale="ts100")
    page([other_scale])
    assert EW._ts_doc_oom_cells() == set()
    other_backend = _row("killed", backend="arcadedb_ts_native")
    page([other_backend])
    assert EW._ts_doc_oom_cells() == set()
    other_workload = _row("killed", workload="query")
    page([other_workload])
    assert EW._ts_doc_oom_cells() == set()
