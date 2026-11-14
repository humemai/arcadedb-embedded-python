"""An arm that runs one workload of its lane (runner.ARM_RUNS) is declared 'not measured' in the cells of the other workload's table it still prints
a row on (2026-11-14, first landing of the n=3 rows).

CrateDB ran the document analytics only (no multi-statement transaction). The document OLTP table still prints its row because ingest is shared
across the lane, and its transaction columns were blank with nothing declaring why (page_check A1: 'BLANK docs_oltp: cratedb tpc has no new-order p50 ms').
`_declare_arm_runs_absences` declares each blank column of such a row, with a sentence that states the plain fact; the columns the row does print
(ingest) and the arms that run the workload are left alone.
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="arm-runs-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l1tpc")
import export_web as EW  # noqa: E402


def test_a_row_of_an_arm_that_does_not_run_the_workload_declares_its_blank_columns():
    table = {"id": "docs_oltp", "columns": ["new-order p50 ms", "payment p50 ms", "ingest s"], "entries": [
        {"backend": "CrateDB", "backend_key": "cratedb_tpc", "scale": "tpch1", "metrics": {"ingest s": {"median": 185.0, "n": 3}}},
        {"backend": "PostgreSQL", "backend_key": "postgres", "scale": "tpch1",
         "metrics": {"ingest s": {"median": 90.0, "n": 3}, "new-order p50 ms": {"median": 2.39, "n": 3}}}]}
    EW._DECLARED_ABSENCES.clear()
    EW._declare_arm_runs_absences([table])
    got = EW._DECLARED_ABSENCES["docs_oltp"]
    cols = {(a["backend"], a["column"]) for a in got}
    assert cols == {("CrateDB", "new-order p50 ms"), ("CrateDB", "payment p50 ms")}, got
    assert all(a["kind"] == "not measured" for a in got), got
    why = got[0]["why"]
    assert "CrateDB" in why and "analytics" in why and "transaction" in why, why
    EW._DECLARED_ABSENCES.clear()
    # the arm's own workload's table is untouched
    olap = {"id": "docs_olap", "columns": ["Q1 p50 ms"], "entries": [
        {"backend": "CrateDB", "backend_key": "cratedb_tpc", "scale": "tpch1", "metrics": {"Q1 p50 ms": {"median": 5.0, "n": 3}}}]}
    EW._declare_arm_runs_absences([olap])
    assert not EW._DECLARED_ABSENCES.get("docs_olap"), EW._DECLARED_ABSENCES


if __name__ == "__main__":
    test_a_row_of_an_arm_that_does_not_run_the_workload_declares_its_blank_columns()
    print("ok")
