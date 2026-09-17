"""Shared social-graph generator for the L2 graph lane.

LDBC-SNB-flavored but deliberately distinct from cypherglot's corpus:
Person(id, name, age, city) vertices and KNOWS(since) edges with a skewed
(Pareto) out-degree distribution. Deterministic per (seed, scale) so every
adapter regenerates identical data — no fixture files shipped.
"""
import random

N_CITIES = 100
AVG_OUT_DEGREE = 20
DEGREE_CAP = 1000

# persons per scale; edges ~= persons * AVG_OUT_DEGREE
SCALE_PERSONS = {"micro": 2_000, "tiny": 10_000, "small": 100_000,
                 "medium": 1_000_000, "large": 5_000_000}
# OLTP query count per scale (per operation); OLAP iterations are fixed small
SCALE_OLTP_QUERIES = {"micro": 50, "tiny": 200, "small": 500, "medium": 200,
                      "large": 100}
# 100, not 5 (2026-09-10, BUGS F29): a p99 needs a hundred samples to be a
# percentile rather than the slowest run. ~2.7 s per pass for ArcadeDB at SF10.
# BENCH_GRAPH_OLAP_ITER lowers it for a laptop smoke; the row records
# `<query>_iters`, so a cell that ran fewer says so.
import os as _os
OLAP_ITERATIONS = int(_os.environ.get("BENCH_GRAPH_OLAP_ITER") or 100)

# A PER-QUERY WALL BUDGET, because one of the five is not like the others.
# DECISIONS #82b: "The triangle count is the most likely cell on the page to
# exceed its budget at the larger scale factor, and that is a result rather
# than a problem: it is recorded as a named censored cell with its budget."
# Measured on the laptop at micro (2,000 persons, about 40,000 edges): Neo4j
# spent over twelve minutes inside the triangle count's warm loop and had not
# finished, because the query enumerates roughly n*d^3 path expansions per
# iteration -- 16 million here, and three orders of magnitude more at SF10.
#
# So the warm loop stops when its cumulative wall clock passes the budget. The
# cold pass always runs, so a censored cell still carries a measurement and a
# count; the row records `<query>_censored`, `<query>_budget_s` and
# `<query>_iters`, and a reader can see it ran nine iterations rather than a
# hundred instead of reading a p99 over nine samples as though it were one over
# a hundred.
OLAP_BUDGET_S = float(_os.environ.get("BENCH_GRAPH_OLAP_BUDGET_S") or 300.0)

GRAPH_SEED = 20260708
PICK_SEED = 777


def gen_persons(n, seed=GRAPH_SEED):
    """Yield (id, name, age, city). Deterministic stream."""
    rng = random.Random(seed)
    for i in range(n):
        yield i, f"person_{i}", rng.randint(18, 90), f"city_{rng.randrange(N_CITIES)}"


def gen_edges(n_persons, seed=GRAPH_SEED + 1):
    """Yield (src_id, dst_id, since_year). Pareto out-degree, capped.

    Separate rng stream from gen_persons so both can be re-streamed
    independently by adapters.
    """
    rng = random.Random(seed)
    for src in range(n_persons):
        out_deg = min(DEGREE_CAP, max(1, int(rng.paretovariate(1.16))))
        # normalize expectation towards AVG_OUT_DEGREE: mix one heavy tail
        # draw with uniform fill
        fill = max(0, rng.randint(0, 2 * AVG_OUT_DEGREE - 2) - out_deg)
        seen = set()
        for _ in range(out_deg + fill):
            dst = rng.randrange(n_persons)
            if dst != src and dst not in seen:
                seen.add(dst)
                yield src, dst, rng.randint(1990, 2026)


def pick_query_ids(n_persons, n_queries, seed=PICK_SEED):
    rng = random.Random(seed)
    return [rng.randrange(n_persons) for _ in range(n_queries)]


