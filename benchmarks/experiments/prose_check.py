#!/usr/bin/env python3
"""Every RESULT number a PUBLICATION states must trace to a pinned claim.

The same results feed three consumers -- the humem.ai project page, the arXiv
paper, and the ICDE 2027 submission -- and each restates numbers in prose that no
generator produces. This file checks all of them through one scanner, because the
alternative is one checker per consumer that slowly disagree about what "covered"
means. claims_check.sweep() already does a paper-only version of this for ratios;
this generalises it to every result-shaped number and to every target.

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

# THE PUBLICATION TARGETS. Adding one is a row here, not code, which is the
# point: the LaTeX papers are being rewritten and must be checkable the day they
# are ready without anyone reworking this file.
#
# `gates`: True means an unpinned number fails the run. The page is live and
# gates. The papers are drafts under active rewrite, so they REPORT until their
# prose settles -- a gate that is red for a fortnight of drafting teaches people
# to pass --skip, and then it is not a gate. Flip them when the rewrite lands.
#
# A target whose file is absent is SKIPPED and said so out loud. It is never
# silently counted as clean: "no numbers found" and "no file" are different
# facts, and only one of them is good news.
TARGETS = [
    {"name": "page",  "env": "BENCH_PAGE_PROSE", "kind": "ts",  "gates": True,
     "default": "~/repos/humemai/humem.ai/src/lib/projects/items/arcadedb.ts"},
    {"name": "arxiv", "env": "BENCH_ARXIV_TEX",  "kind": "tex", "gates": False,
     "default": "~/repos/humemai/arcadedb-paper/paper.tex"},
    {"name": "icde",  "env": "BENCH_ICDE_TEX",   "kind": "tex", "gates": False,
     "default": "~/repos/humemai/arcadedb-icde2027/paper.tex"},
]


def target_path(t):
    return pathlib.Path(os.path.expanduser(os.environ.get(t["env"], t["default"])))

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


def prepare(text, kind):
    """Strip what is not prose, per file kind, before scanning.

    LaTeX carries three things that would produce false findings: comment lines
    (a commented-out paragraph is not published), \\input of generated tables
    (those numbers ARE generated and claims_check checks them at the source), and
    macro arguments like \\num{1.4}. Only the first two are stripped; \\num is
    unwrapped so the value inside is still scanned, because a number the author
    typed is the author's claim however it is wrapped.
    """
    if kind != "tex":
        return text
    text = re.sub(r"(?m)^\s*%.*$", "", text)                 # comment lines
    # ONE backslash, not two. LaTeX escapes a literal percent as \%, so a
    # lookbehind for two backslashes does not fire on it and this regex treats
    # "95.1\%" as the start of a comment -- silently deleting the rest of the
    # sentence, and with it every number in it. That is the failure mode a gate
    # must not have: it reported clean because it had eaten the evidence.
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.M)      # trailing comments
    text = re.sub(r"\\input\{[^}]*\}", "", text)              # generated tables
    text = re.sub(r"\\num\{([^}]*)\}", r"\1", text)           # unwrap siunitx
    # LaTeX writes a literal percent as \%, which the result regex would not
    # match: 95.1\% would scan as the bare number 95.1 with no unit and be
    # dropped. A missed number is worse than a false alarm here, because the
    # gate reports clean and the stale figure ships.
    text = text.replace(r"\%", "%")
    # Ranges: "3--20x" states two numbers, and the second is the one that goes
    # stale when the operands move. Both are scanned.
    text = re.sub(r"(\d)\s*--\s*(\d)", r"\1x \2", text)
    return text


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
    ap.add_argument("--target", help="check only this target by name")
    args = ap.parse_args()

    claims = load_claim_values()
    failed = skipped = 0

    for t in TARGETS:
        if args.target and t["name"] != args.target:
            continue
        path = target_path(t)
        gate = " (gates)" if t["gates"] else " (reports only)"
        if not path.exists():
            # SAID OUT LOUD. "No file" and "no unpinned numbers" are different
            # facts and only one is good news; a silent skip reads as a pass.
            print(f"\n{t['name']}{gate}: NOT PRESENT at {path}")
            print(f"  set {t['env']} to check it")
            skipped += 1
            continue

        numbers = find_numbers(prepare(path.read_text(), t["kind"]))
        if not numbers:
            print(f"\n{t['name']}{gate}: {path}")
            print("  no result-shaped numbers found; the file or the regex "
                  "changed shape, which is not the same as clean")
            failed += 1 if t["gates"] else 0
            continue

        unpinned, pinned, excused = [], [], []
        for lineno, raw, unit, ctx in numbers:
            key = raw.replace(",", "")
            if raw in NOT_A_RESULT or key in NOT_A_RESULT:
                excused.append((lineno, raw, unit))
                continue
            cid = backed_by(float(key), claims, unit)
            (pinned if cid else unpinned).append((lineno, raw, unit, ctx, cid))

        print(f"\n{t['name']}{gate}: {path}")
        print(f"  {len(pinned)} pinned, {len(excused)} excused, "
              f"{len(unpinned)} UNPINNED")
        if args.list:
            for lineno, raw, unit, ctx, cid in sorted(pinned + unpinned):
                print(f"    :{lineno}  {raw}{unit:<3} "
                      f"{'-> ' + cid if cid else 'UNPINNED'}")
        for lineno, raw, unit, ctx, _ in sorted(unpinned):
            print(f"    :{lineno}  {raw}{unit}  <- nothing verifies this")
            print(f"        {ctx}")
        if unpinned and t["gates"]:
            failed += 1

    if skipped:
        print(f"\n{skipped} target(s) not present and therefore NOT checked.")
    if failed:
        print("\nFix: pin each to the selector that produces it in "
              "claims_check.CLAIMS, or add it to NOT_A_RESULT with a reason.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
