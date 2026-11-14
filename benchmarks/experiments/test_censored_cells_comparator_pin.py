"""export_web._censored_cells reads failed and timed-out cells of the run log, scoped to the pin of the publish (BENCH_ENGINE_COMMIT).

The n=3 rows of 2026-11 land as TWO files at two pins: the ArcadeDB arms at a3a5d1245 and the comparators at e85469273 (the label of the
ArcadeDB release the comparator chain was launched with; every comparator row carries it; humemai/mmdbbench#28). A publish at the arms' pin
therefore threw away every failed and censored COMPARATOR cell, and with them the declared absences that tell a reader why a cell has no
number: page_check A1 printed 'BLANK docs_olap: SurrealDB (embedded) has no Q1 ...' and A3 'MISSING DuckPGQ [duckpgq_graph] on l2'.

BENCH_COMPARATOR_PIN (comma list, optional) names the extra pins whose rows the censored cells read. Unset: the old behaviour.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_RES = tempfile.mkdtemp(prefix="censored-pin-")
os.environ.setdefault("BENCH_RESULTS_DIR", _RES)
os.environ.setdefault("BENCH_ONLY_LANES", "l1tpc")          # a landing scoped away from e4 does not need its artifacts at import
import export_web as EW  # noqa: E402


def _rows(tmp):
    import json
    rows = [
        {"lane": "l1tpc", "scale": "tpch1", "workload": "olap", "backend": "surrealdb_tpc", "rep": 1, "engine_commit": "e85469273",
         "error": "timeout_after_7200s", "rc": -1, "instrument": "2026-11"},
        {"lane": "l1tpc", "scale": "tpch1", "workload": "olap", "backend": "duckdb", "rep": 1, "engine_commit": "e85469273",
         "instrument": "2026-11", "rc": 0},
        {"lane": "l1tpc", "scale": "tpch1", "workload": "olap", "backend": "arcadedb_embedded", "rep": 1, "engine_commit": "abc123def",
         "error": "timeout_after_3600s", "rc": -1, "instrument": "2026-11"},
    ]
    (tmp / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _cells(pin, comparator_pin):
    EW._CENSORED_CACHE = None
    old = {k: os.environ.get(k) for k in ("BENCH_ENGINE_COMMIT", "BENCH_COMPARATOR_PIN", "BENCH_RUNS_JSONL")}
    tmp = Path(tempfile.mkdtemp(prefix="censored-pin-rows-"))
    _rows(tmp)
    try:
        os.environ["BENCH_ENGINE_COMMIT"] = pin
        os.environ.pop("BENCH_COMPARATOR_PIN", None)
        if comparator_pin is not None:
            os.environ["BENCH_COMPARATOR_PIN"] = comparator_pin
        EW_RESULTS = EW.RESULTS
        EW.RESULTS = tmp
        try:
            return {k[2]: v for k, v in EW._censored_cells().items()}
        finally:
            EW.RESULTS = EW_RESULTS
    finally:
        EW._CENSORED_CACHE = None
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_a_comparator_pin_is_read_and_the_default_is_unchanged():
    only_arms_pin = _cells("abc123def", None)
    assert set(only_arms_pin) == {"arcadedb_embedded@jvm"} or set(only_arms_pin) == {"arcadedb_embedded"} or \
        all(k.startswith("arcadedb_embedded") for k in only_arms_pin), only_arms_pin
    both = _cells("abc123def", "e85469273")
    assert "surrealdb_tpc" in both and both["surrealdb_tpc"] == 7200, both
    assert "duckdb" not in both, both          # it has a clean row at the same key: not censored
    assert any(k.startswith("arcadedb_embedded") for k in both), both
    # a prefix of the pin is accepted either way, as for the arms' pin
    assert "surrealdb_tpc" in _cells("abc123def", "e854692"), "prefix of the comparator pin"
    assert "surrealdb_tpc" not in _cells("abc123def", "ffffffff")


if __name__ == "__main__":
    test_a_comparator_pin_is_read_and_the_default_is_unchanged()
    print("ok")
