#!/usr/bin/env python3
"""Why does the Graph Analytical View help some OLAP queries 2.7x more?

The queue33 ablation split cleanly and nobody chased why:

    top_degree          381.0 -> 57.2 ms    6.66x   far endpoint never touched
    same_city_edges    1271.6 -> 517.1 ms   2.46x   reads b.city
    friend_age_by_city 1257.2 -> 520.6 ms   2.41x   reads f.age

The two that dereference a property on the FAR endpoint of the edge keep most
of their cost and land within 0.7% of each other. The one that never touches
the far endpoint gets 2.7x more benefit.

SOURCE-LEVEL MECHANISM (read on 26.8.1.dev24, engine/src/main/java):

  GAVExpandAll emits the target as a GAVVertex, a lazy proxy. Asking it for a
  property runs GAVVertex.get(String) -> GraphAnalyticalView.getProperty(int,
  String) -> ColumnStore.getValue(int, String), whose first act is

      final Column column = columns.get(propertyName);   // HashMap<String,Column>

  a string-keyed hash lookup, followed by a boxing allocation on the return.
  Per row. Per property. The source vertex costs none of this: it comes from
  the NodeByLabelScan below the expansion as a real record, already materialised
  once per vertex rather than once per edge.

  Meanwhile GraphAnalyticalView.getBucketColumnStore(int) exists and its javadoc
  says "Returns the per-bucket column store for direct vectorized access". It
  has ZERO callers outside its own definition. The vectorized path is built and
  nothing in the query layer uses it.

That predicts a specific, falsifiable pattern, which is what this probe tests.

THE DISCRIMINATORS. src_prop_only is same_city_edges with the far-endpoint
predicate removed: it reads a property, but only on the source. dst_prop_only
is its mirror: the same single property read, on the target instead. Their
comparison isolates DIRECTION from PROPERTY COUNT, which the three published
queries confound.

  src fast AND dst slow      -> far-endpoint access is the cost. File it.
  src and dst both slow      -> any property access defeats the view; different
                                story, still filable, different fix.
  src and dst both fast      -> the mechanism above is not what costs, and the
                                2.7x split has another cause. Do not file.

PROTOCOL. Both arms are built FIRST, then the queries are interleaved
round-robin across arms at each repetition. Building arm A, measuring it, then
building arm B lets the second arm inherit a warmed JVM; that bias was worth
30pp in the E4 probe and was caught only because a fine sweep disagreed with a
coarse one by 2.5x. Warmup runs every query on every arm before timing starts.

NOT A PUBLISHED CELL. This is a bespoke diagnostic driver, so by the rule in
FAIRNESS.md ("bespoke drivers investigate, lane scripts publish") its numbers
belong in an upstream issue and in the notes, never in a paper table. The two
discriminator queries are deliberately NOT added to graph_common.OLAP_QUERIES:
that suite's median is a published cell and adding queries would silently move
it.
"""
import argparse
import json
import os
import shutil
import statistics as st
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bench_common
import graph_common
from arcadedb_embedded import DatabaseFactory

GAV_NAME = "gavprobe"
GAV_TIMEOUT_S = 3600

# The three published queries verbatim from graph_common, plus the two
# discriminators. Imported rather than retyped so a change to the suite cannot
# silently desynchronise this probe from the cells it is explaining.
QUERIES = dict(graph_common.OLAP_QUERIES)
QUERIES["src_prop_only"] = (
    "MATCH (p:Person)-[:KNOWS]->(:Person) "
    "RETURN p.city AS c, count(*) AS n ORDER BY n DESC LIMIT 10")
QUERIES["dst_prop_only"] = (
    "MATCH (p:Person)-[:KNOWS]->(f:Person) "
    "RETURN f.city AS c, count(*) AS n ORDER BY n DESC LIMIT 10")

# Which queries dereference a property on the far endpoint of the edge. This is
# the hypothesis written down before the numbers land, so the reading afterwards
# cannot drift to fit whatever comes out.
TOUCHES_FAR_ENDPOINT = {
    "top_degree": False,
    "same_city_edges": True,
    "friend_age_by_city": True,
    "src_prop_only": False,
    "dst_prop_only": True,
}


