"""L6: what a SERVED engine costs to come back after a restart, and to go down cleanly.

WHY THIS LANE EXISTS (DECISIONS #139 item 2). The lifecycle table times an
embedded session's open and close; a server has no such step to time (a
database is resident in the running server, and ArcadeDB's open-database
command has no counterpart in SurrealDB's, ArangoDB's, MongoDB's or
PostgreSQL's servers). What a served engine HAS instead is a restart, which an
operator meets after every upgrade, configuration change, and crash: how long
until the server answers again, on the same data, and how long a clean shutdown
takes. Every served engine on the page can run that, so every one is on it.

WHAT IS TIMED, per cycle, on the SAME container the runner started (same data,
flags, cpuset, memory cap, and network name):

  stop (idle)    the engine's own clean shutdown (`docker stop`: the image's
                 STOPSIGNAL, SIGTERM when it declares none, then SIGKILL after
                 a grace the engine never reaches) after a session that wrote
                 nothing: from the signal to the process gone.
  restart        `docker start`, then the engine answering: START is the start
                 call to the first successful liveness call, FIRST QUERY from
                 there to the first answer to a fixed read that equals the
                 answer the engine gave before the stop. TOTAL is both.
  write batch    a fixed number of single-record writes, each committed (not
                 timed for the table; it is what the next stop has to flush).
  stop (write)   the same clean shutdown after that write session. The
                 lifecycle lane's rule applies (DECISIONS #50): a clean stop
                 should be O(what was written), not O(what is stored).
  restart        again, after the write session (its recovery may replay what
                 the stop did not flush), and the batch read back: a write
                 committed before a clean stop must survive it.

The first cycle is warm-up (its idle stop also flushes the whole load; it is
recorded as shutdown_after_load_s and not printed); the rest are medians.

THE OS PAGE CACHE IS WARM, deliberately and on the row: the container stops and
starts on the same host, so the engine's files are still in the host's page
cache. This is a process restart (upgrade, configuration change, crash), not a
host reboot; evicting a server's data needs its data directory on a bind mount
the lane can reach, which no server arm has (BUGS/DECISIONS for the cold variant).

DATA: one model per engine, through that engine's own loader on its own lane,
at that lane's tiers and envelope (FAIRNESS F3/F6): documents (TPC-H, l1_tpc),
graph (LDBC SNB persons and friendships, l2_graph), dense vectors (SIFT, l3d),
time series (TSBS cpu, l4). Rows of different models are different tables'
data and are never compared with each other; the scale names the model.

  l6_restart.py --backend B --workload restart --scale S --out PATH
"""
import argparse
import json
import os
import statistics as st
import sys
import tarfile
import io
import time

import bench_common
import docker_api

ITERS = int(os.environ.get("BENCH_RS_ITERS", "5"))
WARMUP = int(os.environ.get("BENCH_RS_WARMUP", "1"))
WRITE_N = int(os.environ.get("BENCH_RS_WRITE_N", "1000"))
GRACE_S = int(os.environ.get("BENCH_RS_GRACE_S", "600"))
POLL_S = float(os.environ.get("BENCH_RS_POLL_S", "0.05"))
START_TIMEOUT_S = float(os.environ.get("BENCH_RS_START_TIMEOUT_S", "1800"))
TRACE = os.environ.get("BENCH_RS_TRACE", "") == "1"
VERIFY_S = float(os.environ.get("BENCH_RS_VERIFY_S", "300"))

# Which model each served arm runs, and through which lane's loader. One model
# per engine (DECISIONS #139); a binary that several arms share is one row
# (PostgreSQL stands for pgvector, PostgreSQL + AGE, and TimescaleDB, whose
# images run the same server and whose extensions keep no in-memory state a
# start must rebuild: the HNSW index, the graph, and the hypertables are
# relations read through shared buffers).
#
# ArcadeDB's server runs every model, because a page table publishes a tier only
# where ArcadeDB has a row (export_web: a tier of comparator rows alone would read
# as "ArcadeDB could not do this"), and because the engine under test should be
# beside each group it is compared with.
MODEL = {
    "arcadedb_server": "docs", "surrealdb_tpc_server": "docs", "arangodb_tpc": "docs",
    "mongodb": "docs", "postgres": "docs",
    "arcadedb_graph_server": "graph",
    "neo4j_graph": "graph", "memgraph_graph": "graph", "falkordb_graph": "graph",
    "arcadedb_dense_server": "dense",
    "qdrant_dense": "dense", "milvus_dense": "dense", "elasticsearch_dense": "dense",
    "mongodb_dense": "dense",
    "arcadedb_ts_native_server": "ts",
    "questdb": "ts",
}
ARCADE_READY = "GET /api/v1/ready"


