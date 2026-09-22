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
import mongo_common

import budget_lookup
import graph_common
from graph_common import (HOP3_VISITED, LSQB_QUERIES, NA_LSQB_NO_MESSAGE_HALF,
                          OLAP_BUDGET_S, OLAP_DIGEST, OLAP_ITERATIONS, OLAP_QUERIES,
                          OLTP_READS, OLTP_WRITE, OLTP_DELETE, OLTP_UPDATE,
                          PERSON_STATE_DIGEST, READ_DIGEST, SCALE_OLTP_QUERIES,
                          SCALE_PERSONS, UPDATE_AGE, VISITED_DIGEST, VISITED_SAMPLE,
                          gen_edges, gen_persons, pick_query_ids)
import bench_common

# Data-source switch (same pattern as l3_sparse/bigann): BENCH_GRAPH_SOURCE=ldbc
# swaps the synthetic generator for the LDBC-SNB persons+KNOWS projection.
# The generators are rebound to scale-aware wrappers in main() once the scale
# is known; templates/tunables stay identical so runs differ only in data.
_GRAPH_SOURCE = os.environ.get("BENCH_GRAPH_SOURCE", "synthetic")
if _GRAPH_SOURCE == "ldbc":
    import ldbc_snb as _ldbc
    SCALE_PERSONS = _ldbc.SCALE_PERSONS
    SCALE_OLTP_QUERIES = _ldbc.SCALE_OLTP_QUERIES
# The analytics message-half caps for a laptop smoke (DECISIONS #104):
# 0 = the whole SF1 network. Read here only to stamp them onto the row and
# onto a phase marker; the loader (ldbc_snb) reads them itself.
_MSG_LIMIT = int(os.environ.get("BENCH_GRAPH_MSG_LIMIT") or 0)
_PERSON_LIMIT = int(os.environ.get("BENCH_GRAPH_PERSON_LIMIT") or 0)

INGEST_BATCH = 5_000
GAV_NAME = "l2gav"
GAV_TIMEOUT_S = 3600
# NO ROW CAP ON THE SERVED ARM (2026-09-14). The ArcadeDB HTTP API truncates a
# result at 20,000 rows unless the request says otherwise, and the #88 digests
# caught both served time-series arms returning exactly 20,000 where every
# other engine returned 32,944. Nothing on this lane returns that many rows
# today, which is precisely why it would have gone unnoticed the day one did.
# -1 means no cap.
HTTP_LIMIT = -1



class Base:
    name = "base"
    version = "?"

    def connect(self):
        raise NotImplementedError

    def build(self, n_persons):
        raise NotImplementedError

    def build_messages(self):
        """Load the FULL-network message half for the analytics workload only
        (DECISIONS #103b/#104). Called after build() at a full-network tier
        (ldbc_snb.loads_messages) with the olap workload; self._scale names the
        tier. Each engine consumes the shared ldbc_snb.MessageCorpus spec
        (vertex_spec / edge_spec) through its own bulk path and records
        self.msg_counts. The default refuses so an engine missing the loader
        is obvious rather than silently running LSQB's nine queries on an empty
        message half under the full network's label."""
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
        """Execute one cypher statement and RETURN ITS ROWS.

        Returned the row COUNT until 2026-09-14, which is why this lane could
        not record a result digest: the answer was thrown away inside the
        adapter and only its length survived. The loops take len() themselves
        now, so the timed work is unchanged and the rows exist to be digested
        outside the timed section (DECISIONS #88).
        """
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

    def run_delete(self, new_id):
        self.run_cypher_write(OLTP_DELETE.format(new_id=new_id))

    def run_update(self, new_id):
        """One property of one record (DECISIONS #82a)."""
        self.run_cypher_write(OLTP_UPDATE.format(new_id=new_id))

    def run_visited(self, pid):
        """Untimed: the distinct persons at three hops, before the age filter."""
        return self.run_cypher(HOP3_VISITED.format(id=pid))

    def person_scan(self, id_from):
        """Untimed read-back of the persons the CRUD phases wrote."""
        return self.run_cypher(
            f"MATCH (q:Person) WHERE q.id >= {id_from} "
            f"RETURN q.id AS id, q.name AS name, q.age AS age, q.city AS city")

    def run_olap(self, qname):
        return self.run_cypher(OLAP_QUERIES[qname])

    def close(self):
        pass


# --------------------------------------------------------------- ArcadeDB
class ArcadeGraphEmbedded(Base):
    QUERY_LANGUAGE = "openCypher (the engine also has its own SQL; DECISIONS #113)"
    name = "arcadedb_graph_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # -Xms pinned to -Xmx for parity with the server deployment
        self.db = arcadedb.create_database(
            "/tmp/l2_arcade",
            # txWalFlush passed explicitly at both classes (DECISIONS #90).
            jvm_kwargs={"heap_size": heap,
                        "jvm_args": bench_common.arcade_jvm_args(f"-Xms{heap}")})
        self.version = arcadedb.__version__
        self.durability = bench_common.arcade_durability_readback()
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
    # supertype and Post/Comment EXTEND it, so `MATCH (m:Message)` reaches both
    # (verified on 26.9.1: the inheritance, `tag1.id <> tag2.id`, the anti-join
    # `WHERE NOT (c)-[:HAS_TAG]->(t)` and OPTIONAL MATCH all run in openCypher).
    # Vertices carry only `id`; every LSQB query is a structural count and the
    # analytics questions never read a message property. The Graph Analytical
    # View stays over Person and KNOWS: the five projection questions traverse
    # nothing else, and LSQB's nine reach labels the view does not carry.
    MSG_EDGE_TYPES = ("IS_LOCATED_IN", "IS_PART_OF", "HAS_MEMBER", "CONTAINER_OF",
                      "REPLY_OF", "HAS_TAG", "HAS_TYPE", "HAS_CREATOR", "LIKES",
                      "HAS_INTEREST")

    def _msg_schema_ddl(self):
        import ldbc_snb as _ldbc
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
        import ldbc_snb as _ldbc
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
        return self.db.query("opencypher", text).to_json_list()

    def run_cypher_write(self, text):
        with self.db.transaction():
            self.db.command("opencypher", text)

    def close(self):
        self.db.close()


class ArcadeGraphServer(ArcadeGraphEmbedded):
    QUERY_LANGUAGE = "openCypher over HTTP (the engine also has its own SQL; DECISIONS #113)"
    name = "arcadedb_graph_server"
    # The served twin's txWalFlush is a JAVA_OPTS entry runner.py sets for the
    # strict class; no HTTP read-back exists and the string says so. Built in
    # connect() rather than here, because at_class must see the bare relaxed
    # string to map it and a class attribute would freeze one class at import.
    durability = bench_common.DURABILITY_ARCADEDB

    def connect(self):
        self.durability = (bench_common.at_class(bench_common.DURABILITY_ARCADEDB)
                           + bench_common.ARCADE_SERVER_DURABILITY_NOTE)
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
        body = {"language": language, "command": command}
        if endpoint == "query":
            body["limit"] = HTTP_LIMIT   # only the query endpoint takes a row cap
        r = self.rq.post(f"{self.base}/{endpoint}/bench", json=body,
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
        # Comment EXTENDS it, a unique id index on each). The LSQB Cypher is
        # identical to the embedded arm's, which is the tested one; only this
        # ingest text is the server arm's own. INFERRED, not run on the laptop.
        import ldbc_snb as _ldbc
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
        return self._http("query", "cypher", text)

    def run_cypher_write(self, text):
        self._http("command", "cypher", text)

    def close(self):
        pass


# ----------------------------------------------------------------- Neo4j
class Neo4jGraph(Base):
    QUERY_LANGUAGE = "Cypher over Bolt"
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

    # MESSAGE-HALF loader (DECISIONS #103b/#104), shared with Memgraph (which
    # inherits this whole path and overrides only the index DDL and the await).
    # Message is the SNB supertype of Post and Comment, expressed here as a
    # SECOND LABEL on every such node (`CREATE (n:Post:Message {id: r})`), so
    # `MATCH (m:Message)` reaches both. Vertices carry only `id`.
    def _msg_index_ddl(self, label):
        return f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)"

    def build_messages(self):
        import ldbc_snb as _ldbc
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
            return [dict(r) for r in s.run(text)]

    def run_cypher_write(self, text):
        with self.driver.session() as s:
            s.run(text).consume()

    def close(self):
        self.driver.close()


class MemgraphGraph(Neo4jGraph):
    """Memgraph 3.13.1 served (2026-09-17): the Neo4j arm's Bolt path, through
    the same neo4j driver, and the lane's Cypher VERBATIM. Every timed and
    untimed statement ran unchanged on the pinned image and every digest
    matched Neo4j's on the micro corpus (laptop probe, 2026-09-17). What
    differs is the schema statement (`CREATE INDEX ON :Person(id)` against
    Neo4j's `FOR (p:Person) ON (p.id)`), that the index is built synchronously
    so there is nothing to await, and that the server takes no auth by default.

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

    DURABILITY, READ BACK FROM SHOW CONFIG onto the row. storage-wal-enabled
    =true and storage-wal-file-flush-every-n-tx=100000 are the image defaults:
    the WAL is written at commit and fsynced every 100,000 transactions, which
    is the relaxed class. strace on the pinned image, build plus 3,009 commits:
    1 fsync at the default and 3,012 with --storage-wal-file-flush-every-n-tx=1,
    which is what the strict class sets (DECISIONS #90).
    """
    QUERY_LANGUAGE = "Cypher over Bolt"
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
        # the query timeout the runner disables so the lane's own budget is
        # the only censor (DECISIONS #82b), and the WAL flush interval (its
        # durability).
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
        self.durability = self._durability_readback(cfg)
        with self.driver.session() as s:
            s.run("CREATE INDEX ON :Person(id)").consume()

    @staticmethod
    def _durability_readback(cfg):
        """The engine's own answer, never the flag we sent (DECISIONS #81)."""
        wal = str(cfg.get("storage_wal_enabled"))
        every = str(cfg.get("storage_wal_file_flush_every_n_tx"))
        if wal == "true" and every == "100000":
            return bench_common.DURABILITY_MEMGRAPH
        if wal == "true" and every == "1":
            return bench_common.DURABILITY_MEMGRAPH_STRICT
        return (f"storage-wal-enabled={wal}, storage-wal-file-flush-every-n-tx={every}, "
                "which is neither class (DECISIONS #90)")

    def _await_indexes(self, s):
        """CREATE INDEX returns once the index is built; Memgraph has no
        db.awaitIndexes() and needs none."""

    def _msg_index_ddl(self, label):
        """Memgraph's label-index syntax, built synchronously (no await), the
        same one-line difference from Neo4j as the Person index in connect()."""
        return f"CREATE INDEX ON :{label}(id)"

    # LSQB q3 WITH ITS CLAUSES REORDERED (2026-09-18, DECISIONS #92/#93).
    # LSQB's text binds `MATCH (country:Country)` first and joins the KNOWS
    # triangle last; Memgraph's planner follows the written clause order, so
    # it expands every (person, city, country) chain three times over before
    # the triangle is applied, and the probe cell on the capped slice ran q3
    # for the remainder of its hour without answering (q1 and q2 had answered
    # in under two seconds). The same clauses in the other order, triangle
    # first, are the same query: each pattern stays in its own MATCH, so the
    # relationship-uniqueness rule (which a single merged MATCH would apply
    # across the three IS_PART_OF legs, dropping same-city triangles) is
    # unchanged. Proven by the digest against the reference on the slice.
    LSQB = {
        "lsqb_q3": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)"
                    "-[:KNOWS]-(person1) "
                    "MATCH (person1)-[:IS_LOCATED_IN]->(:City)-[:IS_PART_OF]->(country:Country) "
                    "MATCH (person2)-[:IS_LOCATED_IN]->(:City)-[:IS_PART_OF]->(country) "
                    "MATCH (person3)-[:IS_LOCATED_IN]->(:City)-[:IS_PART_OF]->(country) "
                    "RETURN count(*) AS n"),
    }

    def run_olap(self, qname):
        return self.run_cypher(self.LSQB.get(qname) or OLAP_QUERIES[qname])


def _int_or(v):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return v


