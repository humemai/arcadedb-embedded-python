"""page_check.NOT_PRINTED covers the field families the first 2026-11 landing met (A2: every measured field is printed or declared not-printed, with a reason).

The first landing of the n=3 rows is the first time the page gate reads these rows: the per-phase sampler breakdown (mem_, jvm_, proc_, disk_, io_ per
phase), the build window of the post2 build figures, the ArangoDB IVF calibration, the per-engine settings read back from CrateDB, Redis and the servers, and the
warm-up and temperature-gate readings were measured fields that nothing printed and nothing declared (157 fields, A2 'UNCOVERED').
Every family has a pattern with a reason; a name that is a column or a result is not swallowed (the peak memory and the latency fields stay printable).
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import page_check as PC  # noqa: E402

FAMILIES = [
    "build_window_cpu_usec_sum", "build_window_disk_index_build_wal_mib", "mem_idle_anon_mib", "mem_queries_owned_mib", "jvm_load_used_after_gc_mib",
    "proc_index_build_rss_mib", "disk_close_data_mib", "io_load_read_mib", "arangodb_ivf_calibration_recall", "arangodb_ivf_recall_target",
    "cratedb_shards", "cratedb_translog_sync_interval_ms", "redis_maxmemory", "redis_search_workers", "server_cpus", "server_max_heap_bytes",
    "mem_probe_gc_s", "oltp_warmup", "oltp_warmup_s", "phase_probe_s", "precell_gate_wait_s", "recall_target", "vector_ef", "vector_ef_lane",
]
RESULTS = ["warm_point_p50_ms", "hop3f_p99_ms", "build_s", "peak_rss_mb", "recall_at_10", "insert_p50_ms", "ingest_s"]


def _covered(name):
    return any(re.search(p, name) for p, _reason in PC.NOT_PRINTED)


def test_every_family_of_the_first_landing_has_a_pattern_with_a_reason():
    uncovered = [f for f in FAMILIES if not _covered(f)]
    assert not uncovered, uncovered
    for p, reason in PC.NOT_PRINTED:
        assert isinstance(p, str) and isinstance(reason, str) and len(reason) > 40, p


def test_a_result_field_is_not_swallowed_by_the_new_patterns():
    # only the seven patterns this change added (the older, broader ones match some of these names on their own)
    mine = PC.NOT_PRINTED[-7:]
    swallowed = [f for f in RESULTS if any(re.search(p, f) for p, _r in mine)]
    assert not swallowed, swallowed


if __name__ == "__main__":
    test_every_family_of_the_first_landing_has_a_pattern_with_a_reason()
    test_a_result_field_is_not_swallowed_by_the_new_patterns()
    print("ok")
