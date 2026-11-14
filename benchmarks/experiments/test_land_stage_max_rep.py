"""land_stage.py --max-rep N lands repetitions 1..N only, and N defaults to 3 (2026-11-14: the page is n=3 while the comparator passes 4 and 5
appended rep 4 and rep 5 rows to the same rows file on the bench host); --max-rep 0 is the explicit opt-out, and a row whose `rep` is not
an integer refuses loudly (row number, run id and the file), by default too.

Light tests (temporary files, no network, no pytest fixture; run with pytest or as plain functions from this directory):

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


def _run_main(rows, flags):
    """(rc or the SystemExit, kept rows of the filtered file or None, stdout, pulled path): land_stage.main() --dry-run on a pulled file of `rows`."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pulled = root / "pulled.jsonl"
        pulled.write_text("".join(json.dumps(r) + "\n" for r in rows))
        scratch = root / "scratch"
        scratch.mkdir()
        (root / "results").mkdir()
        argv = ["land_stage.py", "--pin", "abc123def"] + flags + ["--dry-run", "--message", "m"]
        out = io.StringIO()
        env = {**__import__("os").environ, "BENCH_LAND_PULLED_FILE": str(pulled)}
        with mock.patch.object(sys, "argv", argv), mock.patch.object(L, "SCRATCH", scratch), mock.patch.object(L.os, "environ", env), \
                mock.patch.object(L, "RESULTS", root / "results"), mock.patch.object(L, "sh", lambda *a, **k: None), mock.patch.object(L.os, "execv", lambda *a, **k: None), \
                mock.patch.object(L, "pull_pycost", lambda *a, **k: None), contextlib.redirect_stdout(out):
            try:
                rc = L.main()
            except SystemExit as e:
                return e, None, out.getvalue(), str(pulled)
        f = scratch / "runs_page_filtered.jsonl"
        kept = [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else None
        return rc, kept, out.getvalue(), str(pulled)


def test_main_dry_run_with_max_rep_filters_the_pulled_file():
    rows = [_row(r, c) for c in "abc" for r in (1, 2, 3, 4, 5)]
    rc, kept, out, _ = _run_main(rows, ["--max-rep", "3"])
    assert rc == 0, out
    assert len(kept) == 9 and sorted({r["rep"] for r in kept}) == [1, 2, 3], (len(kept), out)
    assert "--max-rep 3" in out and "6" in out, out


def test_without_the_flag_a_landing_is_n3_and_drops_rep_4_and_5():
    """The plan is n=3 (2026-11-14): a landing that forgets --max-rep must not publish the stray rep 4 or rep 5 rows."""
    assert L.MAX_REP_DEFAULT == 3
    rows = [_row(r, c) for c in "abc" for r in (1, 2, 3, 4, 5)]
    rc, kept, out, _ = _run_main(rows, [])
    assert rc == 0, out
    assert len(kept) == 9 and sorted({r["rep"] for r in kept}) == [1, 2, 3], (len(kept), out)
    assert "--max-rep 3: 6 row(s) of later repetitions left out" in out, out


def test_an_explicit_max_rep_0_keeps_every_repetition():
    rows = [_row(r, c) for c in "abc" for r in (1, 2, 3, 4, 5)]
    rc, kept, out, _ = _run_main(rows, ["--max-rep", "0"])
    assert rc == 0, out
    assert len(kept) == 15 and sorted({r["rep"] for r in kept}) == [1, 2, 3, 4, 5], (len(kept), out)
    assert "later repetitions left out" not in out, out


def test_a_row_with_a_non_integer_rep_refuses_by_default_naming_the_row_and_the_file():
    for bad in (None, "3", 2.5):
        rows = [_row(1, "a"), {**_row(2, "b"), "run_id": "r-bad-77", "rep": bad}, _row(3, "c")]
        rc, kept, out, pulled = _run_main(rows, [])
        assert isinstance(rc, SystemExit) and kept is None, (bad, rc, out)
        msg = str(rc.code)
        assert "REFUSING" in msg and "r-bad-77" in msg and "runs_page_host.jsonl" in msg and f"rep={bad!r}" in msg and "row 2" in msg, (bad, msg)
    for flags in (["--max-rep", "-1"],):
        rc, kept, out, _ = _run_main([_row(1)], flags)
        assert isinstance(rc, SystemExit) and "--max-rep" in str(rc.code), (flags, rc)


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
    print("ok")
