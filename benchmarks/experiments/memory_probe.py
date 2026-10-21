"""Memory at the end of each phase, the same way for every engine (instrument 2026-11, humemai/arcadedb-embedded-python#352).

Nothing here runs unless the runner is measuring instrument 2026-11, so a 2026-10 row is byte-identical to what it was.

THE SHAPE. A cell is a client container (the lane, and the engine when it is embedded) and, for a served engine, a server
container. The runner, on the host, samples each container's cgroup. The lane, inside the client container, prints PHASE
markers. This module joins the two at the markers that end a phase:

  lane side   PhaseLog.mark() calls LaneProbe.on_mark(name). A marker that ends a phase writes one request file into a
              directory the runner mounted into the container and WAITS for the answer. The lane is between two phases
              when it does, so the wait is outside every timed section.
  host side   HostProbe, a thread on the host, polls that directory every 20 ms, and for each request reads the cgroup
              files of the cell, forces a full GC where the engine is a JVM, and writes the answer file.

Reading cgroup files at the boundary replaces a sampler thread: the only thing that runs near a timed section is an
`os.listdir` on the host every 20 ms, on the runner's cores, not the cell's.

THE HEADLINE. `mem_<phase>_owned_mib`: anonymous plus shared memory (cgroup memory.stat `anon` + `shmem`) of every container
of the cell, read at the end of the phase. Every engine has it, in every runtime. See PROTOCOL "Memory per phase".
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time

MIB = 1048576.0
POLL_S = 0.02            # host polling interval for requests
ACK_TIMEOUT_S = 120.0    # a lane waits this long for the host, then stops probing for the rest of the cell
IDLE_S = float(os.environ.get("BENCH_MEMPROBE_IDLE_S", "5"))   # settle window before the "idle" reading
ENV_DIR = "BENCH_MEMPROBE_DIR"

# The phases a row can carry, in cell order. A lane reaches the ones it has: a lane without a separate index wait has no
# index_build reading, and the field is absent, never a copy of load.
PHASES = ("load", "index_build", "warmup", "queries", "idle")


def enabled():
    """True when the instrument being measured is 2026-11 or later."""
    import bench_common
    return bench_common.instrument_at_least("2026-11")


def phases_for_mark(name):
    """The standard phases a lane PHASE marker closes, in order. Empty for every other marker.

    load         the lane's build/ingest phase is done (rows written; an index that the engine maintains during the
                 write is part of it)
    index_build  the lane's post-build phase is done (the wait for the index to be built, flushed or green)
    warmup       an untimed warm-up is done (the last one wins if a lane has several)
    queries      all timed work is done and the lane is about to close; the lane then waits IDLE_S with the engine open
                 and untouched and takes
    idle         the same reading again
    """
    if name in ("build-done", "ingest-done"):
        return ("load",)
    if name == "post-build-done":
        return ("index_build",)
    if name.endswith("warmup-done"):
        return ("warmup",)
    if name == "close-start":
        return ("queries", "idle")
    return ()


# ---------------------------------------------------------------------------
# parsers (pure, tested on synthetic input)

def parse_memory_stat(text):
    """cgroup v2 memory.stat -> {key: bytes}, only the keys the probe uses."""
    keep = {"anon", "file", "shmem", "file_mapped", "kernel", "slab"}
    out = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in keep:
            try:
                out[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return out


def parse_smaps_rollup(text):
    """/proc/<pid>/smaps_rollup -> {"rss": bytes, "anon": bytes}. Rss minus the file-backed pages is `Anonymous` plus
    shared anonymous memory; `Anonymous` is the number reported."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"(Rss|Anonymous):\s+(\d+) kB", line)
        if m:
            out["rss" if m.group(1) == "Rss" else "anon"] = int(m.group(2)) * 1024
    return out


def _kb(n, unit):
    return int(n) * {"K": 1024, "M": 1048576, "G": 1073741824}[unit]


