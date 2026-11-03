"""Instrument 2026-12 (#352 items 1, 3, 4; #555): exact peak per phase, settled disk per phase, the sampled breakdown beside the peak.

Two halves. The first pins what a 2026-11 (or unset) cell writes, so the next instrument cannot change the one the paper pass is
measuring: the exact set of row fields, and that none of the 2026-12 machinery exists unless BENCH_INSTRUMENT=2026-12. The second
tests the 2026-12 behaviour on fake cgroup directories (no Docker, no engine)."""
import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_common  # noqa: E402
import memory_probe as mp  # noqa: E402
from test_memory_probe import FakeSampler, _cgroup, _drive  # noqa: E402

# Every field name 2026-12 adds. A 2026-11 row has none of them.
_PH = "(?:" + "|".join(mp.PHASES) + ")"
_V12_FIELD = re.compile(
    rf"^(?:mem_{_PH}_(?:peak_kind|peak_unavailable_reason|peak_upper_mib|peak_sampled_mib|peak_owned_sampled_mib|peak_anon_sampled_mib"
    rf"|peak_shmem_sampled_mib|peak_file_sampled_mib|peak_samples|peak_server_mib|peak_client_mib)"
    rf"|disk_{_PH}_(?:settled|settle_s|note)|phase_{_PH}_probe_s|mem_probe_peak_reset_error)$")


def _is_v12_field(k):
    return bool(_V12_FIELD.match(k))


