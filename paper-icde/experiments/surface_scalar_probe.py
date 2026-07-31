#!/usr/bin/env python3
"""A clean Cypher-vs-SQL latency number, immune to #5613.

queue49 measured Cypher at 1.69-1.81x SQL MATCH on a whole-vertex projection.
The payload probe then showed that comparison is not like-for-like: every
Cypher row carries the matched type's declared properties as extra null
columns (#5613), so Cypher ships 1.61x the bytes for the same vertices, and
the payload ratio sits right against the latency ratio.

#5613 does NOT affect scalar projections: `RETURN f.name` comes back clean on
both surfaces. So a scalar A/B gives the surface-vs-surface number the
whole-vertex one cannot, today, without waiting for a fix.

Reports both projections side by side so the difference between them IS the
measurement: if scalar converges and whole-vertex does not, the gap is #5613
rather than the traversal.

Setup copied verbatim from profile_surface_driver.py; see surface_payload_probe
for why re-deriving it is a bad idea.
"""
import json, os, statistics as st, sys, time

SCALE = os.environ.get("BENCH_GRAPH_SCALE", "sf1")
N_SEEDS = int(os.environ.get("N_SEEDS", "20"))
REPS = int(os.environ.get("REPS", "60"))
WARMUP = 5

SQL = {
 "hop1_whole": "MATCH {{type: Person, as: p, where: (id = {id})}}.out('KNOWS'){{as: f}} RETURN DISTINCT f",
 "hop1_scalar": "MATCH {{type: Person, as: p, where: (id = {id})}}.out('KNOWS'){{as: f}} RETURN DISTINCT f.name",
 "hop2_whole": "MATCH {{type: Person, as: p, where: (id = {id})}}.out('KNOWS'){{as: m}}.out('KNOWS'){{as: fof}} RETURN DISTINCT fof",
 "hop2_scalar": "MATCH {{type: Person, as: p, where: (id = {id})}}.out('KNOWS'){{as: m}}.out('KNOWS'){{as: fof}} RETURN DISTINCT fof.name",
}
CY = {
 "hop1_whole": "MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} RETURN DISTINCT f",
 "hop1_scalar": "MATCH (p:Person)-[:KNOWS]->(f:Person) WHERE p.id = {id} RETURN DISTINCT f.name",
 "hop2_whole": "MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) WHERE p.id = {id} RETURN DISTINCT fof",
 "hop2_scalar": "MATCH (p:Person)-[:KNOWS]->(:Person)-[:KNOWS]->(fof:Person) WHERE p.id = {id} RETURN DISTINCT fof.name",
}

def pct(v, q):
    v = sorted(v)
    return v[min(int(q * len(v)), len(v) - 1)] if v else float("nan")

def main():
    os.environ.setdefault("BENCH_GRAPH_SOURCE", "ldbc")
    import l2_graph, ldbc_snb as _ldbc
    l2_graph.gen_persons = lambda _n: _ldbc.gen_persons(SCALE)
    l2_graph.gen_edges = lambda _n: _ldbc.gen_edges(SCALE)
    l2_graph.pick_query_ids = lambda _n, k: _ldbc.pick_query_ids(SCALE, k)
    be = l2_graph.ADAPTERS["arcadedb_graph_embedded"]()
    be.connect(); be.build(l2_graph.SCALE_PERSONS[SCALE]); be.post_build("oltp")
    seeds = list(_ldbc.pick_query_ids(SCALE, N_SEEDS))
    print(f"engine {be.version}  scale {SCALE}  seeds {len(seeds)}  reps {REPS}\n", flush=True)

    res = {}
    for q in ("hop1_whole", "hop1_scalar", "hop2_whole", "hop2_scalar"):
        order = [("opencypher", CY[q], "cypher"), ("sql", SQL[q], "sql")]
        if os.environ.get("SQL_FIRST"):
            order.reverse()
        for lang, tmpl, tag in order:
            lat, nrows, nbytes = [], 0, 0
            for i in range(REPS):
                sid = seeds[i % len(seeds)]
                t = time.perf_counter()
                rows = be.db.query(lang, tmpl.format(id=sid)).to_json_list()
                dt = (time.perf_counter() - t) * 1000
                if i >= WARMUP:
                    lat.append(dt); nrows += len(rows); nbytes += len(json.dumps(rows))
            res[(q, tag)] = (st.median(lat), pct(lat, 0.95), nrows, nbytes)
            print(f"  {q:12} {tag:7} p50={st.median(lat):7.2f}ms p95={pct(lat,0.95):7.2f}ms "
                  f"rows={nrows:6} bytes={nbytes:8}", flush=True)

    print("\n=== surface ratio, by projection ===")
    for base in ("hop1", "hop2"):
        for kind in ("whole", "scalar"):
            c = res[(f"{base}_{kind}", "cypher")]; s = res[(f"{base}_{kind}", "sql")]
            lr = c[0] / s[0] if s[0] else float("nan")
            br = c[3] / s[3] if s[3] else float("nan")
            same = "same" if c[2] == s[2] else f"ROWS DIFFER {c[2]} vs {s[2]}"
            print(f"  {base:5} {kind:7} latency {lr:5.2f}x   payload {br:5.2f}x   rows {same}")
    print("\nIf scalar converges toward 1.0x while whole-vertex does not, the")
    print("whole-vertex gap is #5613's null columns and not the traversal.")
    sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
