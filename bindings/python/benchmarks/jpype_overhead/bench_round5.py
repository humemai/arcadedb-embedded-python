"""Round-5 Python benches: UPDATE/DELETE, record mutation, GraphBatch,
threaded OLTP scaling, extreme value shapes, importer/exporter wrappers.

Same RESULT protocol as bench_python.py.
Usage: uv run python bench_round5.py <phase> <dbDir>
"""

import statistics
import sys
import time

import arcadedb_embedded as arcadedb

WARM = 1_000


def report(phase, layer, lat_ns, extra=""):
    s = sorted(lat_ns)
    mean = statistics.fmean(s) / 1e3
    p50 = s[len(s) // 2] / 1e3
    p95 = s[int(len(s) * 0.95)] / 1e3
    p99 = s[min(len(s) - 1, int(len(s) * 0.99))] / 1e3
    print(f"RESULT,{phase},{layer},{len(s)},{mean:.1f},{p50:.1f},{p95:.1f},{p99:.1f},{extra}", flush=True)


def bench_update(db_dir):
    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE DOCUMENT TYPE U")
        db.command("sql", "CREATE PROPERTY U.id INTEGER")
        db.command("sql", "CREATE PROPERTY U.score DOUBLE")
        db.command("sql", "CREATE INDEX ON U (id) UNIQUE")
        for b in range(10):
            with db.transaction():
                for j in range(1_000):
                    i = b * 1_000 + j
                    db.command("sql", "INSERT INTO U SET id = ?, score = ?", i, i * 1.0)

        lat_u, i = [], 0
        for _b in range(10):
            with db.transaction():
                for _j in range(1_000):
                    s = time.perf_counter_ns()
                    db.command("sql", "UPDATE U SET score = score + 1 WHERE id = ?", i)
                    lat_u.append(time.perf_counter_ns() - s)
                    i += 1
        report("update", "P-update-sql", lat_u)

        lat_d, i = [], 0
        for _b in range(5):
            with db.transaction():
                for _j in range(1_000):
                    s = time.perf_counter_ns()
                    db.command("sql", "DELETE FROM U WHERE id = ?", i)
                    lat_d.append(time.perf_counter_ns() - s)
                    i += 1
        report("update", "P-delete-sql", lat_d)


def bench_mutate(db_dir):
    with arcadedb.open_database(db_dir) as db:
        docs = [row for row in db.query("sql", "SELECT FROM Doc LIMIT 10000")]
        lat = []
        i = 0
        for b in range(10):
            with db.transaction():
                for j in range(1_000):
                    rec = docs[i].get_element()
                    s = time.perf_counter_ns()
                    rec.modify().set("score", i * 0.5).save()
                    lat.append(time.perf_counter_ns() - s)
                    i += 1
        report("mutate", "P-modify-set-save", lat)


def bench_graphbatch(db_dir):
    import random

    def seeded_batch(path, edge_fn):
        """Fresh db + batch: 20k vertices, then edge_fn buffers 60k edges.
        Separate DBs per layer so one layer's buffered edges can't push
        engine flush I/O into another layer's timed window."""
        rnd = random.Random(11)
        with arcadedb.create_database(path) as db:
            db.command("sql", "CREATE VERTEX TYPE P")
            db.command("sql", "CREATE EDGE TYPE E")
            with db.graph_batch(use_wal=False) as batch:
                s_v = time.perf_counter_ns()
                rids = []
                for b in range(4):
                    props = [{"id": b * 5_000 + i, "name": f"p{i}"} for i in range(5_000)]
                    rids.extend(batch.create_vertices("P", props))
                per_vertex = (time.perf_counter_ns() - s_v) / 1e3 / 20_000
                pairs = [
                    (rids[rnd.randrange(20_000)], rids[rnd.randrange(20_000)])
                    for _ in range(60_000)
                ]
                s_e = time.perf_counter_ns()
                edge_fn(batch, pairs)
                per_edge = (time.perf_counter_ns() - s_e) / 1e3 / 60_000
        return per_vertex, per_edge

    def per_edge_loop(batch, pairs):
        for a, c in pairs:
            batch.new_edge(a, "E", c)

    def bulk(batch, pairs):
        batch.new_edges([a for a, _ in pairs], "E", [c for _, c in pairs])

    pv, pe = seeded_batch(db_dir, per_edge_loop)
    print(f"RESULT,graphbatch,P-create-vertices,20000,{pv:.1f},{pv:.1f},{pv:.1f},{pv:.1f},per-vertex", flush=True)
    print(f"RESULT,graphbatch,P-new-edge,60000,{pe:.2f},{pe:.2f},{pe:.2f},{pe:.2f},per-edge-buffered", flush=True)
    _, pb = seeded_batch(db_dir + "_bulk", bulk)
    print(f"RESULT,graphbatch,P-new-edges-bulk,60000,{pb:.2f},{pb:.2f},{pb:.2f},{pb:.2f},per-edge-buffered", flush=True)


def bench_threads(db_dir):
    import random
    from concurrent.futures import ThreadPoolExecutor

    with arcadedb.open_database(db_dir) as db:
        try:
            db.command("sql", "CREATE INDEX ON Doc (id) UNIQUE")
        except Exception:
            pass
        ops_per_worker = 2_000

        def worker(seed):
            r = random.Random(seed)
            for _op in range(ops_per_worker):
                doc_id = r.randrange(100_000)
                if r.random() < 0.9:
                    for _row in db.query("sql", "SELECT score FROM Doc WHERE id = ?", doc_id):
                        pass
                else:
                    db.run_in_transaction(
                        lambda d=doc_id: db.command(
                            "sql", "UPDATE Doc SET score = score + 1 WHERE id = ?", d
                        )
                    )

        for workers in (1, 2, 4, 8):
            s = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(worker, range(42, 42 + workers)))
            qps = workers * ops_per_worker / (time.perf_counter() - s)
            print(f"RESULT,threads,P-oltp-{workers}t,{workers * ops_per_worker},{qps:.0f},{qps:.0f},{qps:.0f},{qps:.0f},qps", flush=True)


