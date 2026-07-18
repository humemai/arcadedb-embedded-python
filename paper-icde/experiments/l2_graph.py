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

    def build(self, n_persons):
        # Native Java API with batched commits — ArcadeDB's embedded bulk path
        jdb = self.db.get_java_database()
        verts = [None] * n_persons
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
        # ArcadeDB's documented OLAP mode: build a Graph Analytical View and
        # wait for READY; the executor then uses it for matching traversals.
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
        self.rq.auth = ("root", "icdebench")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        self.version = "server:latest"
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
            buf.append(f"CREATE VERTEX Person SET id = {i}, name = '{name}', "
                       f"age = {age}, city = '{city}'")
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
            f"bolt://{host}:{port}", auth=("neo4j", "icdebench"))
        self.driver.verify_connectivity()
        self.version = f"neo4j-driver:{neo4j.__version__}"
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
        pcsv, kcsv = "/tmp/l2_persons.csv", "/tmp/l2_knows.csv"
        with open(pcsv, "w") as f:
            for i, name, age, city in gen_persons(n_persons):
                f.write(f"{i},{name},{age},{city}\n")
        with open(kcsv, "w") as f:
            for src, dst, since in gen_edges(n_persons):
                f.write(f"{src},{dst},{since}\n")
        self.conn.execute(f"COPY Person FROM '{pcsv}'")
        self.conn.execute(f"COPY KNOWS FROM '{kcsv}'")
        os.unlink(pcsv)
        os.unlink(kcsv)

    def post_build(self, workload):
        self.conn.execute("CHECKPOINT")

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

    n_persons = SCALE_PERSONS[args.scale]
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
        for op, tmpl in OLTP_READS.items():
            lat = []
            for w, pid in enumerate(ids):
                t = time.perf_counter()
                ad.run_cypher(tmpl.format(id=pid))
                if w >= 5:  # warmups discarded
                    lat.append((time.perf_counter() - t) * 1000)
            lat.sort()
            out[f"{op}_p50_ms"] = round(pct(lat, 0.50), 3)
            out[f"{op}_p95_ms"] = round(pct(lat, 0.95), 3)
            out[f"{op}_p99_ms"] = round(pct(lat, 0.99), 3)
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
            rows0 = ad.run_cypher(text)  # warmup, sanity row count
            lat = []
            for _ in range(OLAP_ITERATIONS):
                t = time.perf_counter()
                ad.run_cypher(text)
                lat.append((time.perf_counter() - t) * 1000)
            out[f"{qname}_mean_ms"] = round(statistics.mean(lat), 2)
            out[f"{qname}_min_ms"] = round(min(lat), 2)
            out[f"{qname}_rows"] = rows0

    ad.close()
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
