#!/usr/bin/env python3
"""Everything that must be true, and everything that must change, when the page
moves to a new engine pin (DECISIONS #83, #96).

A re-pin changes the whole page at once: a new engine pin, new numbers, and a
documentation site that describes all of it. It happens rarely enough that
nobody remembers the steps and often enough that forgetting one is expensive,
so this reports rather than relies on memory.

    python campaign_switch_check.py --new-pin <commit-or-version> [--old-pin <commit-or-version>]

It answers four questions:
  1. Are the preconditions met: does the payload exist, is it stamped with the
     publish instrument and not a skeleton, and does it carry the new pin.
  2. What still names the OLD pin: every tracked file outside results/ that
     mentions it, so the re-pin updates them together instead of leaving a page
     that says one thing and a document that says another.
  3. What the docs site says that a new pin can invalidate: the pages that
     name a version, a date, a query set, or an instrument, listed with the
     lines, because those are prose a generator cannot keep current.
  4. What should be REMOVED rather than carried: decisions already superseded,
     bugs fixed in the build that is ending, retired markers whose subject is
     gone, and withheld cells whose upstream issue has closed. A re-pin is when
     pruning is cheapest, and the reason this step exists is that we have twice
     confused ourselves by piling entries up instead.

Nothing is changed. The output is a checklist to work through.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from publish_instrument import PUBLISH_INSTRUMENT, results_dir

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCS = REPO / "bindings" / "python" / "docs"

# Prose that a re-pin can invalidate, by pattern rather than by file, so a
# page added later is still covered.
DOC_PATTERNS = [
    (r"\b\d{2}\.\d{1,2}\.\d{1,2}\b", "an engine or library version"),
    (r"\b20\d\d-\d\d-\d\d\b", "a date"),
    (r"#\s?7[0-9]{3}\b", "an upstream issue number"),
    (r"\bforty\b|\b40 (operations|timed)", "the query-set size"),
    (r"\b2026-\d\d\b", "an instrument label"),
]


def sh(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def step(n, title):
    print(f"\n[{n}] {title}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new-pin", required=True)
    ap.add_argument("--old-pin", default=os.environ.get("BENCH_ENGINE_COMMIT"),
                    help="the pin being replaced (default: BENCH_ENGINE_COMMIT)")
    args = ap.parse_args()
    if not args.old_pin:
        ap.error("--old-pin is required when BENCH_ENGINE_COMMIT is not set")
    problems = 0

    step(1, "preconditions for the new pin")
    payload = results_dir() / "web_benchmarks.json"
    print(f"  {'ok  ' if payload.exists() else 'MISS'} payload: {payload}")
    if not payload.exists():
        problems += 1
    else:
        doc = json.loads(payload.read_text())
        if doc.get("instrument") != PUBLISH_INSTRUMENT or doc.get("skeleton"):
            print(f"  FAIL the payload is stamped {doc.get('instrument')!r}, skeleton={doc.get('skeleton')!r}; "
                  f"a re-pin publishes {PUBLISH_INSTRUMENT} measured rows")
            problems += 1
        commits = doc.get("arcadedb_commits") or []
        if not any(str(c).startswith(args.new_pin) or args.new_pin.startswith(str(c)) for c in commits):
            print(f"  FAIL the payload's engine commits {commits} do not include {args.new_pin}")
            problems += 1
        print(f"  tables: {len(doc.get('tables', []))}")

    step(2, "what still names the old pin")
    out = sh(["git", "grep", "-l", args.old_pin, "--", ".", ":!benchmarks/experiments/results"], cwd=REPO).stdout
    files = [f for f in out.splitlines() if f.strip()]
    for f in files:
        print(f"  {f}")
    print(f"  {len(files)} tracked file(s) name {args.old_pin}; each is a re-pin edit or a deliberate historical mention")

    step(3, "documentation prose a new pin can invalidate")
    for page in sorted(DOCS.rglob("*.md")):
        hits = []
        for i, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            for pat, what in DOC_PATTERNS:
                if re.search(pat, line):
                    hits.append((i, what, line.strip()[:90]))
                    break
        if hits:
            print(f"  {page.relative_to(REPO)}")
            for i, what, text in hits[:6]:
                print(f"    line {i}: {what}: {text}")
            if len(hits) > 6:
                print(f"    ... and {len(hits) - 6} more")

    step(4, "what to remove, because a re-pin is when pruning is cheapest")
    notes = REPO / ".notes" / "bench"
    dec = notes / "DECISIONS.md"
    bugs = notes / "BUGS.md"
    if dec.exists():
        stat = re.findall(r"(?m)^## (#\d+\w*) .*?\n> Status: (.+?)\.?$", dec.read_text(encoding="utf-8"))
        if stat:
            print(f"  {len(stat)} decision(s) already carry a status; a re-pin is when a superseded one moves to the archive:")
            for num, why in stat[:8]:
                print(f"    {num}: {why[:80]}")
    if bugs.exists():
        fixed = re.findall(r"(?m)^### (\w+)\. .*?\n\nStatus: (fixed[^\n]*)", bugs.read_text(encoding="utf-8"))
        old = [(n, w) for n, w in fixed if args.old_pin[:7] in w or "re-run" in w]
        print(f"  {len(fixed)} bug(s) recorded as fixed; {len(old)} name the build that is ending and can be archived with it")
    # Prose markers that outlive their subject.
    for path, pat, what in (
        (HERE / "PAGE-SPEC.md", r"(?i)retired|no longer (run|published)", "retired-table markers"),
        (HERE / "COMPARATORS.md", r"(?i)retired|replaced by", "retired comparator pins"),
        (HERE / "export_web.py", r"KNOWN_DISAGREEMENTS|WITHHELD_CELLS", "withheld cells and known disagreements"),
    ):
        if not path.exists():
            continue
        n = len(re.findall(pat, path.read_text(encoding="utf-8")))
        if n:
            print(f"  {path.name}: {n} mention(s) of {what}; each one outlives its subject at a re-pin and should be re-read")
    # A withheld cell exists because an upstream defect does. If the issue closed, the entry goes.
    issues = sorted(set(re.findall(r"#(7\d{3})", (HERE / "export_web.py").read_text(encoding="utf-8"))))
    for num in issues:
        r = sh(["gh", "issue", "view", num, "--repo", "ArcadeData/arcadedb", "--json", "state,title"])
        if r.returncode == 0:
            try:
                d = json.loads(r.stdout)
                mark = "CLOSED, so the entry that cites it should go" if d.get("state") == "CLOSED" else "still open, so the entry stays"
                print(f"  upstream #{num}: {mark}  ({d.get('title','')[:60]})")
            except json.JSONDecodeError:
                pass

    step(5, "the re-pin itself, in order")
    for i, line in enumerate([
        "land the final stage and freeze (land_stage.py --apply)",
        "run every gate on the new payload, including the manifest coverage check",
        "publish the results asset (publish_results_asset.py --tag <tag> --publish)",
        "update every file listed in step 2 that is not a historical mention",
        "update every documentation line listed in step 3 that the new pin changes",
        "archive what step 4 listed: superseded decisions, bugs fixed in the build that ended, retired markers, and any withheld cell whose upstream issue has closed",
        "re-read every doc the pruning touched: removing a rule leaves sentences that referred to it, and a document describing a thing that no longer exists is worse than no document",
        "rebuild the documentation site and the page, and check both links still resolve",
    ], 1):
        print(f"  {i}. {line}")

    print(f"\n{'PROBLEMS: ' + str(problems) if problems else 'preconditions look satisfied'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