def parse_heap_info(text):
    """jcmd GC.heap_info -> {"used": bytes, "committed": bytes} or {} when no known collector line is found.

    G1 on JDK 17 prints `total 262144K, used 12345K`; on JDK 21 `total reserved 4194304K, committed 262144K, used
    12345K`. Parallel and Serial print one such line per generation, summed here. ZGC prints `used 28M, capacity 64M`.
    Metaspace and class space are not heap and are skipped."""
    used = committed = 0
    found = False
    for line in (text or "").splitlines():
        if "etaspace" in line or "class space" in line:
            continue
        m = re.search(r"total (?:reserved \d+[KMG], committed (\d+)([KMG])|(\d+)([KMG])), used (\d+)([KMG])", line)
        if m:
            c = _kb(m.group(1), m.group(2)) if m.group(1) else _kb(m.group(3), m.group(4))
            committed += c
            used += _kb(m.group(5), m.group(6))
            found = True
            continue
        m = re.search(r"ZHeap\s+used (\d+)([KMG]), capacity (\d+)([KMG])", line)
        if m:
            used += _kb(m.group(1), m.group(2))
            committed += _kb(m.group(3), m.group(4))
            found = True
    return {"used": used, "committed": committed} if found else {}


def parse_io_stat(text):
    """cgroup v2 io.stat -> {"rbytes": n, "wbytes": n}, summed over devices. Cumulative since the cgroup was created."""
    out = {"rbytes": 0, "wbytes": 0}
    for line in (text or "").splitlines():
        for tok in line.split()[1:]:
            k, _, v = tok.partition("=")
            if k in out:
                try:
                    out[k] += int(v)
                except ValueError:
                    pass
    return out


# The write-ahead log or journal an engine keeps apart from its data files, found by name inside the container: ArcadeDB's
# `txlog_*.wal`, PostgreSQL's `pg_wal`, MongoDB's `journal`, Elasticsearch's `translog`, Neo4j's `neostore.transaction.db.*`.
# `/work`, `/data` and `/memprobe` are the repository, the read-only corpus and this probe: not the engine's.
# An engine with another layout reads 0.0, which means "none found", not "none exists"; the disk fields are context.
WAL_SCRIPT = (
    "find / \\( -path /proc -o -path /sys -o -path /dev -o -path /work -o -path /data -o -path /memprobe \\) -prune -o "
    "\\( -name pg_wal -o -name journal -o -name translog \\) -type d -print -prune -o "
    "\\( -name '*.wal' -o -name 'neostore.transaction.db.*' \\) -type f -print 2>/dev/null "
    "| xargs -r du -sk 2>/dev/null | awk '{s+=$1} END{print s+0}'")


def parse_nmt_other(text):
    """jcmd VM.native_memory summary -> committed bytes of the `Other` category (direct ByteBuffers), or None.

    Only present when the JVM runs with -XX:NativeMemoryTracking; otherwise jcmd says so and this returns None."""
    m = re.search(r"-\s+Other \(reserved=\d+KB, committed=(\d+)KB\)", text or "")
    return int(m.group(1)) * 1024 if m else None


# ---------------------------------------------------------------------------
# lane side

