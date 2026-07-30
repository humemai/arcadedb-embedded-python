#!/usr/bin/env python3
"""Hot-path driver for profiling the QUERY SURFACES over one graph.

The vector lanes have profiles; the graph lanes have none. Two questions this
answers that nothing else does:

  1. Where does a 2-hop actually spend its time? We established that latency
     tracks 2-hop result size (Spearman 0.971 at SF10), which says the work is
     proportional to the neighbourhood but not what the per-edge cost is made of.

  2. Cypher vs SQL MATCH over the SAME storage. The SciPy paper calls these two
     surfaces "at parity" while reporting 1.4 ms and 3.0 ms for them, which is a
     2.1x gap. Profiling both on one graph says whether the difference is
     translation overhead, a different plan, or the measurement.

SURFACE=cypher | sql selects which surface the loop drives. Both surfaces run
once at startup and their row counts must agree, or the driver aborts: profiling
two queries that return different answers would compare different work.

Prints QUERY-PHASE-START when the loop begins; loops for PROFILE_SECS.
"""
import os
import random
import time

SURFACE = os.environ.get("SURFACE", "cypher")
QUERY = os.environ.get("SURFACE_QUERY", "hop2")
SCALE = os.environ.get("BENCH_GRAPH_SCALE", "sf1")
SECS = int(os.environ.get("PROFILE_SECS", "1200"))
N_SEEDS = int(os.environ.get("SURFACE_SEEDS", "200"))

# ArcadeDB SQL MATCH equivalents of graph_common.OLTP_READS. Kept beside the
# Cypher text rather than derived from it: these are two hand-written surfaces
# and the point is to compare them as a user would write them.
SQL_READS = {
    "point": "SELECT name, age FROM Person WHERE id = {id}",
    "hop1": ("SELECT count(*) AS n, avg(f.age) AS a FROM ("
             "MATCH {{type: Person, as: p, where: (id = {id})}}"
             "-KNOWS->{{type: Person, as: f}} RETURN f)"),
    "hop2": ("SELECT count(DISTINCT fof) AS n FROM ("
             "MATCH {{type: Person, as: p, where: (id = {id})}}"
             "-KNOWS->{{as: m}}-KNOWS->{{type: Person, as: fof}} RETURN fof)"),
}


def main():
    os.environ.setdefault("BENCH_GRAPH_SOURCE", "ldbc")
    import l2_graph
    import ldbc_snb as _ldbc
    from graph_common import OLTP_READS

    # l2_graph rebinds its generators to LDBC only inside its own main(), so a
    # driver that imports it gets the synthetic graph unless it rebinds too.
    # This exact bug made an earlier probe measure a graph the seeds did not
    # address; see hop2_degree_probe.py.
    l2_graph.gen_persons = lambda _n: _ldbc.gen_persons(SCALE)
    l2_graph.gen_edges = lambda _n: _ldbc.gen_edges(SCALE)

    be = l2_graph.BACKENDS["arcadedb_graph_embedded"]()
    be.connect()
    be.build(_ldbc.SCALE_PERSONS[SCALE])
    be.post_build("oltp")

    rnd = random.Random(20260730)
    seeds = [rnd.randrange(_ldbc.SCALE_PERSONS[SCALE]) for _ in range(N_SEEDS)]

    cy = OLTP_READS[QUERY]
    sq = SQL_READS[QUERY]

    def run_cypher(i):
        return be.db.query("opencypher", cy.format(id=seeds[i % len(seeds)]))

    def run_sql(i):
        return be.db.query("sql", sq.format(id=seeds[i % len(seeds)]))

    # Equivalence guard. Both surfaces must answer the same question over the
    # same seeds before either is profiled, and the answer must be non-empty:
    # a query returning zero rows is not a fast query, it is a broken one.
    mismatch = 0
    nonempty = 0
    for i in range(20):
        a = len(run_cypher(i).to_json_list())
        b = len(run_sql(i).to_json_list())
        if a != b:
            mismatch += 1
        if a > 0:
            nonempty += 1
    if mismatch:
        raise SystemExit(
            f"ABORT: cypher and sql disagreed on {mismatch}/20 seeds for "
            f"{QUERY}; profiling them would compare different work")
    if nonempty == 0:
        raise SystemExit(
            f"ABORT: {QUERY} returned zero rows on all 20 seeds; the seeds do "
            f"not address this graph")
    print(f"EQUIV-OK {QUERY} surfaces agree on 20 seeds, {nonempty} non-empty",
          flush=True)

    run = run_cypher if SURFACE == "cypher" else run_sql

    # Time both surfaces before the profile so the flame graph has a latency
    # number sitting next to it rather than needing one from another run.
    for label, fn in (("cypher", run_cypher), ("sql", run_sql)):
        ts = []
        for i in range(60):
            t0 = time.perf_counter()
            fn(i).to_json_list()
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        print(f"LATENCY {label} p50={ts[len(ts)//2]:.2f}ms "
              f"p95={ts[int(len(ts)*0.95)]:.2f}ms n=60", flush=True)

    for i in range(20):
        run(i).to_json_list()
    print("QUERY-PHASE-START", flush=True)
    t0 = time.perf_counter()
    i = 0
    while time.perf_counter() - t0 < SECS:
        run(i).to_json_list()
        i += 1
    print(f"QUERY-PHASE-END n={i}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
