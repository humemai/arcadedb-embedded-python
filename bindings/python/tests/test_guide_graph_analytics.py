"""Every example in docs/guide/graph-analytics.md, run and asserted (#388).

Each statement a test sends must appear verbatim in the guide, so an edit to
the page that this file does not follow fails here instead of drifting.
Everything below was measured on the 26.10.2 engine.
"""

import time
from pathlib import Path

import arcadedb_embedded as arcadedb
import pytest

DOC = (
    Path(__file__).resolve().parents[1] / "docs" / "guide" / "graph-analytics.md"
).read_text(encoding="utf-8")

NAMES = ["ada", "bob", "cy", "dee", "eve", "fay"]
EDGES = [
    ("ada", "bob", 1.0),
    ("bob", "cy", 1.0),
    ("ada", "cy", 5.0),
    ("cy", "dee", 1.0),
    ("dee", "ada", 1.0),
    ("eve", "fay", 1.0),
]
CREATE_VIEW = (
    "CREATE GRAPH ANALYTICAL VIEW social VERTEX TYPES (Person) EDGE TYPES (Follows) "
    "PROPERTIES (name) EDGE PROPERTIES (weight) UPDATE MODE SYNCHRONOUS"
)
VIEW_STATE = (
    "SELECT status, nodeCount, edgeCount, updateMode "
    "FROM schema:graphAnalyticalViews WHERE name = 'social'"
)


def doc(statement):
    """Return `statement` after checking that the guide shows it."""
    assert statement in DOC, f"not in docs/guide/graph-analytics.md: {statement}"
    return statement


def view_state(db):
    return db.query("sql", doc(VIEW_STATE)).first().to_dict()


def wait_for(db, **expected):
    """Poll the view row until it shows `expected` (a build runs in the background)."""
    deadline = time.time() + 30
    state = view_state(db)
    while time.time() < deadline:
        state = view_state(db)
        if all(state.get(k) == v for k, v in expected.items()):
            return state
        time.sleep(0.05)
    raise AssertionError(f"view never reached {expected}: {state}")


def cypher_raw(db, statement):
    return [row.to_dict() for row in db.query("opencypher", statement)]


def cypher(db, statement):
    return [row.to_dict() for row in db.query("opencypher", doc(statement))]


@pytest.fixture
def db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as database:
        database.command("sql", doc("CREATE VERTEX TYPE Person"))
        database.command("sql", doc("CREATE EDGE TYPE Follows"))
        database.command("sql", doc("CREATE PROPERTY Follows.weight DOUBLE"))
        with database.transaction():
            for name in NAMES:
                database.command("sql", doc("CREATE VERTEX Person SET name = ?"), name)
            for src, dst, weight in EDGES:
                database.command(
                    "sql",
                    doc(
                        "CREATE EDGE Follows FROM (SELECT FROM Person WHERE name = ?) "
                        "TO (SELECT FROM Person WHERE name = ?) SET weight = ?"
                    ),
                    src,
                    dst,
                    weight,
                )
        yield database


@pytest.fixture
def view_db(db):
    row = db.command("sql", doc(CREATE_VIEW)).first()
    assert row.to_dict() == {
        "operation": "create graph analytical view",
        "name": "social",
        "created": True,
    }
    wait_for(db, status="READY")
    return db


def test_create_view_and_read_its_state(db):
    db.command("sql", doc(CREATE_VIEW))
    state = wait_for(db, status="READY")
    assert state == {
        "status": "READY",
        "nodeCount": 6,
        "edgeCount": 6,
        "updateMode": "SYNCHRONOUS",
    }
    memory = db.query(
        "sql", "SELECT memoryUsageBytes FROM schema:graphAnalyticalViews"
    ).first()
    assert memory.get("memoryUsageBytes") > 0


def test_pagerank(view_db):
    query = (
        "CALL algo.pagerank() YIELD node, score "
        "RETURN node.name AS name, round(score * 1000) / 1000.0 AS score "
        "ORDER BY score DESC, name"
    )
    rows = cypher(view_db, query)
    assert [(r["name"], r["score"]) for r in rows] == [
        ("cy", 0.259),
        ("dee", 0.254),
        ("ada", 0.25),
        ("bob", 0.14),
        ("fay", 0.063),
        ("eve", 0.034),
    ]
    # The options go in one map; a tighter run changes the digits, not the order.
    tuned = cypher(
        view_db,
        "CALL algo.pagerank({dampingFactor: 0.9, maxIterations: 50}) "
        "YIELD node, score RETURN node.name AS name ORDER BY score DESC, name LIMIT 1",
    )
    assert tuned == [{"name": "cy"}]