def bench_values(db_dir):
    """Extreme value shapes through the conversion layer (Python-only micro)."""
    import timeit

    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE DOCUMENT TYPE V")
        big_str = "x" * 1_000_000
        nested = {"a": {"b": {"c": {"d": {"e": [1, 2, 3]}}}}}
        big_list = [float(i) for i in range(10_000)]
        with db.transaction():
            db.command(
                "sql", "INSERT INTO V SET s = ?, nested = ?, biglist = ?", big_str, nested, big_list
            )

        row = db.query("sql", "SELECT s, nested, biglist FROM V").first()

        def t(name, fn, n=200):
            per = timeit.timeit(fn, number=n) / n * 1e6
            print(f"MICRO,value_{name},{per:.1f}us", flush=True)

        t("get_1mb_string", lambda: row.get("s"))
        t("get_nested_depth5", lambda: row.get("nested"))
        t("get_10k_float_list", lambda: row.get("biglist"), 50)


def bench_importexport(db_dir):
    with arcadedb.open_database(db_dir) as db:
        out = db_dir + "_pyexport.jsonl.tgz"
        import os

        if os.path.exists(out):
            os.remove(out)
        s = time.perf_counter_ns()
        db.export_database(out, format="jsonl", overwrite=True)
        total_ms = (time.perf_counter_ns() - s) / 1e6
        print(f"RESULT,importexport,P-export-jsonl,1,{total_ms:.0f},0,0,0,ms-total", flush=True)

        # export_to_csv: the pure-Python row loop (inherits per-row conversion tax)
        csv_out = db_dir + "_pyexport.csv"
        if os.path.exists(csv_out):
            os.remove(csv_out)
        s = time.perf_counter_ns()
        db.export_to_csv(
            "SELECT id, score, name, category FROM Doc LIMIT 100000", csv_out
        )
        total_ms = (time.perf_counter_ns() - s) / 1e6
        print(f"RESULT,importexport,P-export-csv-100k,1,{total_ms:.0f},0,0,0,ms-total", flush=True)


if __name__ == "__main__":
    phase, db_dir = sys.argv[1], sys.argv[2]
    {
        "bench-update": bench_update,
        "bench-mutate": bench_mutate,
        "bench-graphbatch": bench_graphbatch,
        "bench-threads": bench_threads,
        "bench-values": bench_values,
        "bench-importexport": bench_importexport,
    }[phase](db_dir)
