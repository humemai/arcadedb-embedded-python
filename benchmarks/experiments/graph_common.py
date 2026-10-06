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

# THE TRANSACTIONAL READS GET THE SAME KIND OF BUDGET (DECISIONS #120). One
# per read, covering both of its passes over the start set; a read that spends
# it stops, keeps its percentiles over the starts it answered, and records
# `<read>_censored`, `<read>_budget_s` and `<read>_iters` as the analytics
# queries do, so the other reads and the writes in the cell keep their numbers.
# Until the re-pin one slow read timed the whole cell out: with the three-hop
# filter keeping half (BUGS F146), SurrealDB embedded's 2.3.10 core dedups
# quadratically and its SF1 cell hit the one-hour cap with nothing recorded.
# 1,800 s is the documents lane's per-query budget (#100a); budget_lookup
# clamps it to a read's share of the cell cap (540 s at SF1, the full 1,800 s
# at SF10). The slowest engine that answers, MongoDB, spent about 220 s on the
# three-hop read's two passes at SF1 on the laptop.
OLTP_READ_BUDGET_S = float(_os.environ.get("BENCH_GRAPH_READ_BUDGET_S") or 1800.0)

GRAPH_SEED = 20260708
PICK_SEED = 777

# THE READS' UNTIMED WARM-UP (CAMPAIGN section 7 row 55, DECISIONS #148, which implements #89 and PROTOCOL.md's
# rule that warm queries are disjoint from the cold ones). Through October the lane timed its reads twice over the SAME start
# persons and the table printed the first pass, so for an engine on a JVM the printed column included the JIT
# compiling the query path: ArcadeDB embedded's SF1 point p50 was 3.59x its second pass, Neo4j's 2.13x, every
# engine not on a JVM 0.89x to 1.10x. Every engine now runs READ_WARMUP_IDS untimed reads of each operation on start
# persons the timed set never asks for (the Java control: an untimed warm-up over disjoint ids removed 87-94% of the
# excess), the table prints the warm median, and the one cold number is the first query of the session. The count is
# a property of the lane, never of an engine; BENCH_GRAPH_READ_WARMUP lowers it for a laptop smoke and the row records
# what ran. A warm-up that would take longer than READ_WARMUP_BUDGET_SHARE of its read's budget stops there (the
# slowest engines' three-hop read), and the row records how many it ran.
READ_WARMUP_IDS = int(_os.environ.get("BENCH_GRAPH_READ_WARMUP") or 1000)
READ_WARMUP_SEED = PICK_SEED + 1
READ_WARMUP_BUDGET_SHARE = 0.25


def warmup_ids(universe, timed_ids, n=None, seed=READ_WARMUP_SEED):
    """`n` start persons for the untimed warm-up: distinct, deterministic, and NONE of them in `timed_ids`.

    `universe` is every person id the corpus holds (LDBC ids are sparse). Fewer than `n` candidates return all of them."""
    n = READ_WARMUP_IDS if n is None else n
    timed = set(timed_ids)
    pool = [i for i in universe if i not in timed]
    if len(pool) <= n:
        return pool
    return random.Random(seed).sample(pool, n)


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
# Cypher text templates with BOUND PARAMETERS ($id, $new_id, $name), passed
# by each adapter through its own driver (DECISIONS #116 item 2; BUGS F125).
# Until the re-pin to 26.10.1 the values were pasted into the text, so every
# call was a new text: engines that cache plans by text (ArcadeDB, Neo4j)
# re-planned each call, engines that do not (Memgraph) paid nothing, and the
# table measured that difference instead of the lookups (#8132, #8286).
# Binding is every engine's documented way to send a value. The one engine
# that cannot take parameters in a graph query (DuckPGQ, cwida/duckpgq-
# extension#75) pastes into its own SQL/PGQ texts and says so on its class.
#   (WHERE form, not inline property maps — portable across ArcadeDB
#   opencypher, Neo4j, and LadybugDB)
# THE FAR-END FILTER OF `hop3f`, one number for every engine's spelling of the
# query (Cypher here; SQL/PGQ, SurrealQL, AQL, and the MongoDB pipeline in
# l2_graph.py read it too). It was 30 through October, when every LDBC age was
# 0 (BUGS F146: the epoch-millisecond birthday was read as a date string), so
# the filter matched nobody. Parsed correctly, LDBC ages span 36-46 at SF1 and
# SF10, so 30 would match everybody; 41 keeps 49.7% (SF1) and 49.3% (SF10),
# which is a filter that filters.
HOP3F_MIN_AGE = 41

