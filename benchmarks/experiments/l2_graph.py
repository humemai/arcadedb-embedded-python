#!/usr/bin/env python3
"""L2 graph lane: ArcadeDB (embedded + server) vs Neo4j, LadybugDB, SurrealDB,
ArangoDB, Memgraph, FalkorDB and DuckDB with DuckPGQ.

The shared LDBC questions in each engine's own dialect over one social graph
(graph_common; the LDBC-SNB projection under BENCH_GRAPH_SOURCE=ldbc). Two
workloads: oltp (indexed point/1-hop/2-hop reads + create-and-link writes,
latency percentiles) and olap (three full-graph aggregations; ArcadeDB runs
them against a Graph Analytical View, its documented OLAP mode). Ingest uses
each engine's native bulk path. At the sf1full tier the olap workload loads the
message half of the full SF1 network on top of persons+KNOWS (DECISIONS #103b);
the questions are the same, the corpus under them is not.
"""
import argparse
import json
import os
import statistics
import sys
import time
import surreal_common
import arango_common

from graph_common import (OLAP_ITERATIONS, OLAP_QUERIES, OLTP_READS,
                          OLTP_WRITE, SCALE_OLTP_QUERIES, SCALE_PERSONS,
                          gen_edges, gen_persons, pick_query_ids)

# Data-source switch (same pattern as l3_sparse/bigann): BENCH_GRAPH_SOURCE=ldbc
# swaps the synthetic generator for the LDBC-SNB persons+KNOWS projection.
# The generators are rebound to scale-aware wrappers in main() once the scale
# is known; templates/tunables stay identical so runs differ only in data.
_GRAPH_SOURCE = os.environ.get("BENCH_GRAPH_SOURCE", "synthetic")
if _GRAPH_SOURCE == "ldbc":
    import ldbc_snb as _ldbc
    SCALE_PERSONS = _ldbc.SCALE_PERSONS
    SCALE_OLTP_QUERIES = _ldbc.SCALE_OLTP_QUERIES

# The analytics message-half caps for a laptop smoke: 0 = the whole network.
# Read here only to stamp them onto the row; the loader (ldbc_snb) reads them.
_MSG_LIMIT = int(os.environ.get("BENCH_GRAPH_MSG_LIMIT") or 0)
_PERSON_LIMIT = int(os.environ.get("BENCH_GRAPH_PERSON_LIMIT") or 0)

INGEST_BATCH = 5_000
GAV_NAME = "l2gav"
GAV_TIMEOUT_S = 3600


class Base:
    name = "base"
    version = "?"

    def connect(self):
        raise NotImplementedError

    def build(self, n_persons):
        raise NotImplementedError

    def build_messages(self):
        """Load the FULL-network message half for the analytics workload only
        (DECISIONS #103b). Called after build() at a full-network tier
        (ldbc_snb.loads_messages) with the olap workload; self._scale names the
        tier. Each engine consumes the shared ldbc_snb.MessageCorpus spec
        (vertex_spec / edge_spec) through its own bulk path and records
        self.msg_counts. The default refuses so an engine missing the loader
        is obvious rather than silently measured on the projection under the
        full network's label."""
        raise NotImplementedError(f"{self.name} has no message-half loader")

    def post_build(self, workload):
        """Engine's documented settle step; counted inside build time."""

    def reopen(self):
        """Open an ALREADY-BUILT database, with no DDL and no ingest.

        Separate from connect(), which creates the database and issues the
        schema: calling that twice fails, and if it did not it would time
        creation rather than opening. Reopening is the quantity a build/query
        phase split introduces and that nothing here measures today (#154).
        Adapters with no reopen path leave this alone and the probe records
        the reason rather than a number it did not get.
        """
        raise NotImplementedError(f"{self.name} has no reopen path")

    def run_cypher(self, text):
        """Execute one cypher statement, return row count (results consumed)."""
        raise NotImplementedError

    def run_cypher_write(self, text):
        self.run_cypher(text)

    # NAME-BASED HOOKS (2026-09-11): the loops call these, and the defaults
    # format the shared Cypher text, so an engine without Cypher (SurrealDB)
    # can answer the same question in its own language by overriding three
    # methods while the mix, counts and statistics stay identical.
    def run_read(self, op, pid):
        return self.run_cypher(OLTP_READS[op].format(id=pid))

    def run_write(self, pid, new_id):
        self.run_cypher_write(OLTP_WRITE.format(id=pid, new_id=new_id))

    def run_olap(self, qname):
        return self.run_cypher(OLAP_QUERIES[qname])

    def close(self):
        pass


# --------------------------------------------------------------- ArcadeDB
class ArcadeGraphEmbedded(Base):
    name = "arcadedb_graph_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # -Xms pinned to -Xmx for parity with the server deployment
        self.db = arcadedb.create_database(
            "/tmp/l2_arcade",
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
        self.version = arcadedb.__version__
        for ddl in ["CREATE VERTEX TYPE Person",
                    "CREATE PROPERTY Person.id LONG",
                    "CREATE PROPERTY Person.name STRING",
                    "CREATE PROPERTY Person.age INTEGER",
                    "CREATE PROPERTY Person.city STRING",
                    "CREATE INDEX ON Person (id) UNIQUE",
                    "CREATE EDGE TYPE KNOWS",
                    "CREATE PROPERTY KNOWS.since INTEGER"]:
            self.db.command("sql", ddl)

    def reopen(self):
        """Open the built database again: no create, no DDL, no ingest.

        IN-PROCESS CAVEAT that decides how the number may be read: the JVM is
        already up, so heap_size is inert here and what is timed is the engine
        opening its files, not a JVM start. A phase split implemented as a
        container restart pays the JVM start too, and that cost lands on every
        JVM engine and on none of the others, so it has to be measured
        separately rather than folded in.
        """
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.open_database(
            "/tmp/l2_arcade",
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})

    def build(self, n_persons):
        # Native Java API with batched commits — ArcadeDB's embedded bulk path
        jdb = self.db.get_java_database()
        verts = {}  # keyed by person id (sparse longs under the LDBC source)
        jdb.begin()
        n = 0
        for i, name, age, city in gen_persons(n_persons):
            v = jdb.newVertex("Person")
            v.set("id", i)
            v.set("name", name)
            v.set("age", age)
            v.set("city", city)
            v.save()
            verts[i] = v
            n += 1
            if n % INGEST_BATCH == 0:
                jdb.commit()
                jdb.begin()
        jdb.commit()
        jdb.begin()
        n = 0
        for src, dst, since in gen_edges(n_persons):
            verts[src].newEdge("KNOWS", verts[dst], "since", since)
            n += 1
            if n % INGEST_BATCH == 0:
                jdb.commit()
                jdb.begin()
        jdb.commit()

    # MESSAGE-HALF SCHEMA, shared by both ArcadeDB arms. Message is an abstract
    # supertype and Post/Comment EXTEND it, so `MATCH (m:Message)` reaches both.
    # Vertices carry only `id`; the analytics questions never read a message
    # property. The Graph Analytical View stays over Person and KNOWS: the
    # three questions traverse nothing else.
    MSG_EDGE_TYPES = ("IS_LOCATED_IN", "IS_PART_OF", "HAS_MEMBER", "CONTAINER_OF",
                      "REPLY_OF", "HAS_TAG", "HAS_TYPE", "HAS_CREATOR", "LIKES",
                      "HAS_INTEREST")

    def _msg_schema_ddl(self):
        ddl = ["CREATE VERTEX TYPE Message"]
        for label in _ldbc.MSG_VERTEX_LABELS:
            if label in _ldbc.MSG_MESSAGE_SUBLABELS:
                ddl.append(f"CREATE VERTEX TYPE {label} EXTENDS Message")
            else:
                ddl.append(f"CREATE VERTEX TYPE {label}")
            ddl.append(f"CREATE PROPERTY {label}.id LONG")
            ddl.append(f"CREATE INDEX ON {label} (id) UNIQUE")
        for rel in self.MSG_EDGE_TYPES:
            ddl.append(f"CREATE EDGE TYPE {rel}")
        return ddl

    def build_messages(self):
        # Native Java API with index lookups, the same batched-commit path the
        # persons+KNOWS load uses. Person is already loaded with a unique id
        # index (connect()), so its endpoints resolve by lookupByKey too.
        mc = _ldbc.MessageCorpus(self._scale)
        for ddl in self._msg_schema_ddl():
            self.db.command("sql", ddl)
        jdb = self.db.get_java_database()
        vcount = ecount = 0
        jdb.begin()
        n = 0
        for label, ids in mc.vertex_spec():
            for vid in ids:
                v = jdb.newVertex(label)
                v.set("id", vid)
                v.save()
                vcount += 1
                n += 1
                if n % INGEST_BATCH == 0:
                    jdb.commit()
                    jdb.begin()
        jdb.commit()

        def _lookup(label, vid):
            cur = jdb.lookupByKey(label, "id", vid)
            return cur.next().getRecord() if cur.hasNext() else None

        jdb.begin()
        n = 0
        for rel, src_label, dst_label, gen in mc.edge_spec():
            for s, d in gen():
                sv = _lookup(src_label, s)
                dv = _lookup(dst_label, d)
                if sv is None or dv is None:
                    continue          # a capped slice can drop an endpoint
                sv.newEdge(rel, dv)
                ecount += 1
                n += 1
                if n % INGEST_BATCH == 0:
                    jdb.commit()
                    jdb.begin()
        jdb.commit()
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def post_build(self, workload):
        if workload != "olap":
            return
        # BENCH_GAV=0 skips the view, so the analytical queries can be run
        # with and without it. Nothing in the campaign had ever done that: every
        # OLAP cell built a view, so we have no evidence the executor actually
        # uses it. Two things make the question worth asking. The view costs
        # only ~1.5 s to build over SF10 (30.0 s OLAP build against 28.5 s
        # OLTP) for 65k vertices and ~2.5M edges, which is cheap for an
        # analytical projection; and our OLAP latencies sit in Neo4j's
        # traversal band rather than moving toward LadybugDB's columnar one,
        # which is what an effective projection should look like.
        if os.environ.get("BENCH_GAV", "1") == "0":
            self.gav_build_s = 0.0
            return
        # ArcadeDB's documented OLAP mode: build a Graph Analytical View and
        # wait for READY; the executor then uses it for matching traversals.
        # TIMED SEPARATELY: a view that accelerates a query is not free, and
        # the paper cannot claim the speedup without pricing the view.
        _gav_t0 = time.perf_counter()
        self.db.command(
            "sql",
            f"CREATE GRAPH ANALYTICAL VIEW {GAV_NAME} "
            "VERTEX TYPES (Person) EDGE TYPES (KNOWS) "
            "PROPERTIES (id, name, age, city) EDGE PROPERTIES (since) "
            "UPDATE MODE OFF")
        t0 = time.time()
        while time.time() - t0 < GAV_TIMEOUT_S:
            rows = self.db.query(
                "sql", "SELECT FROM schema:graphAnalyticalViews WHERE name = ?",
                GAV_NAME).to_json_list()
            status = rows[0].get("status") if rows else None
            if status == "READY":
                self.gav_build_s = round(time.perf_counter() - _gav_t0, 3)
                return
            if status in ("FAILED", "ERROR"):
                raise RuntimeError(f"GAV build failed: {rows[0]}")
            time.sleep(1)
        raise RuntimeError("GAV not READY within timeout")

    def run_cypher(self, text):
        return len(self.db.query("opencypher", text).to_json_list())

    def run_cypher_write(self, text):
        with self.db.transaction():
            self.db.command("opencypher", text)

    def close(self):
        self.db.close()