# ---------------------------------------------------------------- workloads
# Cypher text templates; {id} formatted in by adapters (literal params keep
# every engine on the same query plan surface).
#   (WHERE form, not inline property maps — portable across ArcadeDB
#   opencypher, Neo4j, and LadybugDB)
OLTP_READS = {
    # ALIASED RETURN COLUMNS (2026-10). `RETURN p.name, p.age` gives the column
    # the driver's own spelling -- "p.name" through the Neo4j driver, a
    # positional value through LadybugDB, "name" through the SurrealDB and
    # ArangoDB hooks -- and a digest cannot compare three spellings of one
    # column (DECISIONS #88). The alias costs nothing and makes the answer
    # comparable.
    "point": ("MATCH (p:Person) WHERE p.id = {id} "
              "RETURN p.name AS name, p.age AS age"),
    "hop1": ("MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} "
             "RETURN count(f) AS n, avg(f.age) AS a"),
    "hop2": ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) "
             "WHERE p.id = {id} RETURN count(DISTINCT fof) AS n"),
    # 2026-10 (DECISIONS #82): three hops with a property filter on the far
    # end, the interactive workload's characteristic shape, where the planner
    # decides whether the filter or the expansion goes first.
    "hop3f": ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(x:Person) "
              "WHERE p.id = {id} AND x.age > 30 RETURN count(DISTINCT x) AS n"),
}
# write op: create a person and link them to an existing one (one txn)
OLTP_WRITE = ("MATCH (p:Person) WHERE p.id = {id} "
              "CREATE (q:Person {{id: {new_id}, name: 'w{new_id}', age: 33, "
              "city: 'city_0'}}) "
              "CREATE (p)-[:KNOWS {{since: 2026}}]->(q)")

# 2026-10 (DECISIONS #82): the write's partner. Delete the person the write
# created, with the edge that linked them, one transaction; the page then
# carries a delete per engine, which no table did.
OLTP_DELETE = "MATCH (q:Person) WHERE q.id = {new_id} DETACH DELETE q"

# 2026-10 (DECISIONS #82a): the fourth single-record operation. One property
# of one record, set to a fixed value so the post-state is deterministic and
# every engine must agree on it.
OLTP_UPDATE = "MATCH (q:Person) WHERE q.id = {new_id} SET q.age = 44"
UPDATE_AGE = 44

# HOW LOCAL IS THE THREE-HOP READ? The page will say the filtered three-hop
# read stays local; that is a claim about the data, not about the engine, and
# until now nothing recorded the number it rests on. This is hop3f without the
# age filter: the distinct persons at exactly three hops, which is the set the
# filter is applied to. Run UNTIMED, once per cell, over a small sample of the
# same ids the timed loop uses, so a reader can check "stays local" against a
# number instead of a word.
HOP3_VISITED = ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(x:Person) "
                "WHERE p.id = {id} RETURN count(DISTINCT x) AS n")
VISITED_SAMPLE = 20

# EVERY "ORDER BY ... LIMIT" CARRIES A TOTAL ORDER, and it did not until
# 2026-09-14, when the #88 digests showed what that costs. Three of these five
# had ties spanning the limit boundary -- dozens of people share an out-degree,
# dozens of cities share an edge count -- so "the top ten" was a different ten
# on different engines, all of them correct. LadybugDB returned ten person ids
# at degrees 102, 107 and 122; Neo4j, ArcadeDB and ArangoDB returned ten
# DIFFERENT ids at exactly those degrees. A benchmark query whose answer is
# ambiguous cannot be compared across engines and should not be published as
# "the top ten" either, so the second sort key is part of the question now. It
# costs one comparison per row and it is added on every engine at once.
OLAP_QUERIES = {
    "top_degree": ("MATCH (p:Person)-[:KNOWS]->(:Person) "
                   "RETURN p.id AS id, count(*) AS d ORDER BY d DESC, id ASC LIMIT 10"),
    "same_city_edges": ("MATCH (a:Person)-[:KNOWS]->(b:Person) "
                        "WHERE a.city = b.city "
                        "RETURN a.city AS c, count(*) AS n ORDER BY n DESC, c ASC "
                        "LIMIT 10"),
    "friend_age_by_city": ("MATCH (p:Person)-[:KNOWS]->(f:Person) "
                           "RETURN p.city AS c, avg(f.age) AS a, count(*) AS n "
                           "ORDER BY n DESC, c ASC LIMIT 10"),
    # 2026-10 (DECISIONS #82b), so the graph table is as thorough as the
    # document one: five analytics queries on each.
    #
    # The degree distribution: how many people have how many friends. A
    # whole-graph aggregation over every edge, and the cheapest honest way to
    # make the planner touch everything. Persons with no outgoing KNOWS are
    # outside the MATCH and therefore outside the histogram, on every engine,
    # which is stated here because it is the one modelling choice in it.
    "degree_dist": ("MATCH (p:Person)-[:KNOWS]->(f:Person) "
                    "WITH p, count(f) AS d "
                    "RETURN d AS deg, count(*) AS n ORDER BY deg"),
    # The triangle count: mutual-friend triples, each counted once. The
    # canonical graph analytic, and the one query on the page that punishes a
    # bad join or traversal plan rather than a slow scan. A directed 3-cycle
    # has three rotations; requiring the start to be the smallest id selects
    # exactly one of them, so each triangle is counted once on every engine.
    # Expected to exceed its budget at the larger scale factor, which is a
    # named censored cell and not a bug (#82b).
    "triangles": ("MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person)-[:KNOWS]->(a) "
                  "WHERE a.id < b.id AND a.id < c.id RETURN count(*) AS n"),
}

