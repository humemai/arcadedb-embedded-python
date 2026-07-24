#!/usr/bin/env python3
"""L3d dense-vector lane: SIFT1M (ann-benchmarks, exact L2 ground truth).

Data: /data/dense/sift_{train,test,neighbors}.npy (host-prepped by
gen_dense_npy.py; containers need only numpy).

Fairness: matched HNSW operating point M=16, ef_construction=100, ef_search=100,
L2 metric, FP32 vectors everywhere. Disclosed deviations: LanceDB's HNSW variant
is IVF_HNSW_SQ (int8 scalar-quantized, its only HNSW offering; nprobes=20
default); sqlite-vec is an exact scan (no ANN index exists), so it is the
recall=1.0 embedded baseline. Recall@10 is reported next to latency so every
precision/algorithm difference is visible.

Scales: small = full 1M (the canonical unit). Smaller scales cap the corpus and
keep only queries whose true top-k lies inside the cap (subset-exact recall).
"""
import argparse
import json
import os
import statistics
import sys
import time
import traceback

import numpy as np

DATA = os.environ.get("BENCH_DENSE_DATA", "/data/dense")
DIM = 128
K = 10
M = int(os.environ.get("BENCH_DENSE_M", "16"))  # degree-matched ablation: 32 = hnswlib-M16 equivalent (see #5352)
EF_CONSTRUCTION = 100
EF_SEARCH = 100
SCALE_DOCS = {"micro": 5_000, "tiny": 100_000, "small": 1_000_000,
              "deep10m": 9_990_000}
N_QUERIES = 1_000
BATCH = 10_000


def load_dataset(scale):
    global DIM
    if scale == "deep10m":
        # ann-benchmarks deep-image-96-angular: cosine GT. Rows are normalized
        # to unit length so L2 ranking == cosine ranking and every adapter's
        # L2 configuration (and the shipped GT) stays valid unchanged.
        DIM = 96
        mm = np.load(os.path.join(DATA, "..", "deep10m", "deep_base.npy"),
                     mmap_mode="r")
        # chunked copy+normalize: a single np.array(memmap) holds the 3.8GB
        # anon copy WHILE the read fills 3.8GB of page cache — transiently
        # ~7.6GB, which OOM-killed the 7GB client share of server-topology
        # cells. Chunking keeps cache pages clean/reclaimable (peak ~4.2GB).
        base = np.empty(mm.shape, dtype=np.float32)
        CH = 500_000
        for s in range(0, mm.shape[0], CH):
            c = np.array(mm[s:s + CH], dtype=np.float32)  # copy: asarray on a float32 memmap returns a read-only view
            c /= np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-12)
            base[s:s + CH] = c
        test = np.load(os.path.join(DATA, "..", "deep10m",
                                    "deep_query.npy"))[:N_QUERIES]
        test = test / np.maximum(
            np.linalg.norm(test, axis=1, keepdims=True), 1e-12)
        gt = np.load(os.path.join(DATA, "..", "deep10m",
                                  "deep_gt.npy"))[:N_QUERIES, :K]
        return base, test.astype(np.float32), gt
    train = np.load(os.path.join(DATA, "sift_train.npy"), mmap_mode="r")
    test = np.load(os.path.join(DATA, "sift_test.npy"))[:N_QUERIES]
    n = SCALE_DOCS[scale]
    full = np.load(os.path.join(DATA, "sift_train.npy"), mmap_mode="r").shape[0]
    train = np.asarray(train[:n], dtype=np.float32)
    if n == full:  # full corpus: use the shipped exact GT
        gt = np.load(os.path.join(DATA, "sift_neighbors.npy"))[:N_QUERIES, :K]
    else:  # subset scale: exact GT by chunked brute force (L2)
        qn = (test ** 2).sum(1)
        best_d = np.full((len(test), K), np.inf, dtype=np.float64)
        best_i = np.full((len(test), K), -1, dtype=np.int64)
        CH = 100_000
        for s in range(0, n, CH):
            c = train[s:s + CH]
            d = qn[:, None] - 2.0 * test @ c.T + (c ** 2).sum(1)[None, :]
            md = np.concatenate([best_d, d], axis=1)
            mi = np.concatenate(
                [best_i, np.broadcast_to(np.arange(s, s + len(c)),
                                         (len(test), len(c)))], axis=1)
            top = np.argpartition(md, K - 1, axis=1)[:, :K]
            rows = np.arange(len(test))[:, None]
            order = np.argsort(md[rows, top], axis=1)
            best_d = md[rows, top][rows, order]
            best_i = mi[rows, top][rows, order]
        gt = best_i
    return train, test, gt