class LaneProbe:
    """Inside the client container: at a phase-ending marker, collect what only the process can see (its own JVM when
    the engine is embedded, its own smaps), write a request, wait for the host's answer."""

    def __init__(self, directory):
        self.dir = directory
        self.seq = 0
        self.dead = False
        self.idle_s = IDLE_S

    def _jvm(self):
        """In-process JVM, when the engine is embedded and a JVM was started: full GC, then used/committed heap and the
        direct buffer pool. {} when there is no JVM."""
        try:
            import jpype
        except ImportError:
            return {}
        try:
            if not jpype.isJVMStarted():
                return {}
            t0 = time.perf_counter()
            system = jpype.JClass("java.lang.System")
            rt = jpype.JClass("java.lang.Runtime").getRuntime()
            system.gc()
            total, free = int(rt.totalMemory()), int(rt.freeMemory())
            out = {"used": total - free, "committed": total,
                   "gc_ms": round((time.perf_counter() - t0) * 1000, 1), "source": "jpype"}
            try:
                mx = jpype.JClass("java.lang.management.ManagementFactory")
                pools = mx.getPlatformMXBeans(jpype.JClass("java.lang.management.BufferPoolMXBean"))
                for p in pools:
                    if str(p.getName()) == "direct":
                        out["direct"] = int(p.getMemoryUsed())
            except Exception:  # noqa: BLE001
                pass
            return out
        except Exception as e:  # noqa: BLE001
            return {"error": f"jpype: {type(e).__name__}: {e}"[:200]}

    def _proc(self):
        try:
            with open("/proc/self/smaps_rollup") as fh:
                return parse_smaps_rollup(fh.read())
        except OSError:
            return {}

    def _request(self, phase):
        self.seq += 1
        body = {"seq": self.seq, "phase": phase, "t": time.time(), "jvm": self._jvm(), "proc": self._proc()}
        tmp = os.path.join(self.dir, f".req.{self.seq:03d}.tmp")
        with open(tmp, "w") as fh:
            json.dump(body, fh)
        os.rename(tmp, os.path.join(self.dir, f"req.{self.seq:03d}.json"))
        ack = os.path.join(self.dir, f"ack.{self.seq:03d}.json")
        deadline = time.time() + ACK_TIMEOUT_S
        while not os.path.exists(ack):
            if time.time() > deadline:
                self.dead = True      # the host is gone; stop asking, the cell goes on
                return
            time.sleep(0.005)

    def on_mark(self, name):
        if self.dead:
            return
        for ph in phases_for_mark(name):
            if ph == "idle":
                time.sleep(self.idle_s)
            self._request(ph)
            if self.dead:
                return


_LANE = None


def lane_on_mark(name):
    """Called by PhaseLog.mark. A no-op unless the runner mounted a probe directory for this cell."""
    global _LANE
    d = os.environ.get(ENV_DIR)
    if not d:
        return
    if _LANE is None:
        _LANE = LaneProbe(d)
    _LANE.on_mark(name)


# ---------------------------------------------------------------------------
# host side

def _mib(b):
    return None if b is None else round(b / MIB, 1)


def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


