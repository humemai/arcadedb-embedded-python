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
OLAP_ITERATIONS = 5

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
#   opencypher, Neo4j, and Kuzu-lineage LadybugDB)
OLTP_READS = {
    "point": ("MATCH (p:Person) WHERE p.id = {id} "
              "RETURN p.name, p.age"),
    "hop1": ("MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} "
             "RETURN count(f) AS n, avg(f.age) AS a"),
    "hop2": ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) "
             "WHERE p.id = {id} RETURN count(DISTINCT fof) AS n"),
}
# write op: create a person and link them to an existing one (one txn)
OLTP_WRITE = ("MATCH (p:Person) WHERE p.id = {id} "
              "CREATE (q:Person {{id: {new_id}, name: 'w{new_id}', age: 33, "
              "city: 'city_0'}}) "
              "CREATE (p)-[:KNOWS {{since: 2026}}]->(q)")

OLAP_QUERIES = {
    "top_degree": ("MATCH (p:Person)-[:KNOWS]->(:Person) "
                   "RETURN p.id AS id, count(*) AS d ORDER BY d DESC LIMIT 10"),
    "same_city_edges": ("MATCH (a:Person)-[:KNOWS]->(b:Person) "
                        "WHERE a.city = b.city "
                        "RETURN a.city AS c, count(*) AS n ORDER BY n DESC "
                        "LIMIT 10"),
    "friend_age_by_city": ("MATCH (p:Person)-[:KNOWS]->(f:Person) "
                           "RETURN p.city AS c, avg(f.age) AS a, count(*) AS n "
                           "ORDER BY n DESC LIMIT 10"),
}
