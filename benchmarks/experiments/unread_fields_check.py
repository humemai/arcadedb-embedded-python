#!/usr/bin/env python3
"""Which recorded fields does nothing read?

The harness records far more than anything reads, and twice on 2026-09-19 that
gap was a rule the page depends on:

  * BUGS F71 -- `host_throttled_ms` and the temperature counters are written
    per cell and read by no gate, while a coverage declaration claimed FAIRNESS
    audited them and PAGE-SPEC required a disclosure the page never carried.
  * BUGS F72 -- `server_disk_settled` is written per cell and read by nothing,
    while PAGE-SPEC 4a rule 3 says "settled=False blocks publication". It never
    blocked anything; 26 Milvus cells published unsettled disk readings.

Both were invisible because nothing FAILED. A field nobody reads produces no
error, no warning, and no missing cell -- it produces a rule that is true in a
document and false in the code.

This is the cheap sweep that finds them: every field name in the frozen rows,
against the source of every consumer, reporting the unread ones that actually
carry data. It is an AUDIT, not a gate: most unread fields are telemetry kept
on purpose, and failing a publish over them would be noise. Read the list and
decide; the ones that matter are the fields a decision or a spec line names.

Usage:
    python3 unread_fields_check.py [--rows results/runs_paper.csv] [--all]
"""
from __future__ import annotations

import argparse
import csv
import os

# Everything that turns a row into a published number, a gate verdict, or a
# figure. A field read by none of these is read by nothing that ships.
CONSUMERS = [
    "export_web.py", "make_paper_tables.py", "page_check.py", "fairness_check.py",
    "provenance_check.py", "equivalence_check.py", "make_paper_figures.py",
    "memo_bottlenecks.py", "version_consistency_check.py", "claims_check.py",
    "publish_results_asset.py", "refresh_web_page.py", "campaign_switch_check.py",
]

# Families that are telemetry by design: kept on the row so a cell can be
# audited after the fact, never intended to reach a page or a gate. Listed so
# the report shows what is left after them rather than burying it.
TELEMETRY_PREFIXES = ("client_", "server_peak", "server_end", "server_io",
                      "server_cpu", "host_", "phase_")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default=os.path.join(here, "results", "runs_paper.csv"))
    ap.add_argument("--all", action="store_true",
                    help="include the telemetry families, which are unread on purpose")
    a = ap.parse_args()

    blob = "\n".join(
        open(os.path.join(here, c), errors="replace").read()
        for c in CONSUMERS if os.path.exists(os.path.join(here, c)))

    with open(a.rows, newline="") as fh:
        rd = csv.DictReader(fh)
        fields = [f for f in (rd.fieldnames or []) if f]
        rows = list(rd)

    # A field DECLARED by regex in page_check.NOT_PRINTED is accounted for
    # even though its literal name appears nowhere: that list is how a
    # recorded-but-not-printed field is justified with a reason. Without this
    # the report is 138 lines of mostly-declared fields, and a report nobody
    # reads is worth as much as the check that was missing.
    declared = []
    try:
        import page_check as _PC
        import re as _re
        declared = [_re.compile(pat) for pat, _why in _PC.NOT_PRINTED]
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not read page_check.NOT_PRINTED: {exc})")

    def is_declared(f):
        return any(rx.match(f) for rx in declared)

    unread = [f for f in fields if f not in blob and not is_declared(f)]
    hits = []
    for f in unread:
        n = sum(1 for r in rows if r.get(f) not in (None, ""))
        if not n:
            continue
        if not a.all and f.startswith(TELEMETRY_PREFIXES):
            continue
        hits.append((n, f))
    hits.sort(reverse=True)

    print(f"{len(fields)} fields in {os.path.basename(a.rows)}; "
          f"{len(unread)} appear in no consumer")
    print(f"of those, {len(hits)} carry data"
          + ("" if a.all else " and are not a telemetry family (use --all to see those)"))
    for n, f in hits:
        print(f"  {n:5} rows  {f}")
    if hits:
        print("\nFor each: is it named by a DECISION or a PAGE-SPEC rule? If so the rule")
        print("is unenforced, which is F71/F72's shape. If not, it is telemetry and fine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
