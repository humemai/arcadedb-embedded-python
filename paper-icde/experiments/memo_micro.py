#!/usr/bin/env python3
"""What the tag memoisation buys, measured on exactly what it changed.

async_executor commit ec2f7a859c replaces

    [convert_python_to_java(v) for v in values]        # stock
with
    _convert_column(values)                            # memoised per distinct str

for non-numeric columns of append_samples. Numeric columns take the buffer
path and are untouched, so the whole effect is on STRING tag columns, and the
whole claim is that TSBS `cpu`'s ten tag columns hold 233 distinct values
across 2,592,000 rows.

This times the two implementations against that exact distribution rather
than timing an ingest around them, because an ingest would bury a
conversion-path change under engine work and make the result depend on
whichever ingest arm happened to be used. Isolate the change, then decide
whether an end-to-end run is worth mini time.

Correctness is checked before speed: memoising is only sound because a Java
String is immutable, so the two implementations must produce equal values.
"""
import os
import sys
import time

# TSBS cpu tag cardinalities: hostname 100, region 10, datacenter 20, rack 100,
# os 3, arch 2, team 5, service 20, service_version 2, service_environment 4.
CARD = [100, 10, 20, 100, 3, 2, 5, 20, 2, 4]
ROWS = int(os.environ.get("MEMO_ROWS", "200000"))


def main():
    home = os.path.expanduser("~")
    dbdir = os.path.join(home, ".cache", "memo_micro_db")
    import arcadedb_embedded as arcadedb
    from arcadedb_embedded.type_conversion import convert_python_to_java

    # A JVM has to be up for convert_python_to_java; the database is incidental.
    db = arcadedb.create_database(dbdir, jvm_kwargs={"heap_size": "2g"})
    try:
        total_distinct = sum(CARD)
        print(f"rows/column {ROWS:,}   columns {len(CARD)}   "
              f"distinct values {total_distinct}")
        print(f"conversions: stock {ROWS * len(CARD):,}  "
              f"memoised {total_distinct}\n")

        def stock(values):
            return [convert_python_to_java(v) for v in values]

        def memoised(values):
            out = []
            seen = {}
            for value in values:
                if type(value) is str:
                    java = seen.get(value)
                    if java is None:
                        java = convert_python_to_java(value)
                        seen[value] = java
                    out.append(java)
                else:
                    out.append(convert_python_to_java(value))
            return out

        cols = [[f"c{i}_{r % card}" for r in range(ROWS)]
                for i, card in enumerate(CARD)]

        # Equal values first. If these disagree the timing is irrelevant.
        probe = cols[0][:1000]
        a, b = stock(probe), memoised(probe)
        assert len(a) == len(b), "length differs"
        assert all(str(x) == str(y) for x, y in zip(a, b)), "values differ"
        print("correctness: stock and memoised produce equal values\n")

        for name, fn in (("stock", stock), ("memoised", memoised)):
            fn(cols[0][:5000])                      # warm JIT/JPype
            t0 = time.perf_counter()
            for c in cols:
                fn(c)
            dt = time.perf_counter() - t0
            rate = (ROWS * len(CARD)) / dt
            print(f"  {name:9} {dt:7.3f} s   {rate:12,.0f} conversions/s")
            if name == "stock":
                stock_dt = dt
            else:
                print(f"\n  speedup on the conversion path: "
                      f"{stock_dt / dt:.1f}x")
                print(f"  time saved per 2.59M-row ten-tag ingest: "
                      f"{(stock_dt - dt) * (2592000 / ROWS):.1f} s")
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    # os._exit in the finally would otherwise swallow the traceback: the first
    # run of this printed nothing at all and looked like a silent no-op.
    try:
        main()
        # The JVM keeps non-daemon threads alive, so a clean interpreter exit
        # can hang; _exit here, on the SUCCESS path only. Putting it in main's
        # finally is what swallowed the traceback twice.
        sys.stdout.flush()
        os._exit(0)
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
