"""Engine findings about openCypher counts over light edges and over Graph Analytical Views that
reach Python users (known-issues.md), both open upstream.

Each finding has plain tests of its documented workarounds, which must keep passing, plain tests of
the cases that are not affected, and a test of the engine behavior itself that asserts the answer
the row pipeline gives. While an engine bug is open that test is a strict `xfail`, a tripwire as in
`test_count_pushdown_known_issues.py`: when the fix reaches the wheel it starts passing and the
suite fails, and the test is then converted to a plain one.

Each tripwire first checks, with `pytest.fail`, which the `xfail` marks do not absorb
(`raises=AssertionError`), that the query is still planned the way the bug needs and that the data
is there. For #9378 that is the `CONSTANT COUNT` plan, and for #9377 a plan that reads the view. A
plan that stops doing so fails the suite instead of staying an expected failure, so a tripwire
cannot pass by comparing the row pipeline with itself.

Upstream: ArcadeData/arcadedb #9378 (a one-hop `count(*)` answers 0 over the edges that
`GraphBatch.withLightEdges(true)` wrote into an edge type that is not declared `LIGHTWEIGHT`: the
count push-down plans `CONSTANT COUNT` because the type holds no records), #9377 (a pattern
predicate over an edge type that a Graph Analytical View does not list is evaluated against the
view, where that type has no edges, so `NOT (a)-[:F]->(b)` excludes nothing and `(a)-[:F]->(b)`
matches nothing in an aggregate). Both are measured on the 26.10.1 wheel and on upstream main
246821a605.
"""

import time

import arcadedb_embedded as arcadedb
import pytest

# ---------------------------------------------------------------------------------------------
# #9378: a one-hop count over light edges in an edge type that is not declared LIGHTWEIGHT
# ---------------------------------------------------------------------------------------------

LIGHT_REASON = (
    "ArcadeData/arcadedb#9378: a one-hop count(*) over edges that GraphBatch wrote as light edges "
    "(light_edges=True) into an edge type not declared LIGHTWEIGHT answers 0 (CONSTANT COUNT: the "
    "type holds no records) where the row pipeline answers 2"
)
light_edge_bug = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason=LIGHT_REASON
)

ONE_HOP = "MATCH (a:V)-[:E]->(b:V) RETURN count(*) AS n"


def _light_edge_graph(db, edge_ddl="CREATE EDGE TYPE E", **batch_options):
    """Vertices a, b, c of type V and the edges a -E-> b and b -E-> c, loaded with a
    `graph_batch`, so two edges hang between three vertices."""
    db.command("sql", "CREATE VERTEX TYPE V")
    db.command("sql", edge_ddl)
    with db.graph_batch(**batch_options) as batch:
        a, b, c = batch.create_vertices("V", 3)
        batch.new_edge(a, "E", b)
        batch.new_edge(b, "E", c)


def _count(db, query, language="opencypher"):
    return db.query(language, query).first().get("n")


def _require_the_edges_are_there(db):
    """The edges are in the graph: the rows, the two-hop count and the SQL traversal see them."""
    rows = len(db.query("opencypher", "MATCH (a:V)-[:E]->(b:V) RETURN a, b").to_list())
    sql = _count(
        db, "SELECT count(*) AS n FROM (SELECT expand(out('E')) FROM V)", "sql"
    )
    if (rows, sql) != (2, 2):
        pytest.fail(
            f"the edges are not all there: {rows} rows, {sql} by out('E'), want 2 and 2"
        )


def _require_constant_count_plan(db):
    plan = (
        db.query("opencypher", f"EXPLAIN {ONE_HOP}")
        .first()
        .get("executionPlanAsString")
    )
    if "CONSTANT COUNT" not in plan:
        pytest.fail(
            f"{ONE_HOP!r} is no longer planned as CONSTANT COUNT; if the engine now answers it "
            f"another way, check the answer and update the test:\n{plan}"
        )


@light_edge_bug
def test_one_hop_count_over_light_edges_in_an_undeclared_type_counts_the_edges(
    temp_db_path,
):
    """#9378: two light edges in a type without `LIGHTWEIGHT`, so the one-hop count is 2, as the
    rows, the two-hop count and `out('E')` show."""
    with arcadedb.create_database(temp_db_path) as db:
        _light_edge_graph(db, light_edges=True)
        _require_the_edges_are_there(db)
        _require_constant_count_plan(db)
        assert _count(db, ONE_HOP) == 2


