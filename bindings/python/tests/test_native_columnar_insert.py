"""The native backend's columnar bulk insert stores what the JSON path stores (``arcadedb_n_insert_colp`` against ``arcadedb_n_insert_rows``).

Needs the native library, so conftest.py collects this file on the native backend only (a skip elsewhere would fail
scripts/check_test_skips.py). Each test loads the same data through the JSON path (``bulk._ENABLED`` off) and through the columnar entry and
compares the stored records value by value and type by type; a spy on the crossing proves which entry point ran, so a silent fall back
to JSON cannot pass for the columnar path.
"""

import ctypes
import datetime
import math

import pytest

np = pytest.importorskip("numpy")

from arcadedb_embedded._native import bulk, columnar, lib  # noqa: E402
from arcadedb_embedded.exceptions import ArcadeDBError  # noqa: E402

COLP, ROWS, MANY = (
    "arcadedb_n_insert_colp",
    "arcadedb_n_insert_rows",
    "arcadedb_n_exec_many",
)


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


@pytest.fixture
def spy(monkeypatch):
    return Spy(monkeypatch)


def _types(db, *names, extra="", unique=False):
    for name in names:
        db.command("sql", f"CREATE DOCUMENT TYPE {name}")
        db.command("sql", f"CREATE PROPERTY {name}.id INTEGER")
        db.command("sql", f"CREATE PROPERTY {name}.grp INTEGER")
        db.command("sql", f"CREATE PROPERTY {name}.val DOUBLE")
        db.command("sql", f"CREATE PROPERTY {name}.cat STRING")
        db.command("sql", f"CREATE PROPERTY {name}.txt STRING")
        db.command("sql", f"CREATE PROPERTY {name}.vec ARRAY_OF_FLOATS")
        if unique:
            db.command("sql", f"CREATE INDEX ON {name} (id) UNIQUE")


def _stored(db, name):
    """Every record of a type as (value, python type) pairs per property, ordered by id."""
    out = []
    for row in db.query("sql", f"SELECT FROM {name} ORDER BY id").to_list():
        out.append(
            {k: (v, type(v).__name__) for k, v in row.items() if not k.startswith("@")}
        )
    return out


def _probe(n, dim=8, seed=7):
    """The probe workload's column types: INTEGER ids, a DOUBLE, a 20-value category, a variable-length text, a float32 vector."""
    rng = np.random.default_rng(seed)
    ids = np.arange(n, dtype=np.int64)
    return {
        "id": ids,
        "grp": ids % 1000,
        "val": (ids * 37 % 10007) / 7.0,
        "cat": ["c%d" % (k % 20) for k in range(n)],
        "txt": ["row-%d-%s" % (k, "x" * (k % 24)) for k in range(n)],
        "vec": rng.standard_normal((n, dim), dtype=np.float32),
    }


def _rows(columns):
    names = list(columns)
    lists = [c.tolist() if hasattr(c, "tolist") else c for c in columns.values()]
    return [dict(zip(names, vals)) for vals in zip(*lists)]


def _json_reference(db, name, rows, monkeypatch, **kw):
    with monkeypatch.context() as m:
        m.setattr(bulk, "_ENABLED", False)
        db.insert_many(name, rows, **kw)


def test_probe_workload_columns_store_the_same_records_on_every_columnar_entry(
    temp_db, spy, monkeypatch
):
    _types(temp_db, "Ref", "ByRows", "ByCols", "ByFrame", "ByTable")
    columns = _probe(2_500)
    rows = _rows(columns)
    _json_reference(temp_db, "Ref", rows, monkeypatch)
    assert spy.count(COLP) == 0 and spy.count(ROWS) == 1

    spy.calls.clear()
    temp_db.insert_many("ByRows", rows)  # dict rows, transposed to columns
    assert spy.count(COLP) == 1 and spy.count(ROWS) == 0
    temp_db.insert_columns("ByCols", columns)  # numpy columns and lists of str
    assert spy.count(COLP) == 2 and spy.count(ROWS) == 0

    pd = pytest.importorskip("pandas")
    pa = pytest.importorskip("pyarrow")
    frame = pd.DataFrame(
        {
            **{k: v for k, v in columns.items() if k != "vec"},
            "vec": list(columns["vec"]),
        }
    )
    temp_db.insert_dataframe("ByFrame", frame)
    temp_db.insert_arrow("ByTable", pa.table({k: v for k, v in frame.items()}))
    assert spy.count(COLP) == 4 and spy.count(ROWS) == 0 and spy.count(MANY) == 0

    expected = _stored(temp_db, "Ref")
    assert len(expected) == 2_500
    assert expected[7]["id"][1] == "int" and expected[7]["vec"][1] == "list"
    for name in ("ByRows", "ByCols", "ByFrame", "ByTable"):
        assert _stored(temp_db, name) == expected, name


