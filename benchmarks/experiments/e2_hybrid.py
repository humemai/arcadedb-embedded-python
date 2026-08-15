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
            "/tmp/e2_arcade",
            # In THIS lane the asymmetry had a direct comparator: the
            # composed arm's Neo4j gets NEO4J_server_memory_heap_initial
            # __size pinned, so under a protocol the paper says applies to
            # everyone, the comparator got the committed, latency-stable
            # heap and ArcadeDB got one that grows.
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
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

    def hybrid_op(self, qvec, crash=False, mirror=False):
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
            # id is the RECORD-ID PART, not the full thing. Passing
            # f"product:{i}" here stores product:<product:i>, and every later
            # `UPDATE product:{p}` / `RELATE product:{a}->...` then addresses a
            # record that does not exist -- silently, because this client
            # returns per-statement errors in the payload instead of raising.
            # That is exactly what happened: all SurrealDB writes were no-ops
            # and total_views() honestly reported 0 for five campaigns.
            rows = [{"id": i, "pid": i, "views": 0,
                     "embedding": vecs[i].tolist()}
                    for i in range(s, min(s + BATCH, len(vecs)))]
            self.db.insert("product", rows)
        for s in range(0, len(edges), BATCH):
            stmts = ";".join(
                f"RELATE product:{a}->related->product:{b}"
                for a, b in edges[s:s + BATCH])
            q(stmts)

    def hybrid_op(self, qvec, crash=False, mirror=False):
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
        # NO `else 0`. A read that returns nothing is a broken read, and it must
        # not be indistinguishable from a database that is genuinely empty --
        # that conflation is half of why the old SurrealDB result looked green.
        if not rows:
            raise RuntimeError("surreal: total_views read returned no rows")
        return int(rows[0]["s"])

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
                                        auth=("neo4j", "dbbenchpass"))
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

    def hybrid_op(self, qvec, crash=False, mirror=False):
        """mirror=True copies the actual counter into qdrant, which costs an
        extra neo4j read. That read is needed to compare the two systems on the
        SAME quantity in the atomicity trial, but it must not be charged to the
        composed stack in the LATENCY workload -- adding a round-trip to the
        rival's op would flatter us. So the timed path keeps the cheap batched
        write it always had, and only the atomicity path mirrors."""
        hits = self.qc.query_points("product", query=qvec.tolist(),
                                    limit=K).points
        pids = [int(h.payload["pid"]) for h in hits]
        with self.neo.session() as s:
            rel = s.run("MATCH (p:Product {pid: $p})-[:RELATED]->(q) "
                        "RETURN q.pid AS pid LIMIT 3", p=pids[0]).data()
            touched = pids[:3] + [r["pid"] for r in rel]
            tp = list(set(touched))
            s.run("UNWIND $ps AS p MATCH (n:Product {pid: p}) "
                  "SET n.views = n.views + 1", ps=tp).consume()
            # Read the new counters back so qdrant mirrors the SAME QUANTITY.
            # The old code wrote a `views_bumped: True` flag, which is a
            # different measure from neo4j's running sum: a product touched by
            # two ops adds 2 to the sum but only 1 to the flag count. The two
            # sides therefore diverged even with no crash and no tearing, so
            # their difference could never have evidenced tornness.
            newv = (s.run("MATCH (n:Product) WHERE n.pid IN $ps "
                          "RETURN n.pid AS pid, n.views AS v", ps=tp).data()
                    if mirror else None)
        if crash:
            raise RuntimeError("injected-crash")  # neo4j write done, qdrant skipped
        if mirror:
            for r in newv:
                self.qc.set_payload("product", payload={"views": int(r["v"])},
                                    points=[int(r["pid"])])
        else:
            self.qc.set_payload("product", payload={"views_bumped": True},
                                points=tp)
        return len(touched)

    def total_views(self):
        """Both subsystems' view of the SAME counter, plus how many products
        they actually disagree about. The disagreement count is the torn-state
        evidence: it is zero when the two stay consistent and non-zero the
        moment one takes a write the other did not."""
        with self.neo.session() as s:
            rows = s.run("MATCH (p:Product) WHERE p.views > 0 "
                         "RETURN p.pid AS pid, p.views AS v").data()
        neo = {int(r["pid"]): int(r["v"]) for r in rows}
        qd, offset = {}, None
        while True:
            pts, offset = self.qc.scroll(
                "product", with_payload=["views"], limit=10_000, offset=offset)
            for p in pts:
                v = int(p.payload.get("views") or 0)
                if v:
                    qd[int(p.id)] = v
            if offset is None:
                break
        disagree = [p for p in set(neo) | set(qd) if neo.get(p, 0) != qd.get(p, 0)]
        return {"neo4j_view_sum": sum(neo.values()),
                "qdrant_view_sum": sum(qd.values()),
                "disagreeing_products": len(disagree)}

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
        # TRIAL COUNT. This used to be a single trial per rep, five reps, and
        # the paper said "5 of 5". By the rule of three, 5 trials with 0
        # failures only bounds the true failure rate below ~45% at 95%
        # confidence -- far too weak to carry an atomicity claim. Each trial
        # costs a handful of ops, so there is no reason to be stingy: 40 per
        # rep across 5 reps is 200 trials, which bounds it below ~1.5%.
        trials = int(os.environ.get("E2_TRIALS", "40"))
        warm_clean = 50            # establishes a non-zero baseline once
        per_trial_clean = 5        # fresh clean work before each injection

        for q in queries[:warm_clean]:
            b.hybrid_op(q, mirror=True)

        # VALIDITY GUARD, and it is not optional. The previous version of this
        # block decided the result from `isinstance(state, dict)` -- i.e. from
        # WHICH BACKEND was running, never from a comparison -- so every
        # single-engine backend was stamped atomic by construction. SurrealDB
        # then reported 0 across five campaigns because its writes were silently
        # addressing records that did not exist, and the else-branch published
        # that as a clean rollback. An arm whose clean ops moved nothing cannot
        # demonstrate anything about rollback, so it fails loudly here instead.
        base = b.total_views()
        moved = (base["neo4j_view_sum"] > 0 if isinstance(base, dict)
                 else base > 0)
        if not moved:
            raise RuntimeError(
                f"{b.name}: {warm_clean} clean ops left the view counters at "
                f"{base}; the writes are not landing, so every atomicity trial "
                "here is void")

        torn, raised, evidence = 0, 0, []
        cursor = warm_clean
        for t in range(trials):
            for _ in range(per_trial_clean):
                b.hybrid_op(queries[cursor % len(queries)], mirror=True)
                cursor += 1
            pre = b.total_views()
            try:
                b.hybrid_op(queries[cursor % len(queries)], crash=True, mirror=True)
            except Exception:
                raised += 1
            cursor += 1
            post = b.total_views()

            if isinstance(post, dict):
                # composed stack: torn iff the two systems now hold DIFFERENT
                # values for the same products. Measured, not assumed -- and
                # the clean ops set the baseline, which must be 0.
                t_torn = post["disagreeing_products"] > pre["disagreeing_products"]
            else:
                # unified engine: the crashed op must have left NOTHING behind,
                # so the counter has to be exactly where the clean ops left it.
                t_torn = post != pre
            torn += bool(t_torn)
            if t_torn and len(evidence) < 3:
                evidence.append({"trial": t, "pre": pre, "post": post})

        out["trials"] = trials
        out["torn_count"] = torn
        out["crash_raised_count"] = raised
        out["torn_state"] = torn > 0
        out["post_crash_state"] = b.total_views()
        if evidence:
            out["torn_evidence"] = evidence

    b.close()
    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out))


if __name__ == "__main__":
    main()
