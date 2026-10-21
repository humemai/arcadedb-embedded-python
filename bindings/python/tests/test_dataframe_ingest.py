"""Tests for Database.insert_dataframe, Database.insert_arrow and ResultSet.to_polars (bindings issue #387).

A pandas or Polars DataFrame, or an Arrow table, loads into a document or vertex type in batches. These tests
hold what a user relies on: each Arrow type stores as the documented ArcadeDB type and reads back equal, nulls
are missing properties, a declared property converts (or the load is refused before a row is written), a frame
larger than one batch loads whole, and a result set goes back out as a Polars frame.
"""

import datetime as dt
import decimal
import sys

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pa = pytest.importorskip("pyarrow")
pl = pytest.importorskip("polars")

from arcadedb_embedded.exceptions import ArcadeDBError  # noqa: E402


def _rows(db, sql):
    return db.query("sql", sql).to_list()


def _count(db, type_name, where=""):
    q = f"SELECT count(*) AS n FROM {type_name} {where}"  # nosec B608 - test-controlled
    return int(_rows(db, q)[0]["n"])


def _one_column(db, arrow_type, values, declared=None):
    """Load ``values`` as one column ``val`` of ``arrow_type`` and return what reads back, in row order."""
    db.command("sql", "CREATE DOCUMENT TYPE One")
    if declared:
        db.command("sql", f"CREATE PROPERTY One.val {declared}")
    table = pa.table(
        {
            "idx": pa.array(range(len(values)), pa.int64()),
            "val": pa.array(values, arrow_type),
        }
    )
    assert db.insert_arrow("One", table) == len(values)
    return [r.get("val") for r in _rows(db, "SELECT FROM One ORDER BY idx")]


