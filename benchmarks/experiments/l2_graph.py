#!/usr/bin/env python3
"""L2 graph lane: ArcadeDB (embedded + server) vs Neo4j vs LadybugDB.

Cypher on all four backends over the shared deterministic social graph
(graph_common). Two workloads: oltp (indexed point/1-hop/2-hop reads +
create-and-link writes, latency percentiles) and olap (three full-graph
aggregations; ArcadeDB runs them against a Graph Analytical View, its
documented OLAP mode). Ingest uses each engine's native bulk path.
"""
import argparse
import json
import os
import statistics
import sys
import time
import surreal_common
import arango_common

from graph_common import (HOP3_VISITED, OLAP_BUDGET_S, OLAP_DIGEST, OLAP_ITERATIONS, OLAP_QUERIES,
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
            s.run("CALL db.awaitIndexes()").consume()
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

    def post_build(self, workload):
        with self.driver.session() as s:
            s.run("CALL db.awaitIndexes()").consume()

    def run_cypher(self, text):
        with self.driver.session() as s:
            return [dict(r) for r in s.run(text)]

    def run_cypher_write(self, text):
        with self.driver.session() as s:
            s.run(text).consume()

    def close(self):
        self.driver.close()


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
        # Rows come back positional, in the RETURN clause's order, which is the
        # declared column order the digest compares against.
        return [list(r) for r in self.conn.execute(text)]


class SurrealGraph(Base):
    """SurrealDB through its Python SDK on the SDK's SurrealKV disk store
    (SDK 2.0.0, which carries core 2.3.10), the same LDBC questions in SurrealQL: person records with
    record ids, KNOWS as a RELATE edge table (2026-09-11). The served twin
    below runs the 3.2.4 server on RocksDB."""
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

    def run_olap(self, qname):
        return self._rows(self.db.query(self.OLAP[qname]))

    def run_cypher(self, text):
        raise NotImplementedError("SurrealDB runs SurrealQL through the name-based hooks")

    def close(self):
        try:
            self.db.close()
        except Exception:  # noqa: BLE001
            pass


class SurrealGraphServer(SurrealGraph):
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
        return self._n(self.OLAP[qname])

    def run_cypher(self, text):
        raise NotImplementedError("ArangoDB runs AQL through the name-based hooks")

    def close(self):
        arango_common.close(self.cl)


ADAPTERS = {a.name: a for a in
            [ArcadeGraphEmbedded, ArcadeGraphServer, Neo4jGraph, LadybugGraph,
             SurrealGraph, SurrealGraphServer, ArangoGraph]}

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

    # PHASE MARKERS (2026-09-14, same pattern as l3d_dense): a cell that dies
    # names the phase it was in. Entered and left AROUND the timed work, never
    # inside a timed loop.
    _beat = bench_common.PhaseBeat()
    _beat.mark("cell-start", backend=args.backend, workload=args.workload,
               scale=args.scale, n_persons=n_persons)

    ad = ADAPTERS[args.backend]()
    t0 = time.perf_counter()
    with _beat.phase("connect", backend=args.backend):
        ad.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = ad.version
    out["instrument"] = bench_common.INSTRUMENT

    t0 = time.perf_counter()
    with _beat.phase("build", n=n_persons):
        ad.build(n_persons)
    with _beat.phase("post-build", workload=args.workload):
        ad.post_build(args.workload)
    out["build_s"] = round(time.perf_counter() - t0, 2)
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
                        lat.append(dt)
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
                lat.append((time.perf_counter() - t) * 1000)
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
                ulat.append((time.perf_counter() - t) * 1000)
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
                dlat.append((time.perf_counter() - t) * 1000)
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
            _budget_t0 = time.perf_counter()
            _c0 = time.perf_counter()
            rows0 = ad.run_olap(qname)  # first touch, now measured
            out[f"cold_{qname}_ms"] = round((time.perf_counter() - _c0) * 1000, 2)
            bench_common.record_first_query(out, qname, out[f"cold_{qname}_ms"])
            lat = []
            for _ in range(OLAP_ITERATIONS):
                if time.perf_counter() - _budget_t0 > OLAP_BUDGET_S:
                    break
                t = time.perf_counter()
                ad.run_olap(qname)
                lat.append((time.perf_counter() - t) * 1000)
            out[f"{qname}_budget_s"] = OLAP_BUDGET_S
            out[f"{qname}_censored"] = len(lat) < OLAP_ITERATIONS
            if out[f"{qname}_censored"]:
                _beat.mark(f"olap-{qname}-censored", iters=len(lat),
                           budget_s=OLAP_BUDGET_S)
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
                    f"{OLAP_BUDGET_S:.0f}s budget (DECISIONS #82b)")
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