# EVERY GRAPH QUESTION IS ASKED UNDIRECTED (CAMPAIGN section 7 row 56, DECISIONS
# #151 item 1, BUGS F169). LDBC lists each friendship ONCE, always from the smaller
# person id to the larger (all 180,623 SF1 rows), and the lane loads each row as one
# KNOWS edge, so a question that follows `->` answers a question about ids: 1-hop saw
# 53.2% of a start person's friends, 2-hop and 3-hop followed rising ids, and the
# triangle count was 0 on every engine by construction. Each friendship stays ONE
# stored edge (load and storage are unchanged: doubling the edges was rejected, it
# moves ingest and storage and is not how LDBC defines knows), and every question is
# asked in each dialect's undirected or ANY form: `-[:KNOWS]-` here, and the
# equivalents l2_graph spells for the other dialects, the way LSQB's nine already
# were. THE QUESTION, in one sentence every dialect must answer the same: walks of
# k distinct friendships (Cypher's relationship isomorphism: a friendship is not
# walked back along itself), counted per walk, where a friendship counts once
# whichever way it is stored; a question that counts friendships or triangles counts
# each one once (friends in same city with `a.id < b.id`, a triangle with
# `a.id < b.id < c.id`). The row records `knows_direction` so the page's one-way
# disclosure (export_web._knows_one_way_note) retires from the rows.
KNOWS_DIRECTION = "undirected"
KNOWS_DIRECTION_FIELD = "knows_direction"   # the row field; export_web._KNOWS_DIRECTION_FIELD reads it

OLTP_READS = {
    # ALIASED RETURN COLUMNS (2026-10). `RETURN p.name, p.age` gives the column
    # the driver's own spelling -- "p.name" through the Neo4j driver, a
    # positional value through LadybugDB, "name" through the SurrealDB and
    # ArangoDB hooks -- and a digest cannot compare three spellings of one
    # column (DECISIONS #88). The alias costs nothing and makes the answer
    # comparable.
    "point": ("MATCH (p:Person) WHERE p.id = $id "
              "RETURN p.name AS name, p.age AS age"),
    "hop1": ("MATCH (p:Person)-[:KNOWS]-(f:Person) WHERE p.id = $id "
             "RETURN count(f) AS n, avg(f.age) AS a"),
    "hop2": ("MATCH (p:Person)-[:KNOWS]-(:Person)-[:KNOWS]-(fof:Person) "
             "WHERE p.id = $id RETURN count(DISTINCT fof) AS n"),
    # 2026-10 (DECISIONS #82): three hops with a property filter on the far
    # end, the interactive workload's characteristic shape, where the planner
    # decides whether the filter or the expansion goes first. The threshold is
    # HOP3F_MIN_AGE, shared by every engine's spelling (BUGS F146).
    "hop3f": ("MATCH (p:Person)-[:KNOWS]-(:Person)-[:KNOWS]-(:Person)-[:KNOWS]-(x:Person) "
              "WHERE p.id = $id AND x.age > " + str(HOP3F_MIN_AGE) + " RETURN count(DISTINCT x) AS n"),
}
# write op: create a person and link them to an existing one (one txn).
# $name is "w" + new_id, passed by the caller, so the text has no string
# building in it.
OLTP_WRITE = ("MATCH (p:Person) WHERE p.id = $id "
              "CREATE (q:Person {id: $new_id, name: $name, age: 33, "
              "city: 'city_0'}) "
              "CREATE (p)-[:KNOWS {since: 2026}]->(q)")

# 2026-10 (DECISIONS #82): the write's partner. Delete the person the write
# created, with the edge that linked them, one transaction; the page then
# carries a delete per engine, which no table did.
OLTP_DELETE = "MATCH (q:Person) WHERE q.id = $new_id DETACH DELETE q"

# 2026-10 (DECISIONS #82a): the fourth single-record operation. One property
# of one record, set to a fixed value so the post-state is deterministic and
# every engine must agree on it.
OLTP_UPDATE = "MATCH (q:Person) WHERE q.id = $new_id SET q.age = 44"
UPDATE_AGE = 44

