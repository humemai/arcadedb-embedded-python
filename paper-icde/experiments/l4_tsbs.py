#!/usr/bin/env python3
"""L4: timeseries lane on TSBS cpu-only data (fixed seed, influx line protocol).

Backends: arcadedb (embedded; Point documents with a composite (host, ts)
index -- its idiomatic timeseries shape), duckdb (table + ART index),
questdb (server; ILP ingest on 9009, SQL over pg-wire). InfluxDB3 omitted
(no stable embedded/pinnable OSS artifact at eval time; disclosed).

Queries (TSBS-flavored):
  q_last   last point for one host
  q_range  1h of one host, per-minute max(usage_user)
  q_global 12h across all hosts, hourly avg(usage_user)

Metrics per rep: ingest points/s, per-query median ms over 10 iterations.
"""
import argparse
import json
import os
import statistics
import time

LP = os.environ.get("TSBS_LP", "/data/tsbs/cpu_influx.lp")
LIMIT = int(os.environ.get("TSBS_LIMIT", "0"))  # 0 = all
QITER = 10
HOST = "host_42"
T0 = 1767225600  # 2026-01-01T00:00:00Z epoch seconds


def parse_lp():
    pts = []  # (host, ts_epoch_s, usage_user, usage_system, usage_idle)
    with open(LP) as f:
        for i, line in enumerate(f):
            if LIMIT and i >= LIMIT:
                break
            try:
                head, fields, ts = line.rsplit(" ", 2)
                host = head.split("hostname=", 1)[1].split(",", 1)[0]
                fd = dict(kv.split("=") for kv in fields.split(","))
                pts.append((host, int(ts) // 1_000_000_000,
                            float(fd["usage_user"].rstrip("i")),
                            float(fd["usage_system"].rstrip("i")),
                            float(fd["usage_idle"].rstrip("i"))))
            except Exception:
                continue
    return pts


class ArcadeTS:
    name = "arcadedb"

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "6g")
        self.db = arcadedb.create_database("/tmp/l4_arcade",
                                           jvm_kwargs={"heap_size": heap})

    def ingest(self, pts):
        db = self.db
        db.command("sql", "CREATE DOCUMENT TYPE Point")
        for c, t in (("host", "STRING"), ("ts", "LONG"), ("uu", "DOUBLE"),
                     ("us", "DOUBLE"), ("ui", "DOUBLE")):
            db.command("sql", f"CREATE PROPERTY Point.{c} {t}")
        db.command("sql", "CREATE INDEX ON Point (host, ts) UNIQUE")
        db.begin()
        for n, (h, ts, uu, us, ui) in enumerate(pts):
            db.command("sql", "INSERT INTO Point SET host=:h, ts=:t, uu=:a, us=:b, ui=:c",
                       {"h": h, "t": ts, "a": uu, "b": us, "c": ui})
            if (n + 1) % 10_000 == 0:
                db.commit()
                db.begin()
        db.commit()

    def q_last(self):
        return self.db.query("sql",
            f"SELECT ts, uu FROM Point WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1").to_list()

    def q_range(self):
        return self.db.query("sql",
            f"SELECT (ts - ts % 60) AS m, max(uu) AS v FROM Point WHERE host='{HOST}' "
            f"AND ts >= {T0} AND ts < {T0+3600} GROUP BY m ORDER BY m").to_list()

    def q_global(self):
        return self.db.query("sql",
            f"SELECT (ts - ts % 3600) AS h, avg(uu) AS v FROM Point "
            f"WHERE ts >= {T0} AND ts < {T0+43200} GROUP BY h ORDER BY h").to_list()

    def close(self):
        self.db.close()


class DuckTS:
    name = "duckdb"

    def connect(self):
        import duckdb
        self.cx = duckdb.connect("/tmp/l4_duck.db")

    def ingest(self, pts):
        self.cx.execute("CREATE TABLE p (host VARCHAR, ts BIGINT, uu DOUBLE, "
                        "us DOUBLE, ui DOUBLE)")
        self.cx.executemany("INSERT INTO p VALUES (?,?,?,?,?)", pts) if len(pts) < 100_000 else None
        if len(pts) >= 100_000:
            import pyarrow as pa
            t = pa.table({"host": [p[0] for p in pts], "ts": [p[1] for p in pts],
                          "uu": [p[2] for p in pts], "us": [p[3] for p in pts],
                          "ui": [p[4] for p in pts]})
            self.cx.register("src", t)
            self.cx.execute("INSERT INTO p SELECT * FROM src")

    def q_last(self):
        return self.cx.execute(
            f"SELECT ts, uu FROM p WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1").fetchall()

    def q_range(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 60) AS m, max(uu) FROM p WHERE host='{HOST}' "
            f"AND ts >= {T0} AND ts < {T0+3600} GROUP BY m ORDER BY m").fetchall()

    def q_global(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 3600) AS h, avg(uu) FROM p WHERE ts >= {T0} "
            f"AND ts < {T0+43200} GROUP BY h ORDER BY h").fetchall()

    def close(self):
        self.cx.close()


class QuestTS:
    name = "questdb"

    def connect(self):
        import socket
        import psycopg
        host = os.environ.get("QUEST_HOST", "localhost")
        self._ilp_host = host
        self.cx = psycopg.connect(
            f"host={host} port=8812 dbname=qdb user=admin password=quest",
            autocommit=True)

    def ingest(self, pts):
        import socket
        s = socket.create_connection((self._ilp_host, 9009))
        buf = []
        for h, ts, uu, us, ui in pts:
            buf.append(f"p,host={h} uu={uu},us={us},ui={ui} {ts*1_000_000_000}")
            if len(buf) >= 20_000:
                s.sendall(("\n".join(buf) + "\n").encode())
                buf = []
        if buf:
            s.sendall(("\n".join(buf) + "\n").encode())
        s.close()
        # wait for WAL apply: poll count until stable
        last, stable = -1, 0
        for _ in range(120):
            try:
                n = self.cx.execute("SELECT count() FROM p").fetchone()[0]
            except Exception:
                time.sleep(1)
                continue
            if n == last and n > 0:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = n
            time.sleep(1)

    def q_last(self):
        return self.cx.execute(
            f"SELECT ts, uu FROM p WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1").fetchall()

    def q_range(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 60) AS m, max(uu) FROM p WHERE host='{HOST}' "
            f"AND ts >= {T0} AND ts < {T0+3600} GROUP BY m ORDER BY m").fetchall()

    def q_global(self):
        return self.cx.execute(
            f"SELECT (ts - ts % 3600) AS h, avg(uu) FROM p WHERE ts >= {T0} "
            f"AND ts < {T0+43200} GROUP BY h ORDER BY h").fetchall()

    def close(self):
        self.cx.close()


BACKENDS = {c.name: c for c in (ArcadeTS, DuckTS, QuestTS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pts = parse_lp()
    out = {"n_points": len(pts), "backend": args.backend}
    b = BACKENDS[args.backend]()
    b.connect()
    t0 = time.perf_counter()
    b.ingest(pts)
    dt = time.perf_counter() - t0
    out["ingest_s"] = round(dt, 2)
    out["ingest_pts_per_s"] = round(len(pts) / dt, 1)
    for qn in ("q_last", "q_range", "q_global"):
        times = []
        ref = None
        for _ in range(QITER):
            t = time.perf_counter()
            ref = getattr(b, qn)()
            times.append((time.perf_counter() - t) * 1000)
        out[f"{qn}_ms"] = round(statistics.median(times), 2)
        out[f"{qn}_rows"] = len(ref) if ref is not None else 0
    b.close()
    with open(args.out, "w") as f:
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
