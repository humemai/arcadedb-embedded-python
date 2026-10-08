"""ArcadeDB 26.10.1's refusal of the TPC-H SF10 top parts query is a declared outcome on the /next page (DECISIONS #176).

Run with `python -m pytest test_docs_top_parts_refusal.py -q -rs` from this directory.

26.10.1 gives each query a heap budget that shrinks as cores are added, and on the benchmark host's 12 cores it refuses the
2,000,000-group aggregate at the engine's defaults (ArcadeData/arcadedb#9402, fixed by #9415 for 26.11.1). Both ArcadeDB arms of the
documents analytics table show `n/c` with one sentence, keyed on the rows: lane l1tpc, olap, tpch10, an ArcadeDB backend, the release,
and the refusal the row recorded. A 26.11.1 row that completes prints its number and no sentence, and a row that ran with the budget
raised (`arcadedb_query_max_heap_ram_mb`, #260) is never the headline. Mirrors the ArangoDB one-list declaration (BUGS F175).
"""
import collections
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

COLUMNS = ["Q1 p50 ms", "Q6 p50 ms", "top parts p50 ms", "peak memory GiB"]
EMBEDDED_ERROR = (", in main\n    r = b.olap(which)\n  File \"/work/l1_tpc.py\", line 1193, in olap\n"
                  "arcadedb_embedded.exceptions.ArcadeDBError: Query failed: com.arcadedb.exception.CommandExecutionException: "
                  "Query heap budget exceeded: the in-heap GROUP BY needs 16.20KB more, and its query would hold more than the "
                  "whole budget of 8.00GB the buffers of all the running queries share. Reduce what the query buffers in heap "
                  "or set arcadedb.queryMaxHeapRAM to increase the budget")
SERVER_ERROR = ("budget_s=864.0 rss=1588.0MiB\nPHASE query-q6-done p50=4759.2 rows=1 rss=1588.0MiB\n"
                "PHASE query-top_parts-start iters=100 budget_s=864.0 rss=1588.0MiB\nTraceback (most recent call last):\n"
                "  File \"/work/lean_http.py\", line 141, in raise_for_status\n"
                "lean_http.HTTPError: 500 Server Error: Internal Server Error for url: "
                "http://srv-l1tpc_arcadedb_server_olap_tpch10_r1:2480/api/v1/query/bench")


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


def _row(backend, error="", release="26.10.1", **extra):
    served = backend.endswith("_server")
    r = {"lane": "l1tpc", "backend": backend, "workload": "olap", "scale": "tpch10", "instrument": "2026-10",
         "engine_commit": "d36b4ca3a", "ts_utc": "2026-10-07T00:26:27+00:00", "rep": 1, "rc": 1 if error else 0, "error": error, "oom_killed": False,
         "cpuset": "0-11", "heap": "16g"}
    if served:
        r.update(server_cpuset="0-11", server_image_ref=f"arcadedb-c25:{release}",
                 engine_version=f"server:{release} (build d36b4ca3ae4c170abc)" if not error else None)
    else:
        r["engine_version"] = release if not error else None
    r.update(extra)
    return r


def _real_rows(**extra):
    """The two real 26.10.1 rows' shape: the failed rows carry no engine_version, so the release is read from the image tag
    (served) and from a sibling row of the same backend and pin (embedded)."""
    return [_row("arcadedb_embedded", EMBEDDED_ERROR, **extra), _row("arcadedb_server", SERVER_ERROR, **extra),
            _row("arcadedb_embedded", "", scale="tpch1"), _row("arcadedb_embedded", "", workload="oltp")]


@pytest.fixture
def page(EW, monkeypatch):
    """Run the exporter's declarations over `rows`, as _finish_table does."""
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "_SKELETON_ENV", False)
    monkeypatch.setattr(EW, "OFF_PAGE_ARMS", set(EW.OFF_PAGE_ARMS))

    def run(rows):
        monkeypatch.setattr(EW, "_run_log_rows", lambda: rows)
        monkeypatch.setattr(EW, "_REFUSAL_CACHE", None)
        monkeypatch.setattr(EW, "_CENSORED_CACHE", None)
        monkeypatch.setattr(EW, "_DECLARED_ABSENCES", collections.defaultdict(list))
        monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", {})
        table = {"id": "docs_olap", "columns": COLUMNS,
                 "entries": [{"backend": "DuckDB (embedded)", "backend_key": "duckdb", "scale": "tpch10",
                              "metrics": {c: {"median": 1.0} for c in COLUMNS}}]}
        entries, marks = EW._refusal_entries(table)
        return table, entries, marks, EW._censored_notes("docs_olap"), EW._censored_cells()
    return run


