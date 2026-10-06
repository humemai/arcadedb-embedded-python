"""LSQB's q5, q6, q8, and q9 run LSQB's own text on every engine (CAMPAIGN section 7 row 60, DECISIONS #154 item 1, BUGS F174).

Run with `python -m pytest test_lsqb_text.py -q -rs` from this directory.

From 2026-09-18 the lane wrote LSQB's node inequality (`tag1 <> tag2`, `person1 <> person3`) as an id comparison
(`tag1.id <> tag2.id`), on the belief that ArcadeDB's openCypher needed the property form. It does not, and its planner
recognises only the inequality between two node variables for the count operators it has for these queries, so the id form
sent all four to the row pipeline (q9 at config A: 33.59 s against 0.0105 s) and cost Neo4j 1.4-1.7x too. The answers are
identical either way, so every digest agreed and nothing noticed.

The texts here are LSQB's own (github.com/ldbc/lsqb, Apache-2.0), copied as fixtures with the one change the lane has always
made (`AS n` for `AS count`, the alias every engine's digest reads), so a drift from LSQB's wording fails by name.
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402

# ldbc/lsqb cypher/q5.cypher, q6, q8, q9 (the canonical Cypher the Neo4j, ArcadeDB, Memgraph, and FalkorDB arms run)
LSQB_CYPHER = {
    "lsqb_q5": ("MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Comment)-[:HAS_TAG]->(tag2:Tag)\n"
                "WHERE tag1 <> tag2\nRETURN count(*) AS count"),
    "lsqb_q6": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)-[:HAS_INTEREST]->(tag:Tag)\n"
                "WHERE person1 <> person3\nRETURN count(*) AS count"),
    "lsqb_q8": ("MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Comment)-[:HAS_TAG]->(tag2:Tag)\n"
                "WHERE NOT (comment)-[:HAS_TAG]->(tag1)\n  AND tag1 <> tag2\nRETURN count(*) AS count"),
    "lsqb_q9": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)-[:HAS_INTEREST]->(tag:Tag)\n"
                "WHERE NOT (person1)-[:KNOWS]-(person3)\n  AND person1 <> person3\nRETURN count(*) AS count"),
}


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("q", sorted(LSQB_CYPHER))
def test_the_cypher_text_is_lsqbs_own_up_to_the_alias(q):
    assert _norm(G.LSQB_QUERIES[q]) == _norm(LSQB_CYPHER[q].replace("AS count", "AS n"))


def test_no_cypher_lsqb_query_compares_ids_where_lsqb_compares_nodes():
    for q, text in G.LSQB_QUERIES.items():
        assert not re.search(r"\w+\.id\s*<>\s*\w+\.id", text), q


def test_the_ladybug_text_is_lsqbs_own_ladybug_text():
    """ldbc/lsqb ladybug/q5, q6, q9 compare id(node); q8 compares the tags' key property (here `id`)."""
    t = L.LadybugGraph.LSQB
    assert "WHERE id(tag1) <> id(tag2)" in t["lsqb_q5"]
    assert "WHERE id(person1) <> id(person3)" in t["lsqb_q6"]
    assert "AND tag1.id <> tag2.id" in t["lsqb_q8"] and "NOT (comment)-[:Message_hasTag_Tag]->(tag1)" in t["lsqb_q8"]
    assert "NOT (person1)-[:KNOWS]-(person3) AND id(person1) <> id(person3)" in t["lsqb_q9"]


def test_duckpgq_runs_lsqbs_own_pgq_text_which_compares_ids_because_sql_pgq_has_no_node_inequality():
    t = L.DuckpgqGraph.LSQB
    assert "WHERE tag1.id <> tag2.id" in t["lsqb_q5"]                          # ldbc/lsqb pgq/q5.sql
    assert "WHERE p1.id <> p3.id" in t["lsqb_q6"]                              # pgq/q6.sql: person1.id <> person3.id
    # q8 and q9 are LSQB's anti-join: the match exposes the ids, LEFT JOINed to the edge table, IS NULL kept
    assert "LEFT JOIN dp_comment_hastag_tag cht" in t["lsqb_q8"] and "cht.s IS NULL" in t["lsqb_q8"]
    assert "LEFT JOIN knows ka" in t["lsqb_q9"] and "ka.src IS NULL AND kb.src IS NULL" in t["lsqb_q9"]


def test_the_dialects_with_no_lsqb_text_compare_node_identity_never_a_property_that_can_differ():
    """LSQB publishes nothing for AQL, SurrealQL, or aggregation pipelines: their spellings are checked against
    LSQB's text by the answers (digest agreement on the smoke), and statically here by what they compare."""
    aql = " ".join(L.ArangoGraph.LSQB[q] for q in ("lsqb_q5", "lsqb_q6", "lsqb_q8", "lsqb_q9"))
    assert aql.count("_key !=") >= 4 and ".id !=" not in aql and ".id <>" not in aql
    sdb = " ".join(L.SurrealGraph.LSQB[q] for q in ("lsqb_q5", "lsqb_q6", "lsqb_q8", "lsqb_q9"))
    assert ".pid" not in sdb and ".id <>" not in sdb
    mongo = repr([L.MongoGraph._LSQB[q] for q in ("lsqb_q5", "lsqb_q6", "lsqb_q8", "lsqb_q9")])
    assert "'$ne'" in mongo


def test_the_field_and_value_the_page_reads():
    ew = (HERE / "export_web.py").read_text()
    assert re.search(r'^_LSQB_TEXT_FIELD = "%s"$' % re.escape(G.LSQB_TEXT_FIELD), ew, re.M)
    assert G.LSQB_TEXT == "lsqb"


# ---- the lane stamps it -------------------------------------------------------------------------------------------

class _Olap(L.Base):
    name = "stub_olap"
    version = "stub"
    QUERY_LANGUAGE = "stub"

    def connect(self):
        pass

    def build(self, n):
        for _ in L.gen_persons(n):
            pass
        for _ in L.gen_edges(n):
            pass

    def run_olap(self, qname):
        return {"top_degree": [{"id": 1, "d": 3}], "same_city_edges": [{"c": "c", "n": 1}],
                "friend_age_by_city": [{"c": "c", "a": 4.0, "n": 1}], "degree_dist": [{"deg": 1, "n": 1}],
                "triangles": [{"n": 2}]}[qname]


def test_every_graph_analytics_row_records_that_it_ran_lsqbs_text(monkeypatch, tmp_path):
    import json
    monkeypatch.setitem(L.ADAPTERS, "stub_olap", _Olap)
    monkeypatch.setattr(L, "OLAP_ITERATIONS", 2)
    monkeypatch.setattr(G, "OLAP_ITERATIONS", 2)
    out = tmp_path / "row.json"
    monkeypatch.setattr(sys, "argv", ["l2_graph.py", "--backend", "stub_olap", "--workload", "olap",
                                       "--scale", "micro", "--out", str(out)])
    L.main()
    row = json.loads(out.read_text())
    assert row["lsqb_text"] == "lsqb" and row["knows_direction"] == "undirected"
    # and an OLTP row does not claim it: it asked no LSQB query
    oltp = tmp_path / "oltp.json"
    src = (HERE / "l2_graph.py").read_text()
    assert 'if args.workload == "olap":\n        out[graph_common.LSQB_TEXT_FIELD]' in src