def test_unicode_empty_and_awkward_strings_survive_the_columnar_path(
    temp_db, spy, monkeypatch
):
    _types(temp_db, "Ref", "Col")
    texts = [
        "",
        "plain",
        "héllo wörld",
        "日本語のテキスト",
        "한국어",
        "😀 emoji, outside the BMP",
        'tab\tnewline\nquote" backslash\\',
        "embedded\x00nul",
        "x" * 70_000,  # larger than the text scratch of the JSON path
        "é́ composed and decomposed",
    ]
    n = len(texts)
    columns = {
        "id": np.arange(n),
        "grp": np.zeros(n, dtype=np.int64),
        "txt": texts,
        "cat": list(reversed(texts)),
    }
    _json_reference(temp_db, "Ref", _rows(columns), monkeypatch)
    temp_db.insert_columns("Col", columns)
    assert spy.count(COLP) == 1
    assert _stored(temp_db, "Col") == _stored(temp_db, "Ref")
    assert [
        r["txt"]
        for r in temp_db.query("sql", "SELECT txt FROM Col ORDER BY id").to_list()
    ] == texts


def test_nulls_are_stored_as_the_json_path_stores_them(temp_db, spy, monkeypatch):
    _types(temp_db, "Ref", "Col", "ByFrame")
    n = 40
    columns = {
        "id": np.arange(n),
        "grp": [None if i % 3 == 0 else i for i in range(n)],
        "val": [None if i % 4 == 0 else i / 4 for i in range(n)],
        "cat": [None if i % 5 == 0 else "c%d" % i for i in range(n)],
        "txt": [None] * n,
    }
    _json_reference(temp_db, "Ref", _rows(columns), monkeypatch)
    temp_db.insert_columns("Col", columns)
    assert spy.count(COLP) == 1
    expected = _stored(temp_db, "Ref")
    assert _stored(temp_db, "Col") == expected
    assert expected[0]["grp"][0] is None and expected[1]["grp"][0] == 1

    pd = pytest.importorskip("pandas")
    spy.calls.clear()
    frame = pd.DataFrame(
        {
            "id": np.arange(n),
            "grp": pd.array(columns["grp"], dtype="Int64"),
            "val": pd.array(columns["val"], dtype="Float64"),
            "cat": pd.array(columns["cat"], dtype="string"),
            "txt": pd.array(columns["txt"], dtype="string"),
        }
    )
    temp_db.insert_dataframe("ByFrame", frame)
    assert spy.count(COLP) == 1 and spy.count(ROWS) == 0
    assert _stored(temp_db, "ByFrame") == expected


def test_int64_edges_nan_and_infinity(temp_db, spy, monkeypatch):
    for name in ("Ref", "Col"):
        temp_db.command("sql", f"CREATE DOCUMENT TYPE {name}")
        temp_db.command("sql", f"CREATE PROPERTY {name}.k INTEGER")
        temp_db.command("sql", f"CREATE PROPERTY {name}.big LONG")
    ints = [-(2**63), -(2**63) + 1, -1, 0, 1, 2**63 - 2, 2**63 - 1]
    floats = [0.0, -0.0, 1.5, math.inf, -math.inf, 5e-324, 1.7976931348623157e308]
    columns = {"k": list(range(len(ints))), "big": ints, "x": floats}
    _json_reference(temp_db, "Ref", _rows(columns), monkeypatch)
    temp_db.insert_columns("Col", columns)
    assert spy.count(COLP) == 1
    assert _stored(temp_db, "Col") == _stored(temp_db, "Ref")

    nan = {"k": [0, 1], "x": [float("nan"), 1.0]}
    temp_db.insert_columns("Col", nan)
    stored = temp_db.query(
        "sql", "SELECT x FROM Col WHERE k = 0 AND x IS NOT NULL ORDER BY x"
    ).to_list()
    assert any(isinstance(r["x"], float) and math.isnan(r["x"]) for r in stored)


