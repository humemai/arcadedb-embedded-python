#!/usr/bin/env python3
"""Where does the delta buffer overtake the graph?

mergeWithDeltaScan() is a LINEAR scan: every query computes a distance for every
buffered vector that the persisted graph does not cover. The rebuild threshold
is max(100, min(0.2 * graph.size(), 50_000)), so past ~250k vectors the cap
binds and the buffer is allowed to reach ~50,000 before a rebuild is considered
-- and per GlobalConfiguration's own text the cap does not bound the buffer at
all, only how often a rebuild drains it.

The RAM side of that is issue #6497, already filed and fixed. The LATENCY side
is unmeasured: nobody has said what a 50,000-entry delta scan costs a query.

METHOD. Build the index, then disable the rebuild entirely
(rebuildGraphRatio=0, mutationsBeforeRebuild enormous) so nothing drains the
buffer, and grow it in steps, timing the same query set at each step. The graph
is identical throughout, so the delta between steps IS the scan cost.

Disabling the rebuild is what makes this an ablation rather than a race: with
the default threshold a rebuild fires mid-sweep and the buffer empties under the
measurement, which is the confound this probe exists to avoid.
"""
import json
import os
import statistics as st
import time

import bench_common

DIM = int(os.environ.get("PROBE_DIM", "64"))
BASE = int(os.environ.get("PROBE_BASE", "200000"))
STEPS = [int(x) for x in os.environ.get(
    "PROBE_DELTA_STEPS", "0,100,1000,5000,10000,25000,50000").split(",")]
QUERIES = int(os.environ.get("PROBE_QUERIES", "200"))
OUT = os.environ.get("PROBE_OUT", "results/probe/delta_scan.jsonl")
DB = os.environ.get("PROBE_DB", "/lcdb/deltaprobe")


def main():
    import arcadedb_embedded as arcadedb
    from arcadedb_embedded import DatabaseFactory  # noqa: F401
    import random

    rng = random.Random(17)
    vec = lambda: [round(rng.gauss(0, 1), 4) for _ in range(DIM)]

    if os.path.isdir(DB):
        import shutil
        shutil.rmtree(DB)

    # Rebuild disabled for the whole run: ratio 0 removes the geometric term and
    # the absolute floor is set past anything this probe will write, so the
    # buffer only ever grows.
    settings = {
        "arcadedb.vectorIndex.rebuildGraphRatio": "0",
        "arcadedb.vectorIndex.mutationsBeforeRebuild": str(10 ** 9),
        "arcadedb.vectorIndex.inactivityRebuildTimeoutMs": str(10 ** 9),
    }
    # -D on the JVM, which is how every other knob in this harness reaches the
    # engine. An env-var convention was a guess and a silently ignored setting
    # here would let a rebuild fire mid-sweep and empty the buffer under the
    # measurement, which is precisely the confound this probe exists to avoid.
    extra = " ".join(f"-D{k}={v}" for k, v in settings.items())
    # ARCADEDB_JVM_ARGS is the name jvm.py:445 actually reads. ARCADEDB_JVM_EXTRA,
    # which this first used, is read by nothing: the settings would have been
    # silently dropped, a rebuild would have fired mid-sweep, and the buffer would
    # have emptied under the measurement.
    os.environ["ARCADEDB_JVM_ARGS"] = (os.environ.get("ARCADEDB_JVM_ARGS", "") + " " + extra).strip()

    db = arcadedb.create_database(DB)
    db.command("sql", "CREATE VERTEX TYPE V")
    db.command("sql", "CREATE PROPERTY V.id INTEGER")
    db.command("sql", "CREATE PROPERTY V.emb ARRAY_OF_FLOATS")
    db.begin()
    for i in range(BASE):
        db.command("sql", f"INSERT INTO V SET id = {i}, emb = {vec()}")
        if i % 20000 == 19999:
            db.commit(); db.begin()
    db.commit()
    db.command("sql", f'CREATE INDEX ON V (emb) LSM_VECTOR METADATA '
                      f'{{ "dimensions": {DIM}, "similarity": "COSINE" }}')

    idx = db.schema.get_index_by_name("V[emb]")
    for _ in range(1200):
        if idx.get_stats().get("graphNodeCount", 0) >= BASE:
            break
        time.sleep(0.1)

    probes = [vec() for _ in range(QUERIES)]

    def timed_pass():
        lat = []
        for p in probes:
            t = time.perf_counter()
            list(db.query("sql", f"SELECT FROM (SELECT expand(vectorNeighbors('V[emb]', {p}, 10)))"))
            lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        return lat

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    stamp = bench_common.run_conditions(lane="delta_scan", backend="arcadedb_embedded",
                                        role="engine", n_rows=BASE, dims=DIM)
    added = 0
    with open(OUT, "w") as f:
        for target in STEPS:
            while added < target:
                db.begin()
                for _ in range(min(1000, target - added)):
                    added += 1
                    db.command("sql", f"INSERT INTO V SET id = {BASE + added}, emb = {vec()}")
                db.commit()
            lat = timed_pass()
            s = idx.get_stats()
            rec = dict(stamp)
            rec.update({
                "delta_target": target,
                "delta_count": s.get("deltaVectorsCount"),
                "graph_nodes": s.get("graphNodeCount"),
                "graph_state": s.get("graphState"),
                "mutations_since_rebuild": s.get("mutationsSinceRebuild"),
                "p50_ms": round(st.median(lat), 3),
                "p95_ms": round(lat[int(0.95 * (len(lat) - 1))], 3),
                "n_queries": len(lat),
            })
            if rec["graph_nodes"] != BASE:
                raise SystemExit(
                    f"graph moved to {rec['graph_nodes']} from {BASE} at delta={target}: a rebuild "
                    f"fired and drained the buffer, so the settings did not reach the engine. "
                    f"Every step from here measures a different graph.")
            if rec["delta_count"] is not None and rec["delta_count"] < target * 0.9:
                raise SystemExit(
                    f"delta buffer holds {rec['delta_count']} against a target of {target}: "
                    f"something drained it, so the scan cost below is not the cost of {target} entries.")
            f.write(json.dumps(rec) + "\n"); f.flush()
            print(f"RESULT delta={target:>6} buffered={rec['delta_count']} "
                  f"graph={rec['graph_nodes']} p50={rec['p50_ms']:.3f} ms "
                  f"p95={rec['p95_ms']:.3f} ms", flush=True)
    db.close()


if __name__ == "__main__":
    main()
