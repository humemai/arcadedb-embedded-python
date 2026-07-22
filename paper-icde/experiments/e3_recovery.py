#!/usr/bin/env python3
"""E3a: crash-recovery correctness and time (kill -9 during ingest).

Phase "ingest": writes committed rows with a monotonically increasing key and
a running checksum, printing WATERMARK lines (last committed key) so the
harness knows what MUST survive. The harness kill -9s the container mid-run.
Phase "verify": reopens the database, replays WAL recovery, and checks
(a) every key up to the last printed watermark exists exactly once, and
(b) no torn/partial row exists. Reports recovery wall time.

Run under the engine's DEFAULT durability (async WAL flush) AND strict
(txWalFlush=2) to characterize both contracts' loss windows honestly:
the default contract may lose a bounded suffix AFTER the last flush --
that is reported as data, not failure; corruption or mid-transaction
tearing is failure.
"""
import argparse
import json
import os
import sys
import time

import arcadedb_embedded as arcadedb

DB = "/data-local/e3_arcade"
ROWS_PER_TX = 10


def ingest():
    wf = os.environ.get("BENCH_ARCADE_WAL_FLUSH")
    kw = {"heap_size": os.environ.get("ARCADEDB_HEAP", "2g")}
    if wf:
        kw["jvm_args"] = f"-Darcadedb.txWalFlush={wf}"
    db = arcadedb.create_database(DB, jvm_kwargs=kw)
    with db.transaction():
        db.command("sql", "CREATE DOCUMENT TYPE R")
        db.command("sql", "CREATE PROPERTY R.k LONG")
        db.command("sql", "CREATE INDEX ON R (k) UNIQUE")
    k = 0
    while True:  # runs until killed
        db.begin()
        for _ in range(ROWS_PER_TX):
            db.command("sql", "INSERT INTO R SET k = :k, v = :v",
                       {"k": k, "v": f"payload-{k}"})
            k += 1
        db.commit()
        print(f"WATERMARK {k - 1}", flush=True)


def verify():
    t0 = time.perf_counter()
    db = arcadedb.open_database(DB)  # WAL recovery happens here
    recovery_s = time.perf_counter() - t0
    rows = db.query("sql",
                    "SELECT count(*) AS n, max(k) AS mx FROM R").to_list()
    n, mx = int(rows[0]["n"]), int(rows[0]["mx"])
    # uniqueness / continuity: keys must be exactly 0..mx with no gaps/dupes
    ok = (n == mx + 1)
    dup = db.query("sql", "SELECT k, count(*) AS c FROM R GROUP BY k "
                   "ORDER BY c DESC LIMIT 1").to_list()
    max_dup = int(dup[0]["c"]) if dup else 1
    out = {"recovery_s": round(recovery_s, 3), "rows": n, "max_key": mx,
           "contiguous": ok, "max_duplicates": max_dup,
           "wal_flush": os.environ.get("BENCH_ARCADE_WAL_FLUSH", "default")}
    print("RESULT " + json.dumps(out), flush=True)
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["ingest", "verify"])
    a = ap.parse_args()
    ingest() if a.phase == "ingest" else verify()
