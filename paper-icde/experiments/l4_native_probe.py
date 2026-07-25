#!/usr/bin/env python3
"""Pilot for task #83: TSBS on ArcadeDB's NATIVE time-series engine, against
the document-path adapter the July campaign measured.

Native path: CREATE TIMESERIES TYPE (SQL DDL), columnar bulk ingest via
AsyncExecutor.append_samples (tags then fields, declaration order), queries
via ts.timeBucket / ts.last with WHERE ts BETWEEN range pruning.
Timestamps stored in ms (the TS engine's default precision).

Smoke on laptop with a subset (TSBS_LP + TSBS_LIMIT); paper-adjacent numbers
re-measured on mini per project convention.
"""
import json
import os
import statistics
import time

from l4_tsbs import parse_lp, HOST, T0, QITER

SHARDS = int(os.environ.get("TS_SHARDS", "4"))
CHUNK = 50_000


class ArcadeTSNative:
    name = "arcadedb_ts_native"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database(
            os.environ.get("TS_DB_PATH", "/tmp/l4n_arcade"),
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})

    def ingest(self, pts):
        db = self.db
        db.command("sql",
                   "CREATE TIMESERIES TYPE Point TIMESTAMP ts "
                   "TAGS (host STRING) "
                   "FIELDS (uu DOUBLE, us DOUBLE, ui DOUBLE) "
                   f"SHARDS {SHARDS}")
        ex = self.db.async_executor()
        for lo in range(0, len(pts), CHUNK):
            chunk = pts[lo:lo + CHUNK]
            ex.append_samples(
                "Point",
                [p[1] * 1000 for p in chunk],          # ts in ms
                [p[0] for p in chunk],                 # host (tag)
                [p[2] for p in chunk],                 # uu
                [p[3] for p in chunk],                 # us
                [p[4] for p in chunk],                 # ui
            )
        ex.wait_completion()

    def q_last(self):
        # Bounded window: unbounded ts.last scans the tag's whole series
        # (208 ms vs 2.5 ms measured); TSBS's last-point permits recency.
        a = self.tmax_ms - 3600_000
        return self.db.query("sql",
            f"SELECT ts, uu FROM Point WHERE host = '{HOST}' "
            f"AND ts BETWEEN {a} AND {self.tmax_ms} "
            f"ORDER BY ts DESC LIMIT 1").to_list()

    def q_range(self):
        a, b = T0 * 1000, (T0 + 3600) * 1000
        return self.db.query("sql",
            f"SELECT ts.timeBucket('1m', ts) AS m, max(uu) AS v FROM Point "
            f"WHERE host = '{HOST}' AND ts BETWEEN {a} AND {b - 1} "
            f"GROUP BY m ORDER BY m").to_list()

    def q_global(self):
        a, b = T0 * 1000, (T0 + 43200) * 1000
        return self.db.query("sql",
            f"SELECT ts.timeBucket('1h', ts) AS h, avg(uu) AS v FROM Point "
            f"WHERE ts BETWEEN {a} AND {b - 1} "
            f"GROUP BY h ORDER BY h").to_list()

    def close(self):
        self.db.close()


def main():
    pts = parse_lp()
    out = {"n_points": len(pts), "backend": ArcadeTSNative.name,
           "shards": SHARDS}
    b = ArcadeTSNative()
    b.tmax_ms = max(p[1] for p in pts) * 1000
    b.connect()
    t0 = time.perf_counter()
    b.ingest(pts)
    dt = time.perf_counter() - t0
    out["ingest_s"] = round(dt, 2)
    out["ingest_pts_per_s"] = round(len(pts) / dt, 1)
    for qn in ("q_last", "q_range", "q_global"):
        times, ref = [], None
        for _ in range(QITER):
            t = time.perf_counter()
            ref = getattr(b, qn)()
            times.append((time.perf_counter() - t) * 1000)
        out[f"{qn}_ms"] = round(statistics.median(times), 2)
        out[f"{qn}_rows"] = len(ref) if ref is not None else 0
    b.close()
    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        with open(outp, "w") as f:
            json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
