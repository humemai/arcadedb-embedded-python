"""Equivalence checks (#347): ArcadeDB answers like a reference engine over the same small seeded data.

Cypher against LadybugDB, SQL against DuckDB, graph algorithms against NetworkX, and vector search against NumPy brute
force. ArcadeDB is also checked against itself: an index, a Graph Analytical View, and parameters in place of literals
must not change an answer. Answers are compared as multisets, or as sequences when the query orders, with every number
compared as a float rounded to 9 significant digits.
"""

import datetime
import random

import arcadedb_embedded as arcadedb
import duckdb
import ladybug
import networkx as nx
import numpy as np
import pytest

# Two directed rings of 60 people plus random edges inside each half: no dangling node, so PageRank needs no dangling
# rule, two weakly connected components, and every pair inside a half is reachable. No self-loops or parallel edges,
# whose counting differs between Cypher engines.
HALF = 60
PEOPLE = []
KNOWS = []


def _seed_graph():
    r = random.Random(7)
    for i in range(2 * HALF):
        age = None if r.random() < 0.1 else r.randint(18, 70)
        PEOPLE.append(
            {"id": i, "age": age, "name": r.choice(["ann", "bob", "cy", "dee", "ed"])}
        )
    pairs = set()
    for base in (0, HALF):
        for i in range(HALF):
            pairs.add((base + i, base + (i + 1) % HALF))
        while len(pairs) < (base // HALF + 1) * 4 * HALF:
            a, b = base + r.randrange(HALF), base + r.randrange(HALF)
            if a != b:
                pairs.add((a, b))
    for a, b in sorted(pairs):
        KNOWS.append((a, b, r.randint(1, 9)))


_seed_graph()

CYPHER = [
    "MATCH (p:Person) RETURN count(*) AS c",
    "MATCH (p:Person) WHERE p.age > 40 RETURN p.id AS id",
    "MATCH (p:Person) WHERE p.age IS NULL RETURN p.id AS id",
    "MATCH (p:Person) RETURN p.name AS name, count(*) AS c, avg(p.age) AS a",
    "MATCH (p:Person) WHERE p.name STARTS WITH 'd' OR p.name IN ['ann', 'ed'] RETURN p.id AS id",
    "MATCH (p:Person) WHERE p.age IS NOT NULL RETURN p.id AS id ORDER BY p.age DESC, p.id LIMIT 10",
    "MATCH (a:Person)-[k:KNOWS]->(b:Person) RETURN count(*) AS c",
    "MATCH (a:Person)-[k:KNOWS]->(b:Person) WHERE k.w >= 7 RETURN a.id AS a, b.id AS b, k.w AS w",
    "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS name, sum(b.age) AS s, max(b.age) AS m",
    "MATCH (a:Person)-[:KNOWS]->(b:Person) WITH a, count(b) AS d WHERE d >= 6 RETURN a.id AS a, d",
    "MATCH (a:Person)-[:KNOWS]-(b:Person) WHERE a.id = 3 RETURN b.id AS b",
    "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person) RETURN count(*) AS c",
    "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person) WHERE a.id < c.id RETURN a.id AS a, count(DISTINCT c.id) AS n",
    "MATCH (a:Person {id: 5})-[:KNOWS*1..3]->(b:Person) RETURN DISTINCT b.id AS b",
    "MATCH (a:Person) OPTIONAL MATCH (a)-[:KNOWS]->(b:Person) WHERE b.age > 60 RETURN a.id AS a, count(b) AS n",
]

# The same question with literals and with parameters (ArcadeDB against itself)
CYPHER_PARAMS = [
    (
        "MATCH (p:Person) WHERE p.age > 40 RETURN p.id AS id",
        "MATCH (p:Person) WHERE p.age > $x RETURN p.id AS id",
        {"x": 40},
    ),
    (
        "MATCH (p:Person) WHERE p.name IN ['ann', 'ed'] RETURN p.id AS id",
        "MATCH (p:Person) WHERE p.name IN $x RETURN p.id AS id",
        {"x": ["ann", "ed"]},
    ),
    (
        "MATCH (a:Person {id: 5})-[:KNOWS*1..3]->(b:Person) RETURN DISTINCT b.id AS b",
        "MATCH (a:Person {id: $x})-[:KNOWS*1..3]->(b:Person) RETURN DISTINCT b.id AS b",
        {"x": 5},
    ),
    (
        "MATCH (a:Person)-[k:KNOWS]->(b:Person) WHERE k.w >= 7 RETURN a.id AS a, b.id AS b",
        "MATCH (a:Person)-[k:KNOWS]->(b:Person) WHERE k.w >= $x RETURN a.id AS a, b.id AS b",
        {"x": 7},
    ),
]


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    return float(f"{float(v):.9g}")


def _canon(rows, ordered):
    out = [tuple(sorted((k, _num(v)) for k, v in row.items())) for row in rows]
    return out if ordered else sorted(out, key=repr)


def _arcade(db, language, query, *params):
    return [dict(row) for row in db.query(language, query, *params).to_list()]


@pytest.fixture(scope="module")
def graph_db(tmp_path_factory):
    db = arcadedb.create_database(str(tmp_path_factory.mktemp("eq") / "graph"))
    for s in (
        "CREATE VERTEX TYPE Person",
        "CREATE PROPERTY Person.id LONG",
        "CREATE PROPERTY Person.age LONG",
        "CREATE PROPERTY Person.name STRING",
        "CREATE EDGE TYPE KNOWS",
        "CREATE PROPERTY KNOWS.w LONG",
    ):
        db.command("sql", s)
    with db.transaction():
        for p in PEOPLE:
            db.command(
                "opencypher", "CREATE (:Person {id: $id, age: $age, name: $name})", p
            )
        for a, b, w in KNOWS:
            db.command(
                "opencypher",
                "MATCH (a:Person {id: $a}), (b:Person {id: $b}) CREATE (a)-[:KNOWS {w: $w}]->(b)",
                {"a": a, "b": b, "w": w},
            )
    yield db
    db.close()


@pytest.fixture(scope="module")
def ladybug_conn(tmp_path_factory):
    conn = ladybug.Connection(
        ladybug.Database(str(tmp_path_factory.mktemp("eq") / "ladybug"))
    )
    conn.execute(
        "CREATE NODE TABLE Person(id INT64, age INT64, name STRING, PRIMARY KEY(id))"
    )
    conn.execute("CREATE REL TABLE KNOWS(FROM Person TO Person, w INT64)")
    for p in PEOPLE:
        conn.execute("CREATE (:Person {id: $id, age: $age, name: $name})", p)
    for a, b, w in KNOWS:
        conn.execute(
            "MATCH (a:Person {id: $a}), (b:Person {id: $b}) CREATE (a)-[:KNOWS {w: $w}]->(b)",
            {"a": a, "b": b, "w": w},
        )
    return conn


def _ladybug(conn, query):
    res = conn.execute(query)
    cols, rows = res.get_column_names(), []
    while res.has_next():
        rows.append(dict(zip(cols, res.get_next())))
    return rows


@pytest.mark.parametrize("query", CYPHER)
def test_cypher_matches_ladybug(graph_db, ladybug_conn, query):
    ordered = "ORDER BY" in query
    assert _canon(_arcade(graph_db, "opencypher", query), ordered) == _canon(
        _ladybug(ladybug_conn, query), ordered
    )


def test_cypher_unchanged_by_parameters(graph_db):
    for literal, param, params in CYPHER_PARAMS:
        assert _canon(_arcade(graph_db, "opencypher", param, params), False) == _canon(
            _arcade(graph_db, "opencypher", literal), False
        ), param


def test_cypher_unchanged_by_index_and_view(graph_db):
    """Answers taken without an index or a view, then with indexes, then with a SYNCHRONOUS view as well."""
    before = {
        q: _canon(_arcade(graph_db, "opencypher", q), "ORDER BY" in q) for q in CYPHER
    }
    for s in (
        "CREATE INDEX ON Person (age) NOTUNIQUE",
        "CREATE INDEX ON Person (name) NOTUNIQUE",
        "CREATE INDEX ON KNOWS (w) NOTUNIQUE",
    ):
        graph_db.command("sql", s)
    for q in CYPHER:
        assert (
            _canon(_arcade(graph_db, "opencypher", q), "ORDER BY" in q) == before[q]
        ), f"with indexes: {q}"
    graph_db.command(
        "sql",
        "CREATE GRAPH ANALYTICAL VIEW eq VERTEX TYPES (Person) EDGE TYPES (KNOWS) PROPERTIES (id, age, name) "
        "EDGE PROPERTIES (w) UPDATE MODE SYNCHRONOUS",
    )
    for _ in range(300):
        if (
            graph_db.query(
                "sql",
                "SELECT status FROM schema:graphAnalyticalViews WHERE name = 'eq'",
            ).to_list()[0]["status"]
            == "READY"
        ):
            break
        import time

        time.sleep(0.1)
    try:
        for q in CYPHER:
            assert (
                _canon(_arcade(graph_db, "opencypher", q), "ORDER BY" in q) == before[q]
            ), f"with the view: {q}"
    finally:
        graph_db.command("sql", "DROP GRAPH ANALYTICAL VIEW eq")


def test_graph_algorithms_match_networkx(graph_db):
    g = nx.DiGraph()
    g.add_nodes_from(p["id"] for p in PEOPLE)
    g.add_edges_from((a, b) for a, b, _ in KNOWS)

    rows = _arcade(
        graph_db,
        "opencypher",
        "CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 200, tolerance: 0.0}) "
        "YIELD node, score RETURN node.id AS id, score",
    )
    total = sum(r["score"] for r in rows)
    expected = nx.pagerank(g, alpha=0.85, tol=1e-14, max_iter=1000)
    for r in rows:
        assert r["score"] / total == pytest.approx(expected[r["id"]], rel=1e-6), r["id"]

    rows = _arcade(
        graph_db,
        "opencypher",
        "CALL algo.wcc() YIELD node, componentId RETURN node.id AS id, componentId AS c",
    )
    components = {}
    for r in rows:
        components.setdefault(r["c"], set()).add(r["id"])
    assert sorted(map(sorted, components.values())) == sorted(
        map(sorted, nx.weakly_connected_components(g))
    )

    rows = _arcade(
        graph_db,
        "opencypher",
        "CALL algo.degree() YIELD node, inDegree, outDegree RETURN node.id AS id, inDegree AS i, outDegree AS o",
    )
    assert {r["id"]: (r["i"], r["o"]) for r in rows} == {
        n: (g.in_degree(n), g.out_degree(n)) for n in g
    }

    r = random.Random(3)
    for _ in range(10):
        base = r.choice((0, HALF))
        a, b = base + r.randrange(HALF), base + r.randrange(HALF)
        if a == b:
            continue
        got = _arcade(
            graph_db,
            "opencypher",
            "MATCH p = shortestPath((a:Person {id: $a})-[:KNOWS*]->(b:Person {id: $b})) RETURN length(p) AS l",
            {"a": a, "b": b},
        )
        assert got[0]["l"] == nx.shortest_path_length(g, a, b), (a, b)


ITEMS = []


def _seed_items():
    r = random.Random(11)
    for i in range(300):
        ITEMS.append(
            {
                "id": i,
                "qty": None if r.random() < 0.15 else r.randint(0, 9),
                "price": round(r.uniform(1, 99), 2),
                "cat": r.choice(["a", "b", "c", "bd"]),
                "day": datetime.date(2026, 1, 1)
                + datetime.timedelta(days=r.randrange(180)),
            }
        )


_seed_items()

# (query with {T} for the table, parameters); the same text runs on both engines
SQL = [
    ("SELECT count(*) AS c FROM {T}", ()),
    ("SELECT id FROM {T} WHERE qty > 5", ()),
    ("SELECT id FROM {T} WHERE qty IS NULL", ()),
    ("SELECT cat, count(*) AS c, sum(qty) AS s FROM {T} GROUP BY cat", ()),
    (
        "SELECT cat, avg(price) AS a, min(price) AS lo, max(price) AS hi FROM {T} GROUP BY cat",
        (),
    ),
    ("SELECT DISTINCT cat FROM {T}", ()),
    ("SELECT id FROM {T} WHERE cat IN ('a', 'c') AND price BETWEEN 10 AND 50", ()),
    ("SELECT id FROM {T} WHERE cat LIKE 'b%'", ()),
    ("SELECT id, price FROM {T} WHERE price > 40 ORDER BY price DESC, id LIMIT 7", ()),
    ("SELECT id, day FROM {T} WHERE id < 12", ()),
    ("SELECT id FROM {T} WHERE day >= ?", (datetime.date(2026, 4, 1),)),
    (
        "SELECT count(*) AS c FROM {T} WHERE day BETWEEN ? AND ?",
        (datetime.date(2026, 2, 1), datetime.date(2026, 3, 15)),
    ),
    ("SELECT id FROM {T} WHERE qty = ? AND cat = ?", (3, "b")),
]


@pytest.fixture(scope="module")
def item_db(tmp_path_factory):
    db = arcadedb.create_database(str(tmp_path_factory.mktemp("eq") / "items"))
    for s in (
        "CREATE DOCUMENT TYPE Item",
        "CREATE PROPERTY Item.id INTEGER",
        "CREATE PROPERTY Item.qty INTEGER",
        "CREATE PROPERTY Item.price DOUBLE",
        "CREATE PROPERTY Item.cat STRING",
        "CREATE PROPERTY Item.day DATE",
    ):
        db.command("sql", s)
    with db.transaction():
        for it in ITEMS:
            db.command(
                "sql",
                "INSERT INTO Item SET id = ?, qty = ?, price = ?, cat = ?, day = ?",
                it["id"],
                it["qty"],
                it["price"],
                it["cat"],
                it["day"],
            )
    yield db
    db.close()


@pytest.fixture(scope="module")
def duck():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE item (id INTEGER, qty INTEGER, price DOUBLE, cat VARCHAR, day DATE)"
    )
    con.executemany(
        "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
        [(i["id"], i["qty"], i["price"], i["cat"], i["day"]) for i in ITEMS],
    )
    return con