class ArcadeGraphServer(ArcadeGraphEmbedded):
    name = "arcadedb_graph_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "dbbenchpass")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        # Ask the server, as l3_sparse and l3d_dense already do. See the same
        # fix in l1_tabular.py: a hardcoded "server:latest" is a tag nobody
        # ran, and it makes every F5 version check on this lane vacuous.
        try:
            info = self.rq.get(f"http://{host}:{port}/api/v1/server", timeout=30)
            self.version = "server:" + (info.json().get("version") or "?")
        except Exception:
            self.version = "server:unknown"
        for ddl in ["CREATE VERTEX TYPE Person",
                    "CREATE PROPERTY Person.id LONG",
                    "CREATE PROPERTY Person.name STRING",
                    "CREATE PROPERTY Person.age INTEGER",
                    "CREATE PROPERTY Person.city STRING",
                    "CREATE INDEX ON Person (id) UNIQUE",
                    "CREATE EDGE TYPE KNOWS",
                    "CREATE PROPERTY KNOWS.since INTEGER"]:
            self._http("command", "sql", ddl)

    def _http(self, endpoint, language, command):
        r = self.rq.post(f"{self.base}/{endpoint}/bench",
                         json={"language": language, "command": command},
                         timeout=3600)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, n_persons):
        # SQL-over-HTTP sqlscript batches — the server's remote bulk surface
        buf = []
        for i, name, age, city in gen_persons(n_persons):
            # literal SQL: escape string payloads (LDBC names contain quotes)
            name_q = name.replace("\\", "\\\\").replace("'", "\\'")
            city_q = city.replace("\\", "\\\\").replace("'", "\\'")
            buf.append(f"CREATE VERTEX Person SET id = {i}, name = '{name_q}', "
                       f"age = {age}, city = '{city_q}'")
            if len(buf) >= INGEST_BATCH:
                self._http("command", "sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._http("command", "sqlscript", ";".join(buf))
        buf = []
        for src, dst, since in gen_edges(n_persons):
            buf.append("CREATE EDGE KNOWS FROM (SELECT FROM Person WHERE id = "
                       f"{src}) TO (SELECT FROM Person WHERE id = {dst}) "
                       f"SET since = {since}")
            if len(buf) >= INGEST_BATCH:
                self._http("command", "sqlscript", ";".join(buf))
                buf = []
        if buf:
            self._http("command", "sqlscript", ";".join(buf))

    def build_messages(self):
        # HTTP sqlscript, the server's remote bulk surface, over the SAME schema
        # the embedded arm builds (_msg_schema_ddl: Message supertype, Post and
        # Comment EXTENDS it, a unique id index on each).
        mc = _ldbc.MessageCorpus(self._scale)
        for ddl in self._msg_schema_ddl():
            self._http("command", "sql", ddl)
        vcount = ecount = 0
        buf = []
        for label, ids in mc.vertex_spec():
            for vid in ids:
                buf.append(f"CREATE VERTEX {label} SET id = {vid}")
                vcount += 1
                if len(buf) >= INGEST_BATCH:
                    self._http("command", "sqlscript", ";".join(buf)); buf = []
        if buf:
            self._http("command", "sqlscript", ";".join(buf)); buf = []
        for rel, src_label, dst_label, gen in mc.edge_spec():
            for s, d in gen():
                buf.append(f"CREATE EDGE {rel} FROM (SELECT FROM {src_label} WHERE id = "
                           f"{s}) TO (SELECT FROM {dst_label} WHERE id = {d})")
                ecount += 1
                if len(buf) >= INGEST_BATCH:
                    self._http("command", "sqlscript", ";".join(buf)); buf = []
        if buf:
            self._http("command", "sqlscript", ";".join(buf))
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def post_build(self, workload):
        if workload != "olap":
            return
        # THE SERVER ARM HONOURS BENCH_GAV TOO. It did not, and that is worse
        # than a missing ablation: main() stamps out["gav"] from the env var
        # regardless, so BENCH_GAV=0 would have written server rows LABELLED
        # gav=False that had a view built anyway. The ablation would then have
        # compared a view against a view and reported the difference as the
        # view's effect. Caught before the ablation ran, not after.
        if os.environ.get("BENCH_GAV", "1") == "0":
            self.gav_build_s = 0.0
            return
        _gav_t0 = time.perf_counter()
        self._http("command", "sql",
                   f"CREATE GRAPH ANALYTICAL VIEW {GAV_NAME} "
                   "VERTEX TYPES (Person) EDGE TYPES (KNOWS) "
                   "PROPERTIES (id, name, age, city) EDGE PROPERTIES (since) "
                   "UPDATE MODE OFF")
        t0 = time.time()
        while time.time() - t0 < GAV_TIMEOUT_S:
            rows = self._http(
                "query", "sql",
                f"SELECT FROM schema:graphAnalyticalViews WHERE name = '{GAV_NAME}'")
            status = rows[0].get("status") if rows else None
            if status == "READY":
                self.gav_build_s = round(time.perf_counter() - _gav_t0, 3)
                return
            if status in ("FAILED", "ERROR"):
                raise RuntimeError(f"GAV build failed: {rows[0]}")
            time.sleep(1)
        raise RuntimeError("GAV not READY within timeout")

    def run_cypher(self, text):
        return len(self._http("query", "cypher", text))

    def run_cypher_write(self, text):
        self._http("command", "cypher", text)

    def close(self):
        pass


# ----------------------------------------------------------------- Neo4j
class Neo4jGraph(Base):
    name = "neo4j_graph"

    def connect(self):
        import neo4j
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "7687")
        self.driver = neo4j.GraphDatabase.driver(
            f"bolt://{host}:{port}", auth=("neo4j", "dbbenchpass"))
        self.driver.verify_connectivity()
        # THE SERVER'S version, not the driver's. This recorded
        # "neo4j-driver:6.2.0" while the server it measured is 5.26.28 -- and
        # e2_hybrid's composed arm asks dbms.components() and gets the server,
        # so one paper reported two different quantities as "the Neo4j
        # version". The driver version is still worth keeping, separately.
        try:
            with self.driver.session() as _s:
                _v = _s.run("CALL dbms.components() YIELD versions "
                            "RETURN versions[0] AS v").single()["v"]
            self.version = f"neo4j:{_v}"
        except Exception as e:
            self.version = f"neo4j:unknown ({e.__class__.__name__})"
        self.driver_version = f"neo4j-driver:{neo4j.__version__}"
        with self.driver.session() as s:
            s.run("CREATE INDEX person_id IF NOT EXISTS "
                  "FOR (p:Person) ON (p.id)").consume()

    def build(self, n_persons):
        # UNWIND batches over bolt — Neo4j's standard client bulk path
        with self.driver.session() as s:
            batch = []
            for i, name, age, city in gen_persons(n_persons):
                batch.append({"id": i, "name": name, "age": age, "city": city})
                if len(batch) >= INGEST_BATCH:
                    s.run("UNWIND $rows AS r CREATE (:Person {id: r.id, "
                          "name: r.name, age: r.age, city: r.city})",
                          rows=batch).consume()
                    batch = []
            if batch:
                s.run("UNWIND $rows AS r CREATE (:Person {id: r.id, "
                      "name: r.name, age: r.age, city: r.city})",
                      rows=batch).consume()
            self._await_indexes(s)
            batch = []
            for src, dst, since in gen_edges(n_persons):
                batch.append({"s": src, "d": dst, "y": since})
                if len(batch) >= INGEST_BATCH:
                    s.run("UNWIND $rows AS r MATCH (a:Person {id: r.s}), "
                          "(b:Person {id: r.d}) "
                          "CREATE (a)-[:KNOWS {since: r.y}]->(b)",
                          rows=batch).consume()
                    batch = []
            if batch:
                s.run("UNWIND $rows AS r MATCH (a:Person {id: r.s}), "
                      "(b:Person {id: r.d}) "
                      "CREATE (a)-[:KNOWS {since: r.y}]->(b)",
                      rows=batch).consume()

    def _await_indexes(self, s):
        """Neo4j populates an index in the background; wait for it before the
        edge load looks persons up by id. A hook, because Memgraph below shares
        this whole load path and builds its index synchronously instead."""
        s.run("CALL db.awaitIndexes()").consume()

    # MESSAGE-HALF loader (DECISIONS #103b), shared with Memgraph (which
    # inherits this whole path and overrides only the index DDL and the await).
    # Message is the SNB supertype of Post and Comment, expressed here as a
    # SECOND LABEL on every such node (`CREATE (n:Post:Message {id: r})`), so
    # `MATCH (m:Message)` reaches both. Vertices carry only `id`.
    def _msg_index_ddl(self, label):
        return f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)"

    def build_messages(self):
        mc = _ldbc.MessageCorpus(self._scale)
        vcount = ecount = 0
        with self.driver.session() as s:
            for label in _ldbc.MSG_VERTEX_LABELS:
                s.run(self._msg_index_ddl(label)).consume()
            self._await_indexes(s)
            for label, ids in mc.vertex_spec():
                extra = ":Message" if label in _ldbc.MSG_MESSAGE_SUBLABELS else ""
                vcount += self._unwind_vertices(s, label, extra, ids)
            self._await_indexes(s)
            for rel, src_label, dst_label, gen in mc.edge_spec():
                ecount += self._unwind_edges(s, rel, src_label, dst_label, gen())
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def _unwind_vertices(self, s, label, extra, ids):
        cy = f"UNWIND $rows AS r CREATE (n:{label}{extra} {{id: r}})"
        batch, n = [], 0
        for vid in ids:
            batch.append(vid)
            if len(batch) >= INGEST_BATCH:
                s.run(cy, rows=batch).consume(); n += len(batch); batch = []
        if batch:
            s.run(cy, rows=batch).consume(); n += len(batch)
        return n

    def _unwind_edges(self, s, rel, src_label, dst_label, pairs):
        cy = (f"UNWIND $rows AS r MATCH (a:{src_label} {{id: r.s}}), "
              f"(b:{dst_label} {{id: r.d}}) CREATE (a)-[:{rel}]->(b)")
        batch, n = [], 0
        for sv, dv in pairs:
            batch.append({"s": sv, "d": dv})
            if len(batch) >= INGEST_BATCH:
                s.run(cy, rows=batch).consume(); n += len(batch); batch = []
        if batch:
            s.run(cy, rows=batch).consume(); n += len(batch)
        return n

    def post_build(self, workload):
        with self.driver.session() as s:
            self._await_indexes(s)

    def run_cypher(self, text):
        with self.driver.session() as s:
            return len(list(s.run(text)))

    def run_cypher_write(self, text):
        with self.driver.session() as s:
            s.run(text).consume()

    def close(self):
        self.driver.close()


