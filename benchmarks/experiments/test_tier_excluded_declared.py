"""A query the protocol does not run at a table's size is declared, not blank and not a MISS (2026-11-14, first landing of the n=3 rows).

LSQB Q6 and Q9 are not run at sf1full for any engine (graph_common.TIER_EXCLUDED); every l2 row at that size records `lsqb_q6_excluded_at_tier`, and
page_check's NOT_PRINTED entry for that field said 'OWED: the exporter should turn this field into a declared absence'. The graph analytics table prints only
that size, so the two columns have no data, are not built, and page_check A1 reported 'MISS l2olap: the query set says this table carries LSQB Q6 p50 ms'.

Exporter: `_declare_excluded_at_tier_absences` declares each excluded query's column for every engine the table prints ('not measured') and says it once
under the table. page_check: an operation with no column passes when the table declares it for every engine it prints; with no declaration it is still a MISS.
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="tier-excluded-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l2")
import export_web as EW  # noqa: E402
import page_check as PC  # noqa: E402


def _table():
    cell = {"median": 5.0, "n": 3}
    return {"id": "l2olap", "columns": ["friends in same city p50 ms"], "entries": [
        {"backend": "ArcadeDB", "backend_key": "arcadedb_graph_embedded", "scale": "sf1full", "metrics": {"friends in same city p50 ms": cell}},
        {"backend": "Neo4j", "backend_key": "neo4j_graph", "scale": "sf1full", "metrics": {"friends in same city p50 ms": cell}}]}


def test_the_exporter_declares_the_excluded_queries_for_every_engine_and_says_it_once():
    rows = [{"lane": "l2", "workload": "olap", "scale": "sf1full", "backend": "neo4j_graph",
             "lsqb_q6_excluded_at_tier": "not measurable at this size: x", "lsqb_q9_excluded_at_tier": "not measurable at this size: y"}]
    old = list(EW._FROZEN_ROWS)
    EW._DECLARED_ABSENCES.clear()
    t = _table()
    try:
        EW._FROZEN_ROWS[:] = rows
        EW._declare_excluded_at_tier_absences([t])
    finally:
        EW._FROZEN_ROWS[:] = old
    got = {(a["backend"], a["column"]): a for a in EW._DECLARED_ABSENCES["l2olap"]}
    assert set(got) == {(b, c) for b in ("ArcadeDB", "Neo4j") for c in ("LSQB Q6 p50 ms", "LSQB Q9 p50 ms")}, sorted(got)
    assert all(a["kind"] == "not measured" for a in got.values())
    said = [c for c in t["conditions"] if "LSQB Q6" in c and "LSQB Q9" in c and "not run at this size" in c]
    assert len(said) == 1, t.get("conditions")
    assert any(r["text"] == said[0] and "LSQB Q6" in r["values"] for r in EW._GENERATED)
    EW._DECLARED_ABSENCES.clear()


def _a1(table):
    saved = PC.OPERATION_MANIFEST
    PC.OPERATION_MANIFEST = {"l2olap": ["LSQB Q6 p50 ms", "friends in same city p50 ms"]}
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            got = PC._coverage_a1({"l2olap": table})
    finally:
        PC.OPERATION_MANIFEST = saved
    return got, out.getvalue()


def test_a1_accepts_an_absent_column_only_when_every_engine_declares_it():
    t = _table()
    (exp, pres, dec, und, bad), out = _a1(t)
    assert bad == 1 and "MISS   l2olap" in out, out
    t["declared_absences"] = [{"backend": b, "column": "LSQB Q6 p50 ms", "kind": "not measured", "why": "x"} for b in ("ArcadeDB", "Neo4j")]
    (exp, pres, dec, und, bad), out = _a1(t)
    assert bad == 0 and dec == 2 and pres == 2, (bad, dec, pres, out)
    t["declared_absences"].pop()                # one engine undeclared: still a MISS
    (exp, pres, dec, und, bad), out = _a1(t)
    assert bad == 1, out


if __name__ == "__main__":
    test_the_exporter_declares_the_excluded_queries_for_every_engine_and_says_it_once()
    test_a1_accepts_an_absent_column_only_when_every_engine_declares_it()
    print("ok")