def build_graph(db, n_persons):
    db.command("sql", "CREATE VERTEX TYPE Person")
    for p, t in (("id", "LONG"), ("name", "STRING"),
                 ("age", "INTEGER"), ("city", "STRING")):
        db.command("sql", f"CREATE PROPERTY Person.{p} {t}")
    db.command("sql", "CREATE EDGE TYPE KNOWS")
    db.command("sql", "CREATE PROPERTY KNOWS.since INTEGER")
    db.command("sql", "CREATE INDEX ON Person (id) UNIQUE")

    t0 = time.time()
    with db.transaction():
        for i, (pid, name, age, city) in enumerate(
                graph_common.gen_persons(n_persons)):
            db.command(
                "sql",
                f"CREATE VERTEX Person SET id={pid}, name='{name}', "
                f"age={age}, city='{city}'")
    n_edges = 0
    with db.transaction():
        for src, dst, since in graph_common.gen_edges(n_persons):
            db.command(
                "sql",
                f"CREATE EDGE KNOWS FROM (SELECT FROM Person WHERE id={src}) "
                f"TO (SELECT FROM Person WHERE id={dst}) SET since={since}")
            n_edges += 1
    return time.time() - t0, n_edges


def make_view(db):
    """Identical DDL to l2_graph.py, PROPERTIES list included."""
    t0 = time.time()
    db.command(
        "sql",
        f"CREATE GRAPH ANALYTICAL VIEW {GAV_NAME} "
        "VERTEX TYPES (Person) EDGE TYPES (KNOWS) "
        "PROPERTIES (id, name, age, city) EDGE PROPERTIES (since) "
        "UPDATE MODE OFF")
    while time.time() - t0 < GAV_TIMEOUT_S:
        rows = db.query(
            "sql", "SELECT FROM schema:graphAnalyticalViews WHERE name = ?",
            GAV_NAME).to_json_list()
        status = rows[0].get("status") if rows else None
        if status == "READY":
            return time.time() - t0, rows[0]
        if status in ("FAILED", "ERROR"):
            raise RuntimeError(f"GAV build failed: {rows[0]}")
        time.sleep(0.5)
    raise RuntimeError("GAV not READY within timeout")


