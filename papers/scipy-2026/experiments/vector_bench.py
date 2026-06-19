#!/usr/bin/env python3
"""Vector lane: build an HNSW index, run the ground-truth queries, report recall@k + timings.

One backend per run (selected via --backend), so it runs in that backend's Docker image.
Data = the precomputed Stack Exchange embeddings under <vectors-dir>:
  <name>-all.meta.json / .ids.jsonl / .gt.jsonl / *.shard*.f32   (MiniLM, 384-d, cosine GT)

Recall is computed against the exact cosine GT (gt.jsonl), so different index families are
compared fairly. Prints one machine-readable line:  RESULT {json}

Usage:
  python vector_bench.py --backend arcadedb --vectors-dir /data/stackoverflow-tiny/vectors \
                         --name stackoverflow-tiny [--corpus all] [--ks 1,10,50]
"""
import argparse
import json
import os
import time

import numpy as np

KS_DEFAULT = "1,10,50"


def load_dataset(vectors_dir, name, corpus):
    """Returns (meta, vecs[N,dim], queries). IDs are vector_id = row index (0..N-1).
    gt.jsonl query_id/doc_id are vector_ids (post_id is NOT unique in the 'all' corpus)."""
    base = os.path.join(vectors_dir, f"{name}-{corpus}")
    meta = json.load(open(f"{base}.meta.json"))
    dim, n = meta["dim"], meta["count"]

    vecs = np.empty((n, dim), dtype=np.float32)
    for sh in meta["shards"]:
        path = os.path.join(vectors_dir, os.path.basename(sh["path"]))
        cnt, start = sh["count"], sh["start"]
        vecs[start:start + cnt] = np.fromfile(path, dtype=np.float32,
                                              count=cnt * dim).reshape(cnt, dim)

    queries = []  # (query_vector_id, [gt vector_ids in rank order])
    with open(f"{base}.gt.jsonl") as f:
        for line in f:
            r = json.loads(line)
            queries.append((r["query_id"], [t["doc_id"] for t in r["topk"]]))
    return meta, vecs, queries


def recall_at_ks(retrieved, gt, ks):
    """retrieved/gt are post_id lists in rank order; returns {k: recall}."""
    out = {}
    for k in ks:
        rk, gk = set(retrieved[:k]), set(gt[:k])
        out[k] = (len(rk & gk) / k) if k else 0.0
    return out


# --- backends: each returns (build_time, search_fn, cold_start) -----------------
# Shared HNSW params (matched across ArcadeDB + Chroma for a fair comparison; mirror ex 11/12)
M = 16              # maxConnections / hnsw:M
EF_CONSTRUCTION = 100  # beamWidth / hnsw:construction_ef


