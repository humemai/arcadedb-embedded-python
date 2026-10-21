#!/usr/bin/env python3
"""Third gate: the page payload must agree with its own sources.

`provenance_check` asks whether a cell traces to a run; `fairness_check`
whether the arms were matched. This asks whether the payload the lane pages
render is consistent with itself, with the generated tables and with the rows:
the DEEP-10M table against the generated table (two generators aggregate
independently, and a change to either alone moves one artifact and not the
other); the atomicity counts against the artifact; every operation the query
set owes a column, with every engine answering or declared; every backend the
runner registers on its table; the multi-model table re-derived; no table
losing its ArcadeDB row; every disk column in gibibytes; every number under a
table traced to a generator, a registered sentence or a row.

The payload must be stamped with the one instrument the publish side renders
(publish_instrument.PUBLISH_INSTRUMENT) and must not be a skeleton. The page
source carries no number, so there is no prose to pin.

Usage:
    python page_check.py [--json PATH]
"""

from __future__ import annotations

import argparse
import collections
import json
import csv
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from publish_instrument import PUBLISH_INSTRUMENT, results_dir

DEFAULT_JSON = results_dir() / "web_benchmarks.json"


def _frozen_path():
    """The freeze the payload was built from, read at CALL time so a test's BENCH_RESULTS_DIR applies."""
    return results_dir() / "runs_paper.csv"


_LANE_ROWS_CACHE = None


def _lane_has_rows(lane, workload=None):
    """Does the frozen set this publish is built from hold ANY row for a lane?

    A landing's scope is cumulative -- the lane being landed plus every lane
    already on the page -- so "in scope" stopped meaning "has rows". A lane
    that is in scope because a LATER landing will add it, and has not been
    measured yet, has no table, and the two guards below read that absence as
    a coverage gap rather than as work not yet done.

    The distinction they actually need is this one: a table is missing either
    because its lane was excluded (the instruction), because its lane has no
    rows at this pin (not measured yet, and the payload declares it pending),
    or because something dropped it (a finding). Only the third is a finding.
    """
    global _LANE_ROWS_CACHE
    if _LANE_ROWS_CACHE is None:
        # (lane, workload, backend) -> row count, so "has rows" can mean what
        # the caller needs it to mean.
        _LANE_ROWS_CACHE = collections.Counter()
        path = _frozen_path()
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r.get("lane"):
                        _LANE_ROWS_CACHE[(r["lane"], str(r.get("workload")),
                                          str(r.get("backend")))] += 1
        except OSError:
            pass
    # A COMPLETE CELL, NOT A ROW. The graph lane has thousands of `oltp` rows
    # and exactly ONE `olap` row -- the single cell qOB produced before it was
    # stopped (#109) -- and the analytics table cannot be built from it, so the
    # payload has no such table and the roster read that as a defect. A lane
    # having rows says nothing about whether a particular TABLE's workload was
    # measured; the table needs at least one backend with a full set of
    # repetitions behind it.
    want = 2   # two repetitions is already more than a stopped stage leaves
    for (ln, wl, _be), n in _LANE_ROWS_CACHE.items():
        if ln != lane:
            continue
        if workload is not None and wl != str(workload):
            continue
        if n >= want:
            return True
    return False


def _generated_dir():
    """The generated tables are this gate's other half: the .tex tables feed the DEEP-10M cross-generator section, and
    they are read through claims_check.TABLES, which main() points here once."""
    return results_dir() / "generated"


def _runs_jsonl():
    """The rows the atomicity counts are read from."""
    return results_dir() / os.environ.get("BENCH_RUNS_JSONL", "runs.jsonl")


_PAGE = None


class _PageCells:
    """Callable accessor over the exported JSON for the page-derived pins."""
    def __init__(self, payload):
        self.t = {t["id"]: t for t in payload.get("tables", [])}

    def __call__(self, table, backend, scale, column):
        for e in self.t[table]["entries"]:
            if e["backend"] == backend and str(e.get("scale")) == str(scale):
                return float(e["metrics"][column]["median"])
        raise KeyError((table, backend, scale, column))

    def max(self, table, scale, column):
        vals = [float(e["metrics"][column]["median"]) for e in self.t[table]["entries"]
                if str(e.get("scale")) == str(scale) and column in e["metrics"]]
        return max(vals)

# The site checkout holds the payload the DBBench lane pages serve. BENCH_SITE_DIR wins, because the repos are only
# siblings in a clone and a worktree is not; refresh_web_page exports the checkout it is publishing to.
_SITE = Path(os.environ.get("BENCH_SITE_DIR")
             or Path(__file__).resolve().parents[2].parent / "humem.ai")
LIVE_JSON = _SITE / "src" / "data" / "dbbench-benchmarks.json"


# The page's DEEP-10M rows against T5's, cell for cell.
#
# Both sides read the dense_mp5_<pin> overlay, but through two separate
# implementations: export_web._dense_overlay_entries for the page and
# make_paper_tables for the paper. That is the "two generators aggregate
# independently" hazard this file's docstring opens with.
#
# page label -> (T5 row label, cold col, warm col, recall col)
# Both label sets now carry the stored precision, so both sides of this map
# moved at once. That is the case a mapping like this is worst at: rename one
# side and every row goes ABSENT, which reads as "the tier vanished" rather
# than "the label changed". Keeping the two columns literally side by side is the cheap defence.
DENSE_10M = {
    # page label                  T5 row label            cold warm recall
    "ArcadeDB (embedded, fp32)": ("ArcadeDB (emb, fp32)", 1, 2, 4),
    "ArcadeDB (embedded, int8)": ("ArcadeDB (emb, int8)", 1, 2, 4),
    "ArcadeDB (server, fp32)":   ("ArcadeDB (srv, fp32)", 1, 2, 4),
    "Qdrant (fp32)":             ("Qdrant (fp32)", 1, 2, 4),
    "Chroma (fp32)":             ("Chroma (fp32)", 1, 2, 4),
    "DuckDB VSS (fp32)":         ("DuckDB-VSS (fp32)", 1, 2, 4),
    "LanceDB (int8)":            ("LanceDB (int8)", 1, 2, 4),
    "Milvus (fp32)":             ("Milvus (fp32)", 1, 2, 4),
}


def _dense_cache_set_by_campaign():
    """The graph build cache sizes SET on ArcadeDB's dense rows.

    graph_build_cache_configured is what the harness handed the engine: 0 is
    the engine's own sizing (DECISIONS #52), anything above is a pinned cache
    (DECISIONS #56 was 9,990,000). Read from the frozen rows the page is built
    from, so the answer follows the data and not a constant written for one
    campaign. The multipass overlay files do not record the field; the
    campaign's single-pass rows of the same arms do, and one stage environment
    runs both. An empty set means nothing was pinned.
    """
    import csv as _csv
    frozen = _frozen_path()
    out = set()
    if not frozen.exists():
        return out
    for r in _csv.DictReader(frozen.open()):
        if r.get("lane") != "l3d" or not str(r.get("backend", "")).startswith("arcadedb"):
            continue
        try:
            v = int(float(r.get("graph_build_cache_configured") or 0))
        except ValueError:
            continue
        if v > 0:
            out.add(v)
    return out


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
        # WITHHELD AGAIN versus NOT YET MEASURED. "Withheld" is the real
        # case: the lane ran and its ten-million tier did not reach the page.
        # Before the dense stage runs -- a staged landing arrives table by
        # table -- there is no tier to withhold. The rows decide,
        # the same way the lost-table check decides.
        if "l3d" not in _lanes_with_rows():
            print("  no deep10m rows yet: the dense lane has no rows at this "
                  "pin, so the cross-generator comparison lands with its stage")
            return 0, 0
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
            # Compare at the precision T5 PRINTS: half a unit in the last
            # printed place. "0.82" against the page's 0.815 is agreement, and
            # the old 0.5%-of-value rule (0.0041) called it a DIFFER.
            _txt = C.cell_text(*(("t5_dense_ts.tex", trow, col)))
            _dec = len(_txt.split(".")[1]) if _txt and "." in _txt else 0
            ok = abs(got - want) <= 0.5 * 10 ** -_dec + 1e-9
            checked += 1
            if not ok:
                print(f"  DIFFER {label:28s} {name}: page={got:.6g} "
                      f"paper={want:.6g}")
                bad += 1
    # The build cache is disclosed when a row records a cache that was SET, and
    # a sentence saying one was set is a false statement when none was
    # (DECISIONS #59: the engine's own defaults). A disclosure that can silently
    # drop off the page is not a disclosure.
    _l3d = next((t for t in payload.get("tables", []) if t["id"] == "l3d"), {})
    conds = " ".join(_l3d.get("conditions", []))
    said = "graphBuildCacheSize pinned to the corpus size" in conds
    set_to = _dense_cache_set_by_campaign()
    if set_to and said:
        checked += 1
        print(f"  build-cache disclosure present on the dense table (cache set to {sorted(set_to)})")
    elif set_to:
        print(f"  MISSING the build-cache disclosure on the dense table: rows record the "
              f"cache set to {sorted(set_to)} and the table does not say so")
        bad += 1
    elif said:
        print("  FALSE build-cache disclosure on the dense table: it says the cache was "
              "pinned and no row records one (graph_build_cache_configured is 0, the "
              "engine default, on every ArcadeDB dense row)")
        bad += 1
    else:
        checked += 1
        print("  build cache: every ArcadeDB dense row ran the engine default "
              "(graph_build_cache_configured 0), so there is no pinned setting to disclose")
    print(f"  {checked} DEEP-10M cells match the paper's table")
    return checked, bad


def _page_index(payload):
    """(table, backend label, column) -> median, for every published cell."""
    out = {}
    for table in payload.get("tables", []):
        for entry in table.get("entries", []):
            for column, stat in entry.get("metrics", {}).items():
                # A derived table's cell is text ({"text": ...}, the
                # multi-model coverage table); it has no median to index.
                out[(table["id"], entry["backend"], column)] = (
                    stat.get("median") if isinstance(stat, dict) else None)
    return out


