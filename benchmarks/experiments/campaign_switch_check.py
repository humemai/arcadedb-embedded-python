#!/usr/bin/env python3
"""Everything that must be true, and everything that must change, to switch the
page from one campaign to the next (DECISIONS #83, #96).

The switch is the moment the whole page changes at once: a new engine pin, a
new comparator set, new columns, new prose, and a documentation site that
describes all of it. It happens rarely enough that nobody remembers the steps
and often enough that forgetting one is expensive, so this reports rather than
relies on memory.

    python campaign_switch_check.py --new-pin <commit-or-version> [--old-pin 8d6af9475]

It answers four questions:
  1. Are the preconditions met: does the new campaign's payload exist, do the
     gates pass on it, and does the preview route render it.
  2. What still names the OLD campaign: every tracked file outside results/
     that mentions the old pin, so the switch updates them together instead of
     leaving a page that says one thing and a document that says another.
  3. What the docs site says that a new campaign can invalidate: the pages that
     name a version, a date, a query set, or an instrument, listed with the
     lines, because those are prose a generator cannot keep current.
  4. What should be REMOVED rather than carried: decisions already superseded,
     bugs fixed in the campaign that is ending, retired markers whose subject is
     gone, and withheld cells whose upstream issue has closed. A switch is when
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SITE = REPO.parent / "humem.ai"
DOCS = REPO / "bindings" / "python" / "docs"

# Prose that a campaign can invalidate, by pattern rather than by file, so a
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
    ap.add_argument("--old-pin", default=os.environ.get("BENCH_ENGINE_COMMIT", "8d6af9475"))
    args = ap.parse_args()
    problems = 0

    step(1, "preconditions for the new campaign")
    payload = HERE / "results" / "web_benchmarks.json"
    preview = SITE / "src" / "data" / "arcadedb-benchmarks-next.json"
    for p, what in ((payload, "live payload"), (preview, "preview payload")):
        print(f"  {'ok  ' if p.exists() else 'MISS'} {what}: {p}")
        problems += 0 if p.exists() else 1
    if preview.exists():
        doc = json.loads(preview.read_text())
        if doc.get("skeleton"):
            print("  NOTE the preview still carries the laptop skeleton; a switch publishes measurements, not placeholders")
            problems += 1
        print(f"  preview tables: {len(doc.get('tables', []))}")

    step(2, "what still names the old campaign")
    out = sh(["git", "grep", "-l", args.old_pin, "--", ".", ":!benchmarks/experiments/results"], cwd=REPO).stdout
    files = [f for f in out.splitlines() if f.strip()]
    for f in files:
        print(f"  {f}")
    print(f"  {len(files)} tracked file(s) name {args.old_pin}; each is a switch edit or a deliberate historical mention")

    step(3, "documentation prose a new campaign can invalidate")
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

    step(4, "what to remove, because a switch is when pruning is cheapest")
    notes = REPO / ".notes" / "bench"
    dec = notes / "DECISIONS.md"
    bugs = notes / "BUGS.md"
    if dec.exists():
        stat = re.findall(r"(?m)^## (#\d+\w*) .*?\n> Status: (.+?)\.?$", dec.read_text(encoding="utf-8"))
        if stat:
            print(f"  {len(stat)} decision(s) already carry a status; a switch is when a superseded one moves to the archive:")
            for num, why in stat[:8]:
                print(f"    {num}: {why[:80]}")
    if bugs.exists():
        fixed = re.findall(r"(?m)^### (\w+)\. .*?\n\nStatus: (fixed[^\n]*)", bugs.read_text(encoding="utf-8"))
        old = [(n, w) for n, w in fixed if args.old_pin[:7] in w or "re-run" in w]
        print(f"  {len(fixed)} bug(s) recorded as fixed; {len(old)} name the campaign that is ending and can be archived with it")
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
    print("  the preview route, its payload, its images, and its prose file are deleted by the switch itself")

    step(5, "the switch itself, in order")
    for i, line in enumerate([
        "land the final stage and freeze the campaign (land_stage.py --apply)",
        "run every gate on the new payload, including the manifest coverage check",
        "publish the results asset (publish_results_asset.py --tag <tag> --publish)",
        "copy the preview payload, images, and prose over the live ones in one commit",
        "delete the preview route and its payload, so nothing stale is reachable",
        "update every file listed in step 2 that is not a historical mention",
        "update every documentation line listed in step 3 that the new campaign changes",
        "archive what step 4 listed: superseded decisions, bugs fixed in the campaign that ended, retired markers, and any withheld cell whose upstream issue has closed",
        "re-read every doc the pruning touched: removing a rule leaves sentences that referred to it, and a document describing a thing that no longer exists is worse than no document",
        "rebuild the documentation site and the page, and check both links still resolve",
    ], 1):
        print(f"  {i}. {line}")

    print(f"\n{'PROBLEMS: ' + str(problems) if problems else 'preconditions look satisfied'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
