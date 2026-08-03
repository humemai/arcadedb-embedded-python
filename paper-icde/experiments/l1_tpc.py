#!/usr/bin/env python3
"""L1-TPC: standard-benchmark tabular lane (TPC-H schema, SF1).

OLAP: official TPC-H Q1 (pricing summary) and Q6 (revenue forecast) — the
canonical single-table queries, expressible identically in every engine's
dialect. Full multi-join TPC-H is NOT run against ArcadeDB: its SQL has no
ad-hoc relational joins (relationships are precomputed links), which the
paper states plainly as a dialect boundary rather than papering over.

OLTP: a New-Order-STYLE transactional mix over the same schema (disclosed
as TPC-C-inspired, not official TPC-C): per transaction, read a part row,
insert an order document, bump the part's stock counter — one ACID txn.

Data: DuckDB dbgen parquet staged under BENCH_DATA/tpch (sf1_lineitem.parquet,
sf1_part.parquet). Deterministic; identical rows for every backend.
"""
import argparse
import json
import os
import random
import statistics
import time

DATA = os.environ.get("BENCH_TPC_DATA", "/data/tpch")
SF = os.environ.get("BENCH_TPC_SF", "1")
OLTP_OPS = 1_000
OLAP_ITER = 5
SEED = 20260722
BATCH = 10_000

Q1_DUCK = """
SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty,
       sum(l_extendedprice) AS sum_base,
       sum(l_extendedprice * (1 - l_discount)) AS sum_disc,
       avg(l_quantity) AS avg_qty, count(*) AS n
FROM lineitem WHERE l_shipdate <= DATE '1998-09-02'
GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus
"""
Q6_DUCK = """
SELECT sum(l_extendedprice * l_discount) AS revenue FROM lineitem
WHERE l_shipdate >= DATE '1994-01-01' AND l_shipdate < DATE '1995-01-01'
  AND l_discount BETWEEN 0.05 AND 0.07 AND l_quantity < 24
"""
# ArcadeDB SQL: same semantics on the LineItem document type; dates stored
# as ISO strings (lexicographic order == chronological for ISO-8601).
Q1_ARCADE = ("SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, "
             "sum(l_extendedprice) AS sum_base, avg(l_quantity) AS avg_qty, "
             "count(*) AS n FROM LineItem WHERE l_shipdate <= '1998-09-02' "
             "GROUP BY l_returnflag, l_linestatus "
             "ORDER BY l_returnflag, l_linestatus")
Q6_ARCADE = ("SELECT sum(l_extendedprice * l_discount) AS revenue FROM LineItem "
             "WHERE l_shipdate >= '1994-01-01' AND l_shipdate < '1995-01-01' "
             "AND l_discount >= 0.05 AND l_discount <= 0.07 AND l_quantity < 24")

LI_COLS = ["l_orderkey", "l_partkey", "l_quantity", "l_extendedprice",
           "l_discount", "l_returnflag", "l_linestatus", "l_shipdate"]


def load_frames():
    import pyarrow.parquet as pq
    li = pq.read_table(os.path.join(DATA, f"sf{SF}_lineitem.parquet"),
                       columns=LI_COLS).to_pandas()
    li["l_shipdate"] = li["l_shipdate"].astype(str)
    for col in ("l_quantity", "l_extendedprice", "l_discount"):
        li[col] = li[col].astype("float64")  # parquet DECIMAL -> uniform DOUBLE
    part = pq.read_table(os.path.join(DATA, f"sf{SF}_part.parquet"),
                         columns=["p_partkey", "p_retailprice"]).to_pandas()
    part["p_retailprice"] = part["p_retailprice"].astype("float64")
    return li, part


class DuckTPC:
    name = "duckdb"

    def connect(self):
        import duckdb
        self.cx = duckdb.connect("/tmp/tpc_duck.db")
        self.version = duckdb.__version__

    def build(self, li, part):
        self.cx.register("li_src", li)
        self.cx.execute("CREATE TABLE lineitem AS SELECT * FROM li_src")
        self.cx.register("p_src", part)
        self.cx.execute("CREATE TABLE part AS SELECT *, 100 AS stock FROM p_src")
        self.cx.execute("CREATE TABLE orders_new (okey BIGINT, pkey BIGINT, qty INT)")
        self.cx.execute("ALTER TABLE lineitem ALTER l_shipdate TYPE DATE")

    def olap(self, which):
        q = Q1_DUCK if which == "q1" else Q6_DUCK
        return self.cx.execute(q).fetchall()

    def new_order(self, i, pkey):
        self.cx.execute("BEGIN")
        self.cx.execute("SELECT p_retailprice, stock FROM part WHERE p_partkey=?",
                        [pkey]).fetchone()
        self.cx.execute("INSERT INTO orders_new VALUES (?, ?, ?)", [i, pkey, 1])
        self.cx.execute("UPDATE part SET stock = stock - 1 WHERE p_partkey=?",
                        [pkey])
        self.cx.execute("COMMIT")

    def close(self):
        self.cx.close()