# Every backend the e2atom table can carry (export_web DISPLAY_NAMES): the
# torn-count check enumerates these rather than a short list, so a comparator
# that joins is checked the day it lands.
E2_SINGLE_ENGINE = ("arcadedb_e2", "arcadedb_e2_server", "surrealdb_e2",
                    "surrealdb_e2_server", "neo4j_e2", "pg_age_e2", "arangodb_e2",
                    "mongodb_e2", "memgraph_e2", "ladybug_e2", "duckdb_e2")
# Optional until a campaign has measured them.
E2_OPTIONAL = ("arangodb_e2", "mongodb_e2", "memgraph_e2", "ladybug_e2", "duckdb_e2")
E2_BACKENDS = E2_SINGLE_ENGINE + ("composed_qdrant_neo4j",)


def _check_page_atomicity(payload):
    """The e2atom table's trial and torn counts, against the artifact.

    A count is exactly the kind of number that rots quietly: re-run the lane
    with a different E2_TRIALS and a stale cell still reads the old total.
    These counts are in no generated table, so they are read from the run log
    directly -- the same rows claims_check's e2_atomicity() reads -- and held
    against the cells the payload prints.
    """
    import json as _json
    runs = _runs_jsonl()
    if not runs.exists():
        # Reported, not a traceback: this path ran into one whenever the log
        # was named something other than runs.jsonl and BENCH_RUNS_JSONL was
        # not exported with it.
        print(f"  no results log at {runs}; atomicity counts unchecked")
        return 0, 1
    # NEWEST ROW PER CANONICAL KEY, the same rule every table applies.
    # runs.jsonl is append-only and a campaign file can be merged more than
    # once, which triples these counts.
    newest = {}
    with open(runs) as fh:
        for line in fh:
            try:
                r = _json.loads(line)
            except ValueError:
                continue
            if not (r.get("lane") == "e2" and r.get("workload") == "atomicity" and r.get("trials") is not None):
                continue
            k = (r.get("lane"), r.get("scale"), r.get("n_docs"), r.get("workload"),
                 r.get("backend"), r.get("gav"), r.get("rep"))
            if k not in newest or str(r.get("ts_utc", "")) > str(newest[k].get("ts_utc", "")):
                newest[k] = r
    per_rep = collections.defaultdict(list)
    for r in newest.values():
        per_rep[r["backend"]].append((int(r.get("trials") or 0), int(r.get("torn_count") or 0)))

    table = next((t for t in payload.get("tables", []) if t.get("id") == "e2atom"), None)
    if table is None:
        print("  (no e2atom table in the payload; nothing to hold against the artifact)")
        return 0, 0
    import statistics as _st
    cells = {str(e.get("backend_key")): e.get("metrics") or {} for e in table.get("entries", [])}
    checked = bad = 0
    for be in E2_BACKENDS:
        reps = per_rep.get(be)
        m = cells.get(be)
        if m is None:
            if reps is None and be in E2_OPTIONAL:
                print(f"  skip    page.e2.{be}: not yet on the table")
            elif reps is None:
                print(f"  NODATA  page.e2.{be}: no fixed-harness rows"); bad += 1
            elif be in E2_OPTIONAL:
                print(f"  skip    page.e2.{be}: rows exist and the table does not print the arm")
            else:
                print(f"  MISSING page.e2.{be}: rows exist and the table does not print the arm"); bad += 1
            continue
        if reps is None:
            print(f"  NODATA  page.e2.{be}: the table prints the arm and the artifact has no fixed-harness rows")
            bad += 1
            continue
        for col, idx in (("trials", 0), ("torn results", 1)):
            want = _st.median(x[idx] for x in reps)
            got = (m.get(col) or {}).get("median")
            checked += 1
            if got is None or abs(float(got) - want) > 1e-9:
                print(f"  DISAGREE page.e2.{be} {col}: page={got} artifact={want}")
                bad += 1
            else:
                print(f"  ok      page.e2.{be:<24} {col}={got:g}")
        # The single-engine arms must be ZERO torn, and zero is the one value
        # a broken read also produces, so the trial count is asserted beside it.
        if be in E2_SINGLE_ENGINE:
            n_trials = sum(x[0] for x in reps)
            n_torn = sum(x[1] for x in reps)
            checked += 1
            if n_trials <= 0 or n_torn != 0:
                print(f"  DISAGREE page.e2.{be}: {n_torn} torn over {n_trials} trials, a single-engine arm must tear none")
                bad += 1
    return checked, bad


_ONLY_LANES = {x.strip() for x in os.environ.get("BENCH_ONLY_LANES", "").split(",") if x.strip()}


def _pin_in_scope(pid):
    """Is this pin's subject a table this landing carries?

    Pin ids are dotted and start with the table or lane they describe
    ("dense.arcadedb.cold", "l2olap.view.top_degree", "l3smp.max_gain.small"),
    so the first segment is the subject. Mapped through the same table->lane
    table the LOST check uses, with a couple of prefixes that name a lane
    directly. Anything that does not resolve stays IN scope, so an unknown pin
    is still checked rather than silently waved through.
    """
    head = str(pid).split(".", 1)[0]
    lane = _table_lanes().get(head, (None,))[0]
    if lane is None:
        lane = {"dense": "l3d", "sparse": "l3s", "l3smp": "l3s",
                "graph": "l2", "docs": "l1tpc", "ts": "l4"}.get(head)
    return lane is None or lane in _ONLY_LANES


def _table_lanes():
    """page table id -> (lane, workload), read from export_web by ast.

    Not imported: export_web validates pinned artifacts at module scope and
    would refuse here for reasons that have nothing to do with this gate.
    """
    if not hasattr(_table_lanes, "_v"):
        import ast as _ast
        src = (HERE / "export_web.py").read_text(encoding="utf-8")
        out = {}
        for node in _ast.parse(src).body:
            if (isinstance(node, _ast.Assign)
                    and getattr(node.targets[0], "id", "") == "_TABLE_LANE"):
                out = _ast.literal_eval(node.value)
        _table_lanes._v = out
    return _table_lanes._v


def _lanes_with_rows():
    """Lanes that have at least one row in this campaign's frozen CSV.

    The evidence for "this lane has run at this pin". Empty when the freeze
    does not exist yet, which makes every lane read as not-yet-measured --
    correct, because nothing has been frozen.
    """
    if not hasattr(_lanes_with_rows, "_v"):
        import csv as _csv_local
        frozen = _frozen_path()
        lanes = set()
        if frozen.exists():
            for r in _csv_local.DictReader(frozen.open()):
                if r.get("lane"):
                    lanes.add(r["lane"])
        _lanes_with_rows._v = lanes
    return _lanes_with_rows._v


def _check_no_arcadedb_row_lost(payload):
    """Every table prints an ArcadeDB row, and none the site serves now has lost one.

    A published table without our own engine in it is not a publish, it is a
    deletion. A re-measure once withheld the ArcadeDB rows of a table (an
    engine_version that identifies no build is withheld, correctly), the fresh
    table carried only the comparators, the exporter said so in a line nobody
    reads in a 200-line log, and no gate failed.

    Two halves. The payload on its own: a table with entries and no ArcadeDB
    row is a loss, unless the table declares the withdrawal. And against the
    payload the site serves today (LIVE_JSON, when the site checkout has one):
    a table that carried ArcadeDB there must still be here."""
    _is_arc = lambda e: bool(e.get("is_arcadedb")) or str(e.get("backend", "")).startswith("ArcadeDB")
    fresh = {t["id"]: t for t in payload.get("tables", [])}
    checked = bad = 0
    # The FLAG is what the page shades and sorts by. A row whose label says
    # ArcadeDB but whose flag is false renders unshaded among the comparators.
    for tid, t in sorted(fresh.items()):
        for e in t.get("entries", []):
            if str(e.get("backend", "")).startswith("ArcadeDB") and not e.get("is_arcadedb"):
                print(f"  UNFLAGGED {tid}: {e.get('backend')!r} reads ArcadeDB but is_arcadedb is false")
                bad += 1

    def _withdrawn(t):
        # A WITHDRAWAL IS DECLARED, A LOSS IS NOT. Taking our own row down is
        # sometimes the honest act (numbers that flatter us come down rather
        # than stand with a caveat), so the table must say so in a condition a
        # reader sees, naming ArcadeDB and giving the reason.
        conds = " ".join(str(c) for c in t.get("conditions", []))
        return "ArcadeDB has no row on this table" in conds and len(conds) > 200

    for tid, t in sorted(fresh.items()):
        if not t.get("entries"):
            continue
        checked += 1
        if any(_is_arc(e) for e in t["entries"]):
            continue
        if _withdrawn(t):
            print(f"  WITHDRAWN {tid}: ArcadeDB's row is down by declaration, and the table says why")
            continue
        print(f"  LOST   table {tid}: no ArcadeDB row, {[e.get('backend') for e in t['entries']][:4]}")
        bad += 1

    if not LIVE_JSON.exists():
        print(f"  (no data file at {LIVE_JSON}; nothing the site serves to compare against)")
        return checked, bad
    live = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
    live_has = {t["id"] for t in live.get("tables", []) if any(_is_arc(e) for e in t.get("entries", []))}
    for tid in sorted(live_has):
        checked += 1
        if tid in fresh:
            continue
        # LOST versus NOT YET MEASURED, and the ROWS decide which: a staged
        # landing legitimately lacks the tables whose lanes are still queued.
        # A table whose lane HAS rows at this pin and is still missing is the
        # real thing this rule protects.
        lane = _table_lanes().get(tid, (None,))[0]
        if lane and lane not in _lanes_with_rows():
            print(f"  not yet measured: table {tid} is on the site and its lane {lane!r} "
                  f"has no rows at this pin; it lands with its stage")
            continue
        # A DERIVED TABLE FOLLOWS THE TABLES IT DERIVES FROM. `multimodel` has
        # no lane of its own, so under a landing scoped to one lane it cannot
        # be built at all.
        if not lane and _ONLY_LANES:
            print(f"  not yet measured: table {tid} is derived from tables this "
                  f"landing does not carry (scoped to {','.join(sorted(_ONLY_LANES))})")
            continue
        print(f"  LOST   table {tid}: on the site, not in the export")
        bad += 1
    return checked, bad