def test_same_answers_with_and_without_the_view(db):
    query = (
        "CALL algo.pagerank() YIELD node, score "
        "RETURN node.name AS name, round(score * 1000) / 1000.0 AS score "
        "ORDER BY score DESC, name"
    )
    before = cypher(db, query)
    db.command("sql", doc(CREATE_VIEW))
    wait_for(db, status="READY")
    with_view = cypher(db, query)
    assert db.command(
        "sql", doc("DROP GRAPH ANALYTICAL VIEW social")
    ).first().to_dict() == {
        "operation": "drop graph analytical view",
        "name": "social",
        "dropped": True,
    }
    assert db.query("sql", "SELECT FROM schema:graphAnalyticalViews").to_list() == []
    after = cypher(db, query)
    assert before == with_view == after


def test_connected_components(view_db):
    weak = cypher(
        view_db,
        "CALL algo.wcc() YIELD node, componentId "
        "RETURN componentId, collect(node.name) AS members",
    )
    assert sorted(sorted(r["members"]) for r in weak) == [
        ["ada", "bob", "cy", "dee"],
        ["eve", "fay"],
    ]
    strong = cypher(
        view_db,
        "CALL algo.scc() YIELD node, componentId "
        "RETURN componentId, collect(node.name) AS members",
    )
    assert sorted(sorted(r["members"]) for r in strong) == [
        ["ada", "bob", "cy", "dee"],
        ["eve"],
        ["fay"],
    ]


def test_bfs(view_db):
    rows = cypher(
        view_db,
        "MATCH (a:Person {name: 'ada'}) CALL algo.bfs(a, 'Follows', 'OUT', 3) "
        "YIELD node, depth RETURN node.name AS name, depth ORDER BY depth, name",
    )
    assert rows == [
        {"name": "bob", "depth": 1},
        {"name": "cy", "depth": 1},
        {"name": "dee", "depth": 2},
    ]


def test_dijkstra(view_db):
    rows = cypher(
        view_db,
        "MATCH (a:Person {name: 'ada'}), (d:Person {name: 'dee'}) "
        "CALL algo.dijkstra(a, d, 'Follows', 'weight', 'OUT') YIELD path, weight "
        "RETURN [n IN nodes(path) | n.name] AS names, weight",
    )
    # ada -> cy costs 5 directly and 2 through bob, so the cheap path wins.
    assert rows == [{"names": ["ada", "bob", "cy", "dee"], "weight": 3.0}]


def test_degree_and_triangles(view_db):
    degrees = cypher(
        view_db,
        "CALL algo.degree() YIELD node, inDegree, outDegree "
        "RETURN node.name AS name, inDegree, outDegree ORDER BY name",
    )
    assert [(r["name"], r["inDegree"], r["outDegree"]) for r in degrees] == [
        ("ada", 1, 2),
        ("bob", 1, 1),
        ("cy", 2, 1),
        ("dee", 1, 1),
        ("eve", 0, 1),
        ("fay", 1, 0),
    ]
    triangles = cypher(
        view_db,
        "CALL algo.triangleCount() YIELD node, triangles "
        "RETURN node.name AS name, triangles ORDER BY name",
    )
    assert [(r["name"], r["triangles"]) for r in triangles] == [
        ("ada", 2),
        ("bob", 1),
        ("cy", 2),
        ("dee", 1),
        ("eve", 0),
        ("fay", 0),
    ]


def test_louvain_and_betweenness(view_db):
    communities = cypher(
        view_db,
        "CALL algo.louvain() YIELD node, communityId "
        "RETURN communityId, collect(node.name) AS members",
    )
    groups = [set(r["members"]) for r in communities]
    # eve and fay form their own community: no edge joins them to the other four.
    assert {"eve", "fay"} in groups
    assert all(not ({"eve", "fay"} & g) for g in groups if g != {"eve", "fay"})
    scores = cypher(
        view_db,
        "CALL algo.betweenness() YIELD node, score "
        "RETURN node.name AS name, score ORDER BY score DESC, name",
    )
    by_name = {r["name"]: r["score"] for r in scores}
    assert by_name["eve"] == by_name["fay"] == 0.0
    assert min(by_name[n] for n in ["ada", "bob", "cy", "dee"]) >= 0.0
    assert max(by_name.values()) == pytest.approx(0.15)


def test_update_mode_synchronous_then_alter_to_off_and_rebuild(view_db):
    with view_db.transaction():
        view_db.command("sql", "CREATE VERTEX Person SET name = 'gus'")
    # SYNCHRONOUS: the commit that returned is already in the view.
    assert view_state(view_db) == {
        "status": "READY",
        "nodeCount": 7,
        "edgeCount": 6,
        "updateMode": "SYNCHRONOUS",
    }

    altered = view_db.command(
        "sql", doc("ALTER GRAPH ANALYTICAL VIEW social UPDATE MODE OFF")
    ).first()
    assert altered.to_dict() == {
        "operation": "alter graph analytical view",
        "name": "social",
        "updateMode": "OFF",
    }
    with view_db.transaction():
        view_db.command("sql", "CREATE VERTEX Person SET name = 'hal'")
    # OFF: the view is marked STALE and keeps its old counts ...
    stale = view_state(view_db)
    assert stale["status"] == "STALE"
    assert stale["nodeCount"] == 7
    # ... yet a whole-graph call still answers from the live graph (it scans).
    count = "CALL algo.wcc() YIELD node RETURN count(node) AS n"
    assert cypher(view_db, count) == [{"n": 8}]

    rebuilt = view_db.command(
        "sql", doc("REBUILD GRAPH ANALYTICAL VIEW social")
    ).first()
    assert rebuilt.get("status") == "READY"
    state = wait_for(view_db, status="READY")
    assert state["nodeCount"] == 8
    assert cypher(view_db, count) == [{"n": 8}]


