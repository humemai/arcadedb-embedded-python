"""resource_check: the publish gate for resource values that cannot be right (issue #349).

Run with `python -m pytest test_resource_check.py -q` from this directory.

Synthetic rows, one behaviour each, so that an edit which makes the gate pass while proving
nothing fails here: a LOW disk, a LOW memory, the shared-memory excuse (and the case where it
must not apply), a BY_DESIGN entry, a NEGATIVE disk, a PRE_DISK step that did not return 0,
failed rows, the lanes whose page tables show no such column, and rows of another instrument.
The second half holds export_web's shared-memory disclosure to the same definition the gate
excuses, so the page explains exactly the entries the gate lets through.
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
    r = {"lane": lane, "scale": scale, "workload": workload, "durability_class": "relaxed", "backend": backend,
         "instrument": "2026-10", "rc": 0, "rep": 1, "disk_data_mb": disk, "peak_anon_mib_sum": anon,
         "peak_shmem_mib_sum": shm}
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
    flags, _ = kinds(group(peak_anon_mib_sum=10.0))
    assert flags == [("LOW", "duckdb", "memory")]


def test_a_group_of_two_has_nothing_to_compare_against():
    flags, _ = kinds([row("duckdb", disk_data_mb=1.0), row("sqlite")])
    assert flags == []


def test_an_engine_with_more_shared_than_anonymous_memory_is_not_flagged_low_for_memory():
    flags, _ = kinds(group(peak_anon_mib_sum=10.0, peak_shmem_mib_sum=9000.0))
    assert flags == []


def test_the_excuse_is_the_rows_and_not_the_name():
    """Little shared memory is not an excuse: the same low cell with less shared than anonymous memory is flagged."""
    flags, _ = kinds(group(peak_anon_mib_sum=10.0, peak_shmem_mib_sum=5.0))
    assert flags == [("LOW", "duckdb", "memory")]
    flags, _ = kinds(group(peak_anon_mib_sum=10.0, peak_shmem_mib_sum=""))
    assert flags == [("LOW", "duckdb", "memory")]


def test_the_shared_memory_excuse_does_not_cover_disk():
    flags, _ = kinds(group(disk_data_mb=1.0, peak_anon_mib_sum=10.0, peak_shmem_mib_sum=9000.0))
    assert flags == [("LOW", "duckdb", "disk")]


def test_by_design_is_known_and_not_a_failure(monkeypatch, capsys):
    rows = [row(b) for b in ("duckdb", "sqlite", "chroma")] + [row("sqlite_vec_dense", peak_anon_mib_sum=10.0)]
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
    flags, not_checked = kinds(group(disk_data_mb=-5.0, peak_anon_mib_sum=0.0, **bad))
    assert flags == []
    assert sum(n for why, n in not_checked.items() if "failed" in why) == 1


@pytest.mark.parametrize("lane", ["lifecycle", "restart"])
def test_lifecycle_and_restart_are_not_checked(lane):
    rows = [row(b, lane=lane) for b in ENGINES]
    rows[0] = dict(rows[0], disk_data_mb=-5.0, peak_anon_mib_sum=1.0)
    flags, not_checked = kinds(rows)
    assert flags == []
    assert sum(not_checked.values()) == 4 and all(why.startswith(lane) for why in not_checked)


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


# ---- the page's disclosure follows the same definition as the gate's excuse

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


def test_gate_and_page_agree_on_which_rows_hold_shared_memory(EW):
    cases = [([row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=9000.0)], True),
             ([row("a", peak_anon_mib_sum=9000.0, peak_shmem_mib_sum=10.0)], False),
             ([row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=10.0)], False),
             ([row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum="")], False),
             ([row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=50.0), row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=50.0),
               row("a", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=1.0)], True),
             ([], False)]
    for rows, expected in cases:
        assert RC.holds_shared_memory(rows) is expected is EW._holds_shared_memory(rows)


def _table(EW, tid, *entries):
    return {"id": tid, "entries": [{"backend": EW.display_name(b), "scale": "small", "scale_label": "1M vectors",
                                    "metrics": {"peak memory GiB": {"median": m}}} for b, m in entries]}


def test_page_discloses_every_entry_that_holds_more_shared_than_anonymous_memory(EW, monkeypatch):
    rows = [row("pgvector_dense", peak_anon_mib_sum=91.0, peak_shmem_mib_sum=9737.0),
            row("duckdb_dense", peak_anon_mib_sum=2000.0, peak_shmem_mib_sum=3.0),
            row("timescaledb", lane="l4", scale="ts100", workload="ingest", peak_anon_mib_sum=50.0, peak_shmem_mib_sum=700.0)]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
    note = EW._shared_memory_note(_table(EW, "l3d", ("pgvector_dense", 91.0 / 1024), ("duckdb_dense", 2000.0 / 1024)))
    assert note.startswith("pgvector holds more memory as shared memory than in its own address space")
    assert "duckdb" not in note.lower()                         # little shared memory: nothing to disclose
    assert "pgvector at 1M vectors shows 0.09 GiB where its rows held 9.51 GiB of shared memory" in note
    # every number the sentence carries is registered as generated
    vals = {v for rec in EW._GENERATED if rec["text"] == note for v in rec["values"]}
    assert {"0.09", "9.51", "1M vectors"} <= vals
    # a table of engines that hold their memory themselves gets no sentence at all
    assert EW._shared_memory_note(_table(EW, "l3d", ("duckdb_dense", 2.0))) is None


def test_page_note_is_not_a_list_of_names(EW, monkeypatch):
    """An engine nobody has heard of is disclosed the moment its rows hold more shared than anonymous memory."""
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [row("pgvector_dense", peak_anon_mib_sum=10.0, peak_shmem_mib_sum=20.0)])
    assert EW._shared_memory_note(_table(EW, "l3d", ("pgvector_dense", 0.01))) is not None
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [row("pgvector_dense", peak_anon_mib_sum=20.0, peak_shmem_mib_sum=10.0)])
    assert EW._shared_memory_note(_table(EW, "l3d", ("pgvector_dense", 0.02))) is None


def test_two_engines_share_one_sentence_and_the_plural_agrees(EW, monkeypatch):
    rows = [row("pgvector_dense", peak_anon_mib_sum=91.0, peak_shmem_mib_sum=9737.0),
            row("milvus_dense", peak_anon_mib_sum=100.0, peak_shmem_mib_sum=4096.0)]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
    note = EW._shared_memory_note(_table(EW, "l3d", ("pgvector_dense", 0.09), ("milvus_dense", 0.1)))
    assert f"{EW.display_name('milvus_dense')} and pgvector hold more memory" in note
    assert "their memory cells are not comparable" in note


def test_the_plain_postgresql_arm_keeps_its_own_sentence(EW, monkeypatch):
    rows = [row("postgres", lane="l1tpc", scale="tpch1", workload="oltp", peak_anon_mib_sum=120.0, peak_shmem_mib_sum=3000.0,
                client_peak_anon_mib=110.0, server_peak_anon_mib=10.0)]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", rows)
    table = {"id": "docs_oltp", "entries": [{"backend": EW.display_name("postgres"), "scale": "tpch1", "scale_label": "TPC-H SF1",
                                             "metrics": {"peak memory GiB": {"median": 120.0 / 1024}}}]}
    pg = EW._pg_memory_note(table)
    assert pg and "PostgreSQL's memory cell is not comparable to the others" in pg
    assert EW._shared_memory_note(table) is None                # said once, by the sentence that also splits the cell