class FalkorGraph(Base):
    """FalkorDB 4.20.6 served (2026-09-17): a Redis module, reached through the
    falkordb Python client over the Redis protocol (GRAPH.QUERY), the lane's
    Cypher VERBATIM. Every timed and untimed statement ran unchanged on the
    pinned image and every digest matched Neo4j's on the micro corpus (laptop
    probe, 2026-09-17); the only text of its own is the index statement,
    `CREATE INDEX FOR (p:Person) ON (p.id)`, Neo4j's without the name. One
    GRAPH.QUERY call is one transaction, so the write's CREATE-and-link and
    the DETACH DELETE are atomic without a session.

    THREE IMAGE DEFAULTS ARE OVERRIDDEN, each recorded on the row, because
    each would have measured something other than the query:
      * FALKORDB_ARGS in the image is "MAX_QUEUED_QUERIES 25 TIMEOUT 1000
        RESULTSET_SIZE 10000": a one-second query timeout and a 10,000-row
        result cap. The triangle count takes 1.2 s at MICRO and a whole-graph
        aggregate can take longer than a second, so the image's own default
        would have aborted it, and the row cap is the ArcadeDB 20,000-row
        trap in another engine (HTTP_LIMIT above). The runner sets
        RESULTSET_SIZE -1 and leaves TIMEOUT at the module default of 0, no
        limit, so the lane's budget and, behind it, the cell watchdog are the
        only censors (#82b).
      * THREAD_COUNT is sized from the HOST's logical cores: the log read
        "Thread pool created, using 16 threads" under a 12-CPU cpuset, while
        its OpenMP pool read 12 (FAIRNESS F6). The runner passes THREAD_COUNT
        from the cpuset and the row records what the server reports.
      * BROWSER=1 starts a Next.js process in the same container; BROWSER=0.

    DURABILITY IS REDIS PERSISTENCE, read back with CONFIG GET. The image
    default is RDB snapshots only (save "3600 1 300 100 60 10000", appendonly
    no): a write returns with nothing on disk until the next snapshot.
    strace on the pinned image, build plus 3,011 writes: 0 fsync at the
    default and 3,011 fdatasync with --appendonly yes --appendfsync always,
    which is what the strict class sets through REDIS_ARGS (DECISIONS #90).
    """
    QUERY_LANGUAGE = "Cypher over the Redis protocol"
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
        self.durability = self._durability_readback()
        self.g.query("CREATE INDEX FOR (p:Person) ON (p.id)")

    def _gcfg(self, name):
        """GRAPH.CONFIG GET, which answers [name, value]."""
        v = self.db.config_get(name)
        return v[-1] if isinstance(v, (list, tuple)) else v

    def _durability_readback(self):
        c = self.conn.config_get("appendonly")
        c.update(self.conn.config_get("appendfsync"))
        c.update(self.conn.config_get("save"))
        ao, fsync, save = c.get("appendonly"), c.get("appendfsync"), c.get("save")
        if ao == "no" and save == "3600 1 300 100 60 10000":
            return bench_common.DURABILITY_FALKORDB
        if ao == "yes" and fsync == "always":
            return bench_common.DURABILITY_FALKORDB_STRICT
        return (f"appendonly={ao}, appendfsync={fsync}, save={save!r}, "
                "which is neither class (DECISIONS #90)")

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

    # MESSAGE-HALF loader (DECISIONS #103b/#104). Same UNWIND shape as Neo4j
    # over GRAPH.QUERY; Message is a second label (FalkorDB 4.x supports
    # multiple labels per node), the index is Neo4j's without the name (as the
    # Person index above). INFERRED, not run: the persons+KNOWS path and every
    # LSQB query text are identical to the tested Neo4j/ArcadeDB arms, so only
    # this ingest text is unverified; the bench host confirms (COMPARATOR-DIALECTS).
    def build_messages(self):
        import ldbc_snb as _ldbc
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

    # LSQB q1 WITH EVERY NODE NAMED (2026-09-18, DECISIONS #92). The canonical
    # text binds none of its nine nodes, and on FalkorDB 4.20.6 the anonymous
    # chain loses PATH MULTIPLICITY across its intermediates: on the capped SF1
    # slice the eight-label chain answered 2,393 against 300,871 on every
    # other engine, and cutting it short showed where. Country<-City<-Person
    # is 2,000 on both spellings, but Country<-City<-Person<-Forum is 69,114
    # anonymous against 101,903 named, and 69,114 is exactly
    # `count(DISTINCT [id(country), id(forum)])`: the eliminated middle nodes
    # are folded into a boolean product. Naming the nodes (or, equally, the
    # edges) restores 300,871 on the same server, so the named spelling is
    # the same query and this is the text FalkorDB runs. Every other LSQB
    # query names the nodes it chains through and agreed unchanged.
    LSQB = {
        "lsqb_q1": ("MATCH (co:Country)<-[:IS_PART_OF]-(ci:City)<-[:IS_LOCATED_IN]-(p:Person)"
                    "<-[:HAS_MEMBER]-(f:Forum)-[:CONTAINER_OF]->(po:Post)<-[:REPLY_OF]-(cm:Comment)"
                    "-[:HAS_TAG]->(t:Tag)-[:HAS_TYPE]->(tc:TagClass) RETURN count(*) AS n"),
    }

    def run_olap(self, qname):
        return self.run_cypher(self.LSQB.get(qname) or OLAP_QUERIES[qname])

    def run_cypher(self, text):
        res = self.g.query(text)
        # header entries are [type, name]; the RETURN aliases are the names
        # the digest compares against.
        cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
        return [dict(zip(cols, row)) for row in res.result_set]

    def run_cypher_write(self, text):
        self.g.query(text)

    def close(self):
        self.conn.close()


# --------------------------------------------------------------- LadybugDB
class LadybugGraph(Base):
    QUERY_LANGUAGE = "Cypher, embedded"
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
        # CSV COPY — LadybugDB's native bulk path
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

    # MESSAGE-HALF loader + LSQB queries (DECISIONS #103b/#104). INFERRED, NOT
    # RUN: LadybugDB (Kùzu) has no type inheritance and no multi-label, so it
    # cannot run the canonical Cypher's `(:Message)`; instead it uses LSQB's own
    # published Kùzu model (github.com/ldbc/lsqb/tree/main/ladybug) -- a single
    # Message node table that holds every Post and Comment, and one typed REL
    # table per relationship. Post and Comment are therefore folded into Message
    # here, and the LSQB queries below are LSQB's ladybug/*.cypher adapted to
    # this lane's `id` primary key and to UNDIRECTED knows (`-[:R]-`), because
    # this lane stores each KNOWS once and the canonical queries traverse it
    # undirected (the tested ArcadeDB/Neo4j arms do). The bench host confirms the
    # digests against the Cypher arms (COMPARATOR-DIALECTS.md).
    #
    # Generic (rel, src_label, dst_label) tuples map onto Kùzu's typed rel
    # tables; Post/Comment both resolve to Message. q2 additionally needs the
    # comment->post reply subset, which LSQB carries as its own Comment_replyOf_Post
    # table, so that generic edge is loaded into BOTH tables.
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
    _REL_ENDPOINTS = {   # Kùzu needs FROM/TO node tables in the DDL
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
        import ldbc_snb as _ldbc
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
        # rel CSVs, one per Kùzu rel table (several generic edges may share one)
        rel_files = {}
        for rel, src_label, dst_label, gen in mc.edge_spec():
            targets = [self._REL_TABLE[(rel, src_label, dst_label)]]
            if (rel, src_label, dst_label) == ("REPLY_OF", "Comment", "Post"):
                targets.append("Comment_replyOf_Post")  # q2's comment->post subset
            pairs = list(gen())
            ecount += len(pairs)   # the edge is counted once even if stored twice
            for rt in targets:
                w = rel_files.get(rt)
                if w is None:
                    fh = open(f"/tmp/l2_lady_rel_{rt}.csv", "a", newline="")
                    rel_files[rt] = (fh, _csv.writer(fh))
                    w = rel_files[rt]
                for s, d in pairs:
                    w[1].writerow([s, d])
        for rt, (fh, _w) in rel_files.items():
            fh.close()
            self.conn.execute(f"COPY {rt} FROM '/tmp/l2_lady_rel_{rt}.csv'")
            os.unlink(f"/tmp/l2_lady_rel_{rt}.csv")
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    # LSQB in LadybugDB's typed-rel-table Cypher (see the note above). Undirected
    # knows to match the canonical queries the tested arms run.
    LSQB = {
        "lsqb_q1": ("MATCH (:Country)<-[:City_isPartOf_Country]-(:City)<-[:Person_isLocatedIn_City]-(:Person)"
                    "<-[:Forum_hasMember_Person]-(:Forum)-[:Forum_containerOf_Message]->(:Message)"
                    "<-[:Message_replyOf_Message]-(:Message)-[:Message_hasTag_Tag]->(:Tag)"
                    "-[:Tag_hasType_TagClass]->(:TagClass) RETURN count(*) AS n"),
        "lsqb_q2": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person), "
                    "(person1)<-[:Message_hasCreator_Person]-(comment:Message)-[:Comment_replyOf_Post]->"
                    "(post:Message)-[:Message_hasCreator_Person]->(person2) RETURN count(*) AS n"),
        "lsqb_q3": ("MATCH (country:Country) "
                    "MATCH (person1:Person)-[:Person_isLocatedIn_City]->(:City)-[:City_isPartOf_Country]->(country) "
                    "MATCH (person2:Person)-[:Person_isLocatedIn_City]->(:City)-[:City_isPartOf_Country]->(country) "
                    "MATCH (person3:Person)-[:Person_isLocatedIn_City]->(:City)-[:City_isPartOf_Country]->(country) "
                    "MATCH (person1)-[:KNOWS]-(person2)-[:KNOWS]-(person3)"
                    "-[:KNOWS]-(person1) RETURN count(*) AS n"),
        "lsqb_q4": ("MATCH (:Tag)<-[:Message_hasTag_Tag]-(message:Message)-[:Message_hasCreator_Person]->(creator:Person), "
                    "(message)<-[:Person_likes_Message]-(liker:Person), "
                    "(message)<-[:Message_replyOf_Message]-(comment:Message) RETURN count(*) AS n"),
        "lsqb_q5": ("MATCH (tag1:Tag)<-[:Message_hasTag_Tag]-(message:Message)<-[:Message_replyOf_Message]-"
                    "(comment:Message)-[:Message_hasTag_Tag]->(tag2:Tag) WHERE tag1.id <> tag2.id RETURN count(*) AS n"),
        "lsqb_q6": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-"
                    "(person3:Person)-[:Person_hasInterest_Tag]->(tag:Tag) WHERE person1.id <> person3.id RETURN count(*) AS n"),
        "lsqb_q7": ("MATCH (:Tag)<-[:Message_hasTag_Tag]-(message:Message)-[:Message_hasCreator_Person]->(creator:Person) "
                    "OPTIONAL MATCH (message)<-[:Person_likes_Message]-(liker:Person) "
                    "OPTIONAL MATCH (message)<-[:Message_replyOf_Message]-(comment:Message) RETURN count(*) AS n"),
        "lsqb_q8": ("MATCH (tag1:Tag)<-[:Message_hasTag_Tag]-(message:Message)<-[:Message_replyOf_Message]-"
                    "(comment:Message)-[:Message_hasTag_Tag]->(tag2:Tag) "
                    "WHERE NOT (comment)-[:Message_hasTag_Tag]->(tag1) AND tag1.id <> tag2.id RETURN count(*) AS n"),
        "lsqb_q9": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-"
                    "(person3:Person)-[:Person_hasInterest_Tag]->(tag:Tag) "
                    "WHERE NOT (person1)-[:KNOWS]-(person3) AND person1.id <> person3.id RETURN count(*) AS n"),
    }

    def run_olap(self, qname):
        # The five hand-written analytics queries run the shared Cypher; the nine
        # LSQB queries need LadybugDB's typed-rel-table spelling.
        return self.run_cypher(self.LSQB.get(qname) or OLAP_QUERIES[qname])

    def run_cypher(self, text):
        # Rows come back positional, in the RETURN clause's order, which is the
        # declared column order the digest compares against.
        return [list(r) for r in self.conn.execute(text)]


