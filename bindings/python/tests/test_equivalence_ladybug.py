"""Equivalence checks (#347), the Cypher half: ArcadeDB answers like LadybugDB over test_equivalence.py's graph and queries.

A file of its own because LadybugDB's compiled module does not load in the Windows test process: the import of
`_lbug` fails and LadybugDB falls back to a C-API library its wheel does not ship. The likeliest cause is a DLL the
already-running bundled JRE loaded first, which could not be confirmed without a Windows machine, so conftest.py does
not collect this file on Windows and the comparison runs on Linux and macOS.
"""

import ladybug
import pytest
from tests.test_equivalence import (  # noqa: F401 (graph_db: fixture)
    CYPHER,
    KNOWS,
    PEOPLE,
    _arcade,
    _canon,
    graph_db,
)


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
