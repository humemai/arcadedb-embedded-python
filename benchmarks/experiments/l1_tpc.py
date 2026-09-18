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
import budget_lookup
import bench_common


def pg_durability(cx):
    """What the PostgreSQL server actually runs, read from it (#81, #90).

    The expected answer depends on the cell's durability class: `off` at the
    relaxed class, `on` at the strict one, both set by runner.py on the server
    itself so every session runs under it. Read rather than asserted, and a
    server that answers something else marks the row instead of passing.
    """
    try:
        with cx.cursor() as c:
            c.execute("SHOW synchronous_commit")
            v = c.fetchone()[0]
        try:
            cx.rollback()
        except Exception:  # noqa: BLE001
            pass
        return bench_common.pg_durability_string(v)
    except Exception as e:  # noqa: BLE001
        return f"synchronous_commit=unknown ({e.__class__.__name__})"

DATA = os.environ.get("BENCH_TPC_DATA", "/data/tpch")
SF = os.environ.get("BENCH_TPC_SF", "1")
OLTP_OPS = 1_000
# 100 runs per analytical query per repetition (DECISIONS #82): was 5, and a
# p99 needs the samples (2026-09-10, BUGS F29). BENCH_OLAP_ITER lowers it for a
# laptop smoke, where one SurrealDB cell is 16 minutes of the same query; the
# count lands on the row as `olap_iters`, so a cell that ran fewer says so
# instead of looking like a campaign cell.
OLAP_ITER = int(os.environ.get("BENCH_OLAP_ITER") or 100)
# THE PER-QUERY BUDGET (DECISIONS #100, third lane): the graph lane's mechanism
# (graph_common.OLAP_BUDGET_S, #82b) as the time-series lane took it
# (l4_tsbs.QUERY_BUDGET_S). A property of the lane and the same for every
# engine on the table, so it moves no comparison by itself. The clock starts
# before the cold pass, the cold pass always runs, the loop stops at the first
# iteration that would start after the budget is spent, and the row records
# <q>_budget_s, <q>_iters, <q>_elapsed_s and <q>_censored; the table names a
# censored query with its iteration count and the time it reached while the
# cell's other queries keep their numbers. Why this lane: the laptop skeleton's
# embedded SurrealDB analytics cell at 60k line items exceeded the whole-cell
# 0.25 h budget and left no row, and at SF1 that engine scans about 35 us per
# row, so a hundred iterations of Q1 alone is hours against the cell timeout.
#
# WHY 1,800 s. Two constraints, and the cell timeout binds first. (1) The
# tpch1 cell timeout is 3 h (runner.TIMEOUT_BY_SCALE), and a censored cell
# costs five budgets plus its build, so 5 x B + 1,280 s (embedded SurrealDB's
# SF1 build, BUGS F41) must stay under 10,800 s: B <= about 1,900 s. (2) The
# slowest legitimate served engines on mini in September (results/runs_paper.csv,
# tpch1, five reps each): ArcadeDB server Q1 10.20-10.35 s and MongoDB Q1
# 9.76-10.08 s, so about 1,035 s for a hundred iterations; 1,800 s is 1.74x
# that, and the three October queries on those engines are cheaper than Q1
# (0.5-0.6x on the laptop skeleton). The SurrealDB 3.2.4 server's Q1 at
# 40.9-41.2 s (4,120 s for a hundred) is the one served number the budget
# cannot cover: covering it needs B >= 6,000 s and a 9 h cell, so it will be
# censored at about 43 of 100 iterations, which leaves a 41 s p50 a 41 s
# p50 and is named on the table. The override exists for a laptop probe of
# the mechanism and never for a campaign.
OLAP_BUDGET_S = float(os.environ.get("BENCH_DOCS_OLAP_BUDGET_S") or 1800.0)
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
SELECT sum(l_extendedprice * l_discount) AS revenue, count(*) AS n FROM lineitem
WHERE l_shipdate >= DATE '1994-01-01' AND l_shipdate < DATE '1995-01-01'
  AND l_discount BETWEEN 0.05 AND 0.07 AND l_quantity < 24