def _arcade_query(language, command, params=None, timeout=30):
    import requests
    body = {"language": language, "command": command}
    if params:
        body["params"] = params
    r = requests.post(f"http://{HOST}:2480/api/v1/query/bench", auth=("root", "dbbenchpass"),
                      json=body, timeout=timeout)
    r.raise_for_status()
    return r.json().get("result", [])
# The tiers each model runs at, the source lane's own names, so the runner gives
# each cell the envelope that lane's cells get. micro is the laptop smoke tier.
MODEL_SCALES = {
    "docs": {"tpch1", "tpch10", "micro"},
    "graph": {"sf1", "sf10", "micro"},
    "dense": {"small", "deep10m", "micro"},
    "ts": {"ts100", "ts1000"},
}
# Corpus selectors that the source lanes read at IMPORT time, derived here from
# the scale so a stage cannot measure one corpus under another's name (BUGS F6).
TPC_SF = {"tpch1": "1", "tpch10": "10"}
DENSE_DATA = {"small": "/data/dense", "deep10m": "/data/deep10m"}
LDBC_SCALES = {"sf1", "sf10"}

HOST = os.environ.get("BENCH_SERVER_HOST", "localhost")

# The vector servers' durability. Their own lane times only an ingest and sets
# none, so the restart lane runs them at the engine default too, and says that
# rather than a class it has not established; the shutdown trace (laptop,
# BENCH_RS_TRACE=1) records what each stop actually synced.
DURABILITY_VECTOR_DEFAULT = ("engine default, not set by the harness (the vector lane times only an "
                             "ingest); what a stop syncs is in the shutdown trace")


# ------------------------------------------------------------------ engines
class Engine:
    """What the lane needs from one served arm.

    build()          load the data through the source lane's adapter, return row extras
    ping()           one cheap liveness call on a FRESH client; raises until the engine is up
    read()           the fixed read on a FRESH client, as a list of plain dicts
    reattach()       an adapter on the restarted server, for the write session (untimed)
    write(cycle)     WRITE_N single-record writes, each committed
    verify(cycle)    True when the batch written in `cycle` reads back
    ping_desc        what the liveness call is, for the row
    """
    model = "?"
    ping_desc = "?"
    adapter = None
    version = "?"
    durability = None

    def __init__(self, backend, scale):
        self.backend, self.scale = backend, scale


def _http_ok(url, auth=None, ok=(200, 204)):
    import requests
    r = requests.get(url, auth=auth, timeout=2)
    if r.status_code not in ok:
        raise RuntimeError(f"{url}: HTTP {r.status_code}")
    return r


