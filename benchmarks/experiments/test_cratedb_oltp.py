"""CrateDB's documents OLTP cells (2026-11-14): the single-record operations run, new-order and payment are declared unexpressible.

Plain functions, no fixtures: `python test_cratedb_oltp.py` runs them all (the laptop queue guard blocks the test runner), and
pytest collects the same functions in CI. No CrateDB is needed: the adapter runs against a fake connection that records every
statement, and the lane's own `main()` runs in-process on the SQLite adapter, over a tiny TPC-H-shaped parquet.

What each test pins, and the change it fails on (every one of them failed on harness commit 4272386cfa):
  * runner.ARM_RUNS registers the arm for both workloads (the old entry said `olap` only).
  * An arm that declares the transaction half absent runs no new-order and no payment, and its row says why in the
    `res_<name>_digest` fields (DECISIONS #88), with no field that ends in `_unexpressible` (resource_check skips such a row).
  * The skipped loops still take their draws from the seeded key streams, so the single-record rows carry the keys every other
    engine's carry (the crud_insert digest reads `pkey`).
  * CrateTPC has a `crud` table keyed by `ckey`, at the translog class of the cell, read back; the four operations address one
    row by primary key and no refresh sits inside them; the untimed scan refreshes first; the probe declares with the engine's
    own answer and stops the cell when the engine contradicts the declaration.
"""
import json
import os
import re
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import bench_common  # noqa: E402
import l1_tpc as T  # noqa: E402
import runner as RN  # noqa: E402

W, OPS, CRUD = 30, 50, 20
ALL_FOUR = set(T.TXN_DIGESTS) if hasattr(T, "TXN_DIGESTS") else {"neworder", "stock", "payment", "payments"}


# ------------------------------------------------------------------ the lane, in-process, on SQLite
def _parquet(d):
    n = 200
    li = pd.DataFrame({"l_orderkey": range(n), "l_partkey": [i % 7 + 1 for i in range(n)],
                       "l_quantity": [float(i % 50 + 1) for i in range(n)],
                       "l_extendedprice": [100.0 + i for i in range(n)], "l_discount": [0.05] * n,
                       "l_returnflag": ["A"] * n, "l_linestatus": ["F"] * n,
                       "l_shipdate": ["1998-01-01"] * n, "l_shipmode": ["AIR"] * n, "l_tax": [0.02] * n})
    part = pd.DataFrame({"p_partkey": list(range(1, 8)), "p_retailprice": [1.0 + i for i in range(7)]})
    li.to_parquet(Path(d) / "sf0.01_lineitem.parquet", row_group_size=100)
    part.to_parquet(Path(d) / "sf0.01_part.parquet")


def _sqlite_no_txn_class(declared):
    class SQLiteNoTxn(T.SQLiteTPC):
        name = "sqlite_notxn"
        UNEXPRESSIBLE = dict(declared)
    return SQLiteNoTxn