def test_light_edges_in_an_undeclared_type_are_in_the_graph(temp_db_path):
    """#9378: what is not wrong. The type holds no records, but the rows, the two-hop count, and the
    SQL traversal over the same edges give the right numbers."""
    with arcadedb.create_database(temp_db_path) as db:
        _light_edge_graph(db, light_edges=True)
        _require_the_edges_are_there(db)
        assert _count(db, "SELECT count(*) AS n FROM E", "sql") == 0
        two_hop = "MATCH (a:V)-[:E]->(b:V)-[:E]->(c:V) RETURN count(*) AS n"
        assert _count(db, two_hop) == 1


@pytest.mark.parametrize(
    "edge_ddl, batch_options",
    [
        pytest.param(
            "CREATE EDGE TYPE E LIGHTWEIGHT", {"light_edges": True}, id="declared-light"
        ),
        pytest.param(
            "CREATE EDGE TYPE E LIGHTWEIGHT",
            {"light_edges": False},
            id="declared-regular",
        ),
        pytest.param("CREATE EDGE TYPE E", {"light_edges": False}, id="flag-false"),
        pytest.param("CREATE EDGE TYPE E", {}, id="flag-not-passed"),
    ],
)
def test_one_hop_count_where_the_edges_and_the_type_agree(
    temp_db_path, edge_ddl, batch_options
):
    """known-issues.md (#9378): declaring the type `LIGHTWEIGHT` before the load, or not passing
    `light_edges=True`, gives the right one-hop count."""
    with arcadedb.create_database(temp_db_path) as db:
        _light_edge_graph(db, edge_ddl, **batch_options)
        _require_the_edges_are_there(db)
        assert _count(db, ONE_HOP) == 2


@pytest.mark.parametrize(
    "query",
    [
        pytest.param(
            "MATCH (a:V)-[:E]->(b:V) WITH a, b RETURN count(*) AS n", id="with"
        ),
        pytest.param(
            "MATCH (a:V)-[:E]->(b:V) RETURN count(b) AS n", id="count-of-a-node"
        ),
        pytest.param(
            "MATCH (a:V)-[r:E]->(b:V) RETURN count(r) AS n",
            id="count-of-the-relationship",
        ),
    ],
)
def test_other_ways_to_count_light_edges_already_loaded(temp_db_path, query):
    """known-issues.md (#9378): on a graph loaded with `light_edges=True` into an undeclared type,
    a `WITH a, b` before the count, `count(b)`, or `count(r)` over a named relationship is not
    planned as `CONSTANT COUNT` and gives the right count."""
    with arcadedb.create_database(temp_db_path) as db:
        _light_edge_graph(db, light_edges=True)
        _require_the_edges_are_there(db)
        plan = (
            db.query("opencypher", f"EXPLAIN {query}")
            .first()
            .get("executionPlanAsString")
        )
        assert "CONSTANT COUNT" not in plan
        assert _count(db, query) == 2


# ---------------------------------------------------------------------------------------------
# #9377: a pattern predicate over an edge type that a Graph Analytical View does not list
# ---------------------------------------------------------------------------------------------

VIEW_REASON = (
    "ArcadeData/arcadedb#9377: a pattern predicate over an edge type the Graph Analytical View does "
    "not list is evaluated against the view, so an aggregate over NOT (a)-[:F]->(b) excludes nothing "
    "and over (a)-[:F]->(b) matches nothing"
)
view_edge_bug = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason=VIEW_REASON
)

VIEW_CHAIN = "MATCH (a:V)-[:E]->(b:V) "


def _view_graph(db, view_edge_types):
    """Vertices x, y, z of type V and the edges x -E-> y, x -F-> y, y -E-> z, then a Graph
    Analytical View over V and `view_edge_types` (None for no view), waited on until it is READY.
    """
    for ddl in ("CREATE VERTEX TYPE V", "CREATE EDGE TYPE E", "CREATE EDGE TYPE F"):
        db.command("sql", ddl)
    with db.transaction():
        x = db.new_vertex("V").save()
        y = db.new_vertex("V").save()
        z = db.new_vertex("V").save()
        x.new_edge("E", y).save()
        x.new_edge("F", y).save()
        y.new_edge("E", z).save()
    if view_edge_types is None:
        return
    db.command(
        "sql",
        f"CREATE GRAPH ANALYTICAL VIEW gav VERTEX TYPES (V) EDGE TYPES ({view_edge_types}) "
        "UPDATE MODE OFF",
    )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        row = db.query(
            "sql", "SELECT FROM schema:graphAnalyticalViews WHERE name = ?", "gav"
        ).first()
        if row is not None and row.get("status") == "READY":
            return
        time.sleep(0.02)
    pytest.fail("the Graph Analytical View did not reach READY in 120 s")