class Docs(Engine):
    """TPC-H line items and parts through l1_tpc; the fixed read is one part's
    retail price by its key, which every engine stores and indexes."""
    model = "docs"

    def build(self):
        if self.scale in TPC_SF:
            os.environ["BENCH_TPC_SF"] = TPC_SF[self.scale]
        import l1_tpc as L
        self.L = L
        li, part = L.load_lineitems(), L.load_part()
        a = L.BACKENDS[self.backend]()
        a.connect()
        t0 = time.perf_counter()
        a.build(li, part)
        build_s = time.perf_counter() - t0
        mid = len(part) // 2
        self.key = int(part["p_partkey"].iloc[mid])
        self.want_price = round(float(part["p_retailprice"].iloc[mid]), 2)
        self.adapter, self.version = a, a.version
        self.durability = getattr(a, "durability", None)
        return {"n_lineitem": len(li), "n_part": len(part), "tpch_sf": L.SF,
                "restart_load_s": round(build_s, 2), "restart_read_key": self.key}

    # -- fresh-client probes, one per engine
    def ping(self):
        be = self.backend
        if be == "arcadedb_server":
            _http_ok(f"http://{HOST}:2480/api/v1/ready")
        elif be == "surrealdb_tpc_server":
            from surrealdb import Surreal
            c = Surreal(f"ws://{HOST}:8000/rpc")
            try:
                c.version()
            finally:
                c.close()
        elif be == "postgres":
            import psycopg
            with psycopg.connect(f"host={HOST} dbname=bench user=postgres password=dbbenchpass",
                                 connect_timeout=2, autocommit=True) as cx:
                cx.execute("SELECT 1").fetchone()
        elif be == "arangodb_tpc":
            import arango_common
            _http_ok(f"http://{HOST}:8529/_api/version", auth=("root", arango_common.PASSWORD))
        elif be == "mongodb":
            import pymongo
            cl = pymongo.MongoClient(f"mongodb://{HOST}:27017/?directConnection=true",
                                     serverSelectionTimeoutMS=1000, connectTimeoutMS=1000)
            try:
                cl.admin.command("ping")
            finally:
                cl.close()

    @property
    def ping_desc(self):
        return {"arcadedb_server": "GET /api/v1/ready", "surrealdb_tpc_server": "ws connect + version",
                "postgres": "connect + SELECT 1", "arangodb_tpc": "GET /_api/version",
                "mongodb": "connect + ping"}[self.backend]

    def read(self):
        be, k = self.backend, self.key
        if be == "arcadedb_server":
            import requests
            r = requests.post(f"http://{HOST}:2480/api/v1/query/bench", auth=("root", "dbbenchpass"),
                              json={"language": "sql", "params": {"k": k},
                                    "command": "SELECT p_retailprice FROM Part WHERE p_partkey = :k"},
                              timeout=30)
            r.raise_for_status()
            vals = [x.get("p_retailprice") for x in r.json().get("result", [])]
        elif be == "surrealdb_tpc_server":
            from surrealdb import Surreal
            c = Surreal(f"ws://{HOST}:8000/rpc")
            try:
                c.signin({"username": "root", "password": "root"})
                c.use("bench", "bench")
                res = c.query(f"SELECT p_retailprice FROM ONLY part:{int(k)}")
            finally:
                c.close()
            if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
                res = res[-1]["result"]
            res = res if isinstance(res, list) else ([res] if res else [])
            vals = [x.get("p_retailprice") for x in res if isinstance(x, dict)]
        elif be == "postgres":
            import psycopg
            with psycopg.connect(f"host={HOST} dbname=bench user=postgres password=dbbenchpass",
                                 connect_timeout=2, autocommit=True) as cx:
                vals = [r[0] for r in cx.execute(
                    "SELECT p_retailprice FROM part WHERE p_partkey = %s", (k,)).fetchall()]
        elif be == "arangodb_tpc":
            import requests
            import arango_common
            r = requests.post(f"http://{HOST}:8529/_db/{arango_common.DB}/_api/cursor",
                              auth=("root", arango_common.PASSWORD), timeout=30,
                              json={"query": "FOR p IN part FILTER p._key == @k RETURN p.p_retailprice",
                                    "bindVars": {"k": str(k)}})
            r.raise_for_status()
            vals = r.json().get("result", [])
        elif be == "mongodb":
            import pymongo
            cl = pymongo.MongoClient(f"mongodb://{HOST}:27017/?directConnection=true",
                                     serverSelectionTimeoutMS=1000, connectTimeoutMS=1000)
            try:
                d = cl["bench"]["part"].find_one({"p_partkey": k}, {"_id": 0, "p_retailprice": 1})
            finally:
                cl.close()
            vals = [d["p_retailprice"]] if d else []
        return [{"price": round(float(v), 2)} for v in vals if v is not None]

    def expected(self):
        return [{"price": self.want_price}]

    def reattach(self):
        be, L = self.backend, self.L
        a = L.BACKENDS[be]()
        if be == "surrealdb_tpc_server":
            a._open()                       # connect() would REMOVE every table
        elif be == "arangodb_tpc":
            import arango_common
            a.cl, a.db, a.version = arango_common.connect(fresh=False)   # fresh=True drops the database
        else:
            a.connect()
        if be == "mongodb":
            a._crud = a.db.get_collection("crud", write_concern=a._wc)
        self.adapter = a

    def _keys(self, cycle):
        base = 50_000_000 + cycle * WRITE_N
        return range(base, base + WRITE_N)

    def write(self, cycle):
        for i in self._keys(cycle):
            self.adapter.crud_insert(i, self.key)

    def verify(self, cycle):
        last = list(self._keys(cycle))[-1]
        return bool(self.adapter.crud_read(last))