def _run_lane(backend, extra_backends=None):
    """Run l1_tpc.main() for the oltp workload on an in-process backend; return the row it wrote."""
    with tempfile.TemporaryDirectory() as d:
        _parquet(d)
        out = Path(d) / "row.json"
        real = sqlite3.connect
        patches = [mock.patch.object(T, "DATA", d), mock.patch.object(T, "SF", "0.01"), mock.patch.object(T, "OLTP_OPS", OPS),
                   mock.patch.object(T, "CRUD_OPS", CRUD), mock.patch.object(T, "OLTP_WARMUP", W),
                   mock.patch.object(sqlite3, "connect", lambda _p, *a, **k: real(str(Path(d) / "t.db"), *a, **k)),
                   mock.patch.object(T.os, "_exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code))),
                   mock.patch.object(sys, "argv", ["l1_tpc.py", "--backend", backend, "--workload", "oltp", "--scale", "tpch1",
                                                   "--out", str(out)]),
                   mock.patch.dict(T.BACKENDS, extra_backends or {})]
        for p in patches:
            p.start()
        try:
            try:
                T.main()
            except SystemExit as e:
                if e.code not in (0, None):
                    raise
            return json.loads(out.read_text())
        finally:
            for p in reversed(patches):
                p.stop()


# ------------------------------------------------------------------ CrateTPC against a recording fake connection
class FakeCur:
    def __init__(self, cx):
        self.cx, self._rows = cx, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.cx.log.append((sql, params))
        self._rows = self.cx.answer(sql, params)

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeCx:
    def __init__(self, probe_count=1, rollback_error=None, crud_durability=None, explain_error=False):
        self.log, self.probe_count, self.rollback_error = [], probe_count, rollback_error
        self.crud_durability, self.explain_error = crud_durability, explain_error

    def cursor(self):
        return FakeCur(self)

    def close(self):
        pass

    def _durability_of(self, table):
        for sql, _p in self.log:
            m = re.match(r"CREATE TABLE (\w+) ", sql)
            if m and m.group(1) == table:
                return re.search(r'"translog\.durability" = \'(\w+)\'', sql).group(1)
        raise AssertionError(f"no CREATE TABLE {table} in the log")

    def answer(self, sql, params):
        if sql == "ROLLBACK" and self.rollback_error:
            raise RuntimeError(self.rollback_error)
        if sql == "SELECT version()":
            return [("CrateDB 6.4.6 (built x)",)]
        if "FROM sys.nodes" in sql:
            return [(1 << 30, 12)]
        if "FROM information_schema.tables" in sql:
            table = params[0]
            shards = 1 if table in ("part", "crud", "txn_probe") else len(os.sched_getaffinity(0))
            dur = self.crud_durability if (table == "crud" and self.crud_durability) else self._durability_of(table)
            return [(shards, 0, dur, None, None)]
        if sql.startswith("EXPLAIN"):
            if self.explain_error:
                raise RuntimeError("explain refused")
            return [("Get[doc.crud | ckey, pkey, qty | DocKeys{1}]",)]
        if sql == "SELECT count(*) FROM txn_probe":
            return [(self.probe_count,)]
        return []


class FakeLi:
    def frames(self):
        yield pd.DataFrame({"l_orderkey": [1, 2], "l_partkey": [1, 2], "l_quantity": [1.0, 2.0], "l_extendedprice": [1.0, 2.0],
                            "l_discount": [0.1, 0.1], "l_returnflag": ["A", "A"], "l_linestatus": ["F", "F"],
                            "l_shipdate": ["1998-01-01", "1998-01-02"], "l_shipmode": ["AIR", "AIR"], "l_tax": [0.0, 0.0]})


def _built(cls="relaxed", **fake):
    """A CrateTPC that has built its tables on a fake connection at the given durability class."""
    cx = FakeCx(**fake)
    b = T.CrateTPC()
    b.cc, b.cx, b.row_extra = __import__("cratedb_common"), cx, {}
    part = pd.DataFrame({"p_partkey": [1, 2], "p_retailprice": [1.0, 2.0]})
    with mock.patch.object(bench_common, "DURABILITY_CLASS", cls):
        b.build(FakeLi(), part)
    return b, cx


# ------------------------------------------------------------------ tests
def test_the_arm_is_registered_for_both_workloads_at_both_sizes():
    cfg = RN.ARM_RUNS["cratedb_tpc"]["l1tpc"]
    assert set(cfg["workloads"]) == {"oltp", "olap"}, cfg["workloads"]
    assert tuple(cfg["scales"]) == ("tpch1", "tpch10")
    assert RN.arm_runs("l1tpc", "oltp", "cratedb_tpc") and RN.arm_runs("l1tpc", "olap", "cratedb_tpc")
    assert "durability" not in cfg and "reps" not in cfg, "both durability classes, the lane's repetitions"
    assert RN.ARM_RUNS["redis_tpc"]["l1tpc"]["scales"] == ("tpch1",), "the other restricted arms are untouched"


def test_a_declared_absence_runs_no_transaction_and_the_row_says_why():
    why = "no multi-statement transaction: a probe said so"
    row = _run_lane("sqlite_notxn", {"sqlite_notxn": _sqlite_no_txn_class({k: why for k in ALL_FOUR})})
    for k in ("neworder_p50_ms", "neworder_p99_ms", "payment_p50_ms", "payment_p99_ms", "oltp_ops_per_s", "oltp_ops", "payments_n"):
        assert k not in row, f"{k} printed for a transaction that was never run"
    for name in ALL_FOUR:
        assert row[f"res_{name}_digest"] == "unexpressible: " + why, (name, row.get(f"res_{name}_digest"))
        assert row[f"res_{name}_n"] is None
    assert not [k for k in row if k.endswith("_unexpressible")], "resource_check would skip the whole row"
    for op in ("insert", "read", "update", "delete"):
        assert row[f"crud_{op}_p50_ms"] is not None and row[f"crud_{op}_ops"] == CRUD, op
        assert str(row[f"res_crud_{op}_digest"]) and not str(row[f"res_crud_{op}_digest"]).startswith("unexpressible"), op
    assert row["cold_first_query_name"] == "crud_insert", row.get("cold_first_query_name")
    assert row["oltp_warmup"] == W


def test_a_normal_engine_still_runs_both_transactions():
    row = _run_lane("sqlite")
    assert row["neworder_p50_ms"] is not None and row["payment_p50_ms"] is not None and row["oltp_ops"] == 2 * (OPS - 20)
    assert row["cold_first_query_name"] == "new_order"
    assert not str(row["res_neworder_digest"]).startswith("unexpressible")


def test_the_skipped_transactions_leave_the_single_record_keys_as_every_other_engine_has_them():
    plain = _run_lane("sqlite")
    skipped = _run_lane("sqlite_notxn", {"sqlite_notxn": _sqlite_no_txn_class({k: "x" for k in ALL_FOUR})})
    # the digest reads ckey, pkey and qty: a key stream that moved would change pkey
    assert skipped["res_crud_insert_digest"] == plain["res_crud_insert_digest"]
    assert skipped["res_crud_read_digest"] == plain["res_crud_read_digest"]
    assert skipped["res_crud_update_digest"] == plain["res_crud_update_digest"]
    assert skipped["res_crud_delete_digest"] == plain["res_crud_delete_digest"]


def test_a_half_declared_transaction_stops_the_cell():
    cls = _sqlite_no_txn_class({"neworder": "x", "stock": "x"})
    try:
        _run_lane("sqlite_notxn", {"sqlite_notxn": cls})
    except SystemExit as e:
        assert "UNEXPRESSIBLE" in str(e.code) and "payment" in str(e.code), e.code
    else:
        raise AssertionError("a cell that declares only new-order and stock ran")


def test_the_crud_table_is_keyed_by_ckey_and_follows_the_class_of_the_cell():
    for klass, want in (("relaxed", "ASYNC"), ("strict", "REQUEST")):
        b, cx = _built(klass)
        ddl = [s for s, _p in cx.log if s.startswith("CREATE TABLE crud ")]
        assert len(ddl) == 1 and "ckey BIGINT PRIMARY KEY" in ddl[0] and "pkey BIGINT" in ddl[0], ddl
        assert "CLUSTERED INTO 1 SHARDS" in ddl[0] and f"'{want}'" in ddl[0], (klass, ddl[0])
        assert b.row_extra["cratedb_crud_translog_durability"] == want, b.row_extra
        assert b.row_extra["cratedb_crud_shards"] == 1
        assert b.durability == (bench_common.DURABILITY_CRATEDB_STRICT if klass == "strict" else bench_common.DURABILITY_CRATEDB)


def test_a_crud_table_that_did_not_take_the_class_stops_the_build():
    try:
        _built("relaxed", crud_durability="REQUEST")
    except RuntimeError as e:
        assert "crud" in str(e) and "one cell, one class" in str(e)
    else:
        raise AssertionError("the build published a cell whose two tables run different translog classes")


def test_the_four_operations_address_one_row_by_primary_key_and_no_refresh_sits_inside_them():
    b, cx = _built()
    cx.log.clear()
    b.crud_insert(7, 3)
    b.crud_read(7)
    b.crud_update(7)
    b.crud_delete(7)
    sqls = [s for s, _p in cx.log]
    assert len(sqls) == 4 and all("REFRESH" not in s.upper() for s in sqls), sqls
    assert sqls[0].startswith("INSERT INTO crud (ckey, pkey, qty, price)")
    assert sqls[1] == "SELECT ckey, pkey, qty FROM crud WHERE ckey = %s"
    assert sqls[2] == "UPDATE crud SET qty = 2 WHERE ckey = %s"
    assert sqls[3] == "DELETE FROM crud WHERE ckey = %s"
    assert [p for _s, p in cx.log] == [(7, 3), (7,), (7,), (7,)]


def test_the_untimed_scan_refreshes_before_it_reads():
    b, cx = _built()
    cx.log.clear()
    b.crud_scan()
    sqls = [s for s, _p in cx.log]
    assert sqls == ["REFRESH TABLE crud", "SELECT ckey, pkey, qty FROM crud"], sqls


def test_the_probe_declares_the_four_digests_with_the_engines_own_answer():
    b, cx = _built()
    extra = b.preflight("oltp")
    assert set(b.UNEXPRESSIBLE) == ALL_FOUR
    reason = b.UNEXPRESSIBLE["neworder"]
    assert "no multi-statement transaction" in reason and "count 1 after REFRESH TABLE" in reason, reason
    assert extra["cratedb_txn_probe"] in reason and extra["cratedb_crud_read_plan"].startswith("Get[")
    probe = [s for s, _p in cx.log if s in ("BEGIN", "ROLLBACK") or "txn_probe" in s]
    assert probe[0].startswith("CREATE TABLE txn_probe") and "BEGIN" in probe and "ROLLBACK" in probe, probe


def test_an_engine_error_is_the_evidence_and_the_declaration_stands():
    b, _cx = _built(rollback_error="ROLLBACK is not supported")
    extra = b.preflight("oltp")
    assert "ROLLBACK is not supported" in extra["cratedb_txn_probe"] and set(b.UNEXPRESSIBLE) == ALL_FOUR


def test_a_rollback_that_worked_contradicts_the_declaration_and_stops_the_cell():
    b, _cx = _built(probe_count=0)
    try:
        b.preflight("oltp")
    except SystemExit as e:
        assert "must be re-read" in str(e.code)
    else:
        raise AssertionError("CrateDB rolled the probe back and the cell went on declaring transactions unexpressible")
    assert not b.UNEXPRESSIBLE


def test_a_failed_plan_read_is_recorded_and_never_ends_the_cell():
    b, _cx = _built(explain_error=True)
    extra = b.preflight("oltp")
    assert "explain refused" in extra["cratedb_readback_error"] and "cratedb_crud_read_plan" not in extra
    assert set(b.UNEXPRESSIBLE) == ALL_FOUR


def test_an_analytics_cell_declares_nothing_and_probes_nothing():
    b, cx = _built()
    cx.log.clear()
    assert b.preflight("olap") == {} and not b.UNEXPRESSIBLE and not cx.log


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    bad = 0
    for k, v in tests:
        try:
            v()
            print("PASS", k)
        except Exception:  # noqa: BLE001
            bad += 1
            print("FAIL", k)
            traceback.print_exc()
    print(f"{len(tests) - bad} of {len(tests)} passed")
    sys.exit(1 if bad else 0)