"""
# The 2026-10 line-item set (DECISIONS #82): the same three questions in
# every engine's language, no join anywhere.
# A TOTAL ORDER, because "the top ten" must be one ten. Revenue ties are
# unlikely here, but the graph lane's analytics showed what an ambiguous
# ORDER BY ... LIMIT does across engines, and the same rule applies to every
# limited query in the instrument (2026-09-14).
TOP_PARTS_SQL = ("SELECT l_partkey, sum(l_extendedprice * (1 - l_discount)) AS rev "
                 "FROM lineitem GROUP BY l_partkey ORDER BY rev DESC, l_partkey ASC LIMIT 10")
SHIP_MODE_SQL = "SELECT l_shipmode, count(*) AS n FROM lineitem GROUP BY l_shipmode ORDER BY l_shipmode"
BY_MONTH_DUCK = ("SELECT date_trunc('month', l_shipdate) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev, "
                 "count(*) AS n FROM lineitem GROUP BY m ORDER BY m")
BY_MONTH_TEXT = ("SELECT substr(l_shipdate, 1, 7) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev, "
                 "count(*) AS n FROM lineitem GROUP BY m ORDER BY m")
# ArcadeDB SQL: same semantics on the LineItem document type; dates stored
# as ISO strings (lexicographic order == chronological for ISO-8601).
# sum_disc WAS MISSING HERE, AND ONLY HERE (found 2026-09-14 while declaring
# the #88 digest columns). Every comparator's Q1 -- DuckDB, PostgreSQL, SQLite,
# MongoDB, SurrealDB, ArangoDB -- computes five aggregates; this one computed
# four, because sum(l_extendedprice * (1 - l_discount)) was never written into
# the ArcadeDB text. Both ArcadeDB arms therefore ran a cheaper Q1 than every
# engine they were printed beside, from the first TPC-H row in August to the
# September freeze on the live page. The digest would have caught it on the
# first comparison; the point of #88 is that nothing did for six weeks.
Q1_ARCADE = ("SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, "
             "sum(l_extendedprice) AS sum_base, "
             "sum(l_extendedprice * (1 - l_discount)) AS sum_disc, "
             "avg(l_quantity) AS avg_qty, "
             "count(*) AS n FROM LineItem WHERE l_shipdate <= '1998-09-02' "
             "GROUP BY l_returnflag, l_linestatus "
             "ORDER BY l_returnflag, l_linestatus")
# BETWEEN, NOT >= AND <=, AND THE REASON IS AN ENGINE DEFECT (found 2026-09-14
# by the #88 digest, on its first cross-engine comparison). ArcadeDB SQL parses
# a decimal literal in a comparison at single precision, so a literal 0.05 is
# 0.05000000074505806 and the stored DOUBLE 0.05 is 0.05000000000000000277:
# `l_discount >= 0.05` therefore behaves as `> 0.05` and drops the whole 0.05
# bucket. Measured on the laptop at SF0.01 against wheel 26.8.1, 60,175 line
# items, 11 discount values of about 5,470 rows each:
#
#     l_discount = 0.05                              0 rows
#     l_discount >= 0.05      == l_discount > 0.05   27,187 (five buckets)
#     l_discount <= 0.07      == l_discount < 0.07   43,749 (eight buckets)
#     >= 0.05 AND <= 0.07                            10,761 (TWO buckets)
#     BETWEEN 0.05 AND 0.07                          16,323 (three buckets)
#     >= :a AND <= :b as bound parameters            16,323 (three buckets)
#
# So both ArcadeDB arms have been answering Q6 over two thirds of the qualifying
# rows since the lane was written: revenue 842,572.68 against every comparator's
# 1,193,053.23, and a latency over a third fewer rows. BETWEEN and bound
# parameters are both correct; BETWEEN is also what Q6_DUCK writes, so the two
# texts now say the same thing in the same shape. The defect itself is an
# upstream matter (a Java repro against the engine's SQL parser), not a harness
# one, and the published September Q6 cell for ArcadeDB is wrong.
Q6_ARCADE = ("SELECT sum(l_extendedprice * l_discount) AS revenue, count(*) AS n FROM LineItem "
             "WHERE l_shipdate >= '1994-01-01' AND l_shipdate < '1995-01-01' "
             "AND l_discount BETWEEN 0.05 AND 0.07 AND l_quantity < 24")
ARCADE_OLAP = {
    "q1": Q1_ARCADE, "q6": Q6_ARCADE,
    "top_parts": ("SELECT l_partkey, sum(l_extendedprice * (1 - l_discount)) AS rev FROM LineItem "
                  "GROUP BY l_partkey ORDER BY rev DESC, l_partkey ASC LIMIT 10"),
    "ship_mode": "SELECT l_shipmode, count(*) AS n FROM LineItem GROUP BY l_shipmode ORDER BY l_shipmode",
    "by_month": ("SELECT l_shipdate.substring(0, 7) AS m, sum(l_extendedprice * (1 - l_discount)) AS rev, "
                 "count(*) AS n FROM LineItem GROUP BY m ORDER BY m"),
}
DUCK_OLAP = {"q1": Q1_DUCK, "q6": Q6_DUCK, "top_parts": TOP_PARTS_SQL, "ship_mode": SHIP_MODE_SQL, "by_month": BY_MONTH_DUCK}

LI_COLS = ["l_orderkey", "l_partkey", "l_quantity", "l_extendedprice",
           "l_discount", "l_returnflag", "l_linestatus", "l_shipdate",
           "l_shipmode"]   # l_shipmode joined for the 2026-10 ship-mode query
OLAP_QUERIES = ("q1", "q6", "top_parts", "ship_mode", "by_month")
# THE SERVED ARM'S ROW CAP, written down because it is invisible until it
# bites. The ArcadeDB HTTP API truncates a result at 20,000 rows unless the
# request says otherwise, and the #88 digests caught both served time-series
# arms returning exactly 20,000 where every other engine returned 32,944. This
# lane sends everything through /command, which takes no `limit` field, so its
# scans carry an explicit LIMIT in the SQL instead; the largest answer here is
# CRUD_OPS rows, three orders of magnitude under the cap. A query on this lane
# that starts returning more than 20,000 rows needs the cap raised in the SQL.


# ---------------------------------------------------------------------------
# WHAT THE ANSWER LOOKS LIKE (DECISIONS #88). One declaration per query, not
# per engine: the tuple is the query's column order, and the alternatives in a
# tuple are the names the dialects give the same column -- a MongoDB $group
# calls its key "_id" (and reaches into it for a composite key), an AQL COLLECT
# calls it whatever its RETURN names, and psycopg, DuckDB and SQLite hand back
# positional tuples that already ARE this order.
#
# `coerce` says what a column IS where the engines spell it differently but
# mean the same thing: by_month's key is a truncated DATE in DuckDB and
# PostgreSQL and a seven-character substring everywhere else, which is the same
# month.
#
# A MEASURE IS DECLARED `num`; A COUNT AND AN IDENTIFIER ARE NOT. Found at the
# campaign's own SF1 on 2026-09-14, where the pricing summary split SEVEN
# ENGINES TO ONE and nobody had the wrong answer:
#
#     ArangoDB   sum_qty = 37734107     (an int: AQL's SUM over a column
#                                        VelocyPack stored as integers returns
#                                        an integer)
#     every other engine
#                sum_qty = 37734107.0   (a double: SQL sum(), MongoDB $sum,
#                                        SurrealQL math::sum)
#
# The canonical form prints an int exactly and a double to six significant
# digits, so those became "37734107" and "3.77341e+07". `n` in the same row was
# an int on every engine and identical, `avg_qty` was bit-identical, and
# `avg_qty * n` is `sum_qty` -- so the two sides held the SAME NUMBER and the
# digest split on its spelling. It is invisible below 10**6, which is why the
# SF0.01 skeleton passed: at that size sum_qty is 377,341 and both spellings
# are "377341". At SF1 three of Q1's four groups cross the boundary; at SF10 all
# four do. A gate that refuses a publish over this is refusing arithmetic.
#
# So the fix is a declaration, not a looser hash: every summed or averaged
# MEASURE is declared `num` and compared as a number whatever type the driver
# returns, while `n`, `l_partkey` and the CRUD keys stay EXACT -- a count
# rounded to six significant digits would let 1,234,567 and 1,234,568 agree.
# Declared once per query and never per engine, so it cannot be used to make
# one engine's answer match another's. Verified across all eight engines that
# produced a clean SF1 row (tpc_rounding_audit.py).
OLAP_DIGEST = {
    "q1": dict(columns=(("l_returnflag", "_id.f", "f"), ("l_linestatus", "_id.s", "s"),
                        "sum_qty", "sum_base", "sum_disc", "avg_qty", "n"),
               coerce={"sum_qty": "num", "sum_base": "num",
                       "sum_disc": "num", "avg_qty": "num"}),
    # THE COUNT IS PART OF THE ANSWER (DECISIONS #94). `revenue` is one large
    # float, so at SF1 and above a single lost row falls inside six significant
    # digits and the digest does not move: measured, the revenue total detected
    # a missing row 10.8 per cent of the time and the monthly revenue 36.5. The
    # rows each of them aggregates are now counted in the query itself and
    # compared EXACTLY, so one lost row fails the gate whatever the sum does.
    # The count rides the same scan the sum already makes, and the published
    # latency columns still time exactly one call of exactly this query, so
    # what they MEAN is unchanged -- which is why #94 required the change
    # before the campaign rather than during it.
    "q6": dict(columns=("revenue", "n"), coerce={"revenue": "num"}),
    # ORDER BY rev DESC LIMIT 10: the membership of the top ten is the answer,
    # and two engines may break a revenue tie differently, so the canonical
    # form sorts on rev with the part key as tie-break.
    "top_parts": dict(columns=(("l_partkey", "_id", "k"), "rev"),
                      order_matters=True, order_key="rev", id_key="l_partkey",
                      coerce={"rev": "num"}),
    # No measure here: the only value column is a count.
    "ship_mode": dict(columns=(("l_shipmode", "_id", "m"), "n")),
    "by_month": dict(columns=(("m", "_id"), "rev", "n"),
                     coerce={"m": "month", "rev": "num"}),
}

# ---------------------------------------------------------------------------
# THE FOUR SINGLE-RECORD OPERATIONS (DECISIONS #82a). "Nothing times the
# simplest thing anyone does to a database, which is one record created, read,
# updated, and deleted", and it is the most comparable operation across engines
# because every one of them expresses it without dialect argument. 1,000 of
# each per repetition, on a table of the same shape as a TPC-C order line,
# printed as their own columns beside the two transactions.
#
# A WRITE HAS NO ANSWER TO DIGEST, so what is digested is the POST-STATE: the
# whole crud table read back after each phase, untimed. After the inserts that
# is 1,000 rows at qty 1, after the updates 1,000 rows at qty 2, after the
# deletes none. An insert that wrote nothing, an update that matched nothing,
# and a delete that deleted nothing each fail the gate instead of printing a
# fast number (#82a). A read-back rather than count(*)+sum(qty) because
# engines disagree about what an aggregate over no rows returns, and that
# disagreement would be about SQL, not about the data.
CRUD_OPS = int(os.environ.get("BENCH_CRUD_OPS", "1000"))
CRUD_QTY_AFTER_UPDATE = 2
CRUD_DIGEST = dict(columns=(("ckey", "_id"), "pkey", "qty"))
OLTP_STATE_DIGEST = dict(columns=(("okey", "_id"), "pkey", "qty", "paid"))
CRUD_READ_DIGEST = dict(columns=(("ckey", "_id"), "pkey", "qty"))


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
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_DUCKDB

    def connect(self):
        import duckdb
        self.cx = duckdb.connect("/tmp/tpc_duck.db")
        # F6: DuckDB sizes its pool from the host (20 threads) under the 12-thread
        # cpuset; only sched_getaffinity sees the cpuset. Same fix as l1_tabular.
        self.cx.execute(f"PRAGMA threads={len(os.sched_getaffinity(0))}")
        self.version = duckdb.__version__

    def build(self, li, part):
        self.cx.register("li_src", li)
        self.cx.execute("CREATE TABLE lineitem AS SELECT * FROM li_src")
        self.cx.register("p_src", part)
        self.cx.execute("CREATE TABLE part AS SELECT *, 100 AS stock FROM p_src")
        self.cx.execute("CREATE TABLE orders_new (okey BIGINT, pkey BIGINT, qty INT, paid INT DEFAULT 0)")
        self.cx.execute("CREATE INDEX o_okey ON orders_new (okey)")
        self.cx.execute("CREATE TABLE payments (okey BIGINT, pkey BIGINT, amount DOUBLE)")
        self.cx.execute("CREATE TABLE crud (ckey BIGINT PRIMARY KEY, pkey BIGINT, qty INT, price DOUBLE)")
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

    # The four single-record operations (#82a). Each is one auto-committed
    # statement, which on this engine is one transaction.
    def crud_insert(self, i, pkey):
        self.cx.execute("INSERT INTO crud VALUES (?, ?, 1, 9.99)", [i, pkey])

    def crud_read(self, i):
        return self.cx.execute("SELECT ckey, pkey, qty FROM crud WHERE ckey=?", [i]).fetchall()

    def crud_update(self, i):
        self.cx.execute("UPDATE crud SET qty = 2 WHERE ckey=?", [i])

    def crud_delete(self, i):
        self.cx.execute("DELETE FROM crud WHERE ckey=?", [i])

    def crud_scan(self):
        return self.cx.execute("SELECT ckey, pkey, qty FROM crud").fetchall()

    def oltp_scan(self):
        return self.cx.execute("SELECT okey, pkey, qty, paid FROM orders_new").fetchall()

    def payments_n(self):
        return self.cx.execute("SELECT count(*) FROM payments").fetchone()[0]

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
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_SQLITE

    def connect(self):
        import sqlite3
        self.cx = sqlite3.connect("/tmp/tpc_sqlite.db")
        self.cx.execute("PRAGMA foreign_keys=ON")   # no schema here declares one; stated for completeness
        self.cx.execute("PRAGMA journal_mode=WAL")
        # NORMAL at the relaxed class, FULL at the strict one (DECISIONS #90).
        self.cx.execute(f"PRAGMA synchronous={bench_common.sqlite_synchronous()}")
        self.durability = bench_common.sqlite_durability_readback(self.cx)
        self.version = f"sqlite {sqlite3.sqlite_version}"

    def build(self, li, part):
        self.cx.execute("CREATE TABLE lineitem (l_orderkey INTEGER, l_partkey INTEGER, "
                        "l_quantity REAL, l_extendedprice REAL, l_discount REAL, "
                        "l_returnflag TEXT, l_linestatus TEXT, l_shipdate TEXT, l_shipmode TEXT)")
        self.cx.execute("CREATE TABLE part (p_partkey INTEGER PRIMARY KEY, p_retailprice REAL, stock INTEGER)")
        self.cx.execute("CREATE TABLE orders_new (okey INTEGER PRIMARY KEY, pkey INTEGER, qty INTEGER, paid INTEGER DEFAULT 0)")
        self.cx.execute("CREATE TABLE payments (okey INTEGER, pkey INTEGER, amount REAL)")
        self.cx.execute("CREATE TABLE crud (ckey INTEGER PRIMARY KEY, pkey INTEGER, qty INTEGER, price REAL)")
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

    # The four single-record operations (#82a), each one committed transaction.
    def crud_insert(self, i, pkey):
        self.cx.execute("INSERT INTO crud VALUES (?, ?, 1, 9.99)", (i, pkey))
        self.cx.commit()

    def crud_read(self, i):
        return self.cx.execute("SELECT ckey, pkey, qty FROM crud WHERE ckey=?", (i,)).fetchall()

    def crud_update(self, i):
        self.cx.execute("UPDATE crud SET qty = 2 WHERE ckey=?", (i,))
        self.cx.commit()

    def crud_delete(self, i):
        self.cx.execute("DELETE FROM crud WHERE ckey=?", (i,))
        self.cx.commit()

    def crud_scan(self):
        return self.cx.execute("SELECT ckey, pkey, qty FROM crud").fetchall()

    def oltp_scan(self):
        return self.cx.execute("SELECT okey, pkey, qty, paid FROM orders_new").fetchall()

    def payments_n(self):
        return self.cx.execute("SELECT count(*) FROM payments").fetchone()[0]

    def close(self):
        self.cx.close()


class MongoTPC:
    """MongoDB 8.2: lineitem and part as collections, ISO-text dates like the
    ArcadeDB and SQLite arms, Q1/Q6 as aggregation pipelines, new-order as
    one multi-document transaction (which is why the server runs as a
    single-node replica set) (2026-09-11)."""
    name = "mongodb"
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_MONGODB

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
        # j=false at the relaxed class, j=true at the strict one, which is what
        # makes the ack wait for the journal sync (DECISIONS #90).
        self._wc = WriteConcern(w=1, j=bench_common.journal_ack())
        self.durability = bench_common.at_class(bench_common.DURABILITY_MONGODB)

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
        # w=1, j=false on every timed write (#81); cached so the timed loop
        # does not build a collection handle per operation.
        self._crud = self.db.get_collection("crud", write_concern=self._wc)
        self._crud.create_index("ckey", unique=True)

    _REV = {"$sum": {"$multiply": ["$l_extendedprice", {"$subtract": [1, "$l_discount"]}]}}
    TOP_PARTS = [{"$group": {"_id": "$l_partkey", "rev": _REV}},
                 {"$sort": {"rev": -1, "_id": 1}}, {"$limit": 10}]
    SHIP_MODE = [{"$group": {"_id": "$l_shipmode", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
    BY_MONTH = [{"$group": {"_id": {"$substr": ["$l_shipdate", 0, 7]}, "rev": _REV, "n": {"$sum": 1}}},
                {"$sort": {"_id": 1}}]
    Q1 = [{"$match": {"l_shipdate": {"$lte": "1998-09-02"}}},
          {"$group": {"_id": {"f": "$l_returnflag", "s": "$l_linestatus"},
                      "sum_qty": {"$sum": "$l_quantity"}, "sum_base": {"$sum": "$l_extendedprice"},
                      "sum_disc": {"$sum": {"$multiply": ["$l_extendedprice", {"$subtract": [1, "$l_discount"]}]}},
                      "avg_qty": {"$avg": "$l_quantity"}, "n": {"$sum": 1}}},
          {"$sort": {"_id.f": 1, "_id.s": 1}}]
    Q6 = [{"$match": {"l_shipdate": {"$gte": "1994-01-01", "$lt": "1995-01-01"},
                      "l_discount": {"$gte": 0.05, "$lte": 0.07}, "l_quantity": {"$lt": 24}}},
          {"$group": {"_id": None, "revenue": {"$sum": {"$multiply": ["$l_extendedprice", "$l_discount"]}},
                      "n": {"$sum": 1}}}]

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

    # The four single-record operations (#82a). No session: a single-document
    # write is atomic in MongoDB by construction, and wrapping it in a
    # transaction would time a distributed-commit path no other engine pays.
    def crud_insert(self, i, pkey):
        self._crud.insert_one({"ckey": i, "pkey": pkey, "qty": 1, "price": 9.99})

    def crud_read(self, i):
        return list(self._crud.find({"ckey": i}, {"_id": 0, "ckey": 1, "pkey": 1, "qty": 1}))

    def crud_update(self, i):
        self._crud.update_one({"ckey": i}, {"$set": {"qty": 2}})

    def crud_delete(self, i):
        self._crud.delete_one({"ckey": i})

    def crud_scan(self):
        return list(self.db["crud"].find({}, {"_id": 0, "ckey": 1, "pkey": 1, "qty": 1}))

    def oltp_scan(self):
        return list(self.db["orders_new"].find({}, {"_id": 0, "okey": 1, "pkey": 1, "qty": 1, "paid": 1}))

    def payments_n(self):
        return self.db["payments"].count_documents({})

    def close(self):
        self.cl.close()


class SurrealTPC:
    """SurrealDB embedded through its Python SDK on SurrealKV (SDK 2.0.0, which carries core 2.3.10):
    lineitem and part as tables, part keyed by record id, dates as ISO text,
    Q1/Q6 in SurrealQL, new-order as one BEGIN/COMMIT transaction
    (2026-09-11). The served twin runs the 3.2.4 server on RocksDB."""
    name = "surrealdb_tpc"   # not "surrealdb": that is the cross-model lane's old row name
    URL = "surrealkv:///tmp/tpc_surrealkv"
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_SURREAL_EMBEDDED

    def _open(self):
        # SURREAL_SYNC_DATA must be in the environment before the datastore is
        # opened, not passed to it (DECISIONS #90).
        self.durability = bench_common.at_class(bench_common.DURABILITY_SURREAL_EMBEDDED)
        surreal_common.apply_durability()
        import shutil
        from surrealdb import Surreal
        shutil.rmtree("/tmp/tpc_surrealkv", ignore_errors=True)
        self.db = Surreal(self.URL)
        self.db.use("bench", "bench")
        self.version = surreal_common.engine_stamp(self.db)   # core version, not the SDK's (F39)

    def connect(self):
        self._open()
        self.db.query("REMOVE TABLE IF EXISTS lineitem; REMOVE TABLE IF EXISTS part; "
                      "REMOVE TABLE IF EXISTS orders_new; REMOVE TABLE IF EXISTS payments; "
                      "REMOVE TABLE IF EXISTS crud")

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
    Q6 = ("SELECT math::sum(l_extendedprice * l_discount) AS revenue, count() AS n FROM lineitem "
          "WHERE l_shipdate >= '1994-01-01' "
          "AND l_shipdate < '1995-01-01' AND l_discount >= 0.05 AND l_discount <= 0.07 AND l_quantity < 24 GROUP ALL")
    # Subquery form for the ordered group-bys: core 2.3.10 sorts by the group
    # key after GROUP BY (the l2 finding of 2026-09-11); 3.2.4 accepts both.
    OLAP = {
        "top_parts": ("SELECT * FROM (SELECT l_partkey, math::sum(l_extendedprice * (1 - l_discount)) AS rev "
                      "FROM lineitem GROUP BY l_partkey) ORDER BY rev DESC, l_partkey ASC LIMIT 10"),
        "ship_mode": "SELECT l_shipmode, count() AS n FROM lineitem GROUP BY l_shipmode ORDER BY l_shipmode",
        "by_month": ("SELECT * FROM (SELECT string::slice(l_shipdate, 0, 7) AS m, "
                     "math::sum(l_extendedprice * (1 - l_discount)) AS rev, count() AS n "
                     "FROM lineitem GROUP BY m) ORDER BY m"),
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

    # The four single-record operations (#82a), by record id.
    def crud_insert(self, i, pkey):
        self.db.query(f"CREATE crud:{i} SET ckey = {i}, pkey = {pkey}, qty = 1, price = 9.99")

    def crud_read(self, i):
        return self._rows(self.db.query(f"SELECT ckey, pkey, qty FROM crud:{i}"))

    def crud_update(self, i):
        self.db.query(f"UPDATE crud:{i} SET qty = 2")

    def crud_delete(self, i):
        self.db.query(f"DELETE crud:{i}")

    def crud_scan(self):
        return self._rows(self.db.query("SELECT ckey, pkey, qty FROM crud"))

    def oltp_scan(self):
        return self._rows(self.db.query("SELECT okey, pkey, qty, paid FROM orders_new"))

    def payments_n(self):
        r = self._rows(self.db.query("SELECT count() AS n FROM payments GROUP ALL"))
        return (r[0].get("n") if r and isinstance(r[0], dict) else 0) or 0

    def close(self):
        try:
            self.db.close()
        except Exception:  # noqa: BLE001
            pass


class SurrealServedTPC(SurrealTPC):
    name = "surrealdb_tpc_server"
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_SURREAL_SERVER

    def _open(self):
        # One shared client for every served arm (DECISIONS #91): it sets the
        # WebSocket options the SDK leaves at the library's defaults, and it
        # reconnects, re-authenticates and re-selects the namespace once when
        # the socket dies mid-query.
        self.db = surreal_common.served_client()
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
        cur.execute("CREATE TABLE crud (ckey BIGINT PRIMARY KEY, pkey BIGINT, qty INT, price DOUBLE PRECISION)")
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

    # The four single-record operations (#82a), each one committed transaction.
    def crud_insert(self, i, pkey):
        self.cx.cursor().execute("INSERT INTO crud VALUES (%s, %s, 1, 9.99)", (i, pkey))
        self.cx.commit()

    def crud_read(self, i):
        cur = self.cx.cursor()
        cur.execute("SELECT ckey, pkey, qty FROM crud WHERE ckey=%s", (i,))
        r = cur.fetchall()
        self.cx.commit()
        return r

    def crud_update(self, i):
        self.cx.cursor().execute("UPDATE crud SET qty = 2 WHERE ckey=%s", (i,))
        self.cx.commit()

    def crud_delete(self, i):
        self.cx.cursor().execute("DELETE FROM crud WHERE ckey=%s", (i,))
        self.cx.commit()

    def _all(self, sql):
        cur = self.cx.cursor()
        cur.execute(sql)
        r = cur.fetchall()
        self.cx.commit()
        return r

    def crud_scan(self):
        return self._all("SELECT ckey, pkey, qty FROM crud")

    def oltp_scan(self):
        return self._all("SELECT okey, pkey, qty, paid FROM orders_new")

    def payments_n(self):
        return self._all("SELECT count(*) FROM payments")[0][0]

    def close(self):
        self.cx.close()


class ArcadeTPC:
    name = "arcadedb_embedded"
    # DECISIONS #81. Every string, and the evidence for the default it
    # names, is in bench_common (one per engine, so two lanes cannot
    # describe the same engine differently).
    durability = bench_common.DURABILITY_ARCADEDB

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
                                           # txWalFlush passed EXPLICITLY at both classes
                                           # (DECISIONS #90): 0 relaxed, 2 strict, so the
                                           # row's claim is a flag this process set rather
                                           # than a default someone remembered.
                                           jvm_kwargs={"heap_size": heap,
                                                       "jvm_args": bench_common.arcade_jvm_args(f"-Xms{heap}")})
        from importlib.metadata import version as _pv
        self.version = _pv("arcadedb-embedded")
        # ASKED, not asserted (#81's standard, doubled by #90's second class).
        self.durability = bench_common.arcade_durability_readback()

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
        db.command("sql", "CREATE DOCUMENT TYPE Crud")
        db.command("sql", "CREATE PROPERTY Crud.ckey LONG")
        db.command("sql", "CREATE INDEX ON Crud (ckey) UNIQUE")
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

    # The four single-record operations (#82a), each in its own transaction so
    # the number is a committed write, as it is on every other engine.
    def crud_insert(self, i, pkey):
        db = self.db
        db.begin()
        db.command("sql", "INSERT INTO Crud SET ckey=:c, pkey=:p, qty=1, price=9.99",
                   {"c": i, "p": pkey})
        db.commit()

    def crud_read(self, i):
        return self.db.query("sql", "SELECT ckey, pkey, qty FROM Crud WHERE ckey=:c",
                             {"c": i}).to_list()

    def crud_update(self, i):
        db = self.db
        db.begin()
        db.command("sql", "UPDATE Crud SET qty = 2 WHERE ckey=:c", {"c": i})
        db.commit()

    def crud_delete(self, i):
        db = self.db
        db.begin()
        db.command("sql", "DELETE FROM Crud WHERE ckey=:c", {"c": i})
        db.commit()

    def crud_scan(self):
        return self.db.query("sql", "SELECT ckey, pkey, qty FROM Crud LIMIT 1000000").to_list()

    def oltp_scan(self):
        return self.db.query("sql", "SELECT okey, pkey, qty, paid FROM OrderNew LIMIT 1000000").to_list()

    def payments_n(self):
        r = self.db.query("sql", "SELECT count(*) AS n FROM Payment").to_list()
        return (r[0].get("n") if r else 0) or 0

    def close(self):
        self.db.close()


class ArcadeServerTPC(ArcadeTPC):
    name = "arcadedb_server"
    # The served twin's txWalFlush is a JAVA_OPTS entry on its container, which
    # runner.py sets for the strict class and records as durability_server_flags.
    # There is no HTTP read-back for it, and the string says so rather than
    # implying the engine was asked.
    durability = bench_common.DURABILITY_ARCADEDB

    def connect(self):
        self.durability = (bench_common.at_class(bench_common.DURABILITY_ARCADEDB)
                           + bench_common.ARCADE_SERVER_DURABILITY_NOTE)
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
                    "CREATE DOCUMENT TYPE Payment",
                    "CREATE DOCUMENT TYPE Crud",
                    "CREATE PROPERTY Crud.ckey LONG",
                    "CREATE INDEX ON Crud (ckey) UNIQUE"):
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
        # The UPDATE goes last: the server appends "limit 20001" to a script
        # that opens with SELECT, and an INSERT ... SET as the final statement
        # cannot parse it (laptop, 2026-09-14); new-order ends with UPDATE too.
        self._cmd(f"SELECT pkey, qty FROM OrderNew WHERE okey={okey};"
                  f"INSERT INTO Payment SET okey={okey}, amount=1.0;"
                  f"UPDATE OrderNew SET paid = 1 WHERE okey={okey}",
                  language="sqlscript")

    # The four single-record operations (#82a), one HTTP command each, which
    # on this server is one transaction each.
    def crud_insert(self, i, pkey):
        self._cmd(f"INSERT INTO Crud SET ckey={i}, pkey={pkey}, qty=1, price=9.99")

    def crud_read(self, i):
        return self._cmd(f"SELECT ckey, pkey, qty FROM Crud WHERE ckey={i}")

    def crud_update(self, i):
        self._cmd(f"UPDATE Crud SET qty = 2 WHERE ckey={i}")

    def crud_delete(self, i):
        self._cmd(f"DELETE FROM Crud WHERE ckey={i}")

    def crud_scan(self):
        return self._cmd("SELECT ckey, pkey, qty FROM Crud LIMIT 1000000")

    def oltp_scan(self):
        return self._cmd("SELECT okey, pkey, qty, paid FROM OrderNew LIMIT 1000000")

    def payments_n(self):
        r = self._cmd("SELECT count(*) AS n FROM Payment")
        return (r[0].get("n") if r else 0) or 0

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
        # waitForSync on the collections the timed writes touch (DECISIONS #90);
        # the two bulk-loaded ones stay at the default, because #90 keeps bulk
        # ingest at one setting.
        _sync = arango_common.sync_flag()
        lc = self.db.create_collection("lineitem")
        pc = self.db.create_collection("part")
        self.db.create_collection("orders_new", sync=_sync)
        self.db.create_collection("payments", sync=_sync)
        self.db.create_collection("crud", sync=_sync)
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
        # Read back from the collection the timed writes touch (#90).
        self.durability = arango_common.durability_readback(self.db, "orders_new")

    Q1 = ("FOR l IN lineitem FILTER l.l_shipdate <= '1998-09-02' "
          "COLLECT f = l.l_returnflag, s = l.l_linestatus "
          "AGGREGATE sum_qty = SUM(l.l_quantity), sum_base = SUM(l.l_extendedprice), "
          "sum_disc = SUM(l.l_extendedprice * (1 - l.l_discount)), avg_qty = AVG(l.l_quantity), n = COUNT(1) "
          "SORT f, s RETURN {f, s, sum_qty, sum_base, sum_disc, avg_qty, n}")
    Q6 = ("FOR l IN lineitem FILTER l.l_shipdate >= '1994-01-01' AND l.l_shipdate < '1995-01-01' "
          "AND l.l_discount >= 0.05 AND l.l_discount <= 0.07 AND l.l_quantity < 24 "
          "COLLECT AGGREGATE revenue = SUM(l.l_extendedprice * l.l_discount), n = COUNT(1) "
          "RETURN {revenue, n}")

    OLAP = {
        "top_parts": ("FOR l IN lineitem COLLECT k = l.l_partkey "
                      "AGGREGATE rev = SUM(l.l_extendedprice * (1 - l.l_discount)) "
                      "SORT rev DESC, k ASC LIMIT 10 RETURN {k, rev}"),
        "ship_mode": "FOR l IN lineitem COLLECT m = l.l_shipmode WITH COUNT INTO n SORT m RETURN {m, n}",
        "by_month": ("FOR l IN lineitem COLLECT m = SUBSTRING(l.l_shipdate, 0, 7) "
                     "AGGREGATE rev = SUM(l.l_extendedprice * (1 - l.l_discount)), n = COUNT(1) "
                     "SORT m RETURN {m, rev, n}"),
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

    # The four single-record operations (#82a). One document operation is one
    # transaction in ArangoDB, so no stream transaction is opened around it.
    def crud_insert(self, i, pkey):
        self.db.collection("crud").insert(
            {"_key": str(i), "ckey": i, "pkey": pkey, "qty": 1, "price": 9.99})

    def crud_read(self, i):
        doc = self.db.collection("crud").get(str(i))
        return [doc] if doc else []

    def crud_update(self, i):
        self.db.collection("crud").update({"_key": str(i), "qty": 2})

    def crud_delete(self, i):
        self.db.collection("crud").delete(str(i))

    def crud_scan(self):
        return list(self.db.aql.execute(
            "FOR c IN crud RETURN {ckey: c.ckey, pkey: c.pkey, qty: c.qty}", batch_size=10_000))

    def oltp_scan(self):
        return list(self.db.aql.execute(
            "FOR o IN orders_new RETURN {okey: o.okey, pkey: o.pkey, qty: o.qty, paid: o.paid}",
            batch_size=10_000))

    def payments_n(self):
        return self.db.collection("payments").count()

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

    # PHASE MARKERS (2026-09-14, same pattern as l3d_dense): a cell that dies
    # names the phase it was in. Entered and left AROUND the timed work, never
    # inside a timed loop.
    _beat = bench_common.PhaseBeat()
    _beat.mark("corpus-load-start", sf=SF, backend=args.backend)
    li, part = load_frames()
    _beat.mark("corpus-loaded", n_lineitem=len(li), n_part=len(part))
    out = {"n_lineitem": len(li), "n_part": len(part), "tpch_sf": SF}

    b = BACKENDS[args.backend]()
    with _beat.phase("connect", backend=args.backend):
        b.connect()
    out["engine_version"] = b.version
    t0 = time.perf_counter()
    with _beat.phase("build", n=len(li)):
        b.build(li, part)
    out["build_s"] = round(time.perf_counter() - t0, 2)

    # `durability` (what the engine runs), `durability_class` (what the cell
    # asked for), and `durability_no_setting` (this engine has no knob), all
    # from one place (DECISIONS #90).
    bench_common.stamp_durability(out, getattr(b, "durability", None))
    out["instrument"] = bench_common.INSTRUMENT
    if args.workload == "olap":
        out["olap_iters"] = OLAP_ITER
        for which in OLAP_QUERIES:
            times = []
            ref = None
            _budget_s, _budget_src = budget_lookup.budget_for(
                "l1tpc", args.scale, which, OLAP_BUDGET_S, "BENCH_DOCS_OLAP_BUDGET_S")
            _beat.mark(f"query-{which}-start", iters=OLAP_ITER, budget_s=_budget_s)
            # THE BUDGET STARTS BEFORE THE COLD PASS (#82b, #100): the first
            # iteration IS the cold pass and always runs, so a censored query
            # still carries a measurement and its answer digest.
            _budget_t0 = time.perf_counter()
            _ran = 0
            _aband_why = ""
            for _ in range(OLAP_ITER):
                if _ran and time.perf_counter() - _budget_t0 > _budget_s:
                    break
                # After the cold pass, abandon rather than spend the whole
                # budget proving what it already showed (DECISIONS #107).
                if _ran == 1:
                    _a, _aband_why = budget_lookup.abandon(
                        time.perf_counter() - _budget_t0, _budget_s, OLAP_ITER)
                    if _a:
                        break
                t = time.perf_counter()
                r = b.olap(which)
                _ran += 1
                # The sample is dropped when the connection broke while it was
                # being taken (DECISIONS #91); every other engine keeps it.
                surreal_common.keep(b, times, (time.perf_counter() - t) * 1000)
                ref = r
            # Censored is counted on iterations RUN, not samples KEPT, so a
            # sample #91 dropped cannot read as a budget the engine did not hit.
            out[f"{which}_budget_s"] = _budget_s
            out[f"{which}_budget_source"] = _budget_src
            if _aband_why:
                out[f"{which}_abandoned"] = _aband_why
            out[f"{which}_iters"] = len(times)
            out[f"{which}_elapsed_s"] = round(time.perf_counter() - _budget_t0, 2)
            out[f"{which}_censored"] = _ran < OLAP_ITER
            if out[f"{which}_censored"]:
                _beat.mark(f"query-{which}-censored", iters=_ran, budget_s=_budget_s,
                           elapsed_s=out[f"{which}_elapsed_s"])
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
            # COLD AND WARM AT p50 AND p99 (DECISIONS #89). The pooled p99
            # above includes the cold iteration, which at OLAP_ITER=100 IS the
            # 99th percentile whenever the first touch is the slowest -- so the
            # published tail was sometimes the cold number wearing a
            # percentile's name. One naming convention across every lane.
            bench_common.record_cold_warm(out, which, times, digits=2)
            # The cell's one cold number, from the first query it ran after the
            # database opened (DECISIONS #89 as amended); setdefault inside, so
            # only the first of these five calls sticks.
            bench_common.record_first_query(out, which, times[0])
            out[f"{which}_rows"] = len(ref) if ref is not None else 0
            # THE ANSWER, not just how long it took (DECISIONS #88). Computed
            # here, outside the timed loop, from the object the LAST timed call
            # returned; re-running the query to digest it would digest a second
            # execution against a different cache state.
            bench_common.record_result(out, which, ref, **OLAP_DIGEST[which])
            _beat.mark(f"query-{which}-done", p50=out[f"{which}_ms"],
                       rows=out[f"{which}_rows"],
                       digest=out[f"res_{which}_digest"])
    else:
        rng = random.Random(SEED)
        keys = part["p_partkey"].tolist()
        lat = []
        _beat.mark("new-order-start", n=OLTP_OPS)
        for i in range(OLTP_OPS):
            k = keys[rng.randrange(len(keys))]
            t = time.perf_counter()
            b.new_order(i, int(k))
            _dt = (time.perf_counter() - t) * 1000
            if i == 0:
                # The first timed operation of the cell, which is this lane's
                # cold number under #89 as amended. The twenty discarded
                # warmups below are still discarded from the percentiles.
                bench_common.record_first_query(out, "new_order", _dt)
            if i >= 20:
                surreal_common.keep(b, lat, _dt)
        lat.sort()
        out["neworder_p50_ms"] = round(statistics.median(lat), 3)
        out["neworder_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)
        _beat.mark("new-order-done", n=OLTP_OPS, p50=out["neworder_p50_ms"])
        # WHAT THE TRANSACTION LEFT BEHIND (#88). A transaction returns nothing
        # to digest, so what is digested is the state it wrote: every order the
        # loop placed, read back untimed. A new-order that silently inserted
        # nothing now fails the gate instead of printing the best number on the
        # table. Taken BEFORE the payment loop, which changes `paid`.
        bench_common.record_result(out, "neworder", b.oltp_scan(), **OLTP_STATE_DIGEST)
        # PAYMENT (2026-10, DECISIONS #82): the same count, against the orders
        # new-order just placed, each chosen at random so the read is not a
        # scan of the newest page. Read the order, mark it paid, insert the
        # payment, one transaction.
        plat = []
        _beat.mark("payment-start", n=OLTP_OPS)
        for j in range(OLTP_OPS):
            okey = rng.randrange(OLTP_OPS)
            t = time.perf_counter()
            b.payment(okey)
            if j >= 20:
                surreal_common.keep(b, plat, (time.perf_counter() - t) * 1000)
        plat.sort()
        out["payment_p50_ms"] = round(statistics.median(plat), 3)
        out["payment_p99_ms"] = round(plat[int(len(plat) * 0.99)], 3)
        _beat.mark("payment-done", n=OLTP_OPS, p50=out["payment_p50_ms"])
        # ops/s over BOTH transaction types since 2026-10; the September rows
        # (new-order alone) carry the same field under the old instrument, and
        # make_paper_tables keeps the two instruments out of one table.
        out["oltp_ops_per_s"] = round((len(lat) + len(plat)) / ((sum(lat) + sum(plat)) / 1000), 1)
        out["oltp_ops"] = len(lat) + len(plat)
        # The same orders after the payments: the rows the loop marked paid are
        # decided by the seeded rng, so the post-state is deterministic and the
        # engines must agree on it.
        bench_common.record_result(out, "payment", b.oltp_scan(), **OLTP_STATE_DIGEST)
        out["payments_n"] = b.payments_n()

        # ------------------------------------------------------------------
        # THE FOUR SINGLE-RECORD OPERATIONS (2026-10, DECISIONS #82a), 1,000 of
        # each, run in the order a record actually lives: created, read,
        # updated, deleted. Each phase finishes before the next starts, so the
        # read reads rows that exist and the delete deletes rows that are there.
        crud_pkeys = [int(keys[rng.randrange(len(keys))]) for _ in range(CRUD_OPS)]
        crud_read_rows = []
        CRUD_WARMUP = min(20, max(0, CRUD_OPS // 10))

        def _crud_phase(label, fn, collect=False):
            lat = []
            _beat.mark(f"{label}-start", n=CRUD_OPS)
            for i in range(CRUD_OPS):
                t = time.perf_counter()
                r = fn(i)
                dt = (time.perf_counter() - t) * 1000
                if i >= CRUD_WARMUP:
                    surreal_common.keep(b, lat, dt)
                if collect and r:
                    crud_read_rows.extend(r)
            lat.sort()
            out[f"{label}_p50_ms"] = round(statistics.median(lat), 3)
            out[f"{label}_p99_ms"] = round(lat[int(len(lat) * 0.99)], 3)
            out[f"{label}_ops"] = CRUD_OPS
            _beat.mark(f"{label}-done", n=CRUD_OPS, p50=out[f"{label}_p50_ms"])

        _crud_phase("crud_insert", lambda i: b.crud_insert(i, crud_pkeys[i]))
        bench_common.record_result(out, "crud_insert", b.crud_scan(), **CRUD_DIGEST)
        _crud_phase("crud_read", b.crud_read, collect=True)
        # The read's digest is the VALUES THE TIMED READS RETURNED, accumulated
        # as they came back and hashed here; the three write phases have no
        # answer of their own and are digested by the state they left.
        bench_common.record_result(out, "crud_read", crud_read_rows, **CRUD_READ_DIGEST)
        _crud_phase("crud_update", b.crud_update)
        bench_common.record_result(out, "crud_update", b.crud_scan(), **CRUD_DIGEST)
        _crud_phase("crud_delete", b.crud_delete)
        bench_common.record_result(out, "crud_delete", b.crud_scan(), **CRUD_DIGEST)

        # DECISIONS #89: where a measurement does not apply the row says so in
        # one clause rather than leaving a blank.
        out["cold_warm_na"] = bench_common.NA_COLD_WARM_TXN

    # TIME THE CLOSE, do not merely perform it (#155). A clean close is when
    # compaction, writeback and WAL truncation happen: measured on 26.8.1 it
    # settles a roughly fixed 30-87 MB, against nothing at all for an
    # already-settled comparator. An unrecorded close is an unpriced one, and
    # the row cannot be told apart from a lane that never settles.
    _t = time.perf_counter()
    with _beat.phase("close"):
        b.close()
    out["close_s"] = round(time.perf_counter() - _t, 3)
    # `reconnects` on every SurrealDB row, zero when nothing happened
    # (DECISIONS #91): a dropped connection has to be visible as a number on
    # the row, not as a traceback in a log nobody reads until a cell dies.
    surreal_common.stamp_reconnects(out, b)
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