class DuckpgqGraph(Base):
    """DuckDB with the DuckPGQ community extension (embedded, in-process through
    the duckdb Python package on the pinned dbbench:duckdb image, duckdb==1.5.4).
    The persons-and-knows data lives in two DuckDB tables; a PROPERTY GRAPH over
    them answers every graph read in SQL/PGQ (`GRAPH_TABLE ... MATCH`), and the
    writes are plain SQL on the underlying tables, one statement group per
    transaction (DECISIONS #103d, #92).

    WHY 1.5.4 AND NOT 1.5.5. The community-extensions registry has a DuckPGQ
    build for 1.5.4 and none for 1.5.5 or 1.6.0, so the page pins every DuckDB
    arm to 1.5.4 (DECISIONS #103d): `INSTALL duckpgq FROM community` on 1.5.5
    answers HTTP 404. Verified on the image, INSTALL/LOAD both succeed on 1.5.4.

    NOTHING IS UNEXPRESSIBLE ON THIS LANE. All twelve questions run in SQL/PGQ
    and every digest matched the Cypher engines' on the micro corpus (laptop,
    2026-09-17). The point lookup, one/two/three hops and the three-hop visited
    probe are `GRAPH_TABLE MATCH` patterns; the five analytics queries are a
    MATCH feeding an outer GROUP BY; the triangle count is the natural 3-cycle
    pattern `(a)->(b)->(c)->(a)` with `a.id` the smallest, exact against the
    harness's own enumeration (2,776 at 2,000 persons, 2,999 at 600). DuckPGQ
    requires EVERY edge pattern to bind a variable -- a bare `-[:knows]->` raises
    "All patterns must bind to a variable" -- so each hop names its edge. The
    same rule for LABELS (2026-09-18, LSQB q2/q3/q4): a vertex variable that
    is re-used in a second pattern element must repeat its label, `(p1:Person)`
    every time and never a bare `(p1)`, or the extension raises "All patterns
    must bind to a label"; the triangle count's closing `(a:Person)` is the
    same rule already obeyed. The
    property graph is a live view over the tables, so a plain-SQL insert or
    delete is visible to the next MATCH with no re-definition (verified). The
    UNEXPRESSIBLE hook stays and stays empty (DECISIONS #88), for the next query
    added to OLAP_QUERIES.

    DURABILITY is DuckDB's own, with no knob (DECISIONS #90): fsync at commit,
    the same string the document, time-series and dense-VSS DuckDB arms record,
    printed unchanged in both durability classes.

    THREAD POOL fitted to the cpuset (FAIRNESS F6): `PRAGMA threads` from
    `sched_getaffinity`, the fix every other DuckDB arm carries, recorded as
    `duckpgq_threads`.
    """
    QUERY_LANGUAGE = "SQL/PGQ (GRAPH_TABLE ... MATCH)"
    name = "duckpgq_graph"
    durability = bench_common.DURABILITY_DUCKDB
    DBPATH = "/tmp/l2_duckpgq.db"

    # PGQ reads: {id} formatted in as a literal, like the lane's Cypher, so
    # every engine stays on the same query-plan surface. Every edge binds a
    # variable (DuckPGQ requires it); the COLUMNS clause names the answer in the
    # declared digest order (graph_common.READ_DIGEST).
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
        "hop3f": ("SELECT count(DISTINCT x) AS n FROM GRAPH_TABLE (pg "
                  "MATCH (p:Person WHERE p.id = {id})-[k1:knows]->(m1:Person)"
                  "-[k2:knows]->(m2:Person)-[k3:knows]->(x:Person WHERE x.age > 30) "
                  "COLUMNS (x.id AS x))"),
    }
    VISITED = ("SELECT count(DISTINCT x) AS n FROM GRAPH_TABLE (pg "
               "MATCH (p:Person WHERE p.id = {id})-[k1:knows]->(m1:Person)"
               "-[k2:knows]->(m2:Person)-[k3:knows]->(x:Person) COLUMNS (x.id AS x))")
    OLAP = {
        "top_degree": ("SELECT id, count(*) AS d FROM GRAPH_TABLE (pg "
                       "MATCH (p:Person)-[k:knows]->(f:Person) COLUMNS (p.id AS id)) "
                       "GROUP BY id ORDER BY d DESC, id ASC LIMIT 10"),
        "same_city_edges": ("SELECT c, count(*) AS n FROM GRAPH_TABLE (pg "
                            "MATCH (a:Person)-[k:knows]->(b:Person) WHERE a.city = b.city "
                            "COLUMNS (a.city AS c)) GROUP BY c ORDER BY n DESC, c ASC LIMIT 10"),
        "friend_age_by_city": ("SELECT c, avg(fage) AS a, count(*) AS n FROM GRAPH_TABLE (pg "
                               "MATCH (p:Person)-[k:knows]->(f:Person) "
                               "COLUMNS (p.city AS c, f.age AS fage)) "
                               "GROUP BY c ORDER BY n DESC, c ASC LIMIT 10"),
        # Degree distribution: the per-person out-degree, then a histogram over
        # it. Two levels, the inner GROUP BY over the MATCH's one-row-per-edge
        # and the outer over the degrees; persons with no outgoing KNOWS are
        # outside the MATCH and so outside the histogram, matching the Cypher.
        "degree_dist": ("SELECT deg, count(*) AS n FROM (SELECT id, count(*) AS deg "
                        "FROM GRAPH_TABLE (pg MATCH (p:Person)-[k:knows]->(f:Person) "
                        "COLUMNS (p.id AS id)) GROUP BY id) GROUP BY deg ORDER BY deg"),
        # The triangle count as the 3-cycle pattern, closing back on `a`; the
        # id ordering keeps `a` the smallest of the three so each triangle is
        # counted once, the same rule the Cypher and every other adapter apply.
        "triangles": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg "
                      "MATCH (a:Person)-[k1:knows]->(b:Person)-[k2:knows]->(c:Person)"
                      "-[k3:knows]->(a:Person) WHERE a.id < b.id AND a.id < c.id "
                      "COLUMNS (a.id AS aid, b.id AS bid, c.id AS cid))"),
    }
    # Nothing on this lane is unexpressible in SQL/PGQ. The hook stays, and
    # stays empty (DECISIONS #88), for the next query added to OLAP_QUERIES.
    UNEXPRESSIBLE = {}

    def connect(self):
        import duckdb
        if os.path.exists(self.DBPATH):
            os.remove(self.DBPATH)
        self.cx = duckdb.connect(self.DBPATH)
        # F6: DuckDB sizes its pool from the host under the cpuset; only
        # sched_getaffinity sees the mask. Same fix as the other DuckDB arms.
        self._threads = len(os.sched_getaffinity(0))
        self.cx.execute(f"PRAGMA threads={self._threads}")
        # The community DuckPGQ build for the pinned 1.5.4 (404 on 1.5.5).
        self.cx.execute("INSTALL duckpgq FROM community; LOAD duckpgq;")
        _ext = self.cx.execute(
            "SELECT extension_version FROM duckdb_extensions() "
            "WHERE extension_name = 'duckpgq'").fetchall()
        _ev = _ext[0][0] if _ext else "?"
        self.version = f"duckdb:{duckdb.__version__} + duckpgq:{_ev}"
        self.row_extra = {"duckpgq_threads": self._threads,
                          "duckpgq_extension_version": _ev}
        # Tables first, then the property graph over them (empty is fine: the
        # graph is a live view, so the build below fills it). Person keyed by id
        # so the point lookup and the plain-SQL writes reach one row by key.
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
        # AFTER the load, like MongoDB's graph arm: src is every write's edge
        # lookup, dst is the inbound side the delete needs. PGQ builds its own
        # traversal structures, so these serve only the plain-SQL write/delete.
        self.cx.execute("CREATE INDEX k_src ON knows(src)")
        self.cx.execute("CREATE INDEX k_dst ON knows(dst)")

    # MESSAGE-HALF loader + LSQB SQL/PGQ (DECISIONS #103b/#104). INFERRED, NOT
    # RUN on the laptop (no duckdb wheel here). It follows LSQB's own published
    # DuckPGQ implementation (github.com/ldbc/lsqb/tree/main/pgq): separate Post,
    # Comment and Message vertex tables (Message = Post UNION ALL Comment), one
    # base edge table per relationship plus Message-level UNION tables for the
    # queries that use the supertype, and the property graph redefined over all
    # of them with a LABEL per edge table. The anti-joins (q8, q9) are expressed
    # the way LSQB does -- a GRAPH_TABLE match exposing the ids through COLUMNS,
    # LEFT JOINed to the edge table with an IS NULL filter -- because SQL/PGQ has
    # no inline NOT-pattern. Every edge binds a variable (DuckPGQ requires it).
    # knows is undirected to match the canonical queries. Bench host confirms.
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
        import ldbc_snb as _ldbc
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
            before = self.cx.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            self._bulk(table, ["s", "d"], edge_gen[key]())
            ecount += self.cx.execute(f"SELECT count(*) FROM {table}").fetchone()[0] - before
        # Message-level UNION edge tables for the supertype queries.
        self.cx.execute("CREATE TABLE dp_message_hastag AS "
                        "SELECT s, d FROM dp_post_hastag_tag UNION ALL SELECT s, d FROM dp_comment_hastag_tag")
        self.cx.execute("CREATE TABLE dp_message_hascreator AS "
                        "SELECT s, d FROM dp_post_hascreator_person UNION ALL SELECT s, d FROM dp_comment_hascreator_person")
        self.cx.execute("CREATE TABLE dp_person_likes_message AS "
                        "SELECT s, d FROM dp_person_likes_post UNION ALL SELECT s, d FROM dp_person_likes_comment")
        self.cx.execute("CREATE TABLE dp_message_replyof_message AS "
                        "SELECT s, d FROM dp_comment_replyof_post UNION ALL SELECT s, d FROM dp_comment_replyof_comment")
        # Redefine the property graph over everything (CREATE PROPERTY GRAPH
        # cannot be altered). The persons+KNOWS labels are unchanged, so the five
        # hand-written queries still run against `pg`.
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

    # LSQB in SQL/PGQ (see the note above). count(*) over a GRAPH_TABLE match;
    # the anti-joins are a LEFT JOIN ... IS NULL over the match's COLUMNS output.
    LSQB = {
        "lsqb_q1": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(co:Country)<-[e1:City_isPartOf_Country]-(ci:City)<-[e2:Person_isLocatedIn]-(p:Person)"
                    "<-[e3:hasMember]-(f:Forum)-[e4:containerOf]->(po:Post)<-[e5:replyOf_Post]-(cm:Comment)"
                    "-[e6:Comment_hasTag]->(t:Tag)-[e7:hasType]->(tc:TagClass) COLUMNS (p.id AS x))"),
        "lsqb_q2": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(p1:Person)-[k:knows]-(p2:Person), "
                    "(p1:Person)<-[hc:Comment_hasCreator]-(cm:Comment)-[ro:replyOf_Post]->(po:Post)"
                    "-[pc:Post_hasCreator]->(p2:Person) COLUMNS (p1.id AS x))"),
        "lsqb_q3": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(p1:Person)-[e1:Person_isLocatedIn]->(c1:City)-[e2:City_isPartOf_Country]->(co:Country), "
                    "(p2:Person)-[e3:Person_isLocatedIn]->(c2:City)-[e4:City_isPartOf_Country]->(co:Country), "
                    "(p3:Person)-[e5:Person_isLocatedIn]->(c3:City)-[e6:City_isPartOf_Country]->(co:Country), "
                    "(p1:Person)-[k1:knows]-(p2:Person)-[k2:knows]-(p3:Person)-[k3:knows]-(p1:Person) COLUMNS (p1.id AS x))"),
        "lsqb_q4": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(t:Tag)<-[mht:Message_hasTag]-(m:Message)-[mhc:Message_hasCreator]->(creator:Person), "
                    "(m:Message)<-[lm:likes_Message]-(liker:Person), "
                    "(m:Message)<-[rom:replyOf_Message]-(cm:Comment) COLUMNS (m.id AS x))"),
        "lsqb_q5": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(tag1:Tag)<-[ht:Message_hasTag]-(m:Message)<-[ro:replyOf_Message]-(cm:Comment)"
                    "-[ht1:Comment_hasTag]->(tag2:Tag) WHERE tag1.id <> tag2.id COLUMNS (m.id AS x))"),
        "lsqb_q6": ("SELECT count(*) AS n FROM GRAPH_TABLE (pg MATCH "
                    "(p1:Person)-[k1:knows]-(p2:Person)-[k2:knows]-(p3:Person)-[hi:hasInterest]->(t:Tag) "
                    "WHERE p1.id <> p3.id COLUMNS (p1.id AS x))"),
        # lsqb_q7 is handled specially in run_olap (its two OPTIONAL MATCHes are
        # a left-join fan-out, not a single GRAPH_TABLE pattern).
        "lsqb_q8": ("SELECT count(*) AS n FROM ("
                    "SELECT g.t1 AS t1, g.cid AS cid, g.t2 AS t2 FROM GRAPH_TABLE (pg MATCH "
                    "(tag1:Tag)<-[ht:Message_hasTag]-(m:Message)<-[ro:replyOf_Message]-(cm:Comment)"
                    "-[ht1:Comment_hasTag]->(tag2:Tag) COLUMNS (tag1.id AS t1, cm.id AS cid, tag2.id AS t2)) g "
                    "LEFT JOIN dp_comment_hastag_tag cht ON cht.s = g.cid AND cht.d = g.t1 "
                    "WHERE g.t2 <> g.t1 AND cht.s IS NULL)"),
        "lsqb_q9": ("SELECT count(*) AS n FROM ("
                    "SELECT g.p1 AS p1, g.p3 AS p3 FROM GRAPH_TABLE (pg MATCH "
                    "(p1:Person)-[k1:knows]-(p2:Person)-[k2:knows]-(p3:Person)-[hi:hasInterest]->(t:Tag) "
                    "COLUMNS (p1.id AS p1, p3.id AS p3)) g "
                    "LEFT JOIN knows ka ON ka.src = g.p1 AND ka.dst = g.p3 "
                    "LEFT JOIN knows kb ON kb.src = g.p3 AND kb.dst = g.p1 "
                    "WHERE g.p1 <> g.p3 AND ka.src IS NULL AND kb.src IS NULL)"),
    }

    def run_read(self, op, pid):
        return self.cx.execute(self.READS[op].format(id=pid)).fetchall()

    def run_visited(self, pid):
        return self.cx.execute(self.VISITED.format(id=pid)).fetchall()

    def run_olap(self, qname):
        if qname == "lsqb_q7":
            # q7's two OPTIONAL MATCHes are a left-join fan-out that a single
            # GRAPH_TABLE cannot express; done as the base match LEFT JOINed to
            # the likes and reply edge tables, counting the product (the OPTIONAL
            # semantics: one row per (message, liker?, reply?) combination).
            return self.cx.execute(
                "SELECT count(*) AS n FROM (SELECT g.mid AS mid FROM GRAPH_TABLE (pg MATCH "
                "(t:Tag)<-[mht:Message_hasTag]-(m:Message)-[mhc:Message_hasCreator]->(creator:Person) "
                "COLUMNS (m.id AS mid, t.id AS tid)) g "
                "LEFT JOIN dp_person_likes_message lm ON lm.d = g.mid "
                "LEFT JOIN dp_message_replyof_message rm ON rm.d = g.mid)").fetchall()
        q = self.LSQB.get(qname)
        return self.cx.execute(q).fetchall() if q else self.cx.execute(self.OLAP[qname]).fetchall()

    def person_scan(self, id_from):
        return self.cx.execute(
            f"SELECT id, name, age, city FROM Person WHERE id >= {id_from} "
            "ORDER BY id").fetchall()

    def run_write(self, pid, new_id):
        # One transaction, the Cypher's CREATE-and-link: the person and the edge
        # either both exist or neither does.
        self.cx.execute("BEGIN")
        self.cx.execute("INSERT INTO Person VALUES (?, ?, 33, 'city_0')",
                        [new_id, f"w{new_id}"])
        self.cx.execute("INSERT INTO knows VALUES (?, ?, 2026)", [pid, new_id])
        self.cx.execute("COMMIT")

    def run_update(self, new_id):
        self.cx.execute("UPDATE Person SET age = ? WHERE id = ?", [UPDATE_AGE, new_id])

    def run_delete(self, new_id):
        # DETACH DELETE: the edges touching the vertex, then the vertex, one txn.
        self.cx.execute("BEGIN")
        self.cx.execute("DELETE FROM knows WHERE src = ? OR dst = ?", [new_id, new_id])
        self.cx.execute("DELETE FROM Person WHERE id = ?", [new_id])
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
    QUERY_LANGUAGE = "SurrealQL, embedded"
    name = "surrealdb_graph"
    URL = "surrealkv:///tmp/l2_surrealkv"

    def _open(self):
        # SURREAL_SYNC_DATA must be set before the datastore opens (#90).
        self.durability = bench_common.at_class(bench_common.DURABILITY_SURREAL_EMBEDDED)
        surreal_common.apply_durability()
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
        elif op == "hop3f":
            r = self.db.query(f"SELECT array::len(array::distinct(->knows->person->knows->person->knows->(person WHERE age > 30))) AS n FROM ONLY person:{pid}")
        else:
            r = self.db.query(f"SELECT array::len(array::distinct(->knows->person->knows->person)) AS n FROM ONLY person:{pid}")
        return self._rows(r)

    def run_visited(self, pid):
        return self._rows(self.db.query(
            f"SELECT array::len(array::distinct(->knows->person->knows->person->knows->person)) AS n "
            f"FROM ONLY person:{pid}"))

    def run_update(self, new_id):
        self.db.query(f"UPDATE person:{new_id} SET age = {UPDATE_AGE}")

    def person_scan(self, id_from):
        return self._rows(self.db.query(
            f"SELECT pid, name, age, city FROM person WHERE pid >= {id_from}"))

    def run_write(self, pid, new_id):
        self.db.query(f"CREATE person:{new_id} SET pid = {new_id}, name = 'w{new_id}', age = 33, city = 'city_0'; "
                      f"RELATE person:{pid}->knows->person:{new_id} SET since = 2026")

    def run_delete(self, new_id):
        # One transaction: the edges into the record, then the record.
        # person:{id}<->knows deletes the edges touching the record through
        # the graph (laptop, 2026-09-14: the WHERE form scanned the edge table,
        # 777 ms at micro); then the record, one transaction.
        self.db.query(f"BEGIN; DELETE person:{new_id}<->knows; DELETE person:{new_id}; COMMIT;")

    OLAP = {
        "top_degree": "SELECT pid, count(->knows) AS d FROM person ORDER BY d DESC, pid ASC LIMIT 10",
        # subquery form: on core 2.3.10 ORDER BY after GROUP BY sorted by the group
        # key, not n (laptop smoke, 2026-09-11); 3.2.4 accepts both forms
        "same_city_edges": "SELECT * FROM (SELECT in.city AS c, count() AS n FROM knows WHERE in.city = out.city GROUP BY c) ORDER BY n DESC, c ASC LIMIT 10",
        "friend_age_by_city": "SELECT * FROM (SELECT in.city AS c, math::mean(out.age) AS a, count() AS n FROM knows GROUP BY c) ORDER BY n DESC, c ASC LIMIT 10",
        # 2026-10 (#82b). The degree distribution is a group-by over a computed
        # out-degree; degree zero is excluded to match the Cypher MATCH, which
        # does not reach a person with no outgoing KNOWS.
        # TWO SUBQUERIES, not one GROUP BY on a computed alias. The one-level
        # form `SELECT count(->knows) AS deg, count() AS n FROM person GROUP BY
        # deg` did NOT group: it returned 2,000 rows, one per person, each
        # reading (1,1), where the Cypher engines return one row per distinct
        # degree. The digest caught it on its first comparison, which is what
        # #88 is for. The degree is computed in the inner query and grouped in
        # the outer one, so the group key is a plain field by the time GROUP BY
        # sees it.
        "degree_dist": ("SELECT * FROM (SELECT deg, count() AS n FROM "
                        "(SELECT count(->knows) AS deg FROM person) WHERE deg > 0 "
                        "GROUP BY deg) ORDER BY deg"),
        # THE TRIANGLE COUNT, WHICH THIS ADAPTER DECLARED UNEXPRESSIBLE UNTIL
        # 2026-09-14. The old reason -- "arrow traversal returns a path's
        # endpoint set and names no intermediate vertex, so the per-path id
        # ordering cannot be written" -- was true about the construct we tried
        # and false about the language. It is written here without naming an
        # intermediate vertex at all, by turning the path pattern into a set
        # intersection over the edge table, which is the shape SurrealQL does
        # have. Same reading as the degree distribution (#82b): a first failure
        # is evidence about our fluency, not about the engine.
        #
        # WHY IT COUNTS EACH TRIANGLE ONCE, which is the whole of the question.
        # The Cypher is MATCH (a)->(b)->(c)->(a) WHERE a.id < b.id AND
        # a.id < c.id, so `a` is the smallest id of the three and exactly one
        # of a directed 3-cycle's three rotations survives. Here one row of
        # `knows` IS the (a -> b) leg: `in` is a, `out` is b, `WHERE in < out`
        # is a.id < b.id, and the third vertex c is any record that b points at
        # and that points at a -- that is N+(b) INTERSECT N-(a), spelled
        # `out->knows.out` and `in<-knows.in`. `|$c| $c > in` is a.id < c.id.
        # So each row contributes the triangles whose smallest-id vertex is its
        # own `in`, and summing over the rows counts every triangle once.
        # Verified against the harness's own Python triangle enumeration on the
        # shared generator at 200/300/600/1000/2000 persons, on core 2.3.10 and
        # on the 3.2.4 server: 1836 / 2452 / 2999 / 2469 / 2776, exact on every
        # one, which is what DECISIONS #88's digest then checks against Neo4j,
        # ArcadeDB, LadybugDB and ArangoDB.
        #
        # THREE CONSTRUCTS, EACH FROM THE DOCUMENTATION, each of which the
        # first attempt got wrong:
        #  - record ids are ordered and compare directly, so `in < out` needs
        #    no .id projection and sorts person:4 after person:30 numerically
        #    (surrealdb.com/docs/surrealql/datamodel/ids).
        #  - array::intersect(a, b) keeps a's duplicates and needs no closure
        #    (surrealdb.com/docs/surrealql/functions/database/array).
        #  - array::filter's closure CAPTURES the fields of the row being
        #    projected, which is how `$c > in` reaches the edge's own `in`.
        #    `$parent` does NOT: inside an idiom filter or a closure it
        #    resolves to nothing and the comparison silently passes, which is
        #    the bug that made the first ordered attempt return 3,656 for a
        #    graph with 2,452 triangles. Documented for subqueries only
        #    (surrealdb.com/docs/surrealql/parameters).
        #
        # AND WHY `.out`/`.in` RATHER THAN `->person`/`<-person`: both spell
        # the same set and both return the same count, but `->knows->person`
        # fetches every neighbour's whole record while `->knows.out` reads the
        # destination id off the edge. On core 2.3.10 that is 16.4 s against
        # 85.9 s at 1,000 persons (laptop, 2026-09-14). This form costs about
        # |E|^1.1 on the shared generator -- 38.1 s over 40,833 edges, 227.0 s
        # over 206,713 -- so SF10's roughly 1.9M edges EXTRAPOLATE to a cold
        # pass of tens of minutes, and the arrow form to several times that.
        # Extrapolated, not measured: no SF10 cell has run since this query
        # existed, and the extrapolation crosses a corpus change as well as a
        # size one, since a triangle count's real cost is sum(deg(u)*deg(v))
        # over the edges and LDBC's degree distribution is not the
        # generator's. The 3.2.4 server inverts the spelling preference, and
        # its subclass overrides this entry for that reason.
        "triangles": ("SELECT math::sum(n) AS n FROM ("
                      "SELECT array::len(array::filter(array::intersect("
                      "out->knows.out, in<-knows.in), |$c| $c > in)) AS n "
                      "FROM knows WHERE in < out) GROUP ALL"),
    }
    # Nothing on this lane is unexpressible in SurrealQL any more. The hook
    # stays, and stays empty, because DECISIONS #88 is about declaring an
    # absence rather than skipping it silently, and the next query added to
    # OLAP_QUERIES may need it.
    UNEXPRESSIBLE = {}

    # MESSAGE-HALF loader + LSQB in SurrealQL (DECISIONS #103b/#104). INFERRED,
    # NOT RUN, and the least certain of all the arms: SurrealQL has no count(*)
    # over a multi-way pattern, so each LSQB count below is built from graph
    # traversal and array lengths, the same shape the triangle count uses, and
    # LSQB publishes no SurrealDB reference. Posts and Comments share a `message`
    # table (an `mtype` field marks which); each relationship is a RELATION edge
    # table; KNOWS is traversed undirected (`<->knows<->`). These are good-faith
    # translations for the bench host to CONFIRM against the Cypher arms or, per
    # DECISIONS #92, to replace with a declared unexpressible carrying the real
    # error -- they are NOT claimed correct here (COMPARATOR-DIALECTS.md).
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
        import ldbc_snb as _ldbc
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

    # Good-faith SurrealQL, one count per query (see the note above). Each sums,
    # over a driving table, the number of pattern completions reachable from
    # each record; `<->knows<->person` is undirected friendship.
    # LSQB IN SURREALQL (2026-09-18, DECISIONS #92/#104a), every one proven
    # against the ArcadeDB/Neo4j reference on the capped SF1 slice. What the
    # first draft got wrong, and the two facts of the dialect that decided
    # the rewrite (measured on core 2.3.10 through the probe cell):
    #   * `<->knows<->person` is NOT the undirected neighbourhood. From a
    #     person it yields BOTH endpoints of every incident edge, so the list
    #     is 4x the edge count and 1,574 of 2,000 persons contain themselves.
    #     The undirected neighbourhood is `->knows->person` concatenated with
    #     `<-knows<-person` (one edge per unordered pair in LDBC, so no
    #     duplicates), which is what every friend-of-friend query below uses.
    #   * A multi-hop traversal keeps PATH multiplicity: the directed two-hop
    #     `->knows->person->knows->person` summed to exactly the 60,345 paths
    #     an independent enumeration counts, so a chain's length is a match
    #     count, the same thing Cypher's count(*) is. A traversal also chains
    #     off a parenthesised array expression, `(array::complement(a, b))
    #     ->hasinterest->tag`, which is what the anti-joins need.
    # Each query is a sum over the edge or vertex that pins the pattern, of a
    # product of independent leg counts (q1, q4, q7) or a set operation on
    # neighbourhoods (q2, q3, q5, q6, q8, q9), every one an exact count of
    # the Cypher's matches rather than an approximation of it.
    _NIN = "array::concat(in->knows->person, in<-knows<-person)"
    _NOUT = "array::concat(out->knows->person, out<-knows<-person)"
    LSQB = {
        # q1: pin the comment->post REPLY_OF edge; the tag/tagclass legs hang
        # off the comment, the forum/person/city/country legs off the post.
        "lsqb_q1": ("SELECT math::sum(array::len(in->hastag->tag->hastype->tagclass) * "
                    "array::len(out<-containerof<-forum->hasmember->person->islocatedin->city"
                    "->ispartof->country)) AS n FROM replyof WHERE out.mtype = 'post' GROUP ALL"),
        # q2: the comment's creator is a KNOWS-neighbour (either direction) of
        # the post's creator. One creator each, so the intersection is 0 or 1.
        "lsqb_q2": ("SELECT math::sum(array::len(array::intersect(in->hascreator->person, "
                    "out->hascreator->person->knows->person)) + array::len(array::intersect("
                    "in->hascreator->person, out->hascreator->person<-knows<-person))) AS n "
                    "FROM replyof WHERE out.mtype = 'post' GROUP ALL"),
        # q3: per KNOWS edge whose ends share a country, the common neighbours
        # in that country; each triangle sits on three edges and the Cypher
        # counts its six orderings, hence the 2x.
        "lsqb_q3": ("SELECT math::sum(2 * array::len(array::filter(array::intersect(" + _NIN + ", " + _NOUT + "), "
                    "|$c| $c->islocatedin->city->ispartof->country = in->islocatedin->city->ispartof->country))) AS n "
                    "FROM knows WHERE in->islocatedin->city->ispartof->country = "
                    "out->islocatedin->city->ispartof->country GROUP ALL"),
        # q4: four independent legs off one message, so the product.
        "lsqb_q4": ("SELECT math::sum(array::len(->hastag->tag) * array::len(->hascreator->person) * "
                    "array::len(<-likes<-person) * array::len(<-replyof<-message)) AS n FROM message GROUP ALL"),
        # q5: pairs (tag1 of the message, tag2 of the reply) with tag1 <> tag2.
        "lsqb_q5": ("SELECT math::sum(array::len(out->hastag->tag) * array::len(in->hastag->tag) - "
                    "array::len(array::intersect(out->hastag->tag, in->hastag->tag))) AS n FROM replyof GROUP ALL"),
        # q6: for the middle person, every ordered (person1, person3) pair of
        # distinct neighbours, weighted by person3's interests: (deg - 1)
        # times the interests summed over the neighbourhood.
        "lsqb_q6": ("SELECT math::sum((count(->knows) + count(<-knows) - 1) * "
                    "(array::len(->knows->person->hasinterest->tag) + "
                    "array::len(<-knows<-person->hasinterest->tag))) AS n FROM person GROUP ALL"),
        # q7: q4 with the liker and reply legs OPTIONAL, so each contributes
        # max(count, 1).
        "lsqb_q7": ("SELECT math::sum(array::len(->hastag->tag) * "
                    "math::max([array::len(<-likes<-person), 1]) * "
                    "math::max([array::len(<-replyof<-message), 1])) AS n FROM message "
                    "WHERE array::len(->hascreator->person) > 0 GROUP ALL"),
        # q8: q5 where tag1 is not also on the reply: |tags(message) minus
        # tags(reply)| times |tags(reply)|.
        "lsqb_q8": ("SELECT math::sum(array::len(array::complement(out->hastag->tag, in->hastag->tag)) * "
                    "array::len(in->hastag->tag)) AS n FROM replyof GROUP ALL"),
        # q9: per KNOWS edge (person1, person2) in both roles, person3 ranges
        # over person2's neighbours minus person1's neighbours minus person1.
        "lsqb_q9": ("SELECT math::sum(array::len((array::complement(" + _NOUT + ", array::append(" + _NIN + ", in)))"
                    "->hasinterest->tag) + array::len((array::complement(" + _NIN + ", array::append(" + _NOUT + ", out)))"
                    "->hasinterest->tag)) AS n FROM knows GROUP ALL"),
    }

    def run_olap(self, qname):
        return self._rows(self.db.query(self.LSQB.get(qname) or self.OLAP[qname]))

    def run_cypher(self, text):
        raise NotImplementedError("SurrealDB runs SurrealQL through the name-based hooks")

    def close(self):
        try:
            self.db.close()
        except Exception:  # noqa: BLE001
            pass


