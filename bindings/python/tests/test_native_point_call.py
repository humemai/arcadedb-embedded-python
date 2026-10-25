"""The results of a point read (``db.query(sql, "... WHERE id = ?", i).first()`` and ``db.lookup_by_key``) on both wheels: the parameter,
the first row and the record wrapper. The native backend shortened this path, and the results have to be the same as before, for every
kind of parameter and key. What looks at the helpers of the native call path (crossing counts, the schema-read cache, the parameter
codec) is in test_native_point_call_native.py, which conftest.py does not collect on the JPype backend.
"""

import re

import pytest

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
    temp_db.command(
        "sql", "CREATE INDEX ON P (id, name) UNIQUE"
    ).close()  # the composite lookups
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


def _no_index_error(type_name, keys):
    """The text both wheels give for a lookup no index covers (Arrays.toString of the keys)."""
    return (
        rf"Failed to lookup by key in '{type_name}': .*No index has been created on type "
        rf"'{type_name}' properties {re.escape('[' + ', '.join(keys) + ']')}"
    )


def test_lookup_by_key_without_an_index_on_exactly_those_keys_raises(temp_db):
    """``lookup_by_key`` is an index lookup (docs/api/database.md): keys no index covers raise ArcadeDBError on the JVM wheel
    (the engine's ``No index has been created``), and on the native wheel too, where the statement it runs would scan the type (P-04).
    The refusal repeats and does not make the next call pass."""
    from arcadedb_embedded.exceptions import ArcadeDBError

    _docs(temp_db)
    temp_db.command("sql", "CREATE PROPERTY P.extra STRING").close()
    for keys, values in (
        (["extra"], ["x"]),  # a property with no index
        (
            ["name", "id"],
            ["n1", 1],
        ),  # the composite index is (id, name): the order counts
        (["id", "extra"], [1, "x"]),  # only a prefix of the keys is indexed
        (["id", "name", "extra"], [1, "n1", "x"]),
    ):
        for _ in range(3):
            with pytest.raises(ArcadeDBError, match=_no_index_error("P", keys)):
                temp_db.lookup_by_key("P", keys, values)
    # the keys an index covers still work after the refusals
    assert temp_db.lookup_by_key("P", ["id"], [1]).get("name") == "n1"
    assert temp_db.lookup_by_key("P", ["id", "name"], [1, "n1"]).get("id") == 1


def test_lookup_by_key_on_a_type_that_does_not_exist_still_raises_the_schema_error(
    temp_db,
):
    from arcadedb_embedded.exceptions import ArcadeDBError

    with pytest.raises(ArcadeDBError, match=r"Failed to lookup by key in 'Nope'") as e:
        temp_db.lookup_by_key("Nope", ["id"], [1])
    assert "No index has been created" not in str(e.value)


def test_lookup_by_key_follows_the_indexes_of_the_database_it_is_called_on(
    temp_db, tmp_path
):
    """What one database answers must not be remembered for another with a type of the same name, nor after DROP INDEX."""
    import arcadedb_embedded as arcadedb
    from arcadedb_embedded.exceptions import ArcadeDBError

    temp_db.command("sql", "CREATE DOCUMENT TYPE K").close()
    temp_db.command("sql", "CREATE PROPERTY K.k LONG").close()
    temp_db.command("sql", "CREATE INDEX ON K (k) NOTUNIQUE").close()
    temp_db.insert_many("K", [{"k": 1}, {"k": 2}])
    for _ in range(2):  # the second call is the remembered one
        assert temp_db.lookup_by_key("K", ["k"], [2]).get("k") == 2

    other = arcadedb.create_database(str(tmp_path / "other_db"))
    try:
        other.command("sql", "CREATE DOCUMENT TYPE K").close()
        other.command("sql", "CREATE PROPERTY K.k LONG").close()
        other.insert_many("K", [{"k": 1}, {"k": 2}])
        with pytest.raises(ArcadeDBError, match=_no_index_error("K", ["k"])):
            other.lookup_by_key("K", ["k"], [2])
    finally:
        other.close()
    assert temp_db.lookup_by_key("K", ["k"], [1]).get("k") == 1

    temp_db.command("sql", "DROP INDEX `K[k]`").close()
    with pytest.raises(ArcadeDBError, match=_no_index_error("K", ["k"])):
        temp_db.lookup_by_key("K", ["k"], [2])
    temp_db.command("sql", "CREATE INDEX ON K (k) NOTUNIQUE").close()
    assert temp_db.lookup_by_key("K", ["k"], [2]).get("k") == 2


def test_lookup_by_key_uses_an_index_of_a_supertype_and_refuses_a_full_text_one(
    temp_db,
):
    from arcadedb_embedded.exceptions import ArcadeDBError

    for sql in (
        "CREATE DOCUMENT TYPE Base",
        "CREATE PROPERTY Base.id LONG",
        "CREATE PROPERTY Base.body STRING",
        "CREATE INDEX ON Base (id) UNIQUE",
        "CREATE INDEX ON Base (body) FULL_TEXT",
        "CREATE DOCUMENT TYPE Sub EXTENDS Base",
    ):
        temp_db.command("sql", sql).close()
    temp_db.insert_many("Sub", [{"id": 5, "body": "hello world"}])
    for _ in range(2):
        found = temp_db.lookup_by_key("Sub", ["id"], [5])
        assert found is not None and found.get("body") == "hello world"
    for type_name in ("Base", "Sub"):
        with pytest.raises(
            ArcadeDBError,
            match=rf"No key index has been created on type '{type_name}' properties \[body\]",
        ):
            temp_db.lookup_by_key(type_name, ["body"], ["hello"])


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


def test_first_of_a_big_result_gives_the_first_row_and_leaves_no_cursor(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE R").close()
    temp_db.insert_many(
        "R", [{"i": i} for i in range(3000)]
    )  # more than the first reply batch
    for _ in range(50):
        assert temp_db.query("sql", "SELECT FROM R ORDER BY i").first().get("i") == 0
    assert temp_db.query("sql", "SELECT count(*) AS c FROM R").first().get("c") == 3000
