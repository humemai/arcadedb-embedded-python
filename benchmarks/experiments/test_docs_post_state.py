"""The documents lane's new-order and payment writes are inside an answer check (CAMPAIGN section 7 row 58, BUGS F172).

Run with `python -m pytest test_docs_post_state.py -q -rs` from this directory (add `--with duckdb` to run the DuckDB case).

New-order inserts an order AND decrements the part's stock; payment marks an order paid AND inserts a payment. The
state digests read the orders only, so an engine that skipped the stock decrement, or a payment's insert, printed a
faster write and passed every gate. The lane now reads back, untimed and in each engine's own language, the parts whose
stock moved (`stock`) and the payment count (`payments`, as a one-row digest so the cross-engine gate compares it).
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import l1_tpc as T  # noqa: E402

ARMS = [T.DuckTPC, T.SQLiteTPC, T.MongoTPC, T.SurrealTPC, T.SurrealServedTPC, T.PostgresTPC, T.PostgresTunedTPC,
        T.ArcadeTPC, T.ArcadeServerTPC, T.ArcadeServerImgDefaultsTPC, T.ArangoTPC]


@pytest.mark.parametrize("cls", ARMS, ids=lambda c: c.__name__)
def test_every_documents_arm_can_read_back_its_stock(cls):
    assert callable(getattr(cls, "stock_scan", None)), f"{cls.__name__} has no stock_scan"


def test_each_language_asks_for_the_parts_whose_stock_moved():
    src = (HERE / "l1_tpc.py").read_text()
    for needle in ('"SELECT p_partkey, stock FROM part WHERE stock <> 100"',                  # DuckDB, SQLite, PostgreSQL
                   '{"stock": {"$ne": 100}}',                                                    # MongoDB
                   '"SELECT p_partkey, stock FROM part WHERE stock != 100"',                    # SurrealQL
                   '"SELECT p_partkey, stock FROM Part WHERE stock <> 100 LIMIT 1000000"',      # ArcadeDB, both
                   '"FOR p IN part FILTER p.stock != 100 RETURN {p_partkey: p.p_partkey, stock: p.stock}"'):   # AQL
        assert needle in src, needle
    assert T.STOCK_START == 100


def test_the_lane_records_the_stock_after_new_order_and_the_payments_after_the_payment_loop():
    src = (HERE / "l1_tpc.py").read_text()
    main = src[src.index("def main():"):]
    a = main.index('record_result(out, "neworder", b.oltp_scan()')
    b = main.index('record_result(out, "stock", b.stock_scan(), **STOCK_DIGEST)')
    c = main.index("# PAYMENT (2026-10, DECISIONS #82)")
    d = main.index('record_result(out, "payments", [(out["payments_n"],)], **PAYMENTS_DIGEST)')
    assert a < b < c < d


def _prepare(cls, monkeypatch, tmp_path):
    """A tiny documents database through the REAL adapter, no server: SQLite and DuckDB are in-process."""
    import pandas as pd
    part = pd.DataFrame({"p_partkey": [1, 2, 3, 4], "p_retailprice": [1.0, 2.0, 3.0, 4.0]})
    if cls is T.SQLiteTPC:
        import sqlite3
        real = sqlite3.connect
        monkeypatch.setattr(sqlite3, "connect", lambda _p, *a, **k: real(str(tmp_path / "t.db"), *a, **k))
    elif cls is T.DuckTPC:
        import duckdb
        real = duckdb.connect
        monkeypatch.setattr(duckdb, "connect", lambda _p, *a, **k: real(str(tmp_path / "t.duckdb"), *a, **k))
    a = cls()
    a.connect()
    return a, part


def _build_orders_only(a, part):
    """build() wants a lineitem stream; the OLTP tables are all this needs, so feed it an empty one."""
    import pandas as pd

    class _NoLines:
        def frames(self):
            yield pd.DataFrame({c: pd.Series([], dtype="object" if c in ("l_shipdate", "l_returnflag", "l_linestatus",
                                                                           "l_shipmode") else "float64")
                                for c in T.LI_COLS})

        def rows(self):
            return iter(())
    a.build(_NoLines(), part)


def test_sqlite_stock_is_the_parts_new_order_touched_and_a_skipped_decrement_changes_the_digest(monkeypatch, tmp_path):
    a, part = _prepare(T.SQLiteTPC, monkeypatch, tmp_path)
    _build_orders_only(a, part)
    assert a.stock_scan() == []                       # nothing has moved: no row differs from the start
    for i, k in enumerate([1, 1, 3]):
        a.new_order(i, k)
    rows = a.stock_scan()
    assert sorted(rows) == [(1, 98), (3, 99)]
    good = bench_common.record_result({}, "stock", rows, **T.STOCK_DIGEST)

    # an engine whose new-order inserts the order and skips the decrement reads back nothing
    skipped = bench_common.record_result({}, "stock", [], **T.STOCK_DIGEST)
    assert good["digest"] != skipped["digest"]
    # and one that decrements twice reads back the wrong stock
    twice = bench_common.record_result({}, "stock", [(1, 97), (3, 98)], **T.STOCK_DIGEST)
    assert good["digest"] != twice["digest"]
    a.close()


def test_duckdb_and_sqlite_agree_on_the_stock_digest(monkeypatch, tmp_path):
    pytest.importorskip("duckdb", reason="add --with duckdb to run the DuckDB case")
    digests = {}
    for cls in (T.SQLiteTPC, T.DuckTPC):
        a, part = _prepare(cls, monkeypatch, tmp_path)
        _build_orders_only(a, part)
        for i, k in enumerate([2, 2, 2, 4]):
            a.new_order(i, k)
        digests[cls.__name__] = bench_common.record_result({}, "stock", a.stock_scan(), **T.STOCK_DIGEST)["digest"]
        a.close()
    assert digests["SQLiteTPC"] == digests["DuckTPC"]


def test_a_payment_count_that_differs_changes_the_digest():
    a = bench_common.record_result({}, "payments", [(1000,)], **T.PAYMENTS_DIGEST)["digest"]
    b = bench_common.record_result({}, "payments", [(999,)], **T.PAYMENTS_DIGEST)["digest"]
    c = bench_common.record_result({}, "payments", [(1000,)], **T.PAYMENTS_DIGEST)["digest"]
    assert a != b and a == c


def test_the_payments_digest_is_in_the_digest_field_the_equivalence_gate_reads():
    out = {}
    bench_common.record_result(out, "payments", [(1000,)], **T.PAYMENTS_DIGEST)
    import equivalence_check as E
    assert any(E.DIGEST_RE.match(k) for k in out) and re.match(r"^res_payments_digest$", "res_payments_digest")
    assert "res_payments_digest" in out and "res_stock_digest" not in out