# HOW LOCAL IS THE THREE-HOP READ? The page will say the filtered three-hop
# read stays local; that is a claim about the data, not about the engine, and
# until now nothing recorded the number it rests on. This is hop3f without the
# age filter: the distinct persons at exactly three hops, which is the set the
# filter is applied to. Run UNTIMED, once per cell, over a small sample of the
# same ids the timed loop uses, so a reader can check "stays local" against a
# number instead of a word.
HOP3_VISITED = ("MATCH (p:Person)-[:KNOWS]-(:Person)-[:KNOWS]-(:Person)-[:KNOWS]-(x:Person) "
                "WHERE p.id = $id RETURN count(DISTINCT x) AS n")
VISITED_SAMPLE = 20

# FOR AN ENGINE WHOSE MATCH MAY WALK A RELATIONSHIP TWICE. Cypher's MATCH forbids reusing a relationship within one pattern
# (relationship isomorphism), and that rule is what makes the 2-hop and 3-hop reads above the question "walks of k DISTINCT
# friendships". FalkorDB and LadybugDB do not apply it to a chain of relationships: on the SF1 slice both answered the 2-hop,
# filtered 3-hop and visited reads differently from a DuckDB reference (the point and 1-hop reads, which have one relationship,
# agreed), because the walk from the start along a friendship and straight back along the same friendship was counted, so the
# start person was its own friend of a friend. The same question for them names the exclusions on the vertices, as DuckPGQ's and
# SurrealQL's spellings do: in a simple graph (LDBC's knows holds each friendship once) the walks the exclusions remove are
# exactly the walks that reuse a relationship, so the two spellings answer alike. The mechanism is `Base.REPEATS_RELATIONSHIPS`.
OLTP_READS_BY_VERTEX = {
    **OLTP_READS,
    "hop2": ("MATCH (p:Person)-[:KNOWS]-(m:Person)-[:KNOWS]-(fof:Person) "
             "WHERE p.id = $id AND fof <> p RETURN count(DISTINCT fof) AS n"),
    "hop3f": ("MATCH (p:Person)-[:KNOWS]-(m1:Person)-[:KNOWS]-(m2:Person)-[:KNOWS]-(x:Person) "
              "WHERE p.id = $id AND m2 <> p AND x <> m1 AND x.age > " + str(HOP3F_MIN_AGE) + " RETURN count(DISTINCT x) AS n"),
}
HOP3_VISITED_BY_VERTEX = ("MATCH (p:Person)-[:KNOWS]-(m1:Person)-[:KNOWS]-(m2:Person)-[:KNOWS]-(x:Person) "
                          "WHERE p.id = $id AND m2 <> p AND x <> m1 RETURN count(DISTINCT x) AS n")


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
# QUERIES THAT DO NOT RUN AT A GIVEN TIER, with the measurement that says why.
#
# Not "this engine cannot express it" (that is each adapter's UNEXPRESSIBLE,
# DECISIONS #88) but "at this corpus size this question is not measurable
# under the protocol, for anybody". October's first analytics cell was
# censored at the two-hour cap with our OWN engine, and the cause was one
# query's FIRST TOUCH: lsqb_q6 took 1,384 s on the full SF1 network against
# 14 s on the skeleton slice, a 98x blow-up, and a budget caps ITERATIONS,
# never the first touch (BUGS F74).
#
# Projecting every engine's skeleton numbers through that same 98x says all
# fourteen queries put 3 of 11 engines over the cap on first touches alone and
# these two dominate: dropping them brings eight engines home, including both
# of ours. The three that remain over are censored with the cap named, which
# is a true statement about those engines at that size.
#
# The row records the exclusion so the page declares it rather than printing a
# silent blank, and it is keyed by TIER: both queries still run, and are
# published, at sf1 and sf10.
TIER_EXCLUDED = {
    ("sf1full", "lsqb_q6"):
        "not measurable at this size: its first touch alone took 1,384 s on "
        "ArcadeDB embedded against a 7,200 s whole-cell cap, and a per-query "
        "budget bounds iterations rather than the first touch",
    ("sf1full", "lsqb_q9"):
        "not measurable at this size: 602 s on a laptop skeleton slice for "
        "ArcadeDB embedded and 2,146 s for SurrealDB, which the measured 98x "
        "slice-to-full-network blow-up puts far past the whole-cell cap",
}


def tier_excluded(scale, qname):
    """The reason this query does not run at this tier, or None."""
    return TIER_EXCLUDED.get((str(scale), str(qname)))


