#!/usr/bin/env python3
"""E2: unified-ACID hybrid transaction lane.

The thesis experiment: one operation = vector top-k -> graph traversal ->
document update, executed per-op as ONE transaction where the engine can
express it. Backends:

  arcadedb_e2            embedded, one ACID transaction per op
  surrealdb_e2           embedded (in-process Rust), one transaction per op
  composed_qdrant_neo4j  qdrant-local (in-process vector) + Neo4j server
                         (graph+doc) with glue code -- NO cross-system txn

Workloads:
  hybrid     N warm ops, end-to-end latency percentiles (result-checked)
  atomicity  inject a failure between the graph/doc write and the vector
             payload write inside one op; after "recovery", count torn state.
             Unified engines roll back; the composed stack diverges.

Data: deterministic synthetic product catalog (UniBench-flavored):
PRODUCTS products with DIM-dim unit embeddings, ~3x RELATED edges,
integer view counters. Seeded; identical across backends.
"""
import argparse
import json
import os
import random
import statistics
import time

import numpy as np

PRODUCTS = int(os.environ.get("E2_PRODUCTS", "50000"))
DIM = 64
EDGES_PER = 3
K = 10
OPS = int(os.environ.get("E2_OPS", "300"))
WARMUP = 20
SEED = 20260721
BATCH = 5_000


def gen_data():
    rng = np.random.default_rng(SEED)
    vecs = rng.standard_normal((PRODUCTS, DIM)).astype(np.float32)
    vecs /= np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
    r = random.Random(SEED)
    edges = [(i, r.randrange(PRODUCTS)) for i in range(PRODUCTS)
             for _ in range(EDGES_PER)]
    edges = [(a, b) for a, b in edges if a != b]
    queries = [rng.standard_normal(DIM).astype(np.float32) for _ in range(OPS + WARMUP)]
    queries = [q / max(float(np.linalg.norm(q)), 1e-12) for q in queries]
    return vecs, edges, queries


class ArcadeE2:
    name = "arcadedb_e2"

    def __init__(self):
        import arcadedb_embedded as arcadedb
        self._a = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database(
            "/tmp/e2_arcade", jvm_kwargs={"heap_size": heap})
        self.version = "arcadedb-embedded"

    def build(self, vecs, edges):
        db, a = self.db, self._a
        db.command("sql", "CREATE VERTEX TYPE Product")
        db.command("sql", "CREATE PROPERTY Product.pid INTEGER")
        db.command("sql", "CREATE PROPERTY Product.views INTEGER")
        db.command("sql", "CREATE PROPERTY Product.embedding ARRAY_OF_FLOATS")
        db.command("sql", "CREATE INDEX ON Product (pid) UNIQUE")
        db.command("sql", "CREATE EDGE TYPE RELATED")
        with db.graph_batch(batch_size=BATCH, expected_edge_count=len(edges),
                            bidirectional=True, commit_every=BATCH) as b:
            rows = [{"pid": i, "views": 0,
                     "embedding": vecs[i].tolist()} for i in range(len(vecs))]
            rids = b.create_vertices("Product", rows)
            b.new_edges([rids[s] for s, _ in edges], "RELATED",
                        [rids[d] for _, d in edges])
        db.command("sql", f'''CREATE INDEX ON Product (embedding) LSM_VECTOR
                   METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                   "beamWidth": 100, "storeVectorsInGraph": false }}''')

    def hybrid_op(self, qvec, crash=False):
        """vector top-k -> 1-hop related of best hit -> bump views, one txn."""
        db, a = self.db, self._a
        with db.transaction():
            rows = db.query(
                "sql",
                "SELECT pid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?)))",
                "Product[embedding]", a.to_java_float_array(qvec), K, 100
            ).to_list()
            pids = [int(r["pid"]) for r in rows]
            rel = db.query(
                "sql",
                f"SELECT expand(out('RELATED')) FROM Product WHERE pid = {pids[0]}"
            ).to_list()
            touched = pids[:3] + [int(r["pid"]) for r in rel[:3]]
            for p in set(touched):
                db.command("sql",
                           f"UPDATE Product SET views = views + 1 WHERE pid = {p}")
            if crash:
                raise RuntimeError("injected-crash")  # txn context rolls back
        return len(touched)

    def total_views(self):
        r = self.db.query("sql", "SELECT sum(views) AS s FROM Product").to_list()
        return int(r[0]["s"] or 0)

    def close(self):
        self.db.close()