def test_update_mode_asynchronous_catches_up(db):
    db.command(
        "sql",
        doc(
            "CREATE GRAPH ANALYTICAL VIEW social VERTEX TYPES (Person) "
            "EDGE TYPES (Follows) UPDATE MODE ASYNCHRONOUS COMPACTION THRESHOLD 500"
        ),
    )
    wait_for(db, status="READY", nodeCount=6)
    with db.transaction():
        db.command("sql", "CREATE VERTEX Person SET name = 'gus'")
        db.command(
            "sql",
            "CREATE EDGE Follows FROM (SELECT FROM Person WHERE name = 'gus') "
            "TO (SELECT FROM Person WHERE name = 'ada')",
        )
    # ASYNCHRONOUS: the view folds the change in after the commit returned.
    state = wait_for(db, status="READY", nodeCount=7, edgeCount=7)
    assert state["updateMode"] == "ASYNCHRONOUS"
    row = db.query(
        "sql",
        "SELECT updateMode, compactionThreshold FROM schema:graphAnalyticalViews "
        "WHERE name = 'social'",
    ).first()
    assert row.to_dict() == {"updateMode": "ASYNCHRONOUS", "compactionThreshold": 500}


def test_count_answers_the_same_and_plan_does_not_show_the_view(view_db):
    count = "MATCH (a:Person)-[:Follows]->(b:Person) RETURN count(*) AS n"
    explain = "EXPLAIN MATCH (a:Person)-[:Follows]->(b:Person) RETURN count(*) AS n"
    plan_with = (
        view_db.query("opencypher", explain).first().get("executionPlanAsString")
    )
    assert cypher_raw(view_db, count) == [{"n": 6}]
    view_db.command("sql", "DROP GRAPH ANALYTICAL VIEW social")
    plan_without = (
        view_db.query("opencypher", explain).first().get("executionPlanAsString")
    )
    assert cypher_raw(view_db, count) == [{"n": 6}]
    # The guide says the plan text is the same either way.
    assert "COUNT CHAIN PATHS (CSR count-push-down)" in DOC
    assert "COUNT CHAIN PATHS (CSR count-push-down)" in plan_with
    assert "COUNT CHAIN PATHS (CSR count-push-down)" in plan_without


def test_partial_view_does_not_serve_a_whole_graph_call(db):
    db.command("sql", "CREATE VERTEX TYPE City")
    with db.transaction():
        db.command("sql", "CREATE VERTEX City SET name = 'X'")
    db.command(
        "sql",
        doc(
            "CREATE GRAPH ANALYTICAL VIEW people VERTEX TYPES (Person) "
            "EDGE TYPES (Follows)"
        ),
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        row = db.query(
            "sql",
            "SELECT status FROM schema:graphAnalyticalViews WHERE name = 'people'",
        ).first()
        if row.get("status") == "READY":
            break
        time.sleep(0.05)
    # The view leaves City out, so the call scans and still sees all 7 vertices.
    assert cypher(db, "CALL algo.degree() YIELD node RETURN count(node) AS n") == [
        {"n": 7}
    ]


def test_ddl_errors_and_if_clauses(db):
    db.command("sql", doc(CREATE_VIEW))
    with pytest.raises(arcadedb.ArcadeDBError, match="already exists"):
        db.command("sql", "CREATE GRAPH ANALYTICAL VIEW social")
    again = db.command(
        "sql", doc("CREATE GRAPH ANALYTICAL VIEW IF NOT EXISTS social")
    ).first()
    assert again.get("created") is False
    with pytest.raises(arcadedb.ArcadeDBError, match="Unknown update mode"):
        db.command("sql", "ALTER GRAPH ANALYTICAL VIEW social UPDATE MODE SOMETIMES")
    with pytest.raises(arcadedb.ArcadeDBError, match="does not exist"):
        db.command("sql", "DROP GRAPH ANALYTICAL VIEW nope")
    db.command("sql", doc("DROP GRAPH ANALYTICAL VIEW social"))
    gone = db.command("sql", doc("DROP GRAPH ANALYTICAL VIEW IF EXISTS social")).first()
    assert gone.get("name") == "social"
