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
import bench_common

import numpy as np
import surreal_common
import arango_common

PRODUCTS = int(os.environ.get("E2_PRODUCTS", "50000"))
DIM = 64
EDGES_PER = 3
K = 10
OPS = int(os.environ.get("E2_OPS", "300"))
WARMUP = 20
SEED = 20260721
BATCH = 5_000
# NO ROW CAP ON THE SERVED ARM (2026-09-14). The ArcadeDB HTTP API truncates a
# result at 20,000 rows unless the request says otherwise, and the #88 digests
# caught both served time-series arms returning exactly 20,000 where every
# other engine returned 32,944. Nothing on this lane returns that many rows
# today, which is precisely why it would have gone unnoticed the day one did.
# -1 means no cap.
HTTP_LIMIT = -1



# ---------------------------------------------------------------------------
# THE TWO READ PATHS (DECISIONS #82c). The table measured one write path, which
# argues atomicity well and says nothing about the shape most people run, which
# is retrieval. Both are read-only and run on the same corpus, BEFORE the write
# loop, so every views counter is still zero and the document half of the
# answer is deterministic on every engine.
#
#   retrieval        vector top-k, a one-hop expansion, a projection of the
#                    documents found.
#   filtered search  a top-k restricted to the neighbourhood of a start node:
#                    "the case that separates a single engine from a composed
#                    stack, because the engine can push the filter into the
#                    index while the stack has to move a candidate set between
#                    two systems".
#
# HOW THE HALVES ARE CHECKED, and this is the part #82c is explicit about: the
# vector half is approximate, so it is checked by RECALL against a brute-force
# answer over the same candidate set, exactly as the vector lanes are; the
# graph and document halves are deterministic and are digest-compared exactly.
# A number that comes out of an approximate index is never fed into a digest,
# because a gate that fires on the index's own approximation is a gate people
# learn to ignore.
#
# The expansion anchors on a FIXED start product per query rather than on the
# engine's own best hit, for the same reason: the best hit is the approximate
# half's output, and anchoring on it would make the exactly-comparable half
# depend on the half that is not.
READ_OPS = int(os.environ.get("E2_READ_OPS", "200"))
FILTER_HOPS = 3
# How wide a post-filtering engine searches before dropping non-neighbours.
# Recorded on the row: it is the only knob in this measurement and it decides
# what a post-filter arm's recall can possibly be.
FILTER_OVERFETCH = int(os.environ.get("E2_FILTER_OVERFETCH", "1000"))
RETRIEVAL_DIGEST = dict(columns=("pid", "views"))
FILTER_CAND_DIGEST = dict(columns=("start", "n_candidates"))


def build_adjacency(edges, n):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
    return adj


def neighbourhood(adj, start, hops):
    """The harness's own answer for the candidate set, from the generated
    edges. The engines derive theirs by traversing; comparing the two is what
    checks the graph half of the filtered search."""
    seen, frontier = set(), [start]
    for _ in range(hops):
        nxt = []
        for p in frontier:
            for q in adj[p]:
                if q != start and q not in seen:
                    seen.add(q)
                    nxt.append(q)
        frontier = nxt
        if not frontier:
            break
    return sorted(seen)


def brute_topk(vecs, q, k, candidates=None):
    """Exact nearest neighbours, over every vector or over a candidate set."""
    if candidates is None:
        d = np.linalg.norm(vecs - q, axis=1)
        idx = np.argsort(d, kind="stable")[:k]
        return [int(i) for i in idx]
    if not candidates:
        return []
    cand = np.asarray(candidates, dtype=np.int64)
    d = np.linalg.norm(vecs[cand] - q, axis=1)
    order = np.argsort(d, kind="stable")[:k]
    return [int(cand[i]) for i in order]


def recall_at_k(got, want):
    if not want:
        return 1.0
    return round(len(set(int(g) for g in got) & set(int(w) for w in want)) / float(len(want)), 4)


def engine_neighbourhood(ad, start, hops):
    """The candidate set as the ENGINE sees it: one traversal query per hop.

    One query per hop rather than a variable-length path, because a
    variable-length path is spelled four different ways across these engines
    and two of them cannot express it at all; a hop is a hop everywhere, and
    every arm pays the same number of round trips.
    """
    seen, frontier = set(), [start]
    for _ in range(hops):
        nxt = [int(p) for p in ad._hop(frontier) if p != start and p not in seen]
        seen.update(nxt)
        frontier = sorted(set(nxt))
        if not frontier:
            break
    return sorted(seen)


def do_retrieval(ad, qvec, start_pid):
    """vector top-k -> one-hop expansion -> document projection, one read path."""
    pids = ad._vec_topk(qvec, K)
    nbrs = sorted(set(int(p) for p in ad._hop([start_pid])))
    docs = ad._docs(nbrs) if nbrs else []
    return pids, docs


