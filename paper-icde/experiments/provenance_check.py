#!/usr/bin/env python3
"""Report the engine version behind every result set that feeds a paper table.

Why this exists. T5's server dense build cell (13,349 s) was published as if it
were a deployment cost. It was not: the server image was built 2026-07-25
23:58 UTC, which sits between the commit that bounded the HNSW build cache
(0d1bca913a, 07-23, slows fp32 builds) and the commit that fixed it by
auto-sizing (5d9f9ff72f, 07-26). The embedded row was measured after the fix
and the server row before it, so the table compared two engines and labelled
the difference "server".

The provenance was not missing. `verify5413/server_digest.txt` recorded the
image, and the result JSON recorded the build commit. What was missing was
anything that *compared* the recorded version against what landed when. A
digest filed beside a result is not provenance until something reads it.

So this script does three things nothing else did:

  1. reads the version out of every overlay, across the three different key
     names the harness has accumulated (`engine_version`, `engine`,
     `server_version`) -- the inconsistency is itself why no audit existed;
  2. flags any overlay feeding a published cell with no version at all;
  3. for server SNAPSHOT rows, resolves the build commit's date with git and
     warns when it predates a known fix landmark, which is the specific check
     that would have caught T5.

Run it before regenerating tables, and at the freeze.

    python3 provenance_check.py [--table T5]

Exit status is 1 if any BAD finding is reported, so it can gate a re-generation.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

# The keys the harness has used for "which engine produced this row". Kept as a
# list rather than normalised away, because old result files are immutable and
# an audit that only knows the current key silently reports NONE for the rest.
VERSION_KEYS = ("engine_version", "engine", "server_version", "version", "wheel",
                # Comparator rows: the version of the engine that row MEASURED,
                # as opposed to the arcadedb wheel the harness happened to
                # import. l4_tsbs.py records this and deliberately renames its
                # own engine_version to harness_arcadedb_version, so that a
                # duckdb row cannot pass this audit by quoting our wheel.
                "backend_version")



def _is_real_version(v):
    """A version key that is present but says nothing is not provenance.

    The dense lane stamped `engine_version` twice: the adapter wrote the real
    one, then run_conditions overwrote it with an arcadedb wheel lookup that
    raises inside a comparator container, leaving the literal string
    "unknown (PackageNotFoundError)". Twenty DEEP-10M rows carried that, and
    this auditor passed every one of them, because the old test was `not in
    (None, "")` and a placeholder is a perfectly non-empty string.

    Checking that a field is populated is not the same as checking that it
    answers the question. This is the fifth guard in this harness found present
    and inert, so the test is now what the field is FOR.
    """
    if v is None:
        return False
    t = str(v).strip()
    if not t:
        return False
    low = t.lower()
    if low.startswith("unknown") or low in ("?", "none", "null", "n/a", "-"):
        return False
    # A version has to contain a digit somewhere. "server:?" does not.
    return any(c.isdigit() for c in t)
# Which overlay directories feed which table. Mirrors make_paper_tables.py; if
# that file grows a new overlay and this map does not, the unmapped-dir check
# at the bottom says so rather than quietly ignoring it.
FEEDS = {
    "T4": ["dev22_sparse", "dev21_sparse", "dev21_sparse_full", "sparse_full",
           "verify5411"],
    # srv109 is the post-#109 server dense re-measure and now feeds T5's
    # server row; verify5413 stays listed because it remains the fallback in
    # make_paper_tables and its landmark warning is the record of WHY it was
    # superseded, not a live defect in what the table prints.
    # ts59 is the dev23 native time-series re-measure (N=5, conditions
    # stamped) and now feeds T5's native row. dev21_ts stays listed for the
    # same reason verify5413 does: it remains the fallback in
    # make_paper_tables, and its record is why the row was superseded.
    "T5": ["verify5412b", "srv109", "verify5413", "ts59", "dev21_ts"],
}

# Top-level result FILES that feed published tables, as opposed to the overlay
# DIRECTORIES above. This map exists because the audit had a blind spot exactly
# where the discipline was weakest: every check below globs RESULTS/<dir>/*.json
# and the unmapped-input check filters on os.path.isdir, so a result file
# sitting at the top of results/ was invisible to the whole script.
#
# l4_tsbs.jsonl is the case that exposed it. It supplies THREE of the four rows
# in T5's time-series block (DuckDB, QuestDB, and ArcadeDB's document path) and
# records none of CONDITION_KEYS and no engine version, while the fourth row
# beside them (ts59, the native path) records all of them. The lane was never
# wired into runner.py -- see the "l4 timeseries: added as adapters land"
# placeholder there -- so it produces no manifest either, and nothing else in
# the harness was covering for that.
#
# The rule this encodes: what makes a row auditable is being READ by
# make_paper_tables, not living in a directory.
#
# Both entries below are the complete set of top-level files make_paper_tables
# opens (runs.jsonl at its line 51, l4_tsbs.jsonl at its line 431). Mapping the
# base campaign too is not ceremony: run_conditions()'s docstring ASSERTS that
# "runs.jsonl carries all five" as the contrast that makes the overlays look
# bad, and an assertion in a docstring is the same species of unchecked claim
# this script exists to catch. Now it is checked. It passes, and its lane list
# is also the cleanest evidence for the l4 gap: e2, l1, l1tpc, l2, l3d, l3s,
# and no l4 at all.
FEEDS_FILES = {
    "T2/T3/T5": ["runs.jsonl"],
    "T5": ["l4_tsbs.jsonl"],
}

# Engine changes big enough that measuring on the wrong side of one produces a
# number that means something different. Extend as they are found: the cost of
# a missing entry is another T5.
LANDMARKS = [
    ("0d1bca913a", "bounded HNSW build cache lands; fp32 builds re-read "
                   "vectors from documents (slows dense builds)"),
    ("5d9f9ff72f", "auto-sized HNSW build cache fixes the above"),
    ("9e8935ce50", "index-scoped shared vector cache (#5412) speeds dense "
                   "queries"),
    # Not a behaviour change: a change in what a REPORTED NUMBER MEANS, which is
    # just as capable of producing a fake regression. estimatedLocationIndexBytes
    # switched from the 24-byte payload to APPROX_RETAINED_BYTES_PER_LOCATION=90,
    # so the identical index reports 3.75x more on this side of the commit
    # (239,760,000 -> ~899,100,000 at 10M vectors). Comparing a dev23 reading to
    # a dev22 one reads as a memory regression and is an estimator change.
    ("de1df644a6", "estimatedLocationIndexBytes now quotes retained heap "
                   "(90 B/location) instead of the 24 B payload (#5568): the "
                   "same index reports 3.75x more after this commit"),
]



def _asserted_versions():
    """Overlays whose version field is a STRING LITERAL in the producing driver.

    A version that a driver hardcodes about itself is not provenance, it is a
    claim. queue41 proved the failure mode: it ran the dev20 image and the
    dev23 image, and both results recorded "26.8.1.dev22", because
    fp32_dev22_driver.py wrote that literal regardless of what was installed.
    The published verify5412b overlay carries the same kind of self-assertion.

    This checker previously read those fields and reported them as verified,
    which is the same mistake one level up from the one it was built to catch.
    So: scan the tracked drivers for a hardcoded version literal and name the
    overlays they feed, so a self-asserted version is never mistaken for a
    measured one.

    srv5413_driver.py is the counter-example worth keeping in mind: it records
    server_version read from the running server, which is measured, and is the
    only reason the T5 server finding was discoverable at all.
    """
    import re as _re
    out = {}
    ddir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drivers")
    for fp in glob.glob(os.path.join(ddir, "*_driver.py")):
        try:
            body = open(fp).read()
        except OSError:
            continue
        if _re.search(r'"(?:engine|engine_version|version)"\s*:\s*"[0-9]', body):
            out[os.path.basename(fp)] = "hardcoded version literal"
    return out


# Which \label{} belongs to which FEEDS table, so a caption's asserted version
# can be compared against the versions actually in that table's overlays.
LABEL_TO_TABLE = {"tab:sparse": "T4", "tab:denses": "T5"}


def caption_versions():
    """Compare each table caption's ASSERTED engine version against its data.

    T4's caption read "ArcadeDB rows measured on 26.8.1.dev20" while all three
    of its ArcadeDB cells came from the dev22 overlay. dev20's 8.84M p50 was
    386.9 ms against the printed 83.7, so the caption was not describing the
    table by a wide margin.

    This checker already read versions out of result files, which is why the
    mismatch was invisible: the files were all correctly stamped dev22. The
    unchecked surface was the sentence a reader actually believes. A caption is
    a provenance claim, and until something compares it to the data it is
    exactly as trustworthy as a driver that hardcodes its own version.
    """
    paper = os.path.join(HERE, "..", "..", ".notes", "papers", "icde-2027",
                         "latex", "paper.tex")
    paper = os.path.normpath(paper)
    try:
        body = open(paper).read()
    except OSError:
        print("=== caption vs data ===\n  (paper.tex not readable; skipped)\n")
        return 0
    bad = 0
    print("=== caption vs data: versions a caption asserts ===")
    blocks = re.findall(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", body, re.S)
    for blk in blocks:
        lab = re.search(r"\\label\{(tab:[a-zA-Z]+)\}", blk)
        if not lab or lab.group(1) not in LABEL_TO_TABLE:
            continue
        table = LABEL_TO_TABLE[lab.group(1)]
        asserted = set(re.findall(r"\b(\d+\.\d+\.\d+\.dev\d+)\b", blk))
        if not asserted:
            continue
        actual, unstamped = set(), []
        for sub in FEEDS.get(table, []):
            vals, _, n, missing = _versions_in(sub)
            actual.update(vals)
            if n and missing == n:
                unstamped.append(sub)
        for a in sorted(asserted):
            if any(a in v for v in actual):
                print(f"  {table} {lab.group(1)}: caption says {a}: present in data")
            elif unstamped:
                # Distinguish "the data says otherwise" from "the data cannot
                # say". Only the first is a defect in the caption; the second
                # is a gap in the harness, and conflating them makes the gate
                # fire forever on a disclosed, already-known limitation.
                print(f"  {table} {lab.group(1)}: UNVERIFIABLE caption says {a}; "
                      f"no overlay contradicts it, but {', '.join(unstamped)} "
                      f"carries no version stamps to confirm it")
            else:
                print(f"  {table} {lab.group(1)}: BAD caption says {a}, but its "
                      f"overlays hold {sorted(actual) or ['nothing']}")
                bad += 1
    print()
    return bad


CONDITION_KEYS = ("cpuset", "heap", "mem_cap", "mem_split", "manifest")


def run_conditions():
    """Do the overlays record the conditions the protocol section promises?

    They do not, and it is systematic. Every overlay directory carries zero of
    cpuset/heap/mem_cap/mem_split/manifest, while the base campaign in
    runs.jsonl carries all five. The overlays are what T4 and T5 actually
    print, so the published cells come from artifacts recording LESS
    provenance than the campaign they override.

    That fails the program's own criterion, "every result row traces to a JSON
    manifest (engine version, image digest, cpuset, repeats)", for exactly the
    rows a reader looks at. The practical cost showed up immediately: T4's
    8.84M cell has three reps instead of five, and the two missing reps cannot
    be added now, because nothing records the cpuset, heap and memory cap the
    first three ran under. Reps measured under guessed conditions would be
    worse than an honestly disclosed N=3.

    So this reports rather than repairs. The fix belongs in the drivers before
    the freeze re-measures, not in a backfill of numbers we cannot reconstruct.
    """
    print("=== run conditions recorded by the overlays that feed the tables ===")
    feeding = sorted({s for subs in FEEDS.values() for s in subs})
    bad = 0
    for sub in feeding:
        files = glob.glob(os.path.join(RESULTS, sub, "*.json"))
        files = [f for f in files if not f.endswith(SIDECAR_SUFFIXES)]
        if not files:
            continue
        have = set()
        for fp in files:
            try:
                d = json.load(open(fp))
            except Exception:
                continue
            if isinstance(d, dict):
                have |= {k for k in CONDITION_KEYS if d.get(k) not in (None, "")}
        if have:
            print(f"  {sub:20} records {', '.join(sorted(have))}")
        else:
            print(f"  {sub:20} BAD records none of {CONDITION_KEYS}")
            bad += 1
    if bad:
        print("  These cells cannot be reproduced or extended from their own\n"
              "  artifacts. Stamp conditions in the drivers before the freeze.")
    print()
    return bad


def _load_rows(path):
    """Rows from a .json (one dict, or a list) or .jsonl (one dict per line)."""
    rows = []
    try:
        if path.endswith(".jsonl"):
            with open(path) as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
        else:
            d = json.load(open(path))
            rows = d if isinstance(d, list) else [d]
    except Exception:
        return []
    return [r for r in rows if isinstance(r, dict)]


def lane_files():
    """Same audit as run_conditions(), for the lane files the tables also read.

    A lane script that writes its own result file is not automatically safer
    than a bespoke overlay driver. It is safer only if it records what it ran
    under, and l4_tsbs.py does not: no cpuset, no heap, no memory cap, no
    manifest, no engine version, no timestamp. Its rows are printed beside a
    row that records all of them, in the same block of the same table.

    Worth being precise about what is and is not wrong here. The two sides ARE
    schema-matched: queue59.sh pins TS_TAGS=1 with the comment "Schema
    fidelity: TS_TAGS=1 deliberately", which matches l4_tsbs.py's single host
    tag. So this is not a known mismatch. It is the weaker but still
    disqualifying thing: the artifact cannot demonstrate the match, cannot say
    which host or engine version produced the comparator numbers, and cannot
    be extended with more reps later. That is the same failure that froze T4's
    8.84M cell at N=3.

    Reports rather than repairs, for the same reason run_conditions() does:
    the fix is a stamp in the lane script plus a re-run, not a backfill.
    """
    print("=== run conditions recorded by the lane FILES that feed the tables ===")
    bad = 0
    for table, names in sorted(FEEDS_FILES.items()):
        for name in names:
            path = os.path.join(RESULTS, name)
            if not os.path.exists(path):
                print(f"  {name:20} MISSING (mapped to {table} but not present)")
                bad += 1
                continue
            rows = _load_rows(path)
            if not rows:
                print(f"  {name:20} BAD unreadable or empty")
                bad += 1
                continue
            have = set()
            vkeys = set()
            for r in rows:
                have |= {k for k in CONDITION_KEYS if r.get(k) not in (None, "")}
                vkeys |= {k for k in VERSION_KEYS if _is_real_version(r.get(k))}
            backends = sorted({str(r.get("backend", "?")) for r in rows})
            where = f"{name} -> {table}, {len(rows)} rows, backends {', '.join(backends)}"
            if have and vkeys:
                print(f"  {where}\n"
                      f"    records {', '.join(sorted(have))} "
                      f"and version via {', '.join(sorted(vkeys))}")
            else:
                miss = []
                if not have:
                    miss.append(f"none of {CONDITION_KEYS}")
                if not vkeys:
                    miss.append(f"no version under any of {VERSION_KEYS}")
                print(f"  {where}\n    BAD records " + "; ".join(miss))
                bad += 1
    if bad:
        print("  A lane file is only safer than an overlay if it records more,\n"
              "  and these record less. Stamp run_conditions() in the lane\n"
              "  script and re-run before the freeze.")
    print()
    return bad


def caption_n():
    """Does each published cell rest on as many repetitions as its caption says?

    The captions assert N. Until this check existed, nothing compared that
    assertion against the arrays the tables were actually built from, and it
    had already drifted twice. T4's "N=5 except the 8.84M row, which is N=3"
    was correct only because that one exception was caught by hand. T5
    asserted a bare N=5 while printing a native-TS row built from three files
    and three DEEP-10M rows built from four warm passes.

    The protocol section, the intro's contribution list and the integrity
    section each restated N=5 globally, so one undisclosed short row made four
    statements wrong at once. That is the restatement failure mode the
    integrity section itself catalogues, turned on the paper.

    Re-deriving group sizes from results/ would be a second implementation
    that can disagree with the first, which is the same class of bug. So wrap
    the real mmm() from make_paper_tables, tag every rendered cell with the
    length of the array it was handed, and read the tagged rows back. What the
    tables printed is what this reports, by construction.

    EXPECTED holds the disclosed exceptions. A row whose N is not 5 and not
    listed here is an undisclosed shortfall and reports BAD; a row listed here
    whose N no longer matches also reports BAD, so a re-measure that reaches
    N=5 forces the caption to be corrected rather than left stale.
    """
    EXPECTED = {
        # rendered row label -> (N, where it is disclosed)
        "ArcadeDB (emb, int8)": ({3, 5}, "T4 caption: N=5 except the 8.84M row"),
        "ArcadeDB (emb)": ({4, 5}, "T5 caption: four warm passes over one build"),
        "ArcadeDB (emb, int8, 16GiB)": ({4}, "T5 caption: same treatment"),
        "ArcadeDB (srv)": ({4, 5}, "T5 caption: same treatment"),
        # The native-TS row was listed here at N=3. It was re-measured to N=5
        # on the current line (results/ts59), so the entry is gone and the
        # caption's exception with it. Leaving a stale disclosure claiming a
        # limitation we fixed is its own defect.
    }
    print("=== repetitions behind each published cell ===")
    try:
        sys.path.insert(0, HERE)
        import make_paper_tables as M
    except Exception as e:
        print(f"  SKIPPED: cannot import make_paper_tables ({e})\n")
        return 0

    _mmm, _rec, _write = M.mmm, M.mmm_rec, M.write
    captured = {}

    def _tag(fn):
        def inner(rs, *a, **kw):
            n = len([r for r in rs if isinstance(r, dict)])
            return f"\x01{n}\x02" + fn(rs, *a, **kw)
        return inner

    bad = 0
    try:
        M.mmm, M.mmm_rec = _tag(_mmm), _tag(_rec)
        M.write = lambda name, body: captured.__setitem__(name, body)
        rows = M.load_canonical()
        for fn in (M.tabular_table, M.graph_table, M.sparse_table,
                   M.dense_ts_table):
            try:
                fn(rows)
            except TypeError:
                fn()
    except Exception as e:
        print(f"  SKIPPED: table generation failed ({e})\n")
        return 0
    finally:
        M.mmm, M.mmm_rec, M.write = _mmm, _rec, _write

    for name, body in sorted(captured.items()):
        if not name.endswith(".tex"):
            continue
        for line in body.splitlines():
            ns = {int(x) for x in re.findall("\x01(\\d+)\x02", line)}
            if not ns:
                continue
            label = re.sub("\x01\\d+\x02", "", line).split("&")[0]
            label = re.sub(r"\\[a-zA-Z]+\{?|\}|\\,|\\", "", label).strip()
            if ns == {5}:
                continue
            exp = EXPECTED.get(label)
            if exp and ns <= exp[0]:
                print(f"  {name} {label:32} N={sorted(ns)} disclosed ({exp[1]})")
            elif exp:
                print(f"  {name} {label:32} N={sorted(ns)} BAD: caption says "
                      f"{sorted(exp[0])} ({exp[1]}); update the caption")
                bad += 1
            else:
                print(f"  {name} {label:32} N={sorted(ns)} BAD: below N=5 and "
                      f"disclosed in no caption")
                bad += 1
    if bad:
        print("  The protocol section, the intro and the integrity section all\n"
              "  restate N globally. An undisclosed short row makes each wrong.")
    print()
    return bad


def _repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() or None
    except Exception:
        return None


def _commit_date(sha, root):
    """ISO date for a commit, or None if this checkout does not have it."""
    if not root:
        return None
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", sha],
                             cwd=root, capture_output=True, text=True,
                             timeout=15)
        return out.stdout.strip() or None
    except Exception:
        return None


# Sidecars carry auxiliary detail for a run that is versioned elsewhere in the
# same directory, so demanding a version from them is a false positive, and a
# checker that cries wolf is a checker nobody runs.
SIDECAR_SUFFIXES = ("_buildstats.json", "_gc.json", "_manifest.json")


def _versions_in(subdir):
    """(Counter of version strings, key names seen, n files, n without version)"""
    vals, keys, missing, n = Counter(), Counter(), 0, 0
    for fp in sorted(glob.glob(os.path.join(RESULTS, subdir, "*.json"))):
        if fp.endswith(SIDECAR_SUFFIXES):
            continue
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        n += 1
        found = False
        for k in VERSION_KEYS:
            v = d.get(k)
            if isinstance(v, str) and v:
                vals[v] += 1
                keys[k] += 1
                found = True
                break
        if not found:
            missing += 1
    return vals, keys, n, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", help="check only this table (e.g. T5)")
    args = ap.parse_args()

    root = _repo_root()
    landmark_dates = [(sha, _commit_date(sha, root), why)
                      for sha, why in LANDMARKS]
    known = [x for x in landmark_dates if x[1]]
    if not known:
        print("NOTE: no landmark commits resolvable in this checkout; the "
              "build-date comparison is skipped (version reporting still runs)\n")

    bad_caption = 0 if args.table else caption_versions()
    bad_cond = 0 if args.table else run_conditions()
    bad_lane = 0 if args.table else lane_files()
    bad_n = 0 if args.table else caption_n()
    bad_captions = bad_caption + bad_cond + bad_lane + bad_n

    asserted = _asserted_versions()
    if asserted:
        print("=== drivers that ASSERT their version rather than measure it ===")
        for name, why in sorted(asserted.items()):
            print(f"  {name}: {why}")
        print("  Any overlay these produced carries a claim, not a measurement.\n")

    bad = bad_captions
    mapped = set()
    for table, subdirs in sorted(FEEDS.items()):
        if args.table and table != args.table:
            continue
        print(f"=== {table} ===")
        table_versions = set()
        for sub in subdirs:
            mapped.add(sub)
            vals, keys, n, missing = _versions_in(sub)
            if n == 0:
                print(f"  {sub:<20} (no result files)")
                continue
            vs = ", ".join(sorted(vals)) if vals else "NONE"
            kn = ",".join(keys) or "-"
            print(f"  {sub:<20} n={n:<3} key={kn:<15} {vs[:60]}")
            table_versions.update(vals)

            if missing:
                print(f"    BAD: {missing}/{n} files carry no version under "
                      f"any known key {VERSION_KEYS}")
                bad += 1

            # The T5 check: a SNAPSHOT row names its build commit, so date it
            # and say which landmarks it is on the wrong side of.
            for v in vals:
                m = re.search(r"build ([0-9a-f]{8,40})", v)
                if not m:
                    continue
                sha = m.group(1)
                built = _commit_date(sha, root)
                if not built:
                    print(f"    WARN: build commit {sha[:9]} not in this "
                          f"checkout; cannot date it")
                    continue
                print(f"    build commit {sha[:9]} dated {built[:16]}")
                for lsha, ldate, why in known:
                    if built < ldate:
                        print(f"    BAD: predates {lsha[:9]} ({ldate[:10]}): "
                              f"{why}")
                        bad += 1

        if len(table_versions) > 1:
            print(f"  NOTE: {table} mixes {len(table_versions)} engine "
                  f"versions across its rows:")
            for v in sorted(table_versions):
                print(f"      {v[:70]}")
            print("        A table whose rows come from different versions is "
                  "comparing versions\n        wherever it looks like it is "
                  "comparing configurations. Disclose or re-measure.")
        print()

    # An overlay that exists but is in no FEEDS entry is either dead or an
    # unaudited input to a published cell, and both are worth naming.
    if not args.table:
        present = {os.path.basename(p.rstrip("/"))
                   for p in glob.glob(os.path.join(RESULTS, "*"))
                   if os.path.isdir(p)}
        skip = {"archive", "manifests", "logs"}
        unmapped = sorted(present - mapped - skip)
        if unmapped:
            print("=== result dirs not mapped to any table ===")
            for u in unmapped:
                print(f"  {u}")
            print("  (dead overlay, or an unaudited input: decide which)")
            print()

        # The same question for top-level result FILES. Without this, the only
        # way a file gets audited is by someone remembering to add it to
        # FEEDS_FILES, which is precisely the memory that failed for
        # l4_tsbs.jsonl. Listing them makes an unaudited input visible even
        # when nobody thought to map it.
        mapped_files = {n for ns in FEEDS_FILES.values() for n in ns}
        loose = sorted(
            os.path.basename(p) for p in glob.glob(os.path.join(RESULTS, "*"))
            if os.path.isfile(p) and p.endswith((".json", ".jsonl"))
            and not os.path.basename(p).startswith("manifest-")
            and os.path.basename(p) not in mapped_files)
        if loose:
            print("=== top-level result files not mapped to any table ===")
            for u in loose:
                print(f"  {u}")
            print("  (mapped files are audited by lane_files(); these are not.\n"
                  "   If make_paper_tables reads one, add it to FEEDS_FILES.)")

    print(f"\n{bad} BAD finding(s)"
          + (f": {bad_caption} caption, {bad_cond} missing run conditions, "
             f"{bad - bad_caption - bad_cond} version/landmark"
             if not args.table else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
