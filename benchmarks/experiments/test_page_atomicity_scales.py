"""page_check._check_page_atomicity reads the page's atomicity cell of an arm AT THE SCALE the artifact rows were measured at.

The e2atom table prints an arm once per scale. An arm whose 500k cell did not finish within the cap keeps its e2 row (3 clean repetitions, 40 trials
each) and gets a second, empty entry at e2_500k plus a whole-arm absence that says so. The check keyed the page by arm alone, so the empty
placeholder overwrote the real row and it reported `page=None artifact=40` for SurrealDB (embedded and server) (2026-11-14, first landing of the n=3 rows).

Now: the page entry and the artifact rows are compared per (arm, scale); a printed cell with no count and no artifact rows at its scale passes only when
the table declares the arm's absence, and fails otherwise; a wrong count at one scale still fails.
Light: pure Python, a temporary results directory. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import page_check as PC  # noqa: E402


def _run_rows(backend, scale, trials=40, reps=(1, 2, 3)):
    return [{"lane": "e2", "workload": "atomicity", "backend": backend, "scale": scale, "rep": r, "trials": trials, "torn_count": 0,
             "n_docs": None, "gav": None, "ts_utc": f"2026-11-0{r}T00:00:00Z"} for r in reps]


def _entry(be, scale, trials):
    m = {"trials": {"median": trials, "n": 3 if trials is not None else None},
         "torn results": {"median": 0 if trials is not None else None, "n": 3 if trials is not None else None}}
    return {"backend": be + " label", "backend_key": be, "scale": scale, "metrics": m}


def _check(entries, rows, absences):
    payload = {"tables": [{"id": "e2atom", "entries": entries, "declared_absences": absences}]}
    with tempfile.TemporaryDirectory() as d:
        Path(d, "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        old = os.environ.get("BENCH_RESULTS_DIR")
        os.environ["BENCH_RESULTS_DIR"] = d
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                got = PC._check_page_atomicity(payload)
        finally:
            if old is None:
                os.environ.pop("BENCH_RESULTS_DIR", None)
            else:
                os.environ["BENCH_RESULTS_DIR"] = old
    return got, out.getvalue()


def _full_page_rows():
    rows, entries = [], []
    for be in PC.E2_BACKENDS:
        if be in PC.E2_OPTIONAL:
            continue
        for sc in ("e2", "e2_500k"):
            if be.startswith("surrealdb") and sc == "e2_500k":
                continue
            rows += _run_rows(be, sc)
            entries.append(_entry(be, sc, 40))
    return rows, entries


def test_an_empty_declared_cell_at_another_scale_does_not_hide_the_real_row():
    rows, entries = _full_page_rows()
    for be in ("surrealdb_e2", "surrealdb_e2_server"):
        entries.append(_entry(be, "e2_500k", None))
    absences = [{"backend": be + " label", "column": None, "kind": "censored", "why": "x"} for be in ("surrealdb_e2", "surrealdb_e2_server")]
    (checked, bad), out = _check(entries, rows, absences)
    assert bad == 0, out
    assert "surrealdb_e2" in out and checked > 0


def test_an_empty_cell_without_a_declared_absence_is_still_a_failure():
    rows, entries = _full_page_rows()
    entries.append(_entry("surrealdb_e2", "e2_500k", None))
    (checked, bad), out = _check(entries, rows, [])
    assert bad >= 1 and "surrealdb_e2" in out, out


def test_a_wrong_count_at_one_scale_fails():
    rows, entries = _full_page_rows()
    rows = [r for r in rows if not (r["backend"] == "arcadedb_e2" and r["scale"] == "e2_500k")] + _run_rows("arcadedb_e2", "e2_500k", trials=20)
    (checked, bad), out = _check(entries, rows, [])
    assert bad >= 1 and "arcadedb_e2" in out and "DISAGREE" in out, out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok  ", name)
