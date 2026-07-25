#!/usr/bin/env python3
"""Pilot for task #82: tabular ingest via AsyncExecutor (parallel, the
engine's idiomatic bulk path) vs the harness's serial SQL INSERT loop.

Both paths write the same N synthetic order rows to separate databases and
report rows/s. Smoke on laptop; freeze numbers on mini.
"""
import json
import os
import time

N = int(os.environ.get("PROBE_ROWS", "500000"))
BATCH = 10_000


def rows():
    for i in range(N):
        yield (i, f"cust_{i % 997}", (i * 37) % 100000 / 100.0,
               ("new", "paid", "shipped")[i % 3])


def serial(db):
    db.command("sql", "CREATE DOCUMENT TYPE OrderS")
    t0 = time.perf_counter()
    db.begin()
    for n, (oid, cust, amt, status) in enumerate(rows()):
        db.command("sql",
                   "INSERT INTO OrderS SET oid=:o, customer=:c, amount=:a, status=:s",
                   {"o": oid, "c": cust, "a": amt, "s": status})
        if (n + 1) % BATCH == 0:
            db.commit()
            db.begin()
    db.commit()
    return time.perf_counter() - t0


def async_path(db):
    # Idiomatic bulk path: typed async createRecord (bucket-partitioned per
    # worker), NOT per-row SQL through async. The bindings do not wrap
    # createRecord yet, so go through the Java handles directly.
    db.command("sql", "CREATE DOCUMENT TYPE OrderA")
    jdb = db.get_java_database()
    jasync = jdb.async_()
    jasync.setParallelLevel(int(os.environ.get("PROBE_PARALLEL", "8")))
    jasync.setCommitEvery(BATCH)
    t0 = time.perf_counter()
    for oid, cust, amt, status in rows():
        doc = jdb.newDocument("OrderA")
        doc.set("oid", oid)
        doc.set("customer", cust)
        doc.set("amount", amt)
        doc.set("status", status)
        jasync.createRecord(doc, None)
    jasync.waitCompletion()
    return time.perf_counter() - t0


def main():
    import arcadedb_embedded as arcadedb
    base = os.environ.get("PROBE_DB_BASE", "/tmp/async_probe")
    heap = os.environ.get("ARCADEDB_HEAP", "3g")
    out = {"n_rows": N}
    for name, fn in (("serial_sql", serial), ("async_parallel", async_path)):
        db = arcadedb.create_database(f"{base}_{name}",
                                      jvm_kwargs={"heap_size": heap,
                                                  "jvm_args": f"-Xms{heap}"})
        dt = fn(db)
        n = db.query("sql", f"SELECT count(*) AS n FROM "
                     f"{'OrderS' if name == 'serial_sql' else 'OrderA'}"
                     ).to_list()[0]["n"]
        db.close()
        out[name] = {"s": round(dt, 2), "rows_per_s": round(N / dt, 1),
                     "count_ok": int(n) == N}
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
