#!/usr/bin/env python3
"""Derive per-query time budgets from the bench host's own measured rows.

A budget stops one slow query so the rest of a cell still reports (DECISIONS
#100, #100a). Until 2026-09-18 each lane carried ONE flat constant, which was
wrong in two directions once the corpora were raised (DECISIONS #106): a
query's cost scales with the corpus, and it scales differently per query.
Measured on mini between SF1 and SF10, a tenfold corpus: whole-graph
aggregations grew 11x, most-friends 8.9x, a two-hop from seeds 2.4x, and a
point lookup not at all. One number per lane cannot be right for all of them.

The rule, and it takes engines out of the calculation entirely:

    budget = 3 x (the MEDIAN engine's measured p50 for that query
                  at that tier) x the lane's iteration count

The median, not the slowest, because the slowest is what a budget exists to
bound; the multiplier is the only judgement, and it is the same everywhere.
On the tiers measured so far this covers four or five engines of seven and
censors the genuine outliers, which is what a budget is for.

An engine that ABANDONED the query after its cold pass (budget_lookup.abandon)
is left out of the median. It contributes one cold sample and no warm ones, so
its median is a cold pass masquerading as a p50, and letting it vote would drag
the budget toward the engine the budget exists to bound.

WHERE THE NUMBERS COME FROM. `results/runs_paper.csv`, the frozen rows of the
bench host, by default. Never a laptop: a loaded, throttled laptop runs several
times slower and would hand out budgets nobody needs. `--rows` additionally
accepts a campaign or calibration `.jsonl`, because a tier is usually measured
BEFORE its rows are frozen, and a budget that has to wait for the freeze is a
budget the campaign it bounds never gets:

    python3 derive_budgets.py > budgets.py
    python3 derive_budgets.py --rows results/runs_paper.csv \\
        results/runs_page_<pin>.jsonl > budgets.py

TWO COLUMN SPELLINGS, because the lanes disagree and the disagreement silently
halved this generator's output. The graph lane writes its per-query median as
`<q>_p50_ms`; the document and time-series lanes write theirs as plain
`<q>_ms` with `<q>_p99_ms` beside it. Reading only `*_p50_ms` (as this file did
until 2026-09-19) therefore found the graph lane and nothing else, so every
other lane stayed on its flat constant no matter how many campaigns ran, and
the generated table looked complete because the missing lanes simply did not
appear in it. Both spellings are read now, `_p50_ms` preferred where a lane
writes both.

WHAT IS CHECKED, and why a failure here is a defect rather than a budget. Two
bounds hold a derived number to being a time a query could actually take:

  * it must be at least the FASTEST engine's cold pass at that tier, because a
    budget under the cheapest single touch cannot buy even one iteration, and
  * it must be at most the whole-cell cap for that tier (`TIMEOUT_BY_SCALE`,
    DECISIONS #105), because a budget the cell cannot afford is a cell that
    times out whole and leaves nothing, which is the outcome the budget was
    written to prevent.

The sum of a tier's budgets is reported against the same cap as well: the cap
has to cover every budgeted query of the cell plus its build, which is how
#100a sized the document lane. Failures print to stderr and exit non-zero, so
a table that violates either bound cannot be quietly committed.
"""
import argparse
import ast
import collections
import csv
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "results", "runs_paper.csv")
K = 3.0          # multiplier over the median engine; the one judgement call
FLOOR_S = 60.0   # below this a budget measures scheduler noise, not a query

# The queries a budget applies to: the analytical ones that sweep a corpus.
# Point lookups and per-seed hops do not scale with the corpus (measured) and
# are not budgeted.
BUDGETED = {
    "l2": ("friend_age_by_city", "same_city_edges", "top_degree",
           "degree_dist", "triangles",
           "lsqb_q1", "lsqb_q2", "lsqb_q3", "lsqb_q4", "lsqb_q5",
           "lsqb_q6", "lsqb_q7", "lsqb_q8", "lsqb_q9"),
    "l1tpc": ("q1", "q6", "top_parts", "ship_mode", "by_month"),
    "l4": ("q_last", "q_range", "q_global", "q_groupby", "q_high",
           "q_orderlimit"),
}