class SurrealGraphServer(SurrealGraph):
    QUERY_LANGUAGE = "SurrealQL over WebSocket"
    name = "surrealdb_graph_server"

    # THE SAME QUESTION, THE SPELLING THIS ENGINE'S PLANNER PREFERS. Every
    # other entry is inherited unchanged; only the triangle count is
    # overridden, and only in how it names the two hops. Measured on the
    # laptop on 2026-09-14, both spellings returning the identical count on
    # both engines:
    #
    #            core 2.3.10 (embedded, 1,000 persons)   3.2.4 (served, 2,000)
    #   .out/.in              16.4 s                            7.3 s
    #   ->person/<-person     85.9 s                            1.7 s
    #
    # The preference inverts between the two engine versions -- 2.3.10 pays
    # for the record fetch that ->person forces, 3.2.4 plans the arrow form
    # better than the field form -- so one shared text would hand one of the
    # two arms a 4 to 5x penalty we know is avoidable. That is the same
    # reading as the bulk relation insert (60x over RELATE) and the index
    # defined before the TPC load (BUGS F37): a per-engine path is chosen for
    # each engine, not for the one we measured first. Both texts are here so
    # the choice can be checked rather than trusted.
    OLAP = dict(SurrealGraph.OLAP,
                triangles=("SELECT math::sum(n) AS n FROM ("
                           "SELECT array::len(array::filter(array::intersect("
                           "out->knows->person, in<-knows<-person), |$c| $c > in)) AS n "
                           "FROM knows WHERE in < out) GROUP ALL"))

    # THE SERVED 3.2.4 SPELLS THREE OF THE NINE DIFFERENTLY (2026-09-18,
    # DECISIONS #93 applied to LSQB), each proven against the reference on the
    # capped slice through the probe cell, with the embedded 2.3.10 text's
    # failure on 3.2.4 recorded verbatim:
    #   q6, q7: 3.2.4 treats count() and math::max() inside math::sum() as
    #     nested aggregates ("Invalid query: Nested aggregate functions are
    #     not supported"); array::len() and array::max() are plain functions
    #     on both versions and give the same numbers.
    #   q9: on 3.2.4 a traversal off a parenthesised array keeps ONE hit per
    #     element, `(array::concat(->knows->person, []))->hasinterest->tag`
    #     summed to 7,012 (the edge count) where the same expression on
    #     2.3.10 and the direct chain on both give 155,775; the embedded q9
    #     therefore came out 160,637 against 7,952,866. array::map with the
    #     traversal inside the closure keeps multiplicity on both versions.
    # The other six run the embedded text unchanged.
    LSQB = dict(SurrealGraph.LSQB,
        lsqb_q6=("SELECT math::sum((array::len(->knows) + array::len(<-knows) - 1) * "
                 "(array::len(->knows->person->hasinterest->tag) + "
                 "array::len(<-knows<-person->hasinterest->tag))) AS n FROM person GROUP ALL"),
        lsqb_q7=("SELECT math::sum(array::len(->hastag->tag) * "
                 "array::max([array::len(<-likes<-person), 1]) * "
                 "array::max([array::len(<-replyof<-message), 1])) AS n FROM message "
                 "WHERE array::len(->hascreator->person) > 0 GROUP ALL"),
        lsqb_q9=("SELECT math::sum(array::len(array::flatten(array::map(array::complement("
                 + SurrealGraph._NOUT + ", array::append(" + SurrealGraph._NIN + ", in)), "
                 "|$p| $p->hasinterest->tag))) + array::len(array::flatten(array::map(array::complement("
                 + SurrealGraph._NIN + ", array::append(" + SurrealGraph._NOUT + ", out)), "
                 "|$p| $p->hasinterest->tag)))) AS n FROM knows GROUP ALL"),
    )

    def _open(self):
        # One shared client for every served arm (DECISIONS #91): it sets the
        # WebSocket options the SDK leaves at the library's defaults, and it
        # reconnects, re-authenticates and re-selects the namespace once when
        # the socket dies mid-query.
        self.db = surreal_common.served_client()
        self.version = "surrealdb-server:" + str(self.db.version()).replace("surrealdb-", "")