class PeakFile:
    """memory.peak of one cgroup, held open. Since Linux 6.12 a write to the file resets the watermark for READS THROUGH
    THE SAME FILE DESCRIPTOR, which is why the descriptor is kept; the runner's sampler reads the file by name and sees
    the whole-cell peak unchanged. Opening for write needs the right to write the cgroup file (root, or a delegated
    cgroup); without it `can_reset` is False and the reading is the cell's peak so far."""

    def __init__(self, cg):
        self.path = os.path.join(cg, "memory.peak")
        self.fd = None
        self.can_reset = False
        try:
            self.fd = os.open(self.path, os.O_RDWR)
            self.can_reset = True
        except OSError:
            try:
                self.fd = os.open(self.path, os.O_RDONLY)
            except OSError:
                self.fd = None

    def read(self):
        if self.fd is None:
            return None
        try:
            return int(os.pread(self.fd, 64, 0).decode().strip())
        except (OSError, ValueError):
            return None

    def reset(self):
        if self.fd is None or not self.can_reset:
            return False
        try:
            os.write(self.fd, b"reset")
            return True
        except OSError:
            self.can_reset = False
            return False

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class HostProbe:
    def __init__(self, run_id, parent_dir, sampler_pairs=None, cgroup_dir=None, exec_fn=None):
        self.run_id = run_id
        self.parent = parent_dir
        self.dir = None
        self.pairs = sampler_pairs or []        # [("client", CgroupSampler), ("server", CgroupSampler)]
        self.cgroup_dir = cgroup_dir
        self.exec = exec_fn or self._docker_exec
        self.stop_evt = threading.Event()
        self.thread = None
        self.cgs = {}                           # name -> (cg dir, PeakFile)
        self.series_mark = {}                   # name -> index into sampler.series at the previous boundary
        self.records = {}                       # phase -> dict
        self.errors = []
        self.spent_s = 0.0
        self.jvm = None                         # server JVM: None = not looked yet, False = none, else (pid, bin)
        self.served = False
        self.handled = set()
        self.io_last = {}
        self.disk_fn = None
        self.engine_side = "client"

    @classmethod
    def maybe(cls, run_id, parent_dir):
        """None unless the instrument is 2026-11: the runner then has nothing to do."""
        return cls(run_id, parent_dir) if enabled() else None

    def docker_args(self):
        os.makedirs(self.parent, exist_ok=True)
        self.dir = tempfile.mkdtemp(prefix=f"{self.run_id}.memprobe.", dir=self.parent)
        os.chmod(self.dir, 0o777)
        return ["-e", f"{ENV_DIR}=/memprobe", "-v", f"{self.dir}:/memprobe"]

    def start(self, sampler_pairs, cgroup_dir, disk_fn=None):
        """disk_fn(cid) -> {"disk_mb": float|None, ...}: the runner's container_disk with one sample."""
        self.pairs, self.cgroup_dir, self.disk_fn = sampler_pairs, cgroup_dir, disk_fn
        self.served = any(n == "server" for n, _ in sampler_pairs)
        self.engine_side = "server" if self.served else "client"
        for name, smp in sampler_pairs:          # the io counters start here, so a phase's io is a difference
            c = self._cg(name, smp)
            if c is not None:
                self.io_last[name] = parse_io_stat(_read(os.path.join(c[0], "io.stat")))
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    # -- docker -----------------------------------------------------------
    @staticmethod
    def _docker_exec(cid, argv, timeout=60):
        r = subprocess.run(["docker", "exec", cid] + argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def _find_jvm(self, cid):
        rc, out = self.exec(cid, ["sh", "-c",
                                  'for p in /proc/[0-9]*; do e=$(readlink "$p/exe" 2>/dev/null); '
                                  'case "$e" in */java) echo "${p#/proc/} ${e%/java}"; break;; esac; done'])
        parts = out.split()
        return (parts[0], parts[1]) if rc == 0 and len(parts) == 2 else False

    def _server_jvm(self, cid):
        """Force a full GC in the server container's JVM and read the heap after it. {} when the engine is not a JVM."""
        if self.jvm is None:
            self.jvm = self._find_jvm(cid)
        if not self.jvm:
            return {}
        pid, home = self.jvm
        jcmd = f"{home}/jcmd"
        t0 = time.perf_counter()
        rc, out = self.exec(cid, [jcmd, pid, "GC.run"])
        if rc != 0:
            return {"error": f"jcmd GC.run rc={rc}: {out.strip()[:120]}"}
        gc_ms = round((time.perf_counter() - t0) * 1000, 1)
        rc, out = self.exec(cid, [jcmd, pid, "GC.heap_info"])
        h = parse_heap_info(out) if rc == 0 else {}
        if not h:
            return {"error": f"jcmd GC.heap_info rc={rc}: {out.strip()[:120]}"}
        res = {"used": h["used"], "committed": h["committed"], "gc_ms": gc_ms, "source": "jcmd"}
        rc, out = self.exec(cid, [jcmd, pid, "VM.native_memory", "summary"])
        d = parse_nmt_other(out) if rc == 0 else None
        if d is not None:
            res["direct"] = d
        return res

    # -- cgroups ----------------------------------------------------------
    def _cg(self, name, sampler):
        if name not in self.cgs:
            cg = self.cgroup_dir(sampler.cid) if self.cgroup_dir else None
            if not cg:
                return None
            self.cgs[name] = (cg, PeakFile(cg))
        return self.cgs[name]

    def _sampled_peak(self, name, sampler):
        """The best a cell can say when memory.peak cannot be reset: the largest memory.current the 0.25 s sampler saw
        since the previous boundary."""
        i = self.series_mark.get(name, 0)
        window = [v for _t, v in sampler.series[i:]]
        self.series_mark[name] = len(sampler.series)
        return max(window) if window else None

    def _disk(self, phase):
        """{"mib": writable layer + volumes of the engine's container, "wal": its WAL/journal} or {}; one sample per phase."""
        pair = next(((n, smp) for n, smp in self.pairs if n == self.engine_side), None)
        if pair is None or self.disk_fn is None:
            return {}
        out = {}
        try:
            d = self.disk_fn(pair[1].cid)
            if d.get("disk_mb") is not None:
                out["mib"] = d["disk_mb"]
            else:
                self.errors.append(f"disk {phase}: {d.get('disk_note')}")
            rc, txt = self.exec(pair[1].cid, ["sh", "-c", WAL_SCRIPT])
            if rc == 0 and txt.strip().isdigit():
                out["wal"] = int(txt.strip()) / 1024.0
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"disk {phase}: {type(e).__name__}: {e}"[:120])
        return out

    def handle(self, req):
        t0 = time.perf_counter()
        rec = {"gc_ms": 0.0}
        sides, peaks = {}, {}
        # 1. the phase's peak, before any GC of ours can touch it
        for name, s in self.pairs:
            c = self._cg(name, s)
            if c is None:
                self.errors.append(f"{name}: no cgroup")
                continue
            cg, pf = c
            pk = pf.read() if pf.can_reset else None
            peaks[name] = pk if pk is not None else self._sampled_peak(name, s)
            if pk is not None:
                rec["peak_kind"] = "kernel-reset"
            else:
                rec.setdefault("peak_kind", "sampled-0.25s")
        # 2. a full GC where the engine is a JVM
        jvm = dict(req.get("jvm") or {})
        server = next(((n, s) for n, s in self.pairs if n == "server"), None)
        if server is not None:
            jvm = self._server_jvm(server[1].cid)       # the engine is the server; the lane's JVM (none) is not it
        if jvm.get("error"):
            self.errors.append(jvm["error"])
        # 3. what each cgroup holds now, then 4. restart its peak
        for name, s in self.pairs:
            c = self.cgs.get(name)
            if c is None:
                continue
            cg, pf = c
            sides[name] = parse_memory_stat(_read(os.path.join(cg, "memory.stat")))
        # io since the previous boundary, read before our own disk work below
        io = {}
        for name, _s in self.pairs:
            c = self.cgs.get(name)
            if c is None:
                continue
            now = parse_io_stat(_read(os.path.join(c[0], "io.stat")))
            last = self.io_last.get(name, {"rbytes": 0, "wbytes": 0})
            io[name] = {k: max(0, now[k] - last[k]) for k in now}
            self.io_last[name] = now
        # disk of the engine's side, and its write-ahead log. Done before the peak restarts: the helper processes run inside the
        # container and their memory must not land in the next phase's peak.
        disk = self._disk(req["phase"])
        for name, _s in self.pairs:
            c = self.cgs.get(name)
            if c is not None:
                c[1].reset()
        rec["io"], rec["disk"] = io, disk
        anon = sum(st.get("anon", 0) for st in sides.values())
        shmem = sum(st.get("shmem", 0) for st in sides.values())
        rec.update(anon=anon, shmem=shmem, owned=anon + shmem,
                   file=sum(st.get("file", 0) for st in sides.values()),
                   by_side={n: st.get("anon", 0) + st.get("shmem", 0) for n, st in sides.items()},
                   peak=(sum(v for v in peaks.values() if v is not None) if any(v is not None for v in peaks.values())
                         else None),
                   jvm={k: v for k, v in jvm.items() if k != "error"})
        if not self.served:
            rec["proc"] = req.get("proc") or {}
        rec["gc_ms"] = (jvm.get("gc_ms") or 0.0)
        self.records[req["phase"]] = rec
        self.spent_s += time.perf_counter() - t0

    def _run(self):
        while not self.stop_evt.is_set():
            self.poll_once()
            time.sleep(POLL_S)
        self.poll_once()

    def poll_once(self):
        try:
            names = sorted(n for n in os.listdir(self.dir) if n.startswith("req.") and n.endswith(".json"))
        except OSError:
            return
        for n in names:
            if n in self.handled:
                continue
            self.handled.add(n)
            try:
                with open(os.path.join(self.dir, n)) as fh:
                    req = json.load(fh)
                self.handle(req)
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"{n}: {type(e).__name__}: {e}"[:160])
            ack = os.path.join(self.dir, "ack." + n[len("req."):])
            with open(ack + ".tmp", "w") as fh:
                fh.write("{}")
            os.rename(ack + ".tmp", ack)

    # -- the row ----------------------------------------------------------
    def finish(self, row=None):
        """Stop the thread, return the row fields, remove the directory. `row` is the cell's row, read for the disk
        baselines and the after-close disk reading the runner took."""
        self.stop_evt.set()
        if self.thread:
            self.thread.join(timeout=5)
        out = fields_from(self.records, self.errors, self.spent_s,
                          any(pf.can_reset for _c, pf in self.cgs.values()), row, self.engine_side)
        for _c, pf in self.cgs.values():
            pf.close()
        if self.dir:
            import shutil
            shutil.rmtree(self.dir, ignore_errors=True)
        return out