class Graph(Engine):
    """LDBC SNB persons and friendships (sf1, sf10) through l2_graph; the fixed
    read is the interactive table's point read of one person."""
    model = "graph"

    def build(self):
        if self.scale in LDBC_SCALES:
            os.environ["BENCH_GRAPH_SOURCE"] = "ldbc"
        import l2_graph as G
        import graph_common as GC
        self.G, self.GC = G, GC
        n = G.SCALE_PERSONS[self.scale]
        if G._GRAPH_SOURCE == "ldbc":
            import ldbc_snb as LD
            G.gen_persons = lambda _n: LD.gen_persons(self.scale)
            G.gen_edges = lambda _n: LD.gen_edges(self.scale)
            self.pid = LD.pick_query_ids(self.scale, 1)[0]
            self.id_base = LD.write_id_base(self.scale)
        else:
            self.pid = G.pick_query_ids(n, 1)[0]
            self.id_base = 10_000_000
        ad = G.ADAPTERS[self.backend]()
        ad._scale = self.scale
        ad.connect()
        t0 = time.perf_counter()
        ad.build(n)
        ad.post_build("oltp")
        build_s = time.perf_counter() - t0
        self.adapter, self.version = ad, ad.version
        self.durability = getattr(ad, "durability", None) or G.DURABILITY.get(self.backend)
        self.want = self._norm(ad.run_read("point", self.pid))
        return {"n_persons": n, "graph_source": G._GRAPH_SOURCE, "restart_load_s": round(build_s, 2),
                "restart_read_key": int(self.pid)}

    @staticmethod
    def _norm(rows):
        return [{"name": r.get("name"), "age": int(r["age"]) if r.get("age") is not None else None}
                for r in rows]

    def _bolt(self):
        import neo4j
        auth = ("neo4j", "dbbenchpass") if self.backend == "neo4j_graph" else None
        return neo4j.GraphDatabase.driver(f"bolt://{HOST}:7687", auth=auth,
                                          connection_timeout=2.0, max_connection_pool_size=1)

    def _falkor(self):
        import falkordb
        return falkordb.FalkorDB(host=HOST, port=6379, socket_timeout=10, socket_connect_timeout=2)

    def ping(self):
        if self.backend == "arcadedb_graph_server":
            _http_ok(f"http://{HOST}:2480/api/v1/ready")
        elif self.backend == "falkordb_graph":
            db = self._falkor()
            try:
                db.connection.ping()
            finally:
                db.connection.close()
        else:
            d = self._bolt()
            try:
                d.verify_connectivity()
            finally:
                d.close()

    @property
    def ping_desc(self):
        return {"arcadedb_graph_server": ARCADE_READY, "falkordb_graph": "PING"}.get(
            self.backend, "Bolt verify_connectivity")

    def read(self):
        text = self.GC.OLTP_READS["point"]
        if self.backend == "arcadedb_graph_server":
            rows = _arcade_query("cypher", text, {"id": int(self.pid)})
        elif self.backend == "falkordb_graph":
            db = self._falkor()
            try:
                res = db.select_graph("bench").ro_query(text, {"id": int(self.pid)})
                cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
                rows = [dict(zip(cols, r)) for r in res.result_set]
            finally:
                db.connection.close()
        else:
            d = self._bolt()
            try:
                with d.session() as s:
                    rows = s.run(text, {"id": int(self.pid)}).data()
            finally:
                d.close()
        return self._norm(rows)

    def expected(self):
        return self.want

    def reattach(self):
        ad = self.G.ADAPTERS[self.backend]()
        ad._scale = self.scale
        if self.backend == "arcadedb_graph_server":
            import lean_http
            ad.rq = lean_http.Session()        # connect() would issue the schema DDL again
            ad.rq.auth = ("root", "dbbenchpass")
            ad.row_extra = {**(getattr(ad, "row_extra", None) or {}), **lean_http.row_fields(ad.rq)}
            ad.base = f"http://{HOST}:2480/api/v1"
        elif self.backend == "falkordb_graph":
            import falkordb
            ad.db = falkordb.FalkorDB(host=HOST, port=6379)
            ad.conn = ad.db.connection
            ad.g = ad.db.select_graph("bench")
        else:
            import neo4j
            auth = ("neo4j", "dbbenchpass") if self.backend == "neo4j_graph" else None
            ad.driver = neo4j.GraphDatabase.driver(f"bolt://{HOST}:7687", auth=auth)
        self.adapter = ad

    def _ids(self, cycle):
        base = self.id_base + 500_000 + cycle * WRITE_N
        return range(base, base + WRITE_N)

    def write(self, cycle):
        for nid in self._ids(cycle):
            self.adapter.run_write(self.pid, nid)

    def verify(self, cycle):
        last = list(self._ids(cycle))[-1]
        return len(self.adapter.run_read("point", last)) == 1