def test_the_refusal_is_declared_with_one_plain_sentence(EW, page):
    table, entries, marks, notes, censored = page(_real_rows())
    assert {e["backend_key"] for e in entries} == {"arcadedb_embedded", "arcadedb_server"}
    assert marks == {"n/c"}
    for e in entries:
        assert e["outcome"] == "not comparable" and e["scale"] == "tpch10"
        assert all(v == {"text": "n/c"} for v in e["metrics"].values()) and set(e["metrics"]) == set(COLUMNS)
    [text] = [n for n in notes if "top parts" in n]
    assert text == EW._top_parts_refusal_note("docs_olap")
    assert text.endswith(".") and text.count(". ") == 0        # one sentence
    for fact in ("ArcadeDB 26.10.1", "heap budget that shrinks as cores are added", "12 cores", "2,000,000-group",
                 "default settings", "ArcadeDB 26.11.1 fixes it (ArcadeData/arcadedb#9402, fixed by #9415)",
                 "the next measurement re-measures it", "ArcadeDB (embedded) and ArcadeDB (server)"):
        assert fact in text, fact
    assert not re.search(r"\b(lane|cell|row|arm|harness)s?\b", text)     # PAGE-SPEC: the reader's language
    assert ".notes" not in text
    # the numbers in it are pinned to their sources for page_check
    pinned = [g for g in EW._GENERATED if g["text"] == text][0]["values"]
    assert {"12", "2,000,000", "26.10.1", "26.11.1"} <= set(pinned)
    # declared absent for the coverage gate, and no longer an unexplained failed cell
    assert {a["backend"] for a in EW._DECLARED_ABSENCES["docs_olap"]} == {"ArcadeDB (embedded)", "ArcadeDB (server)"}
    assert all(a["kind"] == "not comparable" for a in EW._DECLARED_ABSENCES["docs_olap"])
    assert not any(k[2].startswith("arcadedb") for k in censored)
    assert not any("failed" in n for n in notes)
    assert text in EW._NEXT_ITEM_SENTENCES["release"]


def test_a_release_that_completes_prints_a_number_and_no_sentence(EW, page):
    rows = [_row("arcadedb_embedded", "", release="26.11.1"), _row("arcadedb_server", "", release="26.11.1")]
    table, entries, marks, notes, censored = page(rows)
    assert entries == [] and marks == set()
    assert EW._top_parts_refusal_note("docs_olap") is None and notes == []
    assert not EW._DECLARED_ABSENCES["docs_olap"] and censored == {}


def test_only_the_release_with_the_defect_is_declared(EW, page):
    rows = [_row("arcadedb_embedded", EMBEDDED_ERROR, release="26.11.1"),
            _row("arcadedb_server", SERVER_ERROR, release="26.11.1")]
    _, entries, _, notes, censored = page(rows)
    assert entries == [] and not any("heap budget" in n for n in notes)
    assert ("l1tpc", "tpch10", "arcadedb_embedded", "olap") in censored      # still a failed cell, said as one


def test_another_failure_is_not_the_refusal(EW, page):
    other = ", in main\n    r = b.olap(which)\nlean_http.HTTPError: 500 Server Error"      # no top_parts phase, no budget message
    _, entries, _, _, censored = page([_row("arcadedb_embedded", other), _row("arcadedb_server", "timeout_after_864s")])
    assert entries == [] and ("l1tpc", "tpch10", "arcadedb_embedded", "olap") in censored


def test_a_raised_budget_row_is_not_the_headline(EW, page):
    stamp = {"arcadedb_query_max_heap_ram_mb": 12288, "arcadedb_query_max_heap_ram_source": "read from the engine"}
    clean_raised = [_row("arcadedb_embedded", "", **stamp), _row("arcadedb_server", "", **stamp)]
    # a completing raised row neither prints in place of the refusal nor cancels it
    _, entries, _, _, censored = page(_real_rows() + clean_raised)
    assert {e["backend_key"] for e in entries} == {"arcadedb_embedded", "arcadedb_server"}
    # a failing raised row alone declares nothing about the defaults
    _, entries, _, _, _ = page([_row("arcadedb_embedded", EMBEDDED_ERROR, **stamp)])
    assert entries == []
    # the export drops stamped rows from the frozen CSV, whose blank cells are empty strings
    assert EW._query_budget_raised(_row("arcadedb_embedded", "", **stamp))
    assert not EW._query_budget_raised(_row("arcadedb_embedded", "", arcadedb_query_max_heap_ram_mb=""))
    assert not EW._query_budget_raised(_row("arcadedb_embedded", ""))
    assert not EW._query_budget_raised(dict(_row("duckdb", ""), **stamp))


def test_cores_come_from_the_rows(EW):
    assert [EW._cpuset_cores(s) for s in ("0-11", "0-3,8-9", "5", "", "x")] == [12, 6, 1, None, None]
