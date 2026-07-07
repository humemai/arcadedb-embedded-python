#!/usr/bin/env python3
"""L3 sparse-vector lane: build + top-K search + recall@10 vs exact GT.

Backends: arcadedb_embedded / arcadedb_server (LSM_SPARSE_VECTOR, dot-product
BlockMax-WAND), qdrant_sparse, milvus_sparse, elasticsearch_sparse. Same seeded
SPLADE-shaped corpus (sparse_common.py); ground truth from gen_sparse_gt.py
must exist at /data/sparse/<scale>/gt.npy (mounted read-only by the runner).

Timing: build (ingest incl. transactional index maintenance) and warm query
latency (warmups discarded). Recall resolution (id lookup) happens OUTSIDE the
timed section. Emits one JSON metric block.
"""
import argparse
import json
import os
import statistics
import time

from sparse_common import (DIMENSIONS, K, SCALE_DOCS, SCALE_QUERIES,
                           gen_docs, gen_queries)

WARMUP = 5
INGEST_BATCH = 500


def pct(vals):
    v = sorted(vals)
    g = lambda q: v[min(len(v) - 1, int(q * len(v)))]
    return {"mean_ms": round(statistics.mean(v) * 1e3, 3),
            "p50_ms": round(g(0.50) * 1e3, 3), "p95_ms": round(g(0.95) * 1e3, 3),
            "p99_ms": round(g(0.99) * 1e3, 3), "n": len(v)}


def recall_at_k(result_ids, gt_row):
    truth = set(int(x) for x in gt_row)
    return len(truth.intersection(int(x) for x in result_ids)) / len(truth)


class Base:
    name = "base"

    def connect(self):
        raise NotImplementedError

    def build(self, n_docs):
        """Ingest corpus (index maintained per backend's idiomatic path)."""
        raise NotImplementedError

    def search(self, idx, vals, k):
        """Return list of doc ordinals, best first. Must be warm-callable."""
        raise NotImplementedError

    def post_build(self):
        """Optional: wait for index readiness (counts as build time)."""

    def disk_mb(self):
        return None


class ArcadeEmbedded(Base):
    name = "arcadedb_sparse_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database("/tmp/l3_arcade",
                                           jvm_kwargs={"heap_size": heap})
        self.version = arcadedb.__version__
        self.db.command("sql", "CREATE DOCUMENT TYPE Doc")
        self.db.command("sql", "CREATE PROPERTY Doc.id LONG")
        self.db.command("sql", "CREATE PROPERTY Doc.tokens ARRAY_OF_INTEGERS")
        self.db.command("sql", "CREATE PROPERTY Doc.weights ARRAY_OF_FLOATS")
        self.db.command("sql", 'CREATE INDEX ON Doc (tokens, weights) '
                               'LSM_SPARSE_VECTOR METADATA {"dimensions": %d}'
                               % DIMENSIONS)
        self.idx_name = "Doc[tokens,weights]"

    def build(self, n_docs):
        buf = []
        for i, idx, vals in gen_docs(n_docs):
            t = ",".join(map(str, idx))
            # 9 decimals: exact float32 round-trip, keeps ingest == GT weights
            w = ",".join(f"{v:.9f}" for v in vals)
            buf.append(f"INSERT INTO Doc SET id = {i}, tokens = [{t}], "
                       f"weights = [{w}]")
            if len(buf) >= INGEST_BATCH:
                with self.db.transaction():
                    self.db.command("sqlscript", ";".join(buf))
                buf = []
        if buf:
            with self.db.transaction():
                self.db.command("sqlscript", ";".join(buf))

    def post_build(self):
        # ArcadeDB's settle step (fairness parity with ES forcemerge / Milvus
        # flush+load / Qdrant green-wait): blocking LSM segment compaction via
        # the Java API — embedded-only, no SQL/HTTP trigger exists. Measured at
        # 1M docs: ~2s, query p50 9.5ms -> 7.0ms (control run: no change).
        jdb = self.db.get_java_database()
        for idx in jdb.getSchema().getIndexes():
            if "SparseVector" in str(idx.getClass().getSimpleName()):
                idx.compact()

    def search(self, idx, vals, k):
        import jpype
        ji = jpype.JArray(jpype.JInt)(idx)
        jv = jpype.JArray(jpype.JFloat)(vals)
        rows = self.db.query(
            "sql", "SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?))",
            self.idx_name, ji, jv, k).to_json_list()
        self._last_rids = [r["@rid"] for r in rows]
        return self._last_rids  # RIDs; resolved to ordinals untimed

    def resolve(self, rids):
        if not rids:
            return []
        in_list = ",".join(rids)
        rows = self.db.query(
            "sql", f"SELECT id, @rid AS r FROM Doc WHERE @rid IN [{in_list}]"
        ).to_json_list()
        by_rid = {r["r"]: r["id"] for r in rows}
        return [by_rid.get(x, -1) for x in rids]


