"""Completeness sweep: scale/width axes, tail latency, write-direction micros.

Phases:
  scan-1m <db1m>        P-columns / P-jsonbatch on a 1M-row docs table
  wide <dbwide>         seed + scan 10k rows x 50 columns (columns/jsonbatch/get)
  edges-1m <db>         1M-edge bulk ingest (exercises _BULK_CHUNK chunking)
  tail <docs_db>        10k-sample P-SQL-vector-free tail: to_columns 2k-scan
                        p99/p99.9/max + GC-collection correlation
  writemicro <scratch>  convert_python_to_java micro-benchmarks

Usage: uv run python bench_scale.py <phase> <db_dir> [vector_data_dir]
"""

import statistics
import sys
import time

import arcadedb_embedded as arcadedb


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


def scan_1m(db_dir):
    with arcadedb.open_database(db_dir) as db:
        sql = "SELECT FROM Doc LIMIT 1000000"
        for layer, fn in (
            ("P-columns-1m", lambda: len(next(iter(db.query("sql", sql).to_columns().values())))),
            ("P-jsonbatch-1m", lambda: len(db.query("sql", sql).to_json_list())),
        ):
            lat = []
            n = 0
            for r in range(-1, 4):
                s = time.perf_counter_ns()
                n = fn()
                if r >= 0:
                    lat.append(time.perf_counter_ns() - s)
            report("scale", layer, lat, f"rows={n}")


def wide(db_dir):
    import shutil

    shutil.rmtree(db_dir, ignore_errors=True)
    ncols = 50
    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE DOCUMENT TYPE W")
        cols = [f"c{i}" for i in range(ncols)]
        with db.transaction():
            for r in range(10_000):
                sets = ", ".join(f"c{i} = {r * ncols + i}" for i in range(ncols))
                db.command("sql", f"INSERT INTO W SET {sets}")

        sql = "SELECT FROM W LIMIT 10000"

        def run_get():
            n = 0
            for row in db.query("sql", sql):
                for c in cols:
                    row.get(c)
                n += 1
            return n

        for layer, fn in (
            ("P-columns-wide50", lambda: len(next(iter(db.query("sql", sql).to_columns().values())))),
            ("P-jsonbatch-wide50", lambda: len(db.query("sql", sql).to_json_list())),
            ("P-get-wide50", run_get),
        ):
            lat = []
            n = 0
            for r in range(-1, 6):
                s = time.perf_counter_ns()
                n = fn()
                if r >= 0:
                    lat.append(time.perf_counter_ns() - s)
            report("scale", layer, lat, f"rows={n}")


def edges_1m(db_dir):
    import random
    import shutil

    shutil.rmtree(db_dir, ignore_errors=True)
    rnd = random.Random(9)
    with arcadedb.create_database(db_dir) as db:
        db.command("sql", "CREATE VERTEX TYPE P")
        db.command("sql", "CREATE EDGE TYPE E")
        with db.graph_batch(use_wal=False) as batch:
            rids = batch.create_vertices("P", 50_000)
            srcs = [rids[rnd.randrange(50_000)] for _ in range(1_000_000)]
            dsts = [rids[rnd.randrange(50_000)] for _ in range(1_000_000)]
            s = time.perf_counter_ns()
            batch.new_edges(srcs, "E", dsts)
            per_edge = (time.perf_counter_ns() - s) / 1e3 / 1_000_000
            print(
                f"RESULT,scale,P-edges-1m,1000000,{per_edge:.2f},{per_edge:.2f},{per_edge:.2f},{per_edge:.2f},per-edge-buffered",
                flush=True,
            )
        count = db.query("sql", "SELECT count(*) as c FROM E").first().get("c")
        print(f"INFO,scale,edges_created,{count}", flush=True)


def tail(db_dir):
    import jpype

    with arcadedb.open_database(db_dir) as db:
        mgmt = jpype.JClass("java.lang.management.ManagementFactory")

        def gc_count():
            return sum(int(b.getCollectionCount()) for b in mgmt.getGarbageCollectorMXBeans())

        sql = "SELECT id, name, category FROM Doc LIMIT 2000"
        for _ in range(50):
            db.query("sql", sql).to_columns()
        gc0 = gc_count()
        lat = []
        for _ in range(10_000):
            s = time.perf_counter_ns()
            db.query("sql", sql).to_columns()
            lat.append(time.perf_counter_ns() - s)
        gc1 = gc_count()
        lat.sort()
        n = len(lat)
        print(
            f"RESULT,tail,P-columns-2k,{n},{statistics.fmean(lat)/1e3:.1f},"
            f"{lat[n//2]/1e3:.1f},{lat[int(n*0.99)]/1e3:.1f},{lat[int(n*0.999)]/1e3:.1f},"
            f"max_us={lat[-1]/1e3:.0f};gc_collections={gc1-gc0}",
            flush=True,
        )


def writemicro(db_dir):
    import datetime
    import timeit

    from arcadedb_embedded.type_conversion import convert_python_to_java

    with arcadedb.create_database(db_dir) as db:  # noqa: F841  (JVM must be up)
        d10 = {f"k{i}": i for i in range(10)}
        l100 = list(range(100))
        nested = {"a": {"b": [1, 2, {"c": 3}]}}
        dt = datetime.datetime(2026, 1, 2, 3, 4, 5)
        big = "x" * 1_000_000

        def t(name, fn, n=2000):
            per = timeit.timeit(fn, number=n) / n * 1e6
            print(f"MICRO,py2java_{name},{per:.2f}us", flush=True)

        t("dict10", lambda: convert_python_to_java(d10))
        t("list100", lambda: convert_python_to_java(l100))
        t("nested", lambda: convert_python_to_java(nested))
        t("datetime", lambda: convert_python_to_java(dt))
        t("str1mb", lambda: convert_python_to_java(big), 200)


if __name__ == "__main__":
    phase, db_dir = sys.argv[1], sys.argv[2]
    {
        "scan-1m": scan_1m,
        "wide": wide,
        "edges-1m": edges_1m,
        "tail": tail,
        "writemicro": writemicro,
    }[phase](db_dir)
