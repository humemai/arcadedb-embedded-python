#!/usr/bin/env python3
"""How much of the dense lane's p50 is transport rather than search?

l3d_dense's ArcadeDB adapter materializes its k=10 result with .to_list(),
the per-row path, which the transport probe measured at 15x the columnar path
on wide results. The paper reports dense p50 0.723 ms. If a meaningful slice
of that is the binding rather than the engine, the number is harness-limited
and the comparison against Qdrant/Chroma is distorted in OUR favour, which is
the harder direction to audit and so the one worth auditing.

Transport cost depends on ROWS RETURNED (k=10), not on index size, so a small
index gives a number that transfers to DEEP-10M. Same query shape as the lane,
three materializations, plus a floor that drives execution without building
Python objects.
"""
import os, statistics as st, sys, time
import numpy as np

N = int(os.environ.get("PROBE_VECS", "100000"))
DIM, K, EF, M = 96, 10, 100, 32
REPS = int(os.environ.get("REPS", "200"))
WARMUP = 20


def main():
    import arcadedb_embedded as arcadedb
    db = arcadedb.create_database(os.path.expanduser("~/.cache/dense_tp_db"),
                                  jvm_kwargs={"heap_size": "8g", "jvm_args": "-Xms8g"})
    print(f"engine {arcadedb.__version__}  vectors {N:,}x{DIM}  k={K}", flush=True)
    db.command("sql", "CREATE VERTEX TYPE Article")
    db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
    rng = np.random.default_rng(7)
    vecs = rng.random((N, DIM), dtype=np.float32)
    # Same ingest statement the lane uses; insert_many cannot take a numpy
    # row for ARRAY_OF_FLOATS, and using a different ingest here would change
    # what the index is built from.
    db.begin()
    for i in range(N):
        db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                   {"v": i, "e": arcadedb.to_java_float_array(vecs[i])})
        if (i + 1) % 10_000 == 0:
            db.commit(); db.begin()
    db.commit()
    t0 = time.perf_counter()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
               METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
               "maxConnections": {M}, "beamWidth": {EF},
               "storeVectorsInGraph": false, "addHierarchy": true }}''')
    print(f"index built in {time.perf_counter()-t0:.1f}s\n", flush=True)

    SQL = ("SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
           "ORDER BY distance")

    def run(materialize):
        ts = []
        for r in range(REPS):
            q = vecs[r % 1000]
            t = time.perf_counter()
            rs = db.query("sql", SQL, "Article[embedding]",
                          arcadedb.to_java_float_array(q), K, EF)
            materialize(rs)
            dt = (time.perf_counter() - t) * 1000
            if r >= WARMUP:
                ts.append(dt)
        ts.sort()
        return st.median(ts), ts[int(len(ts) * 0.95)]

    arms = [
        ("to_list  (what the lane uses)", lambda rs: [int(r["vid"]) for r in rs.to_list()]),
        ("to_json_list", lambda rs: [int(r["vid"]) for r in rs.to_json_list()]),
        ("to_columns", lambda rs: (lambda c: c["vid"] if c else None)(rs.to_columns())),
        ("count only (execution floor)", lambda rs: sum(1 for _ in rs)),
    ]
    res = {}
    for name, fn in arms:
        try:
            p50, p95 = run(fn)
            res[name] = p50
            print(f"  {name:32} p50={p50:6.3f}ms  p95={p95:6.3f}ms", flush=True)
        except Exception as e:
            print(f"  {name:32} FAILED {type(e).__name__}: {e}", flush=True)

    base = res.get("count only (execution floor)")
    lane = res.get("to_list  (what the lane uses)")
    if base and lane:
        print(f"\n  execution floor        {base:.3f} ms")
        print(f"  lane's path adds       {lane - base:+.3f} ms "
              f"({100*(lane-base)/lane:.0f}% of its own measurement)")
        for n in ("to_json_list", "to_columns"):
            if n in res:
                print(f"  {n:22} adds {res[n]-base:+.3f} ms "
                      f"(would save {lane-res[n]:+.3f} ms vs the lane)")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