def _check_disk_units(payload):
    """Every 'disk GiB' cell must be gibibytes: mini's largest data set is
    DEEP-10M at a few dozen GiB, so a median above 200 is a megabyte value that
    skipped the divisor."""
    bad = []
    for t in payload.get("tables", []):
        cols = t.get("columns") or []
        for e in t.get("entries", []):
            m = e.get("metrics") or {}
            for c in cols:
                if "disk" in c.lower() and "GiB" in c:
                    v = m.get(c) if isinstance(m, dict) else None
                    med = v.get("median") if isinstance(v, dict) else v
                    if isinstance(med, (int, float)) and med > 200:
                        bad.append((t.get("id"), e.get("backend"), e.get("scale"), c, med))
    for b in bad:
        print(f"  DISK-UNITS FAIL {b}")
    return not bad


def _check_instrument(payload):
    """The payload must be the one instrument the publish side renders, measured rows only. Returns bad count."""
    bad = 0
    if payload.get("instrument") != PUBLISH_INSTRUMENT:
        print(f"  WRONG INSTRUMENT: the payload is stamped {payload.get('instrument')!r}; "
              f"this tooling publishes {PUBLISH_INSTRUMENT} only")
        bad += 1
    if payload.get("skeleton"):
        print("  SKELETON: the payload is stamped skeleton; the lane pages take measured rows only")
        bad += 1
    for t in payload.get("tables", []):
        if t.get("instrument") != PUBLISH_INSTRUMENT:
            print(f"  WRONG INSTRUMENT: table {t.get('id')} is stamped {t.get('instrument')!r}")
            bad += 1
    if not bad:
        print(f"  payload and all {len(payload.get('tables', []))} tables are {PUBLISH_INSTRUMENT}, not a skeleton")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    ap.add_argument("--rows", default=None,
                    help="the frozen CSV the condition pins are evaluated against "
                         "(default: results/runs_paper.csv)")
    args = ap.parse_args()

    # Point claims_check at the generated tables, once. page_check reads every
    # generated cell through claims_check.cell(), whose TABLES was fixed at
    # import; setting the attribute keeps one definition, and the two
    # functions that import claims_check get the same module object.
    import claims_check as _C
    _C.TABLES = str(_generated_dir() / "tables")
    print(f"generated tables: {_C.TABLES}")

    path = Path(args.json)
    if not path.exists():
        print(f"missing {path}; run export_web.py first", file=sys.stderr)
        return 2

    payload = json.loads(path.read_text(encoding="utf-8"))
    cells = _page_index(payload)

    print(f"page: {path}")
    print(f"  {len(payload['tables'])} tables, {len(cells)} published cells")
    print("\nthe payload's instrument")
    i_bad = _check_instrument(payload)

    print("\nDEEP-10M tier, page table vs the generated table")
    d_checked, d_bad = _check_dense_10m(payload)

    global _PAGE
    _PAGE = _PageCells(payload)

    print("\nE2 atomicity counts on the page, against the artifact")
    a_checked, a_bad = _check_page_atomicity(payload)
    print(f"\n{a_checked} page count(s) checked against the artifact, "
          f"{a_bad} disagree")
    print("\nno table loses its ArcadeDB row")
    l_checked, l_bad = _check_no_arcadedb_row_lost(payload)
    print(f"\n{l_checked} table(s) checked, {l_bad} lost ArcadeDB")
    c_bad, (c_exp, c_present, c_declared, c_undeclared) = _check_coverage(payload)
    print(f"\ncoverage: {c_exp} operation-engine cell(s) expected, "
          f"{c_present} present, {c_declared} absent and declared, "
          f"{c_undeclared} absent and undeclared")
    print("\ncoverage A3: every backend the runner registers for a lane is on "
          "each table the lane feeds, as a row or a declared absence")
    r_checked, r_bad = _check_lane_roster(payload)
    print(f"\n{r_checked} lane registration(s) held against the tables, "
          f"{r_bad} roster finding(s)")
    print("\nmulti-model coverage table, cell for cell against the tables it is derived from")
    m_checked, m_bad = _check_multimodel(payload)
    print(f"\n{m_checked} coverage cell(s) re-derived, {m_bad} disagree")
    print("\nevery disk column is in gibibytes")
    u_ok = _check_disk_units(payload)
    if u_ok:
        print("  no disk cell above 200 GiB")
    print("\nconditions: every sentence under every table has a source for its numbers")
    rows_path = Path(args.rows) if args.rows else _frozen_path()
    rows = list(csv.DictReader(rows_path.open())) if rows_path.exists() else []
    if not rows:
        print(f"  (no frozen rows at {rows_path}; row-derived pins will read as STALE)")
    k_bad = _check_conditions(payload, rows)
    print(f"\n{k_bad} condition finding(s)")
    print("\nno sentence names an arm the page does not print (OFF_PAGE_ARMS)")
    o_bad = _check_off_page_names(payload)
    print(f"  {o_bad} off-page name(s) in page sentences")
    print("\na dense cell ArangoDB's one-list defect decided is marked not comparable "
          "(BUGS F175)")
    n_bad = _check_one_list_not_comparable(payload)
    print(f"  {n_bad} not-comparable finding(s)")
    print("\nthe dense table's ArangoDB IVF sentence says what the harness does, from the rows")
    iv_bad = _check_arango_ivf_sentence(payload, rows)
    print(f"  {iv_bad} IVF sentence finding(s)")
    print("\nevery override a table meets is named under it (CAMPAIGN section 7 row 21)")
    ov_bad = _check_override_disclosures(payload, rows)
    print(f"  {ov_bad} undisclosed override(s)")
    return 1 if (i_bad or d_bad or a_bad or l_bad or c_bad
                 or r_bad or m_bad or not u_ok or k_bad or o_bad or n_bad or iv_bad or ov_bad or j_bad) else 0


# --------------------------------------------------------------------------
# COVERAGE: the query set the page owes, and the fields it measured
#
# WHY THIS EXISTS. Tables whose column lists did not move when the instrument
# did printed neither the single-record operations, nor most analytical
# queries, nor a cold column; a fix applied by hand missed two dense
# maintenance operations in the same pass. Attention is not a mechanism; a
# gate is.
#
# TWO ASSERTIONS, because one of them only catches half of it.
#
#   A1, the manifest. Every operation the settled query set says a table
#   carries must BE a column on that table, and every engine on the table must
#   have a value in it or a declared reason why not. This is the half that
#   catches a query which stopped being measured: no field, nothing unprinted,
#   and without the manifest nothing to notice the silence against. The
#   operations are written here EXPLICITLY, as data, because a list derived
#   from what happens to be present cannot assert anything. The engines are
#   not written here: they are read from the table, because the engine roster
#   is a campaign decision that moves, while the query set is #82d and is
#   settled.
#
#   A2, the fields. Every measured field on a published row either appears in
#   a column of its table or is named in NOT_PRINTED with a reason. This is
#   the half that catches a measurement the page forgot.
#
#   A3, the roster. A1 reads its engines OFF THE TABLE, so an engine with no
#   row at all is not "on the table" and A1 cannot miss it: an engine whose
#   analytics row was never written left the table one engine short while
#   every gate was green. The roster
#   is therefore read from the RUNNER: every backend runner.LANES registers
#   for a lane must be on each table the lane feeds, either as a row
#   (matched by the backend_key the exporter stamps on every lane-fed entry)
#   or as a declared absence naming the engine; an ablation arm the page
#   deliberately does not print is named in export_web.OFF_PAGE_ARMS with its
#   reason. Anything else registered is MISSING, and a row from a backend the
#   runner does not register for the lane is STRAY.
#
# A declared absence is one of three things, and all three are DATA on the
# payload rather than prose a gate has to parse: a censored cell (the engine
# exceeded the budget every arm had, so there is no row), a withheld cell (the
# answer disagreed and the number was taken off the page), or a query the
# engine's language cannot express, declared by the adapter under DECISIONS
# #88. The fourth case, a measurement an engine does not make at all because
# the operation has no meaning for it, is NOT_MEASURED_BY_ENGINE below.
OPERATION_MANIFEST = {
    # DECISIONS #82d, forty operations. The label is the page's own column
    # heading, so a renamed column fails here and is renamed deliberately.
    "docs_oltp": ["new-order p50 ms", "payment p50 ms", "insert p50 ms",
                  "read p50 ms", "update p50 ms", "delete p50 ms",
                  "OLTP ops/s"],
    "docs_olap": ["Q1 p50 ms", "Q6 p50 ms", "top parts p50 ms",
                  "ship mode p50 ms", "by month p50 ms", "cold first query ms"],
    "l2": ["point p50 ms", "1-hop p50 ms", "2-hop p50 ms",
           "3-hop filtered p50 ms", "insert p50 ms", "update p50 ms",
           "delete p50 ms"],
    "l2olap": ["average friend age p50 ms", "friends in same city p50 ms",
               "most friends p50 ms", "degree distribution p50 ms",
               "triangle count p50 ms",
               # LSQB's nine (DECISIONS #104): fourteen query columns in all.
               *[f"LSQB Q{i} p50 ms" for i in range(1, 10)],
               "cold first query ms"],
    "l3d": ["cold p50 ms", "recall@10", "after insert p50 ms",
            "after delete p50 ms", "insert into index ms/vector",
            "delete from index ms/vector", "recall@10 after insert",
            "recall@10 after delete", "ingest+index total s"],
    # "cold p50 ms", as l3d: the sparse table carries the multipass overlay's
    # cold/warm pairs, and a bare "p50 ms" matches no column.
    "l3s": ["cold p50 ms", "recall@10", "ingest+index total s"],
    "l4": ["newest reading p50 ms", "12h aggregate p50 ms",
           "per-host hourly p50 ms", "high-usage p50 ms",
           "grouped, ordered, limited p50 ms", "cold first query ms",
           "ingest points/s"],
    "e2": ["transaction p50 ms", "retrieval p50 ms",
           "graph-filtered search p50 ms"],
    "e2atom": ["torn results"],
}