# ---------------------------------------------------------------------------
# LSQB's nine pattern-matching queries (DECISIONS #104), on the FULL social
# network at SF1 that the analytics table moves to (#103b). Canonical Cypher
# from github.com/ldbc/lsqb (cypher/q1.cypher .. q9.cypher), taken nearly
# verbatim; the only changes to the published text are:
#   * `RETURN count(*) AS n` in place of `AS count`, the one alias the digest
#     compares against on every engine (the same reason the five above alias);
#   * node inequality written as `<>` on the `.id` property (`tag1.id <>
#     tag2.id`, `person1.id <> person3.id`) rather than on the node
#     (`tag1 <> tag2`). Every vertex here carries a unique per-label id, so the
#     two are the same predicate, and the property form is the one ArcadeDB's
#     openCypher accepts as well as Neo4j/Memgraph/FalkorDB.
# Message is the SNB supertype of Post and Comment; the Cypher engines reach it
# through inheritance (ArcadeDB) or a second label (Neo4j/Memgraph/FalkorDB) on
# every Post and Comment, so `(:Message)` matches both (see ldbc_snb.py).
# KNOWS is UNDIRECTED here, exactly as LSQB writes it (`-[:KNOWS]-`), which is
# why the LSQB queries use `-[:KNOWS]-` where the five hand-written analytics
# queries above use the directed `-[:KNOWS]->`.
#
# Each is a whole-graph count(*), so each digest is `columns=("n",)` (below),
# and the per-query budget (#100/#100a) bounds all fourteen alike.
LSQB_QUERIES = {
    # q1: the eight-label chain, Country<-City<-Person<-Forum->Post<-Comment->Tag->TagClass.
    "lsqb_q1": ("MATCH (:Country)<-[:IS_PART_OF]-(:City)<-[:IS_LOCATED_IN]-(:Person)"
                "<-[:HAS_MEMBER]-(:Forum)-[:CONTAINER_OF]->(:Post)<-[:REPLY_OF]-(:Comment)"
                "-[:HAS_TAG]->(:Tag)-[:HAS_TYPE]->(:TagClass) RETURN count(*) AS n"),
    # q2: friends where one commented a reply on the other's post.
    "lsqb_q2": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person), "
                "(person1)<-[:HAS_CREATOR]-(comment:Comment)-[:REPLY_OF]->(post:Post)"
                "-[:HAS_CREATOR]->(person2) RETURN count(*) AS n"),
    # q3: three people in one country, all pairwise KNOWS (country triangle).
    "lsqb_q3": ("MATCH (country:Country) "
                "MATCH (person1:Person)-[:IS_LOCATED_IN]->(city1:City)-[:IS_PART_OF]->(country) "
                "MATCH (person2:Person)-[:IS_LOCATED_IN]->(city2:City)-[:IS_PART_OF]->(country) "
                "MATCH (person3:Person)-[:IS_LOCATED_IN]->(city3:City)-[:IS_PART_OF]->(country) "
                "MATCH (person1)-[:KNOWS]-(person2)-[:KNOWS]-(person3)-[:KNOWS]-(person1) "
                "RETURN count(*) AS n"),
    # q4: a tagged message with a creator, a liker and an inbound reply.
    "lsqb_q4": ("MATCH (:Tag)<-[:HAS_TAG]-(message:Message)-[:HAS_CREATOR]->(creator:Person), "
                "(message)<-[:LIKES]-(liker:Person), "
                "(message)<-[:REPLY_OF]-(comment:Comment) RETURN count(*) AS n"),
    # q5: a message and a reply to it that carry two different tags.
    "lsqb_q5": ("MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Comment)"
                "-[:HAS_TAG]->(tag2:Tag) WHERE tag1.id <> tag2.id RETURN count(*) AS n"),
    # q6: a two-hop friend chain whose far end has a tag interest.
    "lsqb_q6": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)"
                "-[:HAS_INTEREST]->(tag:Tag) WHERE person1.id <> person3.id RETURN count(*) AS n"),
    # q7: q4's left join -- a tagged message with a creator, likers and replies OPTIONAL.
    "lsqb_q7": ("MATCH (:Tag)<-[:HAS_TAG]-(message:Message)-[:HAS_CREATOR]->(creator:Person) "
                "OPTIONAL MATCH (message)<-[:LIKES]-(liker:Person) "
                "OPTIONAL MATCH (message)<-[:REPLY_OF]-(comment:Comment) RETURN count(*) AS n"),
    # q8: q5 with the reply NOT itself carrying tag1 (anti-join).
    "lsqb_q8": ("MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Comment)"
                "-[:HAS_TAG]->(tag2:Tag) WHERE NOT (comment)-[:HAS_TAG]->(tag1) "
                "AND tag1.id <> tag2.id RETURN count(*) AS n"),
    # q9: q6 with person1 NOT directly KNOWS person3 (anti-join).
    "lsqb_q9": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)"
                "-[:HAS_INTEREST]->(tag:Tag) WHERE NOT (person1)-[:KNOWS]-(person3) "
                "AND person1.id <> person3.id RETURN count(*) AS n"),
}
# The table is five hand-written questions plus LSQB's nine = fourteen columns
# (DECISIONS #104). The harness iterates OLAP_QUERIES, so the nine join it here.
OLAP_QUERIES.update(LSQB_QUERIES)

