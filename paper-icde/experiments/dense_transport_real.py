#!/usr/bin/env python3
"""Definitive: how much of the dense lane's latency is transport, on REAL data.

The uniform-random version of this measured the transport delta at +0.497 ms
for k=10 but had an execution floor of 0.631 ms, which is not credible for a
tuned HNSW: uniform vectors are pathological for graph ANN because there is no
cluster structure to exploit, so the search explores far more of the graph than
it does on real descriptors.

Transport cost is data-independent (10 rows x 1 column of JNI crossings), but
the FLOOR is not, and the share of the paper's 0.723 ms depends on the floor.
So: real DEEP descriptors, the lane's exact schema, index settings and query,
four materialisations.

1M rather than 10M on purpose. What real data buys here is structure, not
scale, and structure arrives at 1M; a 10M build costs 45 minutes to move the
floor by a graph level. If the split is close, 10M settles it afterwards.
"""
import os, statistics as st, sys, time
import numpy as np

N = int(os.environ.get("PROBE_VECS", "1000000"))
DIM, K, EF, M = 96, 10, 100, 32
REPS = int(os.environ.get("REPS", "300"))
WARMUP = 30
DATA = os.environ.get("DEEP_DIR", "/data/deep10m")


def main():
    import arcadedb_embedded as arcadedb
    base = np.load(os.path.join(DATA, "deep_base.npy"), mmap_mode="r")
    query = np.load(os.path.join(DATA, "deep_query.npy"))
    vecs = np.ascontiguousarray(base[:N], dtype=np.float32)
    qs = np.ascontiguousarray(query[:1000], dtype=np.float32)
    print(f"real DEEP descriptors: {vecs.shape}, queries {qs.shape}", flush=True)

    db = arcadedb.create_database(os.path.expanduser("~/.cache/dense_real_db"),
                                  jvm_kwargs={"heap_size": "16g", "jvm_args": "-Xms16g"})
    print(f"engine {arcadedb.__version__}  k={K} ef={EF} M={M}", flush=True)
    db.command("sql", "CREATE VERTEX TYPE Article")
    db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
    t0 = time.perf_counter()
    db.begin()
    for i in range(N):
        db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                   {"v": i, "e": arcadedb.to_java_float_array(vecs[i])})
        if (i + 1) % 10_000 == 0:
            db.commit(); db.begin()
    db.commit()
    print(f"ingest {time.perf_counter()-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
               METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
               "maxConnections": {M}, "beamWidth": {EF},
               "storeVectorsInGraph": false, "addHierarchy": true }}''')
    print(f"index {time.perf_counter()-t0:.1f}s\n", flush=True)

    SQL = ("SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
           "ORDER BY distance")

    arms = [
        ("to_list  (LANE USES THIS)", lambda rs: [int(r["vid"]) for r in rs.to_list()]),
        ("to_json_list", lambda rs: [int(r["vid"]) for r in rs.to_json_list()]),
        ("to_columns", lambda rs: (lambda c: c["vid"] if c else None)(rs.to_columns())),
    ]

    # INTERLEAVED, and rotated per rep. Running each arm to completion makes the
    # first arm pay the page and JIT warming for every arm after it: the earlier
    # version of this probe reported a NEGATIVE transport cost purely because the
    # arm order changed between runs. Rotating the order per rep also cancels any
    # residual first-in-rep advantage.
    #
    # No "execution floor" arm: there is no way to drive a lazy ResultSet without
    # materialising it, and `sum(1 for _ in rs)` is itself the per-row path, so it
    # measured MORE than to_list and looked like negative transport. The
    # actionable quantity is the DIFFERENCE between real paths, which needs no floor.
    lat = {name: [] for name, _ in arms}
    for r in range(REPS):
        q = qs[r % len(qs)]
        order = arms[r % len(arms):] + arms[:r % len(arms)]
        for name, fn in order:
            t = time.perf_counter()
            rs = db.query("sql", SQL, "Article[embedding]",
                          arcadedb.to_java_float_array(q), K, EF)
            fn(rs)
            dt = (time.perf_counter() - t) * 1000
            if r >= WARMUP:
                lat[name].append(dt)
    res = {}
    for name, _ in arms:
        v = sorted(lat[name])
        res[name] = st.median(v)
        print(f"  {name:30} p50={st.median(v):6.3f}ms  "
              f"p95={v[int(len(v)*0.95)]:6.3f}ms  n={len(v)}", flush=True)

    lane = res["to_list  (LANE USES THIS)"]
    col = res["to_columns"]
    js = res["to_json_list"]
    print(f"\n  switching the lane to to_columns saves {lane-col:+.3f} ms/query "
          f"({lane/col:.2f}x on total query time)")
    print(f"  switching to to_json_list saves        {lane-js:+.3f} ms/query "
          f"({lane/js:.2f}x)")
    print(f"\n  The paper reports DEEP-10M dense p50 = 0.723 ms on this same")
    print(f"  query and materialisation. A {lane-col:.3f} ms saving there would")
    print(f"  put it near {max(0.723-(lane-col), 0):.3f} ms, but that is an")
    print(f"  EXTRAPOLATION across index size and needs its own run to claim.")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
