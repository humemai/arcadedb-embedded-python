#!/usr/bin/env python3
"""Third gate: the published project page must agree with its own sources.

`provenance_check` asks whether a cell traces to a run; `fairness_check`
whether the arms were matched. This asks whether the page is consistent with
itself and with the generated tables: the DEEP-10M page table against the
generated table (two generators aggregate independently, and a change to
either alone moves one artifact and not the other); every typed number in the
page prose against the page cell it describes (a typed number is a claim; the
pin makes it a checked one); the atomicity counts against the artifact; no
table losing its ArcadeDB row against the live page; the setup prose naming
the host; every disk column in gibibytes.

Until 2026-09-13 the first section compared page cells to the ICDE paper's
hand-typed prose constants through claims_check.CLAIMS; the paper was dropped
on 2026-09-11 and that section printed "9 disagree" on every run, so it is
gone. claims_check stays as a helper library (torn counts, arm selection).

Usage:
    python page_check.py [--json PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# The skeleton publish exports to its own file (export_web.OUT_NAME), so this
# gate reads the payload that was just written rather than the live one.
DEFAULT_JSON = HERE / "results" / (
    "web_benchmarks_skeleton.json" if os.environ.get("BENCH_SKELETON") == "1"
    else "web_benchmarks.json")

# SKELETON (DECISIONS #86). The laptop placeholder publish. Two sections of
# this gate compare a TYPED NUMBER against a measured cell, and against
# placeholder cells that comparison means nothing in either direction: a match
# would be luck and a mismatch would be the placeholder doing its job. So on a
# skeleton they keep their STRUCTURAL half -- every pinned sentence must still
# be present, exactly once -- and report the value as a placeholder instead of
# comparing it. The DEEP-10M cross-generator section has no tier to read at
# micro scale and says so rather than failing. Both waivers are published in
# the payload (export_web.SKELETON_WAIVERS); nothing here is silent, and
# BENCH_SKELETON is set by the skeleton publish alone.
SKELETON = os.environ.get("BENCH_SKELETON") == "1"

# The rows the atomicity counts are read from. A skeleton publishes from its
# own results file, so those counts are checked for real rather than waived.
RUNS_JSONL = HERE / "results" / os.environ.get("BENCH_RUNS_JSONL", "runs.jsonl")



# --- the page's PROSE, pinned to the paper's own tables -------------------
#
# The exporter writes TABLE CELLS, which the exporter writes straight from
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
     ("t5_dense_ts.tex", "Qdrant (fp32)", 1)),
    ("dense.chroma.cold", r"and Chroma's (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Chroma (fp32)", 1)),
    # Steady state, quoted to show the gap is ours alone. Column 2.
    ("dense.arcadedb.warm", r"ArcadeDB answers in (\d+(?:\.\d+)?) ?ms",
     ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 2)),
    ("dense.qdrant.warm", r"Qdrant moves to (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Qdrant (fp32)", 2)),
    ("dense.chroma.warm", r"and Chroma to (\d+(?:\.\d+)?)",
     ("t5_dense_ts.tex", "Chroma (fp32)", 2)),
    # Row labels carry the precision: a bare "Qdrant" prefix-matched "Qdrant
    # (int8)" (1.13) while the figure divides by Qdrant (fp32) (1.26).
    # Recall, column 4, printed as a percentage (scale 100). These decide WHICH
    # comparator the dense bar divides by, so they are claims, not colour.
    ("dense.chroma.recall", r"Chroma\s+returns (\d+(?:\.\d+)?)% of the true neighbours",
     ("t5_dense_ts.tex", "Chroma (fp32)", 4), 100.0),
    ("dense.arcadedb.recall", r"where ArcadeDB returns (\d+(?:\.\d+)?)%",
     ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 4), 100.0),
    # The steady-state ratio, Qdrant warm over ArcadeDB warm. A "ratio" ref is
    # two cells; the 2026-08 prose said 1.4x from the 26.8.1 overlay and
    # nothing checked it (it is 1.2x on 8d6af9475).
    ("dense.steady.ratio", r"a (\d+(?:\.\d+)?)x win, with the comparators",
     ("ratio", ("t5_dense_ts.tex", "Qdrant (fp32)", 2), ("t5_dense_ts.tex", "ArcadeDB (emb, fp32)", 2))),
    # PAGE-DERIVED PINS. These sentences quote tables that exist only on the
    # page (pycost, l2olap's view gain, l3smp's gains), so the reference is a
    # function of the exported JSON rather than a paper cell. 2026-09-07: five
    # of them were stale on the live page after the re-pin (1.28x/1.63x/13.8x/
    # 6.5x/2.4x/1.18x/1.13x/nine times) because nothing checked them.
    ("pycost.vector.ratio", r"a vector search costs (\d+(?:\.\d+)?)x",
     lambda P: P("pycost", "Python", "vector search", "vs Java")),
    ("pycost.scan.ratio", r"a 100k-document scan (\d+(?:\.\d+)?)x",
     lambda P: P("pycost", "Python, to_columns", "100k-document scan", "vs Java")),
    ("pycost.rows_vs_columns", r"record objects is (\d+(?:\.\d+)?)x slower",
     lambda P: P("pycost", "Python, to_list", "100k-document scan", "time ms") / P("pycost", "Python, to_columns", "100k-document scan", "time ms")),
    ("l2olap.view.top_degree", r"[Tt]he view is worth (\d+(?:\.\d+)?)x on top degree",
     lambda P: P("l2olap", "ArcadeDB (embedded)", "sf10", "most friends p50 ms") / P("l2olap", "ArcadeDB (embedded, GAV)", "sf10", "most friends p50 ms")),
    ("l2olap.view.other_two", r"about (\d+(?:\.\d+)?)x on the other two",
     lambda P: (P("l2olap", "ArcadeDB (embedded)", "sf10", "average friend age p50 ms") / P("l2olap", "ArcadeDB (embedded, GAV)", "sf10", "average friend age p50 ms")
                + P("l2olap", "ArcadeDB (embedded)", "sf10", "friends in same city p50 ms") / P("l2olap", "ArcadeDB (embedded, GAV)", "sf10", "friends in same city p50 ms")) / 2),
    ("l3smp.max_gain.small", r"largest gain by any engine is (\d+(?:\.\d+)?)x at a million",
     lambda P: P.max("l3s", "small", "gain")),
    ("l3smp.max_gain.medium", r"and (\d+(?:\.\d+)?)x at 8\.84 million",
     lambda P: P.max("l3s", "medium", "gain")),
    ("l3smp.max_gain.medium.pct", r"no engine gains more than (\d+)%",
     lambda P: round((P.max("l3s", "medium", "gain") - 1) * 100)),
    ("e2atom.trials", r"interrupted mid-way, (\d+) trials per run",
     lambda P: P("e2atom", "ArcadeDB (one transaction)", "e2", "trials")),
    ("e2atom.composed.torn", r"left torn in (\d+) of 40 trials",
     lambda P: P("e2atom", "Qdrant + Neo4j (no shared transaction)", "e2", "torn results")),
    # Every single-engine label the caption names is under this max, so naming
    # one more engine without adding it here is a page_check failure by design
    # (the regex anchors on the last name in the list).
    ("e2atom.single_engines.torn", r"PostgreSQL \+ pgvector \+ AGE, in (\d+) of 40",
     lambda P: max(P("e2atom", lbl, "e2", "torn results") for lbl in (
         "ArcadeDB (one transaction)", "ArcadeDB (server, one transaction)",
         "SurrealDB (embedded)", "SurrealDB (server)", "Neo4j (vector index)",
         "PostgreSQL + pgvector + AGE"))),
    ("lifecycle.cold_process", r"reaches its first database call in about (\d+(?:\.\d+)?) s",
     lambda P: round(P("lifecycle", "Empty database (embedded)", "lc10k", "cold process ms") / 1000, 2)),
    ("lifecycle.clean_session", r"opening and closing an empty database costs about (\d+(?:\.\d+)?) ms",
     lambda P: P("lifecycle", "Empty database (embedded)", "lc10k", "open and close ms")),
    ("dense.second_pass", r"ArcadeDB alone gains about (\d+(?:\.\d+)?)x on a second pass",
     lambda P: P("l3d", "ArcadeDB (embedded, fp32)", "deep10m", "cold p50 ms") / P("l3d", "ArcadeDB (embedded, fp32)", "deep10m", "warm p50 ms")),
]


# THE PREVIEW PAGE HAS ITS OWN PINS, and starts with none.
#
# Every entry in PROSE exists because the LIVE page typed that number into a
# sentence; "absent is a failure" is right for that page and wrong for a page
# built from nothing (DECISIONS #83, #86: the October page starts empty and
# fills in). Checking the live page's sentences against the preview would fail
# twenty pins for claims the preview has never made, which is noise, not a
# gate.
#
# So the preview is pinned to its OWN prose. It is empty while the October
# page keeps its numbers in table cells and out of sentences; the moment a
# preview sentence types a number, its pin goes here, in the same commit, and
# this gate covers it exactly as it covers the live page.
PREVIEW_PROSE = []


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

# repos are siblings, same assumption refresh_web_page.py makes. --preview
# swaps both the prose file and the "live" payload for the preview's own
# (/projects/arcadedb/next, DECISIONS #83), so the preview is checked against
# itself and never against the live page.
# BENCH_SITE_DIR wins, because the repos are only siblings in the layout this
# line assumes and a worktree is not in it: checked out at /home/tk/wt-october,
# this resolved to /home/tk/humem.ai, the prose file was "not found", and the
# atomicity check then died on the same missing path with a traceback instead
# of a finding. refresh_web_page exports the checkout it is publishing to.
_SITE = Path(os.environ.get("BENCH_SITE_DIR")
             or Path(__file__).resolve().parents[2].parent / "humem.ai")
PAGE_TS = _SITE / "src" / "lib" / "projects" / "items" / "arcadedb.ts"
PREVIEW_TS = _SITE / "src" / "lib" / "projects" / "items" / "arcadedb-next.ts"
PREVIEW_JSON = _SITE / "src" / "data" / "arcadedb-benchmarks-next.json"


# The page's DEEP-10M rows against T5's, cell for cell.
#
# Both sides read results/dense_mp5_2681, but through two separate
# implementations: export_web._dense_overlay_entries for the page and
# make_paper_tables for the paper. That is the "two generators aggregate
# independently" hazard this file's docstring opens with, now applied to the
# tier that was withheld until 2026-08-13 and so never had a pin at all.
#
# page label -> (T5 row label, cold col, warm col, recall col)
# Both label sets now carry the stored precision, so both sides of this map
# moved at once. That is the case a mapping like this is worst at: rename one
# side and every row goes ABSENT, which reads as "the tier vanished" rather
# than "the label changed" (it happened on 2026-08-11 to all nine MAPPING
# cells). Keeping the two columns literally side by side is the cheap defence.
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
        if SKELETON:
            print("  skeleton: no ten-million tier at micro scale, so the "
                  "cross-generator DEEP-10M comparison does not apply")
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
    # DECISIONS #56: when the 10M rows come from the pinned multipass re-run,
    # the table must say the fp32 build cache was pinned to the corpus. A
    # disclosure that can silently drop off the page is not a disclosure.
    import export_web as _EW
    if _EW._dense_overlay_is_pinned():
        conds = " ".join(next((t.get("conditions", []) for t in payload.get("tables", [])
                               if t["id"] == "l3d"), []))
        if "graphBuildCacheSize pinned to the corpus size" in conds:
            checked += 1
            print("  #56 disclosure present on the dense table")
        else:
            print("  MISSING the #56 build-cache disclosure on the dense table while the pinned overlay is in use")
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
    pins = PREVIEW_PROSE if page_ts == PREVIEW_TS else PROSE
    if not pins:
        print("  no pins for this page yet (it types no numbers into prose)")
    for entry in pins:
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
        if SKELETON:
            # Structure checked (the sentence is here, once); the number is a
            # placeholder and is not compared. See SKELETON above.
            print(f"  placeholder {pid:24s} page={hits[0]} (skeleton: not compared)")
            continue
        if callable(ref):
            try:
                table_val = ref(_PAGE)
            except (KeyError, ZeroDivisionError, TypeError) as exc:
                print(f"  STALE  {pid:24s} page cell missing: {exc}")
                bad += 1
                continue
        elif ref[0] == "ratio":
            _a, _b = C.cell(*ref[1]), C.cell(*ref[2])
            table_val = (_a / _b) if (_a and _b) else None
        else:
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
              f"page={printed:<11.6g} paper={want:<13.6g} {'(page)' if callable(ref) else ref[1]}")
        if not ok:
            bad += 1
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
# torn-count check enumerates these rather than the three it began with, so a
# comparator that joins (ArangoDB, qDV) is checked the day it lands.
E2_SINGLE_ENGINE = ("arcadedb_e2", "arcadedb_e2_server", "surrealdb_e2",
                    "surrealdb_e2_server", "neo4j_e2", "pg_age_e2", "arangodb_e2",
                    "mongodb_e2")
E2_OPTIONAL = ("arangodb_e2", "mongodb_e2")
E2_BACKENDS = E2_SINGLE_ENGINE + ("composed_qdrant_neo4j",)


def _check_page_atomicity(page_path):
    """The page's atomicity counts, against the artifact rather than the paper.

    Added because I put "200 of 200" on a public page and pinned it to nothing,
    on the same day as an audit whose whole subject was unpinned numbers. The
    other PROSE entries compare the page to a TABLE cell; these counts are in
    no table, so they need the artifact directly -- the same rows
    claims_check's e2_atomicity() reads.

    A count is exactly the kind of number that rots quietly: re-run the lane
    with a different E2_TRIALS and the page still reads 200, still sounds
    authoritative, and nothing anywhere disagrees.
    """
    import json as _json
    import re as _re
    if not Path(page_path).exists():
        # A FINDING, not a crash. The prose check above already reports the
        # missing file; dying here hid it behind a traceback.
        print(f"  no page prose at {page_path}; atomicity counts unchecked")
        return 0, 1
    text = open(page_path, encoding="utf-8").read()
    if not Path(RUNS_JSONL).exists():
        # Same rule as the missing prose file above: report it. This path ran
        # into a traceback whenever the results log was named something other
        # than runs.jsonl and BENCH_RUNS_JSONL was not exported with it.
        print(f"  no results log at {RUNS_JSONL}; atomicity counts unchecked")
        return 0, 1
    totals = {}
    for backend in E2_BACKENDS:
        n_trials = n_torn = 0
        seen = False
        # NEWEST ROW PER CANONICAL KEY, the same rule every table applies.
        # runs.jsonl is append-only and a campaign file can be merged more than
        # once (2026-09-06: three merges of one file tripled these counts to 600).
        _newest = {}
        with open(RUNS_JSONL) as fh:
            for line in fh:
                try:
                    _r = _json.loads(line)
                except Exception:
                    continue
                _k = (_r.get("lane"), _r.get("scale"), _r.get("n_docs"), _r.get("workload"),
                      _r.get("backend"), _r.get("gav"), _r.get("rep"))
                if _k not in _newest or str(_r.get("ts_utc", "")) > str(_newest[_k].get("ts_utc", "")):
                    _newest[_k] = _r
        if True:
            for line in (_json.dumps(_r) for _r in _newest.values()):
                if not line.strip():
                    continue
                try:
                    r = _json.loads(line)
                except ValueError:
                    continue
                if (r.get("lane") == "e2" and r.get("workload") == "atomicity"
                        and r.get("backend") == backend
                        and r.get("trials") is not None):
                    seen = True
                    n_trials += int(r.get("trials") or 0)
                    n_torn += int(r.get("torn_count") or 0)
        totals[backend] = (n_trials, n_torn) if seen else None

    checks = [
        ("page.e2.trials",
         r"interrupted (\d+) trials against each system",
         lambda: totals["arcadedb_e2"] and totals["arcadedb_e2"][0]),
        ("page.e2.composed_torn",
         r"left half-updated in all (\d+)",
         lambda: totals["composed_qdrant_neo4j"] and totals["composed_qdrant_neo4j"][1]),
    ]
    checked = bad = 0
    preview = page_path == PREVIEW_TS
    for name, rx, get in checks:
        m = _re.search(rx, text)
        want = get()
        if m is None:
            if preview:
                # A page built from nothing has not made this claim yet. When
                # it does, the branch below checks it against the artifact
                # exactly as it does for the live page.
                print(f"  n/a     {name}: the preview page does not state this count")
                continue
            print(f"  MISSING {name}: the page no longer states this count")
            bad += 1
            continue
        if want is None:
            print(f"  NODATA  {name}: page says {m.group(1)}, artifact has no "
                  f"fixed-harness rows")
            bad += 1
            continue
        checked += 1
        got = int(m.group(1))
        if got == want:
            print(f"  ok      {name:24} page={got:<6} artifact={want}")
        else:
            print(f"  DISAGREE {name:23} page={got:<6} artifact={want}")
            bad += 1
    # The single-engine arms must be ZERO torn, and zero is the one value a
    # broken read also produces, so assert the trial count alongside it.
    # An optional arm (ArangoDB until qDV lands) skips while it has no rows;
    # the required ones fail.
    for be in E2_SINGLE_ENGINE:
        t = totals[be]
        if preview and not _re.search(r"half-updated in none|in 0 of", text):
            # The preview page has not claimed anything about torn state yet.
            continue
        if t is None and be in E2_OPTIONAL:
            print(f"  skip    page.e2.{be}: not yet on the table")
        elif t is None:
            print(f"  NODATA  page.e2.{be}: no fixed-harness rows"); bad += 1
        elif t[1] != 0:
            print(f"  DISAGREE page.e2.{be}: {t[1]} torn, page says none"); bad += 1
        else:
            checked += 1
            print(f"  ok      page.e2.{be:17} 0 torn over {t[0]} trials")
    return checked, bad


LIVE_JSON = PAGE_TS.parents[3] / "data" / "arcadedb-benchmarks.json"


# Tables removed from the page on purpose, with the reason. Anything else
# that disappears against the live page is a defect and fails below.
RETIRED_TABLES = {
    "ingest": "2026-09-11: folded into load columns on the graph, TPC and "
              "cross-model tables at the user's request; lived one day",
    "l3smp": "2026-09-11: its warm columns and gain moved onto the sparse search table (l3s)",
    "l1": "2026-09-11: the synthetic 20M-order workload stays in the paper; the page shows TPC only",
    "l1olap": "2026-09-11: never rendered (BUGS F30); its queries are the synthetic set, paper only",
    "l1tpc": "2026-09-11: split by workload into docs_oltp (new-order) and docs_olap (Q1, Q6)",
}


def _check_no_arcadedb_row_lost(payload):
    """Every table that shows an ArcadeDB row on the LIVE page still shows one.

    2026-09-07: the 8d6af9475 campaign never re-ran e2, the exporter withheld
    the 08-14 ArcadeDB rows (engine_version "arcadedb-embedded" identifies no
    build, correctly), and the fresh E2 table carried only the two
    comparators. The exporter SAID so, in a line nobody reads in a 200-line
    log, and no gate failed. A published table without our own engine in it
    is not a publish, it is a deletion. Compared against the site's current
    data file, so the rule needs no list to maintain."""
    if not LIVE_JSON.exists():
        print(f"  (no live page data at {LIVE_JSON}; nothing to compare)")
        return 0, 0
    live = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
    _is_arc = lambda e: bool(e.get("is_arcadedb")) or str(e.get("backend", "")).startswith("ArcadeDB")
    live_has = {t["id"] for t in live.get("tables", []) if any(_is_arc(e) for e in t.get("entries", []))}
    fresh = {t["id"]: t for t in payload.get("tables", [])}
    checked = bad = 0
    # The FLAG is what the page shades and sorts by. A row whose label says
    # ArcadeDB but whose flag is false renders unshaded among the comparators
    # (the time-series table, 2026-09-12 to 13, after the labels were
    # capitalised and a lowercase test stopped matching). Fail on the mismatch.
    for tid, t in sorted(fresh.items()):
        for e in t.get("entries", []):
            if str(e.get("backend", "")).startswith("ArcadeDB") and not e.get("is_arcadedb"):
                print(f"  UNFLAGGED {tid}: {e.get('backend')!r} reads ArcadeDB but is_arcadedb is false")
                bad += 1
    for tid in sorted(live_has):
        if tid in RETIRED_TABLES:
            print(f"  retired table {tid}: {RETIRED_TABLES[tid]}")
            continue
        checked += 1
        t = fresh.get(tid)
        if t is None:
            print(f"  LOST   table {tid}: on the live page, not in the export")
            bad += 1
        elif not any(_is_arc(e) for e in t.get("entries", [])):
            print(f"  LOST   table {tid}: live page has ArcadeDB, export has {[e.get('backend') for e in t.get('entries', [])][:4]}")
            bad += 1
    return checked, bad


def _check_disk_units(payload):
    """Every 'disk GiB' cell must be gibibytes: mini's largest data set is
    DEEP-10M at a few dozen GiB, so a median above 200 is a megabyte value that
    skipped the divisor (2026-09-13: seven tables printed MB for a day)."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    ap.add_argument("--preview", action="store_true",
                    help="check the preview page's prose and payload instead of the live page's")
    ap.add_argument("--rows", default=None,
                    help="the frozen CSV the condition pins are evaluated against "
                         "(default: results/runs_paper.csv, or the skeleton's own file)")
    ap.add_argument("--skeleton", action="store_true",
                    help="the payload is the laptop placeholder run (DECISIONS #86): pinned "
                         "prose sentences must still be present, their values are not compared, "
                         "and the DEEP-10M cross-generator section does not apply")
    args = ap.parse_args()
    global PAGE_TS, LIVE_JSON, SKELETON
    SKELETON = SKELETON or args.skeleton
    if SKELETON:
        print("target: SKELETON (DECISIONS #86); prose values are placeholders "
              "and are checked for presence only")
    if args.preview:
        PAGE_TS, LIVE_JSON = PREVIEW_TS, PREVIEW_JSON
        print("target: PREVIEW (arcadedb-next.ts, arcadedb-benchmarks-next.json)")

    path = Path(args.json)
    if not path.exists():
        print(f"missing {path}; run export_web.py first", file=sys.stderr)
        return 2

    payload = json.loads(path.read_text(encoding="utf-8"))
    cells = _page_index(payload)

    print(f"page: {path}")
    print(f"  {len(payload['tables'])} tables, {len(cells)} published cells")
    bad = 0

    print("\nDEEP-10M tier, page table vs the generated table")
    d_checked, d_bad = _check_dense_10m(payload)

    print(f"\nprose: {PAGE_TS}")
    global _PAGE
    _PAGE = _PageCells(payload)
    p_checked, p_bad = _check_prose(PAGE_TS)
    print(f"\n{p_checked} prose numbers checked against the page cells, "
          f"{p_bad} disagree")

    print("\nE2 atomicity counts on the page, against the artifact")
    a_checked, a_bad = _check_page_atomicity(PAGE_TS)
    print(f"\n{a_checked} page count(s) checked against the artifact, "
          f"{a_bad} disagree")
    print("\nno table loses its ArcadeDB row against the live page")
    l_checked, l_bad = _check_no_arcadedb_row_lost(payload)
    print(f"\n{l_checked} table(s) checked against the live page, {l_bad} lost ArcadeDB")
    c_bad, (c_exp, c_present, c_declared, c_undeclared) = _check_coverage(payload)
    print(f"\ncoverage: {c_exp} operation-engine cell(s) expected, "
          f"{c_present} present, {c_declared} absent and declared, "
          f"{c_undeclared} absent and undeclared")
    print("\nmulti-model coverage table, cell for cell against the tables it is derived from")
    m_checked, m_bad = _check_multimodel(payload)
    print(f"\n{m_checked} coverage cell(s) re-derived, {m_bad} disagree")
    h_bad = _check_setup_prose(payload)
    print("\nevery disk column is in gibibytes")
    u_ok = _check_disk_units(payload)
    if u_ok:
        print("  no disk cell above 200 GiB")
    print("\nconditions: every sentence under every table has a source for its numbers"
          " (October: for itself)")
    import csv as _csv
    rows_path = Path(args.rows) if args.rows else HERE / "results" / (
        "runs_skeleton_laptop.csv" if SKELETON else "runs_paper.csv")
    rows = list(_csv.DictReader(rows_path.open())) if rows_path.exists() else []
    if not rows:
        print(f"  (no frozen rows at {rows_path}; row-derived pins will read as STALE)")
    k_bad = _check_conditions(payload, rows)
    print(f"\n{k_bad} condition finding(s)")
    return 1 if (bad or d_bad or p_bad or a_bad or l_bad or h_bad or c_bad
                 or m_bad or not u_ok or k_bad) else 0