class PostgresTPC:
    name = "postgres"

    def connect(self):
        import psycopg
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.cx = psycopg.connect(
            f"host={host} dbname=bench user=postgres password=icdebench",
            autocommit=False)
        self.version = "postgres"

    def build(self, li, part):
        cur = self.cx.cursor()
        cur.execute("CREATE TABLE lineitem (l_orderkey BIGINT, l_partkey BIGINT, "
                    "l_quantity DOUBLE PRECISION, l_extendedprice DOUBLE PRECISION, "
                    "l_discount DOUBLE PRECISION, l_returnflag TEXT, "
                    "l_linestatus TEXT, l_shipdate DATE)")
        with cur.copy("COPY lineitem FROM STDIN") as cp:
            for t in li.itertuples(index=False):
                cp.write_row(tuple(t))
        cur.execute("CREATE TABLE part (p_partkey BIGINT PRIMARY KEY, "
                    "p_retailprice DOUBLE PRECISION, stock INT DEFAULT 100)")
        with cur.copy("COPY part (p_partkey, p_retailprice) FROM STDIN") as cp:
            for t in part.itertuples(index=False):
                cp.write_row(tuple(t))
        cur.execute("CREATE TABLE orders_new (okey BIGINT, pkey BIGINT, qty INT)")
        self.cx.commit()

    def olap(self, which):
        q = Q1_DUCK if which == "q1" else Q6_DUCK
        cur = self.cx.cursor()
        cur.execute(q)
        r = cur.fetchall()
        self.cx.commit()
        return r

    def new_order(self, i, pkey):
        cur = self.cx.cursor()
        cur.execute("SELECT p_retailprice, stock FROM part WHERE p_partkey=%s",
                    (pkey,))
        cur.fetchone()
        cur.execute("INSERT INTO orders_new VALUES (%s, %s, %s)", (i, pkey, 1))
        cur.execute("UPDATE part SET stock = stock - 1 WHERE p_partkey=%s",
                    (pkey,))
        self.cx.commit()

    def close(self):
        self.cx.close()


class ArcadeTPC:
    name = "arcadedb_embedded"

    def connect(self):
        import arcadedb_embedded as arcadedb
        self._a = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database("/tmp/tpc_arcade",
                                           jvm_kwargs={"heap_size": heap})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")

    def build(self, li, part):
        db = self.db
        db.command("sql", "CREATE DOCUMENT TYPE LineItem")
        for c in LI_COLS:
            t = ("STRING" if c in ("l_returnflag", "l_linestatus", "l_shipdate")
                 else ("LONG" if c.endswith("key") else "DOUBLE"))
            db.command("sql", f"CREATE PROPERTY LineItem.{c} {t}")
        db.command("sql", "CREATE DOCUMENT TYPE Part")
        db.command("sql", "CREATE PROPERTY Part.p_partkey LONG")
        db.command("sql", "CREATE INDEX ON Part (p_partkey) UNIQUE")
        db.command("sql", "CREATE DOCUMENT TYPE OrderNew")
        # bulk path: batched multi-row INSERT via parameters
        db.begin()
        n = 0
        for t in li.itertuples(index=False):
            db.command("sql",
                       "INSERT INTO LineItem SET l_orderkey=:a, l_partkey=:b, "
                       "l_quantity=:c, l_extendedprice=:d, l_discount=:e, "
                       "l_returnflag=:f, l_linestatus=:g, l_shipdate=:h",
                       {"a": int(t.l_orderkey), "b": int(t.l_partkey),
                        "c": float(t.l_quantity), "d": float(t.l_extendedprice),
                        "e": float(t.l_discount), "f": t.l_returnflag,
                        "g": t.l_linestatus, "h": t.l_shipdate})
            n += 1
            if n % BATCH == 0:
                db.commit()
                db.begin()
        db.commit()
        db.begin()
        n = 0
        for t in part.itertuples(index=False):
            db.command("sql", "INSERT INTO Part SET p_partkey=:k, "
                       "p_retailprice=:p, stock=100",
                       {"k": int(t.p_partkey), "p": float(t.p_retailprice)})
            n += 1
            if n % BATCH == 0:
                db.commit()
                db.begin()
        db.commit()
        # aggregate columns indexed so Q1/Q6 filters avoid full scans
        db.command("sql", "CREATE INDEX ON LineItem (l_shipdate) NOTUNIQUE")

    def olap(self, which):
        q = Q1_ARCADE if which == "q1" else Q6_ARCADE
        return self.db.query("sql", q).to_list()

    def new_order(self, i, pkey):
        db = self.db
        db.begin()
        db.query("sql", "SELECT p_retailprice, stock FROM Part WHERE p_partkey=:k",
                 {"k": pkey}).to_list()
        db.command("sql", "INSERT INTO OrderNew SET okey=:o, pkey=:p, qty=1",
                   {"o": i, "p": pkey})
        db.command("sql", "UPDATE Part SET stock = stock - 1 WHERE p_partkey=:k",
                   {"k": pkey})
        db.commit()

    def close(self):
        self.db.close()