def test_booleans_and_narrow_numpy_dtypes_keep_the_json_paths_types(
    temp_db, spy, monkeypatch
):
    for name in ("Ref", "Col"):
        temp_db.command("sql", f"CREATE DOCUMENT TYPE {name}")
        temp_db.command("sql", f"CREATE PROPERTY {name}.k INTEGER")
        temp_db.command("sql", f"CREATE PROPERTY {name}.flag BOOLEAN")
        temp_db.command("sql", f"CREATE PROPERTY {name}.small INTEGER")
        temp_db.command("sql", f"CREATE PROPERTY {name}.single FLOAT")
    n = 300
    ids = np.arange(n)
    columns = {
        "k": ids,
        "flag": ids % 3 == 0,
        "small": (ids - 150).astype(np.int32),  # declared INTEGER: crosses as int32
        "single": (ids / 8).astype(np.float32),  # declared FLOAT: crosses as float32
        "narrow": ids.astype(np.int16),  # undeclared: a Long, as from JSON
        "half": (ids / 4).astype(np.float32),  # undeclared: a Double, as from JSON
    }
    _json_reference(temp_db, "Ref", _rows(columns), monkeypatch)
    temp_db.insert_columns("Col", columns)
    assert spy.count(COLP) == 1
    assert _stored(temp_db, "Col") == _stored(temp_db, "Ref")


def test_vertex_types_load_like_documents(temp_db, spy, monkeypatch):
    for name in ("Ref", "Col"):
        temp_db.command("sql", f"CREATE VERTEX TYPE {name}")
        temp_db.command("sql", f"CREATE PROPERTY {name}.id INTEGER")
    columns = {"id": np.arange(50), "label": ["v%d" % i for i in range(50)]}
    _json_reference(temp_db, "Ref", _rows(columns), monkeypatch)
    temp_db.insert_columns("Col", columns)
    assert spy.count(COLP) == 1
    assert _stored(temp_db, "Col") == _stored(temp_db, "Ref")
    assert temp_db.query("sql", "SELECT count(*) AS n FROM Col").to_list()[0]["n"] == 50


# ---- the fallback: anything the buffers cannot carry unchanged goes through the JSON path, with the same result


def _fallback_case(temp_db, spy, monkeypatch, rows, expect_entry):
    _types(temp_db, "Ref", "Col")
    _json_reference(temp_db, "Ref", rows, monkeypatch)
    spy.calls.clear()
    temp_db.insert_many("Col", rows)
    assert spy.count(COLP) == 0
    assert spy.count(expect_entry) == 1, spy.calls
    assert _stored(temp_db, "Col") == _stored(temp_db, "Ref")


def test_nested_maps_and_lists_fall_back_to_json(temp_db, spy, monkeypatch):
    rows = [
        {"id": i, "txt": "t%d" % i, "meta": {"k": i, "tags": ["a", "b"]}}
        for i in range(20)
    ]
    _fallback_case(temp_db, spy, monkeypatch, rows, ROWS)


def test_a_mixed_type_column_falls_back_to_json(temp_db, spy, monkeypatch):
    rows = [
        {"id": i, "txt": "t%d" % i, "mixed": i if i % 2 else "s%d" % i}
        for i in range(20)
    ]
    _fallback_case(temp_db, spy, monkeypatch, rows, ROWS)
    rows = [
        {"id": i, "txt": "t%d" % i, "n": i if i % 2 else i + 0.5} for i in range(20)
    ]  # int and float
    spy.calls.clear()
    temp_db.insert_many("Col", rows)
    assert spy.count(COLP) == 0 and spy.count(ROWS) == 1


