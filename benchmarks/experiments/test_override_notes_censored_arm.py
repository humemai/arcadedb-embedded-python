"""An override's sentence is owed to a table that prints the arm as an empty 'did not finish' row, not only as a measured one (2026-11-14, first landing).

DuckPGQ never finished the graph OLTP cells: the l2 table prints it as a row of marks (export_web._censored_entries, added by _finish_table AFTER the
override sentences are generated), and page_check refused the table because it 'shows a backend that runs `duckdb_threads` and no sentence says so'.
The sentences are now generated for the arms the table will print, measured or not: `_override_backend_keys(table)`.
Light: a temporary run log. Run with pytest, or as plain functions from this directory.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="override-censored-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l2")
import export_web as EW  # noqa: E402
import override_registry as OV  # noqa: E402


def test_the_threads_sentence_reaches_a_table_that_prints_the_arm_only_as_a_censored_row():
    tmp = Path(tempfile.mkdtemp(prefix="override-censored-rows-"))
    row = {"lane": "l2", "scale": "sf1", "workload": "oltp", "backend": "duckpgq_graph", "rep": 1, "engine_commit": "abc123def",
           "instrument": "2026-11", "rc": -1, "error": "timeout_after_3600s"}
    (tmp / "runs.jsonl").write_text(json.dumps(row) + "\n")
    old = {k: os.environ.get(k) for k in ("BENCH_ENGINE_COMMIT", "BENCH_COMPARATOR_PIN")}
    os.environ["BENCH_ENGINE_COMMIT"] = "abc123def"
    os.environ.pop("BENCH_COMPARATOR_PIN", None)
    real = EW.RESULTS
    EW.RESULTS, EW._CENSORED_CACHE = tmp, None
    try:
        table = {"id": "l2", "columns": ["point p50 ms"],
                 "entries": [{"backend": "ArcadeDB", "backend_key": "arcadedb_graph_embedded", "scale": "sf1",
                              "metrics": {"point p50 ms": {"median": 1.0, "n": 3}}}]}
        keys = EW._override_backend_keys(table)
        assert "duckpgq_graph" in keys and "arcadedb_graph_embedded" in keys, keys
        rows = [{"lane": "l2", "backend": "duckpgq_graph", "duckdb_threads": 8}]
        notes = OV.notes_for_table("l2", "l2", keys, rows)
        assert any("DuckDB is given one thread" in text for text, _v in notes), notes
    finally:
        EW.RESULTS, EW._CENSORED_CACHE = real, None
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    test_the_threads_sentence_reaches_a_table_that_prints_the_arm_only_as_a_censored_row()
    print("ok")
