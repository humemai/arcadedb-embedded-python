"""Every graph question is asked undirected, on every engine (CAMPAIGN section 7 row 56, DECISIONS #151, BUGS F169).

Run with `python -m pytest test_graph_undirected.py -q -rs` from this directory.

LDBC lists each friendship once, from the smaller person id to the larger, and the lane loads each row as one
KNOWS edge. Through October every question followed `->`: 1-hop saw the friends with a larger id, 2-hop and 3-hop
walked rising ids, and the triangle count was 0 on every engine by construction. The re-pin asks each question
in each dialect's undirected (or ANY) form over the same one stored edge, and writes `knows_direction` into
every graph row. The engines are not available here, so these checks hold the TEXTS: they fail on October's
directed spellings, and the answers themselves are proven against a DuckDB reference at LDBC SF1 on the laptop
(REPIN-REHEARSAL), not by this file.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402

CYPHER_QUESTIONS = {
    **{f"read {k}": G.OLTP_READS[k] for k in ("hop1", "hop2", "hop3f")},
    "visited": G.HOP3_VISITED,
    **{f"olap {k}": G.OLAP_QUERIES[k] for k in ("top_degree", "same_city_edges", "friend_age_by_city",
                                                "degree_dist", "triangles")},
}


def test_the_row_says_undirected_and_the_page_reads_the_same_field():
    assert G.KNOWS_DIRECTION == "undirected"
    ew = (HERE / "export_web.py").read_text()
    assert re.search(r'^_KNOWS_DIRECTION_FIELD = "%s"$' % re.escape(G.KNOWS_DIRECTION_FIELD), ew, re.M)


def test_the_lane_stamps_the_direction_before_any_query_runs():
    src = (HERE / "l2_graph.py").read_text()
    main = src[src.index("def main():"):]
    stamp = main.index("out[graph_common.KNOWS_DIRECTION_FIELD] = graph_common.KNOWS_DIRECTION")
    assert stamp < main.index("ad.build(n_persons)") < main.index("_read_pass(")


def test_the_cypher_questions_follow_no_edge_direction():
    for name, text in CYPHER_QUESTIONS.items():
        assert "[:KNOWS]" in text, name
        assert not re.search(r"\[:KNOWS[^\]]*\]->", text), f"{name} still follows KNOWS forward: {text}"
        assert not re.search(r"<-\[:KNOWS", text), f"{name} still follows KNOWS backward: {text}"


def test_a_question_that_counts_friendships_counts_each_once():
    assert "a.id < b.id" in G.OLAP_QUERIES["same_city_edges"]
    tri = G.OLAP_QUERIES["triangles"]
    assert "a.id < b.id AND b.id < c.id" in tri               # one of a triangle's six walks
    assert tri.count("-[:KNOWS]-") == 3 and "(a)" in tri.split("-[:KNOWS]-")[-1][:4]


def test_lsqb_still_asks_undirected():
    for q, text in G.LSQB_QUERIES.items():
        assert not re.search(r"\[:KNOWS[^\]]*\]->", text), q


# ---- the other dialects -------------------------------------------------------------------------------------

def test_duckpgq_uses_the_undirected_edge_pattern_and_writes_out_the_walks_it_excludes():
    texts = list(L.DuckpgqGraph.READS.values()) + [L.DuckpgqGraph.VISITED] + list(L.DuckpgqGraph.OLAP.values())
    for t in texts:
        assert not re.search(r"-\[\w+:knows\]->", t), t
    assert "fof.id <> p.id" in L.DuckpgqGraph.READS["hop2"]
    for t in (L.DuckpgqGraph.READS["hop3f"], L.DuckpgqGraph.VISITED):
        assert "m2.id <> p.id AND x.id <> m1.id" in t
    assert "a.id < b.id AND b.id < c.id" in L.DuckpgqGraph.OLAP["triangles"]
    assert "a.id < b.id" in L.DuckpgqGraph.OLAP["same_city_edges"]


def test_arangodb_traverses_any_and_never_outbound():
    texts = list(L.ArangoGraph.READS.values()) + [L.ArangoGraph.VISITED] + list(L.ArangoGraph.OLAP.values())
    for t in texts:
        assert "OUTBOUND" not in t and "INBOUND" not in t, t
    assert all("ANY" in L.ArangoGraph.READS[k] for k in ("hop1", "hop2", "hop3f"))
    assert "b.id > a.id" in L.ArangoGraph.OLAP["triangles"] and "c.id > b.id" in L.ArangoGraph.OLAP["triangles"]


def test_surrealdb_reads_both_ends_of_every_friendship():
    S = L.SurrealGraph
    for k in ("hop1", "hop2", "hop3f"):
        assert "<-knows<-person" in S.READS[k] and "->knows->person" in S.READS[k], k
    assert "<-knows<-person" in S.VISITED
    for k in ("top_degree", "degree_dist", "friend_age_by_city"):
        assert "<-knows" in S.OLAP[k] and "->knows" in S.OLAP[k], k
    for cls in (S, L.SurrealGraphServer):
        t = cls.OLAP["triangles"]
        assert "in<-knows" in t and "out<-knows" in t, cls.__name__      # both ends, both directions
        assert "WHERE in < out" not in t                                 # the October directed 3-cycle


def test_mongodb_has_no_directed_graph_lookup_and_looks_up_both_ends():
    M = L.MongoGraph
    built = repr([M._first_hop(7), M._second_hop(7), M._third_hop(7)] + [v[1] for v in M.OLAP.values()])
    assert "graphLookup" not in built      # it walks one direction of `knows`; undirected is two indexed $lookups
    for name in ("top_degree", "degree_dist"):
        assert {"$unwind": "$v"} in M.OLAP[name][1], name
    tri = repr(M.OLAP["triangles"][1])
    assert tri.count("'foreignField': 'src'") == 2 and tri.count("'foreignField': 'dst'") == 2
    first = M._first_hop(7)
    assert first[0] == {"$match": {"$or": [{"src": 7}, {"dst": 7}]}}
    step = repr(M._step("$f", ["$e1"], "f2", ["e1", "f"]))
    assert "'foreignField': 'src'" in step and "'foreignField': 'dst'" in step
    # a friendship is not walked back along itself: the edges already on the path are dropped
    assert "'$not': {'$in': ['$$this._id', ['$e1']]}" in step


def test_every_cypher_engine_reads_the_shared_text():
    """The Cypher arms take graph_common's text unchanged, so the checks above cover them; this keeps it so."""
    for cls in (L.ArcadeGraphEmbedded, L.ArcadeGraphServer, L.Neo4jGraph, L.MemgraphGraph, L.FalkorGraph,
                L.LadybugGraph, L.PgAgeGraph):
        assert "READS" not in cls.__dict__ and "OLAP" not in cls.__dict__, f"{cls.__name__} has its own question texts"