def _require_view_plan(db, query):
    plan = (
        db.query("opencypher", f"EXPLAIN {query}").first().get("executionPlanAsString")
    )
    if "GAV" not in plan:
        pytest.fail(
            f"{query!r} is no longer planned through the view; if the engine now answers it "
            f"another way, check the answer and update the test:\n{plan}"
        )


@view_edge_bug
@pytest.mark.parametrize(
    "where, aggregate",
    [
        pytest.param("WHERE NOT (a)-[:F]->(b)", "count(*)", id="negated-count-star"),
        pytest.param("WHERE (a)-[:F]->(b)", "count(*)", id="positive-count-star"),
        pytest.param(
            "WHERE NOT (a)-[:F]->(b)", "count(a)", id="negated-count-of-a-node"
        ),
    ],
)
def test_pattern_predicate_over_an_edge_type_the_view_does_not_list(
    temp_db_path, where, aggregate
):
    """#9377: only the pair (x, y) has an F edge, so the negated form keeps the pair (y, z) and the
    positive form keeps (x, y): the count is 1 either way, as with no view."""
    with arcadedb.create_database(temp_db_path) as db:
        _view_graph(db, "E")
        query = (
            f"{VIEW_CHAIN}{where} RETURN {aggregate} AS n"  # nosec B608 - fixed text
        )
        _require_view_plan(db, query)
        assert _count(db, query) == 1


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("WHERE NOT (a)-[:F]->(b)", id="negated"),
        pytest.param("WHERE (a)-[:F]->(b)", id="positive"),
    ],
)
def test_with_before_the_where_gives_the_row_pipeline_count_over_a_view(
    temp_db_path, where
):
    """known-issues.md (#9377): `WITH a, b` before the WHERE keeps the query on the row pipeline,
    which counts the right number with the view that does not list F."""
    with arcadedb.create_database(temp_db_path) as db:
        _view_graph(db, "E")
        written = f"{VIEW_CHAIN}{where} RETURN count(*) AS n"  # nosec B608 - fixed text
        _require_view_plan(db, written)
        with_form = f"{VIEW_CHAIN}WITH a, b {where} RETURN count(*) AS n"  # nosec B608
        assert _count(db, with_form) == 1


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("WHERE NOT (a)-[:F]->(b)", id="negated"),
        pytest.param("WHERE (a)-[:F]->(b)", id="positive"),
    ],
)
def test_a_view_that_lists_the_predicates_edge_type_counts_right(temp_db_path, where):
    """known-issues.md (#9377): a view that lists F as well as E still serves the query, and the
    count is right."""
    with arcadedb.create_database(temp_db_path) as db:
        _view_graph(db, "E, F")
        query = f"{VIEW_CHAIN}{where} RETURN count(*) AS n"  # nosec B608 - fixed text
        _require_view_plan(db, query)
        assert _count(db, query) == 1


@pytest.mark.parametrize(
    "where",
    [
        pytest.param("WHERE NOT (a)-[:F]->(b)", id="negated"),
        pytest.param("WHERE (a)-[:F]->(b)", id="positive"),
    ],
)
def test_the_same_counts_with_no_view_are_right(temp_db_path, where):
    """#9377 needs a view: with none, the same query counts 1."""
    with arcadedb.create_database(temp_db_path) as db:
        _view_graph(db, None)
        query = f"{VIEW_CHAIN}{where} RETURN count(*) AS n"  # nosec B608 - fixed text
        assert _count(db, query) == 1


def test_a_query_that_returns_rows_is_not_affected_by_the_view(temp_db_path):
    """#9377 is about an aggregate: the same negated query returning rows, over the view that does
    not list F, returns the one pair (y, z)."""
    with arcadedb.create_database(temp_db_path) as db:
        _view_graph(db, "E")
        rows = db.query(
            "opencypher", f"{VIEW_CHAIN}WHERE NOT (a)-[:F]->(b) RETURN a, b"
        ).to_list()
        assert len(rows) == 1