class Dense(Engine):
    """SIFT vectors through l3d_dense; the fixed read is the top 10 of the first
    query, which must equal this engine's own top 10 before the stop (an
    approximate index: engines are not expected to agree with each other)."""
    model = "dense"

    def build(self):
        if self.scale in DENSE_DATA:
            os.environ["BENCH_DENSE_DATA"] = DENSE_DATA[self.scale]
        import l3d_dense as D
        self.D = D
        train, test, gt = D.load_dataset(self.scale)
        self.train, self.q0, self.gt0 = train, test[0], [int(x) for x in gt[0][:10]]
        a = D.BACKENDS[self.backend]()
        a.connect()
        t0 = time.perf_counter()
        a.build(train)
        a.post_build()
        build_s = time.perf_counter() - t0
        self.adapter, self.version = a, a.version
        self.durability = getattr(a, "durability", None) or D.DURABILITY.get(
            self.backend, DURABILITY_VECTOR_DEFAULT)
        self.want = self.read()
        return {"n_docs": len(train), "restart_load_s": round(build_s, 2),
                "restart_read_recall_at_10": len(set(self.want[0]["ids"]) & set(self.gt0)) / 10.0}

    def ping(self):
        be = self.backend
        if be == "arcadedb_dense_server":
            _http_ok(f"http://{HOST}:2480/api/v1/ready")
        elif be == "qdrant_dense":
            _http_ok(f"http://{HOST}:6333/readyz")
        elif be == "milvus_dense":
            _http_ok(f"http://{HOST}:9091/healthz")
        elif be == "elasticsearch_dense":
            _http_ok(f"http://{HOST}:9200/")
        elif be == "mongodb_dense":
            import pymongo
            import mongo_common
            cl = pymongo.MongoClient(mongo_common.uri(True), serverSelectionTimeoutMS=1000,
                                     connectTimeoutMS=1000)
            try:
                cl.admin.command("ping")
            finally:
                cl.close()

    @property
    def ping_desc(self):
        return {"arcadedb_dense_server": ARCADE_READY, "qdrant_dense": "GET /readyz",
                "milvus_dense": "GET :9091/healthz",
                "elasticsearch_dense": "GET /", "mongodb_dense": "connect + ping"}[self.backend]

    def _fresh(self):
        be, D = self.backend, self.D
        b = D.BACKENDS[be]()
        if be == "mongodb_dense":
            import pymongo
            import mongo_common
            b.cl = pymongo.MongoClient(mongo_common.uri(True), serverSelectionTimeoutMS=2000)
            b.db = b.cl[mongo_common.DB]
            b.coll = b.db["articles"]
        else:
            b.connect()
        if be == "milvus_dense":
            # After a restart Milvus serves a collection only once it is loaded
            # again; the client asking for it is the documented step, and it
            # returns at once when the server has already reloaded it.
            b.cl.load_collection("articles")
        return b

    def read(self):
        b = self._fresh()
        try:
            ids = [int(x) for x in b.search(self.q0, 10)]
        finally:
            try:
                if self.backend == "mongodb_dense":
                    b.cl.close()
            except Exception:  # noqa: BLE001
                pass
        return [{"ids": ids}]

    def expected(self):
        return self.want

    def reattach(self):
        self.adapter = self._fresh()

    def _ids(self, cycle):
        base = 900_000_000 + cycle * WRITE_N
        return list(range(base, base + WRITE_N))

    def _vecs(self, cycle):
        # FAR FROM EVERYTHING, so the batch cannot change the fixed read's
        # answer: copies of corpus vectors would tie with their originals and
        # move the first query's top 10 (an Elasticsearch smoke waited out its
        # whole deadline on exactly that). Each is a corpus vector shifted a
        # long way along every axis, a distinct offset per cycle.
        shift = 10_000.0 * (cycle + 1)
        return [self.train[j % len(self.train)] - shift for j in range(WRITE_N)]

    def write(self, cycle):
        self.adapter.insert_vectors(self._ids(cycle), self._vecs(cycle))

    def verify(self, cycle):
        ids, vecs = self._ids(cycle), self._vecs(cycle)
        got = [int(x) for x in self.adapter.search(vecs[-1], 10)]
        return ids[-1] in got


