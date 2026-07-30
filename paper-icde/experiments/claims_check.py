#!/usr/bin/env python3
"""Check every numeric claim in the paper's prose against the data behind it.

The plan's own verification criterion is "every number in prose traces to a
results file". Running that by hand on 2026-07-30 found two real defects, and
also produced THREE false findings, all from the same cause: a hand-rolled
median over `runs.jsonl` is not what the tables do. The generator applies
`load_canonical()` (rc=0, scale in PAPER_SCALES, and dedupe on payload fields
keeping the latest `ts_utc` per rep), which collapses re-run campaigns and
pilot runs to one row per rep. Pooling everything instead pulled two single-rep
E2 pilots into an N=5 measurement, and a correct number in the paper got
replaced with an incorrect one before the mistake was caught.

So this file does not recompute anything its own way. It imports the generator
and asks it, which is the only version of this check that cannot drift from
what the tables actually print.

Each CLAIM below pins one prose number to the selector that produces it. That
mapping is the part a machine cannot infer, so it is written down once here and
re-checked forever after. At the October freeze, running this says exactly
which prose numbers moved and which did not.

    python3 claims_check.py           # check all
    python3 claims_check.py --lane l2 # one lane

Exit status is 1 if any claim disagrees with the data.
"""
import argparse
import statistics as st
import sys

import make_paper_tables as M


def _sel(rows, lane=None, scale=None, backend=None, workload=None):
    out = []
    for r in rows:
        if lane is not None and r.get("lane") != lane:
            continue
        if scale is not None and r.get("scale") != scale:
            continue
        if backend is not None and r.get("backend") != backend:
            continue
        if workload is not None and r.get("workload") != workload:
            continue
        out.append(r)
    return out


def median_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return st.median(g) if g else None


def max_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return max(g) if g else None


def min_of(rows, field, **kw):
    g = [r[field] for r in _sel(rows, **kw) if isinstance(r.get(field), (int, float))]
    return min(g) if g else None


def gib(rows, field, **kw):
    """MiB field -> GiB. The prose divided by 1000 here and called it GiB,
    which inflated every memory number ~2.4%; the figure pipeline had it right
    all along, so prose and figure disagreed."""
    v = median_of(rows, field, **kw)
    return None if v is None else v / 1024


# (id, prose value, tolerance, how to compute it, note)
# Tolerance is what the prose's own rounding allows, not a fudge factor: a
# claim printed as "525 ops/s" is satisfied by anything rounding to 525.
CLAIMS = [
    # --- L1 tabular -------------------------------------------------------
    ("l1.arcadedb.oltp", 5929, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "OLTP ops/s embedded"),
    ("l1.server.oltp", 1288, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_server"),
     "OLTP ops/s server (deployment axis)"),
    ("l1.postgres.oltp", 525, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="postgres"), "PostgreSQL ops/s"),
    ("l1.duckdb.oltp", 268, 1,
     lambda r: median_of(r, "oltp_ops_per_s", lane="l1", scale="medium",
                         workload="oltp", backend="duckdb"), "DuckDB ops/s"),
    ("l1.arcadedb.insert_p99", 0.54, 0.01,
     lambda r: median_of(r, "insert_p99_ms", lane="l1", scale="medium",
                         workload="oltp", backend="arcadedb_embedded"),
     "insert p99 ms"),

    # --- L2 graph ---------------------------------------------------------
    ("l2.arcadedb.hop2_p50", 1.57, 0.01,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="arcadedb_graph_embedded"),
     "2-hop median SF10"),
    ("l2.neo4j.hop2_p50", 4.72, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="neo4j_graph"), "Neo4j 2-hop"),
    ("l2.ladybug.hop2_p50", 5.59, 0.02,
     lambda r: median_of(r, "hop2_p50_ms", lane="l2", scale="sf10",
                         workload="oltp", backend="ladybug_graph"), "LadybugDB 2-hop"),
    ("l2.arcadedb.olap_friendage", 519, 1,
     lambda r: median_of(r, "friend_age_by_city_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP friend-age (WITH GAV)"),
    ("l2.arcadedb.olap_topdeg", 58, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="arcadedb_graph_embedded"),
     "OLAP top-degree (WITH GAV)"),
    ("l2.neo4j.olap_topdeg", 305, 1,
     lambda r: median_of(r, "top_degree_mean_ms", lane="l2", scale="sf10",
                         workload="olap", backend="neo4j_graph"), "Neo4j top-degree"),
    # The unit defect this file exists to stop recurring.
    ("l2.arcadedb.mem_gib", 9.4, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="arcadedb_graph_embedded"),
     "SF10 OLTP peak anon GiB (MiB/1024, NOT /1000)"),
    ("l2.neo4j.mem_gib", 12.9, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l2", scale="sf10",
                   workload="oltp", backend="neo4j_graph"), "Neo4j peak anon GiB"),

    # --- E2 hybrid --------------------------------------------------------
    # These are the ones a hand-rolled median got wrong. load_canonical drops
    # the two single-rep pilots, so the N=5 measurement stands alone.
    ("e2.arcadedb.p50", 3.36, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="arcadedb_e2"), "hybrid p50"),
    ("e2.arcadedb.max", 3.49, 0.01,
     lambda r: max_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range max"),
    ("e2.arcadedb.min", 3.20, 0.01,
     lambda r: min_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                      backend="arcadedb_e2"), "hybrid range min"),
    ("e2.surrealdb.p50", 7.02, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="surrealdb_e2"), "SurrealDB hybrid"),
    ("e2.composed.p50", 22.35, 0.01,
     lambda r: median_of(r, "hybrid_p50_ms", lane="e2", workload="hybrid",
                         backend="composed_qdrant_neo4j"), "composed stack hybrid"),

    # --- L3d dense memory -------------------------------------------------
    # ArcadeDB ran this lane at two pinned heaps and the comparators at one, so
    # the backend alone does not identify an operating point. The figure used to
    # median across both and landed on neither.
    ("l3d.qdrant.mem_gib", 5.97, 0.05,
     lambda r: gib(r, "peak_anon_mib_sum", lane="l3d", scale="deep10m",
                   backend="qdrant_dense"), "Qdrant dense peak anon GiB"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", help="only claims whose id starts with this")
    args = ap.parse_args()

    rows = M.load_canonical()
    print(f"canonical rows: {len(rows)}  "
          f"(rc=0, PAPER_SCALES, latest ts_utc per lane/scale/workload/backend/rep)\n")

    bad = 0
    checked = 0
    for cid, claimed, tol, fn, note in CLAIMS:
        if args.lane and not cid.startswith(args.lane):
            continue
        checked += 1
        try:
            got = fn(rows)
        except Exception as e:
            print(f"  ERROR  {cid:26s} {e.__class__.__name__}: {e}")
            bad += 1
            continue
        if got is None:
            print(f"  NODATA {cid:26s} claim={claimed}  ({note})")
            bad += 1
            continue
        ok = abs(got - claimed) <= tol
        flag = "ok    " if ok else "MISMATCH"
        print(f"  {flag} {cid:26s} paper={claimed:<9} data={got:<11.4g} {note}")
        if not ok:
            bad += 1

    print(f"\n{checked} claims checked, {bad} disagree")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
