"""Engine findings about null keys and index lookups that reach Python users (known-issues.md).

Each finding has a test of its documented workaround, which must keep passing, and a test
of the engine behavior itself that asserts the answer a type without an index gives. While
an engine bug is open that test is a strict `xfail`, a tripwire as in
`test_declared_type_known_issues.py`: when the fix reaches the wheel it starts passing and
the suite fails, and the test is then converted to a plain one, as the tests of #9237 and
#9236 were when PR #9252 fixed them.

Each test first checks that the query it asserts on is planned through the index
(`FETCH FROM INDEX` in SQL, `NodeIndexSeek` in openCypher), so it cannot pass by comparing a
scan with a scan, and that the type without an index still gives the expected answer. These
checks call `pytest.fail`, which the `xfail` marks do not absorb (`raises=AssertionError`): a
plan that stops reading the index fails the suite instead of staying an expected failure. An
exception the issue reports is turned into an answer that fails the comparison; any other
exception fails the suite too.

Upstream: ArcadeData/arcadedb #9238 (SQL `p = ?` with the parameter bound to null returns the
records whose `p` is null or absent through an index that stores null keys, and an
`LSM_TREE` index with `NULL_STRATEGY ERROR` raises; open, PR #9246 pending), #9237 (`p IS NULL`
through a `UNIQUE` or `UNIQUE_HASH` index with `NULL_STRATEGY INDEX` returned one of the
records; fixed in 26.10.1 by PR #9252), #9236 (an openCypher equality on the first property
of a composite `HASH` index raised "does not support ordered iterations"; fixed in 26.10.1
by PR #9252, which plans such a query as a scan of the type).
"""

import arcadedb_embedded as arcadedb
import pytest

# id 1 has p = 1, id 2 has p = null, id 3 has no p; all have q = 7.
THREE_RECORDS = ("id = 1, p = 1, q = 7", "id = 2, p = null, q = 7", "id = 3, q = 7")


def _vertex_type(db, name, index=None, records=THREE_RECORDS, one_tx_each=False):
    db.command("sql", f"CREATE VERTEX TYPE {name}")
    for prop in ("id", "p", "q"):
        db.command("sql", f"CREATE PROPERTY {name}.{prop} INTEGER")
    if index:
        db.command("sql", f"CREATE INDEX ON {name} {index}")
    statements = [f"INSERT INTO {name} SET {r}" for r in records]  # nosec B608
    if one_tx_each:
        for statement in statements:
            with db.transaction():
                db.command("sql", statement)
    else:
        with db.transaction():
            for statement in statements:
                db.command("sql", statement)


def _ids(db, language, query, *args):
    return sorted(r.get("id") for r in db.query(language, query, *args))


def _answer(db, language, query, args, reported_error):
    """The ids the query returns or, when it raises the error the issue reports, that
    error's text, so a tripwire's comparison fails with it as with a wrong row."""
    try:
        return _ids(db, language, query, *args)
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is the reported one
        if reported_error not in str(exc):
            raise
        return f"raised: {exc}"


def _require_scan_answer(db, language, query, args, expected):
    answer = _ids(db, language, query, *args)
    if answer != expected:
        pytest.fail(
            f"the type without an index now returns {answer} for {query!r}, not "
            f"{expected}; the answer this tripwire compares with has changed"
        )


def _require_sql_index(db, query, args, index_name):
    plan = db.query("sql", f"EXPLAIN {query}", *args).first()
    plan = plan.get("executionPlanAsString")
    if f"FETCH FROM INDEX {index_name}[" not in plan:
        pytest.fail(
            f"{query!r} is no longer planned through index {index_name}; if the engine "
            f"now answers it another way, check the answer and convert the test:\n{plan}"
        )


def _require_cypher_index(db, query, args, index_name):
    plan = db.query("opencypher", f"EXPLAIN {query}", *args).first()
    plan = plan.get("executionPlanAsString")
    if f"NodeIndexSeek(n:{index_name}) [index={index_name}[" not in plan:
        pytest.fail(
            f"{query!r} is no longer planned as a seek of index {index_name}; if the "
            f"engine now answers it another way, check the answer and convert the "
            f"test:\n{plan}"
        )


