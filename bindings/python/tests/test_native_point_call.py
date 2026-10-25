"""The call path of a point read on the native backend (``db.query(sql, "... WHERE id = ?", i).first()`` and ``db.lookup_by_key``): the
parameter text, the ctypes call, the first row and the record wrapper. Results have to be the same as before the path was shortened,
for every kind of parameter and key; the first group runs on both backends, the second looks at the helpers of the native one.
"""

import json
import os

import pytest

NATIVE = os.environ.get("ARCADEDB_BACKEND", "jpype").lower() == "native"
native_only = pytest.mark.skipif(not NATIVE, reason="the native call path")

STRINGS = [
    "",
    "plain",
    "café 日本語 \U0001f600 end",  # 2-, 3- and 4-byte UTF-8 sequences
    'quote " backslash \\ slash / newline \n tab \t control \u0001',
    "`backtick` 'single' ?",
    "x" * 300,
]
INTS = [0, 1, -1, 7, 10**9, -(10**9), 2**31, 2**53 + 1, 2**63 - 1, -(2**63)]


def _docs(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE P").close()
    temp_db.command("sql", "CREATE PROPERTY P.id LONG").close()
    temp_db.command("sql", "CREATE PROPERTY P.name STRING").close()
    temp_db.command("sql", "CREATE INDEX ON P (id) UNIQUE").close()
    temp_db.command("sql", "CREATE INDEX ON P (name) UNIQUE").close()
    rows = [{"id": i, "name": f"n{i}"} for i in INTS]
    rows += [{"id": 100 + k, "name": s or "empty"} for k, s in enumerate(STRINGS)]
    temp_db.insert_many("P", rows)
    return rows


def test_point_read_by_an_int_parameter_finds_every_row(temp_db):
    rows = _docs(temp_db)
    for want in rows:
        got = temp_db.query("sql", "SELECT FROM P WHERE id = ?", want["id"]).first()
        assert got is not None and got.get("id") == want["id"]
        assert got.get("name") == want["name"]
    assert temp_db.query("sql", "SELECT FROM P WHERE id = ?", 424242).first() is None


def test_point_read_by_a_str_parameter_finds_every_row(temp_db):
    rows = _docs(temp_db)
    for want in rows:
        got = temp_db.query("sql", "SELECT FROM P WHERE name = ?", want["name"]).first()
        assert got is not None and got.get("id") == want["id"]
    assert (
        temp_db.query("sql", "SELECT FROM P WHERE name = ?", "no such").first() is None
    )


def test_lookup_by_key_returns_the_record_for_int_str_and_composite_keys(temp_db):
    rows = _docs(temp_db)
    for want in rows:
        by_id = temp_db.lookup_by_key("P", ["id"], [want["id"]])
        by_name = temp_db.lookup_by_key("P", ["name"], [want["name"]])
        assert by_id is not None and by_name is not None
        assert by_id.get("name") == want["name"] and by_name.get("id") == want["id"]
        assert by_id.get_rid() == by_name.get_rid()
        both = temp_db.lookup_by_key("P", ["id", "name"], [want["id"], want["name"]])
        assert both is not None and both.get_rid() == by_id.get_rid()
    assert temp_db.lookup_by_key("P", ["id"], [424242]) is None
    assert temp_db.lookup_by_key("P", ["id", "name"], [INTS[0], "n1"]) is None


def test_lookup_by_key_keeps_the_types_and_keys_of_each_call_apart(temp_db):
    _docs(temp_db)
    temp_db.command("sql", "CREATE VERTEX TYPE Q").close()
    temp_db.command("sql", "CREATE PROPERTY Q.id LONG").close()
    temp_db.command("sql", "CREATE PROPERTY Q.name STRING").close()
    temp_db.command("sql", "CREATE INDEX ON Q (id) UNIQUE").close()
    temp_db.command("sql", "CREATE INDEX ON Q (name) UNIQUE").close()
    with temp_db.transaction():
        temp_db.command(
            "sql", "CREATE VERTEX Q SET id = 1, name = 'vertex one'"
        ).close()
    for _ in range(
        3
    ):  # the second and third round reads the statement texts remembered by the first
        p, q = temp_db.lookup_by_key("P", ["id"], [1]), temp_db.lookup_by_key(
            "Q", ["id"], [1]
        )
        assert p.get("name") == "n1" and q.get("name") == "vertex one"
        assert type(p).__name__ == "Document" and type(q).__name__ == "Vertex"
        assert temp_db.lookup_by_key("P", ["name"], ["n1"]).get("id") == 1
        assert (
            temp_db.lookup_by_key("Q", ["name"], ["n1"]) is None
        )  # Q has no such row; the statement is not P's


def test_first_returns_the_first_row_and_closes_the_result(temp_db):
    _docs(temp_db)
    rs = temp_db.query("sql", "SELECT FROM P ORDER BY id")
    assert rs.first().get("id") == min(INTS)
    assert temp_db.query("sql", "SELECT FROM P WHERE id = -999").first() is None


@native_only
def test_a_second_first_on_the_same_result_raises_as_before(temp_db):
    from arcadedb_embedded.exceptions import ArcadeDBError

    _docs(temp_db)
    rs = temp_db.query("sql", "SELECT FROM P ORDER BY id")
    rs.first()
    with pytest.raises(
        ArcadeDBError
    ):  # first() closed it: the rows it did not return are gone
        rs.first()


def test_first_of_a_big_result_gives_the_first_row_and_leaves_no_cursor(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE R").close()
    temp_db.insert_many(
        "R", [{"i": i} for i in range(3000)]
    )  # more than the first reply batch
    for _ in range(50):
        assert temp_db.query("sql", "SELECT FROM R ORDER BY i").first().get("i") == 0
    assert temp_db.query("sql", "SELECT count(*) AS c FROM R").first().get("c") == 3000


@native_only
def test_a_row_read_after_the_database_closed_still_raises(temp_db):
    from arcadedb_embedded.exceptions import ArcadeDBError

    _docs(temp_db)
    row = temp_db.query("sql", "SELECT FROM P WHERE id = ?", 1).first()
    rs = temp_db.query("sql", "SELECT FROM P WHERE id = ?", 7)
    temp_db.close()
    with pytest.raises(ArcadeDBError):
        row.get("name")
    with pytest.raises(ArcadeDBError):
        rs.first()


# ---------------------------------------------------------------- the helpers of the native backend


def _native():
    from arcadedb_embedded._native import codec, database, lib, records

    return codec, database, lib, records


@native_only
@pytest.mark.parametrize(
    "value", INTS + STRINGS + [True, False, None, 1.5, -0.0, 10**30]
)
def test_encode_params_writes_one_parameter_as_json_dumps_does(value):
    codec = _native()[0]
    want = json.dumps({"pos": [value]})
    for args in ((value,), ([value],), ((value,),)):
        assert codec.encode_params(args) == want
        assert codec.encode_params(args, binary=True) == (want, None, 0)


@native_only
def test_encode_params_leaves_subclasses_and_numpy_scalars_to_the_general_path():
    np = pytest.importorskip("numpy")
    codec = _native()[0]

    class MyInt(int):
        pass

    class MyStr(str):
        pass

    for value in (MyInt(5), MyStr("x"), np.int64(5), np.float32(1.5), np.bool_(True)):
        assert codec.encode_params((value,)) == codec.encode_params([value])
    assert codec.encode_params((MyInt(5),)) == '{"pos": [5]}'
    assert codec.encode_params((np.int64(5),)) == '{"pos": [5]}'
    assert (
        codec.encode_params((True,)) == '{"pos": [true]}'
    )  # a bool is not sent as the int 1


@native_only
def test_encode_params_one_int_or_str_does_not_go_through_the_json_encoder(monkeypatch):
    codec = _native()[0]

    def boom(*a, **k):
        raise AssertionError("json encoder used for a lone int or str parameter")

    monkeypatch.setattr(codec, "_dumps", boom)
    assert codec.encode_params((12,)) == '{"pos": [12]}'
    assert codec.encode_params((["a\nb"],)) == '{"pos": ["a\\nb"]}'
    assert codec.encode_params(("é",)) == '{"pos": ["\\u00e9"]}'


@native_only
def test_encode_params_other_shapes_keep_their_text():
    codec = _native()[0]
    assert codec.encode_params(()) == ""
    assert codec.encode_params((), binary=True) == ("", None, 0)
    assert codec.encode_params((1, "a", None)) == '{"pos": [1, "a", null]}'
    assert codec.encode_params(([],)) == '{"pos": []}'
    assert codec.encode_params(({"a": 1},)) == '{"named": {"a": 1}}'


@native_only
def test_exec_query_returns_what_call_bin_returns_for_the_same_statement(temp_db):
    codec, database, lib, records = _native()
    _docs(temp_db)
    text, _, count = codec.encode_params((7,), binary=True)
    args = (
        temp_db._h,
        4,
        lib.bc("sql"),
        lib.bc("SELECT FROM P WHERE id = ?"),
        lib.b(text),
        256,
    )
    assert lib.exec_query(*args) == lib.call_bin("arcadedb_n_exec", *args)
    assert lib.exec_query(*args)[0].startswith("{")
    # a reply with a float tail: the vectors of the later rows come back as numbers in the text, the first batch as a tail
    temp_db.command("sql", "CREATE DOCUMENT TYPE V").close()
    temp_db.command("sql", "CREATE PROPERTY V.v ARRAY_OF_FLOATS").close()
    temp_db.insert_many(
        "V", [{"v": [float(k + j) / 4 for j in range(16)]} for k in range(4)]
    )
    vargs = (temp_db._h, 4, lib.bc("sql"), lib.bc("SELECT v FROM V"), b"", 256)
    got, want = lib.exec_query(*vargs), lib.call_bin("arcadedb_n_exec", *vargs)
    assert got[0] == want[0] and got[1] is not None and list(got[1]) == list(want[1])


@native_only
def test_exec_query_with_a_param_text_of_several_kinds(temp_db):
    _, _, lib, _ = _native()
    _docs(temp_db)
    for param in ('{"pos": [7]}', '{"pos": ["n7"]}', '{"pos": [null]}'):
        args = (
            temp_db._h,
            4,
            lib.bc("sql"),
            lib.bc("SELECT FROM P WHERE id = ? OR name = ?"),
            lib.b(param),
            256,
        )
        # the statement has two placeholders: a one-element list is an error reply, the same one from both entry points
        assert lib.exec_query(*args) == lib.call_bin("arcadedb_n_exec", *args)


@native_only
def test_lookup_by_key_builds_each_statement_text_once(temp_db):
    _, database, _, _ = _native()
    _docs(temp_db)
    database._LOOKUP_SQL.clear()
    temp_db.lookup_by_key("P", ["id"], [1])
    temp_db.lookup_by_key("P", ["id", "name"], [1, "n1"])
    assert sorted(database._LOOKUP_SQL.values()) == [
        "SELECT FROM `P` WHERE `id` = ? AND `name` = ? LIMIT 1",
        "SELECT FROM `P` WHERE `id` = ? LIMIT 1",
    ]
    one = database._LOOKUP_SQL[("P", ("id",))]
    temp_db.lookup_by_key(
        "P", ("id",), (2,)
    )  # a tuple of keys and values is the same lookup
    assert database._LOOKUP_SQL[("P", ("id",))] is one


@native_only
def test_records_share_one_java_stand_in_and_an_import_free_wrap(temp_db):
    _, database, _, records = _native()
    _docs(temp_db)
    assert records._java_object() is records._java_object()
    a, b = temp_db.lookup_by_key("P", ["id"], [1]), temp_db.lookup_by_key(
        "P", ["id"], [7]
    )
    assert a._java_document is b._java_document
    with pytest.raises(NotImplementedError):
        a._java_document.anything
    assert a.get_rid() != b.get_rid() and a.to_dict() == {"id": 1, "name": "n1"}
    a2 = a.modify()  # a mutable copy keeps working on its own properties
    a2.set("name", "changed")
    assert a.get("name") == "n1" and a2.get("name") == "changed"


@native_only
def test_first_takes_the_buffered_row_without_the_iterator_protocol(
    temp_db, monkeypatch
):
    _, database, _, _ = _native()
    _docs(temp_db)

    def boom(self):
        raise AssertionError(
            "first() went through __next__ for a row that was already here"
        )

    monkeypatch.setattr(database.NativeResultSet, "__next__", boom)
    assert (
        temp_db.query("sql", "SELECT FROM P WHERE id = ?", 1).first().get("name")
        == "n1"
    )
    assert temp_db.lookup_by_key("P", ["id"], [1]).get("name") == "n1"