# --------------------------------------------------------------------------
# COVERAGE: the query set the page owes, and the fields it measured
#
# WHY THIS EXISTS, twice over. The laptop skeleton found six tables whose
# column lists had not moved when the instrument did, so the page printed
# neither the four single-record operations, nor three of the five analytical
# queries, nor either graph analytic, nor a cold column anywhere. The fix was
# applied, and the two dense maintenance operations were missed again in the
# same pass. Attention is not a mechanism; a gate is.
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
               "triangle count p50 ms", "cold first query ms"],
    "l3d": ["cold p50 ms", "recall@10", "after insert p50 ms",
            "after delete p50 ms", "insert into index ms/vector",
            "delete from index ms/vector", "recall@10 after insert",
            "recall@10 after delete", "ingest+index total s"],
    "l3s": ["p50 ms", "recall@10", "ingest+index total s"],
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
    (r"^(rep|rc|trials|seed)$",
     "provenance: which repetition this row is and whether it exited clean"),
    (r"^(tpch_sf|n_docs|n_docs_ingested|n_lineitem|n_part|n_persons|"
     r"n_persons_in_corpus|n_persons_ingested|n_edges|n_edges_ingested|"
     r"n_points|n_products|n_rows|dim|dims|ts_chunk|ts_shards|last_window_s)$",
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
     "existed and not in the October query set (#82), which replaced it with "
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
    (r"^(client|server)_(peak|end|io|disk|cpu)_\w+$|^server_(mem_cap_g|shm_size)$|"
     r"^(peak_mib_sum|peak_owned_mib_sum|peak_shmem_mib_sum|end_anon_mib_sum|"
     r"io_read_mib_sum|io_write_mib_sum|disk_mb_sum|cpu_usec_sum|client_mem_cap|"
     r"mem_cap|client_disk_mb|client_disk_baseline_mb)$",
     "the page prints the summed peak memory and the workload's disk; these "
     "are the per-side splits those two are computed from"),
    (r"^(hnsw_M|m|k|ef_construction|ef_search|ivf_\w+|degree_param|"
     r"graph_build_cache_\w+|qps)$",
     "index parameters and their calibration: matched by effect and printed "
     "as conditions under the table, never as columns"),
    (r"^(settle_s|settle_s_lane|settle_s_adapter|engine_settle_s|gt_load_s|"
     r"recall_calc_s|query_gen_s|search_wall_s|phases_accounted_s|connect_s|"
     r"import_ms|build_close_ms|close_s|mutate_n|mutate_queries|mutate_ran)$",
     "harness bookkeeping around a timed phase: settling, loading ground "
     "truth, computing recall, and the phase accounting"),
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
    (r"^(torn_count|build_docs_per_s|ingest_pts_per_s|disk_data_mb|"
     r"peak_anon_mib_sum|build_s|ingest_s|index_s|gav_build_s)$",
     "printed under a different label by the table that owns it; listed here "
     "so a table which stops printing one still has to say so"),
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
    october = EW.multimodel_sources(tables)
    if mm is None:
        if october and payload.get("instrument") == "2026-10":
            print("  MISSING the multi-model coverage table on an October payload")
            return 0, 1
        print("  (no multi-model table; not an October payload)")
        return 0, 0
    checked = bad = 0
    want_cols = [str(t.get("title")) for t in october]
    if list(mm.get("columns") or []) != want_cols:
        print(f"  COLUMNS multimodel: {mm.get('columns')} != the October tables' titles {want_cols}")
        bad += 1
    rows = {str(e.get("backend")): e for e in mm.get("entries", [])}
    if list(rows) != list(EW.MULTIMODEL_ENGINES):
        print(f"  ROWS    multimodel: {list(rows)} != {list(EW.MULTIMODEL_ENGINES)}")
        bad += 1
    for engine in EW.MULTIMODEL_ENGINES:
        anywhere = any(EW.engine_family(e.get("backend"), e.get("is_arcadedb")) == engine
                       for t in tables for e in t.get("entries", []))
        if not anywhere:
            print(f"  ROSTER  multimodel: {engine} is on no table in the payload")
            bad += 1
        e = rows.get(engine)
        if not e:
            continue
        for t in october:
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
                got = [e for e in t.get("entries", [])
                       if str(e["backend"]) == engine
                       and (e.get("metrics") or {}).get(op) is not None]
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
    frozen = HERE / "results" / (
        "runs_skeleton_laptop.csv" if SKELETON else "runs_paper.csv")
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
    # printed. Keyed on the table id first and the lane second, because that
    # is how OCT_TABLE_METRICS is keyed (l2olap has its own list; the two
    # document tables share the lane's).
    lanes = {}
    for tid in tables:
        lane = (EW._TABLE_LANE.get(tid) or (None,))[0]
        if not lane:
            # No lane feeds it: the durability table re-reads the write
            # lanes' rows, and the multi-model table reads the other tables.
            # Neither has a field of its own to have forgotten; said rather
            # than skipped silently.
            print(f"  -      {tid}: no lane of its own ({_derived_kind(tables[tid])}); nothing to cover")
            continue
        spec = (EW.OCT_TABLE_METRICS.get(tid) or EW.OCT_TABLE_METRICS.get(lane)
                or (EW.LANES.get(tid) or EW.LANES.get(lane) or {}).get("metrics") or [])
        lanes.setdefault(lane, set()).update(_fields(spec))
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




# --------------------------------------------------------------------------
# CONDITION SENTENCES: every number under every table has a source
#
# BUGS F52 (2026-09-16): a condition sentence on every October table named
# every engine as one "with no setting to relax". Reading all 74 distinct
# sentences on the preview found more of the class: a PostgreSQL memory split
# typed in August under a cell that had since moved, a "three questions"
# sentence under a five-query table, a 2.0 s view build over a 2.058 s cell,
# two ablation results quoted as if they were rows. Cells are produced from
# the rows and pinned; the sentences under them were the one surface with
# nothing behind them. Now:
#
#   - The exporter records which sentences a GENERATOR produced, with the
#     strings the generator inserted (payload["condition_provenance"]).
#     Every numeric token in a generated sentence must be one of those strings
#     or a non-measurement token (CONDITION_ALLOWED), so a generator that
#     types a number beside the ones it computes fails here.
#   - Under the 2026-10 instrument (table["instrument"]) a sentence that is
#     not generated must be REGISTERED in export_web.OCT_PROSE for that table,
#     and each number it carries must sit inside one of that entry's pins,
#     which are evaluated against the page cells and the frozen rows. Anything
#     else on an October table is refused: the September lists are not a
#     source for the October page.
#   - On a September table (the live page) a sentence that is not generated
#     is typed, and each number in it must sit inside a pin from
#     SEPT_CONDITION_PINS, a CONDITION_ALLOWED token, or a SEPT_QUOTED span
#     (text the September exporter quoted from a row before it had a
#     registry). An unaccounted number fails the publish.
#
# The rule in two sentences: a number in a condition sentence is either
# inserted by a registered generator, matched by a pin the gate evaluates
# against the rows, or one of the listed non-measurement tokens; and under the
# October instrument the sentence itself must additionally come from a
# registered generator or the exporter's October prose registry.
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
    (r"INT8 rows run this engine's default of 100,000",
     "the engine's graphBuildCacheSize default (vector-build-cache-defaults note); September only"),
]