class MemgraphGraph(Neo4jGraph):
    """Memgraph 3.13.1 served (2026-09-17): the Neo4j arm's Bolt path, through
    the same neo4j driver, and the lane's Cypher VERBATIM. Every question, the
    write and the ingest statements ran unchanged on the pinned image and
    every answer matched Neo4j's on the micro corpus (laptop probe, 2026-09-17,
    October branch). What differs is the schema statement (`CREATE INDEX ON
    :Person(id)` against Neo4j's `FOR (p:Person) ON (p.id)`), that the index
    is built synchronously so there is nothing to await, and that the server
    takes no auth by default.

    IN MEMORY, BY DESIGN: the documented default storage mode is
    IN_MEMORY_TRANSACTIONAL, which holds the whole graph in RAM with a WAL and
    periodic snapshots on disk for recovery. Measured on the pinned image:
    10,000 persons and 206,713 KNOWS cost 236 MiB of tracked memory, about
    1.1 KiB per object, so SF10 (72,949 persons, about 1.9M edges) needs on
    the order of 2.3 GiB for the graph before query memory, inside the 24g
    the sf10 tier gives a server. Its own limit ignores the cgroup (it
    reported 30.35 GiB inside an 8g container), so runner.py sets
    --memory-limit to 90% of the container cap, which is the engine's own
    rule for the default applied to the cap rather than to the host. The
    full SF1 network (sf1full, 17M objects) is the tier this arm is most
    likely to exceed; the sf1full cap is sized with that in mind.

    DURABILITY, read back from SHOW CONFIG onto the row: storage-wal-enabled
    true and storage-wal-file-flush-every-n-tx 100000 are the image defaults,
    so the WAL is written at commit and fsynced every 100,000 transactions.
    That is this engine's default, which is what every arm on the September
    page runs at (the page's durability note).
    """
    name = "memgraph_graph"

    def connect(self):
        import neo4j
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "7687")
        self.driver = neo4j.GraphDatabase.driver(f"bolt://{host}:{port}", auth=None)
        self.driver.verify_connectivity()
        with self.driver.session() as s:
            v = s.run("SHOW VERSION").single()["version"]
            cfg = {r["name"]: r["current_value"] for r in s.run("SHOW CONFIG")}
        self.version = f"memgraph:{v}"
        self.driver_version = f"neo4j-driver:{neo4j.__version__}"
        # The settings that decide what was measured, from the server itself:
        # the thread pool (FAIRNESS F6), the memory limit, the storage mode,
        # the query timeout the runner disables so the lane's own watchdog is
        # the only censor, and the WAL flush interval (its durability).
        self.row_extra = {
            "driver_version": self.driver_version,
            "memgraph_storage_mode": cfg.get("storage_mode"),
            "memgraph_bolt_workers": _int_or(cfg.get("bolt_num_workers")),
            "memgraph_snapshot_threads": _int_or(cfg.get("storage_snapshot_thread_count")),
            "memgraph_memory_limit_mib": _int_or(cfg.get("memory_limit")),
            "memgraph_query_timeout_s": _int_or(cfg.get("query_execution_timeout_sec")),
            "memgraph_snapshot_interval_s": _int_or(cfg.get("storage_snapshot_interval_sec")),
            "memgraph_wal_enabled": cfg.get("storage_wal_enabled"),
            "memgraph_wal_flush_every_n_tx": _int_or(cfg.get("storage_wal_file_flush_every_n_tx")),
        }
        with self.driver.session() as s:
            s.run("CREATE INDEX ON :Person(id)").consume()

    def _await_indexes(self, s):
        """CREATE INDEX returns once the index is built; Memgraph has no
        db.awaitIndexes() and needs none."""

    def _msg_index_ddl(self, label):
        """Memgraph's label-index syntax, built synchronously (no await), the
        same one-line difference from Neo4j as the Person index in connect()."""
        return f"CREATE INDEX ON :{label}(id)"


def _int_or(v):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return v


class FalkorGraph(Base):
    """FalkorDB 4.20.6 served (2026-09-17): a Redis module, reached through the
    falkordb Python client over the Redis protocol (GRAPH.QUERY), the lane's
    Cypher VERBATIM. Every timed statement ran unchanged on the pinned image
    and every answer matched Neo4j's on the micro corpus (laptop probe,
    2026-09-17, October branch); the only text of its own is the index
    statement, `CREATE INDEX FOR (p:Person) ON (p.id)`, Neo4j's without the
    name. One GRAPH.QUERY call is one transaction, so the write's
    CREATE-and-link is atomic without a session.

    THREE IMAGE DEFAULTS ARE OVERRIDDEN, each recorded on the row, because
    each would have measured something other than the query:
      * FALKORDB_ARGS in the image is "MAX_QUEUED_QUERIES 25 TIMEOUT 1000
        RESULTSET_SIZE 10000": a one-second query timeout and a 10,000-row
        result cap. A whole-graph aggregate can take longer than a second,
        so the image's own default would abort it, and the row cap is the
        ArcadeDB 20,000-row HTTP trap in another engine. The runner sets
        RESULTSET_SIZE -1 and leaves TIMEOUT at the module default of 0, no
        limit, so the lane's watchdog is the only censor.
      * THREAD_COUNT is sized from the HOST's logical cores: the log read
        "Thread pool created, using 16 threads" under a 12-CPU cpuset, while
        its OpenMP pool read 12 (FAIRNESS F6). The runner passes THREAD_COUNT
        from the cpuset and the row records what the server reports.
      * BROWSER=1 starts a Next.js process in the same container; BROWSER=0.

    DURABILITY IS REDIS PERSISTENCE, read back with CONFIG GET onto the row.
    The image default is RDB snapshots only (save "3600 1 300 100 60 10000",
    appendonly no): a write returns with nothing on disk until the next
    snapshot. That is this engine's default, which is what every arm on the
    September page runs at (the page's durability note).
    """
    name = "falkordb_graph"

    def connect(self):
        import falkordb
        import importlib.metadata as _md
        host = os.environ["BENCH_SERVER_HOST"]
        port = int(os.environ.get("BENCH_SERVER_PORT", "6379"))
        self.db = falkordb.FalkorDB(host=host, port=port)
        self.conn = self.db.connection
        self.g = self.db.select_graph("bench")
        info = self.conn.info("server")
        mods = {m.get("name"): m.get("ver") for m in self.conn.module_list()}
        ver = int(mods.get("graph") or 0)
        self.version = (f"falkordb:{ver // 10000}.{(ver // 100) % 100}.{ver % 100} "
                        f"(redis {info.get('redis_version')})")
        self.driver_version = (f"falkordb:{_md.version('falkordb')}, "
                               f"redis:{_md.version('redis')}")
        c = self.conn.config_get("appendonly")
        c.update(self.conn.config_get("appendfsync"))
        c.update(self.conn.config_get("save"))
        self.row_extra = {
            "driver_version": self.driver_version,
            "falkordb_thread_count": _int_or(self._gcfg("THREAD_COUNT")),
            "falkordb_omp_threads": _int_or(self._gcfg("OMP_THREAD_COUNT")),
            "falkordb_resultset_size": _int_or(self._gcfg("RESULTSET_SIZE")),
            "falkordb_timeout_ms": _int_or(self._gcfg("TIMEOUT")),
            "falkordb_timeout_default_ms": _int_or(self._gcfg("TIMEOUT_DEFAULT")),
            "falkordb_timeout_max_ms": _int_or(self._gcfg("TIMEOUT_MAX")),
            "falkordb_appendonly": c.get("appendonly"),
            "falkordb_appendfsync": c.get("appendfsync"),
            "falkordb_save": c.get("save"),
        }
        self.g.query("CREATE INDEX FOR (p:Person) ON (p.id)")

    def _gcfg(self, name):
        """GRAPH.CONFIG GET, which answers [name, value]."""
        v = self.db.config_get(name)
        return v[-1] if isinstance(v, (list, tuple)) else v

    def build(self, n_persons):
        # UNWIND batches, the same statements as Neo4j's; the client carries
        # the parameter list as a CYPHER prefix on the query.
        batch = []
        for i, name, age, city in gen_persons(n_persons):
            batch.append({"id": i, "name": name, "age": age, "city": city})
            if len(batch) >= INGEST_BATCH:
                self.g.query("UNWIND $rows AS r CREATE (:Person {id: r.id, "
                             "name: r.name, age: r.age, city: r.city})", {"rows": batch})
                batch = []
        if batch:
            self.g.query("UNWIND $rows AS r CREATE (:Person {id: r.id, "
                         "name: r.name, age: r.age, city: r.city})", {"rows": batch})
        batch = []
        for src, dst, since in gen_edges(n_persons):
            batch.append({"s": src, "d": dst, "y": since})
            if len(batch) >= INGEST_BATCH:
                self.g.query("UNWIND $rows AS r MATCH (a:Person {id: r.s}), "
                             "(b:Person {id: r.d}) CREATE (a)-[:KNOWS {since: r.y}]->(b)",
                             {"rows": batch})
                batch = []
        if batch:
            self.g.query("UNWIND $rows AS r MATCH (a:Person {id: r.s}), "
                         "(b:Person {id: r.d}) CREATE (a)-[:KNOWS {since: r.y}]->(b)",
                         {"rows": batch})

    # MESSAGE-HALF loader (DECISIONS #103b). Same UNWIND shape as Neo4j over
    # GRAPH.QUERY; Message is a second label (FalkorDB 4.x supports multiple
    # labels per node), the index is Neo4j's without the name (as the Person
    # index above).
    def build_messages(self):
        mc = _ldbc.MessageCorpus(self._scale)
        vcount = ecount = 0
        for label in _ldbc.MSG_VERTEX_LABELS:
            self.g.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
        for label, ids in mc.vertex_spec():
            extra = ":Message" if label in _ldbc.MSG_MESSAGE_SUBLABELS else ""
            cy = f"UNWIND $rows AS r CREATE (n:{label}{extra} {{id: r}})"
            batch = []
            for vid in ids:
                batch.append(vid)
                if len(batch) >= INGEST_BATCH:
                    self.g.query(cy, {"rows": batch}); vcount += len(batch); batch = []
            if batch:
                self.g.query(cy, {"rows": batch}); vcount += len(batch)
        for rel, src_label, dst_label, gen in mc.edge_spec():
            cy = (f"UNWIND $rows AS r MATCH (a:{src_label} {{id: r.s}}), "
                  f"(b:{dst_label} {{id: r.d}}) CREATE (a)-[:{rel}]->(b)")
            batch = []
            for sv, dv in gen():
                batch.append({"s": sv, "d": dv})
                if len(batch) >= INGEST_BATCH:
                    self.g.query(cy, {"rows": batch}); ecount += len(batch); batch = []
            if batch:
                self.g.query(cy, {"rows": batch}); ecount += len(batch)
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def run_cypher(self, text):
        return len(self.g.query(text).result_set)

    def run_cypher_write(self, text):
        self.g.query(text)

    def close(self):
        self.conn.close()


