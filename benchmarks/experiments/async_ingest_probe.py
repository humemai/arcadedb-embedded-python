#!/usr/bin/env python3
"""Pilot for task #82: tabular ingest via AsyncExecutor (parallel, the
engine's idiomatic bulk path) vs the harness's serial SQL INSERT loop.

Both paths write the same N synthetic order rows to separate databases and
report rows/s. Smoke on laptop; freeze numbers on mini.
"""
import datetime as _dt
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


def insert_many_path(db):
    db.command("sql", "CREATE DOCUMENT TYPE OrderM")
    t0 = time.perf_counter()
    buf = []
    for oid, cust, amt, status in rows():
        buf.append({"oid": oid, "customer": cust, "amount": amt,
                    "status": status})
        if len(buf) >= 100_000:
            db.insert_many("OrderM", buf, commit_every=BATCH)
            buf = []
    if buf:
        db.insert_many("OrderM", buf, commit_every=BATCH)
    return time.perf_counter() - t0


def insert_many_parallel(db):
    db.command("sql", "CREATE DOCUMENT TYPE OrderP")
    t0 = time.perf_counter()
    buf = []
    for oid, cust, amt, status in rows():
        buf.append({"oid": oid, "customer": cust, "amount": amt,
                    "status": status})
        if len(buf) >= 100_000:
            db.insert_many("OrderP", buf, parallel=True)
            buf = []
    if buf:
        db.insert_many("OrderP", buf, parallel=True)
    return time.perf_counter() - t0


def main():
    import arcadedb_embedded as arcadedb
    base = os.environ.get("PROBE_DB_BASE", "/tmp/async_probe")
    heap = os.environ.get("ARCADEDB_HEAP", "3g")
    out = {"n_rows": N}
    variants = (("serial_sql", serial), ("async_parallel", async_path),
                ("insert_many", insert_many_path),
                ("insert_many_parallel", insert_many_parallel))
    for name, fn in variants:
        db = arcadedb.create_database(f"{base}_{name}",
                                      jvm_kwargs={"heap_size": heap,
                                                  "jvm_args": f"-Xms{heap}"})
        dt = fn(db)
        tname = {"serial_sql": "OrderS", "async_parallel": "OrderA",
                 "insert_many": "OrderM",
                 "insert_many_parallel": "OrderP"}[name]
        n = db.query("sql", f"SELECT count(*) AS n FROM {tname}"
                     ).to_list()[0]["n"]
        db.close()
        out[name] = {"s": round(dt, 2), "rows_per_s": round(N / dt, 1),
                     "count_ok": int(n) == N}
    # WRITE THE ARTIFACT, do not just print it. The paper quotes this probe's
    # 500k-row A/B ("the bindings' bulk insert API sustains 177.1k rows/s
    # against 67.3k for per-row SQL"), and until now the only record of that
    # run was a line of stdout in a queue log. Nothing in results/ backed it,
    # so provenance_check could not see it and the freeze could not re-derive
    # it. Same failure the E4 decomposition had: a real measurement that no
    # auditor could reach.
    #
    # Stamped with the conditions the fairness gate reads, so the row is
    # checkable rather than merely present.
    # The module exposes __version__, not .version -- the lanes read .version
    # off their adapter OBJECT, not off the module, and copying that spelling
    # here silently produced engine_version=None on the first five artifacts.
    # A None here is not cosmetic: the pre-release guard reads engine_version,
    # so a row that cannot name its engine is a row no gate can vouch for.
    # Ask the installed distribution, which cannot disagree with what ran.
    ver = None
    try:
        import importlib.metadata as _md
        ver = _md.version("arcadedb-embedded")
    except Exception:
        try:
            import arcadedb_embedded as _ad
            ver = getattr(_ad, "__version__", None)
        except Exception:
            ver = None
    out.update({
        "producer": "async_ingest_probe.py",
        "role": "engine",
        "lane": "l1_ingest_ab",
        "engine_version": ver,
        "heap": heap,
        "cpuset": os.environ.get("BENCH_CPUSET"),
        "mem_cap": os.environ.get("BENCH_MEM_CAP"),
        "host": os.environ.get("BENCH_HOST", "unknown"),
        "ts_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })
    dest = os.environ.get("PROBE_OUT")
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            json.dump(out, f, indent=1)
        print("WROTE " + dest, flush=True)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
