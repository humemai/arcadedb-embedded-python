#!/usr/bin/env python3
"""Every RESULT number in the project page's prose must trace to a pinned claim.

claims_check.py already closes one link: it asks the table generator whether each
pinned value is still what the data produces, and fails when the data moves. But a
claim pins DATA -> EXPECTED VALUE. Nothing pinned EXPECTED VALUE -> THE PROSE THE
READER SEES, and the page lives in another repo entirely, so the two could drift
apart in silence in both directions:

  * the campaign moves a number, claims_check goes red, someone updates the claim
    literal and forgets the page, which keeps publishing the old figure; or
  * someone edits the page prose directly and no check anywhere disagrees.

Audited on 2026-08-27 the page carried 13 numbers and 6 of them were backed by no
claim at all: 95.1%, 93.4%, 6.5x, 2.4x, 1.4x, and the 30,109 corpus constant. The
in-flight dense campaign will move several of those.

WHY NOT SUBSTITUTE THE NUMBERS INTO THE PROSE INSTEAD. It was the first idea and it
is worse. Prose states DIRECTION as well as magnitude -- "worth 6.5x", "moves
ArcadeDB from behind Neo4j to ahead of it" -- and a token that renders 0.8 into a
sentence built around "worth" produces a fluent, generated, false claim. A failing
check makes a human read the sentence, which is exactly the step that needs a human.
Same reasoning claims_check.py gives for importing the generator rather than
recomputing: the check must not be able to invent an answer.

    python3 page_prose_check.py                 # check, exit 1 on an unpinned result
    python3 page_prose_check.py --list          # every number found, with its status
    BENCH_PAGE_PROSE=/path/to/arcadedb.ts python3 page_prose_check.py
"""
import argparse
import os
import pathlib
import re
import sys

DEFAULT_PROSE = os.path.expanduser(
    "~/repos/humemai/humem.ai/src/lib/projects/items/arcadedb.ts")
PROSE = os.environ.get("BENCH_PAGE_PROSE", DEFAULT_PROSE)

# NOT RESULTS, so no claim can back them. Each needs a reason, because an
# allowlist without reasons is how a real result gets quietly excused.
NOT_A_RESULT = {
    "30109": "SPLADE vocabulary size: a property of the corpus, not a measurement",
    "30,109": "SPLADE vocabulary size: a property of the corpus, not a measurement",
    "100": "corpus tier label (100k)",
    "8.84": "corpus tier label (8.84M docs)",
    "10": "corpus tier label",
    "1": "corpus tier label (1M)",
    "0.4": "Elasticsearch's OWN documented relative error for its ~9-bit sparse "
           "weight encoding; an external vendor fact the page cites, not a "
           "measurement of ours, so no selector of ours can produce it",
}

# A number in prose is a RESULT if it carries one of these units, or is written as
# a ratio. Bare integers in a sentence are usually counts of things, not timings.
RESULT_RE = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?)\s*(ms\b|s\b|x\b|%|GB\b|MB\b)")


def load_claim_values():
    """Expected values from claims_check.CLAIMS, without running the checks.

    Imported rather than re-parsed: the claim list is the authority on what is
    pinned, and a second parser of the same file is a second thing to drift.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    try:
        import claims_check as C
    except Exception as exc:                      # noqa: BLE001
        print(f"cannot import claims_check: {exc}", file=sys.stderr)
        raise SystemExit(2)
    out = []
    for claim in getattr(C, "CLAIMS", []):
        if len(claim) >= 3 and isinstance(claim[1], (int, float)):
            out.append((claim[0], float(claim[1]), float(claim[2] or 0)))
    if not out:
        print("claims_check.CLAIMS parsed to nothing; refusing to report a clean "
              "page on an empty claim list", file=sys.stderr)
        raise SystemExit(2)
    return out


def find_numbers(text):
    """Every result-shaped number in the prose, with the line it sits on."""
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in RESULT_RE.finditer(line):
            raw, unit = m.group(1), m.group(2)
            found.append((lineno, raw, unit, line.strip()[:110]))
    return found


def backed_by(value, claims, unit=""):
    """The claim pinning this value, allowing the claim's own tolerance.

    Falls back to 1% when a claim declares none, so a rounded prose figure (13.8
    against a pinned 13.81) still matches. Rounding the other way -- a prose
    number more precise than its claim -- is not something to paper over.

    UNITS DIFFER BETWEEN PROSE AND CLAIMS, and ignoring that makes the check cry
    wolf. Prose says "95.1%" where l3d.arcadedb.recall pins 0.951: the same
    measurement, written for a reader rather than for a selector. The first
    version of this function reported both recall figures as unpinned, which is
    the worst failure mode a gate has -- a false alarm teaches people to skip it,
    and then it is not a gate. A percentage is therefore also tried as a
    fraction.
    """
    candidates = [value]
    if unit == "%":
        candidates.append(value / 100.0)
    for cid, expected, tol in claims:
        for v in candidates:
            if abs(v - expected) <= max(tol, abs(expected) * 0.01):
                return cid
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print every number found and its status")
    args = ap.parse_args()

    path = pathlib.Path(PROSE)
    if not path.exists():
        print(f"page prose not found: {path}\n"
              f"set BENCH_PAGE_PROSE if the site repo lives elsewhere", file=sys.stderr)
        return 2

    claims = load_claim_values()
    numbers = find_numbers(path.read_text())
    if not numbers:
        print(f"no result-shaped numbers found in {path}; the regex or the file "
              f"changed shape, which is not the same as a clean page", file=sys.stderr)
        return 2

    unpinned, pinned, excused = [], [], []
    for lineno, raw, unit, ctx in numbers:
        if raw in NOT_A_RESULT or raw.replace(",", "") in NOT_A_RESULT:
            excused.append((lineno, raw, unit, ctx))
            continue
        cid = backed_by(float(raw.replace(",", "")), claims, unit)
        (pinned if cid else unpinned).append((lineno, raw, unit, ctx, cid))

    if args.list:
        for lineno, raw, unit, ctx, cid in sorted(pinned + unpinned):
            print(f"  {path.name}:{lineno}  {raw}{unit:<3} "
                  f"{'-> ' + cid if cid else 'UNPINNED'}")
        for lineno, raw, unit, ctx in excused:
            print(f"  {path.name}:{lineno}  {raw}{unit:<3} excused: "
                  f"{NOT_A_RESULT.get(raw) or NOT_A_RESULT.get(raw.replace(',', ''))}")

    print(f"\npage prose: {path}")
    print(f"  {len(pinned)} pinned to a claim, {len(excused)} excused as non-results, "
          f"{len(unpinned)} UNPINNED")
    if unpinned:
        print("\nThese publish a number nothing verifies. When the campaign moves "
              "them, no check goes red:")
        for lineno, raw, unit, ctx, _ in sorted(unpinned):
            print(f"  {path.name}:{lineno}  {raw}{unit}")
            print(f"      {ctx}")
        print("\nFix: add a claim to claims_check.CLAIMS pinning each to the "
              "selector that produces it, or add it to NOT_A_RESULT with a reason.")
        return 1
    print("  every result number on the page traces to a pinned claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
