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
    # EVERY LANE'S QUERY SET, or the coverage check protects one lane and
    # leaves the rest to the same false "ok". Read from the lane module, never
    # typed here: a query added to a lane must reach this check on its own.
    want = set()
    try:
        if a.lane == "l2":
            import graph_common
            want = {q for q in graph_common.OLAP_QUERIES
                    if not graph_common.tier_excluded(a.tier, q)}
        elif a.lane == "l1tpc":
            import l1_tpc
            want = set(l1_tpc.OLAP_QUERIES)
        elif a.lane == "l4":
            import l4_tsbs
            want = set(l4_tsbs.QUERIES)
    except Exception as exc:  # noqa: BLE001
        print(f"  (could not read the lane's query set: {exc})")
    if not want:
        # The vector, cross-model and lifecycle lanes time one operation per
        # cell rather than a query set, so there is no roster to hold rows
        # against. Say so rather than scoring a subset in silence.
        print(f"  NOTE: no query roster known for lane {a.lane!r}; scoring whatever "
              f"cold_* fields the rows carry, which may be a SUBSET of the work.")
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

    # THE WHOLE CELL, not just its first touches. A cell is
    #     ingest + first touches + iterations (bounded by the budgets)
    # and estimating any one term alone gets the answer wrong. Three attempts
    # on 2026-09-20 to project the time-series lane from a RATIO between
    # campaigns were wrong twice (8.2x from one arm, then a "fixed overhead"
    # from two) because what changes between campaigns is not a scale factor,
    # it is which work each cell does. Adding the terms up from measured rows
    # predicted the first cell of the next tier to within 4% (2,674 s against
    # an observed 2,793 s) on an engine it had never seen at that size.
    ingest = collections.defaultdict(list)
    for r in rows:
        v = r.get("ingest_s")
        if v not in (None, ""):
            try:
                ingest[str(r.get("backend"))].append(float(v))
            except (TypeError, ValueError):
                pass
    budget_ceiling = 0.0
    if want:
        try:
            import budget_lookup as _B
            # READ THE LANE'S OWN CONSTANT, never a copy here. A typed table
            # of defaults was wrong for l4 on its first run -- 300 against the
            # lane's real 300... no: the lane's QUERY_BUDGET_S, which the
            # stage preflight reads and this did not, so the two disagreed by
            # 900 s on the same tier. Two places holding the same number is
            # one place too many.
            dflt = None
            if a.lane == "l2":
                import graph_common as _G
                dflt = _G.OLAP_BUDGET_S
            elif a.lane == "l1tpc":
                import l1_tpc as _L
                dflt = _L.OLAP_BUDGET_S
            elif a.lane == "l4":
                import l4_tsbs as _T
                dflt = _T.QUERY_BUDGET_S
            if dflt is None:
                raise RuntimeError(f"no lane default known for {a.lane}")
            budget_ceiling = sum(
                _B.budget_for(a.lane, a.tier, q, dflt, None, n_queries=len(want))[0]
                for q in want)
        except Exception:  # noqa: BLE001
            pass

    print(f"{a.lane}/{a.tier}: WHOLE-CELL estimate per engine, cap {cap:.0f} s"
          + (f", projected from {src_tier} x{a.scale_by:g}" if a.scale_by != 1 else ""))
    print(f"  budget ceiling at this tier: {budget_ceiling:.0f} s"
          if budget_ceiling else "  (no budget ceiling known for this lane)")
    print(f"  {'engine':26} {'ingest':>9} {'1st touch':>11} {'total':>9}  {'% cap':>7}  verdict")
    over = 0
    for be in sorted(per):
        # ONLY THE QUERIES THIS TIER WILL RUN. The first version summed every
        # cold_ field in the row, which includes the ones TIER_EXCLUDED drops
        # -- so it scored the excluded work and reported six engines over the
        # cap when the whole point of the exclusion was to bring them under.
        qs = {q: v for q, v in per[be].items() if not want or q in want}
        cold = sum(statistics.median(v) for v in qs.values()) / 1000.0 * a.scale_by
        ing = (statistics.median(ingest[be]) * a.scale_by) if ingest.get(be) else 0.0
        tot = cold + ing + budget_ceiling
        pct = tot / cap * 100
        verdict = "OVER THE CAP" if tot >= cap else ("tight" if pct > 60 else "ok")
        if tot >= cap:
            over += 1
        print(f"  {be:26} {ing:7.0f}s {cold:10.0f}s {tot:8.0f}s  {pct:6.0f}%  {verdict}")
    print(f"\n  {len(per)} engine(s), {over} over the cap")
    print("  total = ingest + first touches + the budget ceiling; the ceiling is")
    print("  what iterations cost if every query uses its whole budget.")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