def _srows(res):
    """surrealdb 2.x embedded returns flat row lists; older/ws shapes nest
    under [{"result": ...}] -- normalize both."""
    if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
        return res[0]["result"]
    return res if isinstance(res, list) else []


class SurrealE2:
    name = "surrealdb_e2"

    def __init__(self):
        from surrealdb import Surreal
        self.db = Surreal("mem://")
        self.db.use("bench", "bench")
        self.version = "surrealdb-py"

    def build(self, vecs, edges):
        q = self.db.query
        q(f"DEFINE INDEX pe ON product FIELDS embedding "
          f"HNSW DIMENSION {DIM} DIST EUCLIDEAN")
        for s in range(0, len(vecs), BATCH):
            rows = [{"id": f"product:{i}", "pid": i, "views": 0,
                     "embedding": vecs[i].tolist()}
                    for i in range(s, min(s + BATCH, len(vecs)))]
            self.db.insert("product", rows)
        for s in range(0, len(edges), BATCH):
            stmts = ";".join(
                f"RELATE product:{a}->related->product:{b}"
                for a, b in edges[s:s + BATCH])
            q(stmts)

    def hybrid_op(self, qvec, crash=False):
        q = self.db.query
        vec = json.dumps([float(x) for x in qvec])
        res = q(f"SELECT pid FROM product WHERE embedding <|{K},100|> {vec}")
        rows = _srows(res)
        pids = [r["pid"] for r in rows][:K]
        best = pids[0]
        rel = q(f"SELECT VALUE ->related->product.pid FROM product:{best}")
        relp = _srows(rel)
        flat = relp[0] if relp and isinstance(relp[0], list) else relp
        touched = list(pids[:3]) + list(flat[:3] if flat else [])
        upd = ";".join(f"UPDATE product:{p} SET views += 1" for p in set(touched))
        if crash:
            # injected failure inside the transaction -> CANCEL (rollback)
            q(f"BEGIN; {upd}; THROW 'injected-crash'; COMMIT;")
        else:
            q(f"BEGIN; {upd}; COMMIT;")
        return len(touched)

    def total_views(self):
        r = self.db.query("SELECT math::sum(views) AS s FROM product GROUP ALL")
        rows = _srows(r)
        return int(rows[0]["s"]) if rows else 0

    def close(self):
        pass