# --------------------------------------------------------------- LadybugDB
class LadybugGraph(Base):
    name = "ladybug_graph"

    def connect(self):
        import ladybug
        self._mod = ladybug
        self.db = ladybug.Database("/tmp/l2_ladybug")
        self.conn = ladybug.Connection(self.db)
        self.version = f"ladybug:{getattr(ladybug, '__version__', '?')}"
        self.conn.execute(
            "CREATE NODE TABLE Person(id INT64, name STRING, age INT64, "
            "city STRING, PRIMARY KEY(id))")
        self.conn.execute(
            "CREATE REL TABLE KNOWS(FROM Person TO Person, since INT64)")

    def build(self, n_persons):
        # CSV COPY — LadybugDB's native bulk path (Kuzu lineage)
        import csv as _csv
        pcsv, kcsv = "/tmp/l2_persons.csv", "/tmp/l2_knows.csv"
        with open(pcsv, "w", newline="") as f:
            w = _csv.writer(f)  # proper quoting: LDBC names can carry commas/quotes
            for i, name, age, city in gen_persons(n_persons):
                w.writerow([i, name, age, city])
        with open(kcsv, "w", newline="") as f:
            w = _csv.writer(f)
            for src, dst, since in gen_edges(n_persons):
                w.writerow([src, dst, since])
        self.conn.execute(f"COPY Person FROM '{pcsv}'")
        self.conn.execute(f"COPY KNOWS FROM '{kcsv}'")
        os.unlink(pcsv)
        os.unlink(kcsv)

    # MESSAGE-HALF loader (DECISIONS #103b). LadybugDB (Kuzu lineage) has no
    # type inheritance and no multi-label, so it cannot express `(:Message)`
    # as a supertype; instead it uses LSQB's own published Kuzu model
    # (github.com/ldbc/lsqb/tree/main/ladybug): a single Message node table
    # that holds every Post and Comment, and one typed REL table per
    # relationship. Post and Comment are therefore folded into Message here,
    # and the comment->post reply subset is additionally kept in its own
    # table (Comment_replyOf_Post), as LSQB carries it, so the October
    # instrument's queries find the same model on both pages. The three
    # September questions read Person and KNOWS only.
    _MSG_NODE_TABLES = ["Country", "City", "Forum", "Message", "Tag", "TagClass"]
    _REL_TABLE = {
        ("IS_LOCATED_IN", "Person", "City"):    "Person_isLocatedIn_City",
        ("IS_PART_OF", "City", "Country"):       "City_isPartOf_Country",
        ("HAS_MEMBER", "Forum", "Person"):       "Forum_hasMember_Person",
        ("CONTAINER_OF", "Forum", "Post"):       "Forum_containerOf_Message",
        ("REPLY_OF", "Comment", "Post"):         "Message_replyOf_Message",
        ("REPLY_OF", "Comment", "Comment"):      "Message_replyOf_Message",
        ("HAS_TAG", "Post", "Tag"):              "Message_hasTag_Tag",
        ("HAS_TAG", "Comment", "Tag"):           "Message_hasTag_Tag",
        ("HAS_TYPE", "Tag", "TagClass"):         "Tag_hasType_TagClass",
        ("HAS_CREATOR", "Post", "Person"):       "Message_hasCreator_Person",
        ("HAS_CREATOR", "Comment", "Person"):    "Message_hasCreator_Person",
        ("LIKES", "Person", "Post"):             "Person_likes_Message",
        ("LIKES", "Person", "Comment"):          "Person_likes_Message",
        ("HAS_INTEREST", "Person", "Tag"):       "Person_hasInterest_Tag",
    }
    _REL_ENDPOINTS = {   # Kuzu needs FROM/TO node tables in the DDL
        "Person_isLocatedIn_City": ("Person", "City"),
        "City_isPartOf_Country": ("City", "Country"),
        "Forum_hasMember_Person": ("Forum", "Person"),
        "Forum_containerOf_Message": ("Forum", "Message"),
        "Message_replyOf_Message": ("Message", "Message"),
        "Comment_replyOf_Post": ("Message", "Message"),
        "Message_hasTag_Tag": ("Message", "Tag"),
        "Tag_hasType_TagClass": ("Tag", "TagClass"),
        "Message_hasCreator_Person": ("Message", "Person"),
        "Person_likes_Message": ("Person", "Message"),
        "Person_hasInterest_Tag": ("Person", "Tag"),
    }

    def build_messages(self):
        import csv as _csv
        mc = _ldbc.MessageCorpus(self._scale)
        for t in self._MSG_NODE_TABLES:
            self.conn.execute(f"CREATE NODE TABLE {t}(id INT64, PRIMARY KEY(id))")
        for rt, (fr, to) in self._REL_ENDPOINTS.items():
            self.conn.execute(f"CREATE REL TABLE {rt}(FROM {fr} TO {to})")
        vcount = ecount = 0

        # node CSVs: Post and Comment both become Message
        def _copy_nodes(table, id_iters):
            nonlocal vcount
            path = f"/tmp/l2_lady_{table}.csv"
            with open(path, "w", newline="") as f:
                w = _csv.writer(f)
                for ids in id_iters:
                    for vid in ids:
                        w.writerow([vid]); vcount += 1
            self.conn.execute(f"COPY {table} FROM '{path}'")
            os.unlink(path)
        by_label = {label: g for label, g in mc.vertex_spec()}
        _copy_nodes("Message", [by_label["Post"], by_label["Comment"]])
        for t in ("Country", "City", "Forum", "Tag", "TagClass"):
            _copy_nodes(t, [by_label[t]])
        # rel CSVs, one per Kuzu rel table (several generic edges may share one)
        rel_files = {}
        for rel, src_label, dst_label, gen in mc.edge_spec():
            targets = [self._REL_TABLE[(rel, src_label, dst_label)]]
            if (rel, src_label, dst_label) == ("REPLY_OF", "Comment", "Post"):
                targets.append("Comment_replyOf_Post")  # the comment->post subset
            for rt in targets:
                if rt not in rel_files:
                    fh = open(f"/tmp/l2_lady_rel_{rt}.csv", "a", newline="")
                    rel_files[rt] = (fh, _csv.writer(fh))
            writers = [rel_files[rt][1] for rt in targets]
            for s, d in gen():
                ecount += 1     # the edge is counted once even if stored twice
                for w in writers:
                    w.writerow([s, d])
        for rt, (fh, _w) in rel_files.items():
            fh.close()
            self.conn.execute(f"COPY {rt} FROM '/tmp/l2_lady_rel_{rt}.csv'")
            os.unlink(f"/tmp/l2_lady_rel_{rt}.csv")
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def post_build(self, workload):
        self.conn.execute("CHECKPOINT")

    def close(self):
        """Close the connection and the database.

        LadybugDB inherited the no-op close(), so this lane never shut its
        control engine down either: the same defect as #155 in l3_sparse, and
        it matters for the same reason. Whatever a clean close settles here is
        work the comparator was not charged for, and it is the engine we
        compare against. Both handles expose close() in 0.19.1.
        """
        for h in ("conn", "db"):
            obj = getattr(self, h, None)
            if obj is not None:
                obj.close()

    def reopen(self):
        """Reattach to the built database: no DDL, the tables persist.

        The control arm for the reopen measurement. LadybugDB is resident from
        load and gains 1.00x on a warm pass where ArcadeDB gains 9x, so if a
        phase split moved the cold pass this is the engine that should not
        care. An arm that moves here is a harness artifact, not an engine
        property.
        """
        import ladybug
        self._mod = ladybug
        self.db = ladybug.Database("/tmp/l2_ladybug")
        self.conn = ladybug.Connection(self.db)

    def run_cypher(self, text):
        return len(list(self.conn.execute(text)))


