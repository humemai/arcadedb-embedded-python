#!/usr/bin/env python3
"""What does the result-transport path cost, as a function of result size?

The bindings expose three ways to materialize a ResultSet, and their own
docstrings rank them against Java-native iteration:

    iter_dicts / to_list   per-row JNI, 2+C crossings per row   15-21x
    to_json_list           one JSON string per batch            ~2.7x
    to_columns             binary columnar + numpy frombuffer   ~1.2x

No benchmark lane uses to_columns. Four use the per-row path. Whether that
matters depends on how many rows a query returns, which is why this varies
result size rather than asserting a ratio: a k=10 vector search cannot care,
a wide scan must.

Same query, same data, same process; only the transport differs. Reports
ms and rows/s so the crossover is visible rather than argued.
"""
import os, statistics as st, sys, time

ROWS = int(os.environ.get("PROBE_ROWS", "200000"))
SIZES = [int(x) for x in os.environ.get("SIZES", "10,100,1000,10000,100000").split(",")]
REPS = int(os.environ.get("REPS", "7"))
WARMUP = 2


def main():
    import arcadedb_embedded as arcadedb
    db = arcadedb.create_database(os.path.expanduser("~/.cache/transport_probe_db"),
                                  jvm_kwargs={"heap_size": "6g", "jvm_args": "-Xms6g"})
    print(f"engine {arcadedb.__version__}  rows {ROWS:,}  reps {REPS}", flush=True)
    db.command("sql", "CREATE DOCUMENT TYPE orders")
    for p in ("CREATE PROPERTY orders.id LONG",
              "CREATE PROPERTY orders.customer_id LONG",
              "CREATE PROPERTY orders.amount DOUBLE",
              "CREATE PROPERTY orders.region STRING"):
        db.command("sql", p)
    db.begin()
    buf = []
    for i in range(ROWS):
        buf.append({"id": i, "customer_id": i % 1000,
                    "amount": (i * 37 % 100000) / 100.0,
                    "region": f"r{i % 8}"})
        if len(buf) >= 50_000:
            db.insert_many("orders", buf, commit_every=10_000)
            buf = []
    if buf:
        db.insert_many("orders", buf, commit_every=10_000)
    db.commit()
    print(f"loaded {ROWS:,} rows\n", flush=True)

    def q(n):
        return f"SELECT id, customer_id, amount, region FROM orders LIMIT {n}"

    paths = [
        ("iter_dicts", lambda rs: sum(1 for _ in rs.iter_dicts())),
        ("to_json_list", lambda rs: len(rs.to_json_list())),
        ("to_columns", lambda rs: (lambda c: len(c["id"]) if c else -1)(rs.to_columns())),
    ]

    print(f"{'rows':>8}  {'iter_dicts':>22}  {'to_json_list':>22}  {'to_columns':>22}")
    for n in SIZES:
        if n > ROWS:
            continue
        cells = []
        for name, fn in paths:
            ts = []
            for r in range(REPS):
                rs = db.query("sql", q(n))
                t0 = time.perf_counter()
                got = fn(rs)
                dt = (time.perf_counter() - t0) * 1000
                if r >= WARMUP:
                    ts.append(dt)
            if got == -1:
                cells.append("unavailable")
            else:
                m = st.median(ts)
                cells.append(f"{m:8.2f}ms {n/(m/1000):9,.0f}/s")
        print(f"{n:>8}  {cells[0]:>22}  {cells[1]:>22}  {cells[2]:>22}", flush=True)

    print("\nratios vs to_columns (higher = transport is costing us):")
    for n in SIZES:
        if n > ROWS:
            continue
        med = {}
        for name, fn in paths:
            ts = []
            for r in range(REPS):
                rs = db.query("sql", q(n))
                t0 = time.perf_counter()
                fn(rs)
                dt = (time.perf_counter() - t0) * 1000
                if r >= WARMUP:
                    ts.append(dt)
            med[name] = st.median(ts)
        base = med["to_columns"]
        print(f"  {n:>8} rows:  iter_dicts {med['iter_dicts']/base:5.2f}x   "
              f"to_json_list {med['to_json_list']/base:5.2f}x", flush=True)
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
