#!/usr/bin/env python3
"""How a result crosses the Java/Python boundary, which is the cost this
package actually controls.

Every other lane here measures an ENGINE. This one measures the BINDING. The
query is identical in all four arms and so is the work the engine does; the
only difference is how the rows are handed to Python:

    iter_dicts / to_list   per-row JNI, 2+ crossings per row
    to_json_list           one JSON string per batch, parsed by Python
    to_columns             binary columnar buffer, numpy.frombuffer
    to_arrow               the same buffer, wrapped as a pyarrow.Table

The gap is not small and it is not the engine's fault, which is why it belongs
in a paper about Python bindings rather than in a database comparison.

SPEED IS ONLY HALF OF IT. to_columns has to widen a nullable integer column to
float64 and spell the missing values NaN, because a numpy integer array cannot
represent absence. to_arrow keeps int64 and carries a validity bitmap, so the
integers stay integers. For a scientific user that is a correctness property,
not a performance one, and it is the reason to_arrow exists at all rather than
being a thin alias. The second half of this script measures exactly that.

Deliberately mirrors the ICDE-side transport_probe.py loop so the two agree on
everything except the added to_arrow arm and the nulls section.

    PROBE_ROWS=200000 REPS=7 python3 transport_lane.py
"""
import json
import os
import statistics as st
import time

ROWS = int(os.environ.get("PROBE_ROWS", "200000"))
SIZES = [int(x) for x in os.environ.get("SIZES", "10,100,1000,10000,100000").split(",")]
REPS = int(os.environ.get("REPS", "7"))
WARMUP = 2
OUT = os.environ.get("PROBE_OUT", "")


def main():
    import arcadedb_embedded as arcadedb

    try:
        import pyarrow  # noqa: F401
        have_arrow = True
    except ImportError:
        have_arrow = False

    db = arcadedb.create_database(
        os.path.expanduser("~/.cache/transport_lane_db"),
        jvm_kwargs={"heap_size": "6g", "jvm_args": "-Xms6g"})
    rec = {"engine_version": arcadedb.__version__, "rows": ROWS, "reps": REPS,
           "pyarrow": have_arrow, "timings": {}, "nulls": {}}
    print(f"engine {arcadedb.__version__}  rows {ROWS:,}  reps {REPS}  "
          f"pyarrow={have_arrow}", flush=True)

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
    if have_arrow:
        paths.append(("to_arrow", lambda rs: (lambda t: t.num_rows if t is not None else -1)(rs.to_arrow())))

    names = [p[0] for p in paths]
    print("  " + "".join(f"{n:>16}" for n in ["rows"] + names), flush=True)
    for n in SIZES:
        if n > ROWS:
            continue
        med = {}
        for name, fn in paths:
            ts = []
            for r in range(REPS + WARMUP):
                t0 = time.perf_counter()
                fn(db.query("sql", q(n)))
                dt = (time.perf_counter() - t0) * 1e3
                if r >= WARMUP:
                    ts.append(dt)
            med[name] = st.median(ts)
        rec["timings"][str(n)] = med
        print("  " + f"{n:>16,}" + "".join(f"{med[x]:>16.2f}" for x in names), flush=True)

    base_name = "to_columns"
    print(f"\nratios vs {base_name} (higher = the transport is costing us):", flush=True)
    for n, med in rec["timings"].items():
        base = med[base_name]
        parts = "   ".join(f"{x} {med[x]/base:5.2f}x" for x in names if x != base_name)
        print(f"  {int(n):>8,} rows:  {parts}", flush=True)

    # ---- the half that is about correctness, not speed --------------------
    # A nullable integer column is the case where the two columnar paths stop
    # agreeing. numpy has no integer NA, so to_columns must widen to float64
    # and write NaN; arrow keeps int64 and marks the slot invalid.
    print("\nnullable integers: what survives the crossing", flush=True)
    db.command("sql", "CREATE DOCUMENT TYPE measurements")
    db.command("sql", "CREATE PROPERTY measurements.sample_id LONG")
    db.command("sql", "CREATE PROPERTY measurements.reading LONG")
    db.begin()
    # Every third reading is absent, which is what a real instrument feed
    # looks like and what a dropped-sensor column looks like after a join.
    db.insert_many("measurements",
                   [{"sample_id": i, **({} if i % 3 == 2 else {"reading": i * 7})}
                    for i in range(3000)],
                   commit_every=1000)
    db.commit()

    cols = db.query("sql", "SELECT sample_id, reading FROM measurements").to_columns()
    c_read = cols["reading"]
    rec["nulls"]["to_columns_dtype"] = str(getattr(c_read, "dtype", type(c_read).__name__))
    try:
        import numpy as np
        rec["nulls"]["to_columns_nan_count"] = int(np.isnan(c_read).sum())
        rec["nulls"]["to_columns_is_integer"] = bool(np.issubdtype(c_read.dtype, np.integer))
    except Exception as e:
        rec["nulls"]["to_columns_note"] = f"{type(e).__name__}: {e}"

    if have_arrow:
        tab = db.query("sql", "SELECT sample_id, reading FROM measurements").to_arrow()
        col = tab.column("reading")
        rec["nulls"]["to_arrow_type"] = str(col.type)
        rec["nulls"]["to_arrow_null_count"] = int(col.null_count)
        rec["nulls"]["to_arrow_is_integer"] = bool(
            __import__("pyarrow").types.is_integer(col.type))

    print(f"  to_columns : dtype={rec['nulls'].get('to_columns_dtype')} "
          f"integer={rec['nulls'].get('to_columns_is_integer')} "
          f"NaNs={rec['nulls'].get('to_columns_nan_count')}", flush=True)
    if have_arrow:
        print(f"  to_arrow   : type={rec['nulls'].get('to_arrow_type')} "
              f"integer={rec['nulls'].get('to_arrow_is_integer')} "
              f"nulls={rec['nulls'].get('to_arrow_null_count')}", flush=True)
        if rec["nulls"].get("to_arrow_is_integer") and not rec["nulls"].get("to_columns_is_integer"):
            print("  => same buffer, but only the arrow path keeps the column an "
                  "integer. That is the reason to_arrow exists.", flush=True)

    db.close()
    if OUT:
        with open(OUT, "w") as f:
            json.dump(rec, f, indent=1)
        print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