class DuckpgqGraph(Base):
    """DuckDB with the DuckPGQ community extension (embedded, in-process through
    the duckdb Python package on the pinned dbbench:duckdb image, duckdb==1.5.4).
    The persons-and-knows data lives in two DuckDB tables; a PROPERTY GRAPH over
    them answers every graph read in SQL/PGQ (`GRAPH_TABLE ... MATCH`), and the
    write is plain SQL on the underlying tables in one transaction (DECISIONS
    #103d, #103e).

    WHY 1.5.4 AND NOT 1.5.5. The community-extensions registry has a DuckPGQ
    build for 1.5.4 and none for 1.5.5 or 1.6.0 (`INSTALL duckpgq FROM
    community` on 1.5.5 answers HTTP 404), so every DuckDB arm on the page pins
    to 1.5.4 (DECISIONS #103e: one engine, one version per page).

    NOTHING IS UNEXPRESSIBLE ON THIS LANE. The point lookup and the one- and
    two-hop reads are `GRAPH_TABLE MATCH` patterns; the three analytics
    questions are a MATCH feeding an outer GROUP BY; every answer matched the
    Cypher engines' on the micro corpus (laptop, 2026-09-17, October branch).
    DuckPGQ requires EVERY edge pattern to bind a variable, so each hop names
    its edge. The property graph is a live view over the tables, so a
    plain-SQL insert is visible to the next MATCH with no re-definition.

    THREAD POOL fitted to the cpuset (FAIRNESS F6): `PRAGMA threads` from
    `sched_getaffinity`, recorded as `duckpgq_threads`. DuckDB sizes its pool
    from the host under a cpuset, and this arm is new, so it carries the fix
    the audit calls for rather than the oversubscription the older DuckDB
    arms on this page still run with (FAIRNESS.md F6 table).
    """
    name = "duckpgq_graph"
    DBPATH = "/tmp/l2_duckpgq.db"

    # PGQ reads: {id} formatted in as a literal, like the lane's Cypher, so
    # every engine stays on the same query-plan surface. Every edge binds a
    # variable (DuckPGQ requires it).
    READS = {
        "point": ("SELECT name, age FROM GRAPH_TABLE (pg "
                  "MATCH (p:Person WHERE p.id = {id}) "
                  "COLUMNS (p.name AS name, p.age AS age))"),
        "hop1": ("SELECT count(*) AS n, avg(fage) AS a FROM GRAPH_TABLE (pg "
                 "MATCH (p:Person WHERE p.id = {id})-[k:knows]->(f:Person) "
                 "COLUMNS (f.age AS fage))"),
        "hop2": ("SELECT count(DISTINCT fof) AS n FROM GRAPH_TABLE (pg "
                 "MATCH (p:Person WHERE p.id = {id})-[k1:knows]->(m:Person)"
                 "-[k2:knows]->(fof:Person) COLUMNS (fof.id AS fof))"),
    }
    # The three analytics questions, the lane's Cypher ORDER BY and LIMIT
    # kept verbatim.
    OLAP = {
        "top_degree": ("SELECT id, count(*) AS d FROM GRAPH_TABLE (pg "
                       "MATCH (p:Person)-[k:knows]->(f:Person) COLUMNS (p.id AS id)) "
                       "GROUP BY id ORDER BY d DESC LIMIT 10"),
        "same_city_edges": ("SELECT c, count(*) AS n FROM GRAPH_TABLE (pg "
                            "MATCH (a:Person)-[k:knows]->(b:Person) WHERE a.city = b.city "
                            "COLUMNS (a.city AS c)) GROUP BY c ORDER BY n DESC LIMIT 10"),
        "friend_age_by_city": ("SELECT c, avg(fage) AS a, count(*) AS n FROM GRAPH_TABLE (pg "
                               "MATCH (p:Person)-[k:knows]->(f:Person) "
                               "COLUMNS (p.city AS c, f.age AS fage)) "
                               "GROUP BY c ORDER BY n DESC LIMIT 10"),
    }

    def connect(self):
        import duckdb
        if os.path.exists(self.DBPATH):
            os.remove(self.DBPATH)
        self.cx = duckdb.connect(self.DBPATH)
        # F6: DuckDB sizes its pool from the host under the cpuset; only
        # sched_getaffinity sees the mask.
        self._threads = len(os.sched_getaffinity(0))
        self.cx.execute(f"PRAGMA threads={self._threads}")
        # The community DuckPGQ build for the pinned 1.5.4 (404 on 1.5.5).
        self.cx.execute("INSTALL duckpgq FROM community; LOAD duckpgq;")
        _ext = self.cx.execute(
            "SELECT extension_version FROM duckdb_extensions() "
            "WHERE extension_name = 'duckpgq'").fetchall()
        _ev = _ext[0][0] if _ext else "?"
        # "duckpgq:<build> on duckdb:<version>": the page's version line takes
        # the first version-shaped token after the engine's name, and the
        # community build id (a short sha) is not one, so the row reads
        # "duckpgq 1.5.4", the DuckDB it ran on, the way the DuckDB VSS row
        # reads its DuckDB. The build id stays in the artifact beside it.
        self.version = f"duckpgq:{_ev} on duckdb:{duckdb.__version__}"
        self.row_extra = {"duckpgq_threads": self._threads,
                          "duckpgq_extension_version": _ev}
        # Tables first, then the property graph over them (empty is fine: the
        # graph is a live view, so the build below fills it). Person keyed by id
        # so the point lookup and the plain-SQL write reach one row by key.
        self.cx.execute("CREATE TABLE Person(id BIGINT PRIMARY KEY, name VARCHAR, "
                        "age BIGINT, city VARCHAR)")
        self.cx.execute("CREATE TABLE knows(src BIGINT, dst BIGINT, since BIGINT)")
        self.cx.execute("CREATE PROPERTY GRAPH pg VERTEX TABLES (Person) "
                        "EDGE TABLES (knows SOURCE KEY (src) REFERENCES Person (id) "
                        "DESTINATION KEY (dst) REFERENCES Person (id))")

    def _bulk(self, table, cols, gen):
        # DuckDB's columnar bulk path: an Arrow table per batch, INSERT SELECT,
        # rather than row-by-row executemany (l3d measured the latter as hours
        # for a large load). Batched so memory stays bounded at the larger tiers.
        import pyarrow as pa
        buf = []

        def flush():
            columns = list(zip(*buf))
            tbl = pa.table({c: pa.array(columns[i]) for i, c in enumerate(cols)})
            self.cx.register("_src", tbl)
            self.cx.execute(f"INSERT INTO {table} SELECT * FROM _src")
            self.cx.unregister("_src")

        for row in gen:
            buf.append(row)
            if len(buf) >= INGEST_BATCH:
                flush(); buf = []
        if buf:
            flush()

    def build(self, n_persons):
        self._bulk("Person", ["id", "name", "age", "city"], gen_persons(n_persons))
        self._bulk("knows", ["src", "dst", "since"], gen_edges(n_persons))
        # AFTER the load: src is the write's edge lookup. PGQ builds its own
        # traversal structures, so this serves only the plain-SQL write.
        self.cx.execute("CREATE INDEX k_src ON knows(src)")

    # MESSAGE-HALF loader (DECISIONS #103b), following LSQB's own published
    # DuckPGQ implementation (github.com/ldbc/lsqb/tree/main/pgq): separate
    # Post, Comment and Message vertex tables (Message = Post UNION ALL
    # Comment), one base edge table per relationship plus Message-level UNION
    # tables for the supertype, and the property graph redefined over all of
    # them with a LABEL per edge table. The persons+KNOWS labels are unchanged,
    # so the three September questions still run against `pg` as before.
    _MSG_EDGE_TABLES = [
        # (table, generic (rel, src, dst), pgq_source_vertex, pgq_dest_vertex, label)
        ("dp_person_islocatedin_city", ("IS_LOCATED_IN", "Person", "City"), "Person", "City", "Person_isLocatedIn"),
        ("dp_city_ispartof_country",   ("IS_PART_OF", "City", "Country"),   "City", "Country", "City_isPartOf_Country"),
        ("dp_forum_hasmember_person",  ("HAS_MEMBER", "Forum", "Person"),   "Forum", "Person", "hasMember"),
        ("dp_forum_containerof_post",  ("CONTAINER_OF", "Forum", "Post"),   "Forum", "Post", "containerOf"),
        ("dp_comment_replyof_post",    ("REPLY_OF", "Comment", "Post"),     "Comment", "Post", "replyOf_Post"),
        ("dp_comment_replyof_comment", ("REPLY_OF", "Comment", "Comment"),  "Comment", "Comment", "replyOf_Comment"),
        ("dp_post_hastag_tag",         ("HAS_TAG", "Post", "Tag"),          "Post", "Tag", "Post_hasTag"),
        ("dp_comment_hastag_tag",      ("HAS_TAG", "Comment", "Tag"),       "Comment", "Tag", "Comment_hasTag"),
        ("dp_tag_hastype_tagclass",    ("HAS_TYPE", "Tag", "TagClass"),     "Tag", "TagClass", "hasType"),
        ("dp_post_hascreator_person",  ("HAS_CREATOR", "Post", "Person"),   "Post", "Person", "Post_hasCreator"),
        ("dp_comment_hascreator_person", ("HAS_CREATOR", "Comment", "Person"), "Comment", "Person", "Comment_hasCreator"),
        ("dp_person_likes_post",       ("LIKES", "Person", "Post"),         "Person", "Post", "likes_Post"),
        ("dp_person_likes_comment",    ("LIKES", "Person", "Comment"),      "Person", "Comment", "likes_Comment"),
        ("dp_person_hasinterest_tag",  ("HAS_INTEREST", "Person", "Tag"),   "Person", "Tag", "hasInterest"),
    ]

    def build_messages(self):
        mc = _ldbc.MessageCorpus(self._scale)
        for t in ("Country", "City", "Forum", "Post", "Comment", "Tag", "TagClass"):
            self.cx.execute(f"CREATE TABLE {t}(id BIGINT)")
        vcount = 0
        by_label = {label: g for label, g in mc.vertex_spec()}
        for t in ("Country", "City", "Forum", "Post", "Comment", "Tag", "TagClass"):
            self._bulk(t, ["id"], ((v,) for v in by_label[t]))
            vcount += self.cx.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        # Message supertype: every Post and Comment.
        self.cx.execute("CREATE TABLE Message AS SELECT id FROM Post UNION ALL SELECT id FROM Comment")
        edge_gen = {(rel, s, d): gen for rel, s, d, gen in mc.edge_spec()}
        ecount = 0
        for table, key, _sv, _dv, _lbl in self._MSG_EDGE_TABLES:
            self.cx.execute(f"CREATE TABLE {table}(s BIGINT, d BIGINT)")
            self._bulk(table, ["s", "d"], edge_gen[key]())
            ecount += self.cx.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        # Message-level UNION edge tables for the supertype.
        self.cx.execute("CREATE TABLE dp_message_hastag AS "
                        "SELECT s, d FROM dp_post_hastag_tag UNION ALL SELECT s, d FROM dp_comment_hastag_tag")
        self.cx.execute("CREATE TABLE dp_message_hascreator AS "
                        "SELECT s, d FROM dp_post_hascreator_person UNION ALL SELECT s, d FROM dp_comment_hascreator_person")
        self.cx.execute("CREATE TABLE dp_person_likes_message AS "
                        "SELECT s, d FROM dp_person_likes_post UNION ALL SELECT s, d FROM dp_person_likes_comment")
        self.cx.execute("CREATE TABLE dp_message_replyof_message AS "
                        "SELECT s, d FROM dp_comment_replyof_post UNION ALL SELECT s, d FROM dp_comment_replyof_comment")
        # Redefine the property graph over everything (CREATE PROPERTY GRAPH
        # cannot be altered). The persons+KNOWS labels are unchanged, so the
        # three questions still run against `pg`.
        et = ["knows SOURCE KEY (src) REFERENCES Person (id) DESTINATION KEY (dst) REFERENCES Person (id) LABEL knows"]
        for table, _key, sv, dv, lbl in self._MSG_EDGE_TABLES:
            et.append(f"{table} SOURCE KEY (s) REFERENCES {sv} (id) "
                      f"DESTINATION KEY (d) REFERENCES {dv} (id) LABEL {lbl}")
        for table, sv, dv, lbl in [
            ("dp_message_hastag", "Message", "Tag", "Message_hasTag"),
            ("dp_message_hascreator", "Message", "Person", "Message_hasCreator"),
            ("dp_person_likes_message", "Person", "Message", "likes_Message"),
            ("dp_message_replyof_message", "Comment", "Message", "replyOf_Message")]:
            et.append(f"{table} SOURCE KEY (s) REFERENCES {sv} (id) "
                      f"DESTINATION KEY (d) REFERENCES {dv} (id) LABEL {lbl}")
        self.cx.execute("DROP PROPERTY GRAPH pg")
        self.cx.execute("CREATE PROPERTY GRAPH pg VERTEX TABLES "
                        "(Person, Message, Post, Comment, Country, City, Forum, Tag, TagClass) "
                        "EDGE TABLES (" + ", ".join(et) + ")")
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    def run_read(self, op, pid):
        return len(self.cx.execute(self.READS[op].format(id=pid)).fetchall())

    def run_olap(self, qname):
        return len(self.cx.execute(self.OLAP[qname]).fetchall())

    def run_write(self, pid, new_id):
        # One transaction, the Cypher's CREATE-and-link: the person and the edge
        # either both exist or neither does.
        self.cx.execute("BEGIN")
        self.cx.execute("INSERT INTO Person VALUES (?, ?, 33, 'city_0')",
                        [new_id, f"w{new_id}"])
        self.cx.execute("INSERT INTO knows VALUES (?, ?, 2026)", [pid, new_id])
        self.cx.execute("COMMIT")

    def run_cypher(self, text):
        raise NotImplementedError("DuckPGQ runs SQL/PGQ through the name-based hooks")

    def close(self):
        self.cx.close()