# The lane module and the constant naming its iteration count, read from the
# lane rather than typed here.
ITER_CONST = {"l2": ("graph_common", "OLAP_ITERATIONS"),
              "l1tpc": ("l1_tpc", "OLAP_ITER"),
              "l4": ("l4_tsbs", "QITER")}


def _rows(paths):
    """Every clean row from a mix of frozen .csv and campaign/calibration .jsonl."""
    out = []
    for p in paths:
        if p.endswith(".jsonl"):
            with open(p) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        else:
            with open(p) as fh:
                out.extend(csv.DictReader(fh))
    # A row that errored measured nothing; a row from another machine measures
    # another machine (#106). `bench_host` is absent on rows written before the
    # field existed, so only an explicit foreign host is dropped.
    out = [r for r in out
           if not r.get("error")
           and str(r.get("bench_host") or "mini") == "mini"]
    # The frozen CSV and the campaign file that fed it hold the same cells, so
    # reading both would let one cell vote twice. Reduce on the canonical
    # store's key, newest `ts_utc` winning, as the freeze does (RESULTS-MAP).
    keep = {}
    for r in out:
        key = tuple(str(r.get(k)) for k in
                    ("lane", "scale", "n_docs", "workload", "backend", "gav", "rep"))
        if key not in keep or str(r.get("ts_utc", "")) >= str(keep[key].get("ts_utc", "")):
            keep[key] = r
    return list(keep.values())


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _median_ms(row, q):
    """The row's per-query median, under either lane's spelling of it."""
    v = _num(row.get(f"{q}_p50_ms"))
    return v if v is not None else _num(row.get(f"{q}_ms"))


def _cold_ms(row, q):
    """The row's cold pass, under either lane's spelling of it."""
    v = _num(row.get(f"cold_{q}_ms"))
    return v if v is not None else _num(row.get(f"{q}_cold_ms"))


def medians(rows):
    """(lane, tier, query) -> (median engine p50 ms, engines, fastest cold ms)."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    cold = collections.defaultdict(list)
    for r in rows:
        lane = r.get("lane")
        for q in BUDGETED.get(lane, ()):
            # An engine that abandoned after its cold pass does not vote.
            if r.get(f"{q}_abandoned"):
                continue
            v = _median_ms(r, q)
            if v is None:
                continue
            key = (lane, str(r.get("scale")), q)
            by[key][r.get("backend")].append(v)
            c = _cold_ms(r, q)
            if c is not None:
                cold[key].append(c)
    out = {}
    for key, per_engine in by.items():
        per = sorted(st.median(v) for v in per_engine.values())
        out[key] = (st.median(per), len(per_engine),
                    min(cold[key]) if cold[key] else None)
    return out


def _literal_default(path, name):
    """The constant's default, read from the lane's source without importing it.

    The lanes spell these as `int(os.environ.get("BENCH_...") or 100)`, so the
    default is the last integer literal in the assignment. Parsing beats
    importing here because importing a lane drags in its engine clients, which
    a machine deriving budgets need not have.
    """
    tree = ast.parse(open(path).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            ints = [n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, int)]
            if ints:
                return ints[-1]
    raise KeyError(f"{name} not found in {path}")


def iterations(lane):
    """The lane's iteration count, read from the lane rather than typed."""
    mod, const = ITER_CONST.get(lane, (None, None))
    if mod is None:
        return 100
    try:
        return int(getattr(__import__(mod), const))
    except Exception:
        return int(_literal_default(os.path.join(HERE, mod + ".py"), const))


