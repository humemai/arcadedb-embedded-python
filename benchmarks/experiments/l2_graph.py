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
            return len(list(s.run(text)))

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


ADAPTERS = {a.name: a for a in
            [ArcadeGraphEmbedded, ArcadeGraphServer, Neo4jGraph, LadybugGraph]}


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

    ad = ADAPTERS[args.backend]()
    t0 = time.perf_counter()
    ad.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = ad.version

    t0 = time.perf_counter()
    ad.build(n_persons)
    ad.post_build(args.workload)
    out["build_s"] = round(time.perf_counter() - t0, 2)

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
                    ad.run_cypher(tmpl.format(id=pid))
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
        n_writes = min(100, n_q)
        lat = []
        for w, pid in enumerate(ids[:n_writes]):
            new_id = write_id_base + w
            t = time.perf_counter()
            ad.run_cypher_write(OLTP_WRITE.format(id=pid, new_id=new_id))
            if w >= 5:
                lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["write_p50_ms"] = round(pct(lat, 0.50), 3)
        out["write_p95_ms"] = round(pct(lat, 0.95), 3)
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
            rows0 = ad.run_cypher(text)  # first touch, now measured
            out[f"cold_{qname}_ms"] = round((time.perf_counter() - _c0) * 1000, 2)
            lat = []
            for _ in range(OLAP_ITERATIONS):
                t = time.perf_counter()
                ad.run_cypher(text)
                lat.append((time.perf_counter() - t) * 1000)
            # p50 FIRST, because the page prints these as times and asserts
            # elsewhere that pycost is its only non-p50 ms column. Three of these
            # were means, where one GC pause inside five iterations moves the
            # published number and a median would not have noticed.
            lat_sorted = sorted(lat)
            out[f"{qname}_p50_ms"] = round(statistics.median(lat_sorted), 2)
            out[f"{qname}_p95_ms"] = round(
                lat_sorted[max(0, int(0.95 * (len(lat_sorted) - 1)))], 2)
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
    if _ingested["persons"] and _ingested["persons"] < n_persons:
        raise SystemExit(
            f"ingested {_ingested['persons']:,} persons against a declared "
            f"{n_persons:,} for scale {args.scale}: the corpus is short, so every "
            f"per-second figure in this row is inflated by {n_persons/_ingested['persons']:.2f}x.")

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