class ArcadeServer(ArcadeEmbedded):
    name = "arcadedb_sparse_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "icdebench")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        self.version = "server:latest"
        for ddl in ["CREATE DOCUMENT TYPE Doc",
                    "CREATE PROPERTY Doc.id LONG",
                    "CREATE PROPERTY Doc.tokens ARRAY_OF_INTEGERS",
                    "CREATE PROPERTY Doc.weights ARRAY_OF_FLOATS",
                    'CREATE INDEX ON Doc (tokens, weights) LSM_SPARSE_VECTOR '
                    'METADATA {"dimensions": %d}' % DIMENSIONS]:
            self._cmd("sql", ddl)
        self.idx_name = "Doc[tokens,weights]"

    def post_build(self):
        # No compaction trigger is reachable over HTTP/SQL — the server runs
        # query-after-ingest as-shipped. Documented asymmetry vs embedded
        # (paper: operational gap worth a sentence).
        pass

    def _cmd(self, language, command, params=None):
        payload = {"language": language, "command": command}
        if params:
            payload["params"] = params
        r = self.rq.post(f"{self.base}/command/bench", json=payload, timeout=600)
        r.raise_for_status()
        return r.json().get("result", [])

    def _query(self, command, params=None):
        payload = {"language": "sql", "command": command}
        if params:
            payload["params"] = params
        r = self.rq.post(f"{self.base}/query/bench", json=payload, timeout=600)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, n_docs):
        buf = []
        for i, idx, vals in gen_docs(n_docs):
            t = ",".join(map(str, idx))
            # 9 decimals: exact float32 round-trip, keeps ingest == GT weights
            w = ",".join(f"{v:.9f}" for v in vals)
            buf.append(f"INSERT INTO Doc SET id = {i}, tokens = [{t}], "
                       f"weights = [{w}]")
            if len(buf) >= INGEST_BATCH:
                self._cmd("sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._cmd("sqlscript", ";".join(buf))

    def search(self, idx, vals, k):
        rows = self._query(
            "SELECT expand(`vector.sparseNeighbors`(:i, :t, :w, :k))",
            {"i": self.idx_name, "t": idx, "w": vals, "k": k})
        self._last_rids = [r["@rid"] for r in rows]
        return self._last_rids

    def resolve(self, rids):
        if not rids:
            return []
        in_list = ",".join(rids)
        rows = self._query(
            f"SELECT id, @rid AS r FROM Doc WHERE @rid IN [{in_list}]")
        by_rid = {r["r"]: r["id"] for r in rows}
        return [by_rid.get(x, -1) for x in rids]


class Qdrant(Base):
    name = "qdrant_sparse"
    COLL = "docs"

    def connect(self):
        from qdrant_client import QdrantClient, models
        self.models = models
        host = os.environ["BENCH_SERVER_HOST"]
        self.cl = QdrantClient(url=f"http://{host}:6333", timeout=600)
        self.version = "qdrant"
        self.cl.create_collection(
            collection_name=self.COLL,
            vectors_config={},
            sparse_vectors_config={
                "text": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False))})

    def build(self, n_docs):
        m, batch = self.models, []
        for i, idx, vals in gen_docs(n_docs):
            batch.append(m.PointStruct(
                id=i, vector={"text": m.SparseVector(indices=idx, values=vals)}))
            if len(batch) >= INGEST_BATCH:
                self.cl.upsert(self.COLL, batch, wait=False)
                batch = []
        if batch:
            self.cl.upsert(self.COLL, batch, wait=True)

    def post_build(self):
        # wait for indexing/optimizer to settle
        while True:
            info = self.cl.get_collection(self.COLL)
            if str(info.status).lower().endswith("green"):
                return
            time.sleep(0.5)

    def search(self, idx, vals, k):
        m = self.models
        hits = self.cl.query_points(
            self.COLL,
            query=m.SparseVector(indices=idx, values=vals),
            using="text", limit=k, with_payload=False).points
        return [h.id for h in hits]

    def resolve(self, ids):
        return ids


