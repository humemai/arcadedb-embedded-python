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


# The real io.stat of a cell container on the mini (2026-11-06): 259:0 is the NVMe, 252:0 the device-mapper device stacked on it,
# both charged the same 8691597312 written bytes, and 8:0 a small unrelated disk.
MINI_IO_STAT = """8:0 rbytes=0 wbytes=0 rios=0 wios=5 dbytes=0 dios=0
259:0 rbytes=0 wbytes=8691597312 rios=0 wios=82042 dbytes=0 dios=0
252:0 rbytes=0 wbytes=8691597312 rios=0 wios=22387 dbytes=0 dios=0
"""


def _block(sysfs, mm, name, slaves=(), partition_of=None):
    """One block device in a synthetic sysfs: class/block/<name> (a symlink like the real one) and dev/block/<mm>."""
    base = sysfs / "devices" / "block"
    d = base / name if partition_of is None else base / partition_of / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "dev").write_text(mm + "\n")
    if partition_of is not None:
        (d / "partition").write_text("3\n")
    (sysfs / "class" / "block").mkdir(parents=True, exist_ok=True)
    (sysfs / "class" / "block" / name).symlink_to(d)
    (sysfs / "dev" / "block").mkdir(parents=True, exist_ok=True)
    (sysfs / "dev" / "block" / mm).symlink_to(d)
    for sl in slaves:
        (d / "slaves").mkdir(exist_ok=True)
        (d / "slaves" / sl).symlink_to(sysfs / "class" / "block" / sl)


def _mini_sysfs(tmp_path):
    """nvme0n1 (259:0) with partition nvme0n1p3 (259:3); dm-0 (252:0) on that partition; sda (8:0) alone."""
    sysfs = tmp_path / "sys"
    _block(sysfs, "259:0", "nvme0n1")
    _block(sysfs, "259:3", "nvme0n1p3", partition_of="nvme0n1")
    _block(sysfs, "252:0", "dm-0", slaves=["nvme0n1p3"])
    _block(sysfs, "8:0", "sda")
    return str(sysfs)


def test_io_stat_is_summed_over_unrelated_devices(tmp_path):
    empty = str(tmp_path / "no-sysfs")                 # no relation info at all: every listed device is counted
    assert mp.parse_io_stat("8:0 rbytes=1024 wbytes=2048 rios=1 wios=2\n259:0 rbytes=1 wbytes=2 dbytes=0\n", empty) == {
        "rbytes": 1025, "wbytes": 2050}
    assert mp.parse_io_stat("", empty) == {"rbytes": 0, "wbytes": 0}
    assert mp.parse_io_stat("\n\n", empty) == {"rbytes": 0, "wbytes": 0}


def test_io_stat_counts_a_stacked_pair_once(tmp_path):
    sysfs = _mini_sysfs(tmp_path)
    # the real mini lines: dm-0 on top of the NVMe is one write, not two; the unrelated 8:0 adds its 0
    assert mp.parse_io_stat(MINI_IO_STAT, sysfs) == {"rbytes": 0, "wbytes": 8691597312}
    # only the dm device listed, or only the disk listed: nothing to dedupe, the same single count
    assert mp.parse_io_stat("252:0 rbytes=7 wbytes=9\n", sysfs) == {"rbytes": 7, "wbytes": 9}
    assert mp.parse_io_stat("259:0 rbytes=7 wbytes=9\n", sysfs) == {"rbytes": 7, "wbytes": 9}
    # the lower device's own bytes differ from the top's (it also served other IO): the top is kept, the lower one dropped
    two = "259:0 rbytes=100 wbytes=500\n252:0 rbytes=40 wbytes=300\n"
    assert mp.parse_io_stat(two, sysfs) == {"rbytes": 40, "wbytes": 300}


def test_io_stat_unrelated_third_device_is_still_counted(tmp_path):
    sysfs = _mini_sysfs(tmp_path)
    text = MINI_IO_STAT.replace("8:0 rbytes=0 wbytes=0", "8:0 rbytes=4096 wbytes=1024")
    assert mp.parse_io_stat(text, sysfs) == {"rbytes": 4096, "wbytes": 8691597312 + 1024}


def test_io_stat_two_layer_stack(tmp_path):
    sysfs = tmp_path / "sys2"
    _block(sysfs, "259:0", "nvme0n1")
    _block(sysfs, "252:0", "dm-0", slaves=["nvme0n1"])
    _block(sysfs, "252:1", "dm-1", slaves=["dm-0"])       # LUKS on LVM on the disk
    text = "259:0 rbytes=1 wbytes=1\n252:0 rbytes=1 wbytes=1\n252:1 rbytes=1 wbytes=1\n"
    assert mp.parse_io_stat(text, str(sysfs)) == {"rbytes": 1, "wbytes": 1}


def test_io_stat_without_sysfs_info_counts_every_device(tmp_path):
    # the old behaviour, and the documented fallback: with nothing known about the devices, no bytes are dropped
    assert mp.parse_io_stat(MINI_IO_STAT, str(tmp_path / "missing")) == {"rbytes": 0, "wbytes": 2 * 8691597312}
    partial = tmp_path / "partial"                        # sysfs knows the NVMe only: 252:0 has no entry, so no relation is found
    _block(partial, "259:0", "nvme0n1")
    assert mp.parse_io_stat(MINI_IO_STAT, str(partial)) == {"rbytes": 0, "wbytes": 2 * 8691597312}


def test_io_stat_tolerates_bad_input(tmp_path):
    sysfs = _mini_sysfs(tmp_path)
    assert mp.parse_io_stat(None, sysfs) == {"rbytes": 0, "wbytes": 0}
    assert mp.parse_io_stat("8:0 rbytes=oops wbytes=5\n", sysfs) == {"rbytes": 0, "wbytes": 5}


def test_runner_read_io_stat_uses_the_stacked_rule(tmp_path):
    import runner as RN
    sysfs = _mini_sysfs(tmp_path)
    cg = tmp_path / "cg"
    cg.mkdir()
    assert RN.read_io_stat(str(cg), sysfs) == {}                     # no io.stat: empty, as before
    (cg / "io.stat").write_text(MINI_IO_STAT)
    assert RN.read_io_stat(str(cg), sysfs) == {"rbytes": 0, "wbytes": 8691597312}
    (cg / "io.stat").write_text("")
    assert RN.read_io_stat(str(cg), sysfs) == {"rbytes": 0, "wbytes": 0}


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


def test_export_web_prints_the_per_phase_memory_column():
    pytest.importorskip("numpy")
    import export_web as ew
    cols = ew._metrics_for("l1tpc", {"metrics": [("x_ms", "x ms")]})
    assert cols[-1] == ew.MEM_PHASE_COLUMN
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