@pytest.mark.parametrize("query,params", SQL)
def test_sql_matches_duckdb(item_db, duck, query, params):
    cur = duck.execute(query.replace("{T}", "item"), list(params))
    cols = [d[0] for d in cur.description]
    expected = [dict(zip(cols, row)) for row in cur.fetchall()]
    ordered = "ORDER BY" in query
    assert _canon(
        _arcade(item_db, "sql", query.replace("{T}", "Item"), *params), ordered
    ) == _canon(expected, ordered)


def test_vector_search_recall_against_brute_force(temp_db):
    rng = np.random.default_rng(5)
    vectors = rng.standard_normal((1000, 16)).astype(np.float32)
    temp_db.command("sql", "CREATE VERTEX TYPE Doc")
    temp_db.command("sql", "CREATE PROPERTY Doc.id INTEGER")
    temp_db.command("sql", "CREATE PROPERTY Doc.vec ARRAY_OF_FLOATS")
    with temp_db.transaction():
        for i, v in enumerate(vectors):
            temp_db.command("sql", "INSERT INTO Doc SET id = ?, vec = ?", i, v.tolist())
    index = temp_db.create_vector_index(
        "Doc", "vec", dimensions=16, distance_function="cosine", quantization="NONE"
    )
    unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    hits = 0
    queries = rng.standard_normal((20, 16)).astype(np.float32)
    for q in queries:
        exact = set(np.argsort(-(unit @ (q / np.linalg.norm(q))))[:10].tolist())
        found = {record.get("id") for record, _ in index.find_nearest(q.tolist(), k=10)}
        hits += len(found & exact)
    assert hits / (10 * len(queries)) >= 0.9
