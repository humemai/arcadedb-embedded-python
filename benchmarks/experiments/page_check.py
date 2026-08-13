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
import re
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
    # The four pyb_tabular/pyb_graph/pyb_vector cells that used to sit here
    # went with their tables on 2026-08-13; export_web._embedded_vs_tables
    # carries the reasoning. Removed rather than left to report ABSENT: this
    # gate's whole contract is that an absent pin means something broke, so a
    # pin kept alive for a table the page deliberately dropped would train a
    # reader to ignore the one signal it exists to send. Restoring the tables
    # means restoring these four.
}


# --- the page's PROSE, pinned to the paper's own tables -------------------
#
# MAPPING above covers TABLE CELLS, which the exporter writes straight from
# the frozen results, so a wrong one is nearly impossible. Prose is the
# opposite: every number in a caption or a body paragraph was typed in by
# hand, and until 2026-08-13 nothing checked a single one of them.
#
# What that cost: the f4 caption read "0.96 ms against Qdrant's 1.30 ... against
# Qdrant's 98.0%". Both comparator numbers were the canonical `runs_paper.csv`
# rows, while ArcadeDB's 0.96 came from the matched `dense_mp5_2681` overlay
# that T5 and the figure both read. The paper's own table says 1.31 and 97.8%.
# Nothing was fabricated and no published cell was wrong; two sources were
# mixed inside one sentence, which is the exact failure _check_f4_against_tables
# was written for after it happened three times between figures and tables.
# Prose was simply the one surface with no equivalent.
#
# Pinned to the TABLE rather than to the data, deliberately, for the reason
# claims_check.cell() gives: prose -> table -> data chains through a step that
# already regenerates byte-identical from the results, so this adds a check
# without adding a second selection to drift. It also enforces the rule
# PUBLISHING.md states, that the page shows what the papers show: a number the
# page prints and the paper does not now fails here rather than going unread.
#
# ADD AN ENTRY whenever prose gains a number. The regex must capture exactly
# the digits as printed, so rounding is compared at the precision published.
# T5's dense columns, 0-based after the row label:
#   0 Build(s)  1 Cold p50  2 Warm p50  3 Cold p99  4 Recall
# COLD AND WARM ARE DIFFERENT QUANTITIES and the pin must name which. The f4
# caption quoted warm for ArcadeDB beside a comparator measured on its first
# pass, which is the same mismatch the figure itself had; every entry below
# therefore carries the column, and cold entries and warm entries are listed
# apart so a future edit cannot slide one into the other unnoticed.
PROSE = [
    # First pass, the operating point f4 plots. All three from column 1.
    ("dense.arcadedb.cold", r"that is (\d+(?:\.\d+)?) ?ms for ArcadeDB",
     ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 1)),
    ("dense.qdrant.cold", r"against Qdrant's (\d+(?:\.\d+)?) and Chroma's",
     ("t5_dense_ts.tex", "Qdrant", 1)),
    ("dense.chroma.cold", r"and Chroma's (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Chroma", 1)),
    # Steady state, quoted to show the gap is ours alone. Column 2.
    ("dense.arcadedb.warm", r"ArcadeDB answers in (\d+(?:\.\d+)?) ?ms",
     ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 2)),
    ("dense.qdrant.warm", r"Qdrant moves to (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Qdrant", 2)),
    ("dense.chroma.warm", r"and Chroma to (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Chroma", 2)),
]

# repos are siblings, same assumption refresh_web_page.py makes
PAGE_TS = Path(__file__).resolve().parents[2].parent / "humem.ai" / \
    "src" / "lib" / "projects" / "items" / "arcadedb.ts"


# The page's DEEP-10M rows against T5's, cell for cell.
#
# Both sides read results/dense_mp5_2681, but through two separate
# implementations: export_web._dense_10m_entries for the page and
# make_paper_tables for the paper. That is the "two generators aggregate
# independently" hazard this file's docstring opens with, now applied to the
# tier that was withheld until 2026-08-13 and so never had a pin at all.
#
# page label -> (T5 row label, cold col, warm col, recall col)
DENSE_10M = {
    "ArcadeDB (embedded, fp32)": ("ArcadeDB (emb, fp32)", 1, 2, 4),
    "ArcadeDB (embedded, int8)": ("ArcadeDB (emb, int8)", 1, 2, 4),
    "ArcadeDB (server)":         ("ArcadeDB (srv)", 1, 2, 4),
    "Qdrant":                    ("Qdrant", 1, 2, 4),
    "Chroma":                    ("Chroma", 1, 2, 4),
    "DuckDB VSS":                ("DuckDB-VSS", 1, 2, 4),
    "LanceDB":                   ("LanceDB", 1, 2, 4),
    "Milvus":                    ("Milvus", 1, 2, 4),
}


