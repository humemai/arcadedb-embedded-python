#!/usr/bin/env python3
"""Shared metrics helpers for the benchmark lanes.

Stdlib-only (so every backend image can import it): latency summary stats,
on-disk size, a raw-latency sidecar dump, and a small timing context manager.
"""
import json
import os
import statistics as st
import time


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
