"""Native backend: ``insert_many`` keeps a chunk on the JSON bulk entry (``arcadedb_n_insert_rows``) when its rows hold a date-time, date,
Decimal, bytes, a numpy scalar, a pandas NA or NaT, or a null.

Before, one such value made ``json.dumps`` raise and the whole 10,000-row chunk went through ``INSERT INTO t CONTENT :row`` for each row
(``arcadedb_n_exec_many``). ``Json.java`` already decodes the tagged values the Python side writes, so the rows now cross in the text as
tagged values. Each test stores the same rows through that statement (``_command_many``, what the chunk used to take) and through
``insert_many`` and compares the stored values and their types; a spy on ``lib.call`` proves which entry ran. A row with a value the text
still cannot carry (NaN, an integer beyond 64 bits, a date-time inside a list or map, a lone surrogate, a ``time``) goes through the
statement on its own; the rows around it keep the bulk entry and the insert order.

Needs the native library, so conftest.py collects this file on the native backend only (a skip elsewhere would fail
scripts/check_test_skips.py).
"""

import datetime as dt
import decimal

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded._native import lib

np = pytest.importorskip("numpy")

ROWS, MANY, COLP = (
    "arcadedb_n_insert_rows",
    "arcadedb_n_exec_many",
    "arcadedb_n_insert_colp",
)
UTC9 = dt.timezone(dt.timedelta(hours=9))

# name -> value; the statement path (INSERT ... CONTENT :row) stores every one of these, so the bulk entry has a stored value to match
VALUES = {
    "naive_dt": dt.datetime(2026, 5, 6, 7, 8, 9, 123456),
    "aware_dt": dt.datetime(2026, 5, 6, 7, 8, 9, 654321, tzinfo=UTC9),
    "dt_whole_second": dt.datetime(2026, 5, 6, 7, 8, 9),
    "date": dt.date(2026, 5, 6),
    "decimal": decimal.Decimal("12345.6789"),
    "decimal_exp": decimal.Decimal("1E+3"),
    "decimal_neg": decimal.Decimal("-0.50"),
    "bytes": b"\x00\xff abc\x7f",
    "bytearray": bytearray(b"ab\x80"),
    "np_int64": np.int64(2**40 + 5),
    "np_int8": np.int8(-3),
    "np_uint32": np.uint32(4_000_000_000),
    "np_float64": np.float64(0.1),
    "np_float32": np.float32(0.1),
    "np_bool": np.bool_(True),
    "none": None,
    "plain_int": 7,
}

DECLARED = {
    "naive_dt": "DATETIME",
    "aware_dt": "DATETIME",
    "dt_whole_second": "DATETIME",
    "date": "DATE",
    "decimal": "DECIMAL",
    "decimal_exp": "DECIMAL",
    "decimal_neg": "DECIMAL",
    "bytes": "BINARY",
    "np_int64": "LONG",
    "np_int8": "INTEGER",
    "np_uint32": "LONG",
    "np_float64": "DOUBLE",
    "np_float32": "FLOAT",
    "np_bool": "BOOLEAN",
}


class Spy:
    def __init__(self, monkeypatch):
        self.calls = []
        real = lib.call

        def call(name, *args):
            self.calls.append(name)
            return real(name, *args)

        monkeypatch.setattr(lib, "call", call)

    def count(self, name):
        return self.calls.count(name)

    def clear(self):
        self.calls.clear()


@pytest.fixture
def spy(monkeypatch):
    return Spy(monkeypatch)


def _create(db, name, declared):
    db.command("sql", f"CREATE DOCUMENT TYPE {name}")
    db.command("sql", f"CREATE PROPERTY {name}.id INTEGER")
    if declared:
        for prop, ty in DECLARED.items():
            db.command("sql", f"CREATE PROPERTY {name}.{prop} {ty}")


def _statement_path(db, type_name, rows):
    """The reference: INSERT INTO t CONTENT :row for each row, as insert_many fell back to it for a chunk with such a value."""
    sql = f"INSERT INTO `{type_name}` CONTENT :row"  # nosec B608 - test-owned type name
    db.begin()
    db._command_many("sql", sql, [{"row": row} for row in rows])
    db.commit()


def _stored(db, type_name):
    """Every record by id as {property: (python type name, repr)}, so a changed type is as visible as a changed value."""
    out = []
    for rec in db.query(
        "sql", f"SELECT FROM {type_name} ORDER BY id"
    ).to_list():  # nosec B608 - test-owned type name
        out.append(
            {
                k: (type(v).__name__, repr(v))
                for k, v in sorted(rec.items())
                if not k.startswith("@") and k != "rid"
            }
        )
    return out


def _rows(names):
    return [{"id": i, name: VALUES[name]} for i, name in enumerate(names)]


@pytest.mark.parametrize("declared", [True, False], ids=["declared", "schemaless"])
def test_every_value_kind_is_stored_as_the_statement_path_stores_it(
    temp_db_path, spy, declared
):
    rows = _rows(list(VALUES))
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", declared)
        _create(db, "Bulk", declared)
        _statement_path(db, "Ref", rows)
        spy.clear()
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 0, "the chunk left the bulk entry"
        assert spy.count(ROWS) == 1
        assert _stored(db, "Bulk") == _stored(db, "Ref")
        assert len(_stored(db, "Bulk")) == len(VALUES)