def test_rows_with_different_keys_fall_back_to_json(temp_db, spy, monkeypatch):
    rows = [
        {"id": i, "txt": "t"} if i % 2 else {"id": i, "cat": "c"} for i in range(20)
    ]
    _fallback_case(temp_db, spy, monkeypatch, rows, ROWS)


def test_values_json_cannot_carry_still_go_row_by_row_in_one_crossing(
    temp_db, spy, monkeypatch
):
    when = datetime.datetime(2024, 5, 6, 7, 8, 9)
    rows = [{"id": i, "txt": "t%d" % i, "when": when} for i in range(10)]
    _fallback_case(temp_db, spy, monkeypatch, rows, MANY)


def test_an_integer_past_64_bits_is_refused_on_both_paths(temp_db, spy):
    _types(temp_db, "Col")
    with pytest.raises(ArcadeDBError):
        temp_db.insert_many("Col", [{"id": 1, "txt": "a", "huge": 2**70}])
    assert spy.count(COLP) == 0
    with pytest.raises(ValueError):
        temp_db.insert_columns("Col", {"id": np.array([2**63], dtype=np.uint64)})


def test_a_dataframe_with_a_column_the_buffers_cannot_carry_falls_back(
    temp_db, spy, monkeypatch
):
    pd = pytest.importorskip("pandas")
    pa = pytest.importorskip("pyarrow")
    _types(temp_db, "Col")
    table = pa.table(
        {
            "id": pa.array([1, 2, 3], type=pa.int32()),
            "txt": pa.array(["a", "b", "c"]),
            "when": pa.array(
                [datetime.datetime(2024, 1, d) for d in (1, 2, 3)],
                type=pa.timestamp("us"),
            ),
        }
    )
    temp_db.insert_arrow("Col", table)
    assert spy.count(COLP) == 0
    assert pd is not None
    rows = temp_db.query("sql", "SELECT id, txt FROM Col ORDER BY id").to_list()
    assert [(r["id"], r["txt"]) for r in rows] == [(1, "a"), (2, "b"), (3, "c")]


# ---- transactions, chunking and failures


def test_more_rows_than_one_chunk_and_the_commit_interval(temp_db, spy):
    _types(temp_db, "Col")
    n = 25_000
    columns = _probe(n)
    assert temp_db.insert_many("Col", _rows(columns), commit_every=4_000) == n
    assert spy.count(COLP) == 7  # chunks of 4,000 rows: six full ones and one of 1,000
    assert temp_db.query("sql", "SELECT count(*) AS n FROM Col").to_list()[0]["n"] == n
    assert temp_db.insert_columns("Col", columns, commit_every=1_000) == n
    assert spy.count(COLP) == 8  # one crossing for the whole call
    assert (
        temp_db.query("sql", "SELECT count(*) AS n FROM Col").to_list()[0]["n"] == 2 * n
    )


def test_a_duplicate_key_fails_the_same_way_on_both_paths(temp_db, monkeypatch):
    _types(temp_db, "Ref", "Col", unique=True)
    ids = list(range(250))
    ids[150] = 7  # a duplicate of an earlier row
    columns = {"id": ids, "txt": ["t%d" % i for i in ids]}
    with monkeypatch.context() as m:
        m.setattr(bulk, "_ENABLED", False)
        with pytest.raises(ArcadeDBError) as ref:
            temp_db.insert_many("Ref", _rows(columns), commit_every=100)
    with pytest.raises(ArcadeDBError) as col:
        temp_db.insert_many("Col", _rows(columns), commit_every=100)
    for error in (
        ref.value,
        col.value,
    ):  # the unique index is checked when the batch commits
        assert "DuplicatedKeyException" in str(error) and "Duplicated key [7]" in str(
            error
        )
    # the rows of the failed batch are rolled back, the batches before it stay
    assert [
        temp_db.query("sql", f"SELECT count(*) AS n FROM {name}").to_list()[0]["n"]
        for name in ("Ref", "Col")
    ] == [100, 100]

    with pytest.raises(ArcadeDBError) as one_call:
        temp_db.insert_columns(
            "Col", {"id": ids, "txt": columns["txt"]}, commit_every=100
        )
    assert "Failed to bulk-insert" in str(one_call.value)


