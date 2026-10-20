"""SQL `=` on a list or map misses a list written from Python (known-issues.md).

`Document.set`, `Vertex.set` and `GraphBatch.create_vertices` store a Python `int` as a `Long`,
and a SQL literal such as `[1, 2]` parses to `Integer` elements. SQL `=` compares list and map
elements with Java `equals()`, so the list written from Python is not equal to the literal.
The workarounds (openCypher `=`, and a named SQL parameter, which crosses as `Long` elements)
must keep passing (the parameter only without a `BY ITEM` index on the list: with one, SQL `=`
is answered from the index and matches nothing). The engine behavior itself is a strict `xfail`, a tripwire as in
`test_null_index_known_issues.py`: when the fix reaches the wheel it starts passing and the
suite fails, and the test then becomes a plain one.

Upstream: ArcadeData/arcadedb #10448 (open; measured on the 26.10.2 wheel and on main
58e00054b1).
"""

import arcadedb_embedded as arcadedb
import pytest


@pytest.fixture
def db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE VERTEX TYPE V")
        with db.transaction():
            v = db.new_vertex("V")
            v.set("k", "set")
            v.set("li", [1, 2])
            v.set("mp", {"a": 1})
            v.save()
        with db.graph_batch(parallel_flush=False) as batch:
            batch.create_vertices("V", [{"k": "batch", "li": [1, 2], "mp": {"a": 1}}])
        yield db


@pytest.fixture
def indexed_db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE VERTEX TYPE X")
        db.command("sql", "CREATE PROPERTY X.li LIST")
        db.command("sql", "CREATE INDEX ON X (li BY ITEM) NOTUNIQUE")
        with db.transaction():
            v = db.new_vertex("X")
            v.set("k", "set")
            v.set("li", [1, 2])
            v.save()
        yield db


def _keys(db, language, query, *args):
    return sorted(row["k"] for row in db.query(language, query, *args).to_list())


def test_opencypher_equality_matches_lists_and_maps_written_from_python(db):
    assert _keys(
        db, "opencypher", "MATCH (n:V) WHERE n.li = [1, 2] RETURN n.k AS k"
    ) == ["batch", "set"]
    assert _keys(
        db, "opencypher", "MATCH (n:V) WHERE n.mp = {a: 1} RETURN n.k AS k"
    ) == ["batch", "set"]


def test_a_named_sql_parameter_matches_lists_written_from_python(db):
    assert _keys(db, "sql", "SELECT k FROM V WHERE li = :p", {"p": [1, 2]}) == [
        "batch",
        "set",
    ]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="ArcadeData/arcadedb#10448"
)
def test_a_sql_list_literal_matches_lists_written_from_python(db):
    assert _keys(db, "sql", "SELECT k FROM V WHERE li = [1, 2]") == ["batch", "set"]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="ArcadeData/arcadedb#10448"
)
def test_a_sql_map_literal_matches_maps_written_from_python(db):
    assert _keys(db, "sql", 'SELECT k FROM V WHERE mp = {"a": 1}') == ["batch", "set"]


def test_opencypher_equality_matches_through_a_by_item_index(indexed_db):
    assert _keys(
        indexed_db, "opencypher", "MATCH (n:X) WHERE n.li = [1, 2] RETURN n.k AS k"
    ) == ["set"]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="ArcadeData/arcadedb#10448"
)
def test_a_named_sql_parameter_matches_through_a_by_item_index(indexed_db):
    # With a BY ITEM index on the list, SQL = is answered from the index and matches nothing
    assert _keys(indexed_db, "sql", "SELECT k FROM X WHERE li = :p", {"p": [1, 2]}) == [
        "set"
    ]