class SurrealGraph(Base):
    """SurrealDB through its Python SDK on the SDK's SurrealKV disk store
    (SDK 2.0.0, which carries core 2.3.10), the same LDBC questions in SurrealQL: person records with
    record ids, KNOWS as a RELATE edge table (2026-09-11). The served twin
    below runs the 3.2.4 server on RocksDB."""
    name = "surrealdb_graph"
    URL = "surrealkv:///tmp/l2_surrealkv"

    def _open(self):
        import shutil
        from surrealdb import Surreal
        shutil.rmtree("/tmp/l2_surrealkv", ignore_errors=True)
        self.db = Surreal(self.URL)
        self.db.use("bench", "bench")
        self.version = surreal_common.engine_stamp(self.db)   # core version, not the SDK's (F39)

    def connect(self):
        self._open()
        self.db.query("REMOVE TABLE IF EXISTS knows; REMOVE TABLE IF EXISTS person")
        self.db.query("DEFINE TABLE person SCHEMALESS; DEFINE TABLE knows TYPE RELATION IN person OUT person SCHEMALESS")

    def build(self, n_persons):
        # RecordID, not "person:7": the SDK stores a string id as a string
        # KEY, and person:7 then names nothing (laptop smoke, 2026-09-11).
        from surrealdb import RecordID
        buf = []
        for i, name, age, city in gen_persons(n_persons):
            buf.append({"id": RecordID("person", i), "pid": i, "name": name, "age": age, "city": city})
            if len(buf) >= INGEST_BATCH:
                self.db.insert("person", buf); buf = []
        if buf:
            self.db.insert("person", buf)
        # insert_relation, not RELATE statements: 5,000 edges took 34.6 s as
        # RELATEs over the wire and 0.6 s as one bulk relation insert on the
        # 3.2.4 server (laptop, 2026-09-11); same hop results either way.
        buf = []
        for src, dst, since in gen_edges(n_persons):
            buf.append({"in": RecordID("person", src), "out": RecordID("person", dst), "since": since})
            if len(buf) >= INGEST_BATCH:
                self.db.insert_relation("knows", buf); buf = []
        if buf:
            self.db.insert_relation("knows", buf)

    # MESSAGE-HALF loader (DECISIONS #103b), shared with the served twin. Posts
    # and Comments share a `message` table (an `mtype` field marks which); each
    # relationship is a RELATION edge table; vertices carry their LDBC id as
    # `pid`. The three September questions read person and knows only.
    _MSG_REL = {   # generic (rel, src, dst) -> (relation table, in table, out table)
        ("IS_LOCATED_IN", "Person", "City"):  ("islocatedin", "person", "city"),
        ("IS_PART_OF", "City", "Country"):     ("ispartof", "city", "country"),
        ("HAS_MEMBER", "Forum", "Person"):     ("hasmember", "forum", "person"),
        ("CONTAINER_OF", "Forum", "Post"):     ("containerof", "forum", "message"),
        ("REPLY_OF", "Comment", "Post"):       ("replyof", "message", "message"),
        ("REPLY_OF", "Comment", "Comment"):    ("replyof", "message", "message"),
        ("HAS_TAG", "Post", "Tag"):            ("hastag", "message", "tag"),
        ("HAS_TAG", "Comment", "Tag"):         ("hastag", "message", "tag"),
        ("HAS_TYPE", "Tag", "TagClass"):       ("hastype", "tag", "tagclass"),
        ("HAS_CREATOR", "Post", "Person"):     ("hascreator", "message", "person"),
        ("HAS_CREATOR", "Comment", "Person"):  ("hascreator", "message", "person"),
        ("LIKES", "Person", "Post"):           ("likes", "person", "message"),
        ("LIKES", "Person", "Comment"):        ("likes", "person", "message"),
        ("HAS_INTEREST", "Person", "Tag"):     ("hasinterest", "person", "tag"),
    }

    def build_messages(self):
        from surrealdb import RecordID
        mc = _ldbc.MessageCorpus(self._scale)
        for t in ("message", "country", "city", "forum", "tag", "tagclass"):
            self.db.query(f"DEFINE TABLE {t} SCHEMALESS")
        rel_tables = {}
        for (_k, (rt, itbl, otbl)) in self._MSG_REL.items():
            if rt not in rel_tables:
                self.db.query(f"DEFINE TABLE {rt} TYPE RELATION IN {itbl} OUT {otbl} SCHEMALESS")
                rel_tables[rt] = (itbl, otbl)
        vcount = ecount = 0
        by_label = {label: g for label, g in mc.vertex_spec()}

        def _ins(table, docs):
            nonlocal vcount
            buf = []
            for d in docs:
                buf.append(d); vcount += 1
                if len(buf) >= INGEST_BATCH:
                    self.db.insert(table, buf); buf = []
            if buf:
                self.db.insert(table, buf)
        for label, t in [("Country", "country"), ("City", "city"), ("Forum", "forum"),
                         ("Tag", "tag"), ("TagClass", "tagclass")]:
            _ins(t, ({"id": RecordID(t, v), "pid": v} for v in by_label[label]))
        _ins("message", ({"id": RecordID("message", v), "pid": v, "mtype": "post"} for v in by_label["Post"]))
        _ins("message", ({"id": RecordID("message", v), "pid": v, "mtype": "comment"} for v in by_label["Comment"]))
        for rel, src_label, dst_label, gen in mc.edge_spec():
            rt, itbl, otbl = self._MSG_REL[(rel, src_label, dst_label)]
            buf = []
            for s, d in gen():
                buf.append({"in": RecordID(itbl, s), "out": RecordID(otbl, d)}); ecount += 1
                if len(buf) >= INGEST_BATCH:
                    self.db.insert_relation(rt, buf); buf = []
            if buf:
                self.db.insert_relation(rt, buf)
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    @staticmethod
    def _rows(res):
        if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
            res = res[-1]["result"]
        return res if isinstance(res, list) else ([res] if res is not None else [])

    def run_read(self, op, pid):
        if op == "point":
            r = self.db.query(f"SELECT name, age FROM ONLY person:{pid}")
        elif op == "hop1":
            r = self.db.query(f"SELECT count(->knows->person) AS n, math::mean(->knows->person.age) AS a FROM ONLY person:{pid}")
        else:
            r = self.db.query(f"SELECT array::len(array::distinct(->knows->person->knows->person)) AS n FROM ONLY person:{pid}")
        return len(self._rows(r))

    def run_write(self, pid, new_id):
        self.db.query(f"CREATE person:{new_id} SET pid = {new_id}, name = 'w{new_id}', age = 33, city = 'city_0'; "
                      f"RELATE person:{pid}->knows->person:{new_id} SET since = 2026")

    OLAP = {
        "top_degree": "SELECT pid, count(->knows) AS d FROM person ORDER BY d DESC LIMIT 10",
        # subquery form: on core 2.3.10 ORDER BY after GROUP BY sorted by the group
        # key, not n (laptop smoke, 2026-09-11); 3.2.4 accepts both forms
        "same_city_edges": "SELECT * FROM (SELECT in.city AS c, count() AS n FROM knows WHERE in.city = out.city GROUP BY c) ORDER BY n DESC LIMIT 10",
        "friend_age_by_city": "SELECT * FROM (SELECT in.city AS c, math::mean(out.age) AS a, count() AS n FROM knows GROUP BY c) ORDER BY n DESC LIMIT 10",
    }

    def run_olap(self, qname):
        return len(self._rows(self.db.query(self.OLAP[qname])))

    def run_cypher(self, text):
        raise NotImplementedError("SurrealDB runs SurrealQL through the name-based hooks")

    def close(self):
        try:
            self.db.close()
        except Exception:  # noqa: BLE001
            pass