class Base:
    name = "?"
    version = "?"

    def connect(self):
        pass

    def build(self, vecs):
        raise NotImplementedError

    def post_build(self):
        pass

    def search(self, qvec, k):
        raise NotImplementedError

    def close(self):
        pass


class ArcadeEmbedded(Base):
    name = "arcadedb_dense_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        self._a = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # ARCADEDB_EXTRA_JVM_ARGS: space-separated extras (e.g. an
        # -agentpath:...  profiler agent for the #3144 heap investigation)
        extra = os.environ.get("ARCADEDB_EXTRA_JVM_ARGS", "")
        self.db = arcadedb.create_database(
            "/tmp/l3d_arcade",
            jvm_kwargs={"heap_size": heap,
                        "jvm_args": f"-Xms{heap} {extra}".strip()})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")

    def build(self, vecs):
        db = self.db
        db.command("sql", "CREATE VERTEX TYPE Article")
        db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
        db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
        db.begin()
        for vid in range(len(vecs)):
            db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                       {"v": vid, "e": self._a.to_java_float_array(vecs[vid])})
            if (vid + 1) % BATCH == 0:
                db.commit()
                db.begin()
        db.commit()
        quant = os.environ.get("BENCH_DENSE_QUANT", "")  # e.g. INT8 (#3144)
        qline = f'"quantization": "{quant}", ' if quant else ""
        db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                   METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                   "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION}, {qline}
                   "storeVectorsInGraph": false, "addHierarchy": true }}''')

    def search(self, qvec, k):
        rows = self.db.query(
            "sql",
            "SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
            "ORDER BY distance",
            "Article[embedding]", self._a.to_java_float_array(qvec), k, EF_SEARCH,
        ).to_list()
        return [int(r["vid"]) for r in rows]

    def close(self):
        self.db.close()


class ArcadeServer(Base):
    """ArcadeDB over HTTP (client-server), same index/params as embedded."""
    name = "arcadedb_dense_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "icdebench")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        try:
            r = self.rq.get(f"{self.base}/server", timeout=30).json()
            self.version = "server:" + str(r.get("version", "?"))
        except Exception:
            self.version = "server:?"

    def _cmd(self, language, command, timeout=1800):
        r = self.rq.post(f"{self.base}/command/bench",
                         json={"language": language, "command": command},
                         timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, vecs):
        self._cmd("sql", "CREATE VERTEX TYPE Article")
        self._cmd("sql", "CREATE PROPERTY Article.vid INTEGER")
        self._cmd("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
        buf = []
        for vid in range(len(vecs)):
            w = ", ".join("%.6f" % x for x in vecs[vid])
            buf.append(f"INSERT INTO Article SET vid = {vid}, embedding = [{w}]")
            if len(buf) >= 500:
                self._cmd("sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._cmd("sqlscript", ";".join(buf))
        self._cmd("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
                  METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                  "maxConnections": {M}, "beamWidth": {EF_CONSTRUCTION},
                  "storeVectorsInGraph": false, "addHierarchy": true }}''',
                  timeout=6 * 3600)  # synchronous 10M HNSW build exceeds 30min

    def search(self, qvec, k):
        w = ", ".join("%.6f" % x for x in qvec)
        r = self.rq.post(f"{self.base}/query/bench", json={
            "language": "sql",
            "command": f"SELECT vid FROM (SELECT expand(vectorNeighbors("
                       f"'Article[embedding]', [{w}], {k}, {EF_SEARCH}))) "
                       f"ORDER BY distance"}, timeout=600)
        r.raise_for_status()
        return [int(x["vid"]) for x in r.json().get("result", [])]


class Chroma(Base):
    name = "chroma_dense"

    def connect(self):
        import chromadb
        self.version = chromadb.__version__
        client = chromadb.PersistentClient(path="/tmp/l3d_chroma")
        self.col = client.create_collection("articles", metadata={
            "hnsw:space": "l2", "hnsw:M": M,
            "hnsw:construction_ef": EF_CONSTRUCTION, "hnsw:search_ef": EF_SEARCH})

    def build(self, vecs):
        ids = [str(i) for i in range(len(vecs))]
        for i in range(0, len(vecs), 5000):
            self.col.add(ids=ids[i:i + 5000],
                         embeddings=vecs[i:i + 5000].tolist())

    def search(self, qvec, k):
        res = self.col.query(query_embeddings=[qvec.tolist()], n_results=k)
        return [int(x) for x in res["ids"][0]]


