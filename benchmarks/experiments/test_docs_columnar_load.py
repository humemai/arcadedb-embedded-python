"""The documents lane loads ArcadeDB embedded through the bindings' columnar insert (CAMPAIGN section 7 row 63, DECISIONS #153 item 2, own issue #150).

Run with `python -m pytest test_docs_columnar_load.py -q -rs` from this directory (needs pandas; numpy for the frame).

Each parquet batch crosses the bridge as whole columns (a long[] or double[] from the numpy buffer, a String[] from a list) and the documents are built in
Java, instead of one JSON payload per batch: 8.21 s against 18.42 s for insert_many on the first 2,000,000 SF1 line items (laptop, relative only, same
sums and count). The user's choice over my recommendation (DECISIONS #153 item 2). The transport is the only change: the same async writers, bucket rule, and
executor flush class (parallel=True). A wheel without insert_columns keeps insert_many and records nothing, so a measurement meant to be columnar cannot
silently become the other one. The adapter runs here against a stand-in database that records the calls it is given.
"""
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

pd = pytest.importorskip("pandas")
import l1_tpc as T  # noqa: E402


def _frame(n=7):
    return pd.DataFrame({
        "l_orderkey": range(n), "l_partkey": [i % 3 + 1 for i in range(n)], "l_quantity": [float(i + 1) for i in range(n)],
        "l_extendedprice": [100.0 + i for i in range(n)], "l_discount": [0.05] * n, "l_returnflag": ["A"] * n,
        "l_linestatus": ["F"] * n, "l_shipdate": ["1998-01-01"] * n, "l_shipmode": ["AIR"] * n, "l_tax": [0.02] * n})[T.LI_COLS]


class _Lines:
    def __init__(self, frames):
        self._frames = frames
        self.n_streamed = sum(len(f) for f in frames)

    def frames(self):
        yield from self._frames

    def records(self):
        for f in self._frames:
            yield from f.itertuples(index=False)


class _Exec:
    def get_parallel_level(self):
        return 3

    def get_commit_every(self):
        return 10_240

    def set_transaction_sync(self, mode):
        self.sync = mode

    def get_transaction_sync(self):
        return self.sync


class _Db:
    def __init__(self, columnar):
        self.calls, self.commands = [], []
        self._ex = _Exec()
        self.stored = 0
        if columnar:
            self.insert_columns = self._insert_columns

    def async_executor(self):
        return self._ex

    def command(self, language, text):
        self.commands.append(text)

    def _insert_columns(self, type_name, columns, commit_every=10_000, parallel=False):
        n = len(next(iter(columns.values())))
        self.calls.append(("insert_columns", type_name, dict(columns), parallel))
        self.stored += n
        return n

    def insert_many(self, type_name, rows, commit_every=10_000, parallel=False):
        self.calls.append(("insert_many", type_name, len(rows), parallel))
        if type_name == "LineItem":
            self.stored += len(rows)
        return len(rows)

    def query(self, language, text, *a):
        return types.SimpleNamespace(to_list=lambda: [{"n": self.stored}])


def _build(columnar, frames):
    arm = object.__new__(T.ArcadeTPC)
    arm.db = _Db(columnar)
    li = _Lines(frames)
    part = pd.DataFrame({"p_partkey": [1, 2, 3], "p_retailprice": [1.0, 2.0, 3.0]})
    arm.build(li, part)
    return arm


def test_li_columns_are_numpy_for_numbers_and_text_objects_for_the_rest():
    cols = T.li_columns(_frame())
    assert list(cols) == T.LI_COLS
    np = pytest.importorskip("numpy")
    for c in ("l_orderkey", "l_partkey"):
        assert cols[c].dtype == np.int64
    for c in ("l_quantity", "l_extendedprice", "l_discount", "l_tax"):
        assert cols[c].dtype == np.float64
    for c in ("l_returnflag", "l_linestatus", "l_shipdate", "l_shipmode"):
        assert cols[c].dtype == object and all(isinstance(v, str) for v in cols[c])


def test_every_batch_goes_through_insert_columns_in_the_parallel_mode_and_the_row_says_so():
    frames = [_frame(7), _frame(5)]
    arm = _build(True, frames)
    li_calls = [c for c in arm.db.calls if c[0] == "insert_columns"]
    assert len(li_calls) == 2 and all(c[1] == "LineItem" and c[3] is True for c in li_calls)
    assert [len(next(iter(c[2].values()))) for c in li_calls] == [7, 5]
    assert set(li_calls[0][2]) == set(T.LI_COLS)
    assert not any(c[0] == "insert_many" and c[1] == "LineItem" for c in arm.db.calls)
    assert arm.columnar_insert == "insert_columns"
    assert arm.db.stored == 12


def test_a_wheel_without_insert_columns_keeps_insert_many_and_says_nothing():
    arm = _build(False, [_frame(7)])
    assert any(c[0] == "insert_many" and c[1] == "LineItem" and c[3] is True for c in arm.db.calls)
    assert not hasattr(arm, "columnar_insert")


def test_the_lane_records_the_call_on_the_row():
    src = (HERE / "l1_tpc.py").read_text()
    assert '"load_call_rows", "columnar_insert"' in src


# ---- the page's sentence -------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def EW():
    import os
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


def _row(**kw):
    base = {"lane": "l1tpc", "workload": "oltp", "backend": "arcadedb_embedded", "instrument": "2026-10"}
    base.update(kw)
    return base


def test_the_sentence_says_insert_many_while_any_row_behind_the_table_loaded_that_way(EW, monkeypatch):
    table = {"id": "docs_oltp"}
    old, new = EW.OCT_PROSE["docs_oltp"]["ingest_insert_many"][0], EW.OCT_PROSE["docs_oltp"]["ingest"][0]
    assert "insert_many in 10,000-row batches" in old and "insert_columns" in new and "insert_many in 10,000" not in new
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [_row()])                                         # an October row
    assert EW._docs_ingest_note(table, new) == old
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [_row(columnar_insert="insert_columns")])        # a re-pin row
    assert EW._docs_ingest_note(table, new) == new
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [_row(columnar_insert="insert_columns"), _row()])  # mixed: the old one stands
    assert EW._docs_ingest_note(table, new) == old
    assert EW._docs_ingest_note({"id": "l2"}, "x") == "x"                                      # no other table changes


def test_both_sentences_are_allowed_entries_of_the_documents_tables_and_the_new_one_names_the_whole_frame_engines(EW):
    for t in ("docs_oltp", "docs_olap"):
        entries = EW._oct_entries(t)
        assert EW.OCT_PROSE[t]["ingest"][0] in entries and EW.OCT_PROSE[t]["ingest_insert_many"][0] in entries
    new = EW.OCT_PROSE["docs_oltp"]["ingest"][0]
    assert "DuckDB and ArcadeDB embedded load whole frames" in new and "are fed row by row" in new