def test_a_callers_transaction_is_not_committed_by_the_call(temp_db, spy):
    _types(temp_db, "Col", unique=True)
    temp_db.begin()
    temp_db.insert_columns("Col", {"id": [1, 2, 3], "txt": ["a", "b", "c"]})
    assert spy.count(COLP) == 1
    assert temp_db.is_transaction_active()
    temp_db.rollback()
    assert temp_db.query("sql", "SELECT count(*) AS n FROM Col").to_list()[0]["n"] == 0


# ---- the image checks the table it is given: a wrong table is an error, never a fault, and writes nothing


def _send(db, columns, mutate):
    rows, packed = columnar.pack(columns, columnar.Declared(known={}))
    spec = columnar.spec_of(packed)
    mutate(spec, packed)
    reply = lib.call(
        COLP,
        db._h,
        lib.b("Col"),
        lib.b(columnar.header_of(rows, 10_000, packed)),
        spec,
        len(spec),
    )
    import json

    return json.loads(reply), packed


def _count(db):
    return db.query("sql", "SELECT count(*) AS n FROM Col").to_list()[0]["n"]


def test_a_table_that_does_not_fit_its_buffers_is_an_error_and_writes_nothing(temp_db):
    _types(temp_db, "Col")
    columns = {"id": np.arange(5), "txt": ["a", "bb", "ccc", "dddd", "eeeee"]}

    reply, _ = _send(
        temp_db, columns, lambda spec, p: spec.__setitem__(1, 8)
    )  # id: 8 bytes for 5 rows
    assert not reply["ok"] and "needed" in reply["error"]

    def decreasing(spec, packed):
        offsets = (ctypes.c_int32 * 6).from_address(spec[6])
        offsets[2], offsets[3] = 9, 4  # not increasing

    reply, _ = _send(temp_db, columns, decreasing)
    assert not reply["ok"] and "offsets" in reply["error"]

    def past_the_bytes(spec, packed):
        spec[9] = 3  # three bytes for 15 characters of text

    reply, _ = _send(temp_db, columns, past_the_bytes)
    assert not reply["ok"] and "offsets" in reply["error"]

    nulls = {"id": np.arange(16), "txt": ["a"] * 8 + [None] * 8}
    reply, _ = _send(
        temp_db, nulls, lambda spec, p: spec.__setitem__(11, 1)
    )  # bitmap of 1 byte for 16 rows
    assert not reply["ok"] and "bitmap" in reply["error"]
    assert _count(temp_db) == 0
    # the connection is fine afterwards
    assert temp_db.insert_columns("Col", columns) == 5 and _count(temp_db) == 5


def test_an_unknown_kind_and_a_wrong_table_size_are_errors(temp_db):
    _types(temp_db, "Col")
    import json

    arr = np.arange(3, dtype=np.int64)
    spec = (ctypes.c_int64 * 6)(arr.ctypes.data, arr.nbytes, 0, 0, 0, 0)
    for header, entries in (
        ({"n": 3, "commit": 0, "cols": [["id", "z", 0]]}, 6),
        (
            {"n": 3, "commit": 0, "cols": [["id", "q", 0], ["grp", "q", 0]]},
            6,
        ),  # two columns, one entry
        ({"n": -1, "commit": 0, "cols": [["id", "q", 0]]}, 6),
    ):
        reply = json.loads(
            lib.call(
                COLP, temp_db._h, lib.b("Col"), lib.b(json.dumps(header)), spec, entries
            )
        )
        assert not reply["ok"], header
    reply = json.loads(
        lib.call(
            COLP,
            temp_db._h,
            lib.b("Col"),
            lib.b(json.dumps({"n": 3, "commit": 0, "cols": []})),
            spec,
            5,
        )
    )
    assert not reply["ok"]  # 5 entries are not a multiple of 6
    assert _count(temp_db) == 0
