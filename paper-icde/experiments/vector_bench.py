#!/usr/bin/env python3
"""Vector lane: build an HNSW index, run the ground-truth queries, report recall@k + rich timings.

One backend per run (selected via --backend), so it runs in that backend's Docker image.
Data = the precomputed Stack Exchange embeddings under <vectors-dir>:
  <name>-all.meta.json / .ids.jsonl / .gt.jsonl / *.shard*.f32   (MiniLM, 384-d, cosine GT)

Recall is computed against the exact cosine GT (gt.jsonl). Records lifecycle phase timings
(import / jvm_init / open / schema / ingest / index_build / close), on-disk size, and full
query-latency stats (mean/std/p50/p90/p95/p99). Prints one line:  RESULT {json}
"""
import argparse
import json
import os
import time

import numpy as np

import bench_common as bc

KS_DEFAULT = "1,10,50"


def load_dataset(vectors_dir, name, corpus):
    """Returns (meta, vecs[N,dim], queries). IDs are vector_id = row index (0..N-1)."""
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
    out = {}
    for k in ks:
        rk, gk = set(retrieved[:k]), set(gt[:k])
        out[k] = (len(rk & gk) / k) if k else 0.0
    return out


# Shared HNSW params (matched across ArcadeDB + Chroma; mirror ex 11/12)
M = 16              # maxConnections / hnsw:M
EF_CONSTRUCTION = 100  # beamWidth / hnsw:construction_ef


def backend_arcadedb(vecs, dim, ef_search):
    import tempfile
    with bc.timed() as t_imp:
        import arcadedb_embedded as arcadedb
        from arcadedb_embedded import jvm
    db_path = tempfile.mkdtemp(prefix="vb_arcadedb_") + "/db"
    heap = os.environ.get("ARCADEDB_HEAP", "4g")
    with bc.timed() as t_jvm:
        jvm.start_jvm(heap_size=heap)  # isolate JVM init; heap must match (else medium OOMs)
    with bc.timed() as t_open:
        ctx = arcadedb.create_database(db_path, jvm_kwargs={"heap_size": heap})
        db = ctx.__enter__()
    with bc.timed() as t_schema:
        db.command("sql", "CREATE VERTEX TYPE Article")  # ex 11 uses a vertex type
        db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
        db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
    with bc.timed() as t_ins:
        db.begin()
        for vid in range(len(vecs)):
            db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                       {"v": vid, "e": arcadedb.to_java_float_array(vecs[vid])})
            if (vid + 1) % 10000 == 0:
                db.commit(); db.begin()
        db.commit()
    with bc.timed() as t_idx:
        db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                              METADATA {{ "dimensions": {dim}, "similarity": "COSINE",
                              "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION},
                              "storeVectorsInGraph": false, "addHierarchy": true }}''')

    def search(qvec, k):
        rows = db.query(
            "sql",
            "SELECT vid, distance FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
            "ORDER BY distance",
            "Article[embedding]", arcadedb.to_java_float_array(qvec), k, ef_search,
        ).to_list()
        return [int(r["vid"]) for r in rows]

    return dict(import_s=t_imp.s, jvm_init_s=t_jvm.s, open_s=t_open.s, schema_s=t_schema.s,
                ingest_s=t_ins.s, index_build_s=t_idx.s, db_path=db_path, search=search,
                close=lambda: ctx.__exit__(None, None, None),
                version=getattr(arcadedb, "__version__", "?"))


def backend_chroma(vecs, dim, ef_search):
    import tempfile
    with bc.timed() as t_imp:
        import chromadb
    path = tempfile.mkdtemp(prefix="vb_chroma_")
    with bc.timed() as t_open:
        client = chromadb.PersistentClient(path=path)
        col = client.create_collection("articles", metadata={
            "hnsw:space": "cosine", "hnsw:M": M,
            "hnsw:construction_ef": EF_CONSTRUCTION, "hnsw:search_ef": ef_search})

    str_ids = [str(i) for i in range(len(vecs))]
    emb = vecs.tolist()
    with bc.timed() as t_ins:  # Chroma builds HNSW incrementally during add()
        B = 5000
        for i in range(0, len(str_ids), B):
            col.add(ids=str_ids[i:i + B], embeddings=emb[i:i + B])

    def search(qvec, k):
        res = col.query(query_embeddings=[qvec.tolist()], n_results=k)
        return [int(x) for x in res["ids"][0]]

    return dict(import_s=t_imp.s, jvm_init_s=0.0, open_s=t_open.s, schema_s=0.0,
                ingest_s=t_ins.s, index_build_s=0.0, db_path=path, search=search,
                close=lambda: None, version=getattr(chromadb, "__version__", "?"))


BACKENDS = {"arcadedb": backend_arcadedb, "chroma": backend_chroma}


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

    be = BACKENDS[args.backend](vecs, meta["dim"], args.ef_search)

    # warmup (untimed); record the first (cold) query separately
    cold_q_ms = None
    for i, (qvid, _) in enumerate(queries[:min(50, len(queries))]):
        t0 = time.time()
        be["search"](vecs[qvid], kmax)
        if i == 0:
            cold_q_ms = (time.time() - t0) * 1000

    lat, recs = [], {k: [] for k in ks}
    for qvid, gt in queries:
        t0 = time.time()
        retrieved = be["search"](vecs[qvid], kmax)
        lat.append((time.time() - t0) * 1000)
        r = recall_at_ks(retrieved, gt, ks)
        for k in ks:
            recs[k].append(r[k])

    with bc.timed() as t_close:
        be["close"]()
    db_size_mb = bc.dir_size_mb(be["db_path"])

    ingest_s, index_s = be["ingest_s"], be["index_build_s"]
    build_s = ingest_s + index_s
    n = meta["count"]
    result = {
        "backend": args.backend, "lib_version": be["version"], "lane": "vector",
        "dataset": args.name, "corpus": args.corpus, "model": meta.get("model", "?"),
        "hnsw_M": M, "hnsw_ef_construction": EF_CONSTRUCTION, "ef_search": args.ef_search,
        "n_vectors": n, "dim": meta["dim"], "n_queries": len(queries),
        # lifecycle phases (s)
        "import_s": round(be["import_s"], 4), "jvm_init_s": round(be["jvm_init_s"], 4),
        "open_s": round(be["open_s"], 4), "schema_s": round(be["schema_s"], 4),
        "ingest_s": round(ingest_s, 3), "index_build_s": round(index_s, 3),
        "close_s": round(t_close.s, 4),
        "cold_start_s": round(be["jvm_init_s"] + be["open_s"], 3),  # continuity
        "insert_s": round(ingest_s, 3), "index_s": round(index_s, 3),  # continuity
        "build_s": round(build_s, 3),
        # storage + throughput
        "db_size_mb": db_size_mb,
        "ingest_vectors_per_s": round(n / ingest_s, 1) if ingest_s else None,
        "cold_query_ms": round(cold_q_ms, 4) if cold_q_ms is not None else None,
        # latency distribution
        **bc.latstats("q", lat),
        **{f"recall@{k}": round(float(np.mean(recs[k])), 4) for k in ks},
    }
    bc.dump_latencies(os.environ.get("RUN_LABEL"), {"q": lat})
    print("RESULT " + json.dumps(result))


if __name__ == "__main__":
    main()
