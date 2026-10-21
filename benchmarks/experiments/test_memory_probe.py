"""Memory per phase (instrument 2026-11, #352): parsers on synthetic input, the lane and host handshake, and that a row from before 2026-11 has nothing new."""
import io
import json
import os
import subprocess
import sys
import threading

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import memory_probe as mp  # noqa: E402

STAT = """anon 1048576
file 2097152
kernel 4096
slab 1024
shmem 524288
file_mapped 8192
pgfault 12
"""

SMAPS = """00400000-ffffffffff601000 ---p 00000000 00:00 0                          [rollup]
Rss:               20480 kB
Pss:               10240 kB
Anonymous:         12288 kB
"""

G1_17 = """ garbage-first heap   total 262144K, used 12345K [0x00000000f0000000, 0x0000000100000000)
  region size 1024K, 3 young (3072K), 1 survivors (1024K)
 Metaspace       used 1000K, committed 1100K, reserved 1056768K
"""
G1_21 = """ garbage-first heap   total reserved 4194304K, committed 262144K, used 12345K [0x0000000700000000, 0x0000000800000000)
  region size 2048K, 2 young (4096K), 0 survivors (0K)
 Metaspace       used 123K, committed 192K, reserved 1114112K
"""
PAR = """ PSYoungGen      total 1000K, used 100K [0x0, 0x1)
 ParOldGen       total 2000K, used 300K [0x1, 0x2)
 Metaspace       used 5K, committed 6K, reserved 7K
"""


def test_parsers():
    assert mp.parse_memory_stat(STAT) == {"anon": 1048576, "file": 2097152, "kernel": 4096, "slab": 1024,
                                          "shmem": 524288, "file_mapped": 8192}
    assert mp.parse_smaps_rollup(SMAPS) == {"rss": 20480 * 1024, "anon": 12288 * 1024}
    assert mp.parse_heap_info(G1_17) == {"used": 12345 * 1024, "committed": 262144 * 1024}
    assert mp.parse_heap_info(G1_21) == {"used": 12345 * 1024, "committed": 262144 * 1024}
    assert mp.parse_heap_info(PAR) == {"used": 400 * 1024, "committed": 3000 * 1024}
    assert mp.parse_heap_info(" ZHeap           used 28M, capacity 64M, max capacity 8192M") == {
        "used": 28 * 1048576, "committed": 64 * 1048576}
    assert mp.parse_heap_info("nothing here") == {}
    assert mp.parse_nmt_other("-   Other (reserved=100KB, committed=64KB)") == 64 * 1024
    assert mp.parse_nmt_other("Native memory tracking is not enabled") is None


def test_io_stat_is_summed_over_devices():
    assert mp.parse_io_stat("8:0 rbytes=1024 wbytes=2048 rios=1 wios=2\n259:0 rbytes=1 wbytes=2 dbytes=0\n") == {
        "rbytes": 1025, "wbytes": 2050}
    assert mp.parse_io_stat("") == {"rbytes": 0, "wbytes": 0}


def test_phase_marks():
    f = mp.phases_for_mark
    assert f("build-done") == ("load",) and f("ingest-done") == ("load",)
    assert f("post-build-done") == ("index_build",)
    assert f("warmup-done") == f("oltp-warmup-done") == f("search-warmup-done") == ("warmup",)
    assert f("close-start") == ("queries", "idle")
    for other in ("build-start", "queries-done", "connect-done", "close-done", "reads-warmup-start"):
        assert f(other) == ()


def _cgroup(tmp_path, name, stat=STAT):
    d = tmp_path / name
    d.mkdir()
    (d / "memory.current").write_text("4194304\n")
    (d / "memory.stat").write_text(stat)
    (d / "memory.peak").write_text("9437184\n")
    return str(d)


class FakeSampler:
    def __init__(self, cid, series=()):
        self.cid, self.series = cid, list(series)