def fields_from(records, errors, spent_s, peak_reset, row=None, engine_side="client"):
    """The row fields of one cell. Units are in the name; a reading the cell did not take is absent."""
    out = {}
    for ph in PHASES:
        r = records.get(ph)
        if not r:
            continue
        p = f"mem_{ph}_"
        out[p + "owned_mib"] = _mib(r["owned"])
        out[p + "anon_mib"] = _mib(r["anon"])
        out[p + "shmem_mib"] = _mib(r["shmem"])
        out[p + "file_mib"] = _mib(r["file"])
        if r.get("peak") is not None:
            out[p + "peak_mib"] = _mib(r["peak"])
        for side, v in (r.get("by_side") or {}).items():
            out[f"{p}{side}_owned_mib"] = _mib(v)
        base = (row or {}).get(f"{engine_side}_disk_baseline_mb")
        dk = r.get("disk") or {}
        if dk.get("mib") is not None:
            out[f"disk_{ph}_mib"] = round(dk["mib"], 1)
            if base is not None:
                out[f"disk_{ph}_data_mib"] = round(dk["mib"] - base, 1)
        if dk.get("wal") is not None:
            out[f"disk_{ph}_wal_mib"] = round(dk["wal"], 1)
        io = r.get("io") or {}
        if io:
            out[f"io_{ph}_read_mib"] = _mib(sum(v["rbytes"] for v in io.values()))
            out[f"io_{ph}_write_mib"] = _mib(sum(v["wbytes"] for v in io.values()))
        j = r.get("jvm") or {}
        if j.get("used") is not None:
            out[f"jvm_{ph}_used_after_gc_mib"] = _mib(j["used"])
            out[f"jvm_{ph}_committed_mib"] = _mib(j["committed"])
        if j.get("direct") is not None:
            out[f"jvm_{ph}_direct_mib"] = _mib(j["direct"])
        pr = r.get("proc") or {}
        if pr.get("anon") is not None:
            out[f"proc_{ph}_anon_mib"] = _mib(pr["anon"])
            out[f"proc_{ph}_rss_mib"] = _mib(pr["rss"])
    if records:
        out["mem_probe_phases"] = ",".join(p for p in PHASES if p in records)
        kinds = {r.get("peak_kind") for r in records.values() if r.get("peak_kind")}
        out["mem_probe_peak_kind"] = "kernel-reset" if kinds == {"kernel-reset"} else "sampled-0.25s"
        out["mem_probe_gc_s"] = round(sum((r.get("gc_ms") or 0.0) for r in records.values()) / 1000, 3)
        srcs = {(r.get("jvm") or {}).get("source") for r in records.values()} - {None}
        if srcs:
            out["jvm_probe_source"] = ",".join(sorted(srcs))
    # after close: the runner's own reading, taken once the lane has exited and the database is closed
    end = (row or {}).get(f"{engine_side}_disk_mb")
    if records and end is not None:
        out["disk_close_mib"] = end
        base = (row or {}).get(f"{engine_side}_disk_baseline_mb")
        if base is not None:
            out["disk_close_data_mib"] = round(end - base, 1)
    out["phase_probe_s"] = round(spent_s, 3)
    out["mem_probe_peak_reset"] = bool(peak_reset)
    if errors:
        out["phase_probe_error"] = "; ".join(dict.fromkeys(errors))[:300]
    return out