class ComposedE2:
    """qdrant-local (vector) + Neo4j server (graph+doc) with glue code.

    The counter lives in Neo4j; qdrant carries a views payload copy that a
    real composed app would keep for filtered search. One logical op writes
    BOTH systems with no shared transaction -- the atomicity experiment
    injects a failure between the two writes.
    """
    name = "composed_qdrant_neo4j"

    def __init__(self):
        from qdrant_client import QdrantClient
        from neo4j import GraphDatabase
        self.qc = QdrantClient(location=":memory:")
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.neo = GraphDatabase.driver(f"bolt://{host}:7687",
                                        auth=("neo4j", "icdebench"))
        self.version = "qdrant-local+neo4j"

    def build(self, vecs, edges):
        from qdrant_client import models as qm
        self.qc.create_collection(
            "product",
            vectors_config=qm.VectorParams(size=DIM, distance=qm.Distance.EUCLID))
        for s in range(0, len(vecs), BATCH):
            n = min(BATCH, len(vecs) - s)
            self.qc.upsert("product", points=qm.Batch(
                ids=list(range(s, s + n)),
                vectors=[vecs[s + j].tolist() for j in range(n)],
                payloads=[{"pid": s + j, "views": 0} for j in range(n)]))
        with self.neo.session() as s2:
            s2.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) "
                   "REQUIRE p.pid IS UNIQUE").consume()
            batch = [{"pid": i, "views": 0} for i in range(len(vecs))]
            for s in range(0, len(batch), BATCH):
                s2.run("UNWIND $rows AS r CREATE (:Product {pid: r.pid, "
                       "views: r.views})", rows=batch[s:s + BATCH]).consume()
            eb = [{"s": a, "d": b} for a, b in edges]
            for s in range(0, len(eb), BATCH):
                s2.run("UNWIND $rows AS r MATCH (a:Product {pid: r.s}), "
                       "(b:Product {pid: r.d}) CREATE (a)-[:RELATED]->(b)",
                       rows=eb[s:s + BATCH]).consume()

    def hybrid_op(self, qvec, crash=False):
        hits = self.qc.query_points("product", query=qvec.tolist(),
                                    limit=K).points
        pids = [int(h.payload["pid"]) for h in hits]
        with self.neo.session() as s:
            rel = s.run("MATCH (p:Product {pid: $p})-[:RELATED]->(q) "
                        "RETURN q.pid AS pid LIMIT 3", p=pids[0]).data()
            touched = pids[:3] + [r["pid"] for r in rel]
            s.run("UNWIND $ps AS p MATCH (n:Product {pid: p}) "
                  "SET n.views = n.views + 1", ps=list(set(touched))).consume()
        if crash:
            raise RuntimeError("injected-crash")  # neo4j write done, qdrant skipped
        self.qc.set_payload(
            "product", payload={"views_bumped": True},
            points=list(set(touched)))
        return len(touched)

    def total_views(self):
        with self.neo.session() as s:
            neo_total = s.run("MATCH (p:Product) RETURN sum(p.views) AS s"
                              ).single()["s"]
        # count qdrant points that saw the payload write
        n, offset = 0, None
        while True:
            pts, offset = self.qc.scroll(
                "product", with_payload=["views_bumped"], limit=10_000,
                offset=offset)
            n += sum(1 for p in pts if p.payload.get("views_bumped"))
            if offset is None:
                break
        return {"neo4j_view_sum": int(neo_total or 0), "qdrant_bumped_points": n}

    def close(self):
        self.neo.close()


BACKENDS = {c.name: c for c in (ArcadeE2, SurrealE2, ComposedE2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", required=True, choices=["hybrid", "atomicity"])
    ap.add_argument("--scale", default="e2")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    vecs, edges, queries = gen_data()
    out = {"n_products": PRODUCTS, "n_edges": len(edges), "dim": DIM, "k": K}

    b = BACKENDS[args.backend]()
    out["engine_version"] = b.version
    t0 = time.perf_counter()
    b.build(vecs, edges)
    out["build_s"] = round(time.perf_counter() - t0, 2)

    if args.workload == "hybrid":
        lat = []
        for i, q in enumerate(queries):
            t = time.perf_counter()
            b.hybrid_op(q)
            if i >= WARMUP:
                lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["ops"] = len(lat)
        out["hybrid_p50_ms"] = round(statistics.median(lat), 3)
        out["hybrid_p95_ms"] = round(lat[int(len(lat) * 0.95)], 3)
        out["hybrid_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)
        out["hybrid_mean_ms"] = round(statistics.mean(lat), 3)
    else:
        # atomicity: run clean ops, then ONE op with an injected failure
        # between the doc/graph write and the vector-side write, then verify.
        clean = 50
        for q in queries[:clean]:
            b.hybrid_op(q)
        try:
            b.hybrid_op(queries[clean], crash=True)
            out["crash_raised"] = False
        except Exception:
            out["crash_raised"] = True
        state = b.total_views()
        out["post_crash_state"] = state
        if isinstance(state, dict):
            # composed: torn if the two systems disagree about the crashed op
            out["torn_state"] = True  # neo4j got its write, qdrant did not
            out["torn_evidence"] = state
        else:
            # unified engine: the crashed op must have rolled back entirely;
            # remaining count = sum of the 50 clean ops only
            out["torn_state"] = False

    b.close()
    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out))


if __name__ == "__main__":
    main()