# #9238 ------------------------------------------------------------------------------

NULL_EQUALITY_REASON = (
    "ArcadeData/arcadedb#9238: SQL p = ? bound to null returns the records whose p is "
    "null or absent through an index that stores null keys"
)
NULL_EQUALITY_SHAPES = [
    pytest.param("(p) NOTUNIQUE NULL_STRATEGY INDEX", "p = :x", id="lsm-index-named"),
    pytest.param(
        "(p) NOTUNIQUE NULL_STRATEGY INDEX", "p = ?", id="lsm-index-positional"
    ),
    pytest.param("(p) NOTUNIQUE_HASH NULL_STRATEGY INDEX", "p = :x", id="hash-index"),
    pytest.param("(q, p) NOTUNIQUE", "q = 7 AND p = :x", id="composite-default-skip"),
    pytest.param("(p, q) NOTUNIQUE", "p = :x", id="composite-first-property"),
]


def _bound_to_none(condition):
    return ({"x": None},) if ":x" in condition else (None,)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=NULL_EQUALITY_REASON)
@pytest.mark.parametrize("index, condition", NULL_EQUALITY_SHAPES)
def test_null_parameter_equality_through_an_index_matches_nothing(
    temp_db_path, index, condition
):
    """#9238: an equality with a null value matches no record, through the index as in
    the scan."""
    args = _bound_to_none(condition)
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Scan")
        _vertex_type(db, "Indexed", index)
        query = f"SELECT id FROM Indexed WHERE {condition}"  # nosec B608 - fixed names
        _require_sql_index(db, query, args, "Indexed")
        scan = f"SELECT id FROM Scan WHERE {condition}"  # nosec B608 - fixed names
        _require_scan_answer(db, "sql", scan, args, [])
        assert _ids(db, "sql", query, *args) == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="ArcadeData/arcadedb#9238: through an LSM_TREE index with NULL_STRATEGY ERROR, "
    "p = ? bound to null raises 'Indexed key ... cannot be NULL' instead of matching nothing",
)
def test_null_parameter_equality_through_an_error_index_matches_nothing(temp_db_path):
    """#9238: the refusal of a null key is for writes; a lookup with null matches nothing.
    The type holds only the record with p = 1, the only one such an index can store."""
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(
            db,
            "Indexed",
            "(p) NOTUNIQUE NULL_STRATEGY ERROR",
            records=THREE_RECORDS[:1],
        )
        query = "SELECT id FROM Indexed WHERE p = :x"
        _require_sql_index(db, query, ({"x": None},), "Indexed")
        assert (
            _answer(db, "sql", query, ({"x": None},), "cannot be NULL") == []
        ), "the lookup raised instead of matching nothing"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=NULL_EQUALITY_REASON)
@pytest.mark.parametrize(
    "index, condition",
    [
        pytest.param("(p) NOTUNIQUE NULL_STRATEGY INDEX", "p = :x", id="lsm-index"),
        pytest.param("(q, p) NOTUNIQUE", "q = 7 AND p = :x", id="composite"),
    ],
)
def test_delete_with_a_null_parameter_through_an_index_deletes_nothing(
    temp_db_path, index, condition
):
    """#9238: the DELETE removes the records the SELECT with the same WHERE returns."""
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Indexed", index)
        query = f"SELECT id FROM Indexed WHERE {condition}"  # nosec B608 - fixed names
        _require_sql_index(db, query, ({"x": None},), "Indexed")
        with db.transaction():
            delete = f"DELETE FROM Indexed WHERE {condition}"  # nosec B608
            db.command("sql", delete, {"x": None})
        assert _ids(db, "sql", "SELECT id FROM Indexed") == [1, 2, 3]