# September-only: text the September exporter quoted from a row's own
# record (a timeout budget, an error message, a query literal) on a payload
# that carries no generated-sentence registry. An October payload registers
# these through the generator, so nothing here applies to it.
SEPT_QUOTED = [
    (r"exceeded its \d+(?:\.\d+)? hour budget", "the cell's budget, from the row's timeout record"),
    (r"exceeded its \d+(?:\.\d+)? s budget", "the query's budget, from the row"),
    (r"after \d+(?: to \d+)?(?: of \d+)? iterations(?:, reaching \d+(?: to \d+)? s)?", "the row's iteration count"),
    (r"What it reported: .*$", "the row's error text"),
    (r"`[^`]*`", "a quoted query literal"),
]


def _rows_median(rows, lane, backend, field, scale=None, workload=None):
    import statistics as _st
    vals = []
    for r in rows:
        if r.get("lane") != lane or str(r.get("backend")) != backend:
            continue
        if scale is not None and str(r.get("scale")) != scale:
            continue
        if workload is not None and r.get("workload") != workload:
            continue
        try:
            vals.append(float(r.get(field)))
        except (TypeError, ValueError):
            continue
    if not vals:
        raise KeyError((lane, backend, field, scale, workload))
    return _st.median(vals)


def _l3d_max_comparator_move(P, rows):
    """ceil of the largest |cold - warm| / warm, in percent, over the dense
    table's comparators: what "within N% of itself" claims."""
    import math
    best = 0.0
    for e in P.t["l3d"]["entries"]:
        m = e.get("metrics") or {}
        if e.get("is_arcadedb") or "cold p50 ms" not in m or "warm p50 ms" not in m:
            continue
        c, w = float(m["cold p50 ms"]["median"]), float(m["warm p50 ms"]["median"])
        best = max(best, abs(c - w) / w * 100)
    return math.ceil(best)