class TestTypeMapping:
    """Every Arrow type of the documented table, with no declared property: write, read back, compare."""

    @pytest.mark.parametrize(
        "arrow_type",
        [
            pa.int8(),
            pa.int16(),
            pa.int32(),
            pa.int64(),
            pa.uint8(),
            pa.uint16(),
            pa.uint32(),
        ],
    )
    def test_integers_store_as_long(self, temp_db, arrow_type):
        got = _one_column(temp_db, arrow_type, [0, 1, 100])
        assert got == [0, 1, 100] and all(type(v) is int for v in got)

    def test_signed_integer_extremes(self, temp_db):
        values = [-(2**63), -1, 2**63 - 1]
        assert _one_column(temp_db, pa.int64(), values) == values

    @pytest.mark.parametrize("arrow_type", [pa.float32(), pa.float64(), pa.float16()])
    def test_floats_store_as_double(self, temp_db, arrow_type):
        # 0.5, -2.25 and 1024.0 are exact in every width, so the read-back is equal and not approximate
        values = [0.5, -2.25, 1024.0]
        got = _one_column(
            temp_db, arrow_type, np.array(values, dtype=arrow_type.to_pandas_dtype())
        )
        assert got == values and all(type(v) is float for v in got)

    def test_bool(self, temp_db):
        assert _one_column(temp_db, pa.bool_(), [True, False, True]) == [
            True,
            False,
            True,
        ]

    @pytest.mark.parametrize("arrow_type", [pa.string(), pa.large_string()])
    def test_string(self, temp_db, arrow_type):
        values = ["a", "", "naïve ✓"]
        assert _one_column(temp_db, arrow_type, values) == values

    def test_dictionary_column_stores_its_values(self, temp_db):
        # a pandas categorical and a Polars Categorical both arrive as an Arrow dictionary
        temp_db.command("sql", "CREATE DOCUMENT TYPE Cat")
        df = pd.DataFrame({"c": pd.Categorical(["x", "y", "x"])})
        assert temp_db.insert_dataframe("Cat", df) == 3
        assert sorted(r["c"] for r in _rows(temp_db, "SELECT FROM Cat")) == [
            "x",
            "x",
            "y",
        ]

    def test_timestamp_without_zone_keeps_the_wall_clock(self, temp_db):
        values = [
            dt.datetime(2020, 1, 2, 3, 4, 5, 123000),
            dt.datetime(1969, 12, 31, 23, 59, 59, 500000),
        ]
        for unit in ("s", "ms", "us", "ns"):
            temp_db.command("sql", "DROP TYPE One IF EXISTS UNSAFE")
            expected = (
                [v.replace(microsecond=0) for v in values] if unit == "s" else values
            )
            assert _one_column(temp_db, pa.timestamp(unit), expected) == expected

    def test_timestamp_with_zone_is_stored_as_utc(self, temp_db):
        local = dt.datetime(
            2020, 1, 2, 3, 4, 5, 123000, tzinfo=dt.timezone(dt.timedelta(hours=5))
        )
        got = _one_column(temp_db, pa.timestamp("us", tz="Asia/Karachi"), [local])
        assert got == [
            dt.datetime(2020, 1, 1, 22, 4, 5, 123000)
        ]  # UTC wall clock, naive on the way out

    def test_date(self, temp_db):
        values = [dt.date(2020, 2, 29), dt.date(1960, 1, 1)]
        assert _one_column(temp_db, pa.date32(), values) == values

    def test_date64(self, temp_db):
        values = [dt.date(2020, 2, 29)]
        assert _one_column(temp_db, pa.date64(), values) == values

    def test_decimal_keeps_every_digit(self, temp_db):
        values = [
            decimal.Decimal("12345678901234567890.123456"),
            decimal.Decimal("-0.000001"),
        ]
        assert _one_column(temp_db, pa.decimal128(38, 6), values) == values

    def test_list_columns(self, temp_db):
        assert _one_column(temp_db, pa.list_(pa.int64()), [[1, 2, 3], [], [4]]) == [
            [1, 2, 3],
            [],
            [4],
        ]

    def test_fixed_size_list_of_floats(self, temp_db):
        values = [[0.5, 1.5], [2.5, 3.5]]
        assert _one_column(temp_db, pa.list_(pa.float32(), 2), values) == values

    def test_list_of_strings_and_large_list(self, temp_db):
        values = [["a", "b"], ["c"]]
        assert _one_column(temp_db, pa.large_list(pa.string()), values) == values

    def test_struct_stores_as_a_map(self, temp_db):
        values = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        assert (
            _one_column(
                temp_db, pa.struct([("a", pa.int64()), ("b", pa.string())]), values
            )
            == values
        )

    def test_binary(self, temp_db):
        got = _one_column(temp_db, pa.binary(), [b"\x00\x01\xff"])
        assert [b & 0xFF for b in got[0]] == [
            0,
            1,
            255,
        ]  # a byte[] reads back as signed ints

    def test_all_null_column_stores_no_value(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Nothing")
        table = pa.table({"id": [1, 2], "gone": pa.nulls(2)})
        assert temp_db.insert_arrow("Nothing", table) == 2
        assert all(r.get("gone") is None for r in _rows(temp_db, "SELECT FROM Nothing"))

    def test_uint64_past_the_signed_range_is_refused(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Big")
        table = pa.table({"v": pa.array([2**63], pa.uint64())})
        with pytest.raises(ValueError):
            temp_db.insert_arrow("Big", table)
        assert _count(temp_db, "Big") == 0


class TestPrecision:
    def test_declared_precisions(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Prec")
        for name, decl in (
            ("sec", "DATETIME_SECOND"),
            ("ms", "DATETIME"),
            ("us", "DATETIME_MICROS"),
            ("ns", "DATETIME_NANOS"),
        ):
            temp_db.command("sql", f"CREATE PROPERTY Prec.{name} {decl}")
        # 2020-01-02 03:04:05.123456789 as nanoseconds since the epoch
        ns = 1_577_934_245_123_456_789
        table = pa.table(
            {n: pa.array([ns], pa.timestamp("ns")) for n in ("sec", "ms", "us", "ns")}
        )
        assert temp_db.insert_arrow("Prec", table) == 1
        row = _rows(temp_db, "SELECT FROM Prec")[0]
        assert row["sec"] == dt.datetime(2020, 1, 2, 3, 4, 5)
        assert row["ms"] == dt.datetime(2020, 1, 2, 3, 4, 5, 123000)
        # a Python datetime holds microseconds, so the nanosecond column reads back to the microsecond
        assert row["us"] == dt.datetime(2020, 1, 2, 3, 4, 5, 123456)
        assert row["ns"] == dt.datetime(2020, 1, 2, 3, 4, 5, 123456)

    def test_dates_before_the_epoch(self, temp_db):
        values = [
            dt.datetime(1900, 1, 1, 0, 0, 1),
            dt.datetime(1969, 12, 31, 23, 59, 59, 999000),
        ]
        assert _one_column(temp_db, pa.timestamp("ms"), values) == values


class TestNulls:
    def test_every_kind_stores_nulls_as_missing(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Nul")
        table = pa.table(
            {
                "i": pa.array([1, None, 3], pa.int64()),
                "f": pa.array([1.5, None, 3.5], pa.float64()),
                "b": pa.array([True, None, False], pa.bool_()),
                "s": pa.array(["a", None, "c"], pa.string()),
                "t": pa.array(
                    [dt.datetime(2020, 1, 1), None, dt.datetime(2021, 1, 1)],
                    pa.timestamp("us"),
                ),
                "d": pa.array(
                    [dt.date(2020, 1, 1), None, dt.date(2021, 1, 1)], pa.date32()
                ),
                "n": pa.array(
                    [decimal.Decimal("1.5"), None, decimal.Decimal("2.5")],
                    pa.decimal128(10, 1),
                ),
                "l": pa.array([[1], None, [3]], pa.list_(pa.int64())),
            }
        )
        table = table.append_column("k", pa.array([0, 1, 2], pa.int64()))
        assert temp_db.insert_arrow("Nul", table) == 3
        middle = _rows(temp_db, "SELECT FROM Nul WHERE k = 1")[0]
        assert [middle.get(c) for c in "ifbstdnl"] == [None] * 8
        first = _rows(temp_db, "SELECT FROM Nul WHERE k = 0")[0]
        assert (
            first["i"] == 1
            and first["f"] == 1.5
            and first["b"] is True
            and first["s"] == "a"
        )
        assert first["t"] == dt.datetime(2020, 1, 1) and first["d"] == dt.date(
            2020, 1, 1
        )
        assert first["n"] == decimal.Decimal("1.5") and first["l"] == [1]

    def test_pandas_nullable_integer_keeps_its_values(self, temp_db):
        # a float64 with NaN would lose the precision past 2**53; Int64 with <NA> must not
        temp_db.command("sql", "CREATE DOCUMENT TYPE Nullable")
        big = 2**60 + 1
        df = pd.DataFrame({"k": [0, 1], "v": pd.array([big, None], dtype="Int64")})
        assert temp_db.insert_dataframe("Nullable", df) == 2
        rows = {r["k"]: r.get("v") for r in _rows(temp_db, "SELECT FROM Nullable")}
        assert rows == {0: big, 1: None}

    def test_pandas_nan_is_a_null_and_polars_nan_stays_nan(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE FromPandas")
        temp_db.command("sql", "CREATE DOCUMENT TYPE FromPolars")
        temp_db.insert_dataframe(
            "FromPandas", pd.DataFrame({"k": [0, 1], "x": [1.5, float("nan")]})
        )
        temp_db.insert_dataframe(
            "FromPolars", pl.DataFrame({"k": [0, 1], "x": [1.5, float("nan")]})
        )
        pandas_row = _rows(temp_db, "SELECT FROM FromPandas WHERE k = 1")[0]
        polars_row = _rows(temp_db, "SELECT FROM FromPolars WHERE k = 1")[0]
        assert pandas_row.get("x") is None
        assert polars_row["x"] != polars_row["x"]  # NaN


class TestDeclaredTypes:
    def test_values_convert_to_the_declared_type(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Decl")
        for prop, decl in (
            ("small", "INTEGER"),
            ("short", "SHORT"),
            ("as_double", "DOUBLE"),
            ("as_decimal", "DECIMAL"),
            ("as_text", "STRING"),
            ("vec", "ARRAY_OF_FLOATS"),
            ("born", "DATE"),
            ("seen", "DATETIME_MICROS"),
        ):
            temp_db.command("sql", f"CREATE PROPERTY Decl.{prop} {decl}")
        df = pd.DataFrame(
            {
                "small": np.array([1, 2], dtype=np.int64),
                "short": np.array([3, 4], dtype=np.int8),
                "as_double": np.array([5, 6], dtype=np.int32),
                "as_decimal": pd.array(
                    [decimal.Decimal("1.25"), decimal.Decimal("2.5")],
                    dtype=pd.ArrowDtype(pa.decimal128(5, 2)),
                ),
                "as_text": np.array([7, 8], dtype=np.int64),
                "vec": [[0.5, 1.5], [2.5, 3.5]],
                "born": [dt.date(2020, 1, 1), dt.date(2021, 1, 1)],
                "seen": pd.to_datetime(
                    ["2020-01-01 00:00:00.000001", "2020-01-02 00:00:00.000000"]
                ),
            }
        )
        assert temp_db.insert_dataframe("Decl", df) == 2
        row = _rows(temp_db, "SELECT FROM Decl WHERE small = 1")[0]
        assert row["small"] == 1 and row["short"] == 3
        assert row["as_double"] == 5.0 and type(row["as_double"]) is float
        assert row["as_decimal"] == decimal.Decimal("1.25")
        assert row["as_text"] == "7"
        assert list(row["vec"]) == [0.5, 1.5]
        assert row["born"] == dt.date(2020, 1, 1)
        assert row["seen"] == dt.datetime(2020, 1, 1, 0, 0, 0, 1)

    def test_a_value_past_the_declared_range_fails_and_rolls_back(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Range")
        temp_db.command("sql", "CREATE PROPERTY Range.v INTEGER")
        with pytest.raises(ArcadeDBError):
            temp_db.insert_arrow(
                "Range", pa.table({"v": pa.array([1, 2**40], pa.int64())})
            )
        assert _count(temp_db, "Range") == 0

    @pytest.mark.parametrize(
        "declared, column",
        [
            ("INTEGER", pa.array([1.5], pa.float64())),  # would truncate to 1
            ("LONG", pa.array(["12"], pa.string())),  # would be parsed
            (
                "DATE",
                pa.array([dt.datetime(2020, 1, 1, 12)], pa.timestamp("us")),
            ),  # would lose the time
            ("BOOLEAN", pa.array([1], pa.int64())),
            ("STRING", pa.array([[1]], pa.list_(pa.int64()))),
            ("DOUBLE", pa.array([dt.date(2020, 1, 1)], pa.date32())),
        ],
    )
    def test_a_kind_that_would_lose_or_guess_is_refused_before_a_row_is_written(
        self, temp_db, declared, column
    ):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Refuse")
        temp_db.command("sql", f"CREATE PROPERTY Refuse.v {declared}")
        with pytest.raises(TypeError, match=f"Refuse.v. is declared {declared}"):
            temp_db.insert_arrow(
                "Refuse", pa.table({"ok": pa.array([0] * len(column)), "v": column})
            )
        assert _count(temp_db, "Refuse") == 0

    def test_declared_property_of_a_parent_type_applies(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Parent")
        temp_db.command("sql", "CREATE PROPERTY Parent.v INTEGER")
        temp_db.command("sql", "CREATE DOCUMENT TYPE Child EXTENDS Parent")
        with pytest.raises(TypeError, match="declared INTEGER"):
            temp_db.insert_arrow("Child", pa.table({"v": [1.5]}))

    def test_an_undeclared_column_next_to_declared_ones_is_stored_as_it_is(
        self, temp_db
    ):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Mixed")
        temp_db.command("sql", "CREATE PROPERTY Mixed.a INTEGER")
        assert (
            temp_db.insert_dataframe("Mixed", pd.DataFrame({"a": [1], "b": [2.5]})) == 1
        )
        row = _rows(temp_db, "SELECT FROM Mixed")[0]
        assert row["a"] == 1 and row["b"] == 2.5


class TestInputsAndErrors:
    def test_pandas_polars_and_arrow_inputs_store_the_same_records(self, temp_db):
        data = {
            "id": [1, 2, 3],
            "name": ["a", "b", "c"],
            "score": [0.5, 1.5, 2.5],
            "ok": [True, False, True],
        }
        sources = {
            "FromPandas": pd.DataFrame(data),
            "FromPolars": pl.DataFrame(data),
            "FromTable": pa.table(data),
            "FromBatch": pa.RecordBatch.from_pydict(data),
            "FromReader": pa.RecordBatchReader.from_batches(
                pa.table(data).schema, pa.table(data).to_batches()
            ),
        }
        stored = {}
        for name, source in sources.items():
            temp_db.command("sql", f"CREATE DOCUMENT TYPE {name}")
            method = (
                temp_db.insert_dataframe
                if name in ("FromPandas", "FromPolars")
                else temp_db.insert_arrow
            )
            assert method(name, source) == 3
            sql = f"SELECT FROM {name} ORDER BY id"  # nosec B608 - test-controlled
            stored[name] = [
                {k: v for k, v in r.items() if not k.startswith("@")}
                for r in _rows(temp_db, sql)
            ]
        assert all(rows == stored["FromTable"] for rows in stored.values())
        assert stored["FromTable"][0] == {
            "id": 1,
            "name": "a",
            "score": 0.5,
            "ok": True,
        }

    def test_insert_dataframe_takes_an_arrow_capsule_object(self, temp_db):
        class Wrapper:  # a library that speaks the Arrow PyCapsule interface, and nothing else
            def __init__(self, table):
                self._table = table

            def __arrow_c_stream__(self, requested_schema=None):
                return self._table.__arrow_c_stream__(requested_schema)

        temp_db.command("sql", "CREATE DOCUMENT TYPE Capsule")
        assert (
            temp_db.insert_dataframe("Capsule", Wrapper(pa.table({"id": [1, 2]}))) == 2
        )

    def test_pandas_index_is_not_loaded(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Indexed")
        df = pd.DataFrame({"v": [1, 2]}, index=["x", "y"])
        temp_db.insert_dataframe("Indexed", df)
        assert set(_rows(temp_db, "SELECT FROM Indexed")[0]) - {
            "@rid",
            "@type",
            "@cat",
        } == {"v"}
        temp_db.insert_dataframe("Indexed", df.rename_axis("name").reset_index())
        assert _count(temp_db, "Indexed", "WHERE name = 'y'") == 1

    def test_empty_frame_writes_nothing(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Empty")
        assert (
            temp_db.insert_dataframe(
                "Empty", pd.DataFrame({"a": pd.Series([], dtype="int64")})
            )
            == 0
        )
        assert _count(temp_db, "Empty") == 0

    def test_missing_type_and_edge_type_are_refused(self, temp_db):
        temp_db.command("sql", "CREATE EDGE TYPE Link")
        with pytest.raises(ArcadeDBError, match="does not exist"):
            temp_db.insert_dataframe("Nope", pd.DataFrame({"a": [1]}))
        with pytest.raises(ArcadeDBError, match="edge type"):
            temp_db.insert_dataframe("Link", pd.DataFrame({"a": [1]}))

    def test_bad_frames_are_refused_before_anything_is_written(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Bad")
        with pytest.raises(ValueError, match="at least one column"):
            temp_db.insert_dataframe("Bad", pd.DataFrame())
        with pytest.raises(ValueError, match="strings"):
            temp_db.insert_dataframe("Bad", pd.DataFrame({0: [1]}))
        with pytest.raises(ValueError, match="duplicate"):
            temp_db.insert_dataframe("Bad", pd.DataFrame([[1, 2]], columns=["a", "a"]))
        with pytest.raises(TypeError, match="LazyFrame"):
            temp_db.insert_dataframe("Bad", pl.DataFrame({"a": [1]}).lazy())
        with pytest.raises(TypeError, match="DataFrame"):
            temp_db.insert_dataframe("Bad", {"a": [1]})
        with pytest.raises(TypeError, match="no ArcadeDB mapping"):
            temp_db.insert_arrow("Bad", pa.table({"t": pa.array([1], pa.time64("us"))}))
        with pytest.raises(TypeError, match="no ArcadeDB mapping"):
            temp_db.insert_arrow(
                "Bad", pa.table({"d": pa.array([1], pa.duration("s"))})
            )
        with pytest.raises(TypeError, match="no ArcadeDB mapping"):
            temp_db.insert_arrow(
                "Bad",
                pa.table(
                    {"m": pa.array([[("k", 1)]], pa.map_(pa.string(), pa.int64()))}
                ),
            )
        for size in (0, -1, 1.5, True):
            with pytest.raises(ValueError, match="batch_size"):
                temp_db.insert_dataframe(
                    "Bad", pd.DataFrame({"a": [1]}), batch_size=size
                )
        assert _count(temp_db, "Bad") == 0

    def test_missing_pyarrow_is_an_import_error_with_the_fix(
        self, temp_db, monkeypatch
    ):
        temp_db.command("sql", "CREATE DOCUMENT TYPE NoArrow")
        monkeypatch.setitem(sys.modules, "pyarrow", None)
        with pytest.raises(ImportError, match=r"pip install pyarrow"):
            temp_db.insert_dataframe("NoArrow", pd.DataFrame({"a": [1]}))

    def test_closed_database_is_refused(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Closed")
        temp_db.close()
        with pytest.raises(ArcadeDBError):
            temp_db.insert_dataframe("Closed", pd.DataFrame({"a": [1]}))


class TestBatching:
    def test_a_frame_of_100k_rows_loads_whole(self, temp_db):
        n = 100_000
        temp_db.command("sql", "CREATE DOCUMENT TYPE Big")
        temp_db.command("sql", "CREATE PROPERTY Big.id LONG")
        ids = np.arange(n, dtype=np.int64)
        df = pd.DataFrame(
            {
                "id": ids,
                "price": ids * 0.25,
                "label": [f"row_{i}" for i in range(n)],
                "flag": ids % 3 == 0,
                "ts": pd.Timestamp("2020-01-01") + pd.to_timedelta(ids, unit="s"),
            }
        )
        assert temp_db.insert_dataframe("Big", df) == n
        assert _count(temp_db, "Big") == n
        total = _rows(
            temp_db, "SELECT sum(id) AS s, count(DISTINCT label) AS d FROM Big"
        )[0]
        assert total["s"] == int(ids.sum()) and total["d"] == n
        last_sql = f"SELECT FROM Big WHERE id = {n - 1}"  # nosec B608 - test-controlled
        last = _rows(temp_db, last_sql)[0]
        assert last["ts"] == dt.datetime(2020, 1, 1) + dt.timedelta(seconds=n - 1)

    @pytest.mark.parametrize("batch_size", [1, 7, 10, 25])
    def test_a_batch_size_that_does_not_divide_the_rows(self, temp_db, batch_size):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Odd")
        assert (
            temp_db.insert_dataframe(
                "Odd", pd.DataFrame({"id": range(23)}), batch_size=batch_size
            )
            == 23
        )
        assert _count(temp_db, "Odd") == 23

    def test_a_table_of_many_chunks_loads_every_chunk(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Chunks")
        table = pa.concat_tables(
            [pa.table({"id": list(range(i * 5, i * 5 + 5))}) for i in range(4)]
        )
        assert temp_db.insert_arrow("Chunks", table, batch_size=8) == 20
        assert _count(temp_db, "Chunks") == 20

    def test_a_failure_rolls_back_its_batch_and_says_what_was_committed(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Dup")
        temp_db.command("sql", "CREATE PROPERTY Dup.id LONG")
        temp_db.command("sql", "CREATE INDEX ON Dup (id) UNIQUE")
        ids = list(range(10)) + [3]  # the 11th row repeats id 3, in the second batch
        with pytest.raises(ArcadeDBError, match=r"10 row\(s\) of the batches before"):
            temp_db.insert_dataframe("Dup", pd.DataFrame({"id": ids}), batch_size=10)
        assert _count(temp_db, "Dup") == 10

    def test_the_failure_message_tells_committed_from_written_in_your_transaction(
        self, temp_db
    ):
        """Outside a transaction the earlier batches are committed; inside the caller's own they
        joined it, so the message must not claim they are committed (a rollback removes them).
        """
        temp_db.command("sql", "CREATE DOCUMENT TYPE Dup2")
        temp_db.command("sql", "CREATE PROPERTY Dup2.id LONG")
        temp_db.command("sql", "CREATE INDEX ON Dup2 (id) UNIQUE")
        frame = pd.DataFrame({"id": list(range(10)) + [3]})  # the 11th row repeats id 3

        with pytest.raises(ArcadeDBError) as outside:
            temp_db.insert_dataframe("Dup2", frame, batch_size=10)
        assert "10 row(s) of the batches before this one were committed" in str(
            outside.value
        )
        assert _count(temp_db, "Dup2") == 10
        with temp_db.transaction():
            temp_db.command("sql", "DELETE FROM Dup2")

        temp_db.begin()
        try:
            with pytest.raises(ArcadeDBError) as inside:
                temp_db.insert_dataframe("Dup2", frame, batch_size=10)
        finally:
            temp_db.rollback()
        assert "10 row(s) of the batches before this one were written in your" in str(
            inside.value
        )
        assert "not committed" in str(inside.value)
        assert "were committed" not in str(inside.value)
        assert _count(temp_db, "Dup2") == 0  # the caller's rollback removed them

    def test_a_callers_transaction_is_left_to_the_caller(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Mine")
        with pytest.raises(RuntimeError, match="stop"):
            with temp_db.transaction():
                temp_db.insert_dataframe(
                    "Mine", pd.DataFrame({"id": [1, 2, 3]}), batch_size=2
                )
                raise RuntimeError("stop")
        assert _count(temp_db, "Mine") == 0

    def test_parallel_documents(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Par")
        assert (
            temp_db.insert_dataframe(
                "Par", pd.DataFrame({"id": range(1000)}), batch_size=300, parallel=True
            )
            == 1000
        )
        assert _count(temp_db, "Par") == 1000


class TestVertices:
    def test_a_vertex_type_gets_vertices(self, temp_db):
        temp_db.command("sql", "CREATE VERTEX TYPE Person")
        temp_db.command("sql", "CREATE PROPERTY Person.id LONG")
        df = pd.DataFrame(
            {
                "id": np.arange(25, dtype=np.int64),
                "name": [f"p{i}" for i in range(25)],
                "born": pd.to_datetime(["2000-01-01"] * 25),
                "score": [None if i % 5 == 0 else i * 0.5 for i in range(25)],
            }
        )
        assert temp_db.insert_dataframe("Person", df, batch_size=10) == 25
        assert _count(temp_db, "Person") == 25
        row = _rows(temp_db, "SELECT FROM Person WHERE id = 7")[0]
        assert (
            row["name"] == "p7"
            and row["born"] == dt.datetime(2000, 1, 1)
            and row["score"] == 3.5
        )
        assert (
            _rows(temp_db, "SELECT outE().size() AS e FROM Person WHERE id = 7")[0]["e"]
            == 0
        )  # a vertex
        assert _rows(temp_db, "SELECT FROM Person WHERE id = 5")[0].get("score") is None

    def test_vertices_from_polars_and_edges_between_them(self, temp_db):
        temp_db.command("sql", "CREATE VERTEX TYPE City")
        temp_db.command("sql", "CREATE EDGE TYPE Road")
        assert temp_db.insert_dataframe("City", pl.DataFrame({"name": ["a", "b"]})) == 2
        a, b = (
            r["rid"]
            for r in _rows(temp_db, "SELECT @rid AS rid FROM City ORDER BY name")
        )
        with temp_db.graph_batch() as batch:
            batch.new_edges([str(a)], "Road", [str(b)])
        assert _count(temp_db, "Road") == 1

    def test_declared_types_apply_to_vertices_too(self, temp_db):
        temp_db.command("sql", "CREATE VERTEX TYPE Typed")
        temp_db.command("sql", "CREATE PROPERTY Typed.v INTEGER")
        with pytest.raises(TypeError, match="declared INTEGER"):
            temp_db.insert_dataframe("Typed", pd.DataFrame({"v": [1.5]}))

    def test_parallel_is_for_documents_only(self, temp_db):
        temp_db.command("sql", "CREATE VERTEX TYPE Pv")
        with pytest.raises(ValueError, match="vertex type"):
            temp_db.insert_dataframe("Pv", pd.DataFrame({"a": [1]}), parallel=True)


class TestToPolars:
    def test_round_trip_through_polars(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Trip")
        frame = pl.DataFrame(
            {
                "id": pl.Series([1, 2, 3], dtype=pl.Int64),
                "score": [0.5, None, 2.5],
                "name": ["a", None, "c"],
                "ok": [True, False, None],
                "at": pl.Series(
                    [
                        dt.datetime(2020, 1, 1),
                        None,
                        dt.datetime(2020, 1, 3, 4, 5, 6, 789000),
                    ]
                ).cast(pl.Datetime("ms")),
                "amount": pl.Series(
                    [decimal.Decimal("1.5"), None, decimal.Decimal("3.25")],
                    dtype=pl.Decimal(10, 2),
                ),
            }
        )
        assert temp_db.insert_dataframe("Trip", frame) == 3
        back = temp_db.query(
            "sql", "SELECT id, score, name, ok, at, amount FROM Trip ORDER BY id"
        ).to_polars()
        assert isinstance(back, pl.DataFrame)
        assert back.schema["id"] == pl.Int64 and back.schema["name"] == pl.String
        assert back.schema["score"] == pl.Float64 and back.schema["ok"] == pl.Boolean
        assert back.schema["at"] == pl.Datetime("ms")
        assert (
            back.get_column("amount").to_list() == frame.get_column("amount").to_list()
        )
        assert back.drop("amount").equals(
            frame.drop("amount").cast({"at": pl.Datetime("ms")})
        )

    def test_matches_to_arrow(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Same")
        temp_db.insert_dataframe("Same", pd.DataFrame({"id": [1, 2], "v": [0.5, 1.5]}))
        sql = "SELECT id, v FROM Same ORDER BY id"
        assert (
            temp_db.query("sql", sql).to_polars().to_dicts()
            == pl.from_arrow(temp_db.query("sql", sql).to_arrow()).to_dicts()
        )

    def test_columns_and_batch_size_pass_through(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Pass")
        temp_db.insert_dataframe(
            "Pass", pd.DataFrame({"id": range(10), "v": range(10)})
        )
        frame = temp_db.query("sql", "SELECT id, v FROM Pass ORDER BY id").to_polars(
            batch_size=3, columns=["id"]
        )
        assert frame.columns == ["id"] and frame.get_column("id").to_list() == list(
            range(10)
        )

    def test_missing_polars_is_an_import_error_with_the_fix(self, temp_db, monkeypatch):
        temp_db.command("sql", "CREATE DOCUMENT TYPE NoPolars")
        monkeypatch.setitem(sys.modules, "polars", None)
        with pytest.raises(
            ImportError,
            match=r"polars is required for to_polars\(\).*arcadedb-embedded\[polars\]",
        ):
            temp_db.query("sql", "SELECT FROM NoPolars").to_polars()

    def test_missing_pyarrow_is_an_import_error_with_the_fix(
        self, temp_db, monkeypatch
    ):
        temp_db.command("sql", "CREATE DOCUMENT TYPE NoArrow2")
        temp_db.insert_dataframe("NoArrow2", pd.DataFrame({"a": [1]}))
        monkeypatch.setitem(sys.modules, "pyarrow", None)
        with pytest.raises(ImportError, match="needs pyarrow"):
            temp_db.query("sql", "SELECT FROM NoArrow2").to_polars()