@pytest.mark.parametrize(
    "index, prefix",
    [
        pytest.param("(p) NOTUNIQUE NULL_STRATEGY INDEX", "", id="lsm-index"),
        pytest.param("(p) NOTUNIQUE_HASH NULL_STRATEGY INDEX", "", id="hash-index"),
        pytest.param("(q, p) NOTUNIQUE", "q = 7 AND ", id="composite-default-skip"),
    ],
)
def test_is_null_or_null_safe_equality_workaround_for_a_null_parameter(
    temp_db_path, index, prefix
):
    """known-issues.md: do not bind None to `=`. `p IS NULL`, and `p <=> :x` with None or a
    value, return what the scan returns; so does the literal `p = null`, which matches
    nothing, as does skipping the query."""
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Scan")
        _vertex_type(db, "Indexed", index)
        for condition, args, expected in (
            (f"{prefix}p IS NULL", (), [2, 3]),
            (f"{prefix}p <=> :x", ({"x": None},), [2, 3]),
            (f"{prefix}p <=> :x", ({"x": 1},), [1]),
            (f"{prefix}p = null", (), []),
            (f"{prefix}p = :x", ({"x": None},), []),  # the scan; skip the query
        ):
            scan = f"SELECT id FROM Scan WHERE {condition}"  # nosec B608 - fixed names
            assert _ids(db, "sql", scan, *args) == expected, condition
            if condition.endswith("p = :x"):
                continue  # the bug itself; the tripwires above cover it
            query = f"SELECT id FROM Indexed WHERE {condition}"  # nosec B608
            assert _ids(db, "sql", query, *args) == expected, condition


# #9237 ------------------------------------------------------------------------------

# id 1 has p = 1, ids 2 and 4 have p = null, id 3 has no p.
FOUR_RECORDS = ("id = 1, p = 1", "id = 2, p = null", "id = 3", "id = 4, p = null")


@pytest.mark.parametrize("kind", ["UNIQUE", "UNIQUE_HASH"])
def test_is_null_through_a_unique_index_returns_every_null_record(temp_db_path, kind):
    """#9237, fixed in 26.10.1: `p IS NULL` returns ids 2, 3, and 4 through the index as in
    the scan, and `count(*)` counts 3. The plan check keeps the query on the index, so the
    test cannot pass by comparing a scan with a scan."""
    with arcadedb.create_database(temp_db_path) as db:
        index = f"(p) {kind} NULL_STRATEGY INDEX"
        _vertex_type(db, "Scan", records=FOUR_RECORDS, one_tx_each=True)
        _vertex_type(db, "Indexed", index, records=FOUR_RECORDS, one_tx_each=True)
        query = "SELECT id FROM Indexed WHERE p IS NULL"
        _require_sql_index(db, query, (), "Indexed")
        scan = "SELECT id FROM Scan WHERE p IS NULL"
        _require_scan_answer(db, "sql", scan, (), [2, 3, 4])
        assert _ids(db, "sql", query) == [2, 3, 4]
        count = "SELECT count(*) AS n FROM Indexed WHERE p IS NULL"
        assert db.query("sql", count).first().get("n") == 3


@pytest.mark.parametrize("kind", ["UNIQUE", "UNIQUE_HASH"])
def test_null_safe_equality_workaround_for_is_null_on_a_unique_index(
    temp_db_path, kind
):
    """known-issues.md: `p <=> null` returns every record whose p is null or absent, on
    a unique index with NULL_STRATEGY INDEX as in the scan; so does openCypher."""
    with arcadedb.create_database(temp_db_path) as db:
        index = f"(p) {kind} NULL_STRATEGY INDEX"
        _vertex_type(db, "Indexed", index, records=FOUR_RECORDS, one_tx_each=True)
        assert _ids(db, "sql", "SELECT id FROM Indexed WHERE p <=> null") == [2, 3, 4]
        count = "SELECT count(*) AS n FROM Indexed WHERE p <=> null"
        assert db.query("sql", count).first().get("n") == 3
        cypher = "MATCH (n:Indexed) WHERE n.p IS NULL RETURN n.id AS id"
        assert _ids(db, "opencypher", cypher) == [2, 3, 4]


# #9236 ------------------------------------------------------------------------------

# id 1 has (p, q) = (1, 5), id 2 has (2, 6).
TWO_RECORDS = ("id = 1, p = 1, q = 5", "id = 2, p = 2, q = 6")
PREFIX_QUERIES = [
    pytest.param("MATCH (n:{t}) WHERE n.p = 1 RETURN n.id AS id", (), [1], id="where"),
    pytest.param("MATCH (n:{t} {{p: 1}}) RETURN n.id AS id", (), [1], id="map"),
    pytest.param(
        "MATCH (n:{t}) WHERE n.p IN [1, 2] RETURN n.id AS id", (), [1, 2], id="in"
    ),
]


