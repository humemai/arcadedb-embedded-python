#!/usr/bin/env python3
"""Shared metrics helpers for the benchmark lanes.

Stdlib-only (so every backend image can import it): latency summary stats,
on-disk size, a raw-latency sidecar dump, and a small timing context manager.
"""
import json
import os
import statistics as st
import time


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
        # "engine" when this process IS the engine, "client" when it drives one
        # over the wire. Without it, a reader cannot tell whether the cgroup
        # fields above describe the thing being measured.
        "role": os.environ.get("BENCH_ROLE",
                               "client" if os.environ.get("BENCH_SERVER_HOST")
                               else "engine"),
        "host": os.environ.get("BENCH_HOST", "mini"),
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