def do_filtered(ad, qvec, start_pid):
    """top-k restricted to the start node's neighbourhood."""
    cands = engine_neighbourhood(ad, start_pid, FILTER_HOPS)
    return ad._rank_candidates(qvec, cands, K), cands


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
            # txWalFlush explicit at both classes (DECISIONS #90).
            jvm_kwargs={"heap_size": heap,
                        "jvm_args": bench_common.arcade_jvm_args(f"-Xms{heap}")})
        # THE WHEEL'S version, not its name (#156). A row stamped
        # "arcadedb-embedded" cannot be re-measured by anyone including us.
        from importlib.metadata import version as _v
        self.version = _v("arcadedb-embedded")
        self.durability = bench_common.arcade_durability_readback()

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

    # THE TWO READ PATHS (DECISIONS #82c).
    #
    # POST-FILTER, AND IT IS NOT A CHOICE. ArcadeDB 26.8.1 exposes no scalar
    # vector-distance function in SQL -- vectorDistance, similarity,
    # cosineSimilarity, euclideanDistance and vector_distance are all "Unknown
    # function name" (laptop probe, 2026-09-14) -- so a candidate set cannot be
    # ranked by distance and the graph filter cannot be pushed into the index.
    # The arm over-fetches a global search and drops the non-neighbours, and
    # its recall says what that costs. Every other engine on this table ranks
    # the candidate set directly.
    FILTER_MODE = ("post-filter: no scalar vector-distance function in SQL at 26.8.1, "
                   "so an over-fetched global search is filtered afterwards")

    def _vec_topk(self, qvec, k, ef=100):
        rows = self.db.query(
            "sql", "SELECT pid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?)))",
            "Product[embedding]", self._a.to_java_float_array(qvec), k, max(ef, k)).to_list()
        return [int(r["pid"]) for r in rows]

    def _hop(self, pids):
        if not pids:
            return []
        lst = ",".join(str(int(p)) for p in pids)
        rows = self.db.query("sql", f"SELECT pid FROM (SELECT expand(out('RELATED')) "
                                    f"FROM Product WHERE pid IN [{lst}])").to_list()
        return [int(r["pid"]) for r in rows]

    def _docs(self, pids):
        if not pids:
            return []
        lst = ",".join(str(int(p)) for p in pids)
        return self.db.query("sql", f"SELECT pid, views FROM Product WHERE pid IN [{lst}]").to_list()

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        lst = ",".join(str(int(p)) for p in cands)
        rows = self.db.query(
            "sql", f"SELECT pid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
                   f"WHERE pid IN [{lst}] LIMIT {k}",
            "Product[embedding]", self._a.to_java_float_array(qvec),
            FILTER_OVERFETCH, max(100, FILTER_OVERFETCH)).to_list()
        return [int(r["pid"]) for r in rows]

    def total_views(self):
        r = self.db.query("sql", "SELECT sum(views) AS s FROM Product").to_list()
        return int(r[0]["s"] or 0)

    def close(self):
        self.db.close()