def _e4_meta():
    import export_web as EW
    reps = sorted(EW.E4_DIR.glob("decomp3m_*_rep*.json"))
    if not reps:
        raise KeyError("no e4 artifact")
    return json.loads(reps[0].read_text(encoding="utf-8"))["meta"]


def _most_common_n(P, rows):
    import collections as _c
    ns = _c.Counter(int(stat.get("n") or 0) for t in P.t.values() for e in t.get("entries", [])
                    for stat in (e.get("metrics") or {}).values() if isinstance(stat, dict))
    return ns.most_common(1)[0][0]


def _const(module, name):
    import importlib
    sys.path.insert(0, str(HERE))
    return getattr(importlib.import_module(module), name)


def _oltp_queries(scale):
    def fn(P, rows):
        import graph_common
        n = graph_common.SCALE_OLTP_QUERIES.get(scale)
        if n is None:
            import ldbc_snb
            n = ldbc_snb.SCALE_OLTP_QUERIES[scale]
        return n
    return fn


# (table id or "*", regex with one capture, fn(P, rows) -> number[, "const"]).
# A "const" pin is compared on a skeleton too; a row-derived one is
# presence-only there, like PROSE. A number typed on the live page that no
# entry here reaches is a finding, and the exporter on the october-instrument
# branch already dropped or generates each of those (the ablation results).
SEPT_CONDITION_PINS = [
    ("*", r"agree within (\d+)%", lambda P, rows: _const("runner", "DISK_SETTLE_TOL") * 100, "const"),
    ("GLOBAL", r"median of (\d+) repetitions", _most_common_n),
    ("l3s", r"in (\d+)-record transactions", lambda P, rows: _const("l3_sparse", "INGEST_BATCH"), "const"),
    ("l3s", r"answers ([\d,]+) queries", lambda P, rows: _const("l3d_dense", "N_QUERIES"), "const"),
    ("l3smp", r"same ([\d,]+) dev queries", lambda P, rows: _const("l3d_dense", "N_QUERIES"), "const"),
    ("l3d", r"answers ([\d,]+) queries", lambda P, rows: _const("l3d_dense", "N_QUERIES"), "const"),
    ("l3d", r"within (\d+)% of itself", _l3d_max_comparator_move),
    ("l3d", r"sealed at (\d+)%", lambda P, rows: _const("export_web", "_milvus_seal_proportion")() * 100, "const"),
    ("l3d", r"image default is (\d+)%", lambda P, rows: _const("runner", "MILVUS_IMAGE_SEAL_PROPORTION") * 100, "const"),
    ("l3d", r"in ([\d,]+)-row transactions", lambda P, rows: _const("l3d_dense", "BATCH"), "const"),
    ("l3d", r"sends (\d+)-statement", lambda P, rows: _const("l3d_dense", "SERVER_BATCH"), "const"),
    ("l3d", r"batches of ([\d,]+); LanceDB", lambda P, rows: _const("l3d_dense", "CHROMA_BATCH"), "const"),
    ("l3d", r"corpus size \(([\d,]+)\)", lambda P, rows: _const("l3d_dense", "SCALE_DOCS")["deep10m"], "const"),
    ("l2", r"SF1 \(11k people\): (\d+)", _oltp_queries("sf1"), "const"),
    ("l2", r"SF10 \(73k people\): (\d+)", _oltp_queries("sf10"), "const"),
    ("l2", r"commits up to ([\d,]+) writes", lambda P, rows: _const("l2_graph", "CRUD_OPS"), "const"),
    ("l2", r"in ([\d,]+)-record transactions", lambda P, rows: _const("l2_graph", "INGEST_BATCH"), "const"),
    ("l2olap", r"in ([\d,]+)-record transactions", lambda P, rows: _const("l2_graph", "INGEST_BATCH"), "const"),
    ("l2olap", r"took (\d+\.\d) seconds here", lambda P, rows: P("l2olap", "ArcadeDB (embedded, GAV)", "sf10", "view build s")),
    ("l2olap", r"runs every query (\d+) times", lambda P, rows: _const("graph_common", "OLAP_ITERATIONS"), "const"),
    ("l4", r"runs every query (\d+) times", lambda P, rows: _const("l4_tsbs", "QITER"), "const"),
    ("l4", r"slower, (\d+\.\d+) ms against", lambda P, rows: _rows_median(rows, "l4", "arcadedb_ts_native", "q_last_windowed_ms")),
    ("l4", r"ms against (\d+\.\d+), because", lambda P, rows: _rows_median(rows, "l4", "arcadedb_ts_native", "q_last_ms")),
    ("docs_olap", r"runs every query (\d+) times", lambda P, rows: _const("l1_tpc", "OLAP_ITER"), "const"),
    ("docs_oltp", r"runs ([\d,]+) new-order", lambda P, rows: _const("l1_tpc", "OLTP_OPS"), "const"),
    ("docs_oltp", r"in ([\d,]+)-row batches", lambda P, rows: _const("l1_tpc", "BATCH"), "const"),
    ("docs_olap", r"in ([\d,]+)-row batches", lambda P, rows: _const("l1_tpc", "BATCH"), "const"),
    ("docs_oltp", r"the (\d+\.\d+) GiB shown is", lambda P, rows: P("docs_oltp", "PostgreSQL", "tpch1", "peak memory GiB")),
    ("docs_oltp", r"is (\d+\.\d+) of Python client", lambda P, rows: _rows_median(rows, "l1tpc", "postgres", "client_peak_anon_mib", "tpch1", "oltp") / 1024),
    ("docs_oltp", r"and (\d+\.\d+) of database", lambda P, rows: _rows_median(rows, "l1tpc", "postgres", "server_peak_anon_mib", "tpch1", "oltp") / 1024),
    ("docs_olap", r"the (\d+\.\d+) GiB shown is", lambda P, rows: P("docs_olap", "PostgreSQL", "tpch1", "peak memory GiB")),
    ("docs_olap", r"is (\d+\.\d+) of Python client", lambda P, rows: _rows_median(rows, "l1tpc", "postgres", "client_peak_anon_mib", "tpch1", "oltp") / 1024),
    ("docs_olap", r"and (\d+\.\d+) of database", lambda P, rows: _rows_median(rows, "l1tpc", "postgres", "server_peak_anon_mib", "tpch1", "oltp") / 1024),
    ("e2", r"the transaction (\d+) times", lambda P, rows: _const("e2_hybrid", "OPS"), "const"),
    ("e2", r"graph_batch \(([\d,]+) records", lambda P, rows: _const("e2_hybrid", "BATCH"), "const"),
    ("lifecycle", r"\((\d+) ms at 10k", lambda P, rows: _rows_median(rows, "lifecycle", "arcadedb_embedded", "clean_session_ms", "lc10k", "vector")),
    ("lifecycle", r", (\d+) ms at 1M", lambda P, rows: _rows_median(rows, "lifecycle", "arcadedb_embedded", "clean_session_ms", "lc1m", "vector")),
    ("lifecycle", r"(\d+\.\d) s at 10M\)", lambda P, rows: _rows_median(rows, "lifecycle", "arcadedb_embedded", "clean_session_ms", "lc10m", "vector") / 1000),
    ("lifecycle", r"at 10M is (\d+\.\d) s", lambda P, rows: _rows_median(rows, "lifecycle", "arcadedb_embedded", "read_session_ms", "lc10m", "vector") / 1000),
    ("e4", r"(\d+) repetitions after", lambda P, rows: _e4_meta()["reps"]),
    ("e4", r"after (\d+) warmup", lambda P, rows: _e4_meta()["warmup"]),
    ("e4", r"memory cap (\d+)g", lambda P, rows: int(str(_e4_meta()["mem_cap"]).rstrip("g"))),
    ("e4", r"heap (\d+)g", lambda P, rows: int(str(_e4_meta()["heap"]).rstrip("g"))),
    ("pycost", r"vector search costs (\d+\.\d+)x", lambda P, rows: P("pycost", "Python", "vector search", "vs Java")),
    ("pycost", r"the scan (\d+\.\d+)x", lambda P, rows: P("pycost", "Python, to_columns", "100k-document scan", "vs Java")),
    ("pycost", r"record objects is (\d+\.\d+)x slower", lambda P, rows: P("pycost", "Python, to_list", "100k-document scan", "time ms") / P("pycost", "Python, to_columns", "100k-document scan", "time ms")),
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
    if SKELETON and kind != "const":
        return spans, None
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
    ones) has a source for each number it carries; under the October
    instrument, for the sentence itself. Returns bad count."""
    import export_web as EW
    generated = {}
    for g in (payload.get("condition_provenance") or {}).get("generated", []):
        generated.setdefault(g["text"], set()).update(g.get("values") or [])
    scale_strings = sorted({str(x) for t in payload.get("tables", []) for e in t.get("entries", [])
                            for x in (e.get("scale"), e.get("scale_label")) if x}, key=len, reverse=True)
    allowed_pats = [p for p, _ in CONDITION_ALLOWED] + [p for p, _ in CONDITION_EXEMPT] + [re.escape(s) for s in scale_strings]
    quoted_pats = [p for p, _ in SEPT_QUOTED]
    bad = 0
    groups = [("GLOBAL", payload.get("instrument"), payload.get("conditions") or [])]
    groups += [(t["id"], t.get("instrument"), t.get("conditions") or []) for t in payload.get("tables", [])]
    for tid, instrument, conds in groups:
        october = instrument == "2026-10"
        registry = EW._oct_entries(tid)
        n_gen = n_reg = n_typed = 0
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
            elif october:
                findings.append(f"UNREGISTERED {tid}: an October sentence that is neither generated nor in OCT_PROSE: {text[:90]!r}")
                continue
            else:
                n_typed += 1
                spans += _spans(quoted_pats, text)
                for pin in SEPT_CONDITION_PINS:
                    scope, pat, fn = pin[0], pin[1], pin[2]
                    kind = pin[3] if len(pin) > 3 else "cell"
                    if scope not in ("*", tid):
                        continue
                    got, finding = _pin_check(f"{tid}:{pat}", pat, fn, kind, text, P=_PAGE, rows=rows)
                    spans += got
                    if finding:
                        findings.append(finding)
                source = "typed"
            loose = [text[s:e] for s, e in tokens if not _covered((s, e), spans)]
            if loose:
                findings.append(f"UNPINNED {tid} ({source}): {loose} in {text[:100]!r}")
        label = "October" if october else "September"
        print(f"  {tid:<10} {n_gen} generated, {n_reg} registered, {n_typed} typed ({label})")
        for f in findings:
            print(f"    {f}")
        bad += len(findings)
    return bad


def _check_setup_prose(payload):
    """The page's hardware paragraph must name every host's CPU (the model
    token) and the cpuset the rows ran on; a re-pin on another machine then
    fails here until the prose is rewritten (2026-09-11)."""
    setup = payload.get("setup") or {}
    try:
        prose = PAGE_TS.read_text(encoding="utf-8")
    except Exception:
        print("  (no page prose file; setup check skipped)")
        return 0
    bad = 0
    for host, hw in (setup.get("hosts") or {}).items():
        token = hw["cpu"].split(",")[0].split()[-1]   # e.g. i9-12900HK
        if token not in prose:
            print(f"  SETUP  host {host}: CPU {token} not named in the page prose"); bad += 1
    cpuset = setup.get("cpuset")
    if cpuset and f"cpuset {cpuset}" not in prose and f"`cpuset` {cpuset}" not in prose and f"CPUs {cpuset}" not in prose:
        print(f"  SETUP  cpuset {cpuset} not named in the page prose"); bad += 1
    if not bad:
        print(f"  setup prose names the host CPU and cpuset {cpuset}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
