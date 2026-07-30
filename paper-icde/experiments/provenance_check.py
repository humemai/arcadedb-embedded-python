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
VERSION_KEYS = ("engine_version", "engine", "server_version", "version", "wheel")

# Which overlay directories feed which table. Mirrors make_paper_tables.py; if
# that file grows a new overlay and this map does not, the unmapped-dir check
# at the bottom says so rather than quietly ignoring it.
FEEDS = {
    "T4": ["dev22_sparse", "dev21_sparse", "dev21_sparse_full", "sparse_full",
           "verify5411"],
    "T5": ["verify5412b", "verify5413", "dev21_ts"],
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

    bad = 0
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

    print(f"\n{bad} BAD finding(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
