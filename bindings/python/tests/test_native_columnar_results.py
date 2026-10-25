"""Query results as columns (N-R2): the rows a result gives back are the same values, types and key order whether the library answers with JSON text
or with a columnar frame, for mixed types with nulls, unicode, integers near 2**31 and 2**53, doubles with -0.0, inf and nan, float32 vectors of
every length, record ids, dates and datetimes, in one batch and in several, for point lookups, for records with missing properties and for results
the columns cannot carry (nested maps and lists, a column that mixes int and double). On the native library the same query runs three ways in one
process: JSON (ARCADEDB_NATIVE_COLRES=0), columns for every batch (COLRES_MIN=1) and the default; the JPype backend only checks the expected values.
"""

import math
import os
import struct
from contextlib import contextmanager
from datetime import date, datetime

NATIVE = os.environ.get("ARCADEDB_BACKEND", "jpype").lower() == "native"
if NATIVE:
    from arcadedb_embedded._native import lib
else:
    lib = None

TEXTS = [
    "",
    "plain",
    "café 日本語",
    "\U0001f600 emoji \U0001f468‍\U0001f469",
    'quote " backslash \\ nl \n tab \t ctrl \u0001 slash /',
    "x" * 300,
    None,
]
LONGS = [
    -(1 << 63),
    -1,
    0,
    (1 << 31) - 1,
    1 << 31,
    1 << 53,
    (1 << 53) + 1,
    (1 << 62),
    (1 << 63) - 1,
]
DOUBLES = [
    -0.0,
    0.0,
    float("inf"),
    float("-inf"),
    float("nan"),
    1e-300,
    0.1,
    1.7976931348623157e308,
    5e-324,
    123456789.12345679,
]


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def bits(x):
    return "nan" if x != x else struct.pack("<d", x).hex()


def norm(v):
    """A value with its type and exact bits: -0.0 differs from 0.0, 1 from 1.0 and True, key order counts."""
    if isinstance(v, float):
        return ("f", bits(v))
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, int):
        return ("i", v)
    if isinstance(v, (list, tuple)):
        return ("l", [norm(x) for x in v])
    if isinstance(v, dict):
        return ("m", [(k, norm(x)) for k, x in v.items()])
    return (type(v).__name__, str(v))


def _vec(i):
    k = i % 7
    if k == 0:
        return [f32(((i * 7 + j) % 1000) / 37.0 - 5.0) for j in range(32)]
    if k == 1:
        return [
            f32(x)
            for x in (
                float("inf"),
                float("-inf"),
                -0.0,
                0.0,
                1e-45,
                3.4028235e38,
                0.1,
                -123456.789,
            )
        ]
    if k == 2:
        return []
    if k == 3:
        return [f32(0.1), f32(-2.5), f32(1e-45)]
    if k == 4:
        return [f32((i + j) / 11.0) for j in range(8)]
    return None


def _rows(n):
    rows = []
    for i in range(n):
        r = {
            "id": i,
            "big": LONGS[i % len(LONGS)],
            "d": DOUBLES[i % len(DOUBLES)],
            "flag": i % 3 == 0,
            "dt": datetime(
                1969 + i % 50,
                1 + i % 12,
                1 + i % 28,
                i % 24,
                i % 60,
                i % 60,
                (i * 7919) % 1000 * 1000,
            ),
            "dd": date(1900 + i % 120, 1 + i % 12, 1 + i % 28),
        }
        if TEXTS[i % len(TEXTS)] is not None:
            r["s"] = TEXTS[i % len(TEXTS)]
        v = _vec(i)
        if v is not None:
            r["v"] = v
        rows.append(r)
    return rows


def _db(temp_db, n):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE T")
    for p, t in (
        ("id", "INTEGER"),
        ("big", "LONG"),
        ("d", "DOUBLE"),
        ("flag", "BOOLEAN"),
        ("dt", "DATETIME"),
        ("dd", "DATE"),
        ("s", "STRING"),
        ("v", "ARRAY_OF_FLOATS"),
    ):
        db.command("sql", f"CREATE PROPERTY T.{p} {t}")
    rows = _rows(n)
    db.insert_many("T", rows)
    return db, rows


@contextmanager
def mode(colres, minrows=None):
    if lib is None or not hasattr(lib, "COLRES"):
        yield
        return
    if colres and not hasattr(lib._lib or lib._load(), "arcadedb_n_exec_col"):
        colres = False  # a library built before columnar results: the JSON path is all there is
    old = lib.COLRES, lib.COLRES_MIN
    lib.COLRES, lib.COLRES_MIN = colres, old[1] if minrows is None else minrows
    try:
        yield
    finally:
        lib.COLRES, lib.COLRES_MIN = old


def _run(db, sql, *args):
    return db.query("sql", sql, *args).to_list()


def _modes(db, sql, *args):
    """The rows in each mode; asserts they are the same, bit for bit; returns the JSON-mode rows."""
    out = {}
    for label, (c, m) in {
        "json": (False, None),
        "cols": (True, 1),
        "default": (True, 16),
    }.items():
        with mode(c, m):
            out[label] = _run(db, sql, *args)
    base = [norm(r) for r in out["json"]]
    for label in ("cols", "default"):
        assert [norm(r) for r in out[label]] == base, label
    return out["json"]


