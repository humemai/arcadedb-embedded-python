"""The helpers of the native call path of a point read (``db.query(sql, "... WHERE id = ?", i).first()`` and ``db.lookup_by_key``): the
parameter text, the ctypes call, the schema-read cache, the first row and the record wrapper. The results of the point reads themselves, for
both wheels, are checked in test_native_point_call.py.

Needs the native library, so conftest.py does not collect this file on the JPype backend (a skip there would fail
scripts/check_test_skips.py); it runs in the native parity run.
"""

import json

import pytest
from tests.test_native_point_call import INTS, STRINGS, _docs


def _native():
    from arcadedb_embedded._native import codec, database, lib, records

    return codec, database, lib, records


def test_lookup_by_key_reads_the_schema_once_per_pair_not_once_per_call(temp_db):
    """The index check costs one extra crossing the first time a (type, keys) pair is looked up on a handle and none after."""
    _docs(temp_db)
    real, seen = temp_db.query, []

    def spy(language, command, *args):
        seen.append(command)
        return real(language, command, *args)

    temp_db.query = spy
    try:
        for i in range(5):
            assert temp_db.lookup_by_key("P", ["id"], [INTS[i]]) is not None
            assert temp_db.lookup_by_key("P", ["id", "name"], [INTS[i], f"n{INTS[i]}"])
    finally:
        del temp_db.query
    checks = [c for c in seen if "schema:" in c]
    assert len(checks) == 2 and len(seen) == 2 * 5 + 2, seen


def test_a_second_first_on_the_same_result_raises_as_before(temp_db):
    from arcadedb_embedded.exceptions import ArcadeDBError

    _docs(temp_db)
    rs = temp_db.query("sql", "SELECT FROM P ORDER BY id")
    rs.first()
    with pytest.raises(
        ArcadeDBError
    ):  # first() closed it: the rows it did not return are gone
        rs.first()


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


@pytest.mark.parametrize(
    "value", INTS + STRINGS + [True, False, None, 1.5, -0.0, 10**30]
)
def test_encode_params_writes_one_parameter_as_json_dumps_does(value):
    codec = _native()[0]
    want = json.dumps({"pos": [value]})
    for args in ((value,), ([value],), ((value,),)):
        assert codec.encode_params(args) == want
        assert codec.encode_params(args, binary=True) == (want, None, 0)


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


def test_encode_params_one_int_or_str_does_not_go_through_the_json_encoder(monkeypatch):
    codec = _native()[0]

    def boom(*a, **k):
        raise AssertionError("json encoder used for a lone int or str parameter")

    monkeypatch.setattr(codec, "_dumps", boom)
    assert codec.encode_params((12,)) == '{"pos": [12]}'
    assert codec.encode_params((["a\nb"],)) == '{"pos": ["a\\nb"]}'
    assert codec.encode_params(("é",)) == '{"pos": ["\\u00e9"]}'


def test_encode_params_other_shapes_keep_their_text():
    codec = _native()[0]
    assert codec.encode_params(()) == ""
    assert codec.encode_params((), binary=True) == ("", None, 0)
    assert codec.encode_params((1, "a", None)) == '{"pos": [1, "a", null]}'
    assert codec.encode_params(([],)) == '{"pos": []}'
    assert codec.encode_params(({"a": 1},)) == '{"named": {"a": 1}}'


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
