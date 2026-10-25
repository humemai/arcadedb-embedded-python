"""insert_many keeps a chunk on the bulk JSON path when its rows hold a date-time, date, Decimal, bytes, a numpy scalar, or a null.

Those values used to make ``json.dumps`` raise, and one such value sent the whole 10,000-row chunk down the per-row path
(``new_document`` + ``set`` per property + ``save``). They now cross inside the JSON text as tagged values that
``DocumentBatcher.fill`` turns back into the objects the per-row path builds. Each test stores the same rows through the per-row path and
through ``insert_many`` and compares the stored values and their types, and counts ``new_document`` calls to prove which path ran.
A value the bulk path still cannot carry (NaN, an integer beyond 64 bits, a datetime inside a list, a lone surrogate, a ``time``) sends only
its own row down the per-row path, not the 10,000 rows around it.
"""

import datetime as dt
import decimal

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded.core import Database

np = pytest.importorskip("numpy")

UTC9 = dt.timezone(dt.timedelta(hours=9))

# name -> value; every one of these is stored by the per-row path (Document.set), so the bulk path has a stored value to match
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

# a declared property per value, so the engine's conversion to the declared type is compared too
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


@pytest.fixture
def new_documents(monkeypatch):
    """Count the per-row path: it is the only caller of Database.new_document while insert_many runs."""
    calls = []
    real = Database.new_document

    def counting(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs.get("type_name"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Database, "new_document", counting)
    return calls


def _create(db, name, declared):
    db.command("sql", f"CREATE DOCUMENT TYPE {name}")
    db.command("sql", f"CREATE PROPERTY {name}.id INTEGER")
    if declared:
        for prop, ty in DECLARED.items():
            db.command("sql", f"CREATE PROPERTY {name}.{prop} {ty}")


def _per_row(db, type_name, rows):
    """The reference: the per-row path, exactly as insert_many used to fall back to it."""
    db.begin()
    for row in rows:
        doc = db.new_document(type_name)
        for k, v in row.items():
            doc.set(k, v)
        doc.save()
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
def test_every_value_kind_is_stored_as_the_per_row_path_stores_it(
    temp_db_path, new_documents, declared
):
    rows = _rows(list(VALUES))
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", declared)
        _create(db, "Bulk", declared)
        _per_row(db, "Ref", rows)
        new_documents.clear()
        db.insert_many("Bulk", rows)
        assert new_documents == [], "the chunk left the bulk path"
        assert _stored(db, "Bulk") == _stored(db, "Ref")
        assert len(_stored(db, "Bulk")) == len(VALUES)


@pytest.mark.parametrize("declared", [True, False], ids=["declared", "schemaless"])
def test_one_row_with_every_kind_at_once(temp_db_path, new_documents, declared):
    row = {"id": 0, **{k: v for k, v in VALUES.items()}}
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", declared)
        _create(db, "Bulk", declared)
        _per_row(db, "Ref", [row])
        new_documents.clear()
        db.insert_many("Bulk", [row])
        assert new_documents == []
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_a_pandas_timestamp_is_stored_as_the_per_row_path_stores_it(
    temp_db_path, new_documents
):
    pd = pytest.importorskip("pandas")
    naive = pd.Timestamp("2026-05-06 07:08:09.123456789")
    aware = pd.Timestamp("2026-05-06 07:08:09.123456", tz="Asia/Seoul")
    rows = [{"id": 0, "ts": naive}, {"id": 1, "ts": aware}]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        _per_row(db, "Ref", rows)
        new_documents.clear()
        db.insert_many("Bulk", rows)
        assert new_documents == []
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_pandas_na_and_nat_are_nulls_on_the_bulk_path(temp_db_path, new_documents):
    """The per-row path refuses pd.NA and pd.NaT (TypeError / ValueError); insert_dataframe stores them as nulls, and so does the bulk path."""
    pd = pytest.importorskip("pandas")
    rows = [
        {"id": 0, "a": pd.NA, "b": pd.NaT, "c": 1},
        {"id": 1, "a": 2, "b": pd.Timestamp("2026-05-06"), "c": pd.NA},
        {"id": 2, "a": np.datetime64("NaT", "us"), "b": None, "c": 3},
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert new_documents == []
        got = db.query("sql", "SELECT FROM Bulk ORDER BY id").to_list()
        assert [(r.get("a"), r.get("b"), r.get("c")) for r in got] == [
            (None, None, 1),
            (2, dt.datetime(2026, 5, 6), None),
            (None, None, 3),
        ]


def test_a_numpy_datetime64_is_the_datetime_the_per_row_path_would_store(
    temp_db_path, new_documents
):
    """The per-row path raises TypeError for np.datetime64; the bulk path stores the UTC wall clock, like a naive datetime."""
    rows = [{"id": 0, "ts": np.datetime64("2026-05-06T07:08:09.123456")}]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert new_documents == []
        got = db.query("sql", "SELECT FROM Bulk").first()
        assert got.get("ts") == dt.datetime(2026, 5, 6, 7, 8, 9, 123456)


def test_none_in_every_column_stays_on_the_bulk_path(temp_db_path, new_documents):
    rows = [
        {"id": i, "a": None, "b": None if i % 2 else 1.5, "c": None} for i in range(50)
    ]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert new_documents == []
        assert db.count_type("Bulk") == 50


def test_a_big_chunk_with_one_datetime_is_one_bulk_call_not_10000_rows(
    temp_db_path, new_documents
):
    n = 10_000
    rows = [{"id": i, "x": i * 2} for i in range(n)]
    rows[5_000]["ts"] = dt.datetime(2026, 1, 1)
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        assert db.insert_many("Bulk", rows) == n
        assert new_documents == []
        assert db.count_type("Bulk") == n


# values the bulk path still cannot carry: only the row that holds one goes per row
UNCARRIABLE = {
    "nan": float("nan"),
    "nested_dt": [dt.datetime(2026, 1, 1)],
    "dict_dt": {"k": dt.datetime(2026, 1, 1)},
    "decimal_in_list": [decimal.Decimal("1.5")],
    "surrogate": "a\ud800b",
}


@pytest.mark.parametrize(
    "name", ["nan", "nested_dt", "dict_dt", "decimal_in_list", "surrogate"]
)
def test_an_uncarriable_value_sends_its_own_row_per_row_not_the_chunk(
    temp_db_path, new_documents, name
):
    n = 1_000
    rows = [
        {"id": i, "x": i, "ts": dt.datetime(2026, 1, 1, 0, 0, i % 60)} for i in range(n)
    ]
    rows[500]["v"] = UNCARRIABLE[name]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        try:
            _per_row(db, "Ref", rows)
        except (
            Exception
        ):  # nosec B110 - a lone surrogate may be refused; the bulk path must refuse it the same way
            db.rollback() if db.is_transaction_active() else None
            new_documents.clear()
            with pytest.raises(Exception):
                db.insert_many("Bulk", rows)
            return
        new_documents.clear()
        db.insert_many("Bulk", rows)
        assert new_documents == [
            "Bulk"
        ], "only the row with the uncarriable value goes per row"
        assert _stored(db, "Bulk") == _stored(db, "Ref")


def test_rows_keep_their_insert_order_around_a_per_row_run(temp_db_path, new_documents):
    n = 300
    rows = [{"id": i, "ts": dt.datetime(2026, 1, 1)} for i in range(n)]
    for i in (3, 4, 5, 150, 299):
        rows[i]["v"] = float("nan")  # per-row rows between and at the ends of bulk runs
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Bulk", False)
        db.insert_many("Bulk", rows)
        assert len(new_documents) == 5
        # a scan returns records in insertion (RID) order
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


def test_parallel_insert_many_carries_the_same_values(temp_db_path, new_documents):
    rows = _rows(list(VALUES))
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Par", False)
        _per_row(db, "Ref", rows)
        new_documents.clear()
        db.insert_many("Par", rows, parallel=True)
        assert new_documents == []
        assert _stored(db, "Par") == _stored(db, "Ref")


def test_parallel_insert_many_sends_only_the_uncarriable_row_per_row(
    temp_db_path, new_documents
):
    rows = [{"id": i, "ts": dt.datetime(2026, 1, 1)} for i in range(500)]
    rows[250]["v"] = float("nan")
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Par", False)
        db.insert_many("Par", rows, parallel=True)
        assert new_documents == ["Par"]
        assert db.count_type("Par") == 500


def test_a_user_dict_that_looks_like_a_tag_is_not_decoded(temp_db_path):
    """The bulk JSON marks a date-time or a Decimal as {"\\u0001": [kind, payload]}; a user's own map with that key stays a map."""
    lookalike = {"\u0001": ["T", "2026-01-01T00:00:00"]}
    rows = [{"id": 0, "m": lookalike, "ts": dt.datetime(2026, 1, 1)}]
    with arcadedb.create_database(temp_db_path) as db:
        _create(db, "Ref", False)
        _create(db, "Bulk", False)
        _per_row(db, "Ref", rows)
        db.insert_many("Bulk", rows)
        assert _stored(db, "Bulk") == _stored(db, "Ref")