class ArangoGraph(Base):
    """ArangoDB 3.12.11 served (2026-09-13): person as a document collection
    keyed by the LDBC id, KNOWS as an edge collection, both loaded through
    the bulk import API; the same LDBC questions in AQL traversals through
    the name-based hooks. The write is one AQL query (two INSERTs), which
    ArangoDB runs as one transaction."""
    QUERY_LANGUAGE = "AQL"
    name = "arangodb_graph"

    def connect(self):
        self.cl, self.db, self.version = arango_common.connect()
        # waitForSync on both collections the writes touch (DECISIONS #90).
        _sync = arango_common.sync_flag()
        self.person = self.db.create_collection("person", sync=_sync)
        self.knows = self.db.create_collection("knows", edge=True, sync=_sync)
        self.durability = arango_common.durability_readback(self.db, "person")

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
        "hop3f": ("LET s = (FOR v IN 3..3 OUTBOUND CONCAT('person/', @k) knows FILTER v.age > 30 RETURN DISTINCT v._key) "
                  "RETURN LENGTH(s)"),
    }
    VISITED = ("LET s = (FOR v IN 3..3 OUTBOUND CONCAT('person/', @k) knows RETURN DISTINCT v._key) "
               "RETURN LENGTH(s)")
    OLAP = {
        "top_degree": ("FOR p IN person FOR f IN 1..1 OUTBOUND p knows "
                       "COLLECT id = p.id WITH COUNT INTO d SORT d DESC, id ASC LIMIT 10 RETURN {id, d}"),
        "same_city_edges": ("FOR a IN person FOR b IN 1..1 OUTBOUND a knows FILTER a.city == b.city "
                            "COLLECT c = a.city WITH COUNT INTO n SORT n DESC, c ASC LIMIT 10 RETURN {c, n}"),
        "friend_age_by_city": ("FOR p IN person FOR f IN 1..1 OUTBOUND p knows "
                               "COLLECT c = p.city AGGREGATE a = AVG(f.age), n = COUNT(1) "
                               "SORT n DESC, c ASC LIMIT 10 RETURN {c, a, n}"),
        # 2026-10 (#82b), the same two questions in AQL. degree zero is filtered
        # out to match the Cypher MATCH.
        "degree_dist": ("FOR p IN person LET d = LENGTH(FOR f IN 1..1 OUTBOUND p knows RETURN 1) "
                        "FILTER d > 0 COLLECT deg = d WITH COUNT INTO n SORT deg RETURN {deg, n}"),
        "triangles": ("RETURN {n: LENGTH("
                      "FOR a IN person "
                      "FOR b IN 1..1 OUTBOUND a knows FILTER b.id > a.id "
                      "FOR c IN 1..1 OUTBOUND b knows FILTER c.id > a.id "
                      "FOR d IN 1..1 OUTBOUND c knows FILTER d._key == a._key "
                      "RETURN 1)}"),
    }

    # MESSAGE-HALF loader + LSQB in AQL (DECISIONS #103b/#104). INFERRED, NOT
    # RUN (no ArangoDB reachable from the laptop). Posts and Comments share one
    # `message` document collection with an `mtype` field ('post'/'comment'),
    # which is how the SNB supertype is expressed here; the other message-half
    # vertices are their own collections and each relationship is its own edge
    # collection. The LSQB queries are AQL traversals: undirected KNOWS is `ANY`
    # (this lane stores each KNOWS once, and the canonical queries traverse it
    # undirected), the two anti-joins (q8, q9) are a NOT with a subquery LENGTH
    # == 0, and each query returns {n: LENGTH(...)} the digest reads as a count.
    # The bench host confirms the digests against the Cypher arms.
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
        import ldbc_snb as _ldbc
        mc = _ldbc.MessageCorpus(self._scale)
        _sync = arango_common.sync_flag()
        colls = {c: self.db.create_collection(c, sync=_sync) for c in self._MSG_VCOLL}
        ecolls = {}
        for _key, (ec, _f, _t) in self._MSG_ECOLL.items():
            if ec not in ecolls:
                ecolls[ec] = self.db.create_collection(ec, edge=True, sync=_sync)
        vcount = ecount = 0
        # vertices: Post and Comment both land in `message` with an mtype field
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
        # edges
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

    LSQB = {
        "lsqb_q1": ("RETURN {n: LENGTH("
                    "FOR ci IN city "
                    "FOR co IN 1..1 OUTBOUND ci e_ispartof "
                    "FOR p IN 1..1 INBOUND ci e_islocatedin "
                    "FOR f IN 1..1 INBOUND p e_hasmember "
                    "FOR po IN 1..1 OUTBOUND f e_containerof "
                    "FOR cm IN 1..1 INBOUND po e_replyof "
                    "FOR t IN 1..1 OUTBOUND cm e_hastag "
                    "FOR tc IN 1..1 OUTBOUND t e_hastype RETURN 1)}"),
        "lsqb_q2": ("RETURN {n: LENGTH("
                    "FOR p1 IN person "
                    "FOR p2 IN 1..1 ANY p1 knows "
                    "FOR cm IN 1..1 INBOUND p1 e_hascreator FILTER cm.mtype == 'comment' "
                    "FOR po IN 1..1 OUTBOUND cm e_replyof FILTER po.mtype == 'post' "
                    "FOR pc IN 1..1 OUTBOUND po e_hascreator FILTER pc._key == p2._key RETURN 1)}"),
        "lsqb_q3": ("RETURN {n: LENGTH("
                    "FOR co IN country "
                    "FOR p1 IN person FILTER LENGTH(FOR c1 IN 1..1 OUTBOUND p1 e_islocatedin "
                    "  FOR x IN 1..1 OUTBOUND c1 e_ispartof FILTER x._key == co._key RETURN 1) > 0 "
                    "FOR p2 IN 1..1 ANY p1 knows FILTER LENGTH(FOR c2 IN 1..1 OUTBOUND p2 e_islocatedin "
                    "  FOR x IN 1..1 OUTBOUND c2 e_ispartof FILTER x._key == co._key RETURN 1) > 0 "
                    "FOR p3 IN 1..1 ANY p2 knows FILTER LENGTH(FOR c3 IN 1..1 OUTBOUND p3 e_islocatedin "
                    "  FOR x IN 1..1 OUTBOUND c3 e_ispartof FILTER x._key == co._key RETURN 1) > 0 "
                    "  AND LENGTH(FOR b IN 1..1 ANY p3 knows FILTER b._key == p1._key RETURN 1) > 0 "
                    "RETURN 1)}"),
        "lsqb_q4": ("RETURN {n: LENGTH("
                    "FOR m IN message "
                    "FOR t IN 1..1 OUTBOUND m e_hastag "
                    "FOR creator IN 1..1 OUTBOUND m e_hascreator "
                    "FOR liker IN 1..1 INBOUND m e_likes "
                    "FOR cm IN 1..1 INBOUND m e_replyof RETURN 1)}"),
        "lsqb_q5": ("RETURN {n: LENGTH("
                    "FOR m IN message "
                    "FOR tag1 IN 1..1 OUTBOUND m e_hastag "
                    "FOR cm IN 1..1 INBOUND m e_replyof "
                    "FOR tag2 IN 1..1 OUTBOUND cm e_hastag FILTER tag1._key != tag2._key RETURN 1)}"),
        "lsqb_q6": ("RETURN {n: LENGTH("
                    "FOR p1 IN person "
                    "FOR p2 IN 1..1 ANY p1 knows "
                    "FOR p3 IN 1..1 ANY p2 knows FILTER p1._key != p3._key "
                    "FOR t IN 1..1 OUTBOUND p3 e_hasinterest RETURN 1)}"),
        "lsqb_q7": ("RETURN {n: SUM("
                    "FOR m IN message "
                    "FOR t IN 1..1 OUTBOUND m e_hastag "
                    "FOR creator IN 1..1 OUTBOUND m e_hascreator "
                    "LET likers = LENGTH(FOR l IN 1..1 INBOUND m e_likes RETURN 1) "
                    "LET replies = LENGTH(FOR r IN 1..1 INBOUND m e_replyof RETURN 1) "
                    "RETURN MAX([likers, 1]) * MAX([replies, 1]))}"),
        "lsqb_q8": ("RETURN {n: LENGTH("
                    "FOR m IN message "
                    "FOR tag1 IN 1..1 OUTBOUND m e_hastag "
                    "FOR cm IN 1..1 INBOUND m e_replyof "
                    "FOR tag2 IN 1..1 OUTBOUND cm e_hastag FILTER tag1._key != tag2._key "
                    "FILTER LENGTH(FOR x IN 1..1 OUTBOUND cm e_hastag FILTER x._key == tag1._key RETURN 1) == 0 "
                    "RETURN 1)}"),
        "lsqb_q9": ("RETURN {n: LENGTH("
                    "FOR p1 IN person "
                    "FOR p2 IN 1..1 ANY p1 knows "
                    "FOR p3 IN 1..1 ANY p2 knows FILTER p1._key != p3._key "
                    "  AND LENGTH(FOR b IN 1..1 ANY p1 knows FILTER b._key == p3._key RETURN 1) == 0 "
                    "FOR t IN 1..1 OUTBOUND p3 e_hasinterest RETURN 1)}"),
    }

    def _n(self, q, **bv):
        return list(self.db.aql.execute(q, bind_vars=bv))

    def run_read(self, op, pid):
        return self._n(self.READS[op], k=str(pid))

    def run_visited(self, pid):
        return self._n(self.VISITED, k=str(pid))

    def run_update(self, new_id):
        self._n("UPDATE {_key: @nk} WITH {age: @a} IN person", nk=str(new_id), a=UPDATE_AGE)

    def person_scan(self, id_from):
        return self._n("FOR p IN person FILTER p.id >= @f "
                       "RETURN {id: p.id, name: p.name, age: p.age, city: p.city}", f=id_from)

    def run_write(self, pid, new_id):
        self._n("INSERT {_key: @nk, id: @n, name: CONCAT('w', @nk), age: 33, city: 'city_0'} INTO person "
                "INSERT {_from: CONCAT('person/', @k), _to: CONCAT('person/', @nk), since: 2026} INTO knows",
                k=str(pid), nk=str(new_id), n=new_id)

    def run_delete(self, new_id):
        # One AQL query, so one transaction: the edges touching the vertex, then the vertex.
        self._n("LET v = CONCAT('person/', @nk) "
                "FOR e IN knows FILTER e._from == v OR e._to == v REMOVE e IN knows "
                "REMOVE {_key: @nk} IN person",
                nk=str(new_id))

    def run_olap(self, qname):
        return self._n(self.LSQB.get(qname) or self.OLAP[qname])

    def run_cypher(self, text):
        raise NotImplementedError("ArangoDB runs AQL through the name-based hooks")

    def close(self):
        arango_common.close(self.cl)


