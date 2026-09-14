#!/usr/bin/env python3
"""L1-TPC: standard-benchmark tabular lane (TPC-H schema, SF1).

OLAP: official TPC-H Q1 (pricing summary) and Q6 (revenue forecast) — the
canonical single-table queries, expressible identically in every engine's
dialect. Full multi-join TPC-H is NOT run against ArcadeDB: its SQL has no
ad-hoc relational joins (relationships are precomputed links), which the
paper states plainly as a dialect boundary rather than papering over.

OLTP: a New-Order-STYLE transactional mix over the same schema (disclosed
as TPC-C-inspired, not official TPC-C): per transaction, read a part row,
insert an order document, bump the part's stock counter, one ACID txn.
Since the 2026-10 instrument (DECISIONS #82) a PAYMENT-style transaction
follows: read an order placed by new-order, mark it paid, insert a payment
row, one ACID txn; the two are 88% of TPC-C's mix. OLTP ops/s covers both.

OLAP since 2026-10: Q1 and Q6 plus three line-item queries every engine can
answer without a join (top ten parts by revenue, count by ship mode, revenue
by month), 100 runs each per repetition.

Durability (DECISIONS #81): every engine commits without waiting for the
disk where it has the knob; each adapter declares what it ran as
`durability`, and the class that cannot be relaxed says so.

Data: DuckDB dbgen parquet staged under BENCH_DATA/tpch (sf1_lineitem.parquet,
sf1_part.parquet). Deterministic; identical rows for every backend.
"""
import argparse
import json
import os
import random
import statistics
import time
import surreal_common
import arango_common
import bench_common
import bench_common as _bench_common_mod  # a name no function-local import can shadow


def pg_durability(cx):
    """What the PostgreSQL server actually runs, read from it (#81)."""
    try:
        with cx.cursor() as c:
            c.execute("SHOW synchronous_commit")
            v = c.fetchone()[0]
        try:
            cx.rollback()
        except Exception:  # noqa: BLE001
            pass
        return f"synchronous_commit={v}" + ("" if v == "off" else " (NOT the #81 setting)")
    except Exception as e:  # noqa: BLE001
        return f"synchronous_commit=unknown ({e.__class__.__name__})"

DATA = os.environ.get("BENCH_TPC_DATA", "/data/tpch")
SF = os.environ.get("BENCH_TPC_SF", "1")
OLTP_OPS = 1_000
OLAP_ITER = 100   # was 5; a p99 needs the samples (2026-09-10, BUGS F29)
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
# The 2026-10 line-item set (DECISIONS #82): the same three questions in
# every engine's language, no join anywhere.
TOP_PARTS_SQL = ("SELECT l_partkey, sum(l_extendedprice * (1 - l_discount)) AS rev "
                 "FROM lineitem GROUP BY l_partkey ORDER BY rev DESC LIMIT 10")
SHIP_MODE_SQL = "SELECT l_shipmode, count(*) AS n FROM lineitem GROUP BY l_shipmode ORDER BY l_shipmode"
BY_MONTH_DUCK = ("SELECT date_trunc('month', l_shipdate) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev "
                 "FROM lineitem GROUP BY m ORDER BY m")
BY_MONTH_TEXT = ("SELECT substr(l_shipdate, 1, 7) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev "
                 "FROM lineitem GROUP BY m ORDER BY m")
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
ARCADE_OLAP = {
    "q1": Q1_ARCADE, "q6": Q6_ARCADE,
    "top_parts": ("SELECT l_partkey, sum(l_extendedprice * (1 - l_discount)) AS rev FROM LineItem "
                  "GROUP BY l_partkey ORDER BY rev DESC LIMIT 10"),
    "ship_mode": "SELECT l_shipmode, count(*) AS n FROM LineItem GROUP BY l_shipmode ORDER BY l_shipmode",
    "by_month": ("SELECT l_shipdate.substring(0, 7) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev "
                 "FROM LineItem GROUP BY m ORDER BY m"),
}
DUCK_OLAP = {"q1": Q1_DUCK, "q6": Q6_DUCK, "top_parts": TOP_PARTS_SQL, "ship_mode": SHIP_MODE_SQL, "by_month": BY_MONTH_DUCK}

LI_COLS = ["l_orderkey", "l_partkey", "l_quantity", "l_extendedprice",
           "l_discount", "l_returnflag", "l_linestatus", "l_shipdate",
           "l_shipmode"]   # l_shipmode joined for the 2026-10 ship-mode query
