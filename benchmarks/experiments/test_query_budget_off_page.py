"""The per-query budget sentence names only arms the table prints (2026-11-14, first landing of the n=3 rows).

`_query_budget_notes` read every frozen row of the lane, so the tuned PostgreSQL ablation (export_web.OFF_PAGE_ARMS: it stays in the rows and off the
document tables) got a sentence under the document analytics table, and page_check refused it: 'names PostgreSQL (tuned), which the page does not print'.
Every other builder skips OFF_PAGE_ARMS at its own site; this one now does too, and the engine that is printed keeps its sentence.
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="budget-offpage-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l1tpc")
import export_web as EW  # noqa: E402


def _row(backend, rep):
    return {"lane": "l1tpc", "scale": "tpch10", "workload": "olap", "backend": backend, "rep": rep, "by_month_censored": "True",
            "by_month_iters": 95, "by_month_budget_s": 900.0, "by_month_elapsed_s": 868.0}


def test_an_off_page_arm_gets_no_budget_sentence_and_the_printed_arm_keeps_its():
    old = list(EW._FROZEN_ROWS)
    try:
        EW._FROZEN_ROWS[:] = [_row("postgres", r) for r in (1, 2, 3)] + [_row("postgres_tuned", r) for r in (1, 2, 3)]
        text = " ".join(EW._query_budget_notes("docs_olap"))
    finally:
        EW._FROZEN_ROWS[:] = old
    assert "PostgreSQL" in text, text
    assert "(tuned)" not in text, text


if __name__ == "__main__":
    test_an_off_page_arm_gets_no_budget_sentence_and_the_printed_arm_keeps_its()
    print("ok")
