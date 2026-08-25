#!/usr/bin/env python3
"""Shared metrics helpers for the benchmark lanes.

Stdlib-only (so every backend image can import it): latency summary stats,
on-disk size, a raw-latency sidecar dump, and a small timing context manager.
"""
import json
import os
import socket
import statistics as st
import sys
import time


def _host_identity():
    """Which machine this is, read rather than assumed.

    Order matters. BENCH_HOST first, because inside a container the kernel
    hostname is a random ID and only the launcher knows it is mini. Then the
    real hostname. A containerised run with BENCH_HOST unset returns
    "container:<id> (host unknown)" rather than a machine name, so a reader
    can see that the physical host was not recorded instead of reading a
    plausible-looking name that nothing checked.
    """
    explicit = os.environ.get("BENCH_HOST")
    if explicit:
        return explicit
    try:
        name = socket.gethostname()
    except Exception:
        return "unknown"
    containerised = os.path.exists("/.dockerenv")
    if containerised:
        return f"container:{name} (host unknown)"
    return name or "unknown"


def run_conditions(**extra):
    """The conditions this process is actually running under, read not asserted.

    Every overlay feeding T4 and T5 records zero of cpuset/heap/mem_cap, while
    runs.jsonl (produced by runner.py) records all of them. The overlays are
    what the tables print, so the published cells came from artifacts carrying
    less provenance than the campaign they override.

    The cost was concrete: Table IV's 8.84M cell is stuck at N=3 because the
    two missing reps cannot be matched to the first three, nothing having
    recorded what those ran under.

    A driver cannot be trusted to be TOLD its conditions, since that is the
    same self-assertion that let fp32_dev22_driver stamp "26.8.1.dev22" onto a
    dev20 run. So read them from the container itself: cgroup v2 exposes the
    effective cpuset and the memory ceiling, and the heap is whatever we asked
    the JVM for. Anything unreadable comes back None rather than a guess.

    Merge into a result dict before writing it:

        out.update(run_conditions(lane="l3s", scale="medium", rep=rep))

    CLIENT/SERVER CAVEAT. This reads the cgroup of the process it runs in. In
    an embedded cell that is the engine. In a client/server cell it is the
    DRIVER container, and the engine under test is in a different container
    with a different cpuset, heap and memory cap. The #109 server dense run
    stamped cpuset=0-11, heap=None, mem_cap=12g, which describes the client:
    the server had 24g of heap under a 36g cap. Those fields are still worth
    recording, but a server cell must record the SERVER's conditions
    separately (see results/srv109/server_conditions.json) and a reader must
    not take the stamped values as the engine's.

    Pass role= to make which side was measured explicit rather than implied.
    """
    def _read(path):
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return None

    mem = _read("/sys/fs/cgroup/memory.max")
    if mem and mem.isdigit():
        mem = f"{int(mem) // (1 << 30)}g"
    elif mem == "max":
        mem = None

    cpus = (_read("/sys/fs/cgroup/cpuset.cpus.effective")
            or _read("/sys/fs/cgroup/cpuset.cpus"))

    out = {
        "cpuset": cpus,
        "mem_cap": mem,
        "heap": os.environ.get("ARCADEDB_HEAP"),
        # WHICH SCRIPT PRODUCED THIS ROW. FAIRNESS.md's structural finding was
        # that both known protocol violations came from a bespoke driver rather
        # than the lane script, and states the rule "bespoke drivers
        # investigate, lane scripts publish". Nothing enforced it, because a
        # row did not say where it came from, so the rule could only be
        # remembered per row by whoever promoted it to a cell. Recording it
        # makes the rule checkable: a published cell whose producer is not its
        # lane script is detectable instead of being an act of memory.
        "producer": os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else None,
        # "engine" when this process IS the engine, "client" when it drives one
        # over the wire. Without it, a reader cannot tell whether the cgroup
        # fields above describe the thing being measured.
        "role": os.environ.get("BENCH_ROLE",
                               "client" if os.environ.get("BENCH_SERVER_HOST")
                               else "engine"),
        # WHICH MACHINE. This used to be os.environ.get("BENCH_HOST", "mini"),
        # which is the exact self-assertion this function was written to stop:
        # a laptop run with BENCH_HOST unset stamped host="mini" and the
        # artifact then said, in writing, that it came from the controlled
        # bench host. "Every paper number is measured on mini" is a constraint
        # this field is supposed to be the EVIDENCE for, so a default that
        # always satisfies it makes the evidence worthless.
        #
        # Caught by running l4_tsbs.py on the laptop and reading the row back:
        # cpuset 0-15 (the laptop's 16 threads, not mini's 0-11 cpuset) beside
        # host "mini".
        #
        # BENCH_HOST still wins when set, because a container genuinely cannot
        # discover its physical host and the queue scripts are the only thing
        # that knows. But unset now reports what is actually readable, and
        # says so when that is a container ID rather than a machine name.
        "host": _host_identity(),
        # WHICH IMAGE. The last field a published cell was missing.
        #
        # runner.py knows every backend's image and its pinned digest, and
        # stamps them onto lane rows. An overlay driver runs inside a container
        # that is never told what image it is, so it could not record one even
        # in principle -- and the overlays are what T4 and T5 print. The
        # consequence was concrete: T5's Qdrant row is produced by a file whose
        # engine_version reads "unknown (PackageNotFoundError)" and which
        # carries no image at all, while the paper states "served comparators
        # are pinned by image digest". That claim is TRUE -- runner.py pins
        # qdrant/qdrant@sha256:75eab8c4... -- but the artifact cannot show it,
        # so the reproducibility promise rests on a config file the reader
        # never sees rather than on the result they are reading.
        #
        # Same rule as host and producer above: read what is passed, and when
        # nothing is passed say so rather than omitting the key. A missing key
        # looks like an old schema; an explicit None looks like what it is.
        "image": os.environ.get("BENCH_IMAGE"),
        "server_image": os.environ.get("BENCH_SERVER_IMAGE"),
        # WHICH ENGINE COMMIT. Same rule as image above, and the same failure.
        # runner.py stamps this from ARCADEDB_ENGINE_COMMIT (runner.py:730) onto
        # every lane row, so lane rows carry it and bespoke probes do not. On
        # 2026-08-24 sparse_cliff was re-run specifically to unblock figure f3,
        # whose ONLY blocker was "sparse_cliff rows carry engine_commit"; the
        # run finished rc=0 and all 1,000 rows came back with engine_commit
        # None, because the stamping was added to the probe while the VALUE was
        # never passed into its container. Reading it here fixes every bespoke
        # driver at once instead of one at a time.
        #
        # PAGE-SPEC rule 3 is one engine commit per table, so a row that cannot
        # say which commit it came from cannot be published under it, whatever
        # else it measured correctly.
        "engine_commit": os.environ.get("ARCADEDB_ENGINE_COMMIT", "").strip() or None,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }
    try:
        from importlib.metadata import version as _v
        out["engine_version"] = _v("arcadedb-embedded")
    except Exception as e:
        out["engine_version"] = f"unknown ({e.__class__.__name__})"
    out.update(extra)
    return out