class MongoGraph(Base):
    """MongoDB 8.2.12 served (2026-09-15): `person` documents keyed by the LDBC
    id and `knows` as an edge document collection, the same questions as
    aggregation pipelines.

    MongoDB CLAIMS NO GRAPH MODEL, which is why DECISIONS #68 left it off this
    table. #92 is the rule that reopens it: an engine competes in its own
    dialect if it can express the query, and the constructs it cannot are
    named rather than assumed. Every one of the twelve questions on this lane
    turned out to be expressible; what follows is the part that is not
    obvious, and the full account is in COMPARATOR-DIALECTS.md.

    THE MULTI-HOP READS USE CHAINED $lookup, NOT $graphLookup, and the reason
    is not that $graphLookup fails. Measured at micro (2,000 persons, 40,833
    edges, the fifty-id read set), with the depth offset written correctly --
    `startWith: "$dst"` has already consumed the first hop, so "exactly N
    hops" is `maxDepth: N-2` with `depthField == N-2` -- $graphLookup agrees
    with the chained form on 50 of 50 ids at two hops AND at three, and both
    agree with a plain Python enumeration over the same generator. The first
    version of this probe compared depth 1 against two hops, got a disagreement
    on 50 of 50, and would have gone into the record as "MongoDB's recursive
    stage answers a different question"; it was our off-by-one. What decided
    the spelling is cost, the way DECISIONS #93 decided SurrealDB's triangle
    count: per operation over the same fifty ids,

        two hops    $graphLookup 4.10 ms   chained $lookup 3.21 ms
        three hops  $graphLookup 30.01 ms  chained $lookup 38.27 ms

    so neither form wins on both. The chained form is used for both, because
    it is the only one of the two that is a faithful translation BY
    CONSTRUCTION rather than by measurement on one corpus (see below), and the
    three-hop reading is the one place this arm is left slower than it needs
    to be. Re-checking $graphLookup's equivalence at the campaign's LDBC
    corpus would buy about 1.3x on hop3f and nothing else.

    RELATIONSHIP UNIQUENESS HAS TO BE WRITTEN OUT. Cypher's MATCH forbids
    reusing the same relationship inside one path and ArangoDB's traversal
    defaults to the same (uniqueEdges: path); neither a chain of $lookups nor
    $graphLookup has such a rule. At three hops the only collision this corpus
    can produce is the first edge reappearing as the third (a->b, b->a, a->b),
    so hop3f and the three-hop visited probe carry an explicit `$ne` on the
    edge _id. On the micro corpus the clause changes the answer on 0 of 50
    ids, because these queries count DISTINCT endpoints and a dropped path
    almost always has a surviving twin -- which is exactly why it is written
    out rather than left to luck: the day it matters, it would be a silent
    over-count against every engine that enforces the rule.
    """
    QUERY_LANGUAGE = "the aggregation pipeline ($graphLookup)"
    name = "mongodb_graph"

    def connect(self):
        self.cl, self.db, self.version = mongo_common.connect(auth=False)
        self.durability = bench_common.at_class(mongo_common.DURABILITY)
        self._wc = mongo_common.write_concern()
        self.person = self.db.get_collection("person", write_concern=self._wc)
        self.knows = self.db.get_collection("knows", write_concern=self._wc)

    def build(self, n_persons):
        buf = []
        for i, name, age, city in gen_persons(n_persons):
            buf.append({"_id": i, "name": name, "age": age, "city": city})
            if len(buf) >= INGEST_BATCH:
                self.person.insert_many(buf, ordered=False); buf = []
        if buf:
            self.person.insert_many(buf, ordered=False)
        buf = []
        for src, dst, since in gen_edges(n_persons):
            buf.append({"src": src, "dst": dst, "since": since})
            if len(buf) >= INGEST_BATCH:
                self.knows.insert_many(buf, ordered=False); buf = []
        if buf:
            self.knows.insert_many(buf, ordered=False)
        # AFTER the load, which is what every other arm does: an index
        # maintained per batch costs more than one built over the finished
        # collection. src is every outbound hop and every write's edge lookup;
        # dst is the inbound side the triangle count and the delete need.
        self.knows.create_index("src")
        self.knows.create_index("dst")

    # ---- reads -------------------------------------------------------
    # One hop is one $lookup from `knows` into `knows`; the last hop joins
    # `person` only where a property of the far end is asked for.
    _HOP = {"from": "knows", "localField": "dst", "foreignField": "src", "as": "e2"}

    def _agg(self, coll, pipeline):
        return list(coll.aggregate(pipeline))

    @staticmethod
    def _count_or_zero(rows):
        """$count and $group emit NOTHING for an empty input; Cypher and AQL
        emit one row holding 0. Our generator gives every person at least one
        outgoing edge so this never fires on this corpus, but a digest that
        depends on that is a digest that breaks the day the corpus changes."""
        return rows if rows else [{"n": 0}]

    def run_read(self, op, pid):
        if op == "point":
            return self._agg(self.person, [
                {"$match": {"_id": pid}},
                {"$project": {"_id": 0, "name": 1, "age": 1}}])
        if op == "hop1":
            rows = self._agg(self.knows, [
                {"$match": {"src": pid}},
                {"$lookup": {"from": "person", "localField": "dst",
                             "foreignField": "_id", "as": "f"}},
                {"$unwind": "$f"},
                {"$group": {"_id": None, "n": {"$sum": 1}, "a": {"$avg": "$f.age"}}},
                {"$project": {"_id": 0, "n": 1, "a": 1}}])
            return rows if rows else [{"n": 0, "a": None}]
        if op == "hop2":
            return self._count_or_zero(self._agg(self.knows, [
                {"$match": {"src": pid}},
                {"$lookup": dict(self._HOP)}, {"$unwind": "$e2"},
                {"$group": {"_id": "$e2.dst"}},
                {"$count": "n"}]))
        if op == "hop3f":
            return self._count_or_zero(self._agg(self.knows, self._three_hops(pid) + [
                {"$lookup": {"from": "person", "localField": "e3.dst",
                             "foreignField": "_id", "as": "x"}},
                {"$unwind": "$x"},
                {"$match": {"x.age": {"$gt": 30}}},
                {"$group": {"_id": "$x._id"}},
                {"$count": "n"}]))
        raise KeyError(op)

    @staticmethod
    def _three_hops(pid):
        return [
            {"$match": {"src": pid}},
            {"$lookup": {"from": "knows", "localField": "dst",
                         "foreignField": "src", "as": "e2"}},
            {"$unwind": "$e2"},
            {"$lookup": {"from": "knows", "localField": "e2.dst",
                         "foreignField": "src", "as": "e3"}},
            {"$unwind": "$e3"},
            # Cypher's relationship isomorphism, written out: the third edge
            # may not be the first one again (a->b, b->a, a->b).
            {"$match": {"$expr": {"$ne": ["$e3._id", "$_id"]}}},
        ]

    def run_visited(self, pid):
        return self._count_or_zero(self._agg(self.knows, self._three_hops(pid) + [
            {"$group": {"_id": "$e3.dst"}},
            {"$count": "n"}]))

    # ---- writes ------------------------------------------------------
    def run_write(self, pid, new_id):
        # ONE TRANSACTION, because the Cypher this translates is one: the
        # person and the edge that links them either both exist or neither
        # does. A multi-document transaction is why the server runs as a
        # single-node replica set.
        with self.cl.start_session() as s:
            with s.start_transaction(write_concern=self._wc):
                self.db["person"].insert_one(
                    {"_id": new_id, "name": f"w{new_id}", "age": 33, "city": "city_0"},
                    session=s)
                self.db["knows"].insert_one(
                    {"src": pid, "dst": new_id, "since": 2026}, session=s)

    def run_update(self, new_id):
        # NO SESSION, deliberately: one field of one document is atomic in
        # MongoDB by construction, and wrapping it in a transaction would time
        # a commit path no other engine on this table pays (the same rule the
        # document lane's single-record operations follow).
        self.person.update_one({"_id": new_id}, {"$set": {"age": UPDATE_AGE}})

    def run_delete(self, new_id):
        # DETACH DELETE: the edges touching the vertex, then the vertex, in
        # one transaction.
        with self.cl.start_session() as s:
            with s.start_transaction(write_concern=self._wc):
                self.db["knows"].delete_many(
                    {"$or": [{"src": new_id}, {"dst": new_id}]}, session=s)
                self.db["person"].delete_one({"_id": new_id}, session=s)

    def person_scan(self, id_from):
        return self._agg(self.person, [
            {"$match": {"_id": {"$gte": id_from}}},
            {"$project": {"_id": 0, "id": "$_id", "name": 1, "age": 1, "city": 1}}])

    # ---- analytics ---------------------------------------------------
    OLAP = {
        "top_degree": ("knows", [
            {"$group": {"_id": "$src", "d": {"$sum": 1}}},
            {"$sort": {"d": -1, "_id": 1}}, {"$limit": 10},
            {"$project": {"_id": 0, "id": "$_id", "d": 1}}]),
        "same_city_edges": ("knows", [
            {"$lookup": {"from": "person", "localField": "src", "foreignField": "_id", "as": "a"}},
            {"$unwind": "$a"},
            {"$lookup": {"from": "person", "localField": "dst", "foreignField": "_id", "as": "b"}},
            {"$unwind": "$b"},
            {"$match": {"$expr": {"$eq": ["$a.city", "$b.city"]}}},
            {"$group": {"_id": "$a.city", "n": {"$sum": 1}}},
            {"$sort": {"n": -1, "_id": 1}}, {"$limit": 10},
            {"$project": {"_id": 0, "c": "$_id", "n": 1}}]),
        "friend_age_by_city": ("knows", [
            {"$lookup": {"from": "person", "localField": "src", "foreignField": "_id", "as": "a"}},
            {"$unwind": "$a"},
            {"$lookup": {"from": "person", "localField": "dst", "foreignField": "_id", "as": "f"}},
            {"$unwind": "$f"},
            {"$group": {"_id": "$a.city", "a": {"$avg": "$f.age"}, "n": {"$sum": 1}}},
            {"$sort": {"n": -1, "_id": 1}}, {"$limit": 10},
            {"$project": {"_id": 0, "c": "$_id", "a": 1, "n": 1}}]),
        "degree_dist": ("knows", [
            {"$group": {"_id": "$src", "d": {"$sum": 1}}},
            {"$group": {"_id": "$d", "n": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "deg": "$_id", "n": 1}}]),
        # THE SET-INTERSECTION FORM, not a triple $unwind. One row of `knows`
        # is the a->b leg with a < b; N+(b) and N-(a) are two indexed
        # $lookups, and the third vertex is any c in both with c > a, so each
        # triangle is counted once at its smallest-id vertex. The same shape
        # SurrealDB's triangle count uses, and for the same reason: the
        # nested-unwind spelling materialises every three-path.
        "triangles": ("knows", [
            {"$match": {"$expr": {"$lt": ["$src", "$dst"]}}},
            {"$lookup": {"from": "knows", "localField": "dst", "foreignField": "src", "as": "bc"}},
            {"$lookup": {"from": "knows", "localField": "src", "foreignField": "dst", "as": "ca"}},
            {"$project": {"n": {"$size": {"$filter": {
                "input": {"$setIntersection": [
                    {"$map": {"input": "$bc", "in": "$$this.dst"}},
                    {"$map": {"input": "$ca", "in": "$$this.src"}}]},
                "cond": {"$gt": ["$$this", "$src"]}}}}}},
            {"$group": {"_id": None, "n": {"$sum": "$n"}}},
            {"$project": {"_id": 0, "n": 1}}]),
    }

    # MESSAGE-HALF loader + LSQB as aggregation pipelines (DECISIONS #103b/#104).
    # INFERRED, NOT RUN (no MongoDB reachable from the laptop), and the LEAST
    # certain of the non-Cypher arms -- LSQB's shapes (a Message supertype, an
    # eight-way join, two anti-joins, undirected friendship) are the hardest to
    # write as pipelines and have no LSQB reference. Modelling: Post and Comment
    # share a `message` collection with an `mtype` field; each relationship is
    # its own {s,d} edge collection; and because a $lookup is directed, an
    # undirected-KNOWS collection `knows_undir` holds every friendship in BOTH
    # directions (built here, used only by the LSQB pipelines, so the five
    # hand-written queries on the directed `knows` are untouched). Each pipeline
    # ends in a document {n: <count(*)>} the digest reads. The anti-joins are a
    # $lookup with a `$match` on an empty result. THE BENCH HOST MUST CONFIRM OR,
    # where a shape is genuinely inexpressible, DECLARE IT WITH THE ERROR (#92).
    _MSG_ECOLL = {
        ("IS_LOCATED_IN", "Person", "City"):  "e_islocatedin",
        ("IS_PART_OF", "City", "Country"):     "e_ispartof",
        ("HAS_MEMBER", "Forum", "Person"):     "e_hasmember",
        ("CONTAINER_OF", "Forum", "Post"):     "e_containerof",
        ("REPLY_OF", "Comment", "Post"):       "e_replyof",
        ("REPLY_OF", "Comment", "Comment"):    "e_replyof",
        ("HAS_TAG", "Post", "Tag"):            "e_hastag",
        ("HAS_TAG", "Comment", "Tag"):         "e_hastag",
        ("HAS_TYPE", "Tag", "TagClass"):       "e_hastype",
        ("HAS_CREATOR", "Post", "Person"):     "e_hascreator",
        ("HAS_CREATOR", "Comment", "Person"):  "e_hascreator",
        ("LIKES", "Person", "Post"):           "e_likes",
        ("LIKES", "Person", "Comment"):        "e_likes",
        ("HAS_INTEREST", "Person", "Tag"):     "e_hasinterest",
    }

    def build_messages(self):
        import ldbc_snb as _ldbc
        mc = _ldbc.MessageCorpus(self._scale)
        vcount = ecount = 0
        by_label = {label: g for label, g in mc.vertex_spec()}

        def _fill(coll_name, docs):
            nonlocal vcount
            coll = self.db.get_collection(coll_name, write_concern=self._wc)
            buf = []
            for doc in docs:
                buf.append(doc); vcount += 1
                if len(buf) >= INGEST_BATCH:
                    coll.insert_many(buf, ordered=False); buf = []
            if buf:
                coll.insert_many(buf, ordered=False)
        for label in ("Country", "City", "Forum", "Tag", "TagClass"):
            _fill(label.lower(), ({"_id": v} for v in by_label[label]))
        _fill("message", ({"_id": v, "mtype": "post"} for v in by_label["Post"]))
        _fill("message", ({"_id": v, "mtype": "comment"} for v in by_label["Comment"]))
        for rel, src_label, dst_label, gen in mc.edge_spec():
            ec = self.db.get_collection(self._MSG_ECOLL[(rel, src_label, dst_label)],
                                        write_concern=self._wc)
            buf = []
            for s, d in gen():
                buf.append({"s": s, "d": d}); ecount += 1
                if len(buf) >= INGEST_BATCH:
                    ec.insert_many(buf, ordered=False); buf = []
            if buf:
                ec.insert_many(buf, ordered=False)
        # undirected KNOWS for q2/q3/q6/q9, both directions, in its own
        # collection so the directed-`knows` analytics queries are untouched.
        ku = self.db.get_collection("knows_undir", write_concern=self._wc)
        buf = []
        for e in self.knows.find({}, {"_id": 0, "src": 1, "dst": 1}):
            buf.append({"s": e["src"], "d": e["dst"]})
            buf.append({"s": e["dst"], "d": e["src"]})
            if len(buf) >= INGEST_BATCH:
                ku.insert_many(buf, ordered=False); buf = []
        if buf:
            ku.insert_many(buf, ordered=False)
        for c in ("e_islocatedin", "e_ispartof", "e_hasmember", "e_containerof",
                  "e_replyof", "e_hastag", "e_hastype", "e_hascreator", "e_likes",
                  "e_hasinterest"):
            self.db[c].create_index("s"); self.db[c].create_index("d")
        ku.create_index("s")
        self.msg_counts = {"msg_vertices": vcount, "msg_edges": ecount}

    # LSQB pipelines. Each names the collection it starts from and ends in a
    # {n: count} document (see the note above). Every join is a $lookup +
    # $unwind that yields one document per matching sub-path, so the final
    # $count is count(*). Anti-joins keep the rows whose lookup came back empty.
    _LSQB = {
        # q1: the eight-label chain, started from the small end (TagClass).
        "lsqb_q1": ("tagclass", [
            {"$lookup": {"from": "e_hastype", "localField": "_id", "foreignField": "d", "as": "ht"}},
            {"$unwind": "$ht"},  # tag -> tagclass
            {"$lookup": {"from": "e_hastag", "localField": "ht.s", "foreignField": "d", "as": "mt"}},
            {"$unwind": "$mt"},  # message -> tag
            # THE TAG IS ON THE COMMENT (LSQB q1: ...Post<-REPLY_OF-Comment-HAS_TAG->Tag).
            # The first version looked up replies TO mt.s and the forum OF
            # mt.s, i.e. it put the tag on the post (found by reading the
            # pipeline against the Cypher, 2026-09-18).
            {"$lookup": {"from": "e_replyof", "localField": "mt.s", "foreignField": "s", "as": "ro"}},
            {"$unwind": "$ro"},  # comment(=mt.s) -> post(=ro.d)
            {"$lookup": {"from": "e_containerof", "localField": "ro.d", "foreignField": "d", "as": "co"}},
            {"$unwind": "$co"},  # forum -> post; only a Post is contained, so ro.d is one
            {"$lookup": {"from": "e_hasmember", "localField": "co.s", "foreignField": "s", "as": "hm"}},
            {"$unwind": "$hm"},  # forum -> person
            {"$lookup": {"from": "e_islocatedin", "localField": "hm.d", "foreignField": "s", "as": "il"}},
            {"$unwind": "$il"},  # person -> city
            {"$lookup": {"from": "e_ispartof", "localField": "il.d", "foreignField": "s", "as": "ip"}},
            {"$unwind": "$ip"},  # city -> country
            {"$count": "n"}]),
        # q5: message with two differently-tagged sides (message, its reply, two tags).
        "lsqb_q5": ("e_replyof", [
            {"$lookup": {"from": "e_hastag", "localField": "d", "foreignField": "s", "as": "t1"}},
            {"$unwind": "$t1"},  # message(=d) -> tag1
            {"$lookup": {"from": "e_hastag", "localField": "s", "foreignField": "s", "as": "t2"}},
            {"$unwind": "$t2"},  # comment(=s) -> tag2
            {"$match": {"$expr": {"$ne": ["$t1.d", "$t2.d"]}}},
            {"$count": "n"}]),
        # q8: q5 with the comment NOT itself carrying tag1 (anti-join).
        "lsqb_q8": ("e_replyof", [
            {"$lookup": {"from": "e_hastag", "localField": "d", "foreignField": "s", "as": "t1"}},
            {"$unwind": "$t1"},
            {"$lookup": {"from": "e_hastag", "localField": "s", "foreignField": "s", "as": "t2"}},
            {"$unwind": "$t2"},
            {"$match": {"$expr": {"$ne": ["$t1.d", "$t2.d"]}}},
            {"$lookup": {"from": "e_hastag", "let": {"c": "$s", "tg": "$t1.d"},
                         "pipeline": [{"$match": {"$expr": {"$and": [
                             {"$eq": ["$s", "$$c"]}, {"$eq": ["$d", "$$tg"]}]}}}], "as": "chk"}},
            {"$match": {"chk": {"$size": 0}}},
            {"$count": "n"}]),
        # q6: two-hop friend chain (undirected) whose far end has a tag interest.
        "lsqb_q6": ("knows_undir", [
            {"$lookup": {"from": "knows_undir", "localField": "d", "foreignField": "s", "as": "k2"}},
            {"$unwind": "$k2"},  # p2 -> p3
            {"$match": {"$expr": {"$ne": ["$s", "$k2.d"]}}},  # person1 <> person3
            {"$lookup": {"from": "e_hasinterest", "localField": "k2.d", "foreignField": "s", "as": "hi"}},
            {"$unwind": "$hi"},  # p3 -> tag
            {"$count": "n"}]),
        # q9: q6 with person1 NOT directly KNOWS person3 (anti-join).
        "lsqb_q9": ("knows_undir", [
            {"$lookup": {"from": "knows_undir", "localField": "d", "foreignField": "s", "as": "k2"}},
            {"$unwind": "$k2"},
            {"$match": {"$expr": {"$ne": ["$s", "$k2.d"]}}},
            {"$lookup": {"from": "knows_undir", "let": {"a": "$s", "c": "$k2.d"},
                         "pipeline": [{"$match": {"$expr": {"$and": [
                             {"$eq": ["$s", "$$a"]}, {"$eq": ["$d", "$$c"]}]}}}], "as": "chk"}},
            {"$match": {"chk": {"$size": 0}}},
            {"$lookup": {"from": "e_hasinterest", "localField": "k2.d", "foreignField": "s", "as": "hi"}},
            {"$unwind": "$hi"},
            {"$count": "n"}]),
    }

    def run_olap(self, qname):
        if qname in self._LSQB:
            coll, pipeline = self._LSQB[qname]
            return self._count_or_zero(list(self.db[coll].aggregate(pipeline, allowDiskUse=True)))
        if qname in ("lsqb_q2", "lsqb_q3", "lsqb_q4", "lsqb_q7"):
            return self._lsqb_special(qname)
        coll, pipeline = self.OLAP[qname]
        # allowDiskUse: the two-sided join in same_city_edges and
        # friend_age_by_city exceeds the 100 MB in-memory sort/group limit at
        # the campaign's scale factors, and an engine refusing its own query
        # for a memory bound is not a result about the query.
        rows = list(self.db[coll].aggregate(pipeline, allowDiskUse=True))
        return self._count_or_zero(rows) if qname == "triangles" else rows

    def _lsqb_special(self, qname):
        """The four LSQB pipelines with an extra structural twist (see the note):
        q2's two-creator + reply chain, q3's country triangle, q4's three-way
        message fan-in, q7's OPTIONAL-MATCH left-join count. INFERRED."""
        if qname == "lsqb_q4":
            return self._count_or_zero(list(self.db["message"].aggregate([
                {"$lookup": {"from": "e_hastag", "localField": "_id", "foreignField": "s", "as": "t"}},
                {"$unwind": "$t"},
                {"$lookup": {"from": "e_hascreator", "localField": "_id", "foreignField": "s", "as": "cr"}},
                {"$unwind": "$cr"},
                {"$lookup": {"from": "e_likes", "localField": "_id", "foreignField": "d", "as": "lk"}},
                {"$unwind": "$lk"},
                {"$lookup": {"from": "e_replyof", "localField": "_id", "foreignField": "d", "as": "ro"}},
                {"$unwind": "$ro"},
                {"$count": "n"}], allowDiskUse=True)))
        if qname == "lsqb_q7":
            # OPTIONAL MATCH: one row per (message,tag,creator) times max(likers,1)
            # times max(replies,1); computed as a sum of that product.
            rows = list(self.db["message"].aggregate([
                {"$lookup": {"from": "e_hastag", "localField": "_id", "foreignField": "s", "as": "t"}},
                {"$unwind": "$t"},
                {"$lookup": {"from": "e_hascreator", "localField": "_id", "foreignField": "s", "as": "cr"}},
                {"$unwind": "$cr"},
                {"$lookup": {"from": "e_likes", "localField": "_id", "foreignField": "d", "as": "lk"}},
                {"$lookup": {"from": "e_replyof", "localField": "_id", "foreignField": "d", "as": "ro"}},
                {"$group": {"_id": None, "n": {"$sum": {"$multiply": [
                    {"$max": [{"$size": "$lk"}, 1]}, {"$max": [{"$size": "$ro"}, 1]}]}}}},
                {"$project": {"_id": 0, "n": 1}}], allowDiskUse=True))
            return self._count_or_zero(rows)
        if qname == "lsqb_q2":
            return self._count_or_zero(list(self.db["knows_undir"].aggregate([
                {"$lookup": {"from": "e_hascreator", "localField": "s", "foreignField": "d", "as": "cm"}},
                {"$unwind": "$cm"},  # comment/post created by person1
                {"$lookup": {"from": "e_replyof", "localField": "cm.s", "foreignField": "s", "as": "ro"}},
                {"$unwind": "$ro"},  # that message replies to ro.d, a post OR a comment
                # (post:Post): REPLY_OF also links comment to comment, and the
                # Cypher counts only replies to a Post (2026-09-18).
                {"$lookup": {"from": "message", "localField": "ro.d", "foreignField": "_id", "as": "pm"}},
                {"$unwind": "$pm"},
                {"$match": {"pm.mtype": "post"}},
                {"$lookup": {"from": "e_hascreator", "localField": "ro.d", "foreignField": "s", "as": "pc"}},
                {"$unwind": "$pc"},  # post's creator
                {"$match": {"$expr": {"$eq": ["$pc.d", "$d"]}}},  # == person2
                {"$count": "n"}], allowDiskUse=True)))
        if qname == "lsqb_q3":
            return self._count_or_zero(list(self.db["knows_undir"].aggregate([
                {"$lookup": {"from": "knows_undir", "localField": "d", "foreignField": "s", "as": "k2"}},
                {"$unwind": "$k2"},
                {"$lookup": {"from": "knows_undir", "let": {"c": "$k2.d", "a": "$s"},
                             "pipeline": [{"$match": {"$expr": {"$and": [
                                 {"$eq": ["$s", "$$c"]}, {"$eq": ["$d", "$$a"]}]}}}], "as": "close"}},
                {"$unwind": "$close"},  # p3 knows p1 -> triangle
                {"$lookup": {"from": "e_islocatedin", "localField": "s", "foreignField": "s", "as": "l1"}},
                {"$unwind": "$l1"},
                {"$lookup": {"from": "e_ispartof", "localField": "l1.d", "foreignField": "s", "as": "c1"}},
                {"$unwind": "$c1"},
                {"$lookup": {"from": "e_islocatedin", "localField": "d", "foreignField": "s", "as": "l2"}},
                {"$unwind": "$l2"},
                {"$lookup": {"from": "e_ispartof", "localField": "l2.d", "foreignField": "s", "as": "c2"}},
                {"$unwind": "$c2"},
                {"$lookup": {"from": "e_islocatedin", "localField": "k2.d", "foreignField": "s", "as": "l3"}},
                {"$unwind": "$l3"},
                {"$lookup": {"from": "e_ispartof", "localField": "l3.d", "foreignField": "s", "as": "c3"}},
                {"$unwind": "$c3"},
                {"$match": {"$expr": {"$and": [{"$eq": ["$c1.d", "$c2.d"]},
                                               {"$eq": ["$c2.d", "$c3.d"]}]}}},
                {"$count": "n"}], allowDiskUse=True)))

    def run_cypher(self, text):
        raise NotImplementedError("MongoDB runs aggregation pipelines through the name-based hooks")

    def close(self):
        mongo_common.close(self.cl)


