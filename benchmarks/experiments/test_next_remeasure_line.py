"""The /next page says ArcadeDB's numbers are re-measured on the paper's release while the rows are another release (DECISIONS #176).

Run with `python -m pytest test_next_remeasure_line.py -q -rs` from this directory.

The list of what the next measurement changes used to show only while the ArcadeDB rows were a development build, so it vanished
when the 26.10.1 release rows landed and a reader would take those numbers as final. It now carries one line while the rows are a
release other than the paper's (26.11.1): ArcadeDB is measured again on 26.11.1 and the comparators' numbers carry over. Keyed on
the rows' engine_version; 26.11.1 rows take the line off the page. The defects 26.11.1 fixes in 26.10.1 other than the top parts
refusal (ArcadeData/arcadedb#9400, #9397, #9452) mark no printed cell, so no per-table mark exists to test (see _PAPER_RELEASE).
"""
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SERVED = "server:{v} (build d36b4ca3ae4c170abc)"
DEV = "26.10.1-SNAPSHOT (build abc/1790000000000/main)"


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


@pytest.fixture
def note(EW, monkeypatch):
    monkeypatch.setattr(EW, "_OCTOBER_ENV", True)
    monkeypatch.setattr(EW, "SKELETON", False)

    def run(versions, tables=(), filed=None):
        rows = [{"backend": b, "engine_version": v} for b, v in versions] + [{"backend": "duckdb", "engine_version": "1.5.0"}]
        monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
        monkeypatch.setattr(EW, "_NEXT_ITEM_SENTENCES", filed or {})
        return EW._next_measurement_note(list(tables))
    return run


def _release_rows(v):
    return [("arcadedb_embedded", v), ("arcadedb_server", SERVED.format(v=v)), ("arcadedb_embedded", None)]


def test_release_rows_show_the_line(EW, note):
    out = note(_release_rows("26.10.1"))
    [line] = [x for x in out if "26.11.1" in x]
    assert line == ("ArcadeDB's numbers here are from release 26.10.1. The next measurement runs ArcadeDB again on release 26.11.1, "
                    "the one the paper reports, and every other engine's numbers carry over.")
    assert out[0].startswith("The next measurement runs after this one is complete")
    assert not re.search(r"\b(lane|cell|row|arm|harness)s?\b", line)      # PAGE-SPEC: the reader's language
    assert ".notes" not in line
    pinned = [g for g in EW._GENERATED if g["text"] == line][0]["values"]
    assert {"26.10.1", "26.11.1"} <= set(pinned)
    assert not any("development build" in x for x in out)


def test_the_line_goes_with_the_target_release(EW, note):
    assert note(_release_rows(EW._PAPER_RELEASE)) == []


def test_a_mix_with_one_other_release_keeps_the_line(EW, note):
    out = note(_release_rows("26.11.1") + [("arcadedb_embedded", "26.10.1")])
    assert any("release 26.10.1." in x for x in out)


def test_a_development_build_keeps_its_own_list(EW, note):
    filed = {"knows": {"Every graph question is asked in both directions of a friendship."}}
    tables = [{"id": "l2", "title": "Graph", "conditions": ["Every graph question is asked in both directions of a friendship."]}]
    out = note([("arcadedb_embedded", DEV)], tables, filed)
    assert any("development build" in x and "every other engine to its latest stable release" in x for x in out)
    assert not any("carry over" in x for x in out)


def test_release_rows_keep_the_table_lines_too(EW, note):
    s = "Every graph question is asked in both directions of a friendship."
    out = note(_release_rows("26.10.1"), [{"id": "l2", "title": "Graph", "conditions": [s]}], {"knows": {s}})
    assert any("both directions of a friendship" in x for x in out) and any("carry over" in x for x in out)


def test_the_refusal_sentence_uses_the_same_constant(EW):
    assert EW._REFUSAL_FIXED_IN == EW._PAPER_RELEASE == "26.11.1"
