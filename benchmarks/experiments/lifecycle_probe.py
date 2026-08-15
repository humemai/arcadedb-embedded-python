#!/usr/bin/env python3
"""Smoke probe: is a build/query phase split physically possible, and does it
measure the same thing?

WHY THIS RUNS BEFORE ANY SCHEDULER IS WRITTEN. The proposed redesign builds
indexes in parallel, stops each engine, then restarts it for an exclusive
timed query pass. Three unknowns decide whether that is viable, and all three
are cheap to measure and expensive to guess:

  close_s     What does a clean shutdown cost? l1_tabular and l3_sparse never
              call close() at all and hard-exit via os._exit(), so deferred
              shutdown work is currently never paid by anyone in those lanes,
              and the disk figure they report is a crash state (#155).

  reopen_s    What does opening an ALREADY-BUILT database cost? connect_s
              today times opening an EMPTY one, so this number does not exist
              anywhere in the project (#154).

  cold drift  Does the first query after a reopen measure the same thing as
              the first query after a build? It cannot, and the size of the
              gap is the point. An engine that loads eagerly pays in reopen;
              one that loads lazily pays in the first query. ArcadeDB is
              lazy, which is why it gains 9.4x on a warm pass while
              LadybugDB, resident from load, gains 1.00x. A split that timed
              only the query would penalise the lazy engine and hand the
              eager one a free pass, measuring a different quantity per
              engine under one protocol name.

WHAT IT DOES NOT DO. It closes and reopens IN PROCESS. It does not restart the
container, so the host page cache stays warm and "cold after reopen" here is
an engine-level cold, not an OS-level one. That is deliberate: measure the
phenomenon before engineering the infrastructure. If reopen_s and the cold
drift turn out small, the split is viable and the container work is worth
doing. If they are large or wildly uneven across engines, the split needs the
cold pass redefined rather than relocated, and no scheduler would have fixed
that.

Usage, inside a bench container, one backend per invocation:

    python lifecycle_probe.py --lane l2 --backend ladybug_graph --scale sf1
"""
import argparse
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_common import run_conditions  # noqa: E402

LANES = {
    "l2": ("l2_graph", "ADAPTERS"),
    "l3s": ("l3_sparse", "BACKENDS"),
    "l1": ("l1_tabular", "BACKENDS"),
}


def _dir_bytes(path):
    """Bytes under a path, or None. Used to see what a clean close settles."""
    if not path or not os.path.exists(path):
        return None
    if os.path.isfile(path):
        return os.path.getsize(path)
    n = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True, choices=sorted(LANES))
    ap.add_argument("--backend", required=True)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-path", default="",
                    help="engine data directory, for the on-disk delta")
    args = ap.parse_args()

    mod_name, table = LANES[args.lane]
    mod = importlib.import_module(mod_name)
    adapters = getattr(mod, table)
    if args.backend not in adapters:
        sys.exit(f"{args.backend} not in {mod_name}.{table}: {sorted(adapters)}")

    out = {"probe": "lifecycle", "lane": args.lane, "backend": args.backend,
           "scale": args.scale}

    # ---- build, using the lane's own adapter so this is the real path ------
    b = adapters[args.backend]()
    t = time.perf_counter()
    b.connect()
    out["connect_empty_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    if args.lane == "l3s":
        b.build(mod.SCALE_DOCS[args.scale])
    elif args.lane == "l2":
        b.build(mod.SCALE_PERSONS[args.scale])
    else:
        b.build(mod.SCALE_ROWS[args.scale])
    if hasattr(b, "post_build"):
        b.post_build()
    out["build_s"] = round(time.perf_counter() - t, 2)

    # ---- FIRST cold pass: the protocol we use today -----------------------
    out["cold_after_build_ms"] = _one_pass(mod, b, args)
    out["warm_after_build_ms"] = _one_pass(mod, b, args)

    out["disk_before_close_mb"] = _mb(_dir_bytes(args.data_path))

    # ---- the measurement that does not exist anywhere today ---------------
    if not hasattr(b, "close"):
        out["close_s"] = None
        out["close_note"] = ("adapter has no close(); this lane hard-exits, so "
                             "deferred shutdown work is never paid")
    else:
        t = time.perf_counter()
        b.close()
        out["close_s"] = round(time.perf_counter() - t, 3)

    # A clean close is when compaction, writeback and WAL truncation actually
    # happen. The delta against the pre-close reading IS the deferred work,
    # per engine, and it is why the disk instrument needed a settle loop.
    out["disk_after_close_mb"] = _mb(_dir_bytes(args.data_path))
    if out["disk_before_close_mb"] and out["disk_after_close_mb"]:
        out["disk_close_delta_mb"] = round(
            out["disk_after_close_mb"] - out["disk_before_close_mb"], 1)

    # ---- reopen an ALREADY-BUILT database ---------------------------------
    try:
        b2 = adapters[args.backend]()
        t = time.perf_counter()
        b2.connect()
        out["reopen_s"] = round(time.perf_counter() - t, 3)
        # THE DECIDING NUMBER. Compare against cold_after_build: if they
        # differ a lot, the split changes what "cold" means, and by how much
        # per engine decides whether it can be relocated or must be redefined.
        out["cold_after_reopen_ms"] = _one_pass(mod, b2, args)
        out["warm_after_reopen_ms"] = _one_pass(mod, b2, args)
        if hasattr(b2, "close"):
            b2.close()
    except Exception as e:
        out["reopen_error"] = f"{e.__class__.__name__}: {e}"

    out.update(run_conditions(lane=f"{args.lane}_lifecycle", scale=args.scale))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print("RESULT " + json.dumps(out))
    # Same reason every lane does this: JPype keeps non-daemon JVM threads
    # alive and the cell would otherwise hang until the watchdog.
    os._exit(0)


def _mb(n):
    return None if n is None else round(n / 1048576.0, 1)


def _one_pass(mod, b, args):
    """One timed pass over a small fixed query set, median ms.

    Deliberately small: this probe is about lifecycle costs, not about
    reproducing a lane's latency number, and a published latency must come
    from the lane script rather than from a bespoke driver.
    """
    import statistics as st
    lat = []
    if args.lane == "l3s":
        qs = mod.gen_queries(min(50, mod.SCALE_QUERIES[args.scale]))
        for idx, vals in qs:
            t = time.perf_counter()
            b.search(idx, vals, mod.K)
            lat.append((time.perf_counter() - t) * 1000)
    elif args.lane == "l2":
        ids = mod.pick_query_ids(mod.SCALE_PERSONS[args.scale], 50)
        tmpl = list(mod.OLTP_READS.values())[0]
        for pid in ids:
            t = time.perf_counter()
            b.run_cypher(tmpl.format(id=pid))
            lat.append((time.perf_counter() - t) * 1000)
    else:
        for i in range(50):
            t = time.perf_counter()
            b.query_all(f"SELECT * FROM orders WHERE id = {i}")
            lat.append((time.perf_counter() - t) * 1000)
    return round(st.median(lat), 3) if lat else None


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