class Milvus(Base):
    name = "milvus_sparse"
    COLL = "docs"

    def connect(self):
        from pymilvus import DataType, MilvusClient
        host = os.environ["BENCH_SERVER_HOST"]
        self.cl = MilvusClient(uri=f"http://{host}:19530")
        self.version = "milvus"
        schema = self.cl.create_schema(auto_id=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("emb", DataType.SPARSE_FLOAT_VECTOR)
        index_params = self.cl.prepare_index_params()
        index_params.add_index(field_name="emb",
                               index_type="SPARSE_INVERTED_INDEX",
                               metric_type="IP")
        self.cl.create_collection(self.COLL, schema=schema,
                                  index_params=index_params)

    def build(self, n_docs):
        batch = []
        for i, idx, vals in gen_docs(n_docs):
            batch.append({"id": i, "emb": dict(zip(idx, vals))})
            if len(batch) >= INGEST_BATCH:
                self.cl.insert(self.COLL, batch)
                batch = []
        if batch:
            self.cl.insert(self.COLL, batch)

    def post_build(self):
        self.cl.flush(self.COLL)
        self.cl.load_collection(self.COLL)

    def search(self, idx, vals, k):
        res = self.cl.search(self.COLL, data=[dict(zip(idx, vals))],
                             anns_field="emb", limit=k,
                             search_params={"metric_type": "IP"})
        return [hit["id"] for hit in res[0]]

    def resolve(self, ids):
        return ids


class Elastic(Base):
    name = "elasticsearch_sparse"
    IDX = "docs"

    def connect(self):
        from elasticsearch import Elasticsearch, helpers
        self.helpers = helpers
        host = os.environ["BENCH_SERVER_HOST"]
        self.es = Elasticsearch(f"http://{host}:9200", request_timeout=600)
        self.version = self.es.info()["version"]["number"]
        self.es.indices.create(index=self.IDX, mappings={
            "properties": {"emb": {"type": "sparse_vector"}}},
            settings={"number_of_shards": 1, "number_of_replicas": 0})

    @staticmethod
    def _tok(idx, vals):
        return {f"t{d}": float(v) for d, v in zip(idx, vals)}

    def build(self, n_docs):
        def actions():
            for i, idx, vals in gen_docs(n_docs):
                yield {"_index": self.IDX, "_id": i,
                       "_source": {"emb": self._tok(idx, vals)}}
        self.helpers.bulk(self.es, actions(), chunk_size=INGEST_BATCH,
                          request_timeout=600)

    def post_build(self):
        self.es.indices.refresh(index=self.IDX)
        self.es.indices.forcemerge(index=self.IDX, max_num_segments=1,
                                   request_timeout=1200)

    def search(self, idx, vals, k):
        res = self.es.search(index=self.IDX, size=k, _source=False, query={
            "sparse_vector": {"field": "emb",
                              "query_vector": self._tok(idx, vals)}})
        return [int(h["_id"]) for h in res["hits"]["hits"]]

    def resolve(self, ids):
        return ids


BACKENDS = {c.name: c for c in
            [ArcadeEmbedded, ArcadeServer, Qdrant, Milvus, Elastic]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", default="search")  # single suite for l3s
    ap.add_argument("--scale", default="micro", choices=list(SCALE_DOCS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    n_docs = SCALE_DOCS[args.scale]
    queries = gen_queries(SCALE_QUERIES[args.scale])
    gt_path = f"/data/sparse/{args.scale}/gt.npy"
    gt = None
    if os.path.exists(gt_path):
        import numpy as np
        gt = np.load(gt_path)

    b = BACKENDS[args.backend]()
    out = {"lane": "l3s", "n_docs": n_docs, "dims": DIMENSIONS, "k": K,
           "n_queries": len(queries)}

    t0 = time.perf_counter()
    b.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = getattr(b, "version", "?")

    t0 = time.perf_counter()
    b.build(n_docs)
    b.post_build()
    build = time.perf_counter() - t0
    out["build_s"] = round(build, 2)
    out["build_docs_per_s"] = round(n_docs / build, 1)

    # timed warm search
    lats, raw_results = [], []
    for qi, (idx, vals) in enumerate(queries):
        t0 = time.perf_counter()
        ids = b.search(idx, vals, K)
        dt = time.perf_counter() - t0
        if qi >= WARMUP:
            lats.append(dt)
        raw_results.append(ids)
    out.update({f"query_{k2}": v for k2, v in pct(lats).items()})
    out["qps"] = round(len(lats) / sum(lats), 1)

    # recall (untimed; resolve backend-native hits to doc ordinals)
    if gt is not None:
        recalls = []
        for qi, ids in enumerate(raw_results):
            ordinals = b.resolve(ids)
            recalls.append(recall_at_k(ordinals, gt[qi]))
        out["recall_at_10"] = round(statistics.mean(recalls), 4)
    else:
        out["recall_at_10"] = None
        out["gt_missing"] = True

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    main()