# A measurement an engine does not make, for a reason that is about the engine
# rather than about this run. Keyed (table, column, backend) or
# (table, column, "*") for every engine on the table.
NOT_MEASURED_BY_ENGINE = {
    # Filled from the publish that first meets each case, with its reason.
    # Seeded empty on purpose: a blank here is a finding, not a default.
}

# Fields that are measured and deliberately not printed. Patterns rather than
# names, because these are families: 428 numeric fields across seven lanes,
# and naming each would be a list nobody maintains. Each entry is (regex,
# reason), and the reason is the thing being asserted -- a family added here
# without one is the same miss this gate exists to catch.
NOT_PRINTED = [
    # AND IT HAPPENED AGAIN, one decision later. The paragraph below was written
    # about `_budget_source` (DECISIONS #106), which is now a correct tuple; the
    # entry it warns about was then reintroduced verbatim by DECISIONS #107 as a
    # bare `r"\w+_abandoned"` with its reason in a trailing comment. Same shape,
    # same silence: a bare string cannot fail until a row actually carries the
    # field. The gate then crashed with ValueError instead of reporting, on the
    # first publish after #107 -- so the commit that added the field also broke
    # the gate that must admit it.
    (r"^(olap_server_limit|\w+_server_limit_s|\w+_server_killed|cold_first_query_censored)$",
     "whether the server enforced the analytics budget and cut a query at it (DECISIONS #179): it "
     "qualifies the timing beside it (a cut time is a floor), a diagnostic about how a cell ended "
     "and not a column of its own"),
        (r"\w+_abandoned$",
     "whether a query was abandoned after its cold pass rather than run to the "
     "budget (DECISIONS #107): it qualifies the timing beside it, which makes "
     "it a diagnostic about how a cell ended and not a column of its own"),
    # Written as a BARE STRING with the reason in a trailing comment when
    # DECISIONS #106 landed, which made the entry a 17-character string that
    # `for pattern, reason in NOT_PRINTED` unpacks into 17 values. It could not
    # fail until a row actually carried a `_budget_source` field, so the gate
    # crashed with ValueError rather than reporting, on the first publish after
    # the change.
    # The paragraph above says a family added here without a reason is the miss
    # this gate exists to catch; this is that miss, in the gate itself.
    (r"\w+_budget_source$",
     "which budget applied to a query and whether it was measured or fell "
     "back to the lane's constant (DECISIONS #106): it qualifies the budget "
     "beside it, which is itself a diagnostic and not a column"),
    (r"^(point|hop1|hop2|hop3f)_warmup_n$|^read_warmup_s$",
     "the graph reads' untimed warm-up before the timed pass: how many queries of each class it ran "
     "and how long it took (l2_graph). It makes the warm columns warm and shows that it ran; it is "
     "not a column of its own"),
    (r"^mongodb_knows_self_loops$",
     "a count the MongoDB graph arm takes after its load: friendships whose two ends are one person. "
     "The undirected hops are exact only when it is 0 and the arm refuses the cell otherwise, so a "
     "published cell implies zero"),
    (r"^(ef|nprobe)\d+_(query_p50_ms|recall_at_10)$|^beam_max_recall_at_10$",
     "the dense search-beam sweep (dense_beam.py): one latency and one recall per beam setting. The "
     "page prints the matched-recall headline read off the curve, and carries the curve itself on the "
     "entry (`beam_curve`, median over runs); the best recall reached is in the text of a target no "
     "beam reached"),
    (r"^matched_r\d+_recall_at_10$",
     "the recall measured at the beam that first reached the target: it qualifies the matched latency "
     "beside it, which is the column"),
    (r"^(rep|rc|trials|seed)$",
     "provenance: which repetition this row is and whether it exited clean"),
    (r"^arcadedb_http_clients?$",
     "which HTTP client an ArcadeDB served arm ran with (CAMPAIGN 7 row 72, lean_http.py): a condition of the served arms, read from "
     "the session that ran, never a column. The e4 decomposition's row lists the two clients it measured (`arcadedb_http_clients`); its table "
     "names the client in each HTTP column instead (export_web._e4_arms)"),
    (r"^jpype_version$",
     "which JPype the process that ran the cell had loaded (CAMPAIGN 7 row 73, bench_common.jpype_version): a condition of the embedded "
     "ArcadeDB arms, read from the process (`jpype.__version__`), empty for every arm that never imports it, never a column"),
    (r"^(tpch_sf|n_docs|n_docs_ingested|n_lineitem|n_part|n_persons|"
     r"n_persons_in_corpus|n_persons_ingested|n_edges|n_edges_ingested|"
     r"n_points|n_products|n_rows|dim|dims|ts_chunk|ts_shards|last_window_s|"
     # the analytics message half (DECISIONS #104): what the LSQB queries walk
     r"msg_vertices|msg_edges)$",
     "the corpus: it is the Size column and the dataset line under the table"),
    (r"^(oltp_ops|oltp_total_s|ops|payments_n|read_ops|write_ops|update_ops|"
     r"delete_ops|crud_\w+_ops|n_queries|n_queries_timed|query_n|olap_iters|"
     r"query_iters|lc_iters|lc_warmup|warmup_held_out|\w+_iters)$",
     "how many operations stand behind a cell: a condition under the table "
     "(_counts_note), never a column"),
    (r"_p95_ms$",
     "the page prints p50 and p99; p95 never changed a reading and costs a "
     "column on a phone"),
    (r"_p99_ms$",
     "one ninety-ninth percentile per table, on that table's headline query "
     "(DECISIONS #89 as amended): a p99 beside every p50 is twice the columns "
     "for an answer the headline already gives. The others are on the row"),
    (r"^q_range_(ms|p99_ms)$",
     "TSBS's one-hour single-host range query: measured since the lane "
     "existed and not in the query set (#82), which replaced it with "
     "the double group-by, the high-usage filter, and the ordered limit"),
    (r"^\w+_mean_ms$|^\w+_min_ms$|_query_max_ms$|^query_max_ms$",
     "the median is the statistic (DECISIONS #44); mean, min and max stay on "
     "the row for an audit"),
    (r"^mutate_(insert|delete)_s$",
     "the batch total behind the per-vector maintenance columns; the page "
     "prints the per-vector cost, which compares across engines and across "
     "the two operations whatever size the batch was"),
    (r"^cold_\w+|_cold_ms$",
     "one cold column per table, the first query of a session, not a cold "
     "number per query (DECISIONS #89 as amended); both spellings, because "
     "two lanes name the same quantity at opposite ends of the field"),
    (r"^q_groupby_distinct_\w+$",
     "the shape of the time-series grouping answer, which is what caught the "
     "served arm returning one bucket per host: an answer check, not a "
     "latency"),
    (r"^q_last_windowed_(ms|rows)$",
     "the last-point query is published unbounded; the windowed form is the "
     "A/B beside it and stays on the row"),
    (r"^warm_\w+",
     "the warm number IS the per-query column; this is the same value under "
     "its explicit name"),
    (r"^res_\w+_n$|^\w+_rows$",
     "the answer check's own record (DECISIONS #88): how many rows an answer "
     "held, compared across engines and not published as a latency"),
    (r"^res_\w+_profile$",
     "the answer profile (CAMPAIGN section 7 row 59): per declared column, how many distinct "
     "canonical values the answer holds and how many are 0 or null, read by degenerate_check.py "
     "to flag an agreed answer that cannot mean anything; a record of the answer, not a column"),
    (r"^(client|server)_(peak|end|io|disk|cpu)_\w+$|^server_(mem_cap_g|shm_size)$|"
     r"^(peak_mib_sum|peak_anon_mib_sum|peak_shmem_mib_sum|end_anon_mib_sum|"
     r"io_read_mib_sum|io_write_mib_sum|disk_mb_sum|cpu_usec_sum|client_mem_cap|"
     r"mem_cap|client_disk_mb|client_disk_baseline_mb)$",
     "the page prints the summed owned memory (anonymous plus shared) and the workload's "
     "disk; these are the per-side splits those two are computed from, and the anonymous "
     "part of the memory sum"),
    (r"^(hnsw_M|m|k|ef_construction|ef_search|ivf_\w+|degree_param|"
     r"graph_build_cache_\w+|qps|neo4j_vector_search_expansion|ladybug_ml|ladybug_mu|"
     r"lance_nprobes|es_num_candidates|es_rescore_oversample)$",
     "index parameters and their calibration: matched by effect and printed "
     "as conditions under the table, never as columns"),
    (r"^(settle_s|settle_s_lane|settle_s_adapter|engine_settle_s|gt_load_s|"
     r"recall_calc_s|query_gen_s|search_wall_s|phases_accounted_s|connect_s|"
     r"import_ms|build_close_ms|close_s|mutate_n|mutate_queries|mutate_ran|"
     r"corpus_release_s)$",
     "harness bookkeeping around a timed phase: settling, loading ground "
     "truth, computing recall, the phase accounting, and the time-series "
     "driver releasing its parsed corpus between ingest and the queries"),
    # Dense rows from the comparators that record these four fields.
    (r"^settle_(probes|first_ms|last_ms)$",
     "the evidence behind a settle wait (SurrealDB's HNSW index builds in the "
     "background, so the adapter probes until the latency is flat): how many "
     "probes it took and the first and last probe's latency. settle_s, the wait "
     "itself, is already declared above; these show that the index had caught "
     "up before any query was timed, which is an audit of a cell and not a "
     "column of it (BUGS F134)"),
    (r"^setup_s$",
     "the residue that makes the build's three timers partition its total "
     "(build_s less ingest_s less index_s, BUGS F101): schema DDL before the "
     "load and the settle after the index. Derived arithmetic over three "
     "numbers the table already prints, and a few seconds at most in builds "
     "of minutes to hours, so the page prints the total and the two phases "
     "and a reader can read the residue off them"),
    (r"^(mutate_deleted_hits|mutate_reinserted_hits)$",
     "correctness counters that must be zero; a non-zero one is a defect "
     "report, not a column (l3d_dense records them on the row)"),
    (r"^(filtered_cand_p50|filtered_candset_match|filtered_overfetch|"
     r"filtered_hops|hop3_visited_\w+|gav_cypher_reads_issued|reconnects|"
     r"crash_raised_count|post_crash_state|degree_dist_budget_s|"
     r"\w+_budget_s|\w+_elapsed_s)$",
     "diagnostics that explain a cell rather than measure it; crashes raised "
     "came off the page under DECISIONS #73"),
    (r"^(first_open_ms|first_open_server_ms|jvm_start_ms|cold_start_penalty_ms|"
     r"cold_process_ms|clean_\w+|drop_\w+|stale_\w+|write_own_\w+|"
     r"write_read_\w+|read_\w+_ms|write_\w+_ms|\w+_session_ms|\w+_action_ms|"
     r"\w+_open_ms|\w+_close_ms)$",
     "the lifecycle lane measures every phase of a session and the table "
     "prints the session totals it compares"),
    (r"^(recall_filtered|recall_retrieval)$",
     "recall for the two cross-model read paths, printed by the e2 table "
     "under its own labels"),
    (r"^(memgraph|falkordb)_\w+$",
     "a served comparator's own config, read back at connect: its thread "
     "pool (FAIRNESS F6, audited in FAIRNESS.md rather than printed as a "
     "column), memory limit, and query timeouts, which explain the cell "
     "rather than measure it"),
    (r"^ladybug_(threads|buffer_pool_mib)$",
     "the LadybugDB graph arm's thread pool (read back from the engine) and "
     "buffer pool, fitted to the cpuset and to the cgroup memory limit (FAIRNESS "
     "F6, BUGS F160; audited in FAIRNESS.md rather than printed as a column)"),
    # THE NEWER ARMS' READ-BACKS: each is a setting or a check a new arm records about itself, and none is
    # a measurement of the work a table compares.
    (r"^pg_\w+$",
     "a PostgreSQL arm's server settings read back with SHOW: the pool fit "
     "(parallel workers, worker processes, work_mem, hash_mem_multiplier) sized "
     "from the cell's cpuset and cap (FAIRNESS F3/F6), audited in FAIRNESS.md "
     "rather than printed as a column"),
    (r"^es_(allocated_processors|available_processors|heap_max_mib)$",
     "Elasticsearch's processors and heap, read back from _nodes: its pool and "
     "heap fitted to the cell (FAIRNESS F6), audited rather than printed"),
    (r"^duckdb_threads$",
     "a DuckDB arm's thread pool, read back from the engine and held against "
     "the size of the cell's cpuset (FAIRNESS F6; fairness_check F15), stated "
     "under every table that shows DuckDB by a generated sentence rather than "
     "printed as a column"),
    # THE OVERRIDES A TABLE DISCLOSES (override_registry.py, CAMPAIGN section 7 row 21):
    # each field below is a setting this benchmark overrides, read back from the
    # engine and named under every table that shows the arm by a generated
    # sentence. fairness_check F15 holds each row to the value the sentence
    # claims, so a field here is a disclosure and never a column.
    (r"^(es_security_enabled|es_replicas)$",
     "Elasticsearch's security features and replica count, read from the engine "
     "(`_xpack`, the index settings): the sentence under every table that shows "
     "Elasticsearch says both are off"),
    (r"^duckdb_hnsw_persistence$",
     "DuckDB's experimental HNSW persistence flag, read from the engine "
     "(`current_setting`): the sentence under every table that shows the "
     "vector arm says it is on"),
    (r"^(neo4j_pagecache|neo4j_checkpoint_interval|neo4j_checkpoint_interval_default)$",
     "Neo4j's page cache size and checkpoint interval, read from the engine "
     "(`SHOW SETTINGS`): the sentences under every table that shows Neo4j say "
     "how each was set"),
    (r"^(arcadedb_add_hierarchy|arcadedb_add_hierarchy_source)$",
     "whether ArcadeDB's vector index was built with a hierarchy, and whether "
     "that was read from the engine (embedded) or recorded as the request "
     "(served, whose HTTP API returns no index metadata)"),
    (r"^index_kinds(_error)?$",
     "the index kinds an ArcadeDB arm's engine reports after its schema is built (SELECT FROM "
     "schema:indexes, type-level entries), or why it could not be asked: the evidence the "
     "sentence about hash indexes is generated from, and fairness_check F14d holds against "
     "the lanes' registry"),
    (r"^server_jvm_\w+$",
     "what a served ArcadeDB's JVM was running, read from the process (its flags, its maximum and initial "
     "heap in bytes, its collector, its JDK major, and the image-defaults stamp): the sentence under a table "
     "that prints the image-defaults arm is generated from them, and the JVM heap column prints the heap"),
    (r"^(server_query_max_heap_elements|server_query_max_heap_source)$",
     "the served ArcadeDB's limit on records or groups one query may hold in "
     "memory, asked of the engine over HTTP by the runner (or the container's "
     "own setting, named as the source when the engine could not be asked)"),
    (r"^server_http_body_max_(bytes|source|default)$",
     "the served ArcadeDB's limit on the size of one HTTP request body on the arms that bulk-load through the batch "
     "endpoint, asked of the engine over HTTP by the runner (or the container's own setting, named as the request in the "
     "source field when the engine could not be asked), and the engine's own default: the evidence behind the sentence "
     "that names the raised limit"),
    (r"^arcadedb_query_max_heap_ram_(mb|source)$",
     "the query heap budget (MB) an ArcadeDB arm of the documents lane ran with when the override was on (DECISIONS #175), read from the "
     "engine (embedded: GlobalConfiguration; served: the server's settings over HTTP) or named as the request in the source field when "
     "the engine could not be asked: the evidence behind the sentence that names the raised budget"),
    (r"^dense_id_index$",
     "the statement that built the dense arm's index on the vector id when BENCH_DENSE_ID_INDEX was on (#291, DECISIONS #178), or "
     "\"key\" where the engine's own record key is the id: the evidence behind the sentence that names the id index"),
    (r"^arcadedb_ts_result_format$",
     "how a served ArcadeDB time-series arm read its query answers when BENCH_ARCADEDB_TS_NDJSON was on (CAMPAIGN section 7 row 85): "
     "\"ndjson\", a stream of lines; the evidence behind the sentence that names the streamed reads"),
    (r"^sparse_warmup_queries$",
     "how many untimed searches the sparse lane ran on this engine before the timed pass when the warm-up was on (DECISIONS #177): "
     "the evidence behind the sentence that names the warm-up"),
    (r"^cpu_dma_latency_(us|held|error)$",
     "the CPU latency target (microseconds) the runner asked the kernel to hold for the timed cell when the idle-state hold was on "
     "(DECISIONS #177), whether the write to /dev/cpu_dma_latency succeeded, and why not when it did not: the evidence behind the "
     "sentence that names the hold"),
    (r"^ts_compaction_interval(_ms|_readback_error)?$",
     "the compaction interval ArcadeDB's native time-series arms created the type with, as the engine "
     "reports it (milliseconds), or why it could not be asked: the evidence behind the sentence that "
     "names the one-hour interval"),
    (r"^ts_mutable_at_ingest_end$",
     "the samples ArcadeDB's native time-series arms had not yet sealed when "
     "the ingest timer stopped, from the engine's own count: the evidence "
     "behind the sentence that says the ingest rate does not include sealing"),
    (r"^(es|duckdb|neo4j|arcadedb)_readback_error$",
     "the reason an override read-back failed on this row; fairness_check F15 "
     "reports the field it left absent, and this names why"),
    (r"^lc_affinity_cpus$",
     "the CPUs the lifecycle process could run on (sched_getaffinity), recorded "
     "beside its thread count after open so the pool can be audited against "
     "them (FAIRNESS F6); it describes the cell, not the session it times"),
    (r"^vector_index_size$",
     "a build check: the entries the vector index holds after the build, and "
     "the cell is refused unless that equals the products loaded; it qualifies "
     "the build rather than measures it"),
    (r"^qdrant_(points_at_first_green|settle_after_green_s)$",
     "the Qdrant sparse settle (BUGS F166): how many points the collection held "
     "at its first green status and how long the build then waited for the "
     "rest, both inside the build timer, so they explain the build column "
     "rather than add one"),
    (r"^(async_writers|lineitem_buckets|served_load_batch|load_call_rows)$",
     "the ArcadeDB documents loader's configuration: async writers, LineItem "
     "buckets (CAMPAIGN section 7 item 10), rows per load call, and the served "
     "batch size, recorded so the load can be reproduced; it sets the build up "
     "rather than measures it"),
    (r"^setup_s$",
     "the part of a dense build that is neither the ingest nor the index timer "
     "(schema, collection, connection), derived from three numbers the row "
     "carries; the table states its range in a sentence computed from the "
     "printed columns (BUGS F101) rather than a column of its own"),
    (r"^duckpgq_threads$",
     "the DuckPGQ graph arm's DuckDB thread pool, sized from the cpuset via "
     "PRAGMA threads=sched_getaffinity (FAIRNESS F6, audited in FAIRNESS.md "
     "rather than printed as a column)"),
    (r"^(torn_count|build_docs_per_s|ingest_pts_per_s|disk_data_mb|"
     r"peak_owned_mib_sum|build_s|ingest_s|index_s|gav_build_s)$",
     "printed under a different label by the table that owns it; listed here "
     "so a table which stops printing one still has to say so"),
    # --- recovered from a SECOND module-level NOT_PRINTED the merge left in
    # this file (BUGS F65). Two assignments, the later one winning, so these
    # four declarations were dead and their fields read as undeclared.
    (r"^duckpgq_(threads|extension_version)$",
     "the DuckPGQ graph arm's DuckDB thread pool, sized from the cpuset via "
     "PRAGMA threads=sched_getaffinity (FAIRNESS F6, audited in FAIRNESS.md "
     "rather than printed as a column), and the community build id the row "
     "carries beside the DuckDB version the page prints"),
    # THE SERVER-RESTART LANE (l6_restart.py, DECISIONS #139 item 2).
    (r"^(restart_iters|restart_warmup|restart_write_n|restart_poll_s|stop_grace_s|"
     r"restart_read_key|n_points)$",
     "the restart lane's protocol (cycles, warm-up, the write batch, the poll "
     "interval, the stop grace) and its fixed read's key, stated on every row and "
     "described under the table, never a column"),
    (r"^(restart_load_s|shutdown_after_load_s|write_batch_s|restart_read_recall_at_10|"
     r"restart_settle_reads|restart_settle_s)$",
     "the restart lane's parts that are not what it measures: the load (its own "
     "table's ingest column), the first stop (it flushes the whole load, a "
     "different question from a stop after a session), the write session that "
     "gives the next stop something to flush, the vector read's recall (the "
     "read is held against the same engine's own answer before the stop), and "
     "how many reads and seconds that answer took to settle"),
    (r"^(stop_killed_after_grace|stop_oom_killed|restart_writes_survived|restart_writes_visible_s)$",
     "the restart lane's checks on its own stops and restarts: whether Docker had "
     "to kill an engine that did not stop, an out-of-memory kill, and that every "
     "batch written before a stop read back after the restart (and how long it "
     "took to reappear); a check, not a column"),
    (r"^shutdown_sync_(calls|s)$",
     "the laptop shutdown trace (BENCH_RS_TRACE=1): which syncs a stop issued, "
     "evidence for the durability notes, never run in a campaign cell"),
    (r"^driver_version$",
     "the client library a served arm was reached through; the page prints "
     "the engine's version, and the driver stays on the row for an audit"),
    (r"^(msg_vertices|msg_edges|msg_limit|person_limit)$",
     "the full-network graph tier's message half, counted at load and "
     "checked against the corpus README by the lane; the Size label names "
     "the corpus and the ingest column prices it"),
    (r"^(n_lineitem_streamed|li_batches|li_batch_rows|li_row_groups|tsbs_lp)$",
     "how the corpus was read: the streamed line-item count the lane refuses "
     "a shortfall against, its batching, and the time-series file's name"),
    # --- host telemetry, recorded on every dense cell so a thermal event can
    # be told from an engine effect. It explains a cell rather than measuring
    # one, and FAIRNESS.md is where it is audited.
    (r"^host_(temp_c|throttle_count|throttle_total_ms)_(start|end)$",
     "the host's package temperature and throttle counters either side of a "
     "cell, so a slow run can be told apart from a throttled machine. NOT "
     "gated: no fairness invariant reads them today, and saying otherwise "
     "here would be false. The analysis "
     "that justifies publishing anyway is in BUGS.md F71: mini throttles "
     "13-26% of wall time, engines within one table throttle at rates that "
     "differ 3-7x, and that difference is NOT an ordering artefact -- cells "
     "do not start hotter later in a stage -- so it tracks how hard each "
     "engine drives the CPU, which is the engine's own property"),
    (r"^\w+_excluded_at_tier$",
     "the reason a query does not run at THIS corpus size, for every engine "
     "(graph_common.TIER_EXCLUDED, BUGS F74). Not an engine's inability -- "
     "that is UNEXPRESSIBLE -- and not a blank: the column is absent at this "
     "size and the table says why, while the same query publishes normally at "
     "the sizes where it is measurable. OWED: the "
     "exporter should turn this field into a declared absence on the table "
     "rather than leaving it only on the row"),
    (r"^host_throttled_ms$",
     "milliseconds the host spent throttled during a cell, from the same "
     "counters; a non-zero value invalidates the cell rather than becoming "
     "a column"),
]


