"""SQL `=` on a list or map and a list written from Python (known-issues.md), fixed in 26.11.1.

`Document.set`, `Vertex.set` and `GraphBatch.create_vertices` store a Python `int` as a `Long`,
and a SQL literal such as `[1, 2]` parses to `Integer` elements. SQL `=` used to compare list and
map elements with Java `equals()`, so the list written from Python was not equal to the literal.
ArcadeData/arcadedb#10448 (fixed by #10457, in 26.11.1) makes `=` and `<>` compare the elements
numerically, as openCypher, `CONTAINSALL` and `GROUP BY` already did, and a `BY ITEM` index is no
longer used to answer a whole-list `=` (the query scans, so the answer is right).

The workarounds that were documented (openCypher `=`, and a named SQL parameter, which crosses as
`Long` elements) must keep passing on every engine. The three SQL tests that were strict `xfail`
tripwires are plain tests now: they assert the fixed answer.

CI builds its wheel from upstream's 26.11.1-SNAPSHOT image, which carries no build number and is
republished only when upstream's deploy job succeeds; at the time of this change it still held the
engine from before #10457, with the same version string as the fixed engine. So the version cannot
tell the two apart, and `fixed` probes the one behavior that changed: two lists that differ only in
the element class are equal. On an engine without the fix the same tests assert the old answer (no
row), as `test_vector_sql.py` does for `where` (the repository accepts no skips,
scripts/check_test_skips.py). When 26.11.1 is released and the wheel the suite runs on is built
from it, delete `fixed` and the old-answer branches.
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


@pytest.fixture
def fixed(tmp_path):
    """True when the engine has the #10448 fix (see the module docstring)."""
    with arcadedb.create_database(str(tmp_path / "probe")) as probe:
        row = probe.query("sql", "SELECT ([1, 2] = :p) AS eq", {"p": [1, 2]}).to_list()
    return row[0]["eq"] is True


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


def test_a_sql_list_literal_matches_lists_written_from_python(db, fixed):
    assert _keys(db, "sql", "SELECT k FROM V WHERE li = [1, 2]") == (
        ["batch", "set"] if fixed else []
    )


def test_a_sql_map_literal_matches_maps_written_from_python(db, fixed):
    assert _keys(db, "sql", 'SELECT k FROM V WHERE mp = {"a": 1}') == (
        ["batch", "set"] if fixed else []
    )


def test_sql_inequality_on_a_list_excludes_lists_written_from_python(db, fixed):
    assert _keys(db, "sql", "SELECT k FROM V WHERE li <> [1, 2]") == (
        [] if fixed else ["batch", "set"]
    )


def test_opencypher_equality_matches_through_a_by_item_index(indexed_db):
    assert _keys(
        indexed_db, "opencypher", "MATCH (n:X) WHERE n.li = [1, 2] RETURN n.k AS k"
    ) == ["set"]


def test_a_named_sql_parameter_matches_through_a_by_item_index(indexed_db, fixed):
    # Before the fix, SQL = on a list with a BY ITEM index was answered from the index and
    # matched nothing; now the query scans
    assert _keys(indexed_db, "sql", "SELECT k FROM X WHERE li = :p", {"p": [1, 2]}) == (
        ["set"] if fixed else []
    )


def test_a_sql_list_literal_matches_through_a_by_item_index(indexed_db, fixed):
    assert _keys(indexed_db, "sql", "SELECT k FROM X WHERE li = [1, 2]") == (
        ["set"] if fixed else []
    )