OLAP_QUERIES = ("q1", "q6", "top_parts", "ship_mode", "by_month")


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
    # DuckDB flushes its write-ahead log to disk at every commit and has no
    # setting that relaxes it (its durability page: a commit returns after the
    # WAL is written and flushed). Named as the exception it is (#81).
    durability = "fsync at commit, not configurable (DuckDB WAL)"

    def connect(self):
        import duckdb
        self.cx = duckdb.connect("/tmp/tpc_duck.db")
        self.version = duckdb.__version__

    def build(self, li, part):
        self.cx.register("li_src", li)
        self.cx.execute("CREATE TABLE lineitem AS SELECT * FROM li_src")
        self.cx.register("p_src", part)
        self.cx.execute("CREATE TABLE part AS SELECT *, 100 AS stock FROM p_src")
        self.cx.execute("CREATE TABLE orders_new (okey BIGINT, pkey BIGINT, qty INT, paid INT DEFAULT 0)")
        self.cx.execute("CREATE INDEX o_okey ON orders_new (okey)")
        self.cx.execute("CREATE TABLE payments (okey BIGINT, pkey BIGINT, amount DOUBLE)")
        self.cx.execute("ALTER TABLE lineitem ALTER l_shipdate TYPE DATE")

    def olap(self, which):
        return self.cx.execute(DUCK_OLAP[which]).fetchall()

    def new_order(self, i, pkey):
        self.cx.execute("BEGIN")
        self.cx.execute("SELECT p_retailprice, stock FROM part WHERE p_partkey=?",
                        [pkey]).fetchone()
        self.cx.execute("INSERT INTO orders_new VALUES (?, ?, ?, 0)", [i, pkey, 1])
        self.cx.execute("UPDATE part SET stock = stock - 1 WHERE p_partkey=?",
                        [pkey])
        self.cx.execute("COMMIT")

    def payment(self, okey):
        self.cx.execute("BEGIN")
        r = self.cx.execute("SELECT okey, pkey, qty FROM orders_new WHERE okey=?", [okey]).fetchone()
        self.cx.execute("UPDATE orders_new SET paid = 1 WHERE okey=?", [okey])
        self.cx.execute("INSERT INTO payments VALUES (?, ?, ?)", [okey, r[1] if r else 0, 1.0])
        self.cx.execute("COMMIT")

    def close(self):
        self.cx.close()


Q1_SQLITE = Q1_DUCK.replace("DATE '1998-09-02'", "'1998-09-02'")
Q6_SQLITE = Q6_DUCK.replace("DATE '1994-01-01'", "'1994-01-01'").replace("DATE '1995-01-01'", "'1995-01-01'")
SQLITE_OLAP = {"q1": Q1_SQLITE, "q6": Q6_SQLITE, "top_parts": TOP_PARTS_SQL, "ship_mode": SHIP_MODE_SQL, "by_month": BY_MONTH_TEXT}


class SQLiteTPC:
    """SQLite in WAL mode with synchronous=NORMAL (DECISIONS #70, disclosed);
    dates as ISO text like the ArcadeDB arm, so the comparisons are
    lexicographic and equal to chronological (2026-09-11)."""
    name = "sqlite"
    durability = "WAL, synchronous=NORMAL: synced at checkpoint, not at commit"

    def connect(self):
        import sqlite3
        self.cx = sqlite3.connect("/tmp/tpc_sqlite.db")
        self.cx.execute("PRAGMA foreign_keys=ON")   # no schema here declares one; stated for completeness
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA synchronous=NORMAL")
        self.version = f"sqlite {sqlite3.sqlite_version}"

    def build(self, li, part):
        self.cx.execute("CREATE TABLE lineitem (l_orderkey INTEGER, l_partkey INTEGER, "
                        "l_quantity REAL, l_extendedprice REAL, l_discount REAL, "
                        "l_returnflag TEXT, l_linestatus TEXT, l_shipdate TEXT, l_shipmode TEXT)")
        self.cx.execute("CREATE TABLE part (p_partkey INTEGER PRIMARY KEY, p_retailprice REAL, stock INTEGER)")
        self.cx.execute("CREATE TABLE orders_new (okey INTEGER PRIMARY KEY, pkey INTEGER, qty INTEGER, paid INTEGER DEFAULT 0)")
        self.cx.execute("CREATE TABLE payments (okey INTEGER, pkey INTEGER, amount REAL)")
        rows = li[LI_COLS].itertuples(index=False, name=None)
        buf = []
        for r in rows:
            buf.append(r)
            if len(buf) >= 50_000:
                self.cx.executemany("INSERT INTO lineitem VALUES (?,?,?,?,?,?,?,?,?)", buf)
                self.cx.commit(); buf = []
        if buf:
            self.cx.executemany("INSERT INTO lineitem VALUES (?,?,?,?,?,?,?,?,?)", buf)
            self.cx.commit()
        self.cx.executemany("INSERT INTO part VALUES (?,?,100)",
                            list(part[["p_partkey", "p_retailprice"]].itertuples(index=False, name=None)))
        self.cx.commit()
        self.cx.execute("CREATE INDEX li_shipdate ON lineitem (l_shipdate)")
        self.cx.commit()

    def olap(self, which):
        return self.cx.execute(SQLITE_OLAP[which]).fetchall()

    def new_order(self, i, pkey):
        self.cx.execute("SELECT p_retailprice, stock FROM part WHERE p_partkey=?", (pkey,)).fetchone()
        self.cx.execute("INSERT INTO orders_new VALUES (?, ?, ?, 0)", (i, pkey, 1))
        self.cx.execute("UPDATE part SET stock = stock - 1 WHERE p_partkey=?", (pkey,))
        self.cx.commit()

    def payment(self, okey):
        r = self.cx.execute("SELECT okey, pkey, qty FROM orders_new WHERE okey=?", (okey,)).fetchone()
        self.cx.execute("UPDATE orders_new SET paid = 1 WHERE okey=?", (okey,))
        self.cx.execute("INSERT INTO payments VALUES (?, ?, ?)", (okey, r[1] if r else 0, 1.0))
        self.cx.commit()

    def close(self):
        self.cx.close()


