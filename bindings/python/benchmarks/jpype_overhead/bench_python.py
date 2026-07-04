"""Python-side layered measurements for the JPype-overhead benchmark.

Runs the same workloads as OverheadBench.java on the same databases, JARs, JRE
and JVM flags, adding intermediate layers so the overhead can be attributed:

  vector:   P-raw-call (pure JPype call, args pre-converted)
            P-rawconv  (adds query-vector marshaling)
            P-wrapper  (VectorIndex.find_nearest incl. record re-fetch loop)
            P-SQL      (db.query vectorNeighbors — the example-12 path)
  query:    P-onecol / P-allcols-get / P-allcols-todict / P-tolist / P-embcol / P-groupby
  write:    P-insert-sql
  cypher:   P-traverse / P-project
  fulltext: P-bm25
  lifecycle:P-create-close / P-open / P-first-query (+ JVM start reported as INFO)
  micro:    conversion primitives (timeit)

Output protocol identical to OverheadBench.java:
  RESULT,<phase>,<layer>,<n>,<mean_us>,<p50_us>,<p95_us>,<p99_us>,<extra>
  PARITY,<phase>,<layer>,<semicolon-joined values>

Usage: uv run python bench_python.py <phase> <dataDir> <dbDir>
"""

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

_JVM_START = time.perf_counter()
import arcadedb_embedded as arcadedb  # noqa: E402  (JVM starts on first factory use)
from arcadedb_embedded.vector import to_java_float_array  # noqa: E402

WARMUP = 20
MEASURED = 100