class TimeSeries(Engine):
    """TSBS cpu points through l4_tsbs; the fixed read is one host's point count."""
    model = "ts"

    def build(self):
        import l4_tsbs as T
        self.T = T
        pts = T.parse_lp(T.lp_path(self.scale))
        self.host0 = pts[0][0]
        self.want_n = sum(1 for p in pts if p[0] == self.host0)
        self.ts_base = max(p[1] for p in pts) + 3600
        b = T.BACKENDS[self.backend]()
        b.connect()
        t0 = time.perf_counter()
        b.ingest(pts)
        if hasattr(b, "settle"):
            b.settle()
        build_s = time.perf_counter() - t0
        self.adapter = b
        self.version = b.version() if callable(getattr(b, "version", None)) else getattr(b, "version", "?")
        self.durability = getattr(b, "durability", None) or T.DURABILITY.get(self.backend)
        return {"n_points": len(pts), "restart_load_s": round(build_s, 2)}

    def _cx(self):
        import psycopg
        return psycopg.connect(f"host={HOST} port=8812 dbname=qdb user=admin password=quest",
                               connect_timeout=2, autocommit=True)

    def ping(self):
        if self.backend == "arcadedb_ts_native_server":
            _http_ok(f"http://{HOST}:2480/api/v1/ready")
        else:
            with self._cx() as cx:
                cx.execute("SELECT 1").fetchone()

    @property
    def ping_desc(self):
        return ARCADE_READY if self.backend == "arcadedb_ts_native_server" else "PostgreSQL wire connect + SELECT 1"

    def _count(self, host):
        if self.backend == "arcadedb_ts_native_server":
            r = _arcade_query("sql", "SELECT count(*) AS n FROM Point WHERE host = :h", {"h": host})
            return int(r[0]["n"]) if r else 0
        with self._cx() as cx:
            return int(cx.execute("SELECT count() FROM p WHERE host = %s", (host,)).fetchone()[0])

    def read(self):
        return [{"n": self._count(self.host0)}]

    def expected(self):
        return [{"n": self.want_n}]

    def reattach(self):
        b = self.T.BACKENDS[self.backend]()
        b.connect()
        self.adapter = b

    def write(self, cycle):
        h = f"rs_{cycle}"
        t0 = self.ts_base + cycle * WRITE_N
        if self.backend == "arcadedb_ts_native_server":
            # The server's own time-series endpoint, the lane's ingest path; one
            # request, committed when it returns.
            import requests
            body = "\n".join(f"Point,host={h} uu=1,us=1,ui=1 {t0 + j}" for j in range(WRITE_N))
            r = requests.post(f"http://{HOST}:2480/api/v1/ts/bench/write?precision=s",
                              auth=("root", "dbbenchpass"), data=body,
                              headers={"Content-Type": "text/plain"}, timeout=600)
            r.raise_for_status()
        else:
            import socket
            lines = [f"p,host={h} uu=1,us=1,ui=1 {(t0 + j) * 1_000_000_000}" for j in range(WRITE_N)]
            sk = socket.create_connection((HOST, 9009))
            sk.sendall(("\n".join(lines) + "\n").encode())
            sk.close()
        # COMMITTED, not merely sent: QuestDB applies line protocol through its
        # WAL asynchronously, and a stop timed before the batch is applied would
        # be timing the apply. Untimed, and the same wait for both engines.
        deadline = time.time() + 300
        while self._count(h) < WRITE_N and time.time() < deadline:
            time.sleep(0.2)

    def verify(self, cycle):
        return self._count(f"rs_{cycle}") == WRITE_N


ENGINES = {"docs": Docs, "graph": Graph, "dense": Dense, "ts": TimeSeries}


# ------------------------------------------------------------------ protocol
class NoAnswer(RuntimeError):
    pass


def stop_server(srv):
    t0 = time.perf_counter()
    docker_api.stop(srv, GRACE_S)
    dt = time.perf_counter() - t0
    state = docker_api.inspect(srv)["State"]
    code, oom = state.get("ExitCode"), bool(state.get("OOMKilled"))
    # 137 = SIGKILL. With OOMKilled false and the grace used up, docker killed
    # an engine that did not stop on its own: the stop was not clean.
    killed = code == 137 and not oom and dt >= GRACE_S - 1
    return dt, code, oom, killed


def restart_server(srv, eng):
    """(start_s, first_query_s, total_s, tries) after `docker start`."""
    t0 = time.perf_counter()
    docker_api.start(srv)
    deadline = t0 + START_TIMEOUT_S
    pings = 0
    last = None
    while True:
        try:
            eng.ping()
            break
        except Exception as e:  # noqa: BLE001 - every failure before the deadline is "not yet"
            last = e
            pings += 1
        if time.perf_counter() > deadline:
            raise NoAnswer(f"no liveness within {START_TIMEOUT_S:.0f} s: {type(last).__name__}: {str(last)[:200]}")
        time.sleep(POLL_S)
    t_up = time.perf_counter()
    reads, want, got = 0, eng.expected(), None
    while True:
        try:
            got = eng.read()
            if got == want:
                break
            last = f"answered {str(got)[:200]}, want {str(want)[:200]}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:200]}"
        reads += 1
        if time.perf_counter() > deadline:
            raise NoAnswer(f"no right answer within {START_TIMEOUT_S:.0f} s: {last}")
        time.sleep(POLL_S)
    t_ans = time.perf_counter()
    return t_up - t0, t_ans - t_up, t_ans - t0, pings, reads