def _py(code, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("BENCH_INSTRUMENT", "BENCH_MEMPROBE_DIR")}
    e.update(env)
    return subprocess.run([sys.executable, "-c", code], cwd=HERE, env=e, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 2026-11 is unchanged

# The fields fields_from() writes for one phase with every optional part present, and the cell-level ones. Pinned by name: this is
# the 2026-11 row schema.
PINNED_2611_PHASE = [
    "mem_load_owned_mib", "mem_load_anon_mib", "mem_load_shmem_mib", "mem_load_file_mib", "mem_load_peak_mib",
    "mem_load_server_owned_mib", "mem_load_client_owned_mib",
    "disk_load_mib", "disk_load_data_mib", "disk_load_wal_mib",
    "io_load_read_mib", "io_load_write_mib",
    "jvm_load_used_after_gc_mib", "jvm_load_committed_mib", "jvm_load_direct_mib",
    "proc_load_anon_mib", "proc_load_rss_mib",
]
PINNED_2611_CELL = [
    "mem_probe_phases", "mem_probe_peak_kind", "mem_probe_gc_s", "jvm_forced_gc_phases", "jvm_probe_source",
    "disk_close_mib", "disk_close_data_mib", "phase_probe_s", "mem_probe_peak_reset", "phase_probe_error",
]


def _record_2611():
    return {"load": {"owned": 3 << 20, "anon": 2 << 20, "shmem": 1 << 20, "file": 4 << 20, "peak": 9 << 20, "peak_kind": "kernel-reset",
                     "by_side": {"server": 2 << 20, "client": 1 << 20},
                     "disk": {"mib": 60.0, "wal": 2.0},
                     "io": {"server": {"rbytes": 1 << 20, "wbytes": 2 << 20}},
                     "jvm": {"used": 5 << 20, "committed": 8 << 20, "direct": 1 << 20, "forced": True, "source": "jcmd"},
                     "proc": {"anon": 1 << 20, "rss": 2 << 20}, "gc_ms": 12.0}}


def test_2611_row_schema_is_pinned():
    row = mp.fields_from(_record_2611(), ["boom"], 0.5, True,
                         {"client_disk_baseline_mb": 10.0, "client_disk_mb": 50.0}, "client")
    assert sorted(row) == sorted(PINNED_2611_PHASE + PINNED_2611_CELL)
    assert row["mem_probe_peak_kind"] == "kernel-reset" and row["mem_load_peak_mib"] == 9.0
    # an unavailable-peak 2026-11 record still falls back to the sampler's label, never to a 2026-12 kind
    rec = _record_2611()
    rec["load"].update(peak=None, peak_kind="sampled-0.25s")
    row = mp.fields_from(rec, [], 0.0, False)
    assert row["mem_probe_peak_kind"] == "sampled-0.25s" and "mem_load_peak_mib" not in row
    assert not [k for k in row if _is_v12_field(k)]


def test_2611_runs_no_2612_machinery(tmp_path):
    assert bench_common.INSTRUMENT == "2026-11"          # the suite runs on the default instrument
    assert mp.v12() is False
    assert mp._ack_timeout_s() == mp.ACK_TIMEOUT_S
    cg = _cgroup(tmp_path, "cli")
    seen = []

    def fake_settle(cid, **kw):                           # must never be called, and never replace the single-sample reader
        seen.append(kw)
        return {"disk_mb": 1.0}

    host = mp.HostProbe("r11", str(tmp_path / "raw"), exec_fn=lambda cid, argv, timeout=60: (0, ""))
    host.settle_disk_fn = fake_settle
    host.docker_args()
    host.start([("client", FakeSampler("c", [(0, 100), (0.25, 7340032)]))], lambda cid: cg, lambda cid: {"disk_mb": 7.0})
    assert host.v12 is False and host.psamplers == {} and host.disk_fn(None) == {"disk_mb": 7.0}
    row = _drive(host, ["build-done", "post-build-done", "close-start"])
    assert seen == []
    assert not [k for k in row if _is_v12_field(k)], [k for k in row if _is_v12_field(k)]
    assert row["mem_load_peak_mib"] == 9.0
    assert row["disk_load_mib"] == 7.0 and "disk_load_settled" not in row
    assert host.records["load"].get("v12") is None
    assert "settle_s" not in host.records["load"]["disk"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write any cgroup file")
def test_2611_unresettable_peak_is_still_the_sampled_one(tmp_path):
    cg = _cgroup(tmp_path, "cli")
    os.chmod(os.path.join(cg, "memory.peak"), 0o444)
    host = mp.HostProbe("r12", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c", [(0.0, 100), (0.25, 7340032)]))], lambda cid: cg)
    row = _drive(host, ["build-done"])
    assert row["mem_probe_peak_kind"] == "sampled-0.25s" and row["mem_load_peak_mib"] == 7.0
    assert not [k for k in row if _is_v12_field(k)]


def test_the_selector_gates_2612_in_a_subprocess():
    for env, want in (({}, "False"), ({"BENCH_INSTRUMENT": "2026-11"}, "False"), ({"BENCH_INSTRUMENT": "2026-12"}, "True")):
        r = _py("import memory_probe as m, bench_common as b; print(b.INSTRUMENT, m.v12(), m.HostProbe('x', '/tmp/x').v12)", **env)
        assert r.returncode == 0, r.stderr
        assert r.stdout.split()[1:] == [want, want], (env, r.stdout)


def test_runner_hook_for_2612_is_gated():
    src = open(os.path.join(HERE, "runner.py")).read()
    i = src.index("_mp.settle_disk_fn = container_disk")
    assert 'if _mp and bench_common.instrument_at_least("2026-12"):' in src[i - 200:i]
    # the 2026-11 call is unchanged: one sample per phase
    assert "_mp.start(samplers, cgroup_dir, lambda c: container_disk(c, tries=1))" in src


# ---------------------------------------------------------------------------
# 2026-12

@pytest.fixture
def v12(monkeypatch):
    monkeypatch.setattr(bench_common, "INSTRUMENT", "2026-12")
    monkeypatch.delenv("BENCH_DISK_SETTLE_S", raising=False)
    monkeypatch.delenv("BENCH_DISK_SETTLE_TRIES", raising=False)
    assert mp.v12()


def _set_peak(cg, n):
    p = os.path.join(cg, "memory.peak")
    os.chmod(p, 0o644)
    with open(p, "w") as fh:
        fh.write(f"{n}\n")
    os.chmod(p, 0o444)


def test_2612_is_a_known_instrument_and_the_lane_waits_longer(v12):
    assert bench_common.INSTRUMENTS == ("2026-11", "2026-12")
    assert mp._ack_timeout_s() == mp.V12_ACK_TIMEOUT_S > mp.ACK_TIMEOUT_S


def test_2612_reset_mode_peak_is_exact_and_the_breakdown_is_beside_it(v12, tmp_path):
    cg = _cgroup(tmp_path, "cli")
    host = mp.HostProbe("r21", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c"))], lambda cid: cg)
    assert set(host.psamplers) == {"client"}
    row = _drive(host, ["build-done"])       # one phase: a fake memory.peak file cannot answer a second read after the reset write
    for ph in ("load",):
        assert row[f"mem_{ph}_peak_kind"] == "kernel-reset" and row[f"mem_{ph}_peak_mib"] == 9.0
        assert row[f"mem_{ph}_peak_client_mib"] == 9.0
        assert f"mem_{ph}_peak_unavailable_reason" not in row
        assert row[f"mem_{ph}_peak_anon_sampled_mib"] == 1.0 and row[f"mem_{ph}_peak_shmem_sampled_mib"] == 0.5
        assert row[f"mem_{ph}_peak_owned_sampled_mib"] == 1.5 and row[f"mem_{ph}_peak_file_sampled_mib"] == 2.0
        assert row[f"mem_{ph}_peak_sampled_mib"] == 4.0 and row[f"mem_{ph}_peak_samples"] >= 1
        assert row[f"phase_{ph}_probe_s"] >= 0
        assert row[f"mem_{ph}_owned_mib"] == 1.5                 # the 2026-11 headline is still there, unchanged
    assert row["mem_probe_peak_kind"] == "kernel-reset" and "mem_probe_peak_reset_error" not in row


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write any cgroup file")
def test_2612_refused_reset_gives_exact_peak_only_where_the_cell_peak_rose(v12, tmp_path):
    cg = _cgroup(tmp_path, "cli")                                # memory.peak reads 9 MiB
    os.chmod(os.path.join(cg, "memory.peak"), 0o444)
    host = mp.HostProbe("r22", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c"))], lambda cid: cg)
    lane = mp.LaneProbe(host.dir)
    lane.idle_s = 0.0
    lane.on_mark("build-done")                                   # first phase: everything so far is in it, exact
    lane.on_mark("post-build-done")                              # the cell peak did not rise: not known
    _set_peak(cg, 12 << 20)
    lane.on_mark("warmup-done")                                  # it rose to 12: this phase's maximum, exact
    assert not lane.dead
    row = host.finish()
    assert row["mem_load_peak_kind"] == "kernel-cumulative-rise" and row["mem_load_peak_mib"] == 9.0
    assert row["mem_index_build_peak_kind"] == "unavailable"
    assert "mem_index_build_peak_mib" not in row and "mem_index_build_peak_client_mib" not in row     # never a stand-in
    assert "memory.peak cannot be reset" in row["mem_index_build_peak_unavailable_reason"]
    assert "open for write: EACCES" in row["mem_index_build_peak_unavailable_reason"]
    assert row["mem_index_build_peak_upper_mib"] == 9.0          # the bounds are facts: sampled maximum below, cell peak above
    assert row["mem_index_build_peak_sampled_mib"] == 4.0
    assert row["mem_warmup_peak_kind"] == "kernel-cumulative-rise" and row["mem_warmup_peak_mib"] == 12.0
    assert row["mem_probe_peak_kind"] == "mixed" and row["mem_probe_peak_reset"] is False
    assert row["mem_probe_peak_reset_error"].startswith("open for write: EACCES")


def test_2612_a_phase_read_twice_keeps_the_larger_exact_peak_and_never_invents_one():
    def v(kind, b, sampled):
        return {"peak_kind": kind, "peak_bytes": b, "peak_by_side": {"client": b} if b else {}, "peak_reason": None if b else "why",
                "sampled": {"anon": sampled, "shmem": 0, "file": 0, "owned": sampled, "current": sampled, "n": 2}, "disk": {}}
    m = mp._v12_merge(v("kernel-reset", 5, 1), v("kernel-reset", 9, 3))
    assert m["peak_bytes"] == 9 and m["peak_by_side"] == {"client": 9} and m["sampled"]["anon"] == 3 and m["sampled"]["n"] == 4
    m = mp._v12_merge(v("kernel-reset", 5, 1), v("unavailable", None, 3))
    assert m["peak_kind"] == "unavailable" and m["peak_bytes"] is None and m["peak_reason"] == "why"
    assert mp._v12_merge(None, v("kernel-reset", 5, 1))["peak_bytes"] == 5


def test_2612_disk_per_phase_settles_and_says_whether_it_did(v12, tmp_path):
    cg = _cgroup(tmp_path, "srv")
    calls = []

    def settle(cid, settle_s=3.0, tries=3):
        calls.append((cid, settle_s, tries))
        return {"disk_mb": 100.0, "disk_settled": False, "disk_note": "still moving after 20 samples: 99.0 -> 100.0 MiB"}

    host = mp.HostProbe("r23", str(tmp_path / "raw"), exec_fn=lambda cid, argv, timeout=60: (0, "2048\n"))
    host.settle_disk_fn = settle
    host.docker_args()
    host.start([("client", FakeSampler("c"))], lambda cid: cg, lambda cid: pytest.fail("the single-sample reader must be replaced"))
    row = _drive(host, ["build-done"])
    assert calls == [("c", mp.V12_DISK_SETTLE_S, mp.V12_DISK_TRIES)] and mp.V12_DISK_TRIES > 3
    assert row["disk_load_mib"] == 100.0 and row["disk_load_wal_mib"] == 2.0
    assert row["disk_load_settled"] is False and row["disk_load_note"].startswith("still moving")
    assert row["disk_load_settle_s"] >= 0


def test_2612_settle_window_can_be_set_from_the_environment(v12, monkeypatch, tmp_path):
    monkeypatch.setenv("BENCH_DISK_SETTLE_TRIES", "7")
    monkeypatch.setenv("BENCH_DISK_SETTLE_S", "1.5")
    calls = []
    host = mp.HostProbe("r24", str(tmp_path / "raw"))
    host.settle_disk_fn = lambda cid, settle_s, tries: calls.append((settle_s, tries)) or {"disk_mb": 1.0, "disk_settled": True}
    host._v12_disk("c")
    assert calls == [(1.5, 7)]
