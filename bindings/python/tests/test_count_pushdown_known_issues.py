"""Engine findings about openCypher count push-downs and BYTE aggregates that reach Python users
(known-issues.md).

Each finding has a test of its documented workaround, which must keep passing, and a test of the
engine behavior itself that asserts the answer the row pipeline gives. While an engine bug is open
that test is a strict `xfail`, a tripwire as in `test_null_index_known_issues.py`: when the fix
reaches the wheel it starts passing and the suite fails, and the test is then converted to a plain
one.

Each test of a count first checks that the query as written is planned through the `COUNT
ANTI-JOIN CHAIN` push-down. The check calls `pytest.fail`, which the `xfail` marks do not absorb
(`raises=AssertionError`): a plan that stops using the push-down fails the suite instead of staying
an expected failure, so the tripwire cannot pass by comparing the row pipeline with itself.

Upstream: ArcadeData/arcadedb #9277 (the push-down counts the wrong vertices when the far end of the
chain has another label than the first hop's target; the change for #9203 let `id(a) <> id(b)` reach
it), #9278 (the push-down ignores the property map of the negated pattern's relationship), #9281
(`sum()` and `avg()` over a `BYTE` property raise `IllegalArgumentException`).
"""

import arcadedb_embedded as arcadedb
import pytest

# ---------------------------------------------------------------------------------------------
# #9277: another label at the far end of the chain
# ---------------------------------------------------------------------------------------------

CROSS_REASON = (
    "ArcadeData/arcadedb#9277: the COUNT ANTI-JOIN CHAIN push-down reuses a hop's neighbour map "
    "filtered for the wrong target label, so a chain whose far end has another label than the "
    "first hop's target counts 0 where the row pipeline counts 1"
)
cross_label_bug = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason=CROSS_REASON
)

CROSS_CHAIN = "MATCH (p1:Person)-[:KNOWS]-(p2:Person)-[:KNOWS]-(p3:Employee)-[:HAS_INTEREST]->(t:Tag) "


def _cross_label_graph(db):
    """One path (x0:Person)-(x1:Person)-(y0:Employee)-(t:Tag) in which x0 and y0 are not
    connected, so the path passes `NOT (p1)-[:KNOWS]-(p3)` and the count is 1."""
    for ddl in (
        "CREATE VERTEX TYPE Person",
        "CREATE VERTEX TYPE Employee",
        "CREATE VERTEX TYPE Tag",
        "CREATE EDGE TYPE KNOWS",
        "CREATE EDGE TYPE HAS_INTEREST",
    ):
        db.command("sql", ddl)
    with db.transaction():
        x0 = db.new_vertex("Person").set("id", 0).save()
        x1 = db.new_vertex("Person").set("id", 1).save()
        y0 = db.new_vertex("Employee").set("id", 0).save()
        tag = db.new_vertex("Tag").save()
        x0.new_edge("KNOWS", x1).save()
        x1.new_edge("KNOWS", y0).save()
        y0.new_edge("HAS_INTEREST", tag).save()


def _count(db, query):
    return db.query("opencypher", query).first().get("n")


def _require_anti_join_plan(db, query):
    plan = (
        db.query("opencypher", f"EXPLAIN {query}").first().get("executionPlanAsString")
    )
    if "ANTI-JOIN" not in plan:
        pytest.fail(
            f"{query!r} is no longer planned through the COUNT ANTI-JOIN CHAIN push-down; if the "
            f"engine now answers it another way, check the answer and update the test:\n{plan}"
        )


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("NOT (p1)-[:KNOWS]-(p3)", id="negated-pattern"),
        pytest.param("NOT (p1)-[:KNOWS]-(p3) AND p1 <> p3", id="node-inequality"),
        pytest.param("NOT (p1)-[:KNOWS]-(p3) AND id(p1) <> id(p3)", id="id-inequality"),
        pytest.param(
            "id(p1) <> id(p3) AND NOT (p1)-[:KNOWS]-(p3)", id="id-inequality-first"
        ),
    ],
)
@cross_label_bug
def test_negated_pattern_in_a_chain_with_another_label_at_the_far_end_counts_the_path(
    temp_db_path, where
):
    """#9277: the single path passes the negated pattern, so the count is 1, as the same WHERE
    after a `WITH` gives."""
    with arcadedb.create_database(temp_db_path) as db:
        _cross_label_graph(db)
        written = f"{CROSS_CHAIN}WHERE {where} RETURN count(*) AS n"  # nosec B608
        _require_anti_join_plan(db, written)
        assert _count(db, written) == 1


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("NOT (p1)-[:KNOWS]-(p3)", id="negated-pattern"),
        pytest.param("NOT (p1)-[:KNOWS]-(p3) AND p1 <> p3", id="node-inequality"),
        pytest.param("NOT (p1)-[:KNOWS]-(p3) AND id(p1) <> id(p3)", id="id-inequality"),
        pytest.param(
            "id(p1) <> id(p3) AND NOT (p1)-[:KNOWS]-(p3)", id="id-inequality-first"
        ),
    ],
)
def test_with_before_the_where_gives_the_row_pipeline_count(temp_db_path, where):
    """known-issues.md (#9277): `WITH p1, p2, p3, t` before the WHERE keeps the query off the
    push-down and gives the right count on every engine."""
    with arcadedb.create_database(temp_db_path) as db:
        _cross_label_graph(db)
        row_pipeline = f"{CROSS_CHAIN}WITH p1, p2, p3, t WHERE {where} RETURN count(*) AS n"  # nosec B608
        assert _count(db, row_pipeline) == 1


