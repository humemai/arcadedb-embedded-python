#!/usr/bin/env python3
"""L1 tabular lane: OLTP + OLAP suites over a synthetic orders/customers schema.

Backends: arcadedb_embedded, arcadedb_server (HTTP), duckdb (embedded),
postgres (server). Same seeded dataset per scale; suites per PROTOCOL.md
(separate OLTP and OLAP, idiomatic config per engine, indexed by default).

Runs INSIDE the bench container; runner.py orchestrates and does resource caps
and cgroup accounting. Emits one JSON file with the metric block.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

SCALE_ROWS = {"tiny": 50_000, "small": 2_000_000, "medium": 20_000_000,
              "large": 100_000_000}
N_CUSTOMERS_FRAC = 0.05
REGIONS = ["na", "eu", "apac", "latam", "mea"]
STATUSES = ["placed", "paid", "shipped", "delivered", "returned"]
OLTP_OPS = 5_000
OLTP_MIX = (0.6, 0.2, 0.2)  # point read / insert / update
OLAP_RUNS = 7
WARMUP_OLTP = 200
WARMUP_OLAP = 1


def gen_rows(n, seed=1234):
    """Deterministic row stream: (id, customer_id, region, status, amount,
    quantity, ts_epoch, note)."""
    rng = random.Random(seed)
    n_cust = max(1, int(n * N_CUSTOMERS_FRAC))
    t0 = 1_600_000_000
    for i in range(n):
        yield (i, rng.randrange(n_cust), rng.choice(REGIONS), rng.choice(STATUSES),
               round(rng.uniform(1, 999), 2), rng.randrange(1, 9),
               t0 + rng.randrange(0, 150_000_000), f"note-{i % 997}")


def pct(vals):
    if not vals:
        return {}
    v = sorted(vals)
    k = lambda q: v[min(len(v) - 1, int(q * len(v)))]
    return {"mean_ms": round(statistics.mean(v) * 1e3, 4),
            "p50_ms": round(k(0.50) * 1e3, 4), "p95_ms": round(k(0.95) * 1e3, 4),
            "p99_ms": round(k(0.99) * 1e3, 4), "n": len(v)}


OLAP_SQL = [
    ("agg_by_region",
     "SELECT region, count(*) AS c, sum(amount) AS s FROM orders GROUP BY region"),
    ("top_customers",
     "SELECT customer_id, sum(amount) AS s FROM orders WHERE status = 'delivered' "
     "GROUP BY customer_id ORDER BY s DESC LIMIT 10"),
    ("filtered_avg",
     "SELECT avg(amount) AS a, avg(quantity) AS q FROM orders "
     "WHERE region = 'eu' AND quantity >= 4"),
    ("status_histogram",
     "SELECT status, count(*) AS c FROM orders GROUP BY status ORDER BY c DESC"),
    ("range_agg",
     "SELECT count(*) AS c, sum(amount) AS s FROM orders "
     "WHERE ts_epoch BETWEEN 1650000000 AND 1700000000"),
]


COLS_SQL = "(id, customer_id, region, status, amount, quantity, ts_epoch, note)"


class Base:
    name = "base"
    placeholder = "?"
    # ArcadeDB SQL requires the explicit column list in INSERT; empty for
    # engines that accept the bare positional form.
    insert_cols = ""

    def connect(self):
        raise NotImplementedError

    def exec(self, sql, params=None):
        raise NotImplementedError

    def query_all(self, sql, params=None):
        raise NotImplementedError

    def begin_batch(self):
        pass

    def commit_batch(self):
        pass

    def schema(self):
        for s in [
            "CREATE TABLE orders (id BIGINT, customer_id BIGINT, region VARCHAR(8), "
            "status VARCHAR(12), amount DOUBLE PRECISION, quantity INT, "
            "ts_epoch BIGINT, note VARCHAR(32))",
            "CREATE INDEX idx_orders_id ON orders (id)",
            "CREATE INDEX idx_orders_customer ON orders (customer_id)",
        ]:
            self.exec(s)

    def ingest(self, n, batch=5_000):
        ph = ",".join([self.placeholder] * 8)
        sql = f"INSERT INTO orders {self.insert_cols} VALUES ({ph})"
        buf = []
        for row in gen_rows(n):
            buf.append(row)
            if len(buf) >= batch:
                self.begin_batch()
                for r in buf:
                    self.exec(sql, r)
                self.commit_batch()
                buf = []
        if buf:
            self.begin_batch()
            for r in buf:
                self.exec(sql, r)
            self.commit_batch()

    def oltp(self, n_rows):
        rng = random.Random(99)
        lat = {"read": [], "insert": [], "update": []}
        next_id = n_rows
        ph = self.placeholder
        ins_sql = f"INSERT INTO orders {self.insert_cols} VALUES ({','.join([ph]*8)})"
        for i in range(OLTP_OPS + WARMUP_OLTP):
            r = rng.random()
            t0 = time.perf_counter()
            if r < OLTP_MIX[0]:
                self.query_all(f"SELECT * FROM orders WHERE id = {ph}",
                               (rng.randrange(n_rows),))
                kind = "read"
            elif r < OLTP_MIX[0] + OLTP_MIX[1]:
                row = next(gen_rows(1, seed=next_id))
                self.begin_batch()
                self.exec(ins_sql, (next_id,) + row[1:])
                self.commit_batch()
                next_id += 1
                kind = "insert"
            else:
                self.begin_batch()
                self.exec(f"UPDATE orders SET status = 'paid' WHERE id = {ph}",
                          (rng.randrange(n_rows),))
                self.commit_batch()
                kind = "update"
            if i >= WARMUP_OLTP:
                lat[kind].append(time.perf_counter() - t0)
        out = {f"{k}_{m}": v for k, lats in lat.items() for m, v in pct(lats).items()}
        total = sum(len(v) for v in lat.values())
        span = sum(sum(v) for v in lat.values())
        out["oltp_ops_per_s"] = round(total / span, 1) if span else None
        return out

    def olap(self):
        out = {}
        for name, sql in OLAP_SQL:
            runs = []
            for i in range(OLAP_RUNS + WARMUP_OLAP):
                t0 = time.perf_counter()
                self.query_all(sql)
                if i >= WARMUP_OLAP:
                    runs.append(time.perf_counter() - t0)
            out[f"olap_{name}_ms"] = round(statistics.mean(runs) * 1e3, 3)
        out["olap_total_ms"] = round(sum(v for k, v in out.items()
                                         if k.startswith("olap_") and k.endswith("_ms")
                                         and k != "olap_total_ms"), 3)
        return out


class DuckDB(Base):
    name = "duckdb"

    def connect(self):
        import duckdb
        self.con = duckdb.connect("/tmp/l1.duckdb")
        self.version = duckdb.__version__

    def exec(self, sql, params=None):
        self.con.execute(sql, params or [])

    def query_all(self, sql, params=None):
        return self.con.execute(sql, params or []).fetchall()

    def ingest(self, n, batch=5_000):  # idiomatic bulk path
        import pandas as pd
        cols = ["id", "customer_id", "region", "status", "amount", "quantity",
                "ts_epoch", "note"]
        self.exec("DROP INDEX IF EXISTS idx_orders_id")
        self.exec("DROP INDEX IF EXISTS idx_orders_customer")
        chunk = []
        for row in gen_rows(n):
            chunk.append(row)
            if len(chunk) >= 500_000:
                df = pd.DataFrame(chunk, columns=cols)  # noqa: F841
                self.con.execute("INSERT INTO orders SELECT * FROM df")
                chunk = []
        if chunk:
            df = pd.DataFrame(chunk, columns=cols)  # noqa: F841
            self.con.execute("INSERT INTO orders SELECT * FROM df")
        self.exec("CREATE INDEX idx_orders_id ON orders (id)")
        self.exec("CREATE INDEX idx_orders_customer ON orders (customer_id)")


class Postgres(Base):
    name = "postgres"
    placeholder = "%s"

    def connect(self):
        import time as _time
        import psycopg
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "5432")
        dsn = (f"host={host} port={port} dbname=bench "
               "user=postgres password=icdebench")
        # retry across the initdb restart window (belt to the runner's
        # ready_regex suspenders); untimed — connect_s covers it
        deadline = _time.time() + 60
        while True:
            try:
                self.con = psycopg.connect(dsn, autocommit=True)
                break
            except psycopg.OperationalError:
                if _time.time() > deadline:
                    raise
                _time.sleep(1)
        self.version = self.con.execute("SHOW server_version").fetchone()[0]

    def exec(self, sql, params=None):
        self.con.execute(sql, params or None)

    def query_all(self, sql, params=None):
        return self.con.execute(sql, params or None).fetchall()

    def ingest(self, n, batch=5_000):  # idiomatic COPY
        with self.con.cursor() as cur:
            with cur.copy("COPY orders FROM STDIN") as cp:
                for row in gen_rows(n):
                    cp.write_row(row)


class ArcadeEmbedded(Base):
    name = "arcadedb_embedded"
    insert_cols = COLS_SQL

    def connect(self):
        import arcadedb_embedded as arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        # -Xms pinned to -Xmx for parity with the server deployment
        self.db = arcadedb.create_database(
            "/tmp/l1_arcade",
            jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
        self.version = arcadedb.__version__
        self._tx = False

    def schema(self):
        self.db.command("sql", "CREATE DOCUMENT TYPE orders")
        for prop, typ in [("id", "LONG"), ("customer_id", "LONG"),
                          ("region", "STRING"), ("status", "STRING"),
                          ("amount", "DOUBLE"), ("quantity", "INTEGER"),
                          ("ts_epoch", "LONG"), ("note", "STRING")]:
            self.db.command("sql", f"CREATE PROPERTY orders.{prop} {typ}")
        self.db.command("sql", "CREATE INDEX ON orders (id) UNIQUE")
        self.db.command("sql", "CREATE INDEX ON orders (customer_id) NOTUNIQUE")

    def begin_batch(self):
        self.db.begin()
        self._tx = True

    def commit_batch(self):
        self.db.commit()
        self._tx = False

    def exec(self, sql, params=None):
        self.db.command("sql", sql, *(params or ()))

    def query_all(self, sql, params=None):
        return self.db.query("sql", sql, *(params or ())).to_json_list()

    def ingest(self, n, batch=500):
        # sqlscript batching: one SQL parse + one boundary crossing per batch
        # (the per-row command() path is the documented anti-pattern)
        buf = []
        for row in gen_rows(n):
            vals = (f"({row[0]},{row[1]},'{row[2]}','{row[3]}',{row[4]},{row[5]},"
                    f"{row[6]},'{row[7]}')")
            buf.append(f"INSERT INTO orders (id, customer_id, region, status, "
                       f"amount, quantity, ts_epoch, note) VALUES {vals}")
            if len(buf) >= batch:
                with self.db.transaction():
                    self.db.command("sqlscript", ";".join(buf))
                buf = []
        if buf:
            with self.db.transaction():
                self.db.command("sqlscript", ";".join(buf))


class ArcadeServer(Base):
    """ArcadeDB over HTTP (client-server topology)."""
    name = "arcadedb_server"
    insert_cols = COLS_SQL

    def connect(self):
        import requests
        self.rq = requests.Session()
        self.rq.auth = ("root", "icdebench")
        host = os.environ["BENCH_SERVER_HOST"]
        port = os.environ.get("BENCH_SERVER_PORT", "2480")
        self.base = f"http://{host}:{port}/api/v1"
        self.version = "server:latest"

    def _post(self, kind, sql, params=None):
        payload = {"language": "sql", "command": sql}
        if params:
            payload["params"] = {f"p{i}": p for i, p in enumerate(params)}
        r = self.rq.post(f"{self.base}/{kind}/bench", json=payload, timeout=300)
        r.raise_for_status()
        return r.json().get("result", [])

    def exec(self, sql, params=None):
        if params:  # positional -> named for the HTTP API
            for i in range(len(params)):
                sql = sql.replace("?", f":p{i}", 1)
        self._post("command", sql, params)

    def query_all(self, sql, params=None):
        if params:
            for i in range(len(params)):
                sql = sql.replace("?", f":p{i}", 1)
        return self._post("query", sql, params)

    def schema(self):
        self.exec("CREATE DOCUMENT TYPE orders")
        for prop, typ in [("id", "LONG"), ("customer_id", "LONG"),
                          ("region", "STRING"), ("status", "STRING"),
                          ("amount", "DOUBLE"), ("quantity", "INTEGER"),
                          ("ts_epoch", "LONG"), ("note", "STRING")]:
            self.exec(f"CREATE PROPERTY orders.{prop} {typ}")
        self.exec("CREATE INDEX ON orders (id) UNIQUE")
        self.exec("CREATE INDEX ON orders (customer_id) NOTUNIQUE")

    def ingest(self, n, batch=500):
        # sqlscript batches: many INSERTs per HTTP round-trip
        buf = []
        for row in gen_rows(n):
            vals = (f"({row[0]},{row[1]},'{row[2]}','{row[3]}',{row[4]},{row[5]},"
                    f"{row[6]},'{row[7]}')")
            buf.append(f"INSERT INTO orders (id, customer_id, region, status, "
                       f"amount, quantity, ts_epoch, note) VALUES {vals}")
            if len(buf) >= batch:
                self._script(";".join(buf))
                buf = []
        if buf:
            self._script(";".join(buf))

    def _script(self, script):
        r = self.rq.post(f"{self.base}/command/bench",
                         json={"language": "sqlscript", "command": script},
                         timeout=600)
        r.raise_for_status()


BACKENDS = {c.name: c for c in [DuckDB, Postgres, ArcadeEmbedded, ArcadeServer]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", required=True, choices=["oltp", "olap"])
    ap.add_argument("--scale", default="tiny", choices=list(SCALE_ROWS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    n = SCALE_ROWS[args.scale]
    b = BACKENDS[args.backend]()
    out = {"lane": "l1", "n_rows": n}

    t0 = time.perf_counter()
    b.connect()
    out["connect_s"] = round(time.perf_counter() - t0, 3)
    out["engine_version"] = getattr(b, "version", "?")

    t0 = time.perf_counter()
    b.schema()
    out["schema_s"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    b.ingest(n)
    ing = time.perf_counter() - t0
    out["ingest_s"] = round(ing, 2)
    out["ingest_rows_per_s"] = round(n / ing, 1)

    if args.workload == "oltp":
        out.update(b.oltp(n))
    else:
        out.update(b.olap())

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    # Fail fast. JPype's JVM keeps non-daemon threads (AsyncFlush,
    # TransactionManager) alive after a Python exception, so a crashed cell
    # would otherwise sit until the runner's multi-hour watchdog. os._exit
    # skips interpreter cleanup and takes the JVM down with it.
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