class LanceDB(Base):
    name = "lancedb_dense"

    def connect(self):
        import lancedb
        self.version = getattr(lancedb, "__version__", "?")
        self.db = lancedb.connect("/tmp/l3d_lance")

    def build(self, vecs):
        import pyarrow as pa
        tbl = pa.table({"id": pa.array(range(len(vecs)), type=pa.int64()),
                        "vector": pa.FixedSizeListArray.from_arrays(
                            pa.array(vecs.ravel(), type=pa.float32()), DIM)})
        self.tbl = self.db.create_table("articles", tbl)
        # IVF_HNSW_SQ is LanceDB's HNSW offering (int8 SQ; disclosed above)
        self.tbl.create_index(metric="l2", index_type="IVF_HNSW_SQ",
                              m=M, ef_construction=EF_CONSTRUCTION)

    def search(self, qvec, k):
        rs = self.tbl.search(qvec).limit(k).to_list()
        return [int(r["id"]) for r in rs]


class SqliteVec(Base):
    name = "sqlite_vec_dense"

    def connect(self):
        import sqlite3
        import sqlite_vec
        self.version = sqlite_vec.__version__
        self.cx = sqlite3.connect("/tmp/l3d_sqlitevec.db")
        self.cx.enable_load_extension(True)
        sqlite_vec.load(self.cx)
        self.cx.enable_load_extension(False)

    def build(self, vecs):
        self.cx.execute(
            f"CREATE VIRTUAL TABLE v USING vec0(embedding float[{DIM}])")
        for i in range(0, len(vecs), BATCH):
            chunk = vecs[i:i + BATCH]
            self.cx.executemany(
                "INSERT INTO v (rowid, embedding) VALUES (?, ?)",
                [(i + j, chunk[j].tobytes()) for j in range(len(chunk))])
            self.cx.commit()

    def search(self, qvec, k):
        rows = self.cx.execute(
            "SELECT rowid FROM v WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance", (qvec.tobytes(), k)).fetchall()
        return [int(r[0]) for r in rows]


class DuckVSS(Base):
    name = "duckdb_vss_dense"

    def connect(self):
        import duckdb
        self.version = duckdb.__version__
        self.cx = duckdb.connect("/tmp/l3d_duck.db")
        self.cx.execute("INSTALL vss; LOAD vss;")
        self.cx.execute("SET hnsw_enable_experimental_persistence=true;")

    def build(self, vecs):
        # native bulk path: Arrow FixedSizeList -> DuckDB FLOAT[DIM] in one
        # relational insert (fairness: executemany over Python lists measured
        # ~2h for 1M x 128 and is a harness artifact, not the engine)
        import pyarrow as pa
        flat = pa.array(vecs.astype("float32").reshape(-1), type=pa.float32())
        tbl = pa.table({
            "id": pa.array(range(len(vecs)), type=pa.int64()),
            "vec": pa.FixedSizeListArray.from_arrays(flat, DIM),
        })
        self.cx.register("src", tbl)
        self.cx.execute(f"CREATE TABLE t AS SELECT id, vec::FLOAT[{DIM}] AS vec FROM src")
        self.cx.unregister("src")
        self.cx.execute(
            f"CREATE INDEX hn ON t USING HNSW (vec) "
            f"WITH (metric = 'l2sq', M = {M}, ef_construction = {EF_CONSTRUCTION})")
        self.cx.execute(f"SET hnsw_ef_search = {EF_SEARCH}")

    def search(self, qvec, k):
        rows = self.cx.execute(
            f"SELECT id FROM t ORDER BY array_distance(vec, ?::FLOAT[{DIM}]) "
            f"LIMIT {k}", [qvec.tolist()]).fetchall()
        return [int(r[0]) for r in rows]