def test_a_chain_with_the_same_label_throughout_is_not_affected(temp_db_path):
    """#9277 needs a far end with another label: with the same label on every node the
    push-down answers as the row pipeline does."""
    with arcadedb.create_database(temp_db_path) as db:
        for ddl in (
            "CREATE VERTEX TYPE Person",
            "CREATE VERTEX TYPE Tag",
            "CREATE EDGE TYPE KNOWS",
            "CREATE EDGE TYPE HAS_INTEREST",
        ):
            db.command("sql", ddl)
        with db.transaction():
            x0 = db.new_vertex("Person").set("id", 0).save()
            x1 = db.new_vertex("Person").set("id", 1).save()
            x2 = db.new_vertex("Person").set("id", 2).save()
            tag = db.new_vertex("Tag").save()
            x0.new_edge("KNOWS", x1).save()
            x1.new_edge("KNOWS", x2).save()
            x2.new_edge("HAS_INTEREST", tag).save()
        chain = (
            "MATCH (p1:Person)-[:KNOWS]-(p2:Person)-[:KNOWS]-(p3:Person)"
            "-[:HAS_INTEREST]->(t:Tag) "
        )
        where = "NOT (p1)-[:KNOWS]-(p3) AND p1 <> p3"
        written = f"{chain}WHERE {where} RETURN count(*) AS n"  # nosec B608
        _require_anti_join_plan(db, written)
        row_pipeline = f"{chain}WITH p1, p2, p3, t WHERE {where} RETURN count(*) AS n"  # nosec B608
        assert _count(db, written) == _count(db, row_pipeline) == 1


# ---------------------------------------------------------------------------------------------
# #9278: the property map of the negated pattern's relationship
# ---------------------------------------------------------------------------------------------

EDGE_PROPERTY_REASON = (
    "ArcadeData/arcadedb#9278: the COUNT ANTI-JOIN CHAIN push-down drops the inline property map "
    "of the negated pattern's relationship, so NOT (x)-[:K {w: 1}]->(z) is counted as "
    "NOT (x)-[:K]->(z)"
)
edge_property_bug = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason=EDGE_PROPERTY_REASON
)

EDGE_CHAIN = "MATCH (x:P)-[:K]->(y:P)-[:K]->(z:P)-[:L]->(t:Q) "


def _edge_property_graph(db):
    """P x -K-> P y -K-> P z -L-> Q t, and one more edge x -K {w: 0}-> z."""
    for ddl in (
        "CREATE VERTEX TYPE P",
        "CREATE VERTEX TYPE Q",
        "CREATE EDGE TYPE K",
        "CREATE EDGE TYPE L",
    ):
        db.command("sql", ddl)
    with db.transaction():
        x = db.new_vertex("P").set("id", 0).save()
        y = db.new_vertex("P").set("id", 1).save()
        z = db.new_vertex("P").set("id", 2).save()
        t = db.new_vertex("Q").set("id", 0).save()
        x.new_edge("K", y).save()
        y.new_edge("K", z).save()
        z.new_edge("L", t).save()
        x.new_edge("K", z, w=0).save()


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("NOT (x)-[:K {w: 1}]->(z)", id="map"),
        pytest.param("NOT (x)-[:K {w: 1}]->(z) AND x <> z", id="map-and-inequality"),
    ],
)
@edge_property_bug
def test_negated_pattern_with_a_property_map_counts_the_path(temp_db_path, where):
    """#9278: the direct edge has w = 0, so no edge with w = 1 connects x to z and the path
    passes: the count is 1, as the same WHERE after a `WITH` gives."""
    with arcadedb.create_database(temp_db_path) as db:
        _edge_property_graph(db)
        written = f"{EDGE_CHAIN}WHERE {where} RETURN count(*) AS n"  # nosec B608
        _require_anti_join_plan(db, written)
        assert _count(db, written) == 1


