#!/usr/bin/env python3
"""Do the two surfaces return the same ROWS, or just the same NUMBER of rows?

queue49 measured Cypher at 1.7-1.8x SQL MATCH on the identical 2-hop traversal
and called the comparison equivalent. Its equivalence check was

    a = len(run_cypher(i).to_json_list())
    b = len(run_sql(i).to_json_list())

which compares cardinality and nothing else. The profiles then showed
ImmutableDocument.getPropertyNames at 7.0% on the Cypher side and 0.0% on the
SQL side, and ResultInternal.getPropertyNames at 11.5% against 6.4%, which is
what enumerating every property of every returned row looks like on one side
only. If Cypher materialises whole vertices where SQL MATCH materialises
references, the surfaces return the same COUNT of different things and the
1.7x is not a latency comparison.

SETUP IS COPIED FROM profile_surface_driver.py ON PURPOSE. Writing this probe
from scratch cost four consecutive runs, each dying on a different property of
one object: the registry's NAME (BACKENDS vs ADAPTERS, queue38), its SHAPE
(list vs dict, queue52), its VALUE type (class vs instance, queue52b), and
then build()/post_build() arities and the query language string, which is
"opencypher" and not "cypher". The driver already encodes all of it and is
known to run. Copy the working sequence; do not re-derive it.
"""
import json
import os
import sys

SCALE = os.environ.get("BENCH_GRAPH_SCALE", "sf1")
N_SEEDS = int(os.environ.get("N_SEEDS", "20"))

SQL_READS = {
    "hop1": ("MATCH {{type: Person, as: p, where: (id = {id})}}"
             ".out('KNOWS'){{as: f}} RETURN DISTINCT f"),
    "hop2": ("MATCH {{type: Person, as: p, where: (id = {id})}}"
             ".out('KNOWS'){{as: m}}.out('KNOWS'){{as: fof}} RETURN DISTINCT fof"),
}
CYPHER_READS = {
    "hop1": ("MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} "
             "RETURN DISTINCT f"),
    "hop2": ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) "
             "WHERE p.id = {id} RETURN DISTINCT fof"),
}


def _ids(rows):
    """Row identity, however the surface chose to express it."""
    out = set()
    for r in rows:
        v = r.get("@rid") or r.get("rid")
        if v is None:
            inner = next((x for x in r.values() if isinstance(x, dict)), None)
            src = inner if inner else r
            v = src.get("@rid") or src.get("id")
        out.add(str(v))
    return out


def main():
    os.environ.setdefault("BENCH_GRAPH_SOURCE", "ldbc")
    import l2_graph
    import ldbc_snb as _ldbc

    # Mirror l2_graph.main()'s LDBC setup exactly: adapters resolve these three
    # names from module globals at call time, and pick_query_ids matters as
    # much as the generators because LDBC ids are sparse longs.
    l2_graph.gen_persons = lambda _n: _ldbc.gen_persons(SCALE)
    l2_graph.gen_edges = lambda _n: _ldbc.gen_edges(SCALE)
    l2_graph.pick_query_ids = lambda _n, k: _ldbc.pick_query_ids(SCALE, k)

    be = l2_graph.ADAPTERS["arcadedb_graph_embedded"]()
    be.connect()
    be.build(l2_graph.SCALE_PERSONS[SCALE])
    be.post_build("oltp")

    seeds = list(_ldbc.pick_query_ids(SCALE, N_SEEDS))
    print(f"engine {be.version}  scale {SCALE}  seeds {len(seeds)}", flush=True)

    for q in ("hop1", "hop2"):
        cy_n = sq_n = cy_b = sq_b = agree = 0
        cy_keys, sq_keys = set(), set()
        sample = None
        for sid in seeds:
            c = be.db.query("opencypher",
                            CYPHER_READS[q].format(id=sid)).to_json_list()
            s = be.db.query("sql", SQL_READS[q].format(id=sid)).to_json_list()
            cy_n += len(c)
            sq_n += len(s)
            cy_b += len(json.dumps(c))
            sq_b += len(json.dumps(s))
            for r in c:
                cy_keys |= set(r.keys())
            for r in s:
                sq_keys |= set(r.keys())
            if _ids(c) == _ids(s):
                agree += 1
            if sample is None and c and s:
                sample = (c[0], s[0])

        ratio = cy_b / max(sq_b, 1)
        print(f"\n=== {q} over {len(seeds)} seeds ===")
        print(f"  rows        cypher {cy_n:6}   sql {sq_n:6}   "
              f"{'same' if cy_n == sq_n else 'DIFFER'}")
        print(f"  json bytes  cypher {cy_b:7}  sql {sq_b:7}  ratio {ratio:.2f}x")
        print(f"  cypher keys {sorted(cy_keys)[:10]}")
        print(f"  sql    keys {sorted(sq_keys)[:10]}")
        print(f"  identity sets agree on {agree}/{len(seeds)} seeds")
        if sample:
            print(f"  sample cypher row {json.dumps(sample[0])[:180]}")
            print(f"  sample sql    row {json.dumps(sample[1])[:180]}")
        if cy_n == sq_n and ratio > 1.15:
            print(f"  VERDICT {q}: SAME row count, cypher payload {ratio:.2f}x "
                  f"larger. The surfaces return different data, so the latency "
                  f"ratio is NOT like-for-like.")
        elif cy_n == sq_n and abs(cy_b - sq_b) <= 0.15 * sq_b:
            print(f"  VERDICT {q}: same rows AND comparable payload "
                  f"({ratio:.2f}x). The latency ratio IS like-for-like.")
        else:
            print(f"  VERDICT {q}: inconclusive, inspect the key sets above.")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    # A leaked Database keeps non-daemon JVM threads alive (#5418), so exit
    # explicitly on the success path only; in a finally it eats the traceback.
    os._exit(0)
