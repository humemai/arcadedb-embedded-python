"""resource_check: the publish gate for resource values that cannot be right (issue #349).

Run with `python -m pytest test_resource_check.py -q` from this directory.

Synthetic rows, one behaviour each, so that an edit which makes the gate pass while proving
nothing fails here: a LOW disk, a LOW memory, memory read as owned memory (anonymous plus shared,
the page's column since issue #353) with the anonymous peak only as a fallback, a BY_DESIGN entry,
a NEGATIVE disk, a PRE_DISK step that did not return 0, failed rows, rows that declare their
situation unexpressible, the lanes whose page tables show no such column, and rows of another
instrument. The second half holds export_web's memory column and PostgreSQL split to the same
definition: owned memory, with no shared-memory disclosure left to keep in step with the gate.
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import resource_check as RC  # noqa: E402

ENGINES = ("duckdb", "sqlite", "chroma", "lancedb")


def row(backend, lane="l3d", scale="small", workload="search", disk=100.0, anon=1000.0, shm=0.0, **extra):
    """A healthy row. peak_owned_mib_sum is anonymous plus shared, as the runner records it, unless `extra` sets it."""
    r = {"lane": lane, "scale": scale, "workload": workload, "durability_class": "relaxed", "backend": backend,
         "instrument": "2026-10", "rc": 0, "rep": 1, "disk_data_mb": disk, "peak_anon_mib_sum": anon,
         "peak_shmem_mib_sum": shm, "peak_owned_mib_sum": anon + shm}
    r.update(extra)
    return r


def group(**odd):
    """Four engines with the same healthy values, the first one changed by `odd`."""
    rows = [row(b) for b in ENGINES]
    rows[0] = dict(rows[0], **odd)
    return rows


def kinds(rows):
    flags, not_checked = RC.check(rows)
    return [(f.kind, f.backend, f.metric) for f in flags], not_checked


def test_a_healthy_group_passes():
    flags, not_checked = kinds(group())
    assert flags == [] and not not_checked


def test_low_disk_is_flagged():
    flags, _ = kinds(group(disk_data_mb=1.0))
    assert flags == [("LOW", "duckdb", "disk")]


def test_low_memory_is_flagged():
    flags, _ = kinds(group(peak_anon_mib_sum=10.0, peak_owned_mib_sum=10.0))
    assert flags == [("LOW", "duckdb", "memory")]


def test_a_group_of_two_has_nothing_to_compare_against():
    flags, _ = kinds([row("duckdb", disk_data_mb=1.0), row("sqlite")])
    assert flags == []


def test_memory_is_owned_memory_so_shared_memory_needs_no_excuse():
    """An engine that keeps its data in shared memory has a high owned peak, so nothing is flagged and nothing is excused."""
    odd = group(peak_anon_mib_sum=10.0, peak_shmem_mib_sum=9000.0, peak_owned_mib_sum=9010.0)
    assert kinds(odd)[0] == []
    assert not hasattr(RC, "holds_shared_memory")


def test_the_anonymous_peak_alone_does_not_decide():
    """The same low anonymous peak is flagged only when owned memory is low too."""
    assert RC.memory(row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=5.0, peak_owned_mib_sum=15.0)) == 15.0
    assert kinds(group(peak_anon_mib_sum=10.0, peak_shmem_mib_sum=5.0, peak_owned_mib_sum=15.0))[0] == [("LOW", "duckdb", "memory")]
    assert kinds(group(peak_anon_mib_sum=10.0, peak_owned_mib_sum=1000.0))[0] == []


def test_a_row_without_owned_memory_falls_back_to_the_anonymous_peak():
    odd = dict(row("duckdb", peak_anon_mib_sum=10.0))
    del odd["peak_owned_mib_sum"]
    assert RC.memory(odd) == 10.0
    assert RC.memory(dict(odd, peak_owned_mib_sum="")) == 10.0
    assert kinds([odd] + [row(b) for b in ENGINES[1:]])[0] == [("LOW", "duckdb", "memory")]
    assert RC.memory({"peak_anon_mib_sum": "", "peak_owned_mib_sum": ""}) is None


def test_by_design_is_known_and_not_a_failure(monkeypatch, capsys):
    rows = [row(b) for b in ("duckdb", "sqlite", "chroma")] + [row("sqlite_vec_dense", peak_anon_mib_sum=10.0, peak_owned_mib_sum=10.0)]
    flags, _ = kinds(rows)
    assert flags == [("LOW", "sqlite_vec_dense", "memory")]
    assert ("l3d", "sqlite_vec_dense", "memory") in RC.BY_DESIGN
    assert ("l3d", "sqlite_vec_dense_int8", "memory") in RC.BY_DESIGN
    monkeypatch.setattr(RC, "load_rows", lambda path=None: (rows, "synthetic"))
    monkeypatch.setattr(sys, "argv", ["resource_check.py"])
    assert RC.main() == 0
    out = capsys.readouterr().out
    assert "KNOWN LOW" in out and "ok: 0 resource values that cannot be right, 1 known" in out
    # the same value on an engine nobody explained is a failure
    rows[-1] = dict(rows[-1], backend="zzz_unexplained")
    assert RC.main() == 1


def test_negative_disk_growth_is_flagged_with_the_rows_note():
    rows = group()
    rows[1] = dict(rows[1], disk_data_mb=-95.9, disk_note="preallocated files shrank")
    flags, _ = RC.check(rows)
    assert [(f.kind, f.backend, f.value) for f in flags if f.kind == "NEGATIVE"] == [("NEGATIVE", "sqlite", -95.9)]
    assert "preallocated files shrank" in [f for f in flags if f.kind == "NEGATIVE"][0].ctx


def test_a_served_row_reads_the_server_growth_not_the_clients():
    served = row("duckdb", server_image="img", server_disk_mb=50.0, server_disk_baseline_mb=60.0, disk_data_mb=500.0)
    assert RC.disk(served) == -10.0
    assert RC.disk(row("duckdb")) == 100.0


def test_pre_disk_step_that_did_not_return_zero_is_flagged():
    rows = group()
    rows[0] = dict(rows[0], server_pre_disk="redis-cli SAVE rc=1 (ERR)", disk_note="no snapshot before the reading")
    flags, _ = RC.check(rows)
    (flag,) = [f for f in flags if f.kind == "PRE_DISK"]
    assert flag.backend == "duckdb" and "no snapshot before the reading" in flag.ctx


def test_pre_disk_step_that_returned_zero_or_is_absent_passes():
    assert kinds(group(server_pre_disk="redis-cli SAVE rc=0 OK"))[0] == []
    assert kinds(group())[0] == []
    # present and empty is a step with no result, which is not rc=0
    assert [k for k, *_ in kinds(group(server_pre_disk=""))[0]] == ["PRE_DISK"]


@pytest.mark.parametrize("bad", [{"rc": 1}, {"error": "boom"}, {"oom_killed": True}, {"server_oom_killed": "True"}])
def test_failed_rows_are_skipped_and_counted(bad):
    flags, not_checked = kinds(group(disk_data_mb=-5.0, peak_owned_mib_sum=0.0, **bad))
    assert flags == []
    assert sum(n for why, n in not_checked.items() if "failed" in why) == 1


def test_restart_is_not_checked():
    rows = [row(b, lane="restart") for b in ENGINES]
    rows[0] = dict(rows[0], disk_data_mb=-5.0, peak_owned_mib_sum=1.0)
    flags, not_checked = kinds(rows)
    assert flags == []
    assert sum(not_checked.values()) == 4 and all(why.startswith("restart") for why in not_checked)


def test_lifecycle_checks_memory_but_not_disk():
    rows = [row(b, lane="lifecycle") for b in ENGINES]
    rows[0] = dict(rows[0], disk_data_mb=-5.0, peak_owned_mib_sum=1.0)
    flags, not_checked = kinds(rows)
    assert [(k, m) for k, _, m in flags] == [("LOW", "memory")]
    assert sum(not_checked.values()) == 0


def test_a_row_declaring_its_situation_unexpressible_is_not_checked():
    rows = [row(b, lane="lifecycle") for b in ENGINES]
    rows[0] = dict(rows[0], peak_owned_mib_sum=1.0, lifecycle_situation_unexpressible="no analytical view")
    flags, not_checked = kinds(rows)
    assert flags == []
    assert sum(n for why, n in not_checked.items() if "unexpressible" in why) == 1


def test_rows_of_another_instrument_are_not_checked_and_say_so(capsys, monkeypatch):
    rows = [dict(r, instrument="") for r in group(disk_data_mb=-5.0)] + [dict(r, instrument="2026-09") for r in group()]
    flags, not_checked = kinds(rows)
    assert flags == []
    assert sum(not_checked.values()) == 8 and len(not_checked) == 2
    monkeypatch.setattr(RC, "load_rows", lambda path=None: (rows, "synthetic"))
    monkeypatch.setattr(sys, "argv", ["resource_check.py"])
    assert RC.main() == 0
    out = capsys.readouterr().out
    assert "checked 0" in out and "not checked: 4 rows, instrument (none)" in out and "instrument 2026-09" in out


def test_no_row_is_both_checked_and_counted_as_unchecked():
    rows = group() + [dict(r, instrument="2026-09") for r in group()] + [dict(r, lane="restart") for r in group()]
    _, not_checked = kinds(rows)
    assert sum(not_checked.values()) == 8


# ---- the page's memory column is the gate's measure: owned memory

@pytest.fixture(scope="module")
def EW():
    """export_web, imported once (it refuses to import without a pin in the environment)."""
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        try:
            import export_web
        except SystemExit as e:                      # the e4 artifacts are not in this checkout
            pytest.skip(f"export_web does not import here: {e}")
    finally:
        mp.undo()
    return export_web


def test_the_pages_memory_column_reads_owned_memory_with_the_anonymous_peak_as_fallback(EW):
    assert EW.MEM_PEAK_FIELD == "peak_owned_mib_sum" and EW.MEM_PEAK_FALLBACK == "peak_anon_mib_sum"
    pg = row("pgvector_dense", anon=91.0, shm=9737.0)
    assert EW._peak_mem(pg) == 91.0 + 9737.0 == RC.memory(pg)
    bare = {k: v for k, v in pg.items() if k != "peak_owned_mib_sum"}
    assert EW._peak_mem(bare) == 91.0 == RC.memory(bare)
    cell = EW._agg([pg, dict(pg), dict(pg)], EW.MEM_PEAK_FIELD)
    assert cell["median"] == round((91.0 + 9737.0) / 1024, 4) and cell["n"] == 3
    assert EW._UNIT_DIVISOR["peak_owned_mib_sum"] == 1024.0


def test_every_memory_column_of_the_page_is_owned_memory(EW):
    """No table spec still names the anonymous peak under the "peak memory GiB" header."""
    specs = [m for spec in list(EW.LANES.values()) + list(EW.OCT_METRICS.values())
             for m in (spec.get("metrics", []) if isinstance(spec, dict) else spec)]
    named = [f for f, label in specs if label == "peak memory GiB"]
    assert named and set(named) == {EW.MEM_PEAK_FIELD}


def test_the_anonymous_peak_notes_are_gone(EW):
    """Owned memory counts the shared memory, so the disclosure and its excuse no longer exist."""
    assert not hasattr(EW, "_shared_memory_note") and not hasattr(EW, "_holds_shared_memory")


def test_the_plain_postgresql_arm_splits_its_cell_into_client_and_database(EW, monkeypatch):
    rows = [row("postgres", lane="l1tpc", scale="tpch1", workload="oltp", anon=120.0, shm=3000.0,
                client_peak_anon_mib=110.0, client_peak_shmem_mib=2.0, server_peak_anon_mib=10.0, server_peak_shmem_mib=2998.0)]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
    cell = 3120.0 / 1024
    table = {"id": "docs_oltp", "entries": [{"backend": EW.display_name("postgres"), "scale": "tpch1", "scale_label": "TPC-H SF1",
                                             "metrics": {"peak memory GiB": {"median": cell}}}]}
    pg = EW._pg_memory_note(table)
    assert pg == (f"PostgreSQL's memory cell adds two containers. At TPC-H SF1, of the {cell:.2f} GiB shown, "
                  f"{112.0 / 1024:.3f} GiB is our Python client and {3008.0 / 1024:.3f} GiB is the database.")
    assert "not comparable" not in pg and "address space" not in pg
    # every number the sentence carries is registered as generated
    vals = {v for rec in EW._GENERATED if rec["text"] == pg for v in rec["values"]}
    assert {f"{cell:.2f}", f"{112.0 / 1024:.3f}", f"{3008.0 / 1024:.3f}", "TPC-H SF1"} <= vals
    # a row that lacks a per-container field gives no split rather than a wrong one
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [dict(rows[0], server_peak_shmem_mib="")])
    assert EW._pg_memory_note(table) is None