def backend_arcadedb(vecs, dim, ef_search):
    import arcadedb_embedded as arcadedb
    import tempfile
    t0 = time.time()
    db_path = tempfile.mkdtemp(prefix="vb_arcadedb_") + "/db"
    ctx = arcadedb.create_database(db_path)
    db = ctx.__enter__()
    cold = time.time() - t0

    db.command("sql", "CREATE VERTEX TYPE Article")  # ex 11 uses a vertex type
    db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")

    t0 = time.time()
    db.begin()
    for vid in range(len(vecs)):
        db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                   {"v": vid, "e": arcadedb.to_java_float_array(vecs[vid])})
        if (vid + 1) % 10000 == 0:
            db.commit()
            db.begin()
    db.commit()
    insert_t = time.time() - t0

    t0 = time.time()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                          METADATA {{ "dimensions": {dim}, "similarity": "COSINE",
                          "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION},
                          "storeVectorsInGraph": false, "addHierarchy": true }}''')
    index_t = time.time() - t0

    def search(qvec, k):
        rows = db.query(
            "sql",
            "SELECT vid, distance FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
            "ORDER BY distance",
            "Article[embedding]", arcadedb.to_java_float_array(qvec), k, ef_search,
        ).to_list()
        return [int(r["vid"]) for r in rows]

    return insert_t, index_t, cold, search, lambda: ctx.__exit__(None, None, None)


def backend_chroma(vecs, dim, ef_search):
    import chromadb
    import tempfile
    path = tempfile.mkdtemp(prefix="vb_chroma_")
    client = chromadb.PersistentClient(path=path)
    # match ArcadeDB's HNSW config (M, ef_construction, ef_search) for fairness
    col = client.create_collection("articles", metadata={
        "hnsw:space": "cosine", "hnsw:M": M,
        "hnsw:construction_ef": EF_CONSTRUCTION, "hnsw:search_ef": ef_search})

    str_ids = [str(i) for i in range(len(vecs))]  # id = vector_id (unique)
    emb = vecs.tolist()
    t0 = time.time()
    B = 5000
    for i in range(0, len(str_ids), B):
        col.add(ids=str_ids[i:i + B], embeddings=emb[i:i + B])
    insert_t = time.time() - t0  # chroma builds HNSW incrementally on add
    index_t = 0.0

    def search(qvec, k):
        res = col.query(query_embeddings=[qvec.tolist()], n_results=k)
        return [int(x) for x in res["ids"][0]]

    return insert_t, index_t, 0.0, search, lambda: None


BACKENDS = {"arcadedb": backend_arcadedb, "chroma": backend_chroma}


def lib_version(backend):
    if backend == "arcadedb":
        import arcadedb_embedded as a
        return getattr(a, "__version__", "?")
    if backend == "chroma":
        import chromadb
        return getattr(chromadb, "__version__", "?")
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--vectors-dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--corpus", default="all")
    ap.add_argument("--ks", default=KS_DEFAULT)
    ap.add_argument("--ef-search", type=int, default=100, help="matched across backends")
    ap.add_argument("--limit", type=int, default=0, help="smoke: cap #vectors (0=all)")
    ap.add_argument("--max-queries", type=int, default=0, help="smoke: cap #queries (0=all)")
    args = ap.parse_args()
    ks = [int(x) for x in args.ks.split(",")]
    kmax = max(ks)

    meta, vecs, queries = load_dataset(args.vectors_dir, args.name, args.corpus)
    if args.limit:
        vecs = vecs[:args.limit]
        meta = {**meta, "count": len(vecs)}
        queries = [(q, gt) for q, gt in queries if q < args.limit]
    if args.max_queries:
        queries = queries[:args.max_queries]
    insert_t, index_t, cold, search, close = BACKENDS[args.backend](vecs, meta["dim"], args.ef_search)

    # warmup (untimed) — avoids penalizing JVM/JIT cold start vs Chroma
    for qvid, _ in queries[:min(50, len(queries))]:
        search(vecs[qvid], kmax)

    lat, recs = [], {k: [] for k in ks}
    for qvid, gt in queries:
        qvec = vecs[qvid]
        t0 = time.time()
        retrieved = search(qvec, kmax)
        lat.append((time.time() - t0) * 1000)
        r = recall_at_ks(retrieved, gt, ks)
        for k in ks:
            recs[k].append(r[k])
    close()

    lat = np.array(lat)
    result = {
        "backend": args.backend, "lib_version": lib_version(args.backend),
        "dataset": args.name, "corpus": args.corpus, "model": meta.get("model", "?"),
        "hnsw_M": M, "hnsw_ef_construction": EF_CONSTRUCTION, "ef_search": args.ef_search,
        "n_vectors": meta["count"], "dim": meta["dim"], "n_queries": len(queries),
        "cold_start_s": round(cold, 3),
        "insert_s": round(insert_t, 3), "index_s": round(index_t, 3),
        "build_s": round(insert_t + index_t, 3),
        "q_mean_ms": round(float(lat.mean()), 3),
        "q_p50_ms": round(float(np.percentile(lat, 50)), 3),
        "q_p95_ms": round(float(np.percentile(lat, 95)), 3),
        **{f"recall@{k}": round(float(np.mean(recs[k])), 4) for k in ks},
    }
    print("RESULT " + json.dumps(result))


if __name__ == "__main__":
    main()
