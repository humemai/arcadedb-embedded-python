"""provenance_check.check_schema_homogeneity and cells whose reps differ only in WHERE a query hit its budget (2026-11-14, first landing of
the n=3 rows).

The check flags a (lane, scale, workload, backend) family whose rows carry different measured fields. Four cells of the n=3 rows tripped it
although every rep ran the same code under the same budget rule: a query that did not finish in one rep (hop3f at l2/sf10 on the native
wheel, LSQB q1 on PostgreSQL + AGE, q5 on MongoDB, q8 on DuckPGQ) is recorded with its cold figure and a censor/missing flag
(`<q>_censored`, `<q>_warm_missing`) instead of the warm figures and the result count, and the sibling reps that finished carry those fields.
That is an outcome at the edge of a budget, not two measurements: re-running the cell gives the same kind of split and dropping the odd rep drops
a valid row.

The rule: a field a row lacks is not a split when the same row declares the query it belongs to as censored or warm-missing; the flags
themselves are declarations, not measurements. A field missing without such a declaration is still a split (the August 2026 failure the check exists for).

Light: pure Python, no files. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# provenance_check reads the pinned overlay rows when it is imported: point it at an empty results directory and a pin, for tests only
_RES = tempfile.mkdtemp(prefix="schema-censored-")
Path(_RES, "runs.jsonl").write_text("")
os.environ.setdefault("BENCH_RESULTS_DIR", _RES)
os.environ.setdefault("BENCH_ENGINE_COMMIT", "abc123def")
import provenance_check as PC  # noqa: E402


def _row(rep, **kw):
    r = {"lane": "l2", "scale": "sf1full", "workload": "olap", "backend": "pgage_graph", "gav": True, "rep": rep, "rc": 0,
         "ts_utc": f"2026-11-13T0{rep}:00:00Z", "build_s": 90.0 + rep, "cold_lsqb_q1_ms": 50000.0 + rep, "lsqb_q1_p50_ms": 50000.0 + rep,
         "lsqb_q1_censored": True}
    r.update(kw)
    return r


def _check(rows):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bad = PC.check_schema_homogeneity(rows)
    return bad, out.getvalue()


def _finished(rep):
    return _row(rep, warm_lsqb_q1_p50_ms=43876.0, warm_lsqb_q1_p99_ms=44045.0, warm_lsqb_q1_n=6, res_lsqb_q1_n=1, lsqb_q1_rows=1)


def _abandoned(rep):
    return _row(rep, lsqb_q1_warm_missing=True, res_lsqb_q1_n=1, lsqb_q1_rows=1)


def test_a_query_that_hit_its_budget_in_one_rep_is_not_a_split():
    # LSQB q1: warm figures in reps 2 and 3, none in rep 1 (its cold pass alone used the budget) -- `lsqb_q1_warm_missing` says so
    bad, out = _check([_abandoned(1), _finished(2), _finished(3)])
    assert bad == 0, out


def test_a_censored_query_without_a_result_count_is_not_a_split():
    # MongoDB q5 / the native sf10 hop3f: the rep killed at its budget has no row count and no warm figures, and says `<q>_censored`
    def killed(rep):
        return _row(rep, lsqb_q1_warm_missing=True, res_lsqb_q1_n=None, lsqb_q1_rows=None)
    bad, out = _check([_abandoned(1), killed(2), _abandoned(3)])
    assert bad == 0, out
    hop = lambda rep, done: {"lane": "l2", "scale": "sf10", "workload": "oltp", "backend": "arcadedb_graph_embedded", "rep": rep, "rc": 0,
                              "ts_utc": f"2026-11-13T0{rep}:00:00Z", "hop3f_p50_ms": 2000.0 + rep, "hop3f_censored": not done,
                              **({"warm_hop3f_p50_ms": 2000.0, "warm_hop3f_p95_ms": 7000.0, "res_hop3f_n": 200, "warm_hop3f_censored": False}
                                 if done else {"warm_hop3f_censored": True})}
    bad, out = _check([hop(1, False), hop(2, True), hop(3, True)])
    assert bad == 0, out


def test_a_field_missing_without_a_declaration_is_still_a_split():
    # rep 1 lacks the warm figures and declares nothing about q1: a different instrument, the thing the check exists for
    bare = _row(1, lsqb_q1_censored=False)
    bad, out = _check([bare, _finished(2), _finished(3)])
    assert bad == 1 and "SPLIT SCHEMA" in out and "warm_lsqb_q1" in out, out
    # a declaration for ANOTHER query does not excuse it
    other = _row(1, lsqb_q1_censored=False, lsqb_q5_warm_missing=True)
    bad, out = _check([other, _finished(2), _finished(3)])
    assert bad == 1, out


def test_a_neighbouring_query_number_is_not_matched_by_substring():
    # a declaration for q1 must not excuse a missing field of q10 (the stem is matched as whole tokens)
    rows = [_row(1, lsqb_q1_warm_missing=True), _row(2, warm_lsqb_q10_p50_ms=5.0), _row(3, warm_lsqb_q10_p50_ms=6.0)]
    bad, out = _check(rows)
    assert bad == 1 and "warm_lsqb_q10_p50_ms" in out, out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok  ", name)