# ------------------------------------------------------------------ the shutdown trace
TRACE_IMAGE = "alpine:3"
TRACE_SYSCALLS = "fsync,fdatasync,sync_file_range,msync,syncfs,sync"


def trace_start(srv):
    """A sidecar in the server's PID namespace tracing every process's sync
    calls, line by line to its own file (it dies with the namespace when the
    server's PID 1 exits, so a summary written at the end would never be
    written). Laptop only (BENCH_RS_TRACE=1): it installs strace from the
    network, and a campaign cell must not."""
    name = f"rstrace-{srv}"[:60]
    docker_api.remove(name)
    script = ("apk add -q strace >/dev/null 2>&1 || exit 3; "
              "args=''; for p in $(ls /proc | grep -E '^[0-9]+$'); do "
              "[ \"$p\" = \"$$\" ] && continue; c=$(cat /proc/$p/comm 2>/dev/null) || continue; "
              "case \"$c\" in sh|ls|grep|cat|apk) continue;; esac; args=\"$args -p $p\"; done; "
              f"exec strace -f -T -tt -e trace={TRACE_SYSCALLS} $args -o /tmp/trace.txt")
    docker_api.create_and_start({"Image": TRACE_IMAGE, "Cmd": ["sh", "-c", script],
                                 "HostConfig": {"PidMode": f"container:{srv}",
                                                "CapAdd": ["SYS_PTRACE"]}}, name)
    time.sleep(8)          # apk add and the attach
    return name