@pytest.mark.parametrize("declared", [True, False], ids=["declared", "schemaless"])
def test_one_row_with_every_kind_at_once(temp_db_path, spy, declared):
    row = {"id": 0, **VALUES}
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", declared)
        _create(db, "Bulk", declared)
        _statement_path(db, "Ref", [row])
        spy.clear()
        db.insert_many("Bulk", [row])
        assert spy.count(MANY) == 0 and spy.count(ROWS) == 1
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_a_pandas_timestamp_is_stored_as_the_statement_path_stores_it(
    temp_db_path, spy
):
    pd = pytest.importorskip("pandas")
    rows = [
        {"id": 0, "ts": pd.Timestamp("2026-05-06 07:08:09.123456789")},
        {"id": 1, "ts": pd.Timestamp("2026-05-06 07:08:09.123456", tz="Asia/Seoul")},
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        _statement_path(db, "Ref", rows)
        spy.clear()
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 0 and spy.count(ROWS) == 1
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_pandas_na_and_nat_are_nulls_on_the_bulk_entry(temp_db_path, spy):
    """The statement path refuses pd.NA and pd.NaT; insert_dataframe stores them as nulls, and so does the bulk entry."""
    pd = pytest.importorskip("pandas")
    rows = [
        {"id": 0, "a": pd.NA, "b": pd.NaT, "c": 1},
        {"id": 1, "a": 2, "b": pd.Timestamp("2026-05-06"), "c": pd.NA},
        {"id": 2, "a": np.datetime64("NaT", "us"), "b": None, "c": 3},
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 0
        got = db.query("sql", "SELECT FROM Bulk ORDER BY id").to_list()
        assert [(r.get("a"), r.get("b"), r.get("c")) for r in got] == [
            (None, None, 1),
            (2, dt.datetime(2026, 5, 6), None),
            (None, None, 3),
        ]


def test_a_numpy_datetime64_is_a_naive_datetime(temp_db_path, spy):
    rows = [{"id": 0, "ts": np.datetime64("2026-05-06T07:08:09.123456")}]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 0
        assert db.query("sql", "SELECT FROM Bulk").first().get("ts") == dt.datetime(
            2026, 5, 6, 7, 8, 9, 123456
        )


def test_none_in_every_column_stays_on_the_bulk_entry(temp_db_path, spy):
    rows = [
        {"id": i, "a": None, "b": None if i % 2 else 1.5, "c": None} for i in range(50)
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 0
        assert db.count_type("Bulk") == 50


def test_a_big_chunk_with_one_datetime_is_one_bulk_call(temp_db_path, spy):
    n = 10_000
    rows = [{"id": i, "x": i * 2} for i in range(n)]
    rows[5_000]["ts"] = dt.datetime(2026, 1, 1)
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        assert db.insert_many("Bulk", rows) == n
        assert spy.count(MANY) == 0 and spy.count(ROWS) == 1
        assert db.count_type("Bulk") == n


UNCARRIABLE = {
    "nan": float("nan"),
    "nested_dt": [dt.datetime(2026, 1, 1)],
    "dict_dt": {"k": dt.datetime(2026, 1, 1)},
    "decimal_in_list": [decimal.Decimal("1.5")],
}


@pytest.mark.parametrize("name", list(UNCARRIABLE))
def test_an_uncarriable_value_sends_its_own_row_to_the_statement_not_the_chunk(
    temp_db_path, spy, name
):
    n = 1_000
    rows = [
        {"id": i, "x": i, "ts": dt.datetime(2026, 1, 1, 0, 0, i % 60)} for i in range(n)
    ]
    rows[500]["v"] = UNCARRIABLE[name]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        _statement_path(db, "Ref", rows)
        spy.clear()
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 1, "one statement run for the one uncarriable row"
        assert (
            spy.count(ROWS) == 2
        ), "the rows before and after it stay on the bulk entry"
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_rows_keep_their_insert_order_around_a_statement_run(temp_db_path, spy):
    n = 300
    rows = [{"id": i, "ts": dt.datetime(2026, 1, 1)} for i in range(n)]
    for i in (3, 4, 5, 150, 299):
        rows[i]["v"] = float("nan")
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert spy.count(MANY) == 3  # runs 3-5, 150, 299
        ids = [r.get("id") for r in db.query("sql", "SELECT id FROM Bulk").to_list()]
        assert ids == list(range(n))


def test_commit_every_still_commits_in_the_middle_of_mixed_chunks(temp_db_path):
    rows = [
        {"id": i, "ts": dt.datetime(2026, 1, 1), "d": decimal.Decimal(i)}
        for i in range(2_500)
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        assert db.insert_many("Bulk", rows, commit_every=1_000) == 2_500
        assert db.count_type("Bulk") == 2_500
        assert not db.is_transaction_active()


def test_a_failing_row_rolls_the_open_batch_back(temp_db_path):
    rows = [{"id": i, "ts": dt.datetime(2026, 1, 1)} for i in range(20)]
    rows[10]["ts"] = object()  # no stored form: both paths raise
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        with pytest.raises(Exception):
            db.insert_many("Bulk", rows)
        assert db.count_type("Bulk") == 0
        assert not db.is_transaction_active()


def test_a_user_dict_that_looks_like_a_tag_is_stored_as_before(temp_db_path):
    """Json.java decodes any one-key map keyed by the tag marker, on the statement path and on the bulk entry alike (a quirk of the native
    parser, not changed here): the row goes to the statement, as before, and is stored as that path stores it.
    """
    rows = [
        {
            "id": 0,
            "m": {"\u0001": ["T", "2026-01-01T00:00:00"]},
            "ts": dt.datetime(2026, 1, 1),
        }
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        _statement_path(db, "Ref", rows)
        db.insert_many("Bulk", rows)
        assert _stored(db, "Bulk") == _stored(db, "Ref")