def _measured_fields(rows, lane):
    """Numeric fields present on this lane's published rows."""
    out = set()
    for r in rows:
        if r.get("lane") != lane:
            continue
        for k, v in r.items():
            if v in (None, ""):
                continue
            try:
                float(v)
            except (TypeError, ValueError):
                continue
            out.add(k)
    return out


def _not_printed_reason(field):
    # search, not match: the families below are written as anchored patterns
    # where they mean a whole name and as suffixes where they mean a family
    # ("_p95_ms$" is every p95 on every lane).
    for pattern, reason in NOT_PRINTED:
        if re.search(pattern, field):
            return reason
    return None


def _derived_kind(table):
    """How a table with no lane got its cells: numbers re-read from other
    lanes' rows, or text derived from the other tables."""
    stats = [v for e in table.get("entries", []) for v in (e.get("metrics") or {}).values()]
    if stats and all(isinstance(v, dict) and "median" not in v for v in stats):
        return "text cells derived from the other tables"
    return "numbers re-read from other lanes' rows"


# THE MULTI-MODEL COVERAGE TABLE (DECISIONS #95) is derived from the other
# tables, so the gate derives it again, here, with the exporter's helpers but
# its own loop, and compares cell for cell: the same two-generators pattern
# the DEEP-10M tier gets. Every engine the roster names must appear on at
# least one table, or the roster has a typo the table would print as a row of
# "no arm".
def _check_multimodel(payload):
    """Returns (checked cells, bad)."""
    import export_web as EW
    tables = [t for t in payload.get("tables", []) if t.get("id") != "multimodel"]
    mm = next((t for t in payload.get("tables", []) if t.get("id") == "multimodel"), None)
    sources = EW.multimodel_sources(tables)
    if mm is None:
        if sources:
            print("  MISSING the multi-model coverage table: the payload carries the tables it derives from")
            return 0, 1
        print("  (no multi-model table; no table to derive it from)")
        return 0, 0
    checked = bad = 0
    want_cols = [str(t.get("title")) for t in sources]
    if list(mm.get("columns") or []) != want_cols:
        print(f"  COLUMNS multimodel: {mm.get('columns')} != the source tables' titles {want_cols}")
        bad += 1
    rows = {str(e.get("backend")): e for e in mm.get("entries", [])}
    if list(rows) != list(EW.MULTIMODEL_ENGINES):
        print(f"  ROWS    multimodel: {list(rows)} != {list(EW.MULTIMODEL_ENGINES)}")
        bad += 1
    for engine in EW.MULTIMODEL_ENGINES:
        anywhere = any(EW.multimodel_engine(EW.engine_family(e.get("backend"), e.get("is_arcadedb"))) == engine
                       for t in tables for e in t.get("entries", []))
        if not anywhere:
            print(f"  ROSTER  multimodel: {engine} is on no table in the payload")
            bad += 1
        e = rows.get(engine)
        if not e:
            continue
        for t in sources:
            col = str(t.get("title"))
            want, _kinds = EW.multimodel_cell(t, engine)
            got = ((e.get("metrics") or {}).get(col) or {}).get("text")
            checked += 1
            if got != want:
                print(f"  DIFFER  multimodel: {engine} x {col!r}: page {got!r}, derived {want!r}")
                bad += 1
        if any("median" in (v or {}) for v in (e.get("metrics") or {}).values()):
            print(f"  NUMBER  multimodel: {engine} carries a numeric cell on a table that measures nothing")
            bad += 1
    return checked, bad


