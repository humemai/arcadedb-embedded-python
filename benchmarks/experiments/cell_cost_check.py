#!/usr/bin/env python3
"""Will this stage's cells fit their cap? Asked BEFORE the stage runs.

October's analytics stage was planned at 18.8 h and censored its FIRST cell,
our own engine, at the two-hour cap (BUGS F74, DECISIONS #109). Nothing had
asked the question this script asks, because the budget derivation (#106)
estimates what a query's ITERATIONS cost and never what its FIRST TOUCH
costs -- and the first touch is unbounded by design (#82b: it always
completes, so a capped query still yields a number and an answer digest).

A cell costs roughly

    sum over queries of  [ first touch ]  +  [ iterations, bounded by budget ]

and only the second term was ever estimated. On the cell that failed, the
first term alone was 1,384 s for ONE query against a 7,200 s cap.

Every row already carries `cold_<query>_ms`. Nothing reads it. This does.

    python3 cell_cost_check.py --lane l2 --tier sf1full
    python3 cell_cost_check.py --lane l2 --tier sf1full --from-tier sf1 --scale-by 98

`--from-tier`/`--scale-by` project from a SMALLER tier's rows when the target
tier has none, which is the planning case. The factor is a measurement, not a
guess: state where it came from in the commit that uses it.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))


def _rows(paths):
    out = []
    for p in paths:
        if not os.path.exists(p):
            continue
        if p.endswith(".csv"):
            with open(p, newline="") as fh:
                out += list(csv.DictReader(fh))
        else:
            with open(p, errors="replace") as fh:
                for line in fh:
                    try:
                        out.append(json.loads(line))
                    except Exception:  # noqa: BLE001
                        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True)
    ap.add_argument("--tier", required=True)
    ap.add_argument("--from-tier", default=None,
                    help="project from this tier's rows when --tier has none")
    ap.add_argument("--scale-by", type=float, default=1.0,
                    help="measured blow-up factor between --from-tier and --tier")
    ap.add_argument("--cap", type=float, default=None,
                    help="seconds; default reads runner.TIMEOUT_BY_SCALE[--tier]")
    ap.add_argument("--rows", nargs="*", default=None)
    a = ap.parse_args()

    cap = a.cap
    if cap is None:
        import runner
        cap = float(runner.TIMEOUT_BY_SCALE[a.tier])

    src_tier = a.from_tier or a.tier
    paths = a.rows or [os.path.join(HERE, "results", f)
                       for f in ("runs_paper.csv", "runs_skeleton_laptop.csv",
                                 "runs.jsonl")]
    rows = [r for r in _rows(paths)
            if r.get("lane") == a.lane and str(r.get("scale")) == src_tier]
    if not rows:
        print(f"no rows for {a.lane}/{src_tier} in {', '.join(os.path.basename(p) for p in paths)}")
        return 2

    per = collections.defaultdict(dict)
    for r in rows:
        be = str(r.get("backend"))
        for k, v in r.items():
            if not k.startswith("cold_") or not k.endswith("_ms") or v in (None, ""):
                continue
            try:
                per[be].setdefault(k[5:-3], []).append(float(v))
            except (TypeError, ValueError):
                pass

    # COVERAGE FIRST, or this tool gives false comfort. Run against September's
    # sf1full rows it reported every engine "ok" for the very stage that was
    # then censored -- because those rows carry the FIVE hand-written queries
    # and October runs FOURTEEN. A check that silently measures a subset of
    # the work is worse than no check: it answers a question nobody asked and
    # sounds like the one they did.
    want = set()
    try:
        if a.lane == "l2":
            import graph_common
            want = {q for q in graph_common.OLAP_QUERIES
                    if not graph_common.tier_excluded(a.tier, q)}
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not read the lane's query set: {exc})")
    have = set()
    for d in per.values():
        have |= set(d)
    missing = sorted(want - have) if want else []
    if missing:
        print(f"REFUSING to score {a.lane}/{a.tier}: the rows cover "
              f"{len(have & want)} of {len(want)} queries this lane will run.")
        print(f"  no first-touch data for: {', '.join(missing)}")
        print(f"  rows read from tier {src_tier!r}. Point --from-tier at a tier "
              f"where these ran, with the measured --scale-by, or run them once.")
        return 2

    print(f"{a.lane}/{a.tier}: FIRST-TOUCH cost per engine, cap {cap:.0f} s"
          + (f", projected from {src_tier} x{a.scale_by:g}" if a.scale_by != 1 else ""))
    print(f"  {'engine':28} {'first touches':>14}  {'% of cap':>9}  verdict")
    over = 0
    for be in sorted(per):
        # ONLY THE QUERIES THIS TIER WILL RUN. The first version summed every
        # cold_ field in the row, which includes the ones TIER_EXCLUDED drops
        # -- so it scored the excluded work and reported six engines over the
        # cap when the whole point of the exclusion was to bring them under.
        qs = {q: v for q, v in per[be].items() if not want or q in want}
        tot = sum(statistics.median(v) for v in qs.values()) / 1000.0 * a.scale_by
        pct = tot / cap * 100
        verdict = "OVER THE CAP" if tot >= cap else ("tight" if pct > 50 else "ok")
        if tot >= cap:
            over += 1
        print(f"  {be:28} {tot:11.0f} s  {pct:8.0f}%  {verdict}")
    print(f"\n  {len(per)} engine(s), {over} over the cap on FIRST TOUCHES ALONE")
    print("  (iterations add on top, bounded by each query's budget)")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