class SurrealGraphServer(SurrealGraph):
    name = "surrealdb_graph_server"

    def _open(self):
        from surrealdb import Surreal
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.db = Surreal(f"ws://{host}:8000/rpc")
        self.db.signin({"username": "root", "password": "root"})
        self.db.use("bench", "bench")
        self.version = "surrealdb-server:" + str(self.db.version()).replace("surrealdb-", "")


class ArangoGraph(Base):
    """ArangoDB 3.12.11 served (2026-09-13): person as a document collection
    keyed by the LDBC id, KNOWS as an edge collection, both loaded through
    the bulk import API; the same LDBC questions in AQL traversals through
    the name-based hooks. The write is one AQL query (two INSERTs), which
    ArangoDB runs as one transaction."""
    name = "arangodb_graph"

    def connect(self):
        self.cl, self.db, self.version = arango_common.connect()
        self.person = self.db.create_collection("person")
        self.knows = self.db.create_collection("knows", edge=True)

    def build(self, n_persons):
        buf = []
        for i, name, age, city in gen_persons(n_persons):
            buf.append({"_key": str(i), "id": i, "name": name, "age": age, "city": city})
            if len(buf) >= INGEST_BATCH:
                self.person.import_bulk(buf); buf = []
        if buf:
            self.person.import_bulk(buf)
        buf = []
        for src, dst, since in gen_edges(n_persons):
            buf.append({"_from": f"person/{src}", "_to": f"person/{dst}", "since": since})
            if len(buf) >= INGEST_BATCH:
                self.knows.import_bulk(buf); buf = []
        if buf:
            self.knows.import_bulk(buf)

    # MESSAGE-HALF loader (DECISIONS #103b). Posts and Comments share one
    # `message` document collection with an `mtype` field ('post'/'comment'),
    # which is how the SNB supertype is expressed here; the other message-half
    # vertices are their own collections and each relationship is its own edge
    # collection, all through the bulk import API like the projection.
    _MSG_VCOLL = ["country", "city", "forum", "message", "tag", "tagclass"]
    # generic (rel, src, dst) -> (edge collection, _from coll, _to coll)
    _MSG_ECOLL = {
        ("IS_LOCATED_IN", "Person", "City"):   ("e_islocatedin", "person", "city"),
        ("IS_PART_OF", "City", "Country"):      ("e_ispartof", "city", "country"),
        ("HAS_MEMBER", "Forum", "Person"):      ("e_hasmember", "forum", "person"),
        ("CONTAINER_OF", "Forum", "Post"):      ("e_containerof", "forum", "message"),
        ("REPLY_OF", "Comment", "Post"):        ("e_replyof", "message", "message"),
        ("REPLY_OF", "Comment", "Comment"):     ("e_replyof", "message", "message"),
        ("HAS_TAG", "Post", "Tag"):             ("e_hastag", "message", "tag"),
        ("HAS_TAG", "Comment", "Tag"):          ("e_hastag", "message", "tag"),
        ("HAS_TYPE", "Tag", "TagClass"):        ("e_hastype", "tag", "tagclass"),
        ("HAS_CREATOR", "Post", "Person"):      ("e_hascreator", "message", "person"),
        ("HAS_CREATOR", "Comment", "Person"):   ("e_hascreator", "message", "person"),
        ("LIKES", "Person", "Post"):            ("e_likes", "person", "message"),
        ("LIKES", "Person", "Comment"):         ("e_likes", "person", "message"),
        ("HAS_INTEREST", "Person", "Tag"):      ("e_hasinterest", "person", "tag"),
    }

    def build_messages(self):
        mc = _ldbc.MessageCorpus(self._scale)
        colls = {c: self.db.create_collection(c) for c in self._MSG_VCOLL}
        ecolls = {}
        for _key, (ec, _f, _t) in self._MSG_ECOLL.items():
            if ec not in ecolls:
                ecolls[ec] = self.db.create_collection(ec, edge=True)
        vcount = ecount = 0
        vlabel_to_coll = {"Country": "country", "City": "city", "Forum": "forum",
                          "Tag": "tag", "TagClass": "tagclass"}
        by_label = {label: g for label, g in mc.vertex_spec()}

        def _load_docs(coll, docs):
            nonlocal vcount
            buf = []
            for doc in docs:
                buf.append(doc); vcount += 1
                if len(buf) >= INGEST_BATCH:
                    colls[coll].import_bulk(buf); buf = []
            if buf:
                colls[coll].import_bulk(buf)
        for label, coll in vlabel_to_coll.items():
            _load_docs(coll, ({"_key": str(v), "id": v} for v in by_label[label]))
        _load_docs("message", ({"_key": str(v), "id": v, "mtype": "post"} for v in by_label["Post"]))
        _load_docs("message", ({"_key": str(v), "id": v, "mtype": "comment"} for v in by_label["Comment"]))
        for rel, src_label, dst_label, gen in mc.edge_spec():
            ec, fc, tc = self._MSG_ECOLL[(rel, src_label, dst_label)]
            buf = []
            for s, d in gen():
                buf.append({"_from": f"{fc}/{s}", "_to": f"{tc}/{d}"}); ecount += 1
                if len(buf) >= INGEST_BATCH:
                    ecolls[ec].import_bulk(buf); buf = []
            if buf:
                ecolls[ec].import_bulk(buf)
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    READS = {
        "point": "FOR p IN person FILTER p._key == @k RETURN {name: p.name, age: p.age}",
        "hop1": ("FOR f IN 1..1 OUTBOUND CONCAT('person/', @k) knows "
                 "COLLECT AGGREGATE n = COUNT(1), a = AVG(f.age) RETURN {n, a}"),
        # DISTINCT at depth two, like count(DISTINCT fof): the default path
        # uniqueness matches Cypher's relationship isomorphism.
        "hop2": ("LET s = (FOR v IN 2..2 OUTBOUND CONCAT('person/', @k) knows RETURN DISTINCT v._key) "
                 "RETURN LENGTH(s)"),
    }
    OLAP = {
        "top_degree": ("FOR p IN person FOR f IN 1..1 OUTBOUND p knows "
                       "COLLECT id = p.id WITH COUNT INTO d SORT d DESC LIMIT 10 RETURN {id, d}"),
        "same_city_edges": ("FOR a IN person FOR b IN 1..1 OUTBOUND a knows FILTER a.city == b.city "
                            "COLLECT c = a.city WITH COUNT INTO n SORT n DESC LIMIT 10 RETURN {c, n}"),
        "friend_age_by_city": ("FOR p IN person FOR f IN 1..1 OUTBOUND p knows "
                               "COLLECT c = p.city AGGREGATE a = AVG(f.age), n = COUNT(1) "
                               "SORT n DESC LIMIT 10 RETURN {c, a, n}"),
    }

    def _n(self, q, **bv):
        return len(list(self.db.aql.execute(q, bind_vars=bv)))

    def run_read(self, op, pid):
        return self._n(self.READS[op], k=str(pid))

    def run_write(self, pid, new_id):
        self._n("INSERT {_key: @nk, id: @n, name: CONCAT('w', @nk), age: 33, city: 'city_0'} INTO person "
                "INSERT {_from: CONCAT('person/', @k), _to: CONCAT('person/', @nk), since: 2026} INTO knows",
                k=str(pid), nk=str(new_id), n=new_id)

    def run_olap(self, qname):
        return self._n(self.OLAP[qname])

    def run_cypher(self, text):
        raise NotImplementedError("ArangoDB runs AQL through the name-based hooks")

    def close(self):
        arango_common.close(self.cl)


ADAPTERS = {a.name: a for a in
            [ArcadeGraphEmbedded, ArcadeGraphServer, Neo4jGraph, LadybugGraph,
             SurrealGraph, SurrealGraphServer, ArangoGraph,
             MemgraphGraph, FalkorGraph, DuckpgqGraph]}