class ArcadeE2Server(ArcadeE2):
    """The same operation against the ArcadeDB SERVER over HTTP, in one server
    transaction (2026-09-07, user: both deployments for every ArcadeDB row).

    The transaction is the HTTP session one: POST /begin/bench opens it and
    returns `arcadedb-session-id`, every command carries that header, and the
    operation ends in /commit or /rollback. The injected crash raises after the
    three writes and BEFORE the commit, and the trial's rollback is explicit,
    which is what a client that dies mid-operation gets from the server anyway
    (an uncommitted session is discarded). Same SQL as the embedded arm; the
    vector query takes its parameters by name because the HTTP API has no
    positional binding.
    """
    name = "arcadedb_e2_server"

    def __init__(self):
        self.durability = (bench_common.at_class(bench_common.DURABILITY_ARCADEDB)
                           + bench_common.ARCADE_SERVER_DURABILITY_NOTE)
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "dbbenchpass")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        try:
            info = self.rq.get(f"http://{host}:{port}/api/v1/server", timeout=30)
            self.version = "server:" + (info.json().get("version") or "?")
        except Exception:  # noqa: BLE001
            self.version = "server:unknown"

    def _post(self, kind, command, params=None, language="sql", sid=None, timeout=600):
        payload = {"language": language, "command": command}
        if kind == "query":
            payload["limit"] = HTTP_LIMIT   # only the query endpoint takes a row cap
        if params:
            payload["params"] = params
        headers = {"arcadedb-session-id": sid} if sid else None
        r = self.rq.post(f"{self.base}/{kind}/bench", json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def _script(self, statements, sid=None):
        return self._post("command", ";".join(statements), language="sqlscript", sid=sid)

    def build(self, vecs, edges):
        for ddl in ("CREATE VERTEX TYPE Product", "CREATE PROPERTY Product.pid INTEGER",
                    "CREATE PROPERTY Product.views INTEGER",
                    "CREATE PROPERTY Product.embedding ARRAY_OF_FLOATS",
                    "CREATE INDEX ON Product (pid) UNIQUE", "CREATE EDGE TYPE RELATED"):
            self._post("command", ddl)
        buf = []
        for i in range(len(vecs)):
            emb = ",".join(f"{x:.6g}" for x in vecs[i].tolist())
            buf.append(f"CREATE VERTEX Product SET pid = {i}, views = 0, embedding = [{emb}]")
            if len(buf) >= 1000:
                self._script(buf); buf = []
        if buf:
            self._script(buf); buf = []
        for sidx, didx in edges:
            buf.append(f"CREATE EDGE RELATED FROM (SELECT FROM Product WHERE pid = {sidx}) "
                       f"TO (SELECT FROM Product WHERE pid = {didx})")
            if len(buf) >= 1000:
                self._script(buf); buf = []
        if buf:
            self._script(buf)
        self._post("command", f'''CREATE INDEX ON Product (embedding) LSM_VECTOR
                   METADATA {{ "dimensions": {DIM}, "similarity": "EUCLIDEAN",
                   "beamWidth": 100, "storeVectorsInGraph": false }}''', timeout=3600)

    def hybrid_op(self, qvec, crash=False, mirror=False):
        r = self.rq.post(f"{self.base}/begin/bench", timeout=60)
        r.raise_for_status()
        sid = r.headers.get("arcadedb-session-id")
        try:
            rows = self._post("query", "SELECT pid FROM (SELECT expand(vectorNeighbors(:idx, :q, :k, :ef)))",
                              {"idx": "Product[embedding]", "q": [float(x) for x in qvec], "k": K, "ef": 100}, sid=sid)
            pids = [int(r["pid"]) for r in rows]
            rel = self._post("query", f"SELECT expand(out('RELATED')) FROM Product WHERE pid = {pids[0]}", sid=sid)
            touched = pids[:3] + [int(r["pid"]) for r in rel[:3]]
            for p_ in set(touched):
                self._post("command", f"UPDATE Product SET views = views + 1 WHERE pid = {p_}", sid=sid)
            if crash:
                raise RuntimeError("injected-crash")
            self.rq.post(f"{self.base}/commit/bench", headers={"arcadedb-session-id": sid}, timeout=60).raise_for_status()
        except Exception:
            try:
                self.rq.post(f"{self.base}/rollback/bench", headers={"arcadedb-session-id": sid}, timeout=60)
            except Exception:  # noqa: BLE001
                pass
            raise
        return len(touched)

    # The same two read paths over HTTP; the same post-filter, for the same
    # reason (the SQL is the server's, and the function is missing there too).
    def _vec_topk(self, qvec, k, ef=100):
        rows = self._post("query", "SELECT pid FROM (SELECT expand(vectorNeighbors(:idx, :q, :k, :ef)))",
                          {"idx": "Product[embedding]", "q": [float(x) for x in qvec],
                           "k": k, "ef": max(ef, k)})
        return [int(r["pid"]) for r in rows]

    def _hop(self, pids):
        if not pids:
            return []
        lst = ",".join(str(int(p)) for p in pids)
        rows = self._post("query", f"SELECT pid FROM (SELECT expand(out('RELATED')) "
                                   f"FROM Product WHERE pid IN [{lst}])")
        return [int(r["pid"]) for r in rows]

    def _docs(self, pids):
        if not pids:
            return []
        lst = ",".join(str(int(p)) for p in pids)
        return self._post("query", f"SELECT pid, views FROM Product WHERE pid IN [{lst}]")

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        lst = ",".join(str(int(p)) for p in cands)
        rows = self._post("query",
                          f"SELECT pid FROM (SELECT expand(vectorNeighbors(:idx, :q, :k, :ef))) "
                          f"WHERE pid IN [{lst}] LIMIT {k}",
                          {"idx": "Product[embedding]", "q": [float(x) for x in qvec],
                           "k": FILTER_OVERFETCH, "ef": max(100, FILTER_OVERFETCH)})
        return [int(r["pid"]) for r in rows]

    def total_views(self):
        r = self._post("query", "SELECT sum(views) AS s FROM Product")
        return int(r[0]["s"] or 0)

    def close(self):
        self.rq.close()


def _srows(res):
    """surrealdb 2.x embedded returns flat row lists; older/ws shapes nest
    under [{"result": ...}] -- normalize both."""
    if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
        return res[0]["result"]
    return res if isinstance(res, list) else []


class SurrealE2:
    """SurrealDB embedded through its Python SDK, on the SDK's SurrealKV disk
    store (2026-09-11; it ran at mem:// before, which no other engine on the
    table was allowed). The SDK bundles core 2.3.10 behind an SDK version of 2.0.0; the served twin below
    runs the 3.2.4 server on RocksDB."""
    name = "surrealdb_e2"
    URL = "surrealkv:///tmp/e2_surrealkv"

    def __init__(self):
        # SURREAL_SYNC_DATA before the datastore opens (DECISIONS #90).
        self.durability = bench_common.at_class(bench_common.DURABILITY_SURREAL_EMBEDDED)
        surreal_common.apply_durability()
        import shutil
        from surrealdb import Surreal
        shutil.rmtree("/tmp/e2_surrealkv", ignore_errors=True)
        self.db = Surreal(self.URL)
        self.db.use("bench", "bench")
        try:
            self.version = surreal_common.engine_stamp(self.db)   # core version, not the SDK's (F39)
        except Exception:  # noqa: BLE001
            from importlib.metadata import version as _v
            self.version = "surrealdb-py:" + _v("surrealdb")

    def build(self, vecs, edges):
        q = self.db.query
        # A fresh cell gets a fresh server; a reused one (laptop smoke) must
        # not fail on "index already exists".
        q("REMOVE TABLE IF EXISTS related; REMOVE TABLE IF EXISTS product")
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
        # Bulk relation insert, not RELATE statements: on the graph lane 5,000
        # RELATEs over the wire took 34.6 s against 0.6 s for one
        # insert_relation call (2026-09-11), and the served cross-model cell
        # sat in this loop past its 15-minute laptop smoke budget (2026-09-12).
        from surrealdb import RecordID
        for s in range(0, len(edges), BATCH):
            self.db.insert_relation("related", [
                {"in": RecordID("product", a), "out": RecordID("product", b)}
                for a, b in edges[s:s + BATCH]])

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

    FILTER_MODE = ("pre-filter: the candidate set is restricted first and ranked by "
                   "vector::distance::euclidean")

    def _vec_topk(self, qvec, k, ef=100):
        vec = json.dumps([float(x) for x in qvec])
        rows = _srows(self.db.query(f"SELECT pid FROM product WHERE embedding <|{k},{max(ef, k)}|> {vec}"))
        return [int(r["pid"]) for r in rows]

    def _hop(self, pids):
        if not pids:
            return []
        lst = ",".join(f"product:{int(p)}" for p in pids)
        out = []
        for r in _srows(self.db.query(f"SELECT VALUE ->related->product.pid FROM [{lst}]")):
            out.extend(r if isinstance(r, list) else [r])
        return [int(x) for x in out if x is not None]

    def _docs(self, pids):
        if not pids:
            return []
        lst = ",".join(f"product:{int(p)}" for p in pids)
        return _srows(self.db.query(f"SELECT pid, views FROM [{lst}]"))

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        vec = json.dumps([float(x) for x in qvec])
        lst = ",".join(str(int(p)) for p in cands)
        rows = _srows(self.db.query(
            f"SELECT pid, vector::distance::euclidean(embedding, {vec}) AS d FROM product "
            f"WHERE pid INSIDE [{lst}] ORDER BY d ASC LIMIT {k}"))
        return [int(r["pid"]) for r in rows]

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


class SurrealServedE2(SurrealE2):
    """SurrealDB 3.2.4 server on RocksDB, reached over WebSocket; the same
    SurrealQL as the embedded arm."""
    name = "surrealdb_e2_server"

    def __init__(self):
        # One shared client for every served arm (DECISIONS #91): it sets the
        # WebSocket options the SDK leaves at the library's defaults, and it
        # reconnects, re-authenticates and re-selects the namespace once when
        # the socket dies mid-query.
        self.db = surreal_common.served_client()
        self.version = "surrealdb-server:" + str(self.db.version()).replace("surrealdb-", "")


class ArangoE2:
    """ArangoDB 3.12.11 served (2026-09-13): product documents with an
    embedding under the engine's vector index (FAISS IVF), related as an
    edge collection, the vector hit in AQL, the hop as a traversal, and the
    document updates inside one stream transaction that the crash trial
    aborts before commit."""
    name = "arangodb_e2"

    def __init__(self):
        self.cl, self.db, self.version = arango_common.connect()

    def build(self, vecs, edges):
        # waitForSync on the collection the timed transaction writes (#90).
        _sync = arango_common.sync_flag()
        prod = self.db.create_collection("product", sync=_sync)
        rel = self.db.create_collection("related", edge=True)
        self.durability = arango_common.durability_readback(self.db, "product")
        for s in range(0, len(vecs), BATCH):
            prod.import_bulk([{"_key": str(i), "pid": i, "views": 0, "embedding": vecs[i].tolist()}
                              for i in range(s, min(s + BATCH, len(vecs)))])
        for s in range(0, len(edges), BATCH):
            rel.import_bulk([{"_from": f"product/{a}", "_to": f"product/{b}"} for a, b in edges[s:s + BATCH]])
        self.ivf_nlists, self.ivf_nprobe = arango_common.vector_index(prod, "embedding", DIM, len(vecs))

    def hybrid_op(self, qvec, crash=False, mirror=False):
        aql = self.db.aql
        pids = list(aql.execute(
            "FOR d IN product LET s = APPROX_NEAR_L2(d.embedding, @q, {nProbe: @np}) SORT s LIMIT @k RETURN d.pid",
            bind_vars={"q": [float(x) for x in qvec], "np": self.ivf_nprobe, "k": K}))
        best = pids[0]
        rel = list(aql.execute("FOR r IN 1..1 OUTBOUND CONCAT('product/', @b) related RETURN r.pid",
                               bind_vars={"b": str(best)}))
        touched = list(pids[:3]) + list(rel[:3])
        txn = self.db.begin_transaction(write=["product"])
        txn.aql.execute("FOR k IN @keys LET p = DOCUMENT('product', k) UPDATE p WITH {views: p.views + 1} IN product",
                        bind_vars={"keys": [str(p) for p in set(touched)]})
        if crash:
            # injected failure inside the transaction -> abort (rollback)
            txn.abort_transaction()
            raise RuntimeError("injected-crash")
        txn.commit_transaction()
        return len(touched)

    FILTER_MODE = "pre-filter: FILTER on the candidate set, SORT by L2_DISTANCE"

    def _vec_topk(self, qvec, k, ef=None):
        return [int(x) for x in self.db.aql.execute(
            "FOR d IN product LET s = APPROX_NEAR_L2(d.embedding, @q, {nProbe: @np}) SORT s LIMIT @k RETURN d.pid",
            bind_vars={"q": [float(x) for x in qvec], "np": self.ivf_nprobe, "k": k})]

    def _hop(self, pids):
        if not pids:
            return []
        return [int(x) for x in self.db.aql.execute(
            "FOR p IN @ps FOR r IN 1..1 OUTBOUND CONCAT('product/', p) related RETURN r.pid",
            bind_vars={"ps": [str(int(p)) for p in pids]})]

    def _docs(self, pids):
        if not pids:
            return []
        return list(self.db.aql.execute(
            "FOR p IN product FILTER p.pid IN @ids RETURN {pid: p.pid, views: p.views}",
            bind_vars={"ids": [int(p) for p in pids]}))

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        return [int(x) for x in self.db.aql.execute(
            "FOR p IN product FILTER p.pid IN @ids SORT L2_DISTANCE(p.embedding, @q) LIMIT @k RETURN p.pid",
            bind_vars={"ids": [int(p) for p in cands],
                       "q": [float(x) for x in qvec], "k": k})]

    def total_views(self):
        rows = list(self.db.aql.execute("FOR p IN product COLLECT AGGREGATE s = SUM(p.views) RETURN s"))
        if not rows or rows[0] is None:
            raise RuntimeError("arangodb: total_views read returned no rows")
        return int(rows[0])

    def close(self):
        arango_common.close(self.cl)


class PgAgeE2:
    """PostgreSQL 17 with pgvector and Apache AGE in one database: the vector
    hit is an HNSW query on a vector column, the hop is Cypher through AGE
    over RELATED edges, the update is a row update, all inside one
    transaction. The strongest "one engine" rival to the claim this lane
    tests (2026-09-11)."""
    name = "pg_age_e2"

    def __init__(self):
        import psycopg
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.cx = psycopg.connect(f"host={host} dbname=bench user=postgres password=dbbenchpass",
                                  autocommit=False)
        with self.cx.cursor() as c:
            c.execute("SHOW synchronous_commit")   # read, not asserted (#81, #90)
            self.durability = bench_common.pg_durability_string(c.fetchone()[0])
            c.execute("CREATE EXTENSION IF NOT EXISTS vector")
            c.execute("CREATE EXTENSION IF NOT EXISTS age")
            c.execute("SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','age')")
            ext = dict(c.fetchall())
            c.execute("SELECT version()")
            pv = c.fetchone()[0].split(" (")[0]
        self.cx.commit()
        self.version = f"{pv} + pgvector:{ext.get('vector')} + age:{ext.get('age')}"

    def _cur(self):
        c = self.cx.cursor()
        c.execute("LOAD 'age'")
        c.execute('SET search_path = ag_catalog, "$user", public')
        return c

    def build(self, vecs, edges):
        c = self._cur()
        # A fresh cell gets a fresh server; a reused one (laptop smoke) starts clean.
        c.execute("DROP TABLE IF EXISTS product")
        c.execute("SELECT ag_catalog.drop_graph('e2graph', true) FROM ag_catalog.ag_graph WHERE name = 'e2graph'")
        self.cx.commit()
        c = self._cur()
        c.execute(f"CREATE TABLE product (pid INTEGER PRIMARY KEY, views INTEGER NOT NULL DEFAULT 0, embedding vector({DIM}))")
        with c.copy("COPY product (pid, views, embedding) FROM STDIN") as cp:
            for i in range(len(vecs)):
                cp.write_row((i, 0, "[" + ",".join("%.9g" % x for x in vecs[i]) + "]"))
        c.execute("CREATE INDEX ON product USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 100)")
        c.execute("SELECT create_graph('e2graph')")
        c.execute("SELECT * FROM cypher('e2graph', $$ CREATE (:Product {pid: -1}) $$) AS (v agtype)")
        c.execute("SELECT * FROM cypher('e2graph', $$ MATCH (p:Product {pid: -1}) DELETE p $$) AS (v agtype)")
        c.execute("""CREATE INDEX ON e2graph."Product" USING btree (ag_catalog.agtype_access_operator(properties, '"pid"'::agtype))""")
        for s in range(0, len(vecs), BATCH):
            c.execute("SELECT * FROM cypher('e2graph', $$ UNWIND $rows AS r CREATE (:Product {pid: r}) $$, %s) AS (v agtype)",
                      (json.dumps({"rows": list(range(s, min(s + BATCH, len(vecs))))}),))
        # Edges by VERTEX ID, not by property map (BUGS F35, 2026-09-12): AGE
        # answers `MATCH (a:Product {pid: r.s})` inside UNWIND with a scan of
        # the vertex table per row, which put 150k edges at about 6.4 hours
        # on the laptop; `WHERE id(a) = r.s` builds them in 3.7 minutes. The
        # pid->id map is one MATCH over the 50k vertices.
        c.execute("SELECT * FROM cypher('e2graph', $$ MATCH (p:Product) RETURN p.pid, id(p) $$) AS (pid agtype, gid agtype)")
        gid = {int(str(r[0])): int(str(r[1])) for r in c.fetchall()}
        for s in range(0, len(edges), BATCH):
            c.execute("SELECT * FROM cypher('e2graph', $$ UNWIND $rows AS r MATCH (a:Product), (b:Product) WHERE id(a) = r.s AND id(b) = r.d CREATE (a)-[:RELATED]->(b) $$, %s) AS (v agtype)",
                      (json.dumps({"rows": [{"s": gid[a], "d": gid[b]} for a, b in edges[s:s + BATCH]]}),))
        c.execute("ANALYZE")
        self.cx.commit()

    def hybrid_op(self, qvec, crash=False, mirror=False):
        c = self._cur()
        c.execute("SET LOCAL hnsw.ef_search = 100")
        c.execute("SELECT pid FROM product ORDER BY embedding <-> %s::vector LIMIT %s",
                  ("[" + ",".join("%.9g" % float(x) for x in qvec) + "]", K))
        pids = [int(r[0]) for r in c.fetchall()]
        # WHERE a.pid = x, not {pid: x}: the map form scanned (17 ms), the
        # WHERE form uses the expression index on pid (1.0 ms), same probe.
        c.execute(f"SELECT * FROM cypher('e2graph', $$ MATCH (a:Product)-[:RELATED]->(b) WHERE a.pid = {pids[0]} RETURN b.pid $$) AS (pid agtype)")
        rel = [int(str(r[0])) for r in c.fetchall()]
        touched = pids[:3] + rel[:3]
        c.execute("UPDATE product SET views = views + 1 WHERE pid = ANY(%s)", (list(set(touched)),))
        if crash:
            self.cx.rollback()
            raise RuntimeError("injected-crash")
        self.cx.commit()
        return len(touched)

    FILTER_MODE = "pre-filter: WHERE pid = ANY(...) then ORDER BY the pgvector <-> operator"

    def _v(self, qvec):
        return "[" + ",".join("%.9g" % float(x) for x in qvec) + "]"

    def _vec_topk(self, qvec, k, ef=100):
        c = self._cur()
        # SET LOCAL takes no bound parameter ("syntax error at or near $1",
        # laptop 2026-09-14); the value is a literal, as it is in hybrid_op.
        c.execute(f"SET LOCAL hnsw.ef_search = {int(max(ef, k))}")
        c.execute("SELECT pid FROM product ORDER BY embedding <-> %s::vector LIMIT %s", (self._v(qvec), k))
        r = [int(x[0]) for x in c.fetchall()]
        self.cx.commit()
        return r

    def _hop(self, pids):
        if not pids:
            return []
        c = self._cur()
        lst = ",".join(str(int(p)) for p in pids)
        c.execute(f"SELECT * FROM cypher('e2graph', $$ MATCH (a:Product)-[:RELATED]->(b) "
                  f"WHERE a.pid IN [{lst}] RETURN b.pid $$) AS (pid agtype)")
        r = [int(str(x[0])) for x in c.fetchall()]
        self.cx.commit()
        return r

    def _docs(self, pids):
        if not pids:
            return []
        c = self._cur()
        c.execute("SELECT pid, views FROM product WHERE pid = ANY(%s)", (list(int(p) for p in pids),))
        r = c.fetchall()
        self.cx.commit()
        return r

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        c = self._cur()
        c.execute("SELECT pid FROM product WHERE pid = ANY(%s) ORDER BY embedding <-> %s::vector LIMIT %s",
                  (list(int(p) for p in cands), self._v(qvec), k))
        r = [int(x[0]) for x in c.fetchall()]
        self.cx.commit()
        return r

    def total_views(self):
        c = self._cur()
        c.execute("SELECT sum(views) FROM product")
        v = int(c.fetchone()[0] or 0)
        self.cx.commit()
        return v

    def close(self):
        self.cx.close()


class Neo4jE2:
    """Neo4j 2026.07 alone: Product nodes with an embedding property under its
    vector index, RELATED edges, the views counter on the node; the hit, the
    hop and the update run in one explicit transaction (2026-09-11)."""
    name = "neo4j_e2"

    def __init__(self):
        from neo4j import GraphDatabase
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.drv = GraphDatabase.driver(f"bolt://{host}:7687", auth=("neo4j", "dbbenchpass"))
        with self.drv.session() as s:
            v = s.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v").single()["v"]
        self.version = f"neo4j:{v}"

    def build(self, vecs, edges):
        with self.drv.session() as s:
            s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.pid IS UNIQUE").consume()
            for b0 in range(0, len(vecs), BATCH):
                rows = [{"pid": i, "e": vecs[i].tolist()} for i in range(b0, min(b0 + BATCH, len(vecs)))]
                s.run("UNWIND $rows AS r CREATE (:Product {pid: r.pid, views: 0, embedding: r.e})", rows=rows).consume()
            eb = [{"s": a, "d": b} for a, b in edges]
            for b0 in range(0, len(eb), BATCH):
                s.run("UNWIND $rows AS r MATCH (a:Product {pid: r.s}), (b:Product {pid: r.d}) CREATE (a)-[:RELATED]->(b)",
                      rows=eb[b0:b0 + BATCH]).consume()
            s.run(f"CREATE VECTOR INDEX prod_emb IF NOT EXISTS FOR (p:Product) ON (p.embedding) "
                  f"OPTIONS {{indexConfig: {{`vector.dimensions`: {DIM}, `vector.similarity_function`: 'euclidean', "
                  f"`vector.hnsw.m`: 16, `vector.hnsw.ef_construction`: 100}}}}").consume()
            s.run("CALL db.awaitIndexes(36000)").consume()

    def hybrid_op(self, qvec, crash=False, mirror=False):
        with self.drv.session() as s:
            tx = s.begin_transaction()
            try:
                hits = tx.run("CYPHER 25 MATCH (p:Product) SEARCH p IN (VECTOR INDEX prod_emb FOR $q LIMIT 100) "
                              "SCORE AS sc RETURN p.pid AS pid ORDER BY sc DESC LIMIT $k",
                              q=[float(x) for x in qvec], k=K).data()
                pids = [int(h["pid"]) for h in hits]
                rel = tx.run("MATCH (p:Product {pid: $p})-[:RELATED]->(q) RETURN q.pid AS pid LIMIT 3", p=pids[0]).data()
                touched = pids[:3] + [int(r["pid"]) for r in rel]
                tx.run("UNWIND $ps AS p MATCH (n:Product {pid: p}) SET n.views = n.views + 1", ps=list(set(touched))).consume()
                if crash:
                    tx.rollback()
                    raise RuntimeError("injected-crash")
                tx.commit()
            finally:
                tx.close()
        return len(touched)

    FILTER_MODE = ("pre-filter: WHERE p.pid IN $ids then ORDER BY "
                   "vector.similarity.euclidean")

    def _vec_topk(self, qvec, k, ef=100):
        with self.drv.session() as s:
            hits = s.run("CYPHER 25 MATCH (p:Product) SEARCH p IN (VECTOR INDEX prod_emb FOR $q LIMIT $ef) "
                         "SCORE AS sc RETURN p.pid AS pid ORDER BY sc DESC LIMIT $k",
                         q=[float(x) for x in qvec], k=k, ef=max(ef, k)).data()
        return [int(h["pid"]) for h in hits]

    def _hop(self, pids):
        if not pids:
            return []
        with self.drv.session() as s:
            return [int(r["pid"]) for r in s.run(
                "MATCH (p:Product)-[:RELATED]->(q) WHERE p.pid IN $ps RETURN q.pid AS pid",
                ps=[int(p) for p in pids]).data()]

    def _docs(self, pids):
        if not pids:
            return []
        with self.drv.session() as s:
            return s.run("MATCH (p:Product) WHERE p.pid IN $ids "
                         "RETURN p.pid AS pid, p.views AS views",
                         ids=[int(p) for p in pids]).data()

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        with self.drv.session() as s:
            return [int(r["pid"]) for r in s.run(
                "MATCH (p:Product) WHERE p.pid IN $ids RETURN p.pid AS pid "
                "ORDER BY vector.similarity.euclidean(p.embedding, $q) DESC LIMIT $k",
                ids=[int(p) for p in cands], q=[float(x) for x in qvec], k=k).data()]

    def total_views(self):
        with self.drv.session() as s:
            return int(s.run("MATCH (n:Product) RETURN sum(n.views) AS s").single()["s"] or 0)

    def close(self):
        self.drv.close()


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
        # BOTH HALVES, with versions (#156). A composed stack whose row names
        # two engines and versions neither cannot be reproduced, and this arm
        # is the comparator our atomicity claim rests on.
        from importlib.metadata import version as _v
        try:
            _qv = _v("qdrant-client")
        except Exception:
            _qv = "?"
        try:
            with self.neo.session() as _s:
                _nv = _s.run("CALL dbms.components() YIELD versions "
                             "RETURN versions[0] AS v").single()["v"]
        except Exception as e:
            _nv = f"unknown ({e.__class__.__name__})"
        self.version = f"qdrant-local:{_qv}+neo4j:{_nv}"

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

    # THE COMPOSED STACK'S VERSION OF THE SAME TWO PATHS. The filter is a
    # pre-filter, as on the single engines that can express one, but the
    # candidate set has to cross a process boundary: Neo4j answers the
    # traversal, the ids are serialised into a Qdrant filter, and Qdrant
    # ranks. That crossing is the quantity this arm exists to price.
    FILTER_MODE = ("cross-system pre-filter: the candidate ids are read from Neo4j "
                   "and sent to Qdrant as a filter")

    def _vec_topk(self, qvec, k, ef=100):
        hits = self.qc.query_points("product", query=list(map(float, qvec)), limit=k).points
        return [int(h.payload["pid"]) for h in hits]

    def _hop(self, pids):
        if not pids:
            return []
        with self.neo.session() as s:
            return [int(r["pid"]) for r in s.run(
                "MATCH (p:Product)-[:RELATED]->(q) WHERE p.pid IN $ps RETURN q.pid AS pid",
                ps=[int(p) for p in pids]).data()]

    def _docs(self, pids):
        if not pids:
            return []
        with self.neo.session() as s:
            return s.run("MATCH (p:Product) WHERE p.pid IN $ids "
                         "RETURN p.pid AS pid, p.views AS views",
                         ids=[int(p) for p in pids]).data()

    def _rank_candidates(self, qvec, cands, k):
        if not cands:
            return []
        from qdrant_client import models as qm
        flt = qm.Filter(must=[qm.FieldCondition(
            key="pid", match=qm.MatchAny(any=[int(p) for p in cands]))])
        hits = self.qc.query_points("product", query=list(map(float, qvec)),
                                    query_filter=flt, limit=k).points
        return [int(h.payload["pid"]) for h in hits]

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


BACKENDS = {c.name: c for c in (ArcadeE2, ArcadeE2Server, SurrealE2, SurrealServedE2, ArangoE2, PgAgeE2, Neo4jE2, ComposedE2)}


# DECISIONS #81, recorded on every row. PG+AGE reads the server's
# synchronous_commit on connect (see PgAgeE2); the composed stack's document
# and graph half is Neo4j, which cannot be relaxed.
# Every string, and the evidence for the default it names, is in bench_common.
DURABILITY = {
    "arcadedb_e2": bench_common.DURABILITY_ARCADEDB,
    "arcadedb_e2_server": bench_common.DURABILITY_ARCADEDB,
    "surrealdb_e2": bench_common.DURABILITY_SURREAL_EMBEDDED,
    "surrealdb_e2_server": bench_common.DURABILITY_SURREAL_SERVER,
    "arangodb_e2": arango_common.DURABILITY,
    "neo4j_e2": bench_common.DURABILITY_NEO4J,
    # The composed stack's document and graph half is Neo4j, so the whole
    # operation waits for Neo4j's log; Qdrant's WAL runs at its own default.
    "composed_qdrant_neo4j": bench_common.DURABILITY_NEO4J + "; Qdrant WAL at its default",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", required=True, choices=["hybrid", "atomicity"])
    ap.add_argument("--scale", default="e2")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # PHASE MARKERS (2026-09-14, same pattern as l3d_dense): a cell that dies
    # names the phase it was in. Entered and left AROUND the timed work, never
    # inside a timed loop.
    _beat = bench_common.PhaseBeat()
    _beat.mark("data-gen-start", backend=args.backend, workload=args.workload)
    vecs, edges, queries = gen_data()
    _beat.mark("data-generated", n_products=PRODUCTS, n_edges=len(edges),
               n_queries=len(queries))
    out = {"n_products": PRODUCTS, "n_edges": len(edges), "dim": DIM, "k": K}

    # A cross-model adapter connects in its constructor (every class here
    # does), so the connect phase wraps the construction, not a connect call.
    with _beat.phase("connect", backend=args.backend):
        b = BACKENDS[args.backend]()
    out["engine_version"] = b.version
    out["instrument"] = bench_common.INSTRUMENT
    t0 = time.perf_counter()
    with _beat.phase("build", n=PRODUCTS, n_edges=len(edges)):
        b.build(vecs, edges)
    out["build_s"] = round(time.perf_counter() - t0, 2)
    # AFTER THE BUILD, not before it. ArangoDB's waitForSync lives on the
    # collection, so the adapter can only read it back once build() has created
    # one; stamping before the build took the map's relaxed constant and a
    # strict cell recorded the relaxed string. fairness_check F10b caught it,
    # which is what it is for (laptop, 2026-09-14).
    bench_common.stamp_durability(out, getattr(b, "durability", None)
                                  or DURABILITY.get(args.backend))

    if args.workload == "hybrid":
        # ------------------------------------------------------------------
        # THE TWO READ PATHS (DECISIONS #82c), BEFORE the write loop, because
        # they are read-only and because every views counter is still zero
        # here, which is what makes the document half of the answer
        # deterministic and therefore digest-comparable across engines.
        adj = build_adjacency(edges, PRODUCTS)
        srng = random.Random(SEED + 7)
        starts = [srng.randrange(PRODUCTS) for _ in range(READ_OPS)]
        out["filtered_mode"] = getattr(b, "FILTER_MODE", "not declared")
        out["filtered_overfetch"] = FILTER_OVERFETCH
        out["filtered_hops"] = FILTER_HOPS
        out["read_ops"] = READ_OPS

        _beat.mark("retrieval-start", n=READ_OPS)
        rlat, rrec, rdocs, rhops = [], [], [], []
        for i in range(READ_OPS):
            q, sp = queries[i % len(queries)], starts[i]
            t = time.perf_counter()
            pids, docs = do_retrieval(b, q, sp)
            _dt = (time.perf_counter() - t) * 1000
            surreal_common.keep(b, rlat, _dt)
            if i == 0:
                # _dt, not rlat[0]: the sample above is dropped when the
                # connection broke during it (DECISIONS #91), and the cold
                # number is still what that first query cost.
                bench_common.record_first_query(out, "retrieval", _dt)
            # Recall of the VECTOR half against an exact answer, computed
            # outside the clock. The graph and document halves are digested.
            rrec.append(recall_at_k(pids, brute_topk(vecs, q, K)))
            rdocs.extend(docs or [])
            rhops.append((sp, len(docs or [])))
        _rl = sorted(rlat)
        out["retrieval_p50_ms"] = round(statistics.median(_rl), 3)
        out["retrieval_p95_ms"] = round(_rl[int(len(_rl) * 0.95)], 3)
        out["retrieval_p99_ms"] = round(_rl[int(len(_rl) * 0.99)], 3)
        bench_common.record_cold_warm(out, "retrieval", rlat)
        out["recall_retrieval"] = round(sum(rrec) / len(rrec), 4)
        bench_common.record_result(out, "retrieval_docs", rdocs, **RETRIEVAL_DIGEST)
        bench_common.record_result(out, "retrieval_hops", rhops,
                                   columns=("start", "n_docs"))
        _beat.mark("retrieval-done", p50=out["retrieval_p50_ms"],
                   recall=out["recall_retrieval"])

        _beat.mark("filtered-start", n=READ_OPS)
        flat, frec, fcand, fmatch = [], [], [], 0
        for i in range(READ_OPS):
            q, sp = queries[i % len(queries)], starts[i]
            t = time.perf_counter()
            got, cands = do_filtered(b, q, sp)
            surreal_common.keep(b, flat, (time.perf_counter() - t) * 1000)
            # RECALL AGAINST BRUTE FORCE OVER THE SAME FILTERED CANDIDATE SET
            # (#82c): an engine that filters after the search instead of
            # before shows it here rather than in latency alone.
            want = brute_topk(vecs, q, K, neighbourhood(adj, sp, FILTER_HOPS))
            frec.append(recall_at_k(got, want))
            fcand.append((sp, len(cands)))
            if sorted(int(x) for x in cands) == neighbourhood(adj, sp, FILTER_HOPS):
                fmatch += 1
        _fl = sorted(flat)
        out["filtered_p50_ms"] = round(statistics.median(_fl), 3)
        out["filtered_p95_ms"] = round(_fl[int(len(_fl) * 0.95)], 3)
        out["filtered_p99_ms"] = round(_fl[int(len(_fl) * 0.99)], 3)
        bench_common.record_cold_warm(out, "filtered", flat)
        out["recall_filtered"] = round(sum(frec) / len(frec), 4)
        _ns = sorted(n for _s, n in fcand)
        out["filtered_cand_p50"] = _ns[len(_ns) // 2]
        # Did the engine's own traversal find the same candidate set the
        # harness derives from the generated edges? A recall of zero means
        # nothing if the candidate set was wrong to begin with.
        out["filtered_candset_match"] = round(fmatch / float(READ_OPS), 4)
        bench_common.record_result(out, "filtered_candidates", fcand, **FILTER_CAND_DIGEST)
        _beat.mark("filtered-done", p50=out["filtered_p50_ms"],
                   recall=out["recall_filtered"])

        lat = []
        _beat.mark("hybrid-start", n=len(queries), warmup=WARMUP)
        for i, q in enumerate(queries):
            t = time.perf_counter()
            b.hybrid_op(q)
            if i >= WARMUP:
                surreal_common.keep(b, lat, (time.perf_counter() - t) * 1000)
        lat.sort()
        out["ops"] = len(lat)
        out["hybrid_p50_ms"] = round(statistics.median(lat), 3)
        out["hybrid_p95_ms"] = round(lat[int(len(lat) * 0.95)], 3)
        out["hybrid_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)
        out["hybrid_mean_ms"] = round(statistics.mean(lat), 3)
        # DECISIONS #89: the composed write is a transaction against a warm
        # database by construction, so it carries the reason rather than a
        # blank cold/warm pair. The two read paths above DO carry the split.
        out["cold_warm_na"] = bench_common.NA_COLD_WARM_TXN
        _beat.mark("hybrid-done", n=len(lat), p50=out["hybrid_p50_ms"])
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

        # DECISIONS #89 as amended: this workload times no query. Its own
        # first operation is a clean composed WRITE, and the cold column the
        # page prints comes from the hybrid cell beside it.
        out["cold_first_query_na"] = ("this workload times an interrupted write, not a "
                                      "query; the cold column comes from the hybrid cell "
                                      "(DECISIONS #89)")
        _beat.mark("atomicity-warmup-start", n=warm_clean, trials=trials)
        for q in queries[:warm_clean]:
            b.hybrid_op(q, mirror=True)
        _beat.mark("atomicity-trials-start", trials=trials)

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

        _beat.mark("atomicity-trials-done", trials=trials, torn=torn, raised=raised)
        out["trials"] = trials
        out["torn_count"] = torn
        out["crash_raised_count"] = raised
        out["torn_state"] = torn > 0
        out["post_crash_state"] = b.total_views()
        if evidence:
            out["torn_evidence"] = evidence

    # TIME THE CLOSE, do not merely perform it. This lane always closed, but it
    # never recorded what the close cost, so the row could not be told apart
    # from a lane that hard-exits and never settles at all (#155). A clean
    # close is when compaction, writeback and WAL truncation happen: measured
    # on 26.8.1 it settles a roughly fixed 30-87 MB, against nothing at all for
    # an already-settled comparator. An unrecorded close is an unpriced one.
    _t = time.perf_counter()
    with _beat.phase("close"):
        b.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)
    # `reconnects` on every SurrealDB row, zero when nothing happened
    # (DECISIONS #91): a dropped connection has to be visible as a number on
    # the row, not as a traceback in a log nobody reads until a cell dies.
    surreal_common.stamp_reconnects(out, b)
    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out))


if __name__ == "__main__":
    main()
