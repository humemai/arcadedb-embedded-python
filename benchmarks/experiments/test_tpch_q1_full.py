"""The documents lane runs the full TPC-H Q1 on every engine (CAMPAIGN section 7 row 57, DECISIONS #151 item 3, BUGS F170).

Run with `python -m pytest test_tpch_q1_full.py -q -rs` from this directory (add `--with duckdb --with pyarrow` for the cases that
run a real adapter; the official-answer case also needs DuckDB's tpch extension and the laptop's SF0.01 parquet, and says so when it skips).

TPC-H Q1 returns ten columns: the two group keys, sum_qty, sum_base_price, sum_disc_price, sum_charge, avg_qty, avg_price, avg_disc,
count_order. The October lane's Q1 returned seven of them on every engine (`l_tax` was never loaded, so no sum_charge, and no
avg_price or avg_disc), while the page called it "TPC-H's own Q1". Now `l_tax` joins the load and every engine's text, the digest
declares all ten columns, and every documents analytics row records `tpch_q1` = full.
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import l1_tpc as T  # noqa: E402

FULL = ("sum_qty", "sum_base", "sum_disc", "sum_charge", "avg_qty", "avg_price", "avg_disc", "n")


def test_the_load_carries_l_tax_last_so_every_positional_table_keeps_its_order():
    assert T.LI_COLS[-1] == "l_tax" and T.LI_COLS.count("l_tax") == 1 and len(T.LI_COLS) == 10


@pytest.mark.parametrize("name,text", [("DuckDB", T.Q1_DUCK), ("SQLite", T.Q1_SQLITE), ("ArcadeDB SQL", T.Q1_ARCADE),
                                       ("SurrealQL", T.SurrealTPC.Q1), ("AQL", T.ArangoTPC.Q1)])
def test_every_text_engines_q1_computes_all_ten_columns(name, text):
    for alias in FULL:
        assert re.search(rf"\b{alias}\b", text), f"{name} Q1 has no {alias}"
    assert re.search(r"\(1 \+ l(\.l)?_tax\)", text), f"{name} Q1 does not charge the tax"


def test_the_mongodb_pipeline_computes_all_ten_columns():
    group = next(st["$group"] for st in T.MongoTPC.Q1 if "$group" in st)
    assert {"sum_qty", "sum_base", "sum_disc", "sum_charge", "avg_qty", "avg_price", "avg_disc", "n"} <= set(group)
    assert "$l_tax" in repr(group["sum_charge"]) and group["avg_price"] == {"$avg": "$l_extendedprice"}
    assert group["avg_disc"] == {"$avg": "$l_discount"}


def test_the_digest_declares_all_ten_columns_and_compares_every_measure_as_a_number():
    d = T.OLAP_DIGEST["q1"]
    names = [c if isinstance(c, str) else c[0] for c in d["columns"]]
    assert names == ["l_returnflag", "l_linestatus", "sum_qty", "sum_base", "sum_disc", "sum_charge", "avg_qty",
                     "avg_price", "avg_disc", "n"]
    assert set(d["coerce"]) == set(FULL) - {"n"}                       # a count stays exact, never rounded


def test_every_loader_names_the_column():
    src = (HERE / "l1_tpc.py").read_text()
    assert "l_shipmode TEXT, l_tax REAL)" in src                       # SQLite
    assert src.count("INSERT INTO lineitem VALUES (?,?,?,?,?,?,?,?,?,?)") == 2
    assert "l_shipdate DATE, l_shipmode TEXT, l_tax DOUBLE PRECISION)" in src      # PostgreSQL's COPY is positional
    assert '"CREATE PROPERTY LineItem.l_tax DOUBLE"' in src            # ArcadeDB served; embedded creates one per LI_COLS entry
    assert src.count('"l_tax": float(t.l_tax)') == 2                   # both ArcadeDB inserts
    assert '"l_discount", "l_tax"' in src                              # _prepare casts the decimal column to double


def test_the_lane_stamps_the_q1_it_ran_on_every_analytics_row():
    src = (HERE / "l1_tpc.py").read_text()
    main = src[src.index("def main():"):]
    assert main.index('if args.workload == "olap":') < main.index("out[TPCH_Q1_FIELD] = TPCH_Q1") < main.index("b.olap(which)")
    assert T.TPCH_Q1_FIELD == "tpch_q1" and T.TPCH_Q1 == "full"
    ew = (HERE / "export_web.py").read_text()
    assert re.search(r'^_TPCH_Q1_FIELD = "tpch_q1"$', ew, re.M)


# ---- the answer, through the real adapters ---------------------------------------------------------------------

def _lineitem_frame():
    """Twelve line items in four groups, with a tax column; dates on both sides of the Q1 cutoff."""
    import pandas as pd
    rows = []
    for i in range(12):
        rows.append({"l_orderkey": i, "l_partkey": i % 3 + 1, "l_quantity": float(i + 1),
                     "l_extendedprice": 100.0 + 7 * i, "l_discount": [0.0, 0.05, 0.1][i % 3],
                     "l_returnflag": "AR"[i % 2], "l_linestatus": "FO"[(i // 2) % 2],
                     "l_shipdate": "1998-08-30" if i < 10 else "1998-12-01", "l_shipmode": "AIR",
                     "l_tax": [0.0, 0.02, 0.08][i % 3]})
    return pd.DataFrame(rows)[T.LI_COLS]


def _reference_q1(df):
    """TPC-H Q1 as the specification defines it, in pandas."""
    import pandas as pd
    d = df[df["l_shipdate"] <= "1998-09-02"].copy()
    d["disc_price"] = d["l_extendedprice"] * (1 - d["l_discount"])
    d["charge"] = d["disc_price"] * (1 + d["l_tax"])
    g = d.groupby(["l_returnflag", "l_linestatus"]).agg(
        sum_qty=("l_quantity", "sum"), sum_base=("l_extendedprice", "sum"), sum_disc=("disc_price", "sum"),
        sum_charge=("charge", "sum"), avg_qty=("l_quantity", "mean"), avg_price=("l_extendedprice", "mean"),
        avg_disc=("l_discount", "mean"), n=("l_quantity", "count")).reset_index()
    return [tuple(r) for r in g.sort_values(["l_returnflag", "l_linestatus"]).itertuples(index=False)]


class _Lines:
    def __init__(self, df):
        self.df = df

    def frames(self):
        d = self.df.copy()
        d["l_shipdate"] = d["l_shipdate"].astype(str)
        yield d

    def rows(self):
        for df in self.frames():
            yield from df[T.LI_COLS].itertuples(index=False, name=None)

    def records(self):
        for df in self.frames():
            yield from df.itertuples(index=False)


def _adapter(cls, monkeypatch, tmp_path):
    part = __import__("pandas").DataFrame({"p_partkey": [1, 2, 3], "p_retailprice": [1.0, 2.0, 3.0]})
    if cls is T.SQLiteTPC:
        import sqlite3
        real = sqlite3.connect
        monkeypatch.setattr(sqlite3, "connect", lambda _p, *a, **k: real(str(tmp_path / "t.db"), *a, **k))
    else:
        import duckdb
        real = duckdb.connect
        monkeypatch.setattr(duckdb, "connect", lambda _p, *a, **k: real(str(tmp_path / "t.duckdb"), *a, **k))
    a = cls()
    a.connect()
    a.build(_Lines(_lineitem_frame()), part)
    return a


@pytest.mark.parametrize("cls", [T.SQLiteTPC, T.DuckTPC], ids=lambda c: c.__name__)
def test_the_real_adapters_answer_the_specifications_q1_and_agree_with_each_other(cls, monkeypatch, tmp_path):
    if cls is T.DuckTPC:
        pytest.importorskip("duckdb", reason="add --with duckdb to run the DuckDB case")
    a = _adapter(cls, monkeypatch, tmp_path)
    got = [tuple(r) for r in a.olap("q1")]
    want = _reference_q1(_lineitem_frame())
    assert len(got) == len(want) == 4
    for g, w in zip(got, want):
        assert g[:2] == w[:2]
        for x, y in zip(g[2:], w[2:]):
            assert x == pytest.approx(y, rel=1e-9)
    a.close()


def test_sqlite_and_duckdb_give_one_digest(monkeypatch, tmp_path):
    pytest.importorskip("duckdb", reason="add --with duckdb to run the DuckDB case")
    digs = []
    for cls in (T.SQLiteTPC, T.DuckTPC):
        a = _adapter(cls, monkeypatch, tmp_path)
        digs.append(bench_common.record_result({}, "q1", a.olap("q1"), **T.OLAP_DIGEST["q1"])["digest"])
        a.close()
    assert digs[0] == digs[1]


def test_without_l_tax_the_old_loader_could_not_have_answered(monkeypatch, tmp_path):
    """The defect, held: the seven-column Q1 and a frame with no tax cannot produce sum_charge."""
    df = _lineitem_frame().drop(columns=["l_tax"])
    assert "l_tax" not in df.columns and "l_tax" in T.Q1_DUCK


# ---- the official SF0.01 answer (laptop: DuckDB's tpch extension and the SF0.01 parquet) ----------------------------------

def test_the_lanes_q1_equals_duckdbs_bundled_official_answer_at_sf001(monkeypatch, tmp_path):
    duckdb = pytest.importorskip("duckdb", reason="add --with duckdb --with pyarrow")
    pytest.importorskip("pyarrow")
    import os
    path = Path(os.path.expanduser("~/bench-data/tpch/sf0.01_lineitem.parquet"))
    if not path.exists():
        pytest.skip(f"no {path}: the SF0.01 parquet lives on the laptop")
    cx = duckdb.connect()
    try:
        cx.execute("INSTALL tpch; LOAD tpch")
        official = cx.execute("SELECT answer FROM tpch_answers() WHERE query_nr = 1 AND scale_factor = 0.01").fetchone()[0]
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"DuckDB's tpch extension is not available here: {e.__class__.__name__}")
    lines = [l.split("|") for l in official.strip().splitlines()]
    head, body = lines[0], lines[1:]
    cols = dict(zip(("sum_qty", "sum_base", "sum_disc", "sum_charge", "avg_qty", "avg_price", "avg_disc", "n"),
                    ("sum_qty", "sum_base_price", "sum_disc_price", "sum_charge", "avg_qty", "avg_price", "avg_disc",
                     "count_order")))
    part = __import__("pandas").DataFrame({"p_partkey": [1], "p_retailprice": [1.0]})
    # the adapters read the parquet through the lane's own streaming loader
    for cls in (T.SQLiteTPC, T.DuckTPC):
        li = T.LineItems(str(path))
        if cls is T.SQLiteTPC:
            import sqlite3
            real = sqlite3.connect
            monkeypatch.setattr(sqlite3, "connect", lambda _p, *a_, **k: real(str(tmp_path / "o.sqlite"), *a_, **k))
        else:
            real = duckdb.connect
            monkeypatch.setattr(duckdb, "connect", lambda _p, *a_, **k: real(str(tmp_path / "o.duckdb"), *a_, **k))
        a = cls()
        a.connect()
        a.build(li, part)
        got = [tuple(r) for r in a.olap("q1")]
        assert len(got) == len(body)
        for g, row in zip(got, body):
            o = dict(zip(head, row))
            assert (g[0], g[1]) == (o["l_returnflag"], o["l_linestatus"])
            for i, (mine, theirs) in enumerate(cols.items(), start=2):
                want = float(o[theirs])
                assert float(g[i]) == pytest.approx(want, rel=1e-9, abs=0.005), (cls.__name__, mine, g[i], want)
        a.close()