def _check_dense_10m(payload):
    """Page's 10M cells vs the paper's, at the precision the paper prints."""
    import claims_check as C

    rows = {}
    for table in payload.get("tables", []):
        if table["id"] != "l3d":
            continue
        for e in table["entries"]:
            if e.get("scale") == "deep10m":
                rows[e["backend"]] = e["metrics"]
    if not rows:
        print("  no deep10m rows on the page; the tier is withheld again")
        return 0, 1
    checked = bad = 0
    for label, (trow, ccol, wcol, rcol) in sorted(DENSE_10M.items()):
        m = rows.get(label)
        if m is None:
            print(f"  ABSENT {label:28s} no such page row")
            bad += 1
            continue
        for name, col, key in (("cold", ccol, "cold p50 ms"),
                               ("warm", wcol, "warm p50 ms"),
                               ("recall", rcol, "recall@10")):
            want = C.cell("t5_dense_ts.tex", trow, col)
            got = m.get(key, {}).get("median")
            if want is None or got is None:
                print(f"  ABSENT {label:28s} {name}: page={got} paper={want}")
                bad += 1
                continue
            # T5 prints 3 significant figures, so compare there.
            ok = abs(got - want) <= max(0.005 * abs(want), 0.005)
            checked += 1
            if not ok:
                print(f"  DIFFER {label:28s} {name}: page={got:.6g} "
                      f"paper={want:.6g}")
                bad += 1
    print(f"  {checked} DEEP-10M cells match the paper's table")
    return checked, bad


def _check_prose(page_ts):
    """Every hand-typed number in the page's prose, against the paper's table.

    Returns (checked, bad). Absent prose is a FAILURE, not a skip: an entry
    here means the page made that claim, so a regex that stops matching means
    either the sentence was reworded (re-pin it) or the claim was dropped
    (delete the entry). Silently passing would turn this gate off one sentence
    at a time, which is how the caption went unchecked in the first place.
    """
    import claims_check as C

    if not page_ts.exists():
        print(f"  page source not found at {page_ts}; prose unchecked")
        return 0, 1
    body = page_ts.read_text(encoding="utf-8")
    checked = bad = 0
    for entry in PROSE:
        pid, pattern, ref = entry[0], entry[1], entry[2]
        scale = entry[3] if len(entry) > 3 else 1.0
        hits = re.findall(pattern, body)
        if not hits:
            print(f"  ABSENT {pid:24s} no prose matches /{pattern}/")
            bad += 1
            continue
        if len(set(hits)) > 1:
            print(f"  SPLIT  {pid:24s} prose says {sorted(set(hits))} in "
                  f"{len(hits)} places")
            bad += 1
            continue
        table_val = C.cell(*ref)
        if table_val is None:
            print(f"  STALE  {pid:24s} no cell {ref} in the paper")
            bad += 1
            continue
        # A capture that will not parse is a BAD REGEX, and it must be a
        # finding rather than a traceback. `([\d.]+)` at the end of a sentence
        # swallows the full stop and returns "0.71.", which crashed this
        # function mid-run: entries after it were never checked at all, and
        # refresh_web_page reported the exception line as the gate's status,
        # so the run read as a pass. A gate that can die partway through is a
        # gate whose coverage nobody can state.
        try:
            printed = float(hits[0])
        except ValueError:
            print(f"  REGEX  {pid:24s} captured {hits[0]!r}, not a number; "
                  "the pattern is over-greedy (a trailing '.' is usually a "
                  "sentence period, so prefer (\\d+(?:\\.\\d+)?))")
            bad += 1
            continue
        want = table_val * scale
        # Half a unit in the last printed digit: the prose rounds the table.
        decimals = len(hits[0].split(".")[1]) if "." in hits[0] else 0
        ok = abs(printed - want) <= 0.5 * 10 ** -decimals + 1e-9
        checked += 1
        print(f"  {'ok    ' if ok else 'DIFFER'} {pid:24s} "
              f"page={printed:<11.6g} paper={want:<13.6g} {ref[1]}")
        if not ok:
            bad += 1
    return checked, bad


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

    print("\nDEEP-10M tier, page table vs the paper's table")
    d_checked, d_bad = _check_dense_10m(payload)

    print(f"\nprose: {PAGE_TS}")
    p_checked, p_bad = _check_prose(PAGE_TS)
    print(f"\n{p_checked} prose numbers checked against the paper, "
          f"{p_bad} disagree")
    return 1 if (bad or d_bad or p_bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