ADAPTERS = {a.name: a for a in
            [ArcadeGraphEmbedded, ArcadeGraphServer, Neo4jGraph, LadybugGraph,
             SurrealGraph, SurrealGraphServer, ArangoGraph, MongoGraph,
             MemgraphGraph, FalkorGraph, DuckpgqGraph]}

# DECISIONS #81: what each arm runs at commit, recorded on the row. Neo4j and
# LadybugDB cannot be relaxed and are the named exceptions on this table; the
# SurrealDB server's behaviour could not be established and its string says so.
# Every string, and the evidence behind it, is in bench_common.
DURABILITY = {
    "arcadedb_graph_embedded": bench_common.DURABILITY_ARCADEDB,
    "arcadedb_graph_server": bench_common.DURABILITY_ARCADEDB,
    "neo4j_graph": bench_common.DURABILITY_NEO4J,
    "ladybug_graph": bench_common.DURABILITY_LADYBUG,
    "surrealdb_graph": bench_common.DURABILITY_SURREAL_EMBEDDED,
    "surrealdb_graph_server": bench_common.DURABILITY_SURREAL_SERVER,
    "arangodb_graph": arango_common.DURABILITY,
    "mongodb_graph": mongo_common.DURABILITY,
    # Both read their own setting back at connect (SHOW CONFIG, CONFIG GET);
    # these are the relaxed strings the read-back is compared against.
    "memgraph_graph": bench_common.DURABILITY_MEMGRAPH,
    "falkordb_graph": bench_common.DURABILITY_FALKORDB,
    # DuckDB has no durability knob (DECISIONS #90): one string in both classes,
    # the same the document, time-series and dense-VSS DuckDB arms record.
    "duckpgq_graph": bench_common.DURABILITY_DUCKDB,
}


# 1,000 single-record operations per repetition (DECISIONS #82a), not the
# read set's size. The write, the update and the delete are the three of the
# four CRUD operations this lane owns; the fourth, read by key, is the point
# lookup already in OLTP_READS, which is why the graph table carries seven
# operations and not ten (#82d).
CRUD_OPS = int(os.environ.get("BENCH_CRUD_OPS", "1000"))