def _seconds(node):
    """One TIMEOUT_BY_SCALE value. The table writes hours as `8 * 3600`, which
    `ast.literal_eval` refuses, so the two operators it uses are folded here."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Add)):
        a, b = _seconds(node.left), _seconds(node.right)
        return a * b if isinstance(node.op, ast.Mult) else a + b
    raise ValueError(ast.dump(node))


def cell_caps():
    """runner.TIMEOUT_BY_SCALE, read without importing the runner."""
    tree = ast.parse(open(os.path.join(HERE, "runner.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "TIMEOUT_BY_SCALE"
                for t in node.targets):
            return {k.value: _seconds(v)
                    for k, v in zip(node.value.keys, node.value.values)}
    return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", nargs="+", default=[FROZEN],
                    help="frozen .csv and/or campaign/calibration .jsonl files")
    args = ap.parse_args()

    rows = _rows(args.rows)
    med = medians(rows)
    caps = cell_caps()
    # The widest roster that ever answered this query, at any tier. A tier that
    # is far below it did not measure a median engine, it measured the ones
    # that survived -- see SURVIVORSHIP below.
    roster = collections.defaultdict(int)
    for (lane, _t, q), (_m, n, _c) in med.items():
        roster[(lane, q)] = max(roster[(lane, q)], n)

    entries, per_tier, bad, withheld = [], collections.defaultdict(float), [], []
    for (lane, tier, q), (m, n, cold) in sorted(med.items(), key=str):
        if q not in BUDGETED.get(lane, ()):
            continue
        # SURVIVORSHIP. A tier where most engines died leaves a median over the
        # fast ones, and a budget derived from it is circular: it censors
        # everything outside the set it was built from, which is the set that
        # survived the previous, looser bound. Measured at TPC-H SF10, where
        # three engines of ten left a row and the other seven timed out whole:
        # the survivors' median was 2.6 s against SF1's ten-engine 10.0 s, so
        # the rule handed a TEN TIMES LARGER corpus a FOUR TIMES SMALLER
        # budget. Withheld, and the lane's constant applies and says so.
        if n * 2 < roster[(lane, q)]:
            withheld.append(f"({lane}, {tier}, {q}): median over {n} engines "
                            f"of the {roster[(lane, q)]} that answer this "
                            f"query elsewhere; a median of the survivors is "
                            f"not the median engine")
            continue
        b = max(FLOOR_S, round(K * m * iterations(lane) / 1000.0 / 10) * 10)
        cap = caps.get(tier)
        if cap is None:
            bad.append(f"({lane}, {tier}, {q}): this tree's runner has no "
                       f"TIMEOUT_BY_SCALE entry for {tier}, so the tier the "
                       f"budget is for cannot be run from here at all")
        if cold is not None and b < cold / 1000.0:
            bad.append(f"({lane}, {tier}, {q}): budget {b:.0f} s is under the "
                       f"fastest engine's cold pass, {cold / 1000.0:.1f} s")
        if cap is not None and b > cap:
            bad.append(f"({lane}, {tier}, {q}): budget {b:.0f} s exceeds the "
                       f"whole-cell cap for {tier}, {cap} s")
        per_tier[(lane, tier)] += b
        entries.append((lane, tier, q, b, m, n))

    print('"""Per-query budgets in seconds, GENERATED by derive_budgets.py.')
    print()
    print("Do not hand-edit: regenerate from the bench host's frozen rows so a")
    print("budget is always something that was measured rather than chosen.")
    print()
    print("Rows read: " + ", ".join(os.path.basename(p) for p in args.rows))
    print('"""')
    print("MEASURED_BUDGETS_S = {")
    for lane, tier, q, b, m, n in entries:
        print(f'    ("{lane}", "{tier}", "{q}"): {b:.0f},'
              f'   # median {m:.1f} ms across {n} engines')
    print("}")
    if withheld:
        print()
        print("# WITHHELD, and the lane's flat constant applies instead. Each")
        print("# of these had rows; none of them had a median engine:")
        for line in withheld:
            print("#   " + line)

    for (lane, tier), tot in sorted(per_tier.items()):
        cap = caps.get(tier)
        if cap is not None and tot > cap:
            bad.append(f"({lane}, {tier}): the tier's budgets total "
                       f"{tot:.0f} s, more than the whole-cell cap {cap} s, "
                       f"so a cell paying all of them cannot finish")
    for line in withheld:
        print("WITHHELD    " + line, file=sys.stderr)
    for line in bad:
        print("IMPLAUSIBLE " + line, file=sys.stderr)
    # A withheld entry has been handled: it is named in the table and the lane
    # falls back. A bound violation has not, so it fails the run.
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
