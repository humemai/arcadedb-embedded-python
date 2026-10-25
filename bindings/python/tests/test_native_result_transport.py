"""Query results across the native boundary: the reply text (and the float32 tail of a reply with vectors) the image hands to Python
is copied out of the image in bulk, not one byte at a time. Every value has to come back exactly as it went in, for replies of
every size: tiny, several batches (arcadedb_n_exec returns the first 256 rows, arcadedb_n_next the following 2048 at a time) and
single rows of about a megabyte of multi-byte text. The tests hold on both backends; only the native one has this copy.
"""

import struct

DIM = 16  # 8 or more floats per vector: they travel in the float32 tail of the first batch, as JSON numbers in the later ones

TEXTS = [
    "",
    "plain",
    "café 日本語 \U0001f600 end",  # 2-, 3- and 4-byte UTF-8 sequences
    'quote " backslash \\ slash / newline \n tab \t nul-free \u0001 control',
    "x" * 300,
]


def f32(x):
    """The double a float32 value widens to (what the engine returns for an ARRAY_OF_FLOATS element)."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _rows(n):
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": i,
                "big": (1 << 62) - i if i % 2 else -(1 << 62) + i,
                "val": (i + 0.5) / 7.0,
                "txt": TEXTS[i % len(TEXTS)],
                "vec": [f32((i * DIM + k) / 1000.0 - 3.0) for k in range(DIM)],
            }
        )
    return rows


def _typed_db(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE R")
    for p, t in (
        ("id", "INTEGER"),
        ("big", "LONG"),
        ("val", "DOUBLE"),
        ("txt", "STRING"),
        ("vec", "ARRAY_OF_FLOATS"),
    ):
        temp_db.command("sql", f"CREATE PROPERTY R.{p} {t}")
    return temp_db


def test_a_reply_of_several_batches_round_trips_exactly(temp_db):
    db = _typed_db(temp_db)
    rows = _rows(
        5000
    )  # 256 in the first reply (vectors in the float tail), then 2048 + 2048 + 648 (vectors as numbers)
    db.insert_many("R", rows)
    got = db.query("sql", "SELECT id, big, val, txt, vec FROM R ORDER BY id").to_list()
    assert len(got) == len(rows)
    for want, have in zip(rows, got):
        assert have["id"] == want["id"]
        assert have["big"] == want["big"]
        assert have["val"] == want["val"]
        assert have["txt"] == want["txt"]
        assert list(have["vec"]) == want["vec"]


def test_a_small_reply_with_a_vector_round_trips_exactly(temp_db):
    db = _typed_db(temp_db)
    rows = _rows(3)
    db.insert_many("R", rows)
    got = db.query("sql", "SELECT id, vec, txt FROM R ORDER BY id").to_list()
    assert [list(r["vec"]) for r in got] == [r["vec"] for r in rows]
    assert [r["txt"] for r in got] == [r["txt"] for r in rows]


def test_rows_of_about_a_megabyte_of_multibyte_text_round_trip(temp_db):
    db = _typed_db(temp_db)
    unit = "aé日\U0001f600"  # 1 + 2 + 3 + 4 bytes
    rows = [
        {"id": i, "txt": unit * (250_000 + i)} for i in range(4)
    ]  # ~1.2 MB of UTF-8 per row
    db.insert_many("R", rows)
    got = db.query("sql", "SELECT id, txt FROM R ORDER BY id").to_list()
    assert [(r["id"], r["txt"]) for r in got] == [(r["id"], r["txt"]) for r in rows]


def test_empty_and_one_row_replies(temp_db):
    db = _typed_db(temp_db)
    assert db.query("sql", "SELECT FROM R").to_list() == []
    assert db.query("sql", "SELECT '' AS s").to_list() == [{"s": ""}]
    assert db.query("sql", "SELECT 1 AS x").first().get("x") == 1


# ---- vectors on every batch (first reply and arcadedb_n_next batches), bit-exact, with short, empty and missing vectors

SPECIAL = [
    float("inf"),
    float("-inf"),
    -0.0,
    0.0,
    1e-45,
    3.4028235e38,
    0.1,
    -123456.789,
]  # 8 values: a float32 tail on the binary path


def _bits(x):
    """The 8 bytes of a double as hex (any NaN is 'nan'): bit-exact comparison, so -0.0 differs from 0.0."""
    return "nan" if x != x else struct.pack("<d", x).hex()


def _vector_rows(n):
    rows, want = [], {}
    for i in range(n):
        kind = i % 6
        if kind == 0:
            vec = [f32(((i * 7 + k) % 1000) / 37.0 - 5.0) for k in range(32)]
        elif kind == 1:
            vec = [f32(x) for x in SPECIAL]
        elif kind == 2:
            vec = []
        elif kind == 3:
            vec = [
                f32(0.1),
                f32(-2.5),
                f32(1e-45),
            ]  # fewer than 8 floats: number text on every path
        elif kind == 4:
            vec = [
                f32((i + k) / 11.0) for k in range(8)
            ]  # exactly 8: the smallest vector that travels as a float32 tail
        else:
            vec = None  # no vec property at all
        row = {"id": i}
        if vec is not None:
            row["vec"] = vec
        rows.append(row)
        want[i] = vec
    return rows, want


def test_vectors_are_bit_exact_on_the_first_and_on_later_batches(temp_db):
    db = _typed_db(temp_db)
    rows, want = _vector_rows(3000)  # 256 rows in the first reply, then 2048 + 696
    db.insert_many("R", rows)
    got = db.query("sql", "SELECT id, vec FROM R ORDER BY id").to_list()
    assert [r["id"] for r in got] == list(range(3000))
    for r in got:
        expect = want[r["id"]]
        if expect is None:
            assert r.get("vec") is None, r["id"]
        else:
            assert [_bits(x) for x in r["vec"]] == [_bits(x) for x in expect], r["id"]


def test_vectors_in_a_cursor_read_row_by_row_are_bit_exact(temp_db):
    db = _typed_db(temp_db)
    rows, want = _vector_rows(700)
    db.insert_many("R", rows)
    seen = 0
    for r in db.query("sql", "SELECT id, vec FROM R ORDER BY id"):
        expect = want[r.get("id")]
        vec = r.get("vec")
        assert (
            (vec is None)
            if expect is None
            else [_bits(x) for x in vec] == [_bits(x) for x in expect]
        )
        seen += 1
    assert seen == 700
