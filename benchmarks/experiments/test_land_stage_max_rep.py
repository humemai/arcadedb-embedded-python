"""land_stage.py --max-rep N lands repetitions 1..N only (2026-11-14: the page is n=3 while the comparator passes 4 and 5 keep appending
rep 4 and rep 5 rows to the same rows file on the bench host).

Two tests, both light (temporary files, no network, no pytest fixture; run with pytest or as plain functions from this directory):

  * `drop_reps_above` keeps rows of reps 1..N, drops the later ones and reports how many of each rep it dropped, and refuses a row
    whose `rep` is not an integer (a row with no repetition cannot be placed under a cap, and dropping or keeping it silently would
    hide a defect of the file);
  * `main()` with `--max-rep 3 --dry-run` on a pulled file of reps 1 to 5 writes a filtered file that holds reps 1 to 3 only, and
    says on stdout how many rows the cap removed.
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage as L  # noqa: E402


def _row(rep, cell="a"):
    return {"instrument": "2026-11", "engine_commit": "abc123def", "lane": "l2", "backend": "duckdb", "workload": cell, "rep": rep}


def test_drop_reps_above_keeps_1_to_n_and_counts_the_rest():
    rows = [_row(r, c) for c in "ab" for r in (1, 2, 3, 4, 5, 5)]
    kept, dropped = L.drop_reps_above(rows, 3)
    assert sorted({r["rep"] for r in kept}) == [1, 2, 3] and len(kept) == 6, kept
    assert dropped == {4: 2, 5: 4}, dropped
    # nothing above the cap: the same rows back, nothing dropped
    kept2, dropped2 = L.drop_reps_above(kept, 3)
    assert kept2 == kept and dropped2 == {}
    for bad in (None, "3", 2.5):
        try:
            L.drop_reps_above([_row(1), {**_row(1), "rep": bad}], 3)
        except SystemExit as e:
            assert "rep" in str(e.code), e.code
        else:
            raise AssertionError(f"a row with rep={bad!r} must be refused")


def test_main_dry_run_with_max_rep_filters_the_pulled_file():
    rows = [_row(r, c) for c in "abc" for r in (1, 2, 3, 4, 5)]
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pulled = root / "pulled.jsonl"
        pulled.write_text("".join(json.dumps(r) + "\n" for r in rows))
        scratch = root / "scratch"
        scratch.mkdir()
        argv = ["land_stage.py", "--pin", "abc123def", "--max-rep", "3", "--dry-run", "--message", "m"]
        out = io.StringIO()
        env = {**__import__("os").environ, "BENCH_LAND_PULLED_FILE": str(pulled)}
        with mock.patch.object(sys, "argv", argv), mock.patch.object(L, "SCRATCH", scratch), mock.patch.object(L.os, "environ", env), \
                mock.patch.object(L, "sh", lambda *a, **k: None), mock.patch.object(L.os, "execv", lambda *a, **k: None), \
                mock.patch.object(L, "pull_pycost", lambda *a, **k: None), contextlib.redirect_stdout(out):
            rc = L.main()
        assert rc == 0, out.getvalue()
        kept = [json.loads(x) for x in (scratch / "runs_page_filtered.jsonl").read_text().splitlines() if x.strip()]
        assert len(kept) == 9 and sorted({r["rep"] for r in kept}) == [1, 2, 3], (len(kept), out.getvalue())
        assert "--max-rep 3" in out.getvalue() and "6" in out.getvalue(), out.getvalue()


if __name__ == "__main__":
    test_drop_reps_above_keeps_1_to_n_and_counts_the_rest()
    test_main_dry_run_with_max_rep_filters_the_pulled_file()
    print("ok")
