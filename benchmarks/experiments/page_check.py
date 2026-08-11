#!/usr/bin/env python3
"""Third gate: the published project page must agree with the paper.

`provenance_check` asks whether a cell traces to a run. `claims_check` asks
whether the paper's hand-typed prose constants match the data. This asks the
remaining question: does the page at humem.ai/projects/arcadedb show the same
numbers the paper does.

WHY THIS IS NOT CIRCULAR. The page is generated from `web_benchmarks.json` and
the paper's tables are generated from the same frozen rows, so it is tempting
to assume they cannot disagree. They can, in three ways this gate catches:

  1. The two generators aggregate independently. `export_web.py` takes a median
     across reps; `make_paper_tables.py` applies the canonical-row rule first.
     A change to either alone moves one artifact and not the other.
  2. They can read different FIELDS for the same concept. The time-series
     12-hour aggregation is `q_global_ms`; `q_range_ms` is a 60-row range
     query. Reading the second as the first produces 4.41 ms where the paper
     says 25.0, and both look like plausible aggregation numbers.
  3. The page can pull from a source the paper does not use at all. The
     time-series lane keeps ArcadeDB's native and document arms in separate
     files, and a page built from one file shows 40.1k pts/s where the paper
     shows 1.86M.

So this compares the page against the paper's CLAIMED constants, which are
hand-transcribed prose rather than generated, reusing the same expected values
and tolerances `claims_check` pins. If the page and the paper ever describe the
same measurement differently, one of them is wrong and this says so.

Usage:
    python page_check.py [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DEFAULT_JSON = HERE / "results" / "web_benchmarks.json"

# claim id -> (table id, backend as the page labels it, column label)
#
# Only claims whose measurement actually appears on the page are listed. A
# claim with no page cell is not a failure: the page is a summary and does not
# publish every number the paper argues from. What IS a failure is a page cell
# that disagrees with a claim covering the same measurement.
# Keyed by the RAW harness backend name, not the label the page prints. The
# page renames backends for readability, and on 2026-08-11 that rename turned
# all nine mapped cells ABSENT at once: no number was wrong, the gate simply
# could not find them. Resolving the raw key through the same display_name()
# the exporter uses means a future rename moves both sides together.
MAPPING = {
    # L1 tabular, OLTP throughput
    "l1.arcadedb.oltp":   ("l1", "arcadedb_embedded", "OLTP ops/s"),
    "l1.server.oltp":     ("l1", "arcadedb_server", "OLTP ops/s"),
    "l1.postgres.oltp":   ("l1", "postgres", "OLTP ops/s"),
    "l1.duckdb.oltp":     ("l1", "duckdb", "OLTP ops/s"),
    # L2 graph, 2-hop traversal
    "l2.arcadedb.hop2_p50": ("l2", "arcadedb_graph_embedded", "2-hop p50 ms"),
    "l2.neo4j.hop2_p50":    ("l2", "neo4j_graph", "2-hop p50 ms"),
    "l2.ladybug.hop2_p50":  ("l2", "ladybug_graph", "2-hop p50 ms"),
    # L4 time series: the lane where reading the wrong field is easiest
    "l4.native.ingest":   ("l4", "arcadedb (native TIMESERIES)", "ingest pts/s"),
    "l4.native.q_global": ("l4", "arcadedb (native TIMESERIES)", "12h aggregate ms"),
    "l4.questdb.ingest":  ("l4", "questdb", "ingest pts/s"),
    "l4.duckdb.ingest":   ("l4", "duckdb", "ingest pts/s"),
    "l4.doc.q_global":    ("l4", "arcadedb (document path)", "12h aggregate ms"),
    # Python binding suite. The ratio cells are the ones a wrong arm silently
    # changes, so they are the ones most worth pinning: swapping P-raw-call for
    # P-SQL republishes 1.71 in place of 1.28 with every other check green.
    "pyb.vector.ratio":   ("pycost", "Python", "vs Java"),
    "pyb.scan.ratio":     ("pycost", "Python, to_columns", "vs Java"),
    "pyb.tabular.arcadedb.oltp": ("pyb_tabular", "arcadedb", "OLTP ops/s"),
    "pyb.tabular.duckdb.olap":   ("pyb_tabular", "duckdb", "OLAP ms"),
    "pyb.graph.arcadedb.oltp":   ("pyb_graph", "arcadedb", "OLTP ops/s"),
    "pyb.vector.arcadedb.recall": ("pyb_vector", "arcadedb", "recall@10"),
}


def _page_index(payload):
    """(table, backend label, column) -> median, for every published cell."""
    out = {}
    for table in payload.get("tables", []):
        for entry in table.get("entries", []):
            for column, stat in entry.get("metrics", {}).items():
                out[(table["id"], entry["backend"], column)] = stat["median"]
    return out


def _resolve(key, cells):
    """Find the page cell for a mapping key, however the page spells it.

    MAPPING mixes two kinds of name: raw harness keys like
    `arcadedb_graph_embedded`, which the page renames, and labels the exporter
    composes itself like `arcadedb (native TIMESERIES)`, which it does not.
    Try the key as written first, then through display_name(). Doing only the
    second mangles the composed labels, since they also start with "arcadedb"
    and would collapse to a bare "ArcadeDB".
    """
    from export_web import display_name

    table, backend, column = key
    for candidate in (backend, display_name(backend)):
        if (table, candidate, column) in cells:
            return (table, candidate, column)
    return key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    args = ap.parse_args()

    path = Path(args.json)
    if not path.exists():
        print(f"missing {path}; run export_web.py first", file=sys.stderr)
        return 2

    payload = json.loads(path.read_text(encoding="utf-8"))
    cells = _page_index(payload)

    import claims_check as C  # noqa: E402  (needs BENCH_PAPER_DIR set)
    claims = {c[0]: (c[1], c[2], c[4]) for c in C.CLAIMS}

    print(f"page: {path}")
    print(f"  {len(payload['tables'])} tables, {len(cells)} published cells")
    print(f"  {len(MAPPING)} of them are also pinned prose constants\n")

    checked = bad = 0
    for cid, key in sorted(MAPPING.items()):
        if cid not in claims:
            print(f"  STALE  {cid:24s} no such claim; MAPPING is out of date")
            bad += 1
            continue
        claimed, tol, note = claims[cid]
        key = _resolve(key, cells)
        if key not in cells:
            # The page dropped a cell the paper argues from. Loud, because a
            # missing row is how a comparison quietly loses its context.
            print(f"  ABSENT {cid:24s} paper={claimed:<11} page has no {key}")
            bad += 1
            continue
        got = cells[key]
        ok = abs(got - claimed) <= tol
        checked += 1
        flag = "ok    " if ok else "DIFFER"
        print(f"  {flag} {cid:24s} paper={claimed:<11.6g} page={got:<13.6g} {note[:44]}")
        if not ok:
            bad += 1

    print(f"\n{checked} page cells checked against the paper, {bad} disagree")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