def _check_coverage(payload):
    """A1 the manifest, A2 the fields. Returns (bad, summary line)."""
    import csv as _csv
    tables = {t["id"]: t for t in payload.get("tables", [])}
    expected = present = declared = undeclared = 0
    bad = 0

    print("\ncoverage A1: every operation in the query set is a column, with "
          "every engine answering or declared")
    for tid, operations in sorted(OPERATION_MANIFEST.items()):
        t = tables.get(tid)
        if not t:
            import export_web as _EW
            _lane = _EW._TABLE_LANE.get(tid, (None,))[0]
            _wl = _EW._TABLE_LANE.get(tid, (None, None))[1]
            if _ONLY_LANES and _lane and (_lane not in _ONLY_LANES
                                          or not _lane_has_rows(_lane, _wl)):
                # Same distinction the roster check draws one function down: a
                # table absent because its lane is outside this landing, or
                # because that lane has no rows at this pin yet, is the
                # instruction rather than a gap in coverage.
                continue
            print(f"  MISS   {tid}: the payload has no such table")
            bad += 1
            continue
        absences = t.get("declared_absences") or []
        whole_row = {a["backend"] for a in absences if not a.get("column")}
        per_cell = {(a["backend"], a.get("column")) for a in absences if a.get("column")}
        engines = sorted({str(e["backend"]) for e in t.get("entries", [])} | whole_row)
        for op in operations:
            expected += len(engines)
            if op not in (t.get("columns") or []):
                print(f"  MISS   {tid}: the query set says this table carries "
                      f"{op!r} and it is not a column")
                bad += 1
                undeclared += len(engines)
                continue
            for engine in engines:
                # A CELL MARK IS NOT A MEASUREMENT (DECISIONS #111). A
                # censored engine now keeps its row and prints `>2h`, `OOM`
                # or `err` in the cells, so "the metric is not None" stopped
                # meaning "the campaign measured this". A stat with no median
                # is a statement about a RUN; the absence it declares is what
                # accounts for it, exactly as before the row was printed.
                got = [e for e in t.get("entries", [])
                       if str(e["backend"]) == engine
                       and isinstance((e.get("metrics") or {}).get(op), dict)
                       and (e["metrics"][op] or {}).get("median") is not None]
                if got:
                    present += 1
                elif engine in whole_row or (engine, op) in per_cell:
                    declared += 1
                elif NOT_MEASURED_BY_ENGINE.get((tid, op, engine)) or \
                        NOT_MEASURED_BY_ENGINE.get((tid, op, "*")):
                    declared += 1
                else:
                    print(f"  BLANK  {tid}: {engine} has no {op!r} and nothing "
                          f"declares why")
                    undeclared += 1
                    bad += 1

    print("\ncoverage A2: every measured field is printed or declared "
          "not-printed, with a reason")
    frozen = _frozen_path()
    if not frozen.exists():
        print(f"  (no {frozen.name}; field coverage skipped)")
        return bad, (expected, present, declared, undeclared)
    rows = list(_csv.DictReader(frozen.open()))
    sys.path.insert(0, str(HERE))
    import export_web as EW

    def _fields(spec):
        """Field names out of a (field, label) spec; a field can be a tuple of
        fallbacks (the last-point query reads unbounded, then windowed)."""
        out = set()
        for field, _label in spec:
            for f in (field if isinstance(field, tuple) else (field,)):
                if isinstance(f, str):
                    out.add(f)
        return out

    # THE UNION PER LANE, not per table. One lane feeds more than one table --
    # the document lane feeds both document tables, the graph lane feeds the
    # transactional and the analytical one -- so a field printed on either is
    # printed. The columns come from export_web._metrics_for, the function the
    # exporter builds each table's columns with, so a column it adds beside the
    # lane's list (the per-phase memory column, the matched-recall headline, a
    # cold column) is a printed field here too.
    lanes = {}
    saved_rows, EW._FROZEN_ROWS = EW._FROZEN_ROWS, rows
    try:
        for tid in tables:
            lane = (EW._TABLE_LANE.get(tid) or (None,))[0]
            if not lane:
                # No lane feeds it: the durability table re-reads the write
                # lanes' rows, and the multi-model table reads the other
                # tables. Neither has a field of its own to have forgotten;
                # said rather than skipped silently.
                print(f"  -      {tid}: no lane of its own ({_derived_kind(tables[tid])}); nothing to cover")
                continue
            key = tid if tid in EW.LANES else lane
            spec = EW.LANES.get(key) or {"metrics": []}
            lanes.setdefault(lane, set()).update(
                _fields(EW._metrics_for(key, spec, spec.get("lane_source", key))))
    finally:
        EW._FROZEN_ROWS = saved_rows
    for lane, printed in sorted(lanes.items()):
        missing = []
        for field in sorted(_measured_fields(rows, lane)):
            if field in printed:
                continue
            if _not_printed_reason(field):
                continue
            missing.append(field)
        if missing:
            print(f"  UNCOVERED {lane}: {len(missing)} measured field(s) are "
                  f"neither a column nor declared: {', '.join(missing)}")
            bad += len(missing)
        else:
            print(f"  ok     {lane}: every measured field printed or declared")
    return bad, (expected, present, declared, undeclared)