@pytest.mark.parametrize(
    "where, expected",
    [
        pytest.param("NOT (x)-[:K {w: 1}]->(z)", 1, id="map-w1"),
        pytest.param(
            "NOT (x)-[:K {w: 1}]->(z) AND x <> z", 1, id="map-w1-and-inequality"
        ),
        pytest.param("NOT (x)-[:K {w: 0}]->(z)", 0, id="map-w0"),
        pytest.param("NOT (x)-[:K]->(z)", 0, id="no-map"),
    ],
)
def test_with_before_the_where_honours_the_property_map(temp_db_path, where, expected):
    """known-issues.md (#9278): after a `WITH` the negated pattern keeps its property map."""
    with arcadedb.create_database(temp_db_path) as db:
        _edge_property_graph(db)
        row_pipeline = f"{EDGE_CHAIN}WITH x, y, z, t WHERE {where} RETURN count(*) AS n"  # nosec B608
        assert _count(db, row_pipeline) == expected


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("NOT (x)-[:K {w: 0}]->(z)", id="map-w0"),
        pytest.param("NOT (x)-[:K]->(z)", id="no-map"),
    ],
)
def test_negated_pattern_the_map_does_not_change_is_counted_right(temp_db_path, where):
    """Where the dropped property map would not change the answer (the direct edge has w = 0,
    or there is no map) the push-down counts 0, as the row pipeline does."""
    with arcadedb.create_database(temp_db_path) as db:
        _edge_property_graph(db)
        written = f"{EDGE_CHAIN}WHERE {where} RETURN count(*) AS n"  # nosec B608
        _require_anti_join_plan(db, written)
        assert _count(db, written) == 0


# ---------------------------------------------------------------------------------------------
# #9281: sum() and avg() over a BYTE property
# ---------------------------------------------------------------------------------------------

BYTE_REASON = (
    "ArcadeData/arcadedb#9281: sum() and avg() over a BYTE property raise IllegalArgumentException "
    "(Cannot increment value ... class java.lang.Byte); Type.increment has no Byte case"
)
byte_aggregate_bug = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason=BYTE_REASON
)


def _byte_types(db):
    db.command("sql", "CREATE DOCUMENT TYPE T")
    db.command("sql", "CREATE PROPERTY T.b BYTE")
    db.command("sql", "CREATE PROPERTY T.s SHORT")
    db.command("sql", "CREATE VERTEX TYPE V")
    db.command("sql", "CREATE PROPERTY V.b BYTE")
    with db.transaction():
        for value in (100, 50):
            db.command(
                "sql", f"INSERT INTO T SET b = {value}, s = {value}"
            )  # nosec B608
            db.command("sql", f"CREATE VERTEX V SET b = {value}")  # nosec B608


def _result_or_error(db, language, query, reported_error="Cannot increment value"):
    """The value of `r`, or the text of the error the issue reports, so the tripwire's
    comparison fails with it as with a wrong value; any other exception fails the suite.
    """
    try:
        return db.query(language, query).first().get("r")
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is the reported one
        if reported_error not in str(exc):
            raise
        return f"raised: {exc}"


@pytest.mark.parametrize(
    "language, query, expected",
    [
        pytest.param("sql", "SELECT sum(b) AS r FROM T", 150, id="sql-sum"),
        pytest.param("sql", "SELECT avg(b) AS r FROM T", 75.0, id="sql-avg"),
        pytest.param(
            "opencypher", "MATCH (n:V) RETURN sum(n.b) AS r", 150, id="cypher-sum"
        ),
    ],
)
@byte_aggregate_bug
def test_sum_and_avg_over_a_byte_property(temp_db_path, language, query, expected):
    """#9281: the two rows hold 100 and 50, so the sum is 150 and the average 75.0, as for a
    SHORT property."""
    with arcadedb.create_database(temp_db_path) as db:
        _byte_types(db)
        assert _result_or_error(db, language, query) == expected


def test_sum_and_avg_over_a_short_property_are_not_affected(temp_db_path):
    """The same two values in a SHORT property sum and average as expected."""
    with arcadedb.create_database(temp_db_path) as db:
        _byte_types(db)
        assert _result_or_error(db, "sql", "SELECT sum(s) AS r FROM T") == 150
        assert _result_or_error(db, "sql", "SELECT avg(s) AS r FROM T") == 75.0


@pytest.mark.parametrize(
    "language, query, expected",
    [
        pytest.param("sql", "SELECT sum(b.asInteger()) AS r FROM T", 150, id="sql-sum"),
        pytest.param(
            "sql", "SELECT avg(b.asInteger()) AS r FROM T", 75.0, id="sql-avg"
        ),
        pytest.param(
            "opencypher",
            "MATCH (n:V) RETURN sum(toInteger(n.b)) AS r",
            150,
            id="cypher-sum",
        ),
    ],
)
def test_converting_a_byte_to_an_integer_before_the_aggregate_works(
    temp_db_path, language, query, expected
):
    """known-issues.md (#9281): `b.asInteger()` in SQL and `toInteger(n.b)` in openCypher
    give the aggregate a value type it can add."""
    with arcadedb.create_database(temp_db_path) as db:
        _byte_types(db)
        assert _result_or_error(db, language, query) == expected