def first_value(rows):
    """The single number a count query returned, whatever shape it came in."""
    if not rows:
        return None
    r = rows[0]
    if isinstance(r, dict):
        return next(iter(r.values()), None)
    if isinstance(r, (list, tuple)):
        return r[0] if r else None
    return r


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
        # The row names the corpus it read, WITH the tier, because "ldbc" alone
        # does not say which projection. Written here, in the branch that
        # selects LDBC, and nowhere else: it used to sit at the end of the
        # gen_edges wrapper below, one indent level inside the function, so
        # every synthetic run stamped itself "ldbc-<scale>" as soon as the
        # first edge stream was drained. The laptop has no LDBC corpus at all
        # and its micro rows still claimed one.
        out["graph_source"] = f"ldbc-{args.scale}"

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

    # PHASE MARKERS (2026-09-14, same pattern as l3d_dense): a cell that dies
    # names the phase it was in. Entered and left AROUND the timed work, never
    # inside a timed loop.
    _beat = bench_common.PhaseBeat()
    _beat.mark("cell-start", backend=args.backend, workload=args.workload,
               scale=args.scale, n_persons=n_persons)

    ad = ADAPTERS[args.backend]()
    ad._scale = args.scale
    t0 = time.perf_counter()
    with _beat.phase("connect", backend=args.backend):
        ad.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = ad.version
    # What a served engine reported about itself at connect: client library
    # version, thread pool, memory limit, timeouts, persistence settings
    # (Memgraph, FalkorDB, DuckPGQ). Read from the server, not restated from
    # the flags the runner sent. Not printed by the page; kept on the row.
    out.update(getattr(ad, "row_extra", None) or {})
    # WHICH LANGUAGE THIS ARM WAS ASKED IN, declared by the adapter.
    #
    # The page has a hand-typed sentence naming which engine answers in what,
    # and on 2026-09-22 it still listed the five arms this table had when it
    # was written while the table had eleven -- Memgraph, FalkorDB, DuckPGQ
    # and MongoDB simply missing from a sentence whose only job is that list.
    # It matters more here than on most tables: ArcadeDB has its own SQL and
    # is asked in Cypher by choice (DECISIONS #113), so a reader comparing its
    # point lookup against Memgraph's cannot otherwise tell that our engine is
    # answering in a non-native dialect.
    #
    # Recorded, not yet published. The sentence stays typed until every arm on
    # the lane has carried this field through a campaign, because a generated
    # sentence built from a half-populated field would name a SUBSET of the
    # engines and read as though the rest answer in nothing. That is the same
    # trap `filtered_mode` avoided by being recorded long before it was
    # published.
    out["query_language"] = getattr(ad, "QUERY_LANGUAGE", "not declared")
    out["instrument"] = bench_common.INSTRUMENT

    # THE MESSAGE HALF, inside the build timer, because at the full-network
    # tier it IS the load: the ingest column prices the whole corpus. The
    # adapters read self._scale (set above) and self._load_messages, which the
    # analytics loop also reads to tell an LSQB query with no message half
    # from one that ran (DECISIONS #103b/#104).
    ad._load_messages = _load_messages
    t0 = time.perf_counter()
    with _beat.phase("build", n=n_persons):
        ad.build(n_persons)
        if _load_messages:
            _beat.mark("build-messages-start", scale=args.scale,
                       msg_limit=_MSG_LIMIT, person_limit=_PERSON_LIMIT)
            ad.build_messages()
            _beat.mark("build-messages-done", **getattr(ad, "msg_counts", {}))
    with _beat.phase("post-build", workload=args.workload):
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
    # AFTER THE BUILD (DECISIONS #90). ArangoDB's waitForSync is a collection
    # property, so it can only be read back once build() has created one; an
    # adapter that read its value out of its own engine wins over the map.
    bench_common.stamp_durability(out, getattr(ad, "durability", None)
                                  or DURABILITY.get(args.backend))

    if args.workload == "oltp":
        ids = pick_query_ids(n_persons, n_q)
        total_t0 = time.perf_counter()

        collected = {}

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
                answers = []
                for w, pid in enumerate(ids):
                    t = time.perf_counter()
                    rows = ad.run_read(op, pid)
                    dt = (time.perf_counter() - t) * 1000
                    if not prefix and w == 0:
                        # The cell's first query after the database opened
                        # (#89 as amended): the first id of the first read op
                        # of the cold pass.
                        bench_common.record_first_query(out, op, dt)
                    # Collected AFTER the clock stops, from the object the
                    # timed call returned (DECISIONS #88).
                    if rows:
                        answers.extend(rows)
                    if w >= 5:  # warmups discarded
                        # ...and so is a sample whose connection dropped
                        # while it was being taken (DECISIONS #91).
                        surreal_common.keep(ad, lat, dt)
                lat.sort()
                res[f"{prefix}{op}_p50_ms"] = round(pct(lat, 0.50), 3)
                res[f"{prefix}{op}_p95_ms"] = round(pct(lat, 0.95), 3)
                res[f"{prefix}{op}_p99_ms"] = round(pct(lat, 0.99), 3)
                collected[op] = answers
            return res

        _beat.mark("reads-cold-start", n=len(ids), ops=len(OLTP_READS))
        out.update(_read_pass())            # first touch
        _beat.mark("reads-warm-start", n=len(ids), ops=len(OLTP_READS))
        out.update(_read_pass("warm_"))     # same queries, index now resident
        _beat.mark("reads-done")
        # ONE NAMING CONVENTION ACROSS THE LANES (DECISIONS #89). This lane's
        # FIRST pass is the cold one and has always been recorded unprefixed,
        # while the second wears "warm_"; the page reads the unprefixed names,
        # so they stay, and these aliases let a table ask every lane the same
        # question without knowing which lane it is asking.
        for _op in OLTP_READS:
            out[f"cold_{_op}_p50_ms"] = out[f"{_op}_p50_ms"]
            out[f"cold_{_op}_p99_ms"] = out[f"{_op}_p99_ms"]
        # THE ANSWERS THE WARM PASS RETURNED (DECISIONS #88): every row of
        # every read, over the same seeded id list on every engine, hashed
        # here rather than in the loop. The two passes ask the same questions,
        # so digesting the second is digesting both.
        for op in OLTP_READS:
            bench_common.record_result(out, op, collected.get(op), **READ_DIGEST[op])
        # HOW LOCAL IS THE THREE-HOP READ? Untimed, over the first
        # VISITED_SAMPLE ids: the distinct persons at three hops before the
        # age filter, which is the set hop3f filters. The page can now say
        # "stays local" against a number.
        _beat.mark("visited-probe-start", n=min(VISITED_SAMPLE, len(ids)))
        visited = []
        for pid in ids[:VISITED_SAMPLE]:
            try:
                visited.append((pid, first_value(ad.run_visited(pid))))
            except Exception as e:  # noqa: BLE001
                out["hop3_visited_error"] = f"{e.__class__.__name__}: {e}"
                break
        vals = sorted(v for _p, v in visited if isinstance(v, (int, float)))
        if vals:
            out["hop3_visited_p50"] = vals[len(vals) // 2]
            out["hop3_visited_max"] = vals[-1]
            out["hop3_visited_n_ids"] = len(vals)
            out["hop3_visited_share"] = round(vals[len(vals) // 2] / float(n_persons), 6)
            bench_common.record_result(out, "hop3_visited", visited, **VISITED_DIGEST)
        _beat.mark("visited-probe-done", p50=out.get("hop3_visited_p50"))
        # Writes stay single-pass on purpose. A second write pass is not a
        # warm repeat, it is a different workload against a larger graph.
        # 1000 writes, not 100: a p99 over 95 timed samples is the second
        # slowest write, not a tail. Ten samples deep at 1000 (2026-09-10).
        #
        # CRUD_OPS, not min(1000, n_q), since 2026-10: DECISIONS #82a asks for
        # 1,000 of each single-record operation per repetition, and n_q is the
        # read set's size, which is 500 at small and 100 at large. The start
        # ids cycle through the read set so a write still attaches to a real
        # person.
        n_writes = CRUD_OPS
        lat = []
        _beat.mark("writes-start", n=n_writes)
        for w in range(n_writes):
            pid = ids[w % len(ids)]
            new_id = write_id_base + w
            t = time.perf_counter()
            ad.run_write(pid, new_id)
            if w >= 5:
                surreal_common.keep(ad, lat, (time.perf_counter() - t) * 1000)
        lat.sort()
        out["write_p50_ms"] = round(pct(lat, 0.50), 3)
        out["write_p95_ms"] = round(pct(lat, 0.95), 3)
        # The reads recorded p99 and the writes stopped at p95, so the page
        # had a p99 beside every latency except this one (2026-09-10).
        out["write_p99_ms"] = round(pct(lat, 0.99), 3)
        out["write_ops"] = n_writes
        _beat.mark("writes-done", n=n_writes, p50=out["write_p50_ms"])
        # WHAT THE WRITES LEFT BEHIND (#88): the persons they created, read
        # back untimed. A create that silently wrote nothing fails the gate.
        bench_common.record_result(out, "graph_insert", ad.person_scan(write_id_base),
                                   **PERSON_STATE_DIGEST)
        # UPDATE, the third of the four (DECISIONS #82a): one property of one
        # record, set to a fixed value, over the same ids the writes created.
        ulat = []
        _beat.mark("updates-start", n=n_writes)
        for w in range(n_writes):
            new_id = write_id_base + w
            t = time.perf_counter()
            ad.run_update(new_id)
            if w >= 5:
                surreal_common.keep(ad, ulat, (time.perf_counter() - t) * 1000)
        ulat.sort()
        out["update_p50_ms"] = round(pct(ulat, 0.50), 3)
        out["update_p95_ms"] = round(pct(ulat, 0.95), 3)
        out["update_p99_ms"] = round(pct(ulat, 0.99), 3)
        out["update_ops"] = n_writes
        _beat.mark("updates-done", n=n_writes, p50=out["update_p50_ms"])
        bench_common.record_result(out, "graph_update", ad.person_scan(write_id_base),
                                   **PERSON_STATE_DIGEST)
        # DELETE (2026-10, DECISIONS #82): the write's partner, over the same
        # ids the write pass created, in the same order. Single pass, like the
        # write, and for the same reason: a delete is not repeatable.
        dlat = []
        _beat.mark("deletes-start", n=n_writes)
        for w in range(n_writes):
            new_id = write_id_base + w
            t = time.perf_counter()
            ad.run_delete(new_id)
            if w >= 5:
                surreal_common.keep(ad, dlat, (time.perf_counter() - t) * 1000)
        dlat.sort()
        out["delete_p50_ms"] = round(pct(dlat, 0.50), 3)
        out["delete_p95_ms"] = round(pct(dlat, 0.95), 3)
        out["delete_p99_ms"] = round(pct(dlat, 0.99), 3)
        out["delete_ops"] = n_writes
        _beat.mark("deletes-done", n=n_writes, p50=out["delete_p50_ms"])
        # Nothing must be left: a delete that deleted nothing is a fast number
        # over a graph that still holds the rows (#82a).
        bench_common.record_result(out, "graph_delete", ad.person_scan(write_id_base),
                                   **PERSON_STATE_DIGEST)
        # DECISIONS #89: where a split does not apply the row says why.
        out["cold_warm_na"] = bench_common.NA_COLD_WARM_TXN
        out["oltp_total_s"] = round(time.perf_counter() - total_t0, 2)
    else:
        for qname, text in OLAP_QUERIES.items():
            # LSQB'S NINE NEED THE MESSAGE HALF (graph_common
            # .NA_LSQB_NO_MESSAGE_HALF). Without it they each count zero
            # matches over labels the corpus does not hold. Skipped with the
            # reason on the row, once, because the absence is a property of
            # this corpus and identical for every engine on it -- not of any
            # engine, which is what an unexpressible declaration states.
            if qname in LSQB_QUERIES and not ad._load_messages:
                out["lsqb_na"] = NA_LSQB_NO_MESSAGE_HALF
                _beat.mark(f"olap-{qname}-skipped-no-message-half")
                continue
            # DECISIONS #88: an engine that cannot ask the question says so on
            # the row, with its reason, and is not silently skipped.
            reason = getattr(ad, "UNEXPRESSIBLE", {}).get(qname)
            if reason:
                bench_common.record_unexpressible(out, qname, reason)
                out[f"{qname}_unexpressible"] = reason
                _beat.mark(f"olap-{qname}-unexpressible")
                continue
            _beat.mark(f"olap-{qname}-start", iters=OLAP_ITERATIONS)
            # The warmup WAS the cold pass, and it was not even timed. Timing
            # it costs nothing (the query ran either way) and gives this lane
            # the cold/warm split every non-vector lane was missing. The dense
            # lane found that split worth about 9x for ArcadeDB, which pages
            # its index off disk while resident comparators do not, so a lane
            # that reports one number without saying which side it is on is
            # reporting an arbitrary point on that curve.
            # THE BUDGET STARTS HERE, BEFORE THE COLD PASS, and that is the
            # part the first version got wrong. Measured on the laptop at micro
            # (2,000 persons, 40,833 edges, 16,949,800 three-paths to walk,
            # 2,776 triangles), one Neo4j triangle count runs for MINUTES: a
            # budget that only bounds the warm loop lets the cold pass run
            # unbounded and then pays for one more full iteration before
            # noticing, which is how a five-minute cell becomes a ten-minute
            # one. With the cold pass inside the budget, a query that blows it
            # on the first touch runs zero warm iterations and the row says so.
            # The budget is per tier and per query, from the bench host's own
            # measured medians (DECISIONS #106, budget_lookup/derive_budgets);
            # where a tier has no measurement yet it falls back to the lane's
            # flat constant and the row records which it was.
            # A QUERY THE TIER EXCLUDES IS NOT RUN AND NOT BLANK. The reason
            # goes on the row so the page declares it, the same way an
            # engine's UNEXPRESSIBLE is declared -- except this one is about
            # the SIZE and applies to every engine, so no engine looks worse
            # for it (graph_common.TIER_EXCLUDED, BUGS F74).
            # The count a fallback budget is divided by is the queries this
            # TIER runs, not every query the lane defines: dividing by the
            # excluded ones would hand the survivors a smaller share than the
            # cell actually has to give.
            _QUERIES_THIS_TIER = [q for q in OLAP_QUERIES
                                  if not graph_common.tier_excluded(args.scale, q)]
            _excl = graph_common.tier_excluded(args.scale, qname)
            if _excl:
                out[f"{qname}_excluded_at_tier"] = _excl
                continue
            _budget_s, _budget_src = budget_lookup.budget_for(
                "l2", args.scale, qname, OLAP_BUDGET_S, "BENCH_GRAPH_OLAP_BUDGET_S",
                n_queries=len(_QUERIES_THIS_TIER))
            _budget_t0 = time.perf_counter()
            _c0 = time.perf_counter()
            rows0 = ad.run_olap(qname)  # first touch, now measured
            out[f"cold_{qname}_ms"] = round((time.perf_counter() - _c0) * 1000, 2)
            bench_common.record_first_query(out, qname, out[f"cold_{qname}_ms"])
            # Abandon here rather than spend the whole budget proving what the
            # cold pass already showed (DECISIONS #107).
            _aband, _aband_why = budget_lookup.abandon(
                out[f"cold_{qname}_ms"] / 1000.0, _budget_s, OLAP_ITERATIONS)
            lat = []
            for _ in range(0 if _aband else OLAP_ITERATIONS):
                if time.perf_counter() - _budget_t0 > _budget_s:
                    break
                t = time.perf_counter()
                ad.run_olap(qname)
                surreal_common.keep(ad, lat, (time.perf_counter() - t) * 1000)
            out[f"{qname}_budget_s"] = _budget_s
            out[f"{qname}_budget_source"] = _budget_src
            out[f"{qname}_censored"] = len(lat) < OLAP_ITERATIONS
            if _aband:
                out[f"{qname}_abandoned"] = _aband_why
            if out[f"{qname}_censored"]:
                _beat.mark(f"olap-{qname}-censored", iters=len(lat),
                           budget_s=_budget_s)
            if not lat:
                # THE COLD PASS ALONE EXCEEDED THE BUDGET. A censored cell with
                # one measurement is a result (DECISIONS #82b); a cell with none
                # is a gap. The percentiles are the cold number and the row says
                # they came from one sample, so nobody reads a p99 over a single
                # observation as a tail.
                lat = [out[f"cold_{qname}_ms"]]
                out[f"{qname}_warm_missing"] = True
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
            out[f"{qname}_iters"] = 0 if out.get(f"{qname}_warm_missing") else len(lat)
            out[f"{qname}_rows"] = len(rows0)
            # COLD AND WARM UNDER ONE NAMING CONVENTION (DECISIONS #89). The
            # cold pass above is separate already, so the warm percentiles come
            # from the loop that follows it.
            if not out.get(f"{qname}_warm_missing"):
                bench_common.record_cold_warm(out, qname, lat,
                                              cold_ms=out[f"cold_{qname}_ms"], digits=2)
            else:
                out[f"cold_warm_{qname}_na"] = (
                    f"no warm pass: the cold one alone exceeded the "
                    f"{_budget_s:.0f}s budget (DECISIONS #82b, #106)")
            # THE ANSWER (DECISIONS #88), from the first touch's rows, outside
            # every timed section.
            bench_common.record_result(out, qname, rows0, **OLAP_DIGEST[qname])
            _beat.mark(f"olap-{qname}-done", p50=out[f"{qname}_p50_ms"],
                       digest=out[f"res_{qname}_digest"])
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
    with _beat.phase("close"):
        ad.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)
    # `reconnects` on every SurrealDB row, zero when nothing happened
    # (DECISIONS #91): a dropped connection has to be visible as a number on
    # the row, not as a traceback in a log nobody reads until a cell dies.
    surreal_common.stamp_reconnects(out, ad)
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