def _check_lane_roster(payload):
    """A3, the roster: every backend runner.LANES registers for a lane is on
    each table the lane feeds, as a row or a declared absence.
    Returns (registrations checked, bad)."""
    import runner as RN
    import export_web as EW
    tables = {t["id"]: t for t in payload.get("tables", [])}
    checked = bad = 0
    for tid, (lane, _wl) in sorted(EW._TABLE_LANE.items()):
        t = tables.get(tid)
        if t is None:
            if _ONLY_LANES and (lane not in _ONLY_LANES
                                or not _lane_has_rows(lane, _wl)):
                # A LANDING SCOPED TO ONE LANE CARRIES ONE LANE'S TABLES. This
                # roster check exists so a registered arm cannot vanish from a
                # table silently, and it reads the RUNNER's lanes rather than
                # the payload's rows precisely so an absent table is loud. Under
                # BENCH_ONLY_LANES the absence is the instruction, not the
                # defect: eight tables on an e2-only landing, every one of them
                # a lane nobody was publishing.
                #
                # The scope is CUMULATIVE, so "in scope" does not imply "has
                # rows": a lane can be in scope because a later landing will
                # add it. A lane with no rows at this pin has not been
                # measured yet, the payload declares it pending, and that is
                # not a roster finding either.
                continue
            print(f"  MISS    {tid}: the payload has no such table")
            bad += 1
            continue
        registered = list(RN.LANES[lane][1])
        keyed = {}
        for e in t.get("entries", []):
            key = e.get("backend_key")
            if not key:
                # No stamp, no mechanism: the label would have to be parsed.
                print(f"  UNKEYED {tid}: row {e.get('backend')!r} carries no "
                      f"backend_key, so the roster cannot be held against it")
                bad += 1
                continue
            keyed.setdefault(str(key), []).append(e)
        absent = {str(a.get("backend")) for a in (t.get("declared_absences") or [])
                  if not a.get("column")}
        for key in registered:
            # An arm that runs one workload of its lane only (runner.ARM_RUNS) is not owed
            # on the other workload's table: not a row, not a declared absence.
            if not RN.arm_runs(lane, _wl, key):
                continue
            checked += 1
            label = EW.display_name(key)
            if key in keyed:
                continue
            if key in EW.OFF_PAGE_ARMS:
                print(f"  off-page {label} [{key}] on {tid}: {EW.OFF_PAGE_ARMS[key]}")
                continue
            if label in absent or EW.engine_family(label) in absent:
                print(f"  declared {label} [{key}] on {tid}: no row, absence declared")
                continue
            print(f"  MISSING {label} [{key}] on {tid}: registered for lane {lane}, "
                  f"no row and no declaration")
            bad += 1
        for key in sorted(set(keyed) - set(registered)):
            print(f"  STRAY   {EW.display_name(key)} [{key}] on {tid}: a row from a "
                  f"backend runner.LANES does not register for lane {lane}")
            bad += 1
    return checked, bad




# --------------------------------------------------------------------------
# CONDITION SENTENCES: every number under every table has a source
#
# A condition sentence under a table is the one surface a cell's pin does not
# cover, so each number in one needs a source:
#
#   - The exporter records which sentences a GENERATOR produced, with the
#     strings the generator inserted (payload["condition_provenance"]).
#     Every numeric token in a generated sentence must be one of those strings
#     or a non-measurement token (CONDITION_ALLOWED), so a generator that
#     types a number beside the ones it computes fails here.
#   - A sentence that is not generated must be REGISTERED in
#     export_web.OCT_PROSE for that table, and each number it carries must sit
#     inside one of that entry's pins, which are evaluated against the page
#     cells and the frozen rows. Anything else is refused.
#
# The rule in one sentence: a number in a condition sentence is either
# inserted by a registered generator, matched by a pin the gate evaluates
# against the rows, or one of the listed non-measurement tokens; and the
# sentence itself must come from a registered generator or the exporter's
# prose registry.
CONDITION_TOKEN = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")

# Non-measurement tokens, each with the reason it is not a claim about a row.
CONDITION_ALLOWED = [
    (r"#\d+[a-z]?\b", "a decision or issue number"),
    (r"\b\d{4}-\d{2}-\d{2}\b", "a date"),
    (r"\b\d+\.\d+\.\d+(?:-dev)?\b", "a release version"),
    (r"\b\d+\.x\b", "a major version line"),
    (r"(?<![\w.])(?=[0-9a-f]*[a-f])[0-9a-f]{7,12}\b", "an engine commit id"),
    (r"\bQ\d+\b", "a TPC-H query number"),
    (r"\b[EL]\d\b", "an experiment or lane name (E2, L4)"),
    (r"\bSF\d+(?:\.\d+)?\b", "a TPC-H scale factor"),
    (r"\bF\d+\b", "a BUGS entry"),
    (r"\b\d+(?:\.\d+)?[kM]\b", "a tier name (10k, 1M, 9.99M)"),
    (r"\b\d-hop\b", "a traversal depth in a column name"),
    (r"\bp(?:50|95|99)\b", "a percentile name"),
    (r"@10\b", "recall@10"),
    (r"\b(?:int|fp)(?:8|16|32)\b", "a precision name"),
    (r"\b\d+h\b", "an hour window in a query name (12h aggregate)"),
    (r"\bv\d+\b", "an API path version"),
    (r"\bsha256\b", "the digest algorithm"),
    (r"\bNeo4j\b", "an engine name"),
    (r"\bvec0\b", "sqlite-vec's virtual-table module name"),
    (r"\b[A-Za-z_]+=\d+\b", "a configuration assignment (txWalFlush=0)"),
    (r"\bcpuset \d+(?:-\d+)?\b", "the cpuset, checked by the setup section"),
    (r"\bTPC-[CH]\b", "a benchmark name"),
    (r"\b(?:PostgreSQL|Cypher|SurrealDB|ArangoDB|MongoDB|Milvus|Qdrant|Elasticsearch|DuckDB|"
     r"QuestDB|TimescaleDB|LadybugDB|Chroma|LanceDB|pgvector|core|SDK|server) \d+(?:\.\d+)*\b",
     "an engine version named in prose"),
]

# Literal facts that are neither a row nor a lane constant, each with why.
CONDITION_EXEMPT = [
    (r"preallocates in 256 MiB steps", "Neo4j's documented transaction-log rotation size"),
]


def _spans(patterns, text):
    out = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.M):
            out.append(m.span())
    return out


def _covered(span, spans):
    s, e = span
    return any(a <= s and e <= b for a, b in spans)


def _pin_check(pid, pattern, fn, kind, text, P, rows):
    """Evaluate one pin against one sentence. Returns (spans it accounts for,
    finding or None). A regex that does not match its own sentence is a
    broken pin, which is a finding."""
    ms = list(re.finditer(pattern, text))
    if not ms:
        return [], None
    spans = [m.span(1) for m in ms]
    try:
        want = float(fn(P, rows))
    except (KeyError, ZeroDivisionError, TypeError, ValueError, IndexError,
            FileNotFoundError, AttributeError, ImportError) as exc:
        return spans, f"STALE  {pid}: the pin cannot be evaluated ({exc!r})"
    for m in ms:
        raw = m.group(1)
        try:
            printed = float(raw.replace(",", ""))
        except ValueError:
            return spans, f"REGEX  {pid}: captured {raw!r}, not a number"
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if abs(printed - want) > 0.5 * 10 ** -decimals + 1e-9:
            return spans, f"DIFFER {pid}: sentence says {raw}, the rows/cells say {want:.6g}"
    return spans, None