OLAP_QUERIES = {
    # UNDIRECTED (row 56): a person's friends are the other end of every friendship
    # touching them, so a friendship counts for BOTH of its people.
    "top_degree": ("MATCH (p:Person)-[:KNOWS]-(:Person) "
                   "RETURN p.id AS id, count(*) AS d ORDER BY d DESC, id ASC LIMIT 10"),
    # One row per friendship, so the pair is ordered (a.id < b.id) to count it once.
    "same_city_edges": ("MATCH (a:Person)-[:KNOWS]-(b:Person) "
                        "WHERE a.city = b.city AND a.id < b.id "
                        "RETURN a.city AS c, count(*) AS n ORDER BY n DESC, c ASC "
                        "LIMIT 10"),
    "friend_age_by_city": ("MATCH (p:Person)-[:KNOWS]-(f:Person) "
                           "RETURN p.city AS c, avg(f.age) AS a, count(*) AS n "
                           "ORDER BY n DESC, c ASC LIMIT 10"),
    # 2026-10 (DECISIONS #82b), so the graph table is as thorough as the
    # document one: five analytics queries on each.
    #
    # The degree distribution: how many people have how many friends. A
    # whole-graph aggregation over every edge, and the cheapest honest way to
    # make the planner touch everything. Persons with no friends are outside
    # the MATCH and therefore outside the histogram, on every engine, which is
    # stated here because it is the one modelling choice in it.
    "degree_dist": ("MATCH (p:Person)-[:KNOWS]-(f:Person) "
                    "WITH p, count(f) AS d "
                    "RETURN d AS deg, count(*) AS n ORDER BY deg"),
    # The triangle count: three people who are all friends with one another,
    # each triangle counted once. The canonical graph analytic, and the one
    # query on the page that punishes a bad join or traversal plan rather than
    # a slow scan. Ordering the three ids a < b < c selects exactly one of a
    # triangle's six walks, so each triangle is counted once on every engine.
    # (Through October this followed `->` and asked for a directed 3-cycle, which
    # a graph stored from the smaller id to the larger cannot hold: 0 on every
    # engine, 387,573 triangles at SF1 undirected; BUGS F169.) Expected to exceed
    # its budget at the larger scale factor, which is a named censored cell and
    # not a bug (#82b).
    "triangles": ("MATCH (a:Person)-[:KNOWS]-(b:Person)-[:KNOWS]-(c:Person)-[:KNOWS]-(a) "
                  "WHERE a.id < b.id AND b.id < c.id RETURN count(*) AS n"),
}

# ---------------------------------------------------------------------------
# LSQB's nine pattern-matching queries (DECISIONS #104), on the FULL social
# network at SF1 that the analytics table moves to (#103b). Canonical Cypher
# from github.com/ldbc/lsqb (cypher/q1.cypher .. q9.cypher), taken nearly
# verbatim; the only change to the published text is:
#   * `RETURN count(*) AS n` in place of `AS count`, the one alias the digest
#     compares against on every engine (the same reason the five above alias).
# LSQB'S NODE INEQUALITY IS KEPT (CAMPAIGN section 7 row 60, DECISIONS #154 item 1,
# BUGS F174): q5, q6, q8, and q9 compare two matched NODES (`tag1 <> tag2`,
# `person1 <> person3`), not their ids. From 2026-09-18 (`d1fe3183a0`) this file
# wrote the id property instead (`tag1.id <> tag2.id`), on the belief that
# ArcadeDB's openCypher needed it; it does not, and its planner recognises only
# the inequality between two node variables for the count operators it has for
# q5, q6, and q9 (`COUNT ANTI-JOIN CHAIN` for q9). The id form sent all four to
# the row pipeline and cost Neo4j 1.4-1.7x too. Every row records `lsqb_text`
# (LSQB_TEXT below) so the page's id-form disclosure retires from the rows.
# Message is the SNB supertype of Post and Comment; the Cypher engines reach it
# through inheritance (ArcadeDB) or a second label (Neo4j/Memgraph/FalkorDB) on
# every Post and Comment, so `(:Message)` matches both (see ldbc_snb.py).
# KNOWS is UNDIRECTED here, exactly as LSQB writes it (`-[:KNOWS]-`), and since
# the re-pin (row 56) the five hand-written analytics questions above ask it the
# same way.
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
                "-[:HAS_TAG]->(tag2:Tag) WHERE tag1 <> tag2 RETURN count(*) AS n"),
    # q6: a two-hop friend chain whose far end has a tag interest.
    "lsqb_q6": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)"
                "-[:HAS_INTEREST]->(tag:Tag) WHERE person1 <> person3 RETURN count(*) AS n"),
    # q7: q4's left join -- a tagged message with a creator, likers and replies OPTIONAL.
    "lsqb_q7": ("MATCH (:Tag)<-[:HAS_TAG]-(message:Message)-[:HAS_CREATOR]->(creator:Person) "
                "OPTIONAL MATCH (message)<-[:LIKES]-(liker:Person) "
                "OPTIONAL MATCH (message)<-[:REPLY_OF]-(comment:Comment) RETURN count(*) AS n"),
    # q8: q5 with the reply NOT itself carrying tag1 (anti-join).
    "lsqb_q8": ("MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Comment)"
                "-[:HAS_TAG]->(tag2:Tag) WHERE NOT (comment)-[:HAS_TAG]->(tag1) "
                "AND tag1 <> tag2 RETURN count(*) AS n"),
    # q9: q6 with person1 NOT directly KNOWS person3 (anti-join).
    "lsqb_q9": ("MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)"
                "-[:HAS_INTEREST]->(tag:Tag) WHERE NOT (person1)-[:KNOWS]-(person3) "
                "AND person1 <> person3 RETURN count(*) AS n"),
}
# The table is five hand-written questions plus LSQB's nine = fourteen columns
# (DECISIONS #104). The harness iterates OLAP_QUERIES, so the nine join it here.
OLAP_QUERIES.update(LSQB_QUERIES)

