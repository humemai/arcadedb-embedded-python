"""The documents OLTP and durability operations get a disjoint untimed warm-up for every engine (CAMPAIGN section 7 row 65, DECISIONS #157).

Run with `python -m pytest test_docs_oltp_warmup.py -q -rs` from this directory (needs pyarrow; the lane runs here in-process on the real
SQLite adapter, over a tiny TPC-H-shaped parquet).

New-order, payment, and the four single-record operations were timed from the first operation after the load, so on the JVM engines the
statements compiled inside the timed window: ArcadeDB embedded's new-order is 2.34x and 2.56x its own payment, timed right after it,
against 0.94x to 1.30x for every engine that is not on a JVM. Every engine now runs an untimed warm-up of each kind first, on keys BELOW
the timed ones (so the timed inserts still land at the end of the order index), the same count in both durability classes; the first
operation of the session is the cold number; the row records `oltp_warmup` and stops saying "already warm by construction".
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

pytest.importorskip("pyarrow")
import pandas as pd  # noqa: E402
import l1_tpc as T  # noqa: E402

W, OPS, CRUD = 30, 50, 20


def _parquet(tmp_path):
    n = 200
    li = pd.DataFrame({"l_orderkey": range(n), "l_partkey": [i % 7 + 1 for i in range(n)],
                       "l_quantity": [float(i % 50 + 1) for i in range(n)],
                       "l_extendedprice": [100.0 + i for i in range(n)], "l_discount": [0.05] * n,
                       "l_returnflag": ["A"] * n, "l_linestatus": ["F"] * n,
                       "l_shipdate": ["1998-01-01"] * n, "l_shipmode": ["AIR"] * n, "l_tax": [0.02] * n})
    part = pd.DataFrame({"p_partkey": list(range(1, 8)), "p_retailprice": [1.0 + i for i in range(7)]})
    li.to_parquet(tmp_path / "sf0.01_lineitem.parquet", row_group_size=100)
    part.to_parquet(tmp_path / "sf0.01_part.parquet")


@pytest.fixture
def lane(monkeypatch, tmp_path):
    _parquet(tmp_path)
    monkeypatch.setattr(T, "DATA", str(tmp_path))
    monkeypatch.setattr(T, "SF", "0.01")
    monkeypatch.setattr(T, "OLTP_OPS", OPS)
    monkeypatch.setattr(T, "CRUD_OPS", CRUD)
    real = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda _p, *a, **k: real(str(tmp_path / "t.db"), *a, **k))

    def run(warmup):
        monkeypatch.setattr(T, "OLTP_WARMUP", warmup)
        out = tmp_path / "row.json"
        monkeypatch.setattr(sys, "argv", ["l1_tpc.py", "--backend", "sqlite", "--workload", "oltp", "--scale", "tpch1",
                                           "--out", str(out)])
        # the lane ends with os._exit(0); run it up to there by catching the exit
        monkeypatch.setattr(T.os, "_exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))
        with pytest.raises(SystemExit):
            T.main()
        con = sqlite3.connect(str(tmp_path / "t.db"))
        state = {"orders": sorted(r[0] for r in con.execute("SELECT okey FROM orders_new")),
                 "payments": con.execute("SELECT count(*) FROM payments").fetchone()[0],
                 "crud": con.execute("SELECT count(*) FROM crud").fetchone()[0]}
        con.close()
        return json.loads(out.read_text()), state
    return run


def test_the_warmup_runs_below_the_timed_keys_and_leaves_the_tables_the_timed_phases_expect(lane):
    row, state = lane(W)
    # warm orders 0..W-1, timed orders W..W+OPS-1: the timed inserts land at the end of the index
    assert state["orders"] == list(range(W + OPS))
    assert state["payments"] == W + OPS                       # W warm payments and OPS timed ones
    assert state["crud"] == 0                                  # the warm-up deletes its own rows; the timed delete phase empties the rest
    assert row["oltp_warmup"] == W and row["oltp_warmup_s"] >= 0


def test_the_cold_number_is_the_first_operation_of_the_session_and_the_row_stops_claiming_warm_by_construction(lane):
    row, _state = lane(W)
    assert row["cold_first_query_name"] == "new_order" and row["cold_first_query_ms"] is not None
    assert "cold_warm_na" not in row


def test_the_timed_state_digests_are_still_there_and_count_what_ran(lane):
    row, _state = lane(W)
    assert row["res_neworder_n"] == W + OPS and row["res_payment_n"] == W + OPS
    assert row["res_crud_insert_n"] == CRUD and row["res_crud_delete_n"] == 0
    assert row["res_payments_n"] == 1 and row["res_stock_n"] >= 1


def test_without_a_warmup_the_old_protocol_and_its_sentence_are_what_the_row_says(lane):
    row, state = lane(0)
    assert "oltp_warmup" not in row and row["cold_warm_na"]
    assert state["orders"] == list(range(OPS))                 # the timed keys start at 0, as they always did


def test_the_default_count_is_the_one_measured_on_the_laptop_and_is_a_lane_constant():
    """Not a per-engine and not a per-class setting: one module constant, overridable only for a smoke and recorded on the row."""
    src = (HERE / "l1_tpc.py").read_text()
    assert T.OLTP_WARMUP == 2_000 and "BENCH_DOCS_OLTP_WARMUP" in src
    assert src.count("OLTP_WARMUP") >= 3 and "durability_class\"] ==" not in src[src.index("W = OLTP_WARMUP"):src.index("W = OLTP_WARMUP") + 400]