def _check_conditions(payload, rows):
    """Every condition sentence under every table (and the page's global
    ones) has a source for each number it carries, and comes from a generator
    or the registry. Returns bad count."""
    import export_web as EW
    generated = {}
    for g in (payload.get("condition_provenance") or {}).get("generated", []):
        generated.setdefault(g["text"], set()).update(g.get("values") or [])
    scale_strings = sorted({str(x) for t in payload.get("tables", []) for e in t.get("entries", [])
                            for x in (e.get("scale"), e.get("scale_label")) if x}, key=len, reverse=True)
    allowed_pats = [p for p, _ in CONDITION_ALLOWED] + [p for p, _ in CONDITION_EXEMPT] + [re.escape(s) for s in scale_strings]
    bad = 0
    groups = [("GLOBAL", payload.get("conditions") or [])]
    groups += [(t["id"], t.get("conditions") or []) for t in payload.get("tables", [])]
    for tid, conds in groups:
        registry = EW._oct_entries(tid)
        n_gen = n_reg = 0
        findings = []
        for text in conds:
            tokens = [m.span() for m in CONDITION_TOKEN.finditer(text)]
            spans = _spans(allowed_pats, text)
            if text in generated:
                n_gen += 1
                for v in generated[text]:
                    if v:
                        spans += [(m.start(), m.end()) for m in re.finditer(re.escape(v), text)]
                source = "generated"
            elif text in registry:
                n_reg += 1
                for pin in registry[text]:
                    pat, fn, kind = pin[0], pin[1], (pin[2] if len(pin) > 2 else "cell")
                    got, finding = _pin_check(f"{tid}:{pat}", pat, fn, kind, text, P=_PAGE, rows=rows)
                    if not got:
                        findings.append(f"REGEX  {tid}: a registered pin /{pat}/ matches nothing in its own sentence")
                    spans += got
                    if finding:
                        findings.append(finding)
                source = "registered"
            else:
                findings.append(f"UNREGISTERED {tid}: a sentence that is neither generated nor in OCT_PROSE: {text[:90]!r}")
                continue
            loose = [text[s:e] for s, e in tokens if not _covered((s, e), spans)]
            if loose:
                findings.append(f"UNPINNED {tid} ({source}): {loose} in {text[:100]!r}")
        print(f"  {tid:<10} {n_gen} generated, {n_reg} registered")
        for f in findings:
            print(f"    {f}")
        bad += len(findings)
    return bad


def _check_override_disclosures(payload, rows=None):
    """A table that shows an arm running a PROTOCOL section 7 override prints a
    sentence that says so (override_registry.py, CAMPAIGN section 7 row 21).

    The exporter appends the sentence from the registry; this holds the payload
    to the registry's own `says` patterns, so a refactor that stops calling the
    generator, or a generator reworded until it no longer names the setting,
    fails here instead of publishing a table that hides what its engine ran
    with. The row-side half (the engine's own read-back on every row) is
    fairness_check F15. Returns bad count."""
    import export_web as EW
    import override_registry as OV
    tables = [t for t in payload.get("tables", []) if t.get("instrument") == OV.INSTRUMENT]
    lane_of = lambda tid: (EW._TABLE_LANE.get(tid) or (None,))[0]   # noqa: E731
    found = OV.sentence_findings(tables, lane_of, rows)
    for f in found:
        print(f"    {f}")
    owed = sum(1 for t in tables for _ in OV.applicable(
        lane_of(t.get("id")), [e.get("backend_key") for e in t.get("entries") or []], rows))
    print(f"  {len(tables)} table(s), {owed} override sentence(s) owed from their entries")
    return len(found)


def _check_jvm_defaults_disclosure(payload):
    """A table that prints the image-defaults ArcadeDB row says what that row runs (CAMPAIGN
    section 7 row 69): the sentence export_web generates from the cells' recorded JVM flags,
    held here to the words that make it say it (the image's own settings, the heap, the
    collector, no initial heap). A table that prints the arm and lost the sentence fails.
    Returns bad count."""
    import export_web as EW
    bad = 0
    for t in payload.get("tables", []):
        if not any(e.get("backend_key") == EW.JVM_DEFAULTS_ARM and not e.get("outcome")
                   for e in t.get("entries") or []):
            continue
        conds = [str(c) for c in (t.get("conditions") or [])]
        if any(all(re.search(p, c) for p in (r"image's own JVM settings", r"\bheap\b", r"collector",
                                              r"initial heap")) for c in conds):
            print(f"  {t['id']}: the image-defaults row is explained")
        else:
            print(f"    MISSING {t['id']}: prints the image-defaults ArcadeDB row and no sentence says what it runs")
            bad += 1
    return bad


def _check_one_list_not_comparable(payload):
    """A dense cell the freeze withheld and that ArangoDB's one-list defect
    decided (BUGS F175, DECISIONS #156: recall below the floor, 10,000 or more
    IVF lists, a release with the defect) carries the sentence that names the
    defect, and its row, where the table prints the size, is marked `n/c` with
    no number in any cell: neither its recall nor a latency may read as a
    result. Re-decided from the freeze's sidecar, as the exporter decides it.
    A pending table is not in the payload and is checked when it lands.
    Returns bad count."""
    import export_web as EW
    bad = 0
    for t in payload.get("tables", []):
        groups = EW._one_list_groups(t.get("id"))
        for (backend, scale), items in sorted(groups.items()):
            want = EW._one_list_note(backend, scale, items)
            if want not in (t.get("conditions") or []):
                print(f"    MISSING {t['id']}: {backend} at {scale} ran on a release with the "
                      f"one-list defect and no sentence says so")
                bad += 1
                continue
            rows_here = [e for e in t.get("entries") or []
                         if str(e.get("backend_key")) == backend and str(e.get("scale")) == scale]
            numbered = [e for e in rows_here
                        if any(isinstance(v, dict) and v.get("median") is not None
                               for v in (e.get("metrics") or {}).values())]
            if numbered:
                print(f"    NUMBERED {t['id']}: {backend} at {scale} prints a number the defect decided")
                bad += 1
            elif rows_here and not all(e.get("outcome") == "not comparable" for e in rows_here):
                print(f"    UNMARKED {t['id']}: {backend} at {scale} has a row not marked not comparable")
                bad += 1
            else:
                print(f"  {t['id']}: {backend} at {scale} disclosed"
                      + (", row marked n/c" if rows_here else ", size not on the table"))
    return bad


# Wording the dense table's ArangoDB sentence must never carry. Neither is what
# the harness does: arango_common.ivf_params builds round(4 * sqrt(n)) lists,
# and the dense lane calibrates nProbe (calibrate_nprobe) rather than probing
# an eighth of the lists.
_ARANGO_IVF_OLD = ("about the square root of the corpus", "an eighth of the lists")


def _check_arango_ivf_sentence(payload, rows):
    """The dense table's ArangoDB sentence says what the harness does
    with its IVF index and takes its numbers from the rows: it never carries
    the old wording, it is the sentence the exporter derives from the same
    rows, and, independently of the exporter, every "N lists at <size>" in it
    is both what the rows record and what arango_common.ivf_params builds
    for that size's vector count. A pending table is not in the payload and is checked when it lands.
    Returns bad count."""
    import export_web as EW
    import arango_common
    bad = 0
    for t in payload.get("tables", []):
        if t.get("id") != "l3d":
            continue
        conds = t.get("conditions") or []
        for c in conds:
            for old in _ARANGO_IVF_OLD:
                if old in c:
                    print(f"    WRONG {t['id']}: a sentence says {old!r}; the harness builds "
                          f"round(4 * sqrt(n)) lists and calibrates the probe count")
                    bad += 1
        shown = [e for e in t.get("entries") or []
                 if str(e.get("backend_key") or "").startswith("arangodb") and not e.get("outcome")]
        want = EW._arango_ivf_note(t, rows)
        if want is None:
            if shown:
                print(f"    MISSING {t['id']}: ArangoDB has a row and no IVF operating point is said")
                bad += 1
            continue
        if want not in conds:
            print(f"    MISSING {t['id']}: the ArangoDB IVF sentence is not the one its rows give")
            bad += 1
            continue
        before = bad
        for m in re.finditer(r"([\d,]+) lists at ([^.;,]+? vectors)", want):
            n_lists, size = int(m.group(1).replace(",", "")), m.group(2)
            rs = [r for r in rows
                  if r.get("lane") == "l3d" and str(r.get("backend") or "").startswith("arangodb")
                  and str(r.get("instrument") or "") == PUBLISH_INSTRUMENT
                  and EW.scale_label("l3d", str(r.get("scale"))) == size]
            ok = bool(rs) and all(
                int(float(r["ivf_nlists"])) == n_lists
                == arango_common.ivf_params(int(float(r["n_docs"])))[0] for r in rs)
            if not ok:
                print(f"    DIFFER {t['id']}: the sentence says {n_lists:,} lists at {size}; "
                      f"the rows or ivf_params say otherwise")
                bad += 1
        if bad == before:
            print(f"  {t['id']}: the ArangoDB IVF sentence matches its rows and the harness")
    return bad


def _check_off_page_names(payload):
    """No sentence on the page names an off-page arm. OFF_PAGE_ARMS are never
    printed as rows, so a condition that names one describes something the
    reader cannot find on the table: the documents index note listed
    "PostgreSQL (tuned)" among the engines that build an index.
    Returns bad count."""
    import export_web as EW
    names = {EW.display_name(k): k for k in EW.OFF_PAGE_ARMS}
    groups = [("GLOBAL", payload.get("conditions") or [])]
    groups += [(t["id"], t.get("conditions") or []) for t in payload.get("tables", [])]
    bad = 0
    for tid, conds in groups:
        for text in conds:
            for name, key in names.items():
                if name and name in str(text):
                    print(f"    OFF-PAGE {tid}: names {name!r} [{key}], which the page does not "
                          f"print: {str(text)[:100]!r}")
                    bad += 1
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