def _pct(sorted_a, p):
    """Linear-interpolation percentile (numpy-compatible), pure-python."""
    n = len(sorted_a)
    if n == 1:
        return sorted_a[0]
    rank = (p / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_a[lo] * (1 - frac) + sorted_a[hi] * frac


def latstats(prefix, arr_ms):
    """Full latency summary (ms) for a list of per-op latencies:
    n, mean, std, min, p50, p90, p95, p99, max."""
    if not arr_ms:
        return {}
    a = sorted(float(x) for x in arr_ms)
    n = len(a)
    return {
        f"{prefix}_n": n,
        f"{prefix}_mean_ms": round(st.mean(a), 4),
        f"{prefix}_std_ms": round(st.pstdev(a) if n > 1 else 0.0, 4),
        f"{prefix}_min_ms": round(a[0], 4),
        f"{prefix}_p50_ms": round(_pct(a, 50), 4),
        f"{prefix}_p90_ms": round(_pct(a, 90), 4),
        f"{prefix}_p95_ms": round(_pct(a, 95), 4),
        f"{prefix}_p99_ms": round(_pct(a, 99), 4),
        f"{prefix}_max_ms": round(a[-1], 4),
    }


def dir_size_mb(path):
    """On-disk size of a file or directory tree (MiB)."""
    if not path or not os.path.exists(path):
        return None
    if os.path.isfile(path):
        total = os.path.getsize(path)
    else:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return round(total / 1048576.0, 3)


def dump_latencies(run_label, lat_by_op):
    """Write raw per-op latency arrays to $LAT_DIR/<label>.json (set by run.py).
    No-op if LAT_DIR is unset. Returns the relative sidecar path or None."""
    d = os.environ.get("LAT_DIR")
    if not d or not run_label:
        return None
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{run_label}.json"), "w") as f:
        json.dump({k: [round(float(x), 5) for x in v] for k, v in lat_by_op.items() if v}, f)
    return f"lat/{run_label}.json"


class timed:
    """`with timed() as t: ...` then read t.s (elapsed seconds)."""
    def __enter__(self):
        self._t0 = time.time()
        self.s = 0.0
        return self

    def __exit__(self, *exc):
        self.s = time.time() - self._t0
        return False

class SelfMemorySampler:
    """Peak anonymous working set of the process's OWN cgroup, sampled.

    WHY THIS EXISTS. runner.py samples each container's cgroup from the host,
    which is why every lane row carries peak_anon_mib_sum. The overlay drivers
    are not launched that way: they run inside a container the runner did not
    start, so nothing samples them, and their records carry only mem_cap, the
    ceiling we set. That is why five of the eleven project-page tables have no
    memory column while the underlying question was measured everywhere else.

    A peak cannot be read after the fact. memory.stat's `anon` is an instant,
    and memory.peak (which would be a kernel-maintained maximum) is absent in
    this cgroup layout, so the only way to a peak is to sample. Same loop the
    runner uses, running on the measured side instead of the host side.

    Usage mirrors the runner's:

        s = SelfMemorySampler(); s.start()
        ... build and query ...
        out.update(s.finish())          # peak_anon_mib_sum, end_anon_mib_sum

    The field names deliberately match the lane rows, so a page table or a
    claim can read one field for both sources instead of branching.

    Returns None values rather than zeros when the cgroup files are absent (a
    non-Linux host, or cgroup v1), because a zero here would read as "measured,
    used nothing" and this project has already shipped one green result built
    on a measurement that silently returned nothing.

    SCOPE, and it is not a detail. This reads the CGROUP, not the process. In
    a benchmark container that is the same thing: one cgroup, one engine, and
    the number is the engine's. Run it anywhere else and it reports whatever
    else shares the cgroup. Tested on the laptop it returned 15.8 GiB while
    the process under test had allocated 300 MiB, because the laptop's shell
    session is one cgroup. So: valid inside the bench containers, meaningless
    outside them, and run_conditions()'s `host` field is what tells a reader
    which of the two they are looking at.
    """

    INTERVAL = 0.5

    def __init__(self, interval=None):
        import threading
        self.interval = interval or self.INTERVAL
        self._stop = threading.Event()
        self._thread = None
        self.peak_anon = 0
        self.end_anon = None
        self._read_ok = False

    def _anon(self):
        try:
            with open("/sys/fs/cgroup/memory.stat") as fh:
                for line in fh:
                    if line.startswith("anon "):
                        return int(line.split()[1])
        except (OSError, ValueError):
            return None
        return None

    def _loop(self):
        while not self._stop.is_set():
            v = self._anon()
            if v is not None:
                self._read_ok = True
                self.peak_anon = max(self.peak_anon, v)
                self.end_anon = v
            self._stop.wait(self.interval)

    def start(self):
        import threading
        if self._anon() is None:
            return self          # nothing to sample; finish() reports None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def finish(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2 * self.interval)
        if not self._read_ok:
            return {"peak_anon_mib_sum": None, "end_anon_mib_sum": None}
        return {
            "peak_anon_mib_sum": round(self.peak_anon / (1 << 20), 1),
            "end_anon_mib_sum": round((self.end_anon or 0) / (1 << 20), 1),
        }