def _counts():
    return (
        (lib.col_frames, lib.col_json)
        if lib is not None and hasattr(lib, "col_frames")
        else (0, 0)
    )


def test_mixed_types_come_back_exactly_in_every_mode(temp_db):
    db, rows = _db(temp_db, 40)
    got = _modes(db, "SELECT id, big, d, flag, s, dt, dd, v FROM T ORDER BY id")
    assert len(got) == len(rows)
    for want, have in zip(rows, got):
        assert have["id"] == want["id"] and type(have["id"]) is int
        assert have["big"] == want["big"] and type(have["big"]) is int
        assert bits(have["d"]) == bits(want["d"])
        assert have["flag"] is want["flag"]
        assert have.get("s") == want.get("s")
        assert (list(have["v"]) if have.get("v") is not None else None) == want.get("v")
        assert isinstance(have["dt"], datetime) and isinstance(have["dd"], date)
    f0, j0 = _counts()
    with mode(True, 1):
        _run(db, "SELECT id, big, d, flag, s, dt, dd, v FROM T ORDER BY id")
    if lib is not None and hasattr(lib, "col_frames"):
        assert (
            _counts()[0] > f0
        )  # carried as a frame (the rows are all of one kind per column)


def test_record_rows_keep_their_meta_and_property_order(temp_db):
    db, rows = _db(temp_db, 30)
    got = _modes(db, "SELECT FROM T ORDER BY id")
    assert [r["id"] for r in got] == list(range(30))
    with mode(True, 1):
        rs = db.query("sql", "SELECT FROM T ORDER BY id")
        first = next(iter(rs))
        assert first.get_rid() is not None and first.get_element() is not None


def test_record_ids_and_types_as_values(temp_db):
    db, _ = _db(temp_db, 12)
    got = _modes(db, "SELECT @rid AS r, @type AS t, id FROM T ORDER BY id")
    assert all(str(r["r"]).startswith("#") and r["t"] == "T" for r in got)
    assert all(type(r["r"]).__name__ == "RID" for r in got)


def test_batches_of_a_big_result_are_the_same_as_one(temp_db):
    db, rows = _db(temp_db, 5000)  # 256 in the first reply, then 2048 + 2048 + 648
    got = _modes(db, "SELECT id, big, d, s, v FROM T ORDER BY id")
    assert len(got) == 5000
    assert [r["id"] for r in got] == list(range(5000))
    for want, have in zip(rows, got):
        assert (
            have["big"] == want["big"]
            and bits(have["d"]) == bits(want["d"])
            and have.get("s") == want.get("s")
        )
        assert (list(have["v"]) if have.get("v") is not None else None) == want.get("v")


def test_point_lookups_and_empty_results(temp_db):
    db, rows = _db(temp_db, 50)
    got = _modes(db, "SELECT id, s, d FROM T WHERE id = :id", {"id": 3})
    assert (
        len(got) == 1 and got[0]["id"] == 3 and bits(got[0]["d"]) == bits(rows[3]["d"])
    )
    assert _modes(db, "SELECT FROM T WHERE id < 0") == []
    assert _modes(db, "SELECT 1 AS one, 'a' AS two") == [{"one": 1, "two": "a"}]
    agg = _modes(db, "SELECT count(*) AS c, avg(id) AS a FROM T")
    assert agg[0]["c"] == 50


def test_records_with_missing_and_null_properties(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Q")
    for i in range(30):
        row = {"a": i}
        if i % 3:
            row["b"] = f"b{i}"
        if i % 4:
            row["c"] = i * 0.5
        if i % 5 == 0:
            row["extra"] = [i, "x"]  # a list: the batch it is in goes as JSON
        db.insert_many("Q", [row])
    got = _modes(db, "SELECT FROM Q ORDER BY a")
    assert [r["a"] for r in got] == list(range(30))
    assert all(("b" in r) == bool(r["a"] % 3) for r in got)
    proj = _modes(db, "SELECT a, b, c FROM Q ORDER BY a")
    assert all(
        set(r) == {"a", "b", "c"} for r in proj
    )  # a projection names every column, null where the property is missing


def test_results_the_columns_cannot_carry_still_come_back(temp_db):
    db, _ = _db(temp_db, 20)
    f0, j0 = _counts()
    nested = _modes(
        db, "SELECT id, [id, id + 1] AS pair, {'k': id} AS m FROM T ORDER BY id"
    )
    assert nested[3]["pair"] == [3, 4] and nested[3]["m"] == {"k": 3}
    mixed = _modes(db, "SELECT id, ifnull(NULL, d) AS z FROM T ORDER BY id")  # doubles
    assert len(mixed) == 20
    with mode(True, 1):
        _run(db, "SELECT id, [id, id + 1] AS pair FROM T ORDER BY id")
    if lib is not None and hasattr(lib, "col_json"):
        assert _counts()[1] > j0  # answered as JSON through the columnar entry points


def test_a_cursor_read_row_by_row_matches(temp_db):
    db, rows = _db(temp_db, 600)
    for label, (c, m) in {"json": (False, None), "cols": (True, 1)}.items():
        with mode(c, m):
            seen = [
                r.get("id") for r in db.query("sql", "SELECT id, s FROM T ORDER BY id")
            ]
            assert seen == list(range(600)), label