def run(db, cypher):
    return db.query("opencypher", cypher).to_json_list()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default=os.environ.get("PROBE_SCALE", "tiny"),
                    choices=sorted(graph_common.SCALE_PERSONS))
    ap.add_argument("--reps", type=int,
                    default=int(os.environ.get("PROBE_REPS", "5")))
    ap.add_argument("--warmup", type=int,
                    default=int(os.environ.get("PROBE_WARMUP", "2")))
    ap.add_argument("--out", default=os.environ.get("PROBE_OUT"))
    args = ap.parse_args()

    n_persons = graph_common.SCALE_PERSONS[args.scale]
    root = tempfile.mkdtemp(prefix="gavprobe_")
    print(f"scale={args.scale} persons={n_persons:,} reps={args.reps} "
          f"warmup={args.warmup}", flush=True)

    # PROBE_PROFILE=<query> builds ONLY the GAV-ON arm and loops that one query
    # so a profiler can be attached to it. The A/B is pointless under a
    # profiler (both arms would be equally perturbed and the ratio is what the
    # A/B is for); what the profile answers is the separate question of WHERE
    # the surviving time goes inside the accelerated arm.
    prof_query = os.environ.get("PROBE_PROFILE")
    if prof_query:
        if prof_query not in QUERIES:
            raise SystemExit(f"PROBE_PROFILE={prof_query!r} is not one of "
                             f"{sorted(QUERIES)}")
        try:
            with DatabaseFactory(os.path.join(root, "on")).create() as db:
                el, n_edges = build_graph(db, n_persons)
                print(f"  built {n_persons:,} vertices, {n_edges:,} edges "
                      f"in {el:.1f}s", flush=True)
                view_s, view_info = make_view(db)
                print(f"  view READY in {view_s:.2f}s", flush=True)
                q = QUERIES[prof_query]
                for _ in range(args.warmup):
                    run(db, q)
                # The marker the watcher waits on. Printed only once the build
                # and the view are done, so the profiler attaches to the query
                # phase and not to a build it was never meant to measure.
                print(f"PROFILE-PHASE-START {prof_query}", flush=True)
                t0 = time.perf_counter()
                for i in range(args.reps):
                    run(db, q)
                    if (i + 1) % 20 == 0:
                        print(f"  {i + 1}/{args.reps} "
                              f"({time.perf_counter() - t0:.0f}s)", flush=True)
                print("PROFILE-PHASE-DONE", flush=True)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        return 0

    try:
        # ---- build BOTH arms before timing anything -------------------------
        f_off = DatabaseFactory(os.path.join(root, "off"))
        f_on = DatabaseFactory(os.path.join(root, "on"))
        with f_off.create() as db_off, f_on.create() as db_on:
            arms = {}
            for label, db in (("gav_off", db_off), ("gav_on", db_on)):
                el, n_edges = build_graph(db, n_persons)
                print(f"  {label}: built {n_persons:,} vertices, "
                      f"{n_edges:,} edges in {el:.1f}s", flush=True)
                arms[label] = db
            view_s, view_info = make_view(db_on)
            print(f"  gav_on: view READY in {view_s:.2f}s "
                  f"({view_info.get('nodeCount')} nodes, "
                  f"{view_info.get('edgeCount')} edges, "
                  f"{view_info.get('memoryUsageBytes', 0) / 1e6:.1f} MB)",
                  flush=True)

            # ---- agreement check: the arms must answer identically ----------
            # Two databases built from the same deterministic generator should
            # return the same rows. If they do not, the arms are not comparable
            # and no speedup computed from them means anything.
            disagreements = []
            for name, q in QUERIES.items():
                a = run(arms["gav_off"], q)
                b = run(arms["gav_on"], q)
                if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
                    disagreements.append(name)
            if disagreements:
                raise SystemExit(
                    f"ARM DISAGREEMENT on {disagreements}: the two arms return "
                    "different results, so no comparison is valid. Refusing to "
                    "report timings.")
            print("  arms agree on all queries", flush=True)

            # ---- warm every query on every arm, then interleave -------------
            for _ in range(args.warmup):
                for q in QUERIES.values():
                    for db in arms.values():
                        run(db, q)

            lat = {a: {k: [] for k in QUERIES} for a in arms}
            for _ in range(args.reps):
                for name, q in QUERIES.items():
                    for label, db in arms.items():   # round-robin the arms
                        t0 = time.perf_counter()
                        run(db, q)
                        lat[label][name].append(
                            (time.perf_counter() - t0) * 1000.0)

        # ---- report ---------------------------------------------------------
        print("\n=== GAV speedup by query (median ms) ===", flush=True)
        print(f"  {'query':<20}{'far_prop':>9}{'gav_off':>10}{'gav_on':>10}"
              f"{'speedup':>9}", flush=True)
        out_rows = {}
        for name in QUERIES:
            off = st.median(lat["gav_off"][name])
            on = st.median(lat["gav_on"][name])
            sp = off / on if on else 0.0
            out_rows[name] = {
                "gav_off_median_ms": round(off, 3),
                "gav_on_median_ms": round(on, 3),
                "speedup": round(sp, 3),
                "touches_far_endpoint": TOUCHES_FAR_ENDPOINT[name],
                "gav_off_all_ms": [round(x, 3) for x in lat["gav_off"][name]],
                "gav_on_all_ms": [round(x, 3) for x in lat["gav_on"][name]],
            }
            print(f"  {name:<20}{str(TOUCHES_FAR_ENDPOINT[name]):>9}"
                  f"{off:>10.2f}{on:>10.2f}{sp:>9.2f}x", flush=True)

        near = [n for n in QUERIES if not TOUCHES_FAR_ENDPOINT[n]]
        far = [n for n in QUERIES if TOUCHES_FAR_ENDPOINT[n]]
        near_sp = st.median([out_rows[n]["speedup"] for n in near])
        far_sp = st.median([out_rows[n]["speedup"] for n in far])
        print(f"\n  median speedup, far endpoint UNTOUCHED: {near_sp:.2f}x  "
              f"({', '.join(near)})", flush=True)
        print(f"  median speedup, far endpoint READ:      {far_sp:.2f}x  "
              f"({', '.join(far)})", flush=True)

        # The decisive pair: same query shape, same single property, source vs
        # target. Everything else differs between the published three.
        s = out_rows["src_prop_only"]["speedup"]
        d = out_rows["dst_prop_only"]["speedup"]
        print(f"\n  DISCRIMINATOR  src_prop_only {s:.2f}x  vs  "
              f"dst_prop_only {d:.2f}x   ratio {s / d if d else 0:.2f}", flush=True)
        if s >= 1.5 * d:
            verdict = ("CONFIRMED: reading the property from the TARGET rather "
                       "than the source costs most of the view's benefit, with "
                       "query shape and property count held equal.")
        elif d >= 0.8 * s:
            verdict = ("NOT CONFIRMED: direction does not matter. The 2.7x "
                       "split in the published three has another cause; do not "
                       "file the per-row column-lookup theory on this evidence.")
        else:
            verdict = ("PARTIAL: direction matters but less than the published "
                       "split implies. Profile before filing.")
        print(f"\n  {verdict}", flush=True)

        result = {
            "queries": out_rows,
            "near_median_speedup": round(near_sp, 3),
            "far_median_speedup": round(far_sp, 3),
            "verdict": verdict,
            "scale": args.scale,
            "n_persons": n_persons,
            "reps": args.reps,
            "warmup": args.warmup,
            "view": view_info,
            "view_build_s": round(view_s, 3),
        }
        result.update(bench_common.run_conditions(
            lane="gav_probe", scale=args.scale, role="engine"))
        if args.out:
            with open(args.out, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\n  wrote {args.out}", flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