def trace_read(name):
    """(sync calls, seconds inside them, by syscall) from the sidecar's file."""
    try:
        _, raw = docker_api.call("GET", f"/containers/{name}/archive?path=/tmp/trace.txt", timeout=60)
        tf = tarfile.open(fileobj=io.BytesIO(raw))
        text = tf.extractfile(tf.getmembers()[0]).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return {"trace_error": f"{type(e).__name__}: {e}"}
    finally:
        docker_api.remove(name)
    calls, secs, by = 0, 0.0, {}
    for line in text.splitlines():
        for sc in TRACE_SYSCALLS.split(","):
            if f" {sc}(" in line or line.split(" ", 2)[-1].startswith(f"{sc}("):
                calls += 1
                by[sc] = by.get(sc, 0) + 1
                if line.rstrip().endswith(">") and "<" in line:
                    try:
                        secs += float(line.rsplit("<", 1)[1].rstrip(">"))
                    except ValueError:
                        pass
                break
    return {"shutdown_sync_calls": calls, "shutdown_sync_s": round(secs, 4),
            "shutdown_sync_by_call": json.dumps(by, sort_keys=True)}


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=sorted(MODEL))
    ap.add_argument("--workload", default="restart", choices=["restart"])
    ap.add_argument("--scale", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    model = MODEL[args.backend]
    if args.scale not in MODEL_SCALES[model]:
        raise SystemExit(f"l6_restart: {args.backend} runs the {model} model, whose tiers are "
                         f"{sorted(MODEL_SCALES[model])}; {args.scale!r} is another model's "
                         f"tier and would measure the wrong data under its name")
    srv = HOST   # the runner names the server container what it gives as the host
    _beat = bench_common.PhaseBeat()
    eng = ENGINES[model](args.backend, args.scale)
    out = bench_common.run_conditions(lane="restart", role="client")
    out.update({"backend": args.backend, "workload": "restart", "scale": args.scale,
                "restart_model": model, "restart_iters": ITERS, "restart_warmup": WARMUP,
                "restart_write_n": WRITE_N, "restart_poll_s": POLL_S, "stop_grace_s": GRACE_S})
    with _beat.phase("build", backend=args.backend, scale=args.scale):
        out.update(eng.build())
    # The override settings the model's adapter read back from its engine
    # (overrides.py, CAMPAIGN section 7 row 21). The dense and graph models
    # build through the same adapters as their tables, so they carry the same
    # stamps; only the registered fields are taken, because the adapters stamp
    # a good deal more that this lane has no table for.
    import overrides as _ov
    _ad = getattr(eng, "adapter", None)
    _rx = dict(getattr(_ad, "row_extra", None) or {})
    if hasattr(_ad, "readbacks"):
        _rx.update(_ad.readbacks())     # the dense adapters' hook, after their build timer
    out.update({k: v for k, v in _rx.items() if k in _ov.STAMP_FIELDS})
    out["engine_version"] = eng.version
    bench_common.stamp_durability(out, eng.durability)
    out["instrument"] = bench_common.INSTRUMENT
    out["restart_ping"] = eng.ping_desc
    info = docker_api.inspect(srv)
    out["stop_signal"] = (info.get("Config") or {}).get("StopSignal") or "SIGTERM"
    out["restart_page_cache"] = "warm: the same host, nothing evicted"

    want = eng.expected()
    first = eng.read()
    if first != want:
        raise SystemExit(f"l6_restart: before any stop the fixed read answered {first!r}, "
                         f"want {want!r}; the load is wrong, not the restart")
    if model == "dense":
        bench_common.record_result(out, "restart_knn",
                                   [{"rank": r, "id": i} for r, i in enumerate(want[0]["ids"])],
                                   columns=["rank", "id"], order_matters=True, order_key="rank")
    else:
        bench_common.record_result(out, "restart_read", want)

    cols = {k: [] for k in ("shutdown_idle_s", "shutdown_write_s", "restart_start_s",
                            "restart_first_query_s", "restart_total_s", "restart_after_write_s",
                            "write_batch_s")}
    exit_codes, killed_any, oom_any = [], False, False
    visible = []
    tries = []
    for c in range(WARMUP + ITERS):
        measured = c >= WARMUP
        with _beat.phase("stop-idle", cycle=c):
            sd, code, oom, killed = stop_server(srv)
        exit_codes.append(code)
        killed_any |= killed
        oom_any |= oom
        if c == 0:
            out["shutdown_after_load_s"] = round(sd, 3)
        with _beat.phase("restart", cycle=c):
            up, fq, tot, pings, reads = restart_server(srv, eng)
        tries.append((pings, reads))
        eng.reattach()
        t0 = time.perf_counter()
        with _beat.phase("write", cycle=c, n=WRITE_N):
            eng.write(c)
        wb = time.perf_counter() - t0
        tr = trace_start(srv) if (TRACE and c == WARMUP) else None
        with _beat.phase("stop-write", cycle=c):
            sdw, code2, oom2, killed2 = stop_server(srv)
        if tr:
            out.update(trace_read(tr))
        exit_codes.append(code2)
        killed_any |= killed2
        oom_any |= oom2
        with _beat.phase("restart-after-write", cycle=c):
            _, _, tot2, _, _ = restart_server(srv, eng)
        eng.reattach()
        # THE BATCH MUST COME BACK, and may take a moment to: an engine whose
        # index is a second process (mongot) answers the fixed read from the
        # data it had indexed before the stop while it catches up on the rest.
        # Polled to a bound, and the wait is recorded; a batch that never
        # reappears is a lost write and fails the cell.
        t_v = time.perf_counter()
        while True:
            try:
                ok = eng.verify(c)
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                break
            if time.perf_counter() - t_v > VERIFY_S:
                raise SystemExit(f"l6_restart: cycle {c}'s {WRITE_N} committed writes were not back "
                                 f"{VERIFY_S:.0f} s after a clean stop and restart")
            time.sleep(0.2)
        visible.append(round(time.perf_counter() - t_v, 3))
        if measured:
            for k, v in (("shutdown_idle_s", sd), ("shutdown_write_s", sdw), ("restart_start_s", up),
                         ("restart_first_query_s", fq), ("restart_total_s", tot),
                         ("restart_after_write_s", tot2), ("write_batch_s", wb)):
                cols[k].append(v)
    for k, vs in cols.items():
        out[k] = round(st.median(vs), 4) if vs else None
        out[f"{k}_all"] = [round(v, 4) for v in vs]
    out["stop_exit_codes"] = sorted(set(exit_codes))
    out["stop_killed_after_grace"] = killed_any
    out["stop_oom_killed"] = oom_any
    out["restart_tries"] = tries
    # The batch read back after every write stop is the lane's correctness
    # check on the restart itself (raised above if any batch was lost).
    out["restart_writes_survived"] = True
    out["restart_writes_visible_s"] = max(visible) if visible else None
    out["restart_writes_visible_s_all"] = visible
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    sys.exit(main())