@pytest.mark.parametrize("kind", ["NOTUNIQUE_HASH", "UNIQUE_HASH"])
@pytest.mark.parametrize("query, args, expected", PREFIX_QUERIES)
def test_cypher_equality_on_the_first_property_of_a_composite_hash_index(
    temp_db_path, kind, query, args, expected
):
    """#9236, fixed in 26.10.1: the MATCH returns what it returns on the type without an
    index. A hash index answers an exact key only, so the planner reads the type for a
    query that gives a part of the key (`NodeByLabelScan`, no index seek); before 26.10.1
    it sought the hash index and the read raised "does not support ordered iterations".
    """
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Scan", records=TWO_RECORDS)
        _vertex_type(db, "Hashed", f"(p, q) {kind}", records=TWO_RECORDS)
        _require_scan_answer(db, "opencypher", query.format(t="Scan"), args, expected)
        assert _ids(db, "opencypher", query.format(t="Hashed"), *args) == expected


@pytest.mark.parametrize("kind", ["NOTUNIQUE_HASH", "UNIQUE_HASH"])
@pytest.mark.parametrize(
    "args, expected",
    [
        pytest.param({"p": 1, "q": 5}, [1], id="value"),
        pytest.param({"p": 1, "q": None}, [], id="null-second-parameter"),
    ],
)
def test_cypher_equality_on_every_property_of_a_composite_hash_index(
    temp_db_path, kind, args, expected
):
    """#9236, fixed in 26.10.1: with every property of the key given, openCypher still seeks
    the hash index, and a `None` for the second property matches nothing, as in the scan. The
    plan check keeps the query on the index, so the test cannot pass by comparing a scan
    with a scan."""
    query = "MATCH (n:{t}) WHERE n.p = $p AND n.q = $q RETURN n.id AS id"
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Scan", records=TWO_RECORDS)
        _vertex_type(db, "Hashed", f"(p, q) {kind}", records=TWO_RECORDS)
        _require_cypher_index(db, query.format(t="Hashed"), (args,), "Hashed")
        _require_scan_answer(
            db, "opencypher", query.format(t="Scan"), (args,), expected
        )
        assert _ids(db, "opencypher", query.format(t="Hashed"), args) == expected


@pytest.mark.parametrize("kind", ["NOTUNIQUE_HASH", "UNIQUE_HASH"])
def test_sql_or_a_full_key_or_lsm_tree_workaround_for_a_hash_prefix(temp_db_path, kind):
    """known-issues.md: SQL answers the prefix on the hash index's type, openCypher answers
    it on a composite LSM_TREE (NOTUNIQUE) index, and openCypher with every property of the
    key uses the hash index."""
    with arcadedb.create_database(temp_db_path) as db:
        _vertex_type(db, "Hashed", f"(p, q) {kind}", records=TWO_RECORDS)
        _vertex_type(db, "Lsm", "(p, q) NOTUNIQUE", records=TWO_RECORDS)
        assert _ids(db, "sql", "SELECT id FROM Hashed WHERE p = ?", 1) == [1]
        assert _ids(db, "sql", "SELECT id FROM Hashed WHERE p IN [1, 2]") == [1, 2]
        for query, expected in (
            ("MATCH (n:Lsm) WHERE n.p = 1 RETURN n.id AS id", [1]),
            ("MATCH (n:Lsm) WHERE n.p IN [1, 2] RETURN n.id AS id", [1, 2]),
        ):
            _require_cypher_index(db, query, (), "Lsm")
            assert _ids(db, "opencypher", query) == expected
        full_key = "MATCH (n:Hashed) WHERE n.p = $p AND n.q = $q RETURN n.id AS id"
        _require_cypher_index(db, full_key, ({"p": 1, "q": 5},), "Hashed")
        assert _ids(db, "opencypher", full_key, {"p": 1, "q": 5}) == [1]
