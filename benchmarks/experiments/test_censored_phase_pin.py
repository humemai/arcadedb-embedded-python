"""The phase a censored cell was still in is a generated value of its sentence and is registered with it (2026-11-14, first landing of the n=3 rows).

`_censored_notes` says "It was still in query lsqb_q1 when the budget ran out." for a cell that hit its budget during a query. The phase comes off the
row's `timeout_phase_hint`, but only the scale and the budget were registered as the sentence's generated values, so page_check printed
`UNPINNED l2olap (generated): ['1'] in 'SurrealDB (server) at SF1FULL ...'`. The phase is now registered with the others.
Light: a temporary run log. Run with pytest, or as plain functions from this directory.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="phase-pin-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l2")
import export_web as EW  # noqa: E402


def test_the_phase_of_a_censored_cell_is_a_registered_value_of_its_sentence():
    tmp = Path(tempfile.mkdtemp(prefix="phase-pin-rows-"))
    row = {"lane": "l2", "scale": "sf1full", "workload": "olap", "backend": "surrealdb_graph_server", "rep": 1, "engine_commit": "abc123def",
           "instrument": "2026-11", "rc": -1, "error": "timeout_after_7200s", "timeout_phase_hint": "PHASE olap-start PHASE olap-lsqb_q1-start"}
    (tmp / "runs.jsonl").write_text(json.dumps(row) + "\n")
    old = {k: os.environ.get(k) for k in ("BENCH_ENGINE_COMMIT", "BENCH_COMPARATOR_PIN")}
    os.environ["BENCH_ENGINE_COMMIT"] = "abc123def"
    os.environ.pop("BENCH_COMPARATOR_PIN", None)
    real = EW.RESULTS
    EW.RESULTS, EW._CENSORED_CACHE = tmp, None
    EW._CENSORED_PHASE.clear()
    EW._DECLARED_ABSENCES.clear()
    try:
        notes = [n for n in EW._censored_notes("l2olap") if "lsqb_q1" in n]
        assert len(notes) == 1, notes
        recs = [r for r in EW._GENERATED if r["text"] == notes[0]]
        assert recs, "the sentence is not registered as generated"
        assert "query lsqb_q1" in recs[0]["values"], recs[0]["values"]
    finally:
        EW.RESULTS, EW._CENSORED_CACHE = real, None
        EW._CENSORED_PHASE.clear()
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    test_the_phase_of_a_censored_cell_is_a_registered_value_of_its_sentence()
    print("ok")
