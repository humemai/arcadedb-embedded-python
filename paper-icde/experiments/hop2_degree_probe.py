#!/usr/bin/env python3
"""Is ArcadeDB's 2-hop latency tail explained by seed degree?

Task #100. From the campaign data, ArcadeDB is 3x FASTER than Neo4j and
LadybugDB at the 2-hop median (1.57 vs 4.72 vs 5.59 ms at SF10) but ~2x slower
at p99, and its p99/p50 dispersion is 11.6x where both comparators sit near 2x.
Median and tail scale together from SF1 to SF10, so the tail is wide rather than
diverging.

Hypothesis: per-query cost tracks the size of the 2-hop neighbourhood,
count(DISTINCT fof) forces that set to be materialised, and LDBC person degree
is power-law, so the latency tail is the degree tail.

Percentiles alone are anecdotal. What made the sparse cliff (#5388) actionable
was a rank correlation between per-query latency and summed posting mass. This
does the same thing for degree, and runs the identical query against Neo4j so
the comparison is like for like: if their dispersion is flat in degree and ours
is not, that is the finding.

Env: BENCH_GRAPH_SCALE (sf1|sf10), PROBE_OUT, PROBE_BACKENDS.
"""
import json
import os
import statistics
import time

SCALE = os.environ.get("BENCH_GRAPH_SCALE", "sf10")
N_SEEDS = int(os.environ.get("PROBE_SEEDS", "400"))
BACKENDS = os.environ.get("PROBE_BACKENDS", "arcadedb_graph_embedded,neo4j_graph").split(",")

# The timed query is the campaign's exact 2-hop text (graph_common OLTP_READS).
HOP2 = ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) "
        "WHERE p.id = {id} RETURN count(DISTINCT fof) AS n")
# Neighbourhood sizes come from row COUNTS, because the adapters' run_cypher
# returns len(rows) rather than the rows themselves. Measured untimed.
DEG2_ROWS = ("MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) "
             "WHERE p.id = {id} RETURN DISTINCT fof")
DEG1_ROWS = ("MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} "
             "RETURN f")


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main():
    from l2_graph import ADAPTERS as BE, SCALE_PERSONS
    from ldbc_snb import pick_query_ids

    out = {"scale": SCALE, "n_seeds": N_SEEDS, "backends": {}}
    seeds = pick_query_ids(SCALE, N_SEEDS)
    n_persons = SCALE_PERSONS[SCALE]

    for name in BACKENDS:
        b = BE[name]()
        b.connect()
        # connect() creates an EMPTY database (ArcadeDB: create_database
        # "/tmp/l2_arcade"), so the graph has to be built here or every query
        # returns zero rows and the correlation is computed over nothing.
        t0 = time.perf_counter()
        b.build(n_persons)
        b.post_build("oltp")
        print(f"BUILT {name} {n_persons} persons in "
              f"{time.perf_counter() - t0:.1f}s", flush=True)
        # refuse to measure an empty graph
        probe_deg = b.run_cypher(DEG1_ROWS.format(id=seeds[0]))
        total = b.run_cypher("MATCH (p:Person) RETURN p")
        if total < n_persons // 2:
            raise SystemExit(f"ABORT {name}: only {total} persons after build")
        print(f"SANITY {name} persons={total} deg1(seed0)={probe_deg}", flush=True)
        rows = []
        for sid in seeds:
            # sizes first and untimed, so they are excluded from the measurement
            deg1 = b.run_cypher(DEG1_ROWS.format(id=sid))
            deg2 = b.run_cypher(DEG2_ROWS.format(id=sid))
            t = time.perf_counter()
            b.run_cypher(HOP2.format(id=sid))
            ms = (time.perf_counter() - t) * 1000
            rows.append({"id": sid, "ms": ms, "deg1": deg1, "deg2": deg2})
        b.close()

        ms = [r["ms"] for r in rows]
        d2 = [r["deg2"] for r in rows]
        d1s = [r["deg1"] for r in rows]
        srt = sorted(ms)
        p50 = statistics.median(srt)
        p99 = srt[min(len(srt) - 1, int(0.99 * len(srt)))]
        # deciles by 2-hop neighbourhood size
        pairs = sorted(zip(d2, ms))
        dec = []
        for i in range(10):
            lo, hi = i * len(pairs) // 10, (i + 1) * len(pairs) // 10
            chunk = [m for _, m in pairs[lo:hi]]
            dec.append(round(statistics.median(chunk), 3) if chunk else None)
        out["backends"][name] = {
            "p50_ms": round(p50, 3), "p99_ms": round(p99, 3),
            "dispersion_p99_over_p50": round(p99 / p50, 2) if p50 else None,
            "spearman_ms_vs_deg2": round(spearman(d2, ms), 3),
            "spearman_ms_vs_deg1": round(spearman(d1s, ms), 3),
            "decile_median_ms_by_deg2": dec,
            "deg2_p10": pairs[len(pairs) // 10][0],
            "deg2_p90": pairs[9 * len(pairs) // 10][0],
        }
        print(f"RESULT {name} " + json.dumps(out["backends"][name]), flush=True)

    p = os.environ.get("PROBE_OUT", "")
    if p:
        json.dump(out, open(p, "w"))
    print("PROBE-DONE " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