# The row field the page's id-form sentence reads (export_web._LSQB_TEXT_FIELD) and its value: LSQB's own text, every
# engine, in the dialect LSQB publishes for it (a dialect with no LSQB text is checked against it, row 60).
LSQB_TEXT_FIELD = "lsqb_text"
LSQB_TEXT = "lsqb"

# AND THE NINE NEED THE MESSAGE HALF. Every one of them counts a pattern over
# Forum, Post, Comment, Tag, TagClass or Country, which ldbc_snb.MessageCorpus
# loads for the analytics workload on the full LDBC network and NOWHERE else
# (DECISIONS #103b/#104: l2_graph sets ad._load_messages from the source and
# the workload). The synthetic interactive corpus holds Person, City and KNOWS
# and nothing else.
#
# Asked anyway, they do not fail: they return `0` in one row, nine times, on
# every engine. l2_graph.build_messages' own docstring names this -- "so an
# engine missing the loader is obvious rather than silently running LSQB's
# nine queries on an empty message half" -- and guards the LOADER while the
# query loop stayed unguarded, so the October l2/micro re-run recorded nine
# digests of `(0)` beside cold times of 4-34 ms. That is a measurement of how
# fast an engine can count nothing, and it is not comparable with the same
# column at SF1, where the labels exist.
#
# It also breaks the answer check in the one direction that matters: the
# comparator rows at micro predate the nine and record no digest, so
# equivalence E3 reads "ArcadeDB answered nine queries its neighbours did not"
# -- eight engines x nine queries = 72 failures -- and refuses the publish.
# The absence belongs to the CORPUS and not to any engine, which is why this
# is a skip with a reason on the row rather than nine per-engine
# `unexpressible` declarations (#92 forbids those without an engine error, and
# there is none: every engine expresses these queries fine).
NA_LSQB_NO_MESSAGE_HALF = (
    "LSQB's nine are not asked on this row: they count patterns over the SNB "
    "message half (Forum, Post, Comment, Tag, TagClass, Country), which is "
    "loaded only for the analytics workload on the full LDBC network "
    "(DECISIONS #103b/#104). This row's corpus holds persons, cities and "
    "KNOWS, so each of the nine would count zero matches over labels that do "
    "not exist and time how long that takes.")

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
# THE EDGE HALF OF THE WRITE (CAMPAIGN section 7 row 58, BUGS F172). OLTP_WRITE creates a person AND the KNOWS edge into
# them, and OLTP_DELETE removes the person AND their edge (DETACH DELETE); the person digests above read the persons only,
# so an engine that skipped the edge write, or left the edge behind on delete, printed a faster write and passed every
# gate. Read back untimed after the insert (one edge into every written person) and after the delete (none): the KNOWS
# edges whose far end is a written person, as (source person id, written person id).
EDGE_STATE_DIGEST = dict(columns=("src", "dst"))
EDGE_SCAN = ("MATCH (a:Person)-[:KNOWS]->(q:Person) WHERE q.id >= $f "
             "RETURN a.id AS src, q.id AS dst")
VISITED_DIGEST = dict(columns=("id", "n"))