def report(phase, layer, lat_ns, extra=""):
    s = sorted(lat_ns)
    mean = statistics.fmean(s) / 1e3
    p50 = s[len(s) // 2] / 1e3
    p95 = s[int(len(s) * 0.95)] / 1e3
    p99 = s[min(len(s) - 1, int(len(s) * 0.99))] / 1e3
    print(
        f"RESULT,{phase},{layer},{len(s)},{mean:.1f},{p50:.1f},{p95:.1f},{p99:.1f},{extra}",
        flush=True,
    )


def timed(fn):
    s = time.perf_counter_ns()
    out = fn()
    return time.perf_counter_ns() - s, out


def load_meta(data_dir: Path):
    return json.loads((data_dir / "meta.json").read_text())


def load_queries(data_dir: Path, meta):
    n = meta["num_queries_warmup"] + meta["num_queries_measured"]
    return np.fromfile(data_dir / "queries.bin", dtype="<f4").reshape(
        n, meta["dimensions"]
    )


# ---------- vector ----------


def bench_vector(data_dir: Path, db_dir: str):
    meta = load_meta(data_dir)
    warm, measured = meta["num_queries_warmup"], meta["num_queries_measured"]
    k, ef = meta["k"], meta["ef_search"]
    queries = load_queries(data_dir, meta)
    q_lists = [q.tolist() for q in queries]  # plain Python lists (typical user input)

    with arcadedb.open_database(db_dir) as db:
        java_db = db._java_db
        java_index = (
            java_db.getSchema()
            .getType("VectorData")
            .getPolymorphicIndexByProperties("vector")
            .getIndexesOnBuckets()[0]
        )

        # graph build trigger (same as Java bench)
        s = time.perf_counter()
        java_index.findNeighborsFromVector(to_java_float_array(q_lists[0]), k, ef)
        print(f"INFO,vector-bench,graph_build_s,{time.perf_counter() - s:.1f}")

        # ---- P-raw-call: args pre-converted outside the timer ----
        jvecs = [to_java_float_array(q) for q in q_lists]
        for i in range(warm):
            java_index.findNeighborsFromVector(jvecs[i], k, ef)
        lat, total, first = [], 0, None
        for q in range(measured):
            jv = jvecs[warm + q]
            t, res = timed(lambda: java_index.findNeighborsFromVector(jv, k, ef))
            lat.append(t)
            total += res.size()
            if q == 0:
                first = res
        report("vector", "P-raw-call", lat, f"hits={total / measured}")
        parity = ";".join(str(p.getFirst().toString()) for p in first) + ";"
        print(f"PARITY,vector,P-raw-call,{parity}")

        # ---- P-rawconv: conversion inside the timer ----
        for i in range(warm):
            java_index.findNeighborsFromVector(to_java_float_array(q_lists[i]), k, ef)
        lat = []
        for q in range(measured):
            pv = q_lists[warm + q]
            t, res = timed(
                lambda: java_index.findNeighborsFromVector(
                    to_java_float_array(pv), k, ef
                )
            )
            lat.append(t)
        report("vector", "P-rawconv", lat, "")

        # ---- P-wrapper: the full VectorIndex.find_nearest path ----
        vidx = db.schema.get_vector_index("VectorData", "vector")
        for i in range(warm):
            vidx.find_nearest(q_lists[i], k=k, ef_search=ef)
        lat, total = [], 0
        first_ids = None
        for q in range(measured):
            pv = q_lists[warm + q]
            t, res = timed(lambda: vidx.find_nearest(pv, k=k, ef_search=ef))
            lat.append(t)
            total += len(res)
            if q == 0:
                first_ids = [str(rec.get_rid()) for rec, _ in res]
        report("vector", "P-wrapper", lat, f"hits={total / measured}")
        print("PARITY,vector,P-wrapper," + ";".join(first_ids) + ";")

        # ---- P-SQL: example-12 shape ----
        index_name = "VectorData[vector]"

        def extract_id(rec):
            # mirrors example 12's _extract_result_id
            if rec is None:
                return None
            if isinstance(rec, dict):
                rid = rec.get("id")
                if rid is not None:
                    return int(rid)
                inner = rec.get("record")
                if inner is not None:
                    rec = inner
            if hasattr(rec, "get"):
                rid = rec.get("id")
                if rid is not None:
                    return int(rid)
            return None

        def sql_query(vec):
            row = db.query(
                "sql",
                "SELECT vectorNeighbors(?, ?, ?, ?) as res",
                index_name,
                vec,
                int(k),
                int(ef),
            ).first()
            res = row.get("res") if row is not None else []
            return [i for i in (extract_id(item) for item in res) if i is not None]

        # pass numpy rows exactly like example 12 (a plain list fails overload
        # resolution in db.query varargs — itself a finding for the report)
        for i in range(warm):
            sql_query(queries[i])
        lat, total = [], 0
        first_ids = None
        for q in range(measured):
            pv = queries[warm + q]
            t, ids = timed(lambda: sql_query(pv))
            lat.append(t)
            total += len(ids)
            if q == 0:
                first_ids = ids
        report("vector", "P-SQL", lat, f"hits={total / measured}")
        print("PARITY,vector,P-SQL," + ";".join(str(i) for i in first_ids) + ";")


# ---------- query / result materialization ----------


def bench_query(db_dir: str):
    cols = ["id", "score", "name", "category", "active", "created", "counts"]
    with arcadedb.open_database(db_dir) as db:
        for limit in (1_000, 10_000, 100_000):
            sql_all = f"SELECT id, score, name, category, active, created, counts FROM Doc LIMIT {limit}"
            sql_one = f"SELECT id FROM Doc LIMIT {limit}"
            sql_emb = f"SELECT id, embedding FROM Doc LIMIT {limit}"

            def run_get_all():
                n = 0
                for row in db.query("sql", sql_all):
                    for c in cols:
                        row.get(c)
                    n += 1
                return n

            def run_todict():
                n = 0
                for row in db.query("sql", sql_all):
                    row.to_dict()
                    n += 1
                return n

            def run_tolist():
                return len(db.query("sql", sql_all).to_list())

            def run_one():
                n = 0
                for row in db.query("sql", sql_one):
                    row.get("id")
                    n += 1
                return n

            def run_jsonbatch():
                return len(db.query("sql", sql_all).to_json_list())

            def run_columns():
                cols = db.query("sql", sql_all).to_columns()
                return len(next(iter(cols.values()))) if cols else 0

            def run_emb():
                n = 0
                for row in db.query("sql", sql_emb):
                    row.get("id")
                    row.get("embedding")
                    n += 1
                return n

            for layer, fn in (
                (f"P-allcols-get-{limit}", run_get_all),
                (f"P-allcols-todict-{limit}", run_todict),
                (f"P-tolist-{limit}", run_tolist),
                (f"P-jsonbatch-{limit}", run_jsonbatch),
                (f"P-columns-{limit}", run_columns),
                (f"P-onecol-{limit}", run_one),
                (f"P-embcol-{limit}", run_emb),
            ):
                reps = 12
                lat = []
                for r in range(-3, reps):
                    t, n = timed(fn)
                    if r >= 0:
                        lat.append(t)
                report("query", layer, lat, f"rows={n}")

        def run_agg():
            n = 0
            for row in db.query(
                "sql",
                "SELECT category, count(*) as c, avg(score) as a FROM Doc GROUP BY category",
            ):
                row.get("category"), row.get("c"), row.get("a")
                n += 1
            return n

        lat = []
        for r in range(-5, 50):
            t, _ = timed(run_agg)
            if r >= 0:
                lat.append(t)
        report("query", "P-groupby", lat, "")


# ---------- write ----------


def bench_write(db_dir: str):
    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE DOCUMENT TYPE W")
        db.command("sql", "CREATE PROPERTY W.id INTEGER")
        db.command("sql", "CREATE PROPERTY W.name STRING")
        db.command("sql", "CREATE PROPERTY W.score DOUBLE")

        with db.transaction():  # warmup 1k
            for j in range(1_000):
                db.command(
                    "sql", "INSERT INTO W SET id = ?, name = ?, score = ?", j, f"n{j}", j * 0.5
                )

        lat = []
        i = 0
        for _batch in range(10):
            with db.transaction():
                for _j in range(1_000):
                    idx = 1_000 + i
                    t, _ = timed(
                        lambda: db.command(
                            "sql",
                            "INSERT INTO W SET id = ?, name = ?, score = ?",
                            idx,
                            f"n{idx}",
                            idx * 0.5,
                        )
                    )
                    lat.append(t)
                    i += 1
        report("write", "P-insert-sql", lat, "")


# ---------- cypher ----------


def bench_cypher(db_dir: str):
    with arcadedb.open_database(db_dir) as db:

        def run(cypher):
            checksum = 0
            for row in db.query("opencypher", cypher):
                d = row.to_dict()
                checksum += len(d)
            return checksum

        for layer, cypher, reps in (
            ("P-traverse", "MATCH (a:Person {id: 1})-[:KNOWS*1..2]->(b) RETURN count(b) AS c", MEASURED),
            ("P-project", "MATCH (p:Person) RETURN p.name AS name, p.age AS age", 12),
        ):
            warm = max(3, reps // 10)
            lat = []
            for r in range(-warm, reps):
                t, _ = timed(lambda: run(cypher))
                if r >= 0:
                    lat.append(t)
            report("cypher", layer, lat, "")


# ---------- fulltext ----------


def bench_fulltext(db_dir: str):
    with arcadedb.open_database(db_dir) as db:
        sql = (
            "SELECT content, $score FROM Article "
            "WHERE SEARCH_INDEX('Article[content]', 'vector^2.0 graph') = true "
            "ORDER BY $score DESC LIMIT 100"
        )

        def run():
            n = 0
            for row in db.query("sql", sql):
                row.get("content")
                n += 1
            return n

        lat = []
        for r in range(-WARMUP, MEASURED):
            t, _ = timed(run)
            if r >= 0:
                lat.append(t)
        report("fulltext", "P-bm25", lat, "")


# ---------- lifecycle ----------


def bench_lifecycle(db_base: str):
    print(f"INFO,lifecycle,jvm_plus_import_s,{time.perf_counter() - _JVM_START:.2f}")
    create_ns, open_ns, firstq_ns = [], [], []
    for i in range(10):
        p = f"{db_base}/plc_{i}"
        s = time.perf_counter_ns()
        with arcadedb.create_database(p) as db:
            db.command("sql", "CREATE DOCUMENT TYPE T")
        create_ns.append(time.perf_counter_ns() - s)

        s = time.perf_counter_ns()
        db = arcadedb.open_database(p)
        open_ns.append(time.perf_counter_ns() - s)
        s = time.perf_counter_ns()
        db.query("sql", "SELECT count(*) as c FROM T").first()
        firstq_ns.append(time.perf_counter_ns() - s)
        db.close()
    report("lifecycle", "P-create-close", create_ns, "")
    report("lifecycle", "P-open", open_ns, "")
    report("lifecycle", "P-first-query", firstq_ns, "")


# ---------- micro ----------


def bench_micro(doc_db_dir: str):
    import timeit

    import jpype
    from arcadedb_embedded.type_conversion import convert_java_to_python

    vec384 = [float(i) / 384 for i in range(384)]
    np_row = np.asarray(vec384, dtype=np.float32)

    def t(name, fn, number=2000):
        per_call_us = timeit.timeit(fn, number=number) / number * 1e6
        print(f"MICRO,{name},{per_call_us:.2f}us", flush=True)

    # opening the DB starts the JVM — everything below needs it running
    with arcadedb.open_database(doc_db_dir) as db:
        t("to_java_float_array_list384", lambda: to_java_float_array(vec384))
        t("to_java_float_array_nprow384", lambda: to_java_float_array(np_row))

        JInt = jpype.JClass("java.lang.Integer")(42)
        JStr = jpype.JClass("java.lang.String")("hello world")
        JLdt = jpype.JClass("java.time.LocalDateTime").now()
        JList = jpype.JClass("java.util.ArrayList")()
        JFloat = jpype.JClass("java.lang.Float")
        for v in vec384:
            JList.add(JFloat(v))

        t("convert_int", lambda: convert_java_to_python(JInt), 20000)
        t("convert_string", lambda: convert_java_to_python(JStr), 20000)
        t("convert_localdatetime", lambda: convert_java_to_python(JLdt), 20000)
        t("convert_list384float", lambda: convert_java_to_python(JList), 500)

        rids = [str(r.get("rid")) for r in db.query("sql", "SELECT @rid as rid FROM Doc LIMIT 1000")]

        def lookup_all():
            for rid in rids:
                db.lookup_by_rid(rid)

        per_lookup_us = timeit.timeit(lookup_all, number=5) / (5 * len(rids)) * 1e6
        print(f"MICRO,lookup_by_rid,{per_lookup_us:.2f}us", flush=True)


# ---------- async executor (callback bridging) ----------


def bench_async(db_dir: str):
    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE DOCUMENT TYPE A")
        db.command("sql", "CREATE PROPERTY A.id INTEGER")
        db.command("sql", "CREATE PROPERTY A.name STRING")

        executor = db.async_executor()

        # warmup
        for i in range(1_000):
            executor.command("sql", "INSERT INTO A SET id = ?, name = ?", args=[i, f"w{i}"])
        executor.wait_completion()

        # no-callback throughput: 10k async inserts, one wall-clock number
        s = time.perf_counter_ns()
        for i in range(10_000):
            executor.command(
                "sql", "INSERT INTO A SET id = ?, name = ?", args=[1_000 + i, f"n{i}"]
            )
        executor.wait_completion()
        total_no_cb = time.perf_counter_ns() - s
        report("async", "P-async-insert", [total_no_cb // 10_000] * 1, "total10k")

        # with a Python ok-callback per command (bridged Java->Python)
        done = {"n": 0}

        def on_ok(_rs):
            done["n"] += 1

        s = time.perf_counter_ns()
        for i in range(10_000):
            executor.command(
                "sql",
                "INSERT INTO A SET id = ?, name = ?",
                callback=on_ok,
                args=[11_000 + i, f"c{i}"],
            )
        executor.wait_completion()
        total_cb = time.perf_counter_ns() - s
        report("async", "P-async-insert-callback", [total_cb // 10_000] * 1, f"cb={done['n']}")


if __name__ == "__main__":
    phase, data_dir, db_dir = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    {
        "vector-bench": lambda: bench_vector(data_dir, db_dir),
        "bench-query": lambda: bench_query(db_dir),
        "bench-write": lambda: bench_write(db_dir),
        "bench-cypher": lambda: bench_cypher(db_dir),
        "bench-fulltext": lambda: bench_fulltext(db_dir),
        "bench-lifecycle": lambda: bench_lifecycle(db_dir),
        "micro": lambda: bench_micro(db_dir),
        "bench-async": lambda: bench_async(db_dir),
    }[phase]()
