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

import pytest

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


def test_surrealql_mean_age_is_a_float_division():
    """Found on the SF1 slice against the DuckDB reference: SurrealQL divides two integers as integers (5 / 2 is 2), so the
    per-city mean friend age came back as 41 where every other engine returned 41.79. The sum is cast before the division."""
    assert "<float> S / N" in L.SurrealGraph.OLAP["friend_age_by_city"]
    assert L.SurrealGraphServer.OLAP["friend_age_by_city"] == L.SurrealGraph.OLAP["friend_age_by_city"]


def test_surrealql_mean_age_on_the_real_engine_is_not_truncated():
    surrealdb = pytest.importorskip("surrealdb", reason="add --with surrealdb==2.0.0 to run the SurrealDB case")
    db = surrealdb.Surreal("mem://")
    db.use("t", "t")
    for pid, age in ((1, 40), (2, 43), (3, 42)):
        db.query(f"CREATE person:{pid} SET pid = {pid}, age = {age}, city = 'c'")
    db.query("RELATE person:1->knows->person:2; RELATE person:1->knows->person:3")
    rows = db.query(L.SurrealGraph.OLAP["friend_age_by_city"])
    # the friendships count for both of their people: the ages seen are 43 and 42 (person 1), 40 (person 2), 40 (person 3)
    assert len(rows) == 1 and rows[0]["n"] == 4
    assert rows[0]["a"] == pytest.approx(165 / 4)          # 41.25; the integer division gave 41


def test_mongodb_lookup_local_fields_are_field_names_never_expressions():
    """The first run of the 2-hop and 3-hop reads on mongod failed with "FieldPath field names may not start with '$'":
    $lookup's localField is a field name ("f"), and the hop builders had passed the expression form ("$f"). The unit tests
    that read the pipelines' structure could not see it, a real mongod rejects it."""
    M = L.MongoGraph
    stages = M._second_hop(7) + M._third_hop(7)
    lookups = [st["$lookup"] for st in stages if "$lookup" in st]
    assert len(lookups) == 6      # two per step: the 2-hop has one step, the 3-hop two (and the 2-hop's own)
    for lk in lookups:
        assert not lk["localField"].startswith("$"), lk
        assert lk["localField"] in ("f", "f2"), lk


def _walks(edges, start, k):
    """Every walk of k pairwise-distinct friendships from `start` (Cypher's relationship isomorphism), as the list of far ends."""
    adj = {}
    for i, (a, b) in enumerate(edges):
        adj.setdefault(a, []).append((b, i))
        adj.setdefault(b, []).append((a, i))
    ends = []

    def go(at, used, left):
        if left == 0:
            ends.append(at)
            return
        for nxt, e in adj.get(at, []):
            if e not in used:
                go(nxt, used | {e}, left - 1)
    go(start, frozenset(), k)
    return ends


def test_surrealql_two_and_three_hop_reads_equal_the_distinct_edge_walks_for_every_start_on_the_real_engine():
    """Found on the SF1 slice (26 of 96 present starts off): inside a SurrealQL closure a query parameter reads as NONE and an
    outer closure's variable is invisible to an inner one, so exclusions written there removed nothing. Every start of a
    small graph with triangles and a pendant person is compared with a brute-force enumeration of distinct-edge walks."""
    surrealdb = pytest.importorskip("surrealdb", reason="add --with surrealdb==2.0.0 to run the SurrealDB case")
    ages = {1: 50, 2: 45, 3: 50, 4: 50, 5: 30, 6: 44, 7: 60, 8: 41}
    edges = [(1, 2), (2, 3), (3, 4), (2, 4), (4, 5), (5, 6), (6, 7), (7, 4), (1, 8), (6, 8), (3, 7)]
    db = surrealdb.Surreal("mem://")
    db.use("t", "t")
    for pid, age in ages.items():
        db.query(f"CREATE person:{pid} SET pid = {pid}, age = {age}, city = 'c'")
    for a, b in edges:
        db.query(f"RELATE person:{a}->knows->person:{b} SET since = 2000")
    S = L.SurrealGraph
    for start in ages:
        rid = surrealdb.RecordID("person", start)

        def one(text):
            out = db.query(text, {"p": rid})
            return out.get("n") if isinstance(out, dict) else None
        two, three = _walks(edges, start, 2), _walks(edges, start, 3)
        assert one(S.READS["hop2"]) == len(set(two)), start
        assert one(S.READS["hop3f"]) == len({x for x in three if ages[x] > G.HOP3F_MIN_AGE}), start
        assert one(S.VISITED) == len(set(three)), start


def test_surrealql_three_hop_text_names_no_parameter_or_outer_variable_inside_a_closure():
    h = L.SurrealGraph._HOP3
    assert "[id]" in h and "[$p]" not in h                  # the start is the current record inside a closure
    assert h.count("[$a]") == 1                              # `a` is excluded once, by the outer closure
    assert "|$b| array::concat($b->knows->person, $b<-knows<-person)" in h      # the inner closure reads only its own variable