class ArcadeServerTPC(ArcadeTPC):
    name = "arcadedb_server"

    def connect(self):
        import requests
        self.rq = requests.Session()
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.base = f"http://{host}:2480/api/v1"
        self.rq.auth = ("root", "icdebench")
        self.version = "server"

    def _cmd(self, command, timeout=1800, language="sql"):
        r = self.rq.post(f"{self.base}/command/bench",
                         json={"language": language, "command": command},
                         timeout=timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def build(self, li, part):
        for ddl in ("CREATE DOCUMENT TYPE LineItem",
                    "CREATE PROPERTY LineItem.l_shipdate STRING",
                    "CREATE PROPERTY LineItem.l_returnflag STRING",
                    "CREATE PROPERTY LineItem.l_linestatus STRING",
                    "CREATE PROPERTY LineItem.l_orderkey LONG",
                    "CREATE PROPERTY LineItem.l_partkey LONG",
                    "CREATE PROPERTY LineItem.l_quantity DOUBLE",
                    "CREATE PROPERTY LineItem.l_extendedprice DOUBLE",
                    "CREATE PROPERTY LineItem.l_discount DOUBLE",
                    "CREATE DOCUMENT TYPE Part",
                    "CREATE PROPERTY Part.p_partkey LONG",
                    "CREATE INDEX ON Part (p_partkey) UNIQUE",
                    "CREATE DOCUMENT TYPE OrderNew"):
            self._cmd(ddl)
        buf = []
        for t in li.itertuples(index=False):
            buf.append("INSERT INTO LineItem SET l_orderkey=%d, l_partkey=%d, "
                       "l_quantity=%f, l_extendedprice=%f, l_discount=%f, "
                       "l_returnflag='%s', l_linestatus='%s', l_shipdate='%s'"
                       % (t.l_orderkey, t.l_partkey, t.l_quantity,
                          t.l_extendedprice, t.l_discount, t.l_returnflag,
                          t.l_linestatus, t.l_shipdate))
            if len(buf) >= 2_000:
                self._cmd(";".join(buf), language="sqlscript")
                buf = []
        if buf:
            self._cmd(";".join(buf), language="sqlscript")
        buf = []
        for t in part.itertuples(index=False):
            buf.append("INSERT INTO Part SET p_partkey=%d, p_retailprice=%f, "
                       "stock=100" % (t.p_partkey, t.p_retailprice))
            if len(buf) >= 2_000:
                self._cmd(";".join(buf), language="sqlscript")
                buf = []
        if buf:
            self._cmd(";".join(buf), language="sqlscript")
        self._cmd("CREATE INDEX ON LineItem (l_shipdate) NOTUNIQUE")

    def olap(self, which):
        return self._cmd(Q1_ARCADE if which == "q1" else Q6_ARCADE)

    def new_order(self, i, pkey):
        self._cmd(f"SELECT p_retailprice, stock FROM Part WHERE p_partkey={pkey};"
                  f"INSERT INTO OrderNew SET okey={i}, pkey={pkey}, qty=1;"
                  f"UPDATE Part SET stock = stock - 1 WHERE p_partkey={pkey}",
                  language="sqlscript")

    def close(self):
        pass


BACKENDS = {c.name: c for c in (DuckTPC, PostgresTPC, ArcadeTPC, ArcadeServerTPC)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=list(BACKENDS))
    ap.add_argument("--workload", required=True, choices=["oltp", "olap"])
    ap.add_argument("--scale", default="tpch1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    li, part = load_frames()
    out = {"n_lineitem": len(li), "n_part": len(part), "tpch_sf": SF}

    b = BACKENDS[args.backend]()
    b.connect()
    out["engine_version"] = b.version
    t0 = time.perf_counter()
    b.build(li, part)
    out["build_s"] = round(time.perf_counter() - t0, 2)

    if args.workload == "olap":
        for which in ("q1", "q6"):
            times = []
            ref = None
            for _ in range(OLAP_ITER):
                t = time.perf_counter()
                r = b.olap(which)
                times.append((time.perf_counter() - t) * 1000)
                ref = r
            out[f"{which}_ms"] = round(statistics.median(times), 2)
            out[f"{which}_rows"] = len(ref) if ref is not None else 0
    else:
        rng = random.Random(SEED)
        keys = part["p_partkey"].tolist()
        lat = []
        for i in range(OLTP_OPS):
            k = keys[rng.randrange(len(keys))]
            t = time.perf_counter()
            b.new_order(i, int(k))
            if i >= 20:
                lat.append((time.perf_counter() - t) * 1000)
        lat.sort()
        out["oltp_ops_per_s"] = round(len(lat) / (sum(lat) / 1000), 1)
        out["neworder_p50_ms"] = round(statistics.median(lat), 3)
        out["neworder_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)

    b.close()
    with open(args.out, "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)  # JVM non-daemon threads must not keep a finished container alive


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)  # guarantee container death on failure too
