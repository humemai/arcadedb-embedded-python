#!/usr/bin/env python3
"""Flag agreed answers that cannot mean anything (a report, not a gate).

equivalence_check proves the engines AGREE. It cannot say the agreed answer is
worth agreeing on, and twice now it was not: every LDBC age loaded as 0, so the
filtered three-hop read matched nobody on nine engines for two months (BUGS
F146), and the graph analytics triangle count is 0 on every engine on the LDBC
projection, because each friendship is stored once from the smaller id to the
larger and a directed 3-cycle cannot exist in that graph (validity hunt
2026-10-04). Both were visible in the rows; nothing looked.

What this flags, per (lane, workload, scale, query), on the majority digest:

  ZERO       a one-row answer whose every value is 0 or null
  CONSTANT   a value column with one distinct value over 10 or more rows
             (needs res_<q>_profile, which bench_common.record_result writes
             from this change on; older rows are checked for ZERO only)
  SCALE      the same digest at two scales for a read whose answer should
             depend on the data
  EMPTY      a read that returned no rows

Answers that are constant BY DESIGN are listed in BY_DESIGN with the reason, so
a flag is either a defect or a sentence someone wrote down.

    python3 degenerate_check.py results/runs.jsonl [--instrument 2026-10]
"""
import argparse
import ast
import collections
import csv
import json
import sys

NULL = "<null>"
# (lane, query, column or None) -> why the answer is constant by construction
BY_DESIGN = {
    ("e2", "retrieval_docs", "views"): "the read paths run before the write loop, so every views counter is 0 (#82c)",
    ("e2", "retrieval_hops", "n_docs"): "the generator gives every product EDGES_PER = 3 outgoing edges",
    ("e2", "filtered_candidates", "n_candidates"): "three hops of three out-edges: at most 3 + 9 + 27 = 39 candidates",
    ("l1tpc", "crud_delete", None): "the post-delete state is empty by definition",
    ("l2", "graph_delete", None): "the post-delete state is empty by definition",
    ("l1tpc", "crud_insert", "qty"): "every insert writes qty 1",
    ("l1tpc", "crud_read", "qty"): "every insert writes qty 1",
    ("l1tpc", "crud_update", "qty"): "every update writes qty 2",
    ("l1tpc", "neworder", "qty"): "every order is for one unit",
    ("l1tpc", "neworder", "paid"): "nothing is paid before the payment phase",
    ("l1tpc", "payment", "qty"): "every order is for one unit",
    ("l2", "graph_insert", "age"): "every insert writes age 33",
    ("l2", "graph_insert", "city"): "every insert writes city_0",
    ("l2", "graph_update", "age"): "every update writes age 44",
    ("l2", "graph_update", "city"): "every insert writes city_0",
    ("lifecycle", "lifecycle_read", None): "each situation's read is a fixed-size probe; compared within a deployment (F167)",
}
KEYLIKE = {"id", "pid", "start", "okey", "ckey", "pkey", "name", "l_partkey", "l_returnflag", "l_linestatus",
           "l_shipmode", "m", "h", "host", "ts", "c", "deg"}
WRITE_STATES = {"crud_insert", "crud_read", "crud_update", "crud_delete", "neworder", "payment",
                "graph_insert", "graph_update", "graph_delete"}


def load(path, instrument):
    rows = []
    if path.endswith(".csv"):
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        with open(path) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if not instrument or r.get("instrument") == instrument]


def by_design(lane, q, col):
    return BY_DESIGN.get((lane, q, col)) or BY_DESIGN.get((lane, q, None))


def self_test():
    """October's three F146 answers, profiled the way record_result now does, must each be flagged."""
    import os
    import tempfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bench_common as B
    import graph_common as G
    out = {"lane": "l2", "workload": "oltp", "scale": "sf1", "instrument": "t"}
    B.record_result(out, "point", [{"name": f"p{i}", "age": 0} for i in range(500)], **G.READ_DIGEST["point"])
    B.record_result(out, "hop1", [{"n": i % 7, "a": (0.0 if i % 7 else None)} for i in range(500)], **G.READ_DIGEST["hop1"])
    B.record_result(out, "hop3f", [{"n": 0} for _ in range(500)], **G.READ_DIGEST["hop3f"])
    B.record_result(out, "hop2", [{"n": i} for i in range(500)], **G.READ_DIGEST["hop2"])
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(out) + "\n")
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sys.argv = ["degenerate_check.py", f.name, "--instrument", "t"]
        main()
    text = buf.getvalue()
    want = ["l2/oltp/sf1/point: column 'age'", "l2/oltp/sf1/hop1: column 'a'", "l2/oltp/sf1/hop3f: column 'n'"]
    missing = [w for w in want if w not in text]
    bad = "l2/oltp/sf1/hop2" in text
    print(text, end="")
    print("self-test", "FAIL" if (missing or bad) else "ok", missing, "hop2 flagged" if bad else "")
    return 1 if (missing or bad) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--instrument", default="2026-10")
    a = ap.parse_args()
    groups = collections.defaultdict(lambda: collections.Counter())
    keep = {}
    for r in load(a.rows, a.instrument):
        for k, v in r.items():
            if not (k.startswith("res_") and k.endswith("_digest")) or not v or str(v).startswith("unexpressible"):
                continue
            q = k[4:-7]
            key = (r.get("lane"), r.get("workload"), r.get("scale"), q)
            groups[key][v] += 1
            prof = r.get(f"res_{q}_profile")
            if isinstance(prof, str) and prof.startswith("{"):
                # JSONL carries a dict; a CSV (the freeze) carries its Python repr, single quotes and all
                try:
                    prof = json.loads(prof)
                except ValueError:
                    prof = ast.literal_eval(prof)
            keep.setdefault((key, v), (r.get(f"res_{q}_sample"), int(r.get(f"res_{q}_n") or 0), prof))
    flags = []
    scale_digests = collections.defaultdict(dict)
    for key, ctr in sorted(groups.items(), key=lambda kv: str(kv[0])):
        lane, wl, scale, q = key
        dig = ctr.most_common(1)[0][0]
        sample, n, prof = keep[(key, dig)]
        scale_digests[(lane, wl, q)][scale] = dig
        if n == 0:
            if not by_design(lane, q, None):
                flags.append(("EMPTY", key, "no rows", sample))
            continue
        if n == 1 and sample:
            vals = sample.strip("()").split(",")
            if all(v.strip() in ("0", NULL) for v in vals) and not by_design(lane, q, None):
                flags.append(("ZERO", key, f"the one answer is {sample}", sample))
        for col, p in (prof or {}).items():
            if col in KEYLIKE or n < 10:
                continue
            if by_design(lane, q, col):
                continue
            if p.get("zero_or_null") == n:
                flags.append(("CONSTANT", key, f"column {col!r} is 0 or null in all {n} rows", sample))
            elif p.get("distinct") == 1:
                flags.append(("CONSTANT", key, f"column {col!r} has one value over {n} rows", sample))
    for (lane, wl, q), per in scale_digests.items():
        if len(per) > 1 and len(set(per.values())) < len(per) and q not in WRITE_STATES and not by_design(lane, q, None):
            same = [s for s, d in per.items() if list(per.values()).count(d) > 1]
            flags.append(("SCALE", (lane, wl, ",".join(sorted(same)), q), "the same answer at these scales", None))
    for kind, key, why, sample in flags:
        print(f"{kind:9s} {'/'.join(str(x) for x in key)}: {why}" + (f"   sample {sample}" if sample else ""))
    print(f"{len(flags)} flag(s) over {len(groups)} answers")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if sys.argv[1:] == ["--self-test"] else main())