def pct(sorted_ms, q):
    return sorted_ms[min(len(sorted_ms) - 1, int(len(sorted_ms) * q))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(ADAPTERS))
    ap.add_argument("--workload", required=True, choices=["oltp", "olap"])
    ap.add_argument("--scale", required=True, choices=list(SCALE_PERSONS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # COUNTED, not asserted. n_persons was SCALE_PERSONS[scale], a module constant, so
    # PAGE-SPEC rule 4's corpus fingerprint was fingerprinting a constant: point a
    # lane at an LDBC extract with a partial person_0_0.csv was meant and the row still claims
    # the full corpus, build rate is inflated by the same factor, and the
    # gate that exists to catch exactly that passes. The generator is wrapped so
    # the row records what was actually ingested, and a shortfall is a refusal
    # rather than a smaller number nobody reads.
    n_persons = SCALE_PERSONS[args.scale]
    _ingested = {"persons": 0, "edges": 0}

    n_q = SCALE_OLTP_QUERIES[args.scale]
    out = {"n_persons": n_persons, "graph_source": _GRAPH_SOURCE}

    # THE FULL-NETWORK TIER carries the analytics workload only (DECISIONS
    # #103b): the interactive table keeps the projection at sf1 and sf10,
    # whose per-seed reads never touch the message half. Refused rather than
    # silently run on the projection under the full network's label.
    _load_messages = _GRAPH_SOURCE == "ldbc" and _ldbc.loads_messages(args.scale)
    if _load_messages and args.workload != "olap":
        raise SystemExit(
            f"scale {args.scale} is the full-network tier for the analytics "
            f"workload only; the interactive workload runs at sf1 or sf10.")

    write_id_base = 10_000_000
    if _GRAPH_SOURCE == "ldbc":
        # Rebind generators to scale-aware LDBC streams. Adapters resolve these
        # names from module globals at call time, so rebinding here is enough.
        global gen_persons, gen_edges, pick_query_ids
        gen_persons = lambda _n: _ldbc.gen_persons(args.scale)
        gen_edges = lambda _n: _ldbc.gen_edges(args.scale)
        pick_query_ids = lambda _n, k: _ldbc.pick_query_ids(args.scale, k)
        # LDBC person ids are sparse longs; harness-invented ids must not collide
        write_id_base = _ldbc.write_id_base(args.scale)

    # Wrap AFTER the rebind above, so both the synthetic and the LDBC streams are
    # counted. Adapters resolve these names from module globals at call time, so
    # rebinding here is what makes the count reach them.
    # NO `global` here: Python's global is a compile-time declaration for the whole
    # function, so the one in the ldbc branch above already covers these defs.
    # Repeating it after the branch assigns them is "name assigned to before global
    # declaration", a SyntaxError that ast.parse does NOT catch (it is raised by
    # the symbol-table pass, which only compile() runs) and that therefore reached
    # the bench host and failed every l2 cell.
    _persons_src, _edges_src = gen_persons, gen_edges

    def gen_persons(n, *a, **kw):        # noqa: F811 - deliberate shadow, counted
        for item in _persons_src(n, *a, **kw):
            _ingested["persons"] += 1
            yield item

    def gen_edges(n, *a, **kw):          # noqa: F811 - deliberate shadow, counted
        for item in _edges_src(n, *a, **kw):
            _ingested["edges"] += 1
            yield item
        out["graph_source"] = f"ldbc-{args.scale}"

    ad = ADAPTERS[args.backend]()
    ad._scale = args.scale
    t0 = time.perf_counter()
    ad.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = ad.version
    # What a served engine reported about itself at connect: client library
    # version, thread pool, memory limit, timeouts, persistence settings
    # (Memgraph, FalkorDB, DuckPGQ). Read from the server, not restated from
    # the flags the runner sent. Not printed by the page; kept on the row.
    out.update(getattr(ad, "row_extra", None) or {})

    # THE MESSAGE HALF, inside the build timer, because at the full-network
    # tier it IS the load: the ingest column prices the whole corpus.
    t0 = time.perf_counter()
    ad.build(n_persons)
    if _load_messages:
        print(f"PHASE build-messages-start scale={args.scale} "
              f"msg_limit={_MSG_LIMIT} person_limit={_PERSON_LIMIT}", flush=True)
        ad.build_messages()
        print(f"PHASE build-messages-done {getattr(ad, 'msg_counts', {})}", flush=True)
    ad.post_build(args.workload)
    out["build_s"] = round(time.perf_counter() - t0, 2)
    if _load_messages:
        # What the message half actually loaded, so a reader can check it
        # against the corpus README the way n_persons_ingested checks the
        # projection; and the caps, so a capped smoke row can never be read as
        # the full network.
        out.update(getattr(ad, "msg_counts", None) or {})
        out["msg_limit"] = _MSG_LIMIT
        out["person_limit"] = _PERSON_LIMIT

    if args.workload == "oltp":
        ids = pick_query_ids(n_persons, n_q)
        total_t0 = time.perf_counter()

        def _read_pass(prefix=""):
            """One full pass over the read set, identical on both calls.

            COLD VERSUS WARM. Every lane except the two vector ones timed a
            single pass and reported it without saying which it was. That is
            not a safe omission: the dense lane found ArcadeDB gains about 9x
            on a second pass, because it pages its index off disk while every
            comparator is already resident. If any of that effect exists here,
            a single timed pass is an arbitrary point on that curve, and the
            project page asserts "every other lane times a single pass" as
            though it were a design choice rather than a gap.

            The first call is left EXACTLY as it was, five discarded warmups
            included, so previously published numbers stay comparable. The
            second call is the same code on the same query set, so the delta
            is what a repeat buys and nothing else.
            """
            res = {}
            for op, tmpl in OLTP_READS.items():
                lat = []
                for w, pid in enumerate(ids):
                    t = time.perf_counter()
                    ad.run_read(op, pid)
                    if w >= 5:  # warmups discarded
                        lat.append((time.perf_counter() - t) * 1000)
                lat.sort()
                res[f"{prefix}{op}_p50_ms"] = round(pct(lat, 0.50), 3)
                res[f"{prefix}{op}_p95_ms"] = round(pct(lat, 0.95), 3)
                res[f"{prefix}{op}_p99_ms"] = round(pct(lat, 0.99), 3)
            return res

        out.update(_read_pass())            # first touch
        out.update(_read_pass("warm_"))     # same queries, index now resident
        # Writes stay single-pass on purpose. A second write pass is not a
        # warm repeat, it is a different workload against a larger graph.
        # 1000 writes, not 100: a p99 over 95 timed samples is the second
        # slowest write, not a tail. Ten samples deep at 1000 (2026-09-10).
        n_writes = min(1000, n_q)
        lat = []
        for w, pid in enumerate(ids[:n_writes]):
            new_id = write_id_base + w
            t = time.perf_counter()
            ad.run_write(pid, new_id)
            if w >= 5:
                lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["write_p50_ms"] = round(pct(lat, 0.50), 3)
        out["write_p95_ms"] = round(pct(lat, 0.95), 3)
        # The reads recorded p99 and the writes stopped at p95, so the page
        # had a p99 beside every latency except this one (2026-09-10).
        out["write_p99_ms"] = round(pct(lat, 0.99), 3)
        out["oltp_total_s"] = round(time.perf_counter() - total_t0, 2)
    else:
        for qname, text in OLAP_QUERIES.items():
            # The warmup WAS the cold pass, and it was not even timed. Timing
            # it costs nothing (the query ran either way) and gives this lane
            # the cold/warm split every non-vector lane was missing. The dense
            # lane found that split worth about 9x for ArcadeDB, which pages
            # its index off disk while resident comparators do not, so a lane
            # that reports one number without saying which side it is on is
            # reporting an arbitrary point on that curve.
            _c0 = time.perf_counter()
            rows0 = ad.run_olap(qname)  # first touch, now measured
            out[f"cold_{qname}_ms"] = round((time.perf_counter() - _c0) * 1000, 2)
            lat = []
            for _ in range(OLAP_ITERATIONS):
                t = time.perf_counter()
                ad.run_olap(qname)
                lat.append((time.perf_counter() - t) * 1000)
            # p50 FIRST, because the page prints these as times and asserts
            # elsewhere that pycost is its only non-p50 ms column. Three of these
            # were means, where one GC pause inside five iterations moves the
            # published number and a median would not have noticed.
            lat_sorted = sorted(lat)
            out[f"{qname}_p50_ms"] = round(statistics.median(lat_sorted), 2)
            out[f"{qname}_p95_ms"] = round(
                lat_sorted[max(0, int(0.95 * (len(lat_sorted) - 1)))], 2)
            out[f"{qname}_p99_ms"] = round(
                lat_sorted[max(0, int(0.99 * (len(lat_sorted) - 1)))], 2)
            out[f"{qname}_mean_ms"] = round(statistics.mean(lat), 2)
            out[f"{qname}_min_ms"] = round(min(lat), 2)
            out[f"{qname}_iters"] = len(lat)
            out[f"{qname}_rows"] = rows0
        # STAMP THE ARM. BENCH_GAV=0 changes what was measured and, until this
        # line, changed nothing that was recorded: an ablation run wrote the
        # same lane/scale/n_persons/workload/backend/rep as the published cell
        # with a newer ts_utc, so load_canonical would have kept the ABLATED
        # number and dropped the real one. T3 and the OLAP prose would have
        # silently become the without-view figures, which are 2-7x worse, and
        # nothing in the pipeline would have said so. That is the same shape as
        # the synthetic-corpus sparse rows: a later run under a different
        # protocol shadowing a good one.
        #
        # gav records the condition; the backend suffix keeps the two arms on
        # separate canonical keys so neither can shadow the other, matching how
        # the sparse lane separates its nocompact arm.
        out["gav"] = os.environ.get("BENCH_GAV", "1") != "0"
        if not out["gav"]:
            out["backend_arm"] = "nogav"

    # TIME THE CLOSE, do not merely perform it (#155). A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. An unrecorded close is an unpriced one, and
    # the row cannot be told apart from a lane that never settles.
    #
    # WHAT THE VIEW COST, beside what it bought. Absent on a backend that has
    # no view; 0.0 on the ablated arm, which is a measurement rather than a
    # gap. Until this existed the GAV build sat inside build_s, so "OLAP is Nx
    # faster with the view" had no companion number for what the view cost to
    # make, and the two ablation arms differed by a term nobody could see.
    _gav = getattr(ad, "gav_build_s", None)
    if _gav is not None:
        out["gav_build_s"] = _gav

    _t = time.perf_counter()
    ad.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)
    # Recorded at the END, when the generators have actually run. A shortfall is a
    # refusal: a row claiming the full corpus while a fraction was ingested is
    # exactly what rule 4's fingerprint cannot catch on its own.
    out["n_persons_ingested"] = _ingested["persons"]
    out["n_edges_ingested"] = _ingested["edges"]
    # COMPARE AGAINST THE CORPUS ON DISK, not a published constant.
    #
    # This compared ingest against SCALE_PERSONS, which ldbc_snb documents as the
    # count of the OFFICIAL dataset. Our generated sf1 holds 9,892 against the
    # official 10,995, so the guard refused every l2 cell of qBI on a run whose
    # ingest was complete. That is the same "fingerprinting a constant" defect
    # the guard was written to catch, committed by the guard itself.
    #
    # The real failure mode is a TRUNCATED LOAD: fewer rows ingested than the
    # file offers. Only the file can say what it offers.
    _expected = None
    if _GRAPH_SOURCE == "ldbc":
        _expected = _ldbc.persons_in_corpus(args.scale)
    if _expected is None:
        _expected = n_persons                      # synthetic: the generator IS the corpus
    out["n_persons_in_corpus"] = _expected
    if _ingested["persons"] and _ingested["persons"] < _expected:
        raise SystemExit(
            f"ingested {_ingested['persons']:,} persons against {_expected:,} in the "
            f"corpus for scale {args.scale}: the load is short, so every per-second "
            f"figure in this row is inflated by {_expected/_ingested['persons']:.2f}x.")
    # The same refusal for the message half, against the corpus README's
    # counts, whenever the load was not capped: a full-network row whose
    # loader dropped a stream would otherwise publish an inflated ingest rate
    # under the full network's label.
    if _load_messages and not (_MSG_LIMIT or _PERSON_LIMIT):
        _want = _ldbc.FULL_NETWORK_COUNTS[args.scale]
        _short = {k: (out.get(k), _want[k]) for k in ("msg_vertices", "msg_edges")
                  if (out.get(k) or 0) < _want[k]}
        if _short:
            raise SystemExit(
                f"the message half loaded short of the corpus for {args.scale}: "
                f"{_short} (loaded, expected); the row would publish an inflated "
                f"ingest rate under the full network's label.")

    with open(args.out, "w") as f:
        json.dump(out, f)
    print(json.dumps(out))


if __name__ == "__main__":
    # Fail fast. JPype's JVM keeps non-daemon threads (AsyncFlush,
    # TransactionManager) alive after a Python exception, so a crashed cell
    # would otherwise sit until the runner's multi-hour watchdog. os._exit
    # skips interpreter cleanup and takes the JVM down with it.
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