# ---------------------------------------------------------------------------
# WHAT EACH ANSWER LOOKS LIKE (DECISIONS #88). Declared once per query, never
# per engine; the alternatives inside a tuple are the names the four dialects
# give the same column.
#
# A MEASURE IS DECLARED `num`, A COUNT IS NOT. The canonical form prints an int
# exactly and a float to six significant digits, and the two spellings coincide
# only below 10**6 -- so a column whose value an engine returns as an integer
# and its neighbour returns as a double is the SAME NUMBER canonicalised two
# ways, and the digest splits as soon as the value passes a million. That is
# not hypothetical: at TPC-H SF1 it split the pricing summary seven engines to
# one, with ArangoDB's integral SUM on one side and every SQL engine's double
# on the other (2026-09-14). `num` says "this column is a measure, compare it
# as a number", and is applied to every AVERAGE here.
#
# Counts, degrees, ages and identifiers deliberately stay exact: `d`, `n`,
# `deg`, `age` and the person key are whole numbers that every engine already
# agrees on, and rounding one to six significant digits would let two DIFFERENT
# counts collide. Declared once per query, never per engine, so it cannot be
# used to make one engine's answer match another's.
OLAP_DIGEST = {
    "top_degree": dict(columns=(("id", "pid"), "d"),
                       order_matters=True, order_key="d", id_key="id"),
    "same_city_edges": dict(columns=("c", "n"),
                            order_matters=True, order_key="n", id_key="c"),
    "friend_age_by_city": dict(columns=("c", "a", "n"),
                               order_matters=True, order_key="n", id_key="c",
                               coerce={"a": "num"}),
    "degree_dist": dict(columns=("deg", "n")),
    "triangles": dict(columns=("n",)),
}
# LSQB's nine are each a whole-graph count(*): one exact integer column `n`
# (DECISIONS #104). Not a `num` measure -- a count is compared exactly, so two
# different counts can never collide (see the note above).
OLAP_DIGEST.update({f"lsqb_q{i}": dict(columns=("n",)) for i in range(1, 10)})
READ_DIGEST = {
    "point": dict(columns=("name", "age")),
    "hop1": dict(columns=("n", "a"), coerce={"a": "num"}),
    "hop2": dict(columns=("n",)),
    "hop3f": dict(columns=("n",)),
}
# The person rows the CRUD phases leave behind, read back untimed.
# ("id", "pid") because SurrealDB records carry their own `id` and aliasing
# the person key onto that name would collide with the record id.
PERSON_STATE_DIGEST = dict(columns=(("id", "pid"), "name", "age", "city"))
VISITED_DIGEST = dict(columns=("id", "n"))
