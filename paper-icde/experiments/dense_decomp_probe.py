#!/usr/bin/env python3
"""Decompose embedded dense-search latency (SIFT1M, same params as the
campaign small tier): where do the milliseconds go between the Python caller
and JVector?

Per query (same 1000 SIFT queries for every variant):
  t_conv   numpy -> Java float[] conversion alone (JPype boundary floor)
  t_direct index.findNeighborsFromVector(...) via the Java API (engine core
           + boundary, no SQL executor)
  t_exec   db.query(...) call returning a lazy result set (adds SQL layer)
  t_total  adapter path: query + to_list materialization (what the paper
           tables measure)

Decomposition: SQL layer ~= t_exec - t_direct; materialization ~= t_total -
t_exec; engine core ~= t_direct - t_conv.
"""
import json
import os
import statistics as st
import time

import numpy as np

DATA = os.environ.get("BENCH_DENSE_DATA", "/data/dense")
K = 10
M = int(os.environ.get("BENCH_DENSE_M", "16"))
EF_CONSTRUCTION = 100
EF_SEARCH = 100
BATCH = 5000
N_QUERIES = 1000


def main():
    import arcadedb_embedded as arcadedb
    train = np.load(os.path.join(DATA, "sift_train.npy"), mmap_mode="r")
    test = np.load(os.path.join(DATA, "sift_test.npy"))[:N_QUERIES]
    dim = train.shape[1]
    heap = os.environ.get("ARCADEDB_HEAP", "8g")
    db = arcadedb.create_database("/tmp/decomp_arcade",
                                  jvm_kwargs={"heap_size": heap,
                                              "jvm_args": f"-Xms{heap}"})
    db.command("sql", "CREATE VERTEX TYPE Article")
    db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
    t0 = time.perf_counter()
    db.begin()
    for vid in range(len(train)):
        db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                   {"v": vid, "e": arcadedb.to_java_float_array(train[vid])})
        if (vid + 1) % BATCH == 0:
            db.commit()
            db.begin()
    db.commit()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
               METADATA {{ "dimensions": {dim}, "similarity": "EUCLIDEAN",
               "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION},
               "storeVectorsInGraph": false, "addHierarchy": true }}''')
    print(f"build_s={time.perf_counter()-t0:.1f}", flush=True)

    jdb = db.get_java_database()
    idx = jdb.getSchema().getIndexByName("Article[embedding]")
    # unwrap TypeIndex -> LSMVectorIndex if needed
    if not hasattr(idx, "findNeighborsFromVector"):
        idx = idx.getIndexesOnBuckets()[0]

    sql = ("SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
           "ORDER BY distance")

    for q in test[:20]:  # warmup all paths
        ja = arcadedb.to_java_float_array(q)
        idx.findNeighborsFromVector(ja, K, EF_SEARCH)
        db.query("sql", sql, "Article[embedding]", ja, K, EF_SEARCH).to_list()

    t_conv, t_direct, t_exec, t_total = [], [], [], []
    for qi in range(N_QUERIES):
        q = test[qi]
        t = time.perf_counter()
        ja = arcadedb.to_java_float_array(q)
        t_conv.append(time.perf_counter() - t)

        t = time.perf_counter()
        idx.findNeighborsFromVector(ja, K, EF_SEARCH)
        t_direct.append(time.perf_counter() - t)

        t = time.perf_counter()
        rs = db.query("sql", sql, "Article[embedding]", ja, K, EF_SEARCH)
        t_exec.append(time.perf_counter() - t)

        t = time.perf_counter()
        rs2 = db.query("sql", sql, "Article[embedding]", ja, K, EF_SEARCH)
        rows = rs2.to_list()
        t_total.append(time.perf_counter() - t)
        if (qi + 1) % 200 == 0:
            print(f"query {qi+1}/{N_QUERIES}", flush=True)

    def p(v):
        v = sorted(x * 1e3 for x in v)
        return {"p50": round(v[len(v) // 2], 3),
                "p99": round(v[int(0.99 * len(v))], 3),
                "mean": round(st.mean(v), 3)}

    out = {"n_docs": int(train.shape[0]), "m": M, "ef_search": EF_SEARCH,
           "conv_ms": p(t_conv), "direct_ms": p(t_direct),
           "sql_exec_ms": p(t_exec), "sql_total_ms": p(t_total)}
    print("RESULT " + json.dumps(out), flush=True)
    with open(os.environ.get("PROBE_OUT", "/pout/dense_decomp.json"), "w") as f:
        json.dump(out, f)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