class MongoTPC:
    """MongoDB 8.2: lineitem and part as collections, ISO-text dates like the
    ArcadeDB and SQLite arms, Q1/Q6 as aggregation pipelines, new-order as
    one multi-document transaction (which is why the server runs as a
    single-node replica set) (2026-09-11)."""
    name = "mongodb"
    # w=1, j=false on every timed write (#81): the write returns once the
    # primary has applied it in memory; the journal is flushed by the
    # storage engine's own commit interval (100 ms). A replica set's default
    # is w:majority with journaling, which waits for the disk.
    durability = "write concern w=1, j=false (journal flushed every 100 ms)"

    def connect(self):
        import pymongo
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.cl = pymongo.MongoClient(f"mongodb://{host}:27017/?directConnection=true",
                                      serverSelectionTimeoutMS=60000)
        try:
            self.cl.admin.command("replSetInitiate", {"_id": "rs0", "members": [{"_id": 0, "host": f"{host}:27017"}]})
        except pymongo.errors.OperationFailure:
            pass
        for _ in range(120):
            try:
                if self.cl.admin.command("hello").get("isWritablePrimary"):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        # Reconnect once the node is primary (2026-09-12, laptop runner smoke):
        # the first client's topology snapshot was taken while the node was
        # still starting and carried no logicalSessionTimeoutMinutes, so the
        # first transaction raised "Sessions are not supported by this
        # MongoDB deployment" before the next heartbeat refreshed it. A fresh
        # client discovers the primary as such; wait until it reports session
        # support before handing the connection to the workload.
        self.cl.close()
        self.cl = pymongo.MongoClient(f"mongodb://{host}:27017/?directConnection=true",
                                      serverSelectionTimeoutMS=60000)
        for _ in range(120):
            try:
                self.cl.admin.command("ping")
                if self.cl.topology_description.logical_session_timeout_minutes is not None:
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        self.version = f"mongodb {self.cl.server_info()['version']}"
        self.db = self.cl["bench"]
        from pymongo import WriteConcern
        self._wc = WriteConcern(w=1, j=False)

    def build(self, li, part):
        lc, pc, oc = self.db["lineitem"], self.db["part"], self.db["orders_new"]
        lc.drop(); pc.drop(); oc.drop()
        buf = []
        for t in li[LI_COLS].itertuples(index=False, name=None):
            buf.append(dict(zip(LI_COLS, t)))
            if len(buf) >= 50_000:
                lc.insert_many(buf, ordered=False); buf = []
        if buf:
            lc.insert_many(buf, ordered=False)
        pc.insert_many([{"p_partkey": int(k), "p_retailprice": float(v), "stock": 100}
                        for k, v in part[["p_partkey", "p_retailprice"]].itertuples(index=False, name=None)],
                       ordered=False)
        pc.create_index("p_partkey", unique=True)
        lc.create_index("l_shipdate")
        oc.create_index("okey", unique=True)

    _REV = {"$sum": {"$multiply": ["$l_extendedprice", {"$subtract": [1, "$l_discount"]}]}}
    TOP_PARTS = [{"$group": {"_id": "$l_partkey", "rev": _REV}}, {"$sort": {"rev": -1}}, {"$limit": 10}]
    SHIP_MODE = [{"$group": {"_id": "$l_shipmode", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
    BY_MONTH = [{"$group": {"_id": {"$substr": ["$l_shipdate", 0, 7]}, "rev": _REV}}, {"$sort": {"_id": 1}}]
    Q1 = [{"$match": {"l_shipdate": {"$lte": "1998-09-02"}}},
          {"$group": {"_id": {"f": "$l_returnflag", "s": "$l_linestatus"},
                      "sum_qty": {"$sum": "$l_quantity"}, "sum_base": {"$sum": "$l_extendedprice"},
                      "sum_disc": {"$sum": {"$multiply": ["$l_extendedprice", {"$subtract": [1, "$l_discount"]}]}},
                      "avg_qty": {"$avg": "$l_quantity"}, "n": {"$sum": 1}}},
          {"$sort": {"_id.f": 1, "_id.s": 1}}]
    Q6 = [{"$match": {"l_shipdate": {"$gte": "1994-01-01", "$lt": "1995-01-01"},
                      "l_discount": {"$gte": 0.05, "$lte": 0.07}, "l_quantity": {"$lt": 24}}},
          {"$group": {"_id": None, "revenue": {"$sum": {"$multiply": ["$l_extendedprice", "$l_discount"]}}}}]

    def olap(self, which):
        q = {"q1": self.Q1, "q6": self.Q6, "top_parts": self.TOP_PARTS,
             "ship_mode": self.SHIP_MODE, "by_month": self.BY_MONTH}[which]
        return list(self.db["lineitem"].aggregate(q, allowDiskUse=True))

    def new_order(self, i, pkey):
        with self.cl.start_session() as sess:
            with sess.start_transaction(write_concern=self._wc):
                self.db["part"].find_one({"p_partkey": pkey}, {"p_retailprice": 1, "stock": 1}, session=sess)
                self.db["orders_new"].insert_one({"okey": i, "pkey": pkey, "qty": 1, "paid": 0}, session=sess)
                self.db["part"].update_one({"p_partkey": pkey}, {"$inc": {"stock": -1}}, session=sess)

    def payment(self, okey):
        with self.cl.start_session() as sess:
            with sess.start_transaction(write_concern=self._wc):
                o = self.db["orders_new"].find_one({"okey": okey}, {"pkey": 1, "qty": 1}, session=sess)
                self.db["orders_new"].update_one({"okey": okey}, {"$set": {"paid": 1}}, session=sess)
                self.db["payments"].insert_one({"okey": okey, "pkey": (o or {}).get("pkey", 0), "amount": 1.0}, session=sess)

    def close(self):
        self.cl.close()


class SurrealTPC:
    """SurrealDB embedded through its Python SDK on SurrealKV (SDK 2.0.0, which carries core 2.3.10):
    lineitem and part as tables, part keyed by record id, dates as ISO text,
    Q1/Q6 in SurrealQL, new-order as one BEGIN/COMMIT transaction
    (2026-09-11). The served twin runs the 3.2.4 server on RocksDB."""
    name = "surrealdb_tpc"   # not "surrealdb": that is the cross-model lane's old row name
    URL = "surrealkv:///tmp/tpc_surrealkv"
    # core 2.3.10: SURREAL_SYNC_DATA defaults to false (crates/core/src/kvs/
    # surrealkv/cnf.rs at v2.3.10), so a commit does not wait for the disk.
    durability = "SurrealKV, SURREAL_SYNC_DATA=false (2.x default): no sync at commit"

    def _open(self):
        import shutil
        from surrealdb import Surreal
        shutil.rmtree("/tmp/tpc_surrealkv", ignore_errors=True)
        self.db = Surreal(self.URL)
        self.db.use("bench", "bench")
        self.version = surreal_common.engine_stamp(self.db)   # core version, not the SDK's (F39)

    def connect(self):
        self._open()
        self.db.query("REMOVE TABLE IF EXISTS lineitem; REMOVE TABLE IF EXISTS part; "
                      "REMOVE TABLE IF EXISTS orders_new; REMOVE TABLE IF EXISTS payments")

    def build(self, li, part):
        # Index BEFORE the load (2026-09-13): on the SDK's SurrealKV store a
        # DEFINE INDEX over the 6.0M loaded rows is one transaction record and
        # failed with "Record is too large to fit in a segment" on mini (qDO);
        # defined first, each 5,000-row batch maintains it in its own record.
        self.db.query("DEFINE INDEX li_shipdate ON lineitem FIELDS l_shipdate")
        buf = []
        for t in li[LI_COLS].itertuples(index=False, name=None):
            buf.append(dict(zip(LI_COLS, t)))
            if len(buf) >= BATCH:
                self.db.insert("lineitem", buf); buf = []
        if buf:
            self.db.insert("lineitem", buf)
        from surrealdb import RecordID   # a string id would become a string key
        pr = [{"id": RecordID("part", int(k)), "p_partkey": int(k), "p_retailprice": float(v), "stock": 100}
              for k, v in part[["p_partkey", "p_retailprice"]].itertuples(index=False, name=None)]
        for s0 in range(0, len(pr), BATCH):
            self.db.insert("part", pr[s0:s0 + BATCH])

    Q1 = ("SELECT l_returnflag, l_linestatus, math::sum(l_quantity) AS sum_qty, math::sum(l_extendedprice) AS sum_base, "
          "math::sum(l_extendedprice * (1 - l_discount)) AS sum_disc, math::mean(l_quantity) AS avg_qty, count() AS n "
          "FROM lineitem WHERE l_shipdate <= '1998-09-02' GROUP BY l_returnflag, l_linestatus ORDER BY l_returnflag, l_linestatus")
    Q6 = ("SELECT math::sum(l_extendedprice * l_discount) AS revenue FROM lineitem WHERE l_shipdate >= '1994-01-01' "
          "AND l_shipdate < '1995-01-01' AND l_discount >= 0.05 AND l_discount <= 0.07 AND l_quantity < 24 GROUP ALL")
    # Subquery form for the ordered group-bys: core 2.3.10 sorts by the group
    # key after GROUP BY (the l2 finding of 2026-09-11); 3.2.4 accepts both.
    OLAP = {
        "top_parts": ("SELECT * FROM (SELECT l_partkey, math::sum(l_extendedprice * (1 - l_discount)) AS rev "
                      "FROM lineitem GROUP BY l_partkey) ORDER BY rev DESC LIMIT 10"),
        "ship_mode": "SELECT l_shipmode, count() AS n FROM lineitem GROUP BY l_shipmode ORDER BY l_shipmode",
        "by_month": ("SELECT * FROM (SELECT string::slice(l_shipdate, 0, 7) AS m, "
                     "math::sum(l_extendedprice * (1 - l_discount)) AS rev FROM lineitem GROUP BY m) ORDER BY m"),
    }

    @staticmethod
    def _rows(res):
        if isinstance(res, list) and res and isinstance(res[0], dict) and "result" in res[0]:
            res = res[-1]["result"]
        return res if isinstance(res, list) else ([res] if res is not None else [])

    def olap(self, which):
        q = {"q1": self.Q1, "q6": self.Q6}.get(which) or self.OLAP[which]
        return self._rows(self.db.query(q))

    def new_order(self, i, pkey):
        self.db.query(f"BEGIN; SELECT p_retailprice, stock FROM ONLY part:{pkey}; "
                      f"CREATE orders_new:{i} SET okey = {i}, pkey = {pkey}, qty = 1, paid = 0; "
                      f"UPDATE part:{pkey} SET stock -= 1; COMMIT;")

    def payment(self, okey):
        self.db.query(f"BEGIN; SELECT pkey, qty FROM ONLY orders_new:{okey}; "
                      f"UPDATE orders_new:{okey} SET paid = 1; "
                      f"CREATE payments SET okey = {okey}, amount = 1.0; COMMIT;")

    def close(self):
        try:
            self.db.close()
        except Exception:  # noqa: BLE001
            pass


class SurrealServedTPC(SurrealTPC):
    name = "surrealdb_tpc_server"
    # 3.2.4 defaults to SyncMode::Every; the runner starts the server with
    # SURREAL_DATASTORE_SYNC_DATA=never (#81), the class ArcadeDB runs in.
    durability = "RocksDB, SURREAL_DATASTORE_SYNC_DATA=never (3.x default is every commit)"

    def _open(self):
        from surrealdb import Surreal
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.db = Surreal(f"ws://{host}:8000/rpc")
        self.db.signin({"username": "root", "password": "root"})
        self.db.use("bench", "bench")
        self.version = "surrealdb-server:" + str(self.db.version()).replace("surrealdb-", "")


class PostgresTPC:
    name = "postgres"

    def connect(self):
        import psycopg
        host = os.environ.get("BENCH_SERVER_HOST", "localhost")
        self.cx = psycopg.connect(
            f"host={host} dbname=bench user=postgres password=dbbenchpass",
            autocommit=False)
        # READ, not asserted: the server was started with synchronous_commit=off
        # (runner.BACKENDS, #81); the row records what the server answers.
        self.durability = pg_durability(self.cx)
        # ASK THE SERVER. "postgres" is a name, not a version, and a row
        # carrying one cannot be re-measured by anyone including us (#156).
        # Never lose a completed run over provenance: record the reason.
        try:
            with self.cx.cursor() as _c:
                _c.execute("SELECT version()")
                self.version = _c.fetchone()[0].split(" (")[0]
            self.cx.rollback()
        except Exception as e:
            self.version = f"postgres:unknown ({e.__class__.__name__})"

    def build(self, li, part):
        cur = self.cx.cursor()
        cur.execute("CREATE TABLE lineitem (l_orderkey BIGINT, l_partkey BIGINT, "
                    "l_quantity DOUBLE PRECISION, l_extendedprice DOUBLE PRECISION, "
                    "l_discount DOUBLE PRECISION, l_returnflag TEXT, "
                    "l_linestatus TEXT, l_shipdate DATE, l_shipmode TEXT)")
        with cur.copy("COPY lineitem FROM STDIN") as cp:
            for t in li.itertuples(index=False):
                cp.write_row(tuple(t))
        cur.execute("CREATE TABLE part (p_partkey BIGINT PRIMARY KEY, "
                    "p_retailprice DOUBLE PRECISION, stock INT DEFAULT 100)")
        with cur.copy("COPY part (p_partkey, p_retailprice) FROM STDIN") as cp:
            for t in part.itertuples(index=False):
                cp.write_row(tuple(t))
        cur.execute("CREATE TABLE orders_new (okey BIGINT PRIMARY KEY, pkey BIGINT, qty INT, paid INT DEFAULT 0)")
        cur.execute("CREATE TABLE payments (okey BIGINT, pkey BIGINT, amount DOUBLE PRECISION)")
        self.cx.commit()

    def olap(self, which):
        q = DUCK_OLAP[which]
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
        cur.execute("INSERT INTO orders_new VALUES (%s, %s, %s, 0)", (i, pkey, 1))
        cur.execute("UPDATE part SET stock = stock - 1 WHERE p_partkey=%s",
                    (pkey,))
        self.cx.commit()

    def payment(self, okey):
        cur = self.cx.cursor()
        cur.execute("SELECT okey, pkey, qty FROM orders_new WHERE okey=%s", (okey,))
        r = cur.fetchone()
        cur.execute("UPDATE orders_new SET paid = 1 WHERE okey=%s", (okey,))
        cur.execute("INSERT INTO payments VALUES (%s, %s, %s)", (okey, r[1] if r else 0, 1.0))
        self.cx.commit()

    def close(self):
        self.cx.close()


class ArcadeTPC:
    name = "arcadedb_embedded"
    # The engine default (GlobalConfiguration TX_WAL_FLUSH = 0): the WAL is
    # written, not flushed, at commit. DECISIONS #81 keeps it; the comparators
    # are set to the same class.
    durability = "txWalFlush=0 (engine default): no flush at commit"

    def connect(self):
        import arcadedb_embedded as arcadedb
        self._a = arcadedb
        heap = os.environ.get("ARCADEDB_HEAP", "4g")
        self.db = arcadedb.create_database("/tmp/tpc_arcade",
                                           # -Xms pinned to -Xmx, matching every server arm and the other lanes.
                                           # heap_size sets -Xmx ONLY (bindings jvm.py), so without this the JVM
                                           # starts at its default initial heap, 1/64 of the cgroup, and grows
                                           # under load. The paper states -Xms=-Xmx as a protocol invariant for
                                           # everyone. It was true of l1, l2, l3s, l3d and every server arm, and
                                           # false here.
                                           jvm_kwargs={"heap_size": heap,
                                                       "jvm_args": f"-Xms{heap}"})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")

    def build(self, li, part):
        db = self.db
        db.command("sql", "CREATE DOCUMENT TYPE LineItem")
        for c in LI_COLS:
            t = ("STRING" if c in ("l_returnflag", "l_linestatus", "l_shipdate", "l_shipmode")
                 else ("LONG" if c.endswith("key") else "DOUBLE"))
            db.command("sql", f"CREATE PROPERTY LineItem.{c} {t}")
        db.command("sql", "CREATE DOCUMENT TYPE Part")
        db.command("sql", "CREATE PROPERTY Part.p_partkey LONG")
        db.command("sql", "CREATE INDEX ON Part (p_partkey) UNIQUE")
        db.command("sql", "CREATE DOCUMENT TYPE OrderNew")
        db.command("sql", "CREATE PROPERTY OrderNew.okey LONG")
        db.command("sql", "CREATE INDEX ON OrderNew (okey) UNIQUE")
        db.command("sql", "CREATE DOCUMENT TYPE Payment")
        # THE ENGINE'S BULK PATH, not one SQL statement per row.
        #
        # This block used to issue a parameterised INSERT per row and call
        # itself "bulk path: batched multi-row INSERT". It was neither: at
        # TPC-H SF10 that is 60M separate db.command() calls, each crossing
        # JPype, each parsed as its own SQL statement. Measured on mini at
        # tpch10, build_s medians: DuckDB 113 s, PostgreSQL 245 s, ArcadeDB
        # 2234 s. A 20x gap against DuckDB that is our binding usage, not the
        # storage engine -- the fifth instance of "the harness, not the
        # engine" in this project, and this one handicapped OURSELVES in a
        # published build_s.
        #
        # insert_many serialises a batch to one JSON payload and loops it
        # Java-side (DocumentBatcher), so the FFI crossing is per BATCH rather
        # than per row. This is the same class of idiomatic bulk path the
        # other engines already get here: DuckDB registers an Arrow table,
        # PostgreSQL uses COPY FROM STDIN. Using per-row SQL for us while they
        # get native bulk was never a defensible comparison.
        #
        # numpy scalars are converted at the boundary on purpose: insert_many
        # json.dumps the batch and falls back to the slow per-row path on a
        # TypeError, so an unconverted np.int64 would silently restore exactly
        # the behaviour this replaces.
        for start in range(0, len(li), BATCH):
            chunk = li.iloc[start:start + BATCH]
            db.insert_many("LineItem", [
                {"l_orderkey": int(t.l_orderkey), "l_partkey": int(t.l_partkey),
                 "l_quantity": float(t.l_quantity),
                 "l_extendedprice": float(t.l_extendedprice),
                 "l_discount": float(t.l_discount),
                 "l_returnflag": str(t.l_returnflag),
                 "l_linestatus": str(t.l_linestatus),
                 "l_shipdate": str(t.l_shipdate),
                 "l_shipmode": str(t.l_shipmode)}
                for t in chunk.itertuples(index=False)], commit_every=BATCH)
        for start in range(0, len(part), BATCH):
            chunk = part.iloc[start:start + BATCH]
            db.insert_many("Part", [
                {"p_partkey": int(t.p_partkey),
                 "p_retailprice": float(t.p_retailprice), "stock": 100}
                for t in chunk.itertuples(index=False)], commit_every=BATCH)
        # aggregate columns indexed so Q1/Q6 filters avoid full scans
        db.command("sql", "CREATE INDEX ON LineItem (l_shipdate) NOTUNIQUE")

    def olap(self, which):
        return self.db.query("sql", ARCADE_OLAP[which]).to_list()

    def new_order(self, i, pkey):
        db = self.db
        db.begin()
        db.query("sql", "SELECT p_retailprice, stock FROM Part WHERE p_partkey=:k",
                 {"k": pkey}).to_list()
        db.command("sql", "INSERT INTO OrderNew SET okey=:o, pkey=:p, qty=1, paid=0",
                   {"o": i, "p": pkey})
        db.command("sql", "UPDATE Part SET stock = stock - 1 WHERE p_partkey=:k",
                   {"k": pkey})
        db.commit()

    def payment(self, okey):
        db = self.db
        db.begin()
        r = db.query("sql", "SELECT pkey, qty FROM OrderNew WHERE okey=:o", {"o": okey}).to_list()
        db.command("sql", "UPDATE OrderNew SET paid = 1 WHERE okey=:o", {"o": okey})
        db.command("sql", "INSERT INTO Payment SET okey=:o, pkey=:p, amount=1.0",
                   {"o": okey, "p": (r[0].get("pkey") if r else 0)})
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
        self.rq.auth = ("root", "dbbenchpass")
        # ASK THE SERVER, as l1_tabular, l2_graph, l3_sparse and l3d_dense all
        # already do. "server" is a name, not a version (#156), and this lane
        # was the last one still asserting it. The same defect in another form
        # made ArcadeDB rows read "server:latest" while a pinned digest ran.
        try:
            info = self.rq.get(f"http://{host}:2480/api/v1/server", timeout=30)
            self.version = "server:" + (info.json().get("version") or "?")
        except Exception as e:
            self.version = f"server:unknown ({e.__class__.__name__})"

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
                    "CREATE PROPERTY LineItem.l_shipmode STRING",
                    "CREATE DOCUMENT TYPE Part",
                    "CREATE PROPERTY Part.p_partkey LONG",
                    "CREATE INDEX ON Part (p_partkey) UNIQUE",
                    "CREATE DOCUMENT TYPE OrderNew",
                    "CREATE PROPERTY OrderNew.okey LONG",
                    "CREATE INDEX ON OrderNew (okey) UNIQUE",
                    "CREATE DOCUMENT TYPE Payment"):
            self._cmd(ddl)
        buf = []
        for t in li.itertuples(index=False):
            buf.append("INSERT INTO LineItem SET l_orderkey=%d, l_partkey=%d, "
                       "l_quantity=%f, l_extendedprice=%f, l_discount=%f, "
                       "l_returnflag='%s', l_linestatus='%s', l_shipdate='%s', l_shipmode='%s'"
                       % (t.l_orderkey, t.l_partkey, t.l_quantity,
                          t.l_extendedprice, t.l_discount, t.l_returnflag,
                          t.l_linestatus, t.l_shipdate, t.l_shipmode))
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
        return self._cmd(ARCADE_OLAP[which])

    def new_order(self, i, pkey):
        self._cmd(f"SELECT p_retailprice, stock FROM Part WHERE p_partkey={pkey};"
                  f"INSERT INTO OrderNew SET okey={i}, pkey={pkey}, qty=1, paid=0;"
                  f"UPDATE Part SET stock = stock - 1 WHERE p_partkey={pkey}",
                  language="sqlscript")

    def payment(self, okey):
        self._cmd(f"SELECT pkey, qty FROM OrderNew WHERE okey={okey};"
                  f"UPDATE OrderNew SET paid = 1 WHERE okey={okey};"
                  f"INSERT INTO Payment SET okey={okey}, amount=1.0",
                  language="sqlscript")

    def close(self):
        pass


# The buffer-pool ablation reuses this adapter unchanged. Only the SERVER
# container differs (shared_buffers and friends sized from its memory cap
# instead of left at the image's start-anywhere defaults), and that is set by
# runner.py's server_cmd, not by anything on this side of the wire. Making it
# a subclass rather than a second entry pointing at the same class keeps
# argparse's --backend choices honest: the runner passes the arm's name down,
# and a name the lane script does not know must fail loudly, which is how this
# ablation's first smoke run failed in 19 seconds instead of eight hours.
class PostgresTunedTPC(PostgresTPC):
    name = "postgres_tuned"


class ArangoTPC:
    """ArangoDB 3.12.11 served through python-arango (2026-09-13): lineitem
    and part as collections through the bulk import API, ISO-text dates like
    the MongoDB arm, Q1/Q6 in AQL, new-order as one stream transaction (read
    the part, insert the order, decrement the stock). Server only: the
    driver is an HTTP client and the engine has no in-process mode."""
    name = "arangodb_tpc"
    durability = arango_common.DURABILITY

    def connect(self):
        self.cl, self.db, self.version = arango_common.connect()

    def build(self, li, part):
        lc = self.db.create_collection("lineitem")
        pc = self.db.create_collection("part")
        self.db.create_collection("orders_new")
        self.db.create_collection("payments")
        buf = []
        for t in li[LI_COLS].itertuples(index=False, name=None):
            buf.append(dict(zip(LI_COLS, t)))
            if len(buf) >= 50_000:
                lc.import_bulk(buf); buf = []
        if buf:
            lc.import_bulk(buf)
        pc.import_bulk([{"_key": str(int(k)), "p_partkey": int(k), "p_retailprice": float(v), "stock": 100}
                        for k, v in part[["p_partkey", "p_retailprice"]].itertuples(index=False, name=None)])
        lc.add_index({"type": "persistent", "fields": ["l_shipdate"]})

    Q1 = ("FOR l IN lineitem FILTER l.l_shipdate <= '1998-09-02' "
          "COLLECT f = l.l_returnflag, s = l.l_linestatus "
          "AGGREGATE sum_qty = SUM(l.l_quantity), sum_base = SUM(l.l_extendedprice), "
          "sum_disc = SUM(l.l_extendedprice * (1 - l.l_discount)), avg_qty = AVG(l.l_quantity), n = COUNT(1) "
          "SORT f, s RETURN {f, s, sum_qty, sum_base, sum_disc, avg_qty, n}")
    Q6 = ("FOR l IN lineitem FILTER l.l_shipdate >= '1994-01-01' AND l.l_shipdate < '1995-01-01' "
          "AND l.l_discount >= 0.05 AND l.l_discount <= 0.07 AND l.l_quantity < 24 "
          "COLLECT AGGREGATE revenue = SUM(l.l_extendedprice * l.l_discount) RETURN {revenue}")

    OLAP = {
        "top_parts": ("FOR l IN lineitem COLLECT k = l.l_partkey "
                      "AGGREGATE rev = SUM(l.l_extendedprice * (1 - l.l_discount)) "
                      "SORT rev DESC LIMIT 10 RETURN {k, rev}"),
        "ship_mode": "FOR l IN lineitem COLLECT m = l.l_shipmode WITH COUNT INTO n SORT m RETURN {m, n}",
        "by_month": ("FOR l IN lineitem COLLECT m = SUBSTRING(l.l_shipdate, 0, 7) "
                     "AGGREGATE rev = SUM(l.l_extendedprice * (1 - l.l_discount)) SORT m RETURN {m, rev}"),
    }

    def olap(self, which):
        q = {"q1": self.Q1, "q6": self.Q6}.get(which) or self.OLAP[which]
        return list(self.db.aql.execute(q, batch_size=10_000))

    def new_order(self, i, pkey):
        txn = self.db.begin_transaction(write=["part", "orders_new"])
        try:
            txn.collection("part").get(str(pkey))
            txn.collection("orders_new").insert({"_key": str(i), "okey": i, "pkey": pkey, "qty": 1, "paid": 0})
            txn.aql.execute("LET p = DOCUMENT('part', @k) UPDATE p WITH {stock: p.stock - 1} IN part",
                            bind_vars={"k": str(pkey)})
            txn.commit_transaction()
        except Exception:
            txn.abort_transaction()
            raise

    def payment(self, okey):
        txn = self.db.begin_transaction(write=["orders_new", "payments"])
        try:
            o = txn.collection("orders_new").get(str(okey)) or {}
            txn.aql.execute("LET o = DOCUMENT('orders_new', @k) UPDATE o WITH {paid: 1} IN orders_new",
                            bind_vars={"k": str(okey)})
            txn.collection("payments").insert({"okey": okey, "pkey": o.get("pkey", 0), "amount": 1.0})
            txn.commit_transaction()
        except Exception:
            txn.abort_transaction()
            raise

    def close(self):
        arango_common.close(self.cl)


BACKENDS = {c.name: c for c in (DuckTPC, SQLiteTPC, MongoTPC, SurrealTPC, SurrealServedTPC, ArangoTPC, PostgresTPC, PostgresTunedTPC,
                                ArcadeTPC, ArcadeServerTPC)}


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

    out["durability"] = getattr(b, "durability", None)
    out["instrument"] = _bench_common_mod.INSTRUMENT
    if args.workload == "olap":
        for which in OLAP_QUERIES:
            times = []
            ref = None
            for _ in range(OLAP_ITER):
                t = time.perf_counter()
                r = b.olap(which)
                times.append((time.perf_counter() - t) * 1000)
                ref = r
            out[f"{which}_ms"] = round(statistics.median(times), 2)
            _s = sorted(times)
            out[f"{which}_p99_ms"] = round(_s[max(0, int(0.99 * (len(_s) - 1)))], 2)
            # COLD AND WARM, both free: this loop discards no warmup, so the
            # published median already BLENDS the first touch with the
            # repeats, and how much it blends depends on OLAP_ITER. Q1 and Q6
            # are full-scan and narrow-filter reads over the same fact table,
            # which is exactly where cache state moves a number: the graph lane
            # measured Neo4j gaining 9.9x on a second pass while LadybugDB,
            # resident from load, gained nothing.
            #
            # The published field is unchanged so existing numbers stay
            # comparable. These two say what it is made of.
            out[f"cold_{which}_ms"] = round(times[0], 2)
            if len(times) > 1:
                out[f"warm_{which}_ms"] = round(statistics.median(times[1:]), 2)
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
        out["neworder_p50_ms"] = round(statistics.median(lat), 3)
        out["neworder_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)
        # PAYMENT (2026-10, DECISIONS #82): the same count, against the orders
        # new-order just placed, each chosen at random so the read is not a
        # scan of the newest page. Read the order, mark it paid, insert the
        # payment, one transaction.
        plat = []
        for j in range(OLTP_OPS):
            okey = rng.randrange(OLTP_OPS)
            t = time.perf_counter()
            b.payment(okey)
            if j >= 20:
                plat.append((time.perf_counter() - t) * 1000)
        plat.sort()
        out["payment_p50_ms"] = round(statistics.median(plat), 3)
        out["payment_p99_ms"] = round(plat[int(len(plat) * 0.99)], 3)
        # ops/s over BOTH transaction types since 2026-10; the September rows
        # (new-order alone) carry the same field under the old instrument, and
        # make_paper_tables keeps the two instruments out of one table.
        out["oltp_ops_per_s"] = round((len(lat) + len(plat)) / ((sum(lat) + sum(plat)) / 1000), 1)
        out["oltp_ops"] = len(lat) + len(plat)

    # TIME THE CLOSE, do not merely perform it (#155). A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. An unrecorded close is an unpriced one, and
    # the row cannot be told apart from a lane that never settles.
    _t = time.perf_counter()
    b.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)
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
