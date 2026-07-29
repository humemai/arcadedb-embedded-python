#!/usr/bin/env python3
"""Is ArcadeDB's 2-hop latency tail explained by seed degree?

Task #100. From the campaign data, ArcadeDB is 3x FASTER than Neo4j and
LadybugDB at the 2-hop median (1.64 vs 4.95 vs 5.52 ms at SF10) but ~2x slower
at p99, and its p99/p50 dispersion is 12.2x where both comparators sit near 2x.
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

WHY THE FIRST RUN OF THIS PROBE PRODUCED GARBAGE (and what now prevents it).
`l2_graph` reads BENCH_GRAPH_SOURCE at import time and rebinds gen_persons /
gen_edges to the LDBC streams only inside its own main(). Importing the module
and calling build() directly -- which is what this probe does -- therefore built
a SYNTHETIC graph with dense ids 0..n while the seeds came from
ldbc_snb.pick_query_ids, whose ids are sparse longs. Every seed addressed a
person that did not exist, so every degree was 0 and the reported Spearman of
0.383 was a correlation over a column of zeros. The old guard only checked that
the vertex COUNT was plausible, which that build satisfied.

The guard below therefore asserts the thing that was actually broken: edges
reachable FROM THE SEEDS. A graph can be fully built and still be useless here
if the seeds do not address it.

Env: BENCH_GRAPH_SCALE (sf1|sf10), BENCH_GRAPH_DATA, PROBE_OUT, PROBE_BACKENDS.
Neo4j additionally needs BENCH_SERVER_HOST (and runs from icde-bench:client).
"""
import json
import os
import statistics
import time

# Must be set BEFORE l2_graph is imported: it reads the switch at module level.
os.environ.setdefault("BENCH_GRAPH_SOURCE", "ldbc")
os.environ.setdefault("BENCH_GRAPH_DATA", "/data/ldbc")

SCALE = os.environ.get("BENCH_GRAPH_SCALE", "sf10")
N_SEEDS = int(os.environ.get("PROBE_SEEDS", "400"))
BACKENDS = os.environ.get("PROBE_BACKENDS", "arcadedb_graph_embedded").split(",")

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
    import l2_graph
    import ldbc_snb as _ldbc

    if l2_graph._GRAPH_SOURCE != "ldbc":
        raise SystemExit(f"ABORT: l2_graph source is {l2_graph._GRAPH_SOURCE!r}, "
                         "expected 'ldbc'; env was set too late")

    # Replicate what l2_graph.main() does for the LDBC source. The adapters
    # resolve these names from module globals at call time, so rebinding the
    # module attributes is what makes build() stream real LDBC data. Without
    # this the build is synthetic and the LDBC seeds address nothing.
    l2_graph.gen_persons = lambda _n: _ldbc.gen_persons(SCALE)
    l2_graph.gen_edges = lambda _n: _ldbc.gen_edges(SCALE)

    seeds = _ldbc.pick_query_ids(SCALE, N_SEEDS)
    n_persons = _ldbc.SCALE_PERSONS[SCALE]
    out = {"scale": SCALE, "n_seeds": N_SEEDS, "n_persons": n_persons,
           "graph_source": l2_graph._GRAPH_SOURCE, "backends": {}}

    for name in BACKENDS:
        b = l2_graph.ADAPTERS[name]()
        b.connect()
        # connect() creates an EMPTY database, so the graph is built here.
        t0 = time.perf_counter()
        b.build(n_persons)
        b.post_build("oltp")
        build_s = time.perf_counter() - t0
        print(f"BUILT {name} {n_persons} persons in {build_s:.1f}s", flush=True)

        # ---- guard: the graph must be present AND reachable from the seeds ---
        total = b.run_cypher("MATCH (p:Person) RETURN p")
        if total < n_persons // 2:
            raise SystemExit(f"ABORT {name}: only {total} persons after build")
        # Existence check only, deliberately bounded: run_cypher returns a ROW
        # COUNT, so `RETURN count(r)` would answer 1 regardless of the graph
        # (that mistake is already in this probe's history). Returning the rows
        # themselves is the only way to count through this API, and at SF10
        # that is ~2.5M rows materialised to prove a boolean. LIMIT makes it
        # cheap; the number below is a floor, not the edge count.
        knows_sample = b.run_cypher("MATCH ()-[r:KNOWS]->() RETURN r LIMIT 1000")
        if knows_sample == 0:
            raise SystemExit(f"ABORT {name}: graph has {total} persons but 0 KNOWS edges")
        # The failure that got through last time: seeds from a different id
        # space than the built graph. Vertex and edge counts were both fine;
        # every seed still resolved to nothing. Sample the seeds themselves.
        sample = seeds[:min(25, len(seeds))]
        sample_deg = [b.run_cypher(DEG1_ROWS.format(id=s)) for s in sample]
        med_deg = statistics.median(sample_deg)
        if med_deg <= 0:
            raise SystemExit(
                f"ABORT {name}: {total} persons and {knows} KNOWS edges, but the "
                f"median 1-hop degree over {len(sample)} seeds is {med_deg}. The "
                "seeds do not address this graph (id-space mismatch); a "
                "correlation here would be computed over zeros.")
        print(f"GUARD OK {name}: persons={total} knows>={knows_sample} "
              f"median_deg1_over_{len(sample)}_seeds={med_deg}", flush=True)

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
        # A second line of defence on the measured set, not just the sample:
        # if the full seed set is degenerate the statistics are meaningless.
        if statistics.median(d2) <= 0:
            raise SystemExit(f"ABORT {name}: median deg2 over {len(rows)} seeds is 0")
        srt = sorted(ms)
        p50 = statistics.median(srt)
        p99 = srt[min(len(srt) - 1, int(0.99 * len(srt)))]
        pairs = sorted(zip(d2, ms))
        dec = []
        for i in range(10):
            lo, hi = i * len(pairs) // 10, (i + 1) * len(pairs) // 10
            chunk = [m for _, m in pairs[lo:hi]]
            dec.append(round(statistics.median(chunk), 3) if chunk else None)
        out["backends"][name] = {
            "build_s": round(build_s, 1),
            # n_persons is the SCALE_PERSONS constant (10,995 for sf1); `total`
            # is what the graph actually holds (9,892). The constant is a little
            # high for the real LDBC stream, so record both rather than either.
            "persons": total, "persons_expected": n_persons,
            "knows_edges_at_least": knows_sample,
            "p50_ms": round(p50, 3), "p99_ms": round(p99, 3),
            "dispersion_p99_over_p50": round(p99 / p50, 2) if p50 else None,
            "spearman_ms_vs_deg2": round(spearman(d2, ms), 3),
            "spearman_ms_vs_deg1": round(spearman(d1s, ms), 3),
            "decile_median_ms_by_deg2": dec,
            "deg2_median": statistics.median(d2),
            "deg2_p10": pairs[len(pairs) // 10][0],
            "deg2_p90": pairs[9 * len(pairs) // 10][0],
            "deg2_max": max(d2),
        }
        print(f"RESULT {name} " + json.dumps(out["backends"][name]), flush=True)

    p = os.environ.get("PROBE_OUT", "")
    if p:
        with open(p, "w") as fh:
            json.dump(out, fh, indent=1)
    print("PROBE-DONE " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