def _drive(host, lane_marks, idle_s=0.0, row=None):
    """Run a LaneProbe against a HostProbe thread: the lane marks, the host answers."""
    lane = mp.LaneProbe(host.dir)
    lane.idle_s = idle_s
    for m in lane_marks:
        lane.on_mark(m)
    assert not lane.dead
    return host.finish(row)


def test_embedded_cell_fields(tmp_path):
    cg = _cgroup(tmp_path, "cli")
    host = mp.HostProbe("r1", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c", [(0, 100), (0.25, 7340032)]))], lambda cid: cg)
    row = _drive(host, ["build-start", "build-done", "post-build-done", "warmup-done", "queries-done", "close-start"])
    assert row["mem_probe_phases"] == "load,index_build,warmup,queries,idle"
    for ph in mp.PHASES:
        assert row[f"mem_{ph}_owned_mib"] == 1.5          # anon 1 MiB + shmem 0.5 MiB
        assert row[f"mem_{ph}_anon_mib"] == 1.0 and row[f"mem_{ph}_shmem_mib"] == 0.5
        assert row[f"mem_{ph}_file_mib"] == 2.0
        assert row[f"mem_{ph}_client_owned_mib"] == 1.5
        assert f"mem_{ph}_server_owned_mib" not in row
        assert f"jvm_{ph}_used_after_gc_mib" not in row      # no JVM in this process
    assert "proc_load_anon_mib" in row                    # embedded: the process's own smaps
    assert row["phase_probe_s"] >= 0 and "phase_probe_error" not in row
    assert not os.path.exists(host.dir)


def test_served_jvm_cell(tmp_path):
    cli, srv = _cgroup(tmp_path, "cli"), _cgroup(tmp_path, "srv", "anon 2097152\nfile 0\nshmem 0\n")
    calls = []

    def fake_exec(cid, argv, timeout=60):
        calls.append(argv)
        if argv[0] == "sh" and "readlink" in argv[2]:
            return 0, "7 /opt/java/bin\n"
        if argv[0] == "sh":
            return 0, "2048\n"            # the WAL script: 2048 KiB found
        if argv[-1] == "GC.run":
            return 0, "ok"
        if argv[-1] == "GC.heap_info":
            return 0, G1_21
        return 1, "Native memory tracking is not enabled"

    host = mp.HostProbe("r2", str(tmp_path / "raw"), exec_fn=fake_exec)
    host.docker_args()
    (tmp_path / "srv" / "io.stat").write_text("8:0 rbytes=1048576 wbytes=0\n")
    host.start([("server", FakeSampler("s")), ("client", FakeSampler("c"))],
               lambda cid: {"s": srv, "c": cli}[cid],
               lambda cid: {"disk_mb": {"s": 130.0, "c": 5.0}[cid]})
    (tmp_path / "srv" / "io.stat").write_text("8:0 rbytes=3145728 wbytes=5242880\n")
    row = _drive(host, ["build-done", "close-start"], row={"server_disk_baseline_mb": 30.0, "server_disk_mb": 100.0})
    assert row["disk_load_mib"] == 130.0 and row["disk_load_data_mib"] == 100.0     # the engine's side, less its empty start
    assert row["disk_load_wal_mib"] == 2.0
    assert row["io_load_read_mib"] == 2.0 and row["io_load_write_mib"] == 5.0        # a difference of two counters
    assert row["io_queries_read_mib"] == 0.0                                          # nothing moved since
    assert row["disk_close_mib"] == 100.0 and row["disk_close_data_mib"] == 70.0
    assert row["mem_load_owned_mib"] == 3.5               # (1 + 0.5) client + 2 server
    assert row["mem_load_server_owned_mib"] == 2.0 and row["mem_load_client_owned_mib"] == 1.5
    assert row["jvm_load_used_mib"] == 12.1 and "jvm_load_used_after_gc_mib" not in row      # load: no GC was forced
    assert row["jvm_queries_used_after_gc_mib"] == 12.1 and row["jvm_idle_used_after_gc_mib"] == 12.1
    assert row["jvm_forced_gc_phases"] == "queries,idle"
    assert sum(1 for a in calls if a[-1] == "GC.run") == 2
    assert row["jvm_load_committed_mib"] == 256.0
    assert "jvm_load_direct_mib" not in row               # native memory tracking off
    assert row["jvm_probe_source"] == "jcmd"
    assert "proc_load_anon_mib" not in row                # the engine is in the server, not the lane's process
    # the JVM is found once, then jcmd runs GC.run before GC.heap_info every time
    assert sum(1 for a in calls if a[0] == "sh" and "readlink" in a[2]) == 1
    assert ["/opt/java/bin/jcmd", "7", "GC.run"] in calls


def test_nonjvm_server_has_no_jvm_fields(tmp_path):
    srv = _cgroup(tmp_path, "srv")
    cli = _cgroup(tmp_path, "cli")
    host = mp.HostProbe("r3", str(tmp_path / "raw"), exec_fn=lambda cid, argv, timeout=60: (0, ""))
    host.docker_args()
    host.start([("server", FakeSampler("s")), ("client", FakeSampler("c"))], lambda cid: {"s": srv, "c": cli}[cid])
    row = _drive(host, ["build-done"])
    assert row["mem_load_owned_mib"] == 3.0
    assert not [k for k in row if k.startswith("jvm_")]


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write any cgroup file")
def test_peak_falls_back_to_the_sampler_when_it_cannot_be_reset(tmp_path):
    cg = _cgroup(tmp_path, "cli")
    os.chmod(os.path.join(cg, "memory.peak"), 0o444)
    host = mp.HostProbe("r4", str(tmp_path / "raw"))
    host.docker_args()
    s = FakeSampler("c", [(0.0, 100), (0.25, 7340032)])
    host.start([("client", s)], lambda cid: cg)
    row = _drive(host, ["build-done"])
    assert row["mem_probe_peak_kind"] == "sampled-0.25s" and row["mem_probe_peak_reset"] is False
    assert row["mem_load_peak_mib"] == 7.0


def test_peak_is_reset_through_the_kept_descriptor(tmp_path):
    cg = _cgroup(tmp_path, "cli")
    host = mp.HostProbe("r5", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c"))], lambda cid: cg)
    row = _drive(host, ["build-done"])
    assert row["mem_probe_peak_kind"] == "kernel-reset" and row["mem_probe_peak_reset"] is True
    assert row["mem_load_peak_mib"] == 9.0
    # a real memory.peak would now read lower; here the write is the evidence that the reset was asked for
    assert open(os.path.join(cg, "memory.peak")).read().startswith("reset")


def test_lane_gives_up_when_nobody_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(mp, "ACK_TIMEOUT_S", 0.05)
    lane = mp.LaneProbe(str(tmp_path))
    lane.on_mark("build-done")
    assert lane.dead
    lane.on_mark("close-start")      # silent from here on, no wait
    assert lane.seq == 1


# ---------------------------------------------------------------------------
# the probe is part of the instrument

def _py(code, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("BENCH_INSTRUMENT", "BENCH_MEMPROBE_DIR")}
    e.update(env)
    return subprocess.run([sys.executable, "-c", code], cwd=HERE, env=e, capture_output=True, text=True)


def test_phase_marks_import_nothing_without_a_probe_dir():
    code = ("import sys, io, bench_common as b\n"
            "cls = getattr(b, 'PhaseBeat')\n"
            "p = cls(out=io.StringIO()); p.mark('build-done'); p.mark('close-start')\n"
            "print('memory_probe' in sys.modules)\n")
    r = _py(code)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["False"]


def test_2611_enabled():
    r = _py("import memory_probe as m; print(m.enabled(), m.HostProbe.maybe('x', '/tmp/x') is not None)",
            BENCH_INSTRUMENT="2026-11")
    assert r.stdout.split() == ["True", "True"], r.stderr


def test_runner_hooks_are_gated():
    src = open(os.path.join(HERE, "runner.py")).read()
    assert src.count("_mp") >= 4
    assert "memory_probe.HostProbe.maybe(" in src
    # the name is bound before the try whose finally reads it: a cell that returns early (a server that never became ready)
    # must not raise UnboundLocalError there
    assert src.index("    _mp = None") < src.index("memory_probe.HostProbe.maybe(")


def test_export_web_column_only_for_2611(monkeypatch):
    pytest.importorskip("numpy")
    mpatch = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mpatch.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web as ew
    except SystemExit as e:      # export_web refuses to import without the campaign's untracked results
        pytest.skip(f"export_web needs the campaign results: {e}")
    finally:
        mpatch.undo()
    spec = {"metrics": [("x_ms", "x ms")]}
    base = ew._metrics_for_instrument("l1tpc", spec)
    monkeypatch.setattr(ew, "_FROZEN_ROWS", [{"lane": "l1tpc", "instrument": "2026-10"}])
    assert ew._metrics_for("l1tpc", spec) == ew._metrics_for_instrument("l1tpc", spec)
    assert ew.MEM_PHASE_COLUMN not in ew._metrics_for("l1tpc", spec)
    monkeypatch.setattr(ew, "_FROZEN_ROWS", [{"lane": "l1tpc", "instrument": "2026-11"}])
    cols = ew._metrics_for("l1tpc", spec)
    assert cols[-1] == ew.MEM_PHASE_COLUMN and cols[:-1] == ew._metrics_for_instrument("l1tpc", spec)
    assert ew._UNIT_DIVISOR[ew.MEM_PHASE_COLUMN[0]] == 1024.0


# ---------------------------------------------------------------------------
# no forced GC right before a timed phase

LANE_MARKS = {   # the PHASE markers of lane shapes, in order; "-start" markers of timed work are listed in TIMED
    "docs": ["connect-start", "connect-done", "build-start", "build-done", "oltp-warmup-start", "oltp-warmup-done",
             "new-order-start", "new-order-done", "close-start", "close-done"],
    "dense": ["build-start", "build-done", "post-build-start", "post-build-done", "warmup-start", "warmup-done",
              "queries-start", "queries-done", "close-start", "close-done"],
    "dense_no_warmup": ["build-start", "build-done", "post-build-start", "post-build-done", "queries-start",
                        "queries-done", "close-start", "close-done"],
    "sparse": ["build-start", "build-done", "post-build-start", "post-build-done", "search-warmup-start",
               "search-warmup-done", "search-start", "search-done", "close-start", "close-done"],
}
TIMED = {"new-order-start", "queries-start", "search-start", "payment-start", "query-q1-start"}


@pytest.mark.parametrize("lane", sorted(LANE_MARKS))
def test_no_forced_gc_right_before_a_timed_phase(lane):
    marks = LANE_MARKS[lane]
    for i, m in enumerate(marks):
        for ph in mp.phases_for_mark(m):
            if not mp.forces_gc(ph):
                continue
            later = marks[i + 1:]
            # a forced GC is allowed only once no timed phase is left to run (idle follows queries at the same marker)
            assert not any(x in TIMED for x in later), f"{lane}: GC forced at {ph} ({m}) before {later}"
    # and the phases that precede a timed phase in these lanes are exactly the ones never forced
    for ph in ("load", "index_build", "warmup"):
        assert not mp.forces_gc(ph)
    assert mp.FORCED_GC_PHASES == ("queries", "idle")


def test_lane_without_a_jvm_records_no_gc_phases(tmp_path):
    cg = _cgroup(tmp_path, "cli")
    host = mp.HostProbe("r6", str(tmp_path / "raw"))
    host.docker_args()
    host.start([("client", FakeSampler("c"))], lambda cid: cg)
    row = _drive(host, ["build-done", "close-start"])
    assert "jvm_forced_gc_phases" not in row