class Qdrant(Base):
    name = "qdrant_dense"

    def connect(self):
        from qdrant_client import QdrantClient
        import qdrant_client
        self.version = getattr(qdrant_client, "__version__", "?")
        self.cl = QdrantClient(host=os.environ["BENCH_SERVER_HOST"], port=6333,
                               timeout=600)

    def build(self, vecs):
        from qdrant_client import models as qm
        self.cl.create_collection(
            "articles",
            vectors_config=qm.VectorParams(
                size=DIM, distance=qm.Distance.EUCLID,
                hnsw_config=qm.HnswConfigDiff(m=M, ef_construct=EF_CONSTRUCTION)))
        for i in range(0, len(vecs), BATCH):
            self.cl.upsert("articles", points=qm.Batch(
                ids=list(range(i, i + len(vecs[i:i + BATCH]))),
                vectors=vecs[i:i + BATCH].tolist()))

    def post_build(self):  # settle: wait for green status (indexing done)
        from qdrant_client import models as qm  # noqa: F401
        for _ in range(600):
            if self.cl.get_collection("articles").status == "green":
                return
            time.sleep(1)

    def search(self, qvec, k):
        from qdrant_client import models as qm
        res = self.cl.query_points(
            "articles", query=qvec.tolist(), limit=k,
            search_params=qm.SearchParams(hnsw_ef=EF_SEARCH))
        return [int(p.id) for p in res.points]


class Milvus(Base):
    name = "milvus_dense"

    def connect(self):
        from pymilvus import MilvusClient
        import pymilvus
        self.version = getattr(pymilvus, "__version__", "?")
        self.cl = MilvusClient(
            uri=f"http://{os.environ['BENCH_SERVER_HOST']}:19530", timeout=600)

    def build(self, vecs):
        from pymilvus import DataType
        sch = self.cl.create_schema()
        sch.add_field("id", DataType.INT64, is_primary=True)
        sch.add_field("vec", DataType.FLOAT_VECTOR, dim=DIM)
        idx = self.cl.prepare_index_params()
        idx.add_index("vec", index_type="HNSW", metric_type="L2",
                      params={"M": M, "efConstruction": EF_CONSTRUCTION})
        self.cl.create_collection("articles", schema=sch, index_params=idx)
        for i in range(0, len(vecs), BATCH):
            self.cl.insert("articles", [
                {"id": i + j, "vec": vecs[i + j].tolist()}
                for j in range(min(BATCH, len(vecs) - i))])

    def post_build(self):  # settle: flush + load (Milvus's own recommended path)
        self.cl.flush("articles")
        self.cl.load_collection("articles")

    def search(self, qvec, k):
        res = self.cl.search("articles", data=[qvec.tolist()], limit=k,
                             search_params={"params": {"ef": EF_SEARCH}})
        return [int(h["id"]) for h in res[0]]


BACKENDS = {b.name: b for b in
            (ArcadeEmbedded, ArcadeServer, Chroma, LanceDB, SqliteVec, DuckVSS, Qdrant, Milvus)}


def pct(vals):
    s = sorted(vals)
    n = len(s)
    return {"p50": s[n // 2], "p95": s[int(n * .95)], "p99": s[int(n * .99)],
            "mean": statistics.mean(s), "max": s[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", default="search")
    ap.add_argument("--scale", default="micro")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    train, test, gt = load_dataset(args.scale)
    out = {"lane": "l3d", "n_docs": len(train), "dims": DIM, "k": K,
           "n_queries": len(test), "m": M, "ef_construction": EF_CONSTRUCTION,
           "ef_search": EF_SEARCH}

    b = BACKENDS[args.backend]()
    out["hnsw_M"] = M  # recorded so degree-matched ablation rows are self-describing
    out["quantization"] = os.environ.get("BENCH_DENSE_QUANT", "none")
    t0 = time.perf_counter()
    b.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = b.version

    t0 = time.perf_counter()
    b.build(train)
    b.post_build()
    build = time.perf_counter() - t0
    out["build_s"] = round(build, 2)
    out["build_docs_per_s"] = round(len(train) / build, 1)

    for q in test[:20]:  # warmup, untimed
        b.search(q, K)
    lats, recalls = [], []
    t0 = time.perf_counter()
    for qi in range(len(test)):
        t1 = time.perf_counter()
        ids = b.search(test[qi], K)
        lats.append((time.perf_counter() - t1) * 1e3)
        recalls.append(len(set(ids[:K]) & set(gt[qi].tolist())) / K)
    span = time.perf_counter() - t0
    p = pct(lats)
    out.update({f"query_{k}_ms": round(v, 3) for k, v in p.items()})
    out["qps"] = round(len(test) / span, 1)
    out["recall_at_10"] = round(statistics.mean(recalls), 4)

    b.close()
    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT", json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
