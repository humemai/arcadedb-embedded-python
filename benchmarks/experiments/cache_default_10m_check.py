#!/usr/bin/env python3
"""#7146 / #7147 verification at the page's scale, embedded only.

Builds the DEEP-10M index once per precision with NO cache settings and records
what the engine's own log line says it chose:

    Building graph with N vectors ... (cache enabled: size=M of N)

On 8d6af9475 the served arm chose 3,674,697 of 9,990,000 at the default and the
INT8 arm never read the percent (100,000). After #7147 both should read
9,990,000 of 9,990,000 with a 24 GB heap. The served side needs a server image
from the same commit and is the re-pin's job; this checks the embedded engine
on the wheel built from that commit.

Host-side, like delta_scan_probe.py: the vectors come from BENCH_DENSE_DATA's
sibling deep10m directory, the JVM heap from ARCADEDB_HEAP. Not a page row.
Timings are printed but this is a mechanism check, not a measurement.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from l3d_dense import BACKENDS, load_dataset  # noqa: E402

OUT = os.environ.get("PROBE_OUT", "results/verify/cache_default_10m.jsonl")
ARMS = os.environ.get("CHECK_ARMS", "arcadedb_dense_embedded,arcadedb_dense_embedded_int8").split(",")
LOG = os.environ.get("CHECK_LOG", "")   # the engine's stderr, captured by the caller


def main():
    for k in ("BENCH_DENSE_BUILD_CACHE", "BENCH_DENSE_BUILD_CACHE_PCT"):
        if os.environ.get(k):
            raise SystemExit(f"{k} is set; this check is about the DEFAULT, unset it")
    train, _test, _gt = load_dataset("deep10m")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for arm in ARMS:
        b = BACKENDS[arm]()
        b.connect()
        t0 = time.perf_counter()
        b.build(train)
        b.post_build()
        build_s = round(time.perf_counter() - t0, 1)
        chosen = total = None
        if LOG and os.path.exists(LOG):
            for m in re.finditer(r"cache enabled: size=(\d+)(?: of (\d+))?", open(LOG, errors="replace").read()):
                chosen, total = int(m.group(1)), (int(m.group(2)) if m.group(2) else None)
        rec = {"arm": arm, "quantization": getattr(b, "quantization", None), "build_s": build_s,
               "heap": os.environ.get("ARCADEDB_HEAP"), "cache_chosen": chosen, "cache_total": total,
               "engine": os.environ.get("VERIFY_ENGINE_COMMIT")}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print("CACHECHECK " + json.dumps(rec), flush=True)
        try:
            b.close()
        except Exception:  # noqa: BLE001
            pass
    os._exit(0)


if __name__ == "__main__":
    main()
