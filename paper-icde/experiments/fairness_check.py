#!/usr/bin/env python3
"""Check that compared systems were actually given the same thing.

claims_check verifies a number against its own artifact. provenance_check
verifies which engine produced it. Neither asks the question that found three
defects in one afternoon on 2026-07-31: was the row NEXT TO IT given the same
resources and the same treatment?

Every number involved was correct about its own run. That is precisely why
nothing caught them:

  * T5 dense, ArcadeDB got one build and five timed passes with the table
    using passes 2-5, while every comparator got five builds and one pass
    each. Worth 4.0-6.1x.
  * T5 dense, the DEEP-10M envelope was raised from 28g/16g to 36g/24g on
    2026-07-20 and only ArcadeDB was re-measured under it. Worth 29% more
    container memory at the scale where memory decides what stays cached.
  * T5 time series, ArcadeDB's probe took a 30 s settle that no comparator
    was given. Worth 2.23x one way and 2.5x the other.

All three favoured us. The contract they violate is written down in
FAIRNESS.md; this file enforces the parts a machine can.

    python3 fairness_check.py

Exit status is 1 if any invariant fails, so it can gate a regeneration.
"""
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
FULL_CPUSET = "0-11"

# Envelope deliberately not matched, with the reason. An entry here is a
# disclosed override; anything else that differs is a defect. Keyed by
# (lane, scale) -> {backend_substring: why}.
DISCLOSED = {
    ("l3d", "deep10m"): {
        # int8 is reported at its own operating point and the row label says
        # "16 GiB" so a reader sees it. fp32/server sit at 24g.
        "__note__": "int8 row is the 16 GiB cell; the row label names the heap",
    },
}


def _canonical():
    sys.path.insert(0, HERE)
    import make_paper_tables as M
    return M.load_canonical()


def check_cpuset(rows):
    """F1/F2: every published cell on the full cpuset, i.e. serial."""
    print("=== F1/F2: full cpuset, serial tier ===")
    bad = [r for r in rows
           if str(r.get("cpuset")) not in (FULL_CPUSET, "None")]
    seen = collections.Counter(str(r.get("cpuset")) for r in rows)
    print(f"  cpuset distribution across {len(rows)} canonical rows: {dict(seen)}")
    if bad:
        print(f"  FAIL {len(bad)} row(s) on a PARTIAL cpuset, i.e. measured as a")
        print("       parallel sweep worker and not eligible for a table:")
        for r in bad[:10]:
            print(f"         {r.get('lane')} {r.get('scale')} {r.get('backend')} "
                  f"cpuset={r.get('cpuset')}")
        return len(bad)
    print("  ok: no published row came from a parallel shard")
    return 0


def check_envelope(rows):
    """F3: same memory/heap envelope across backends within a (lane, scale)."""
    print("\n=== F3: same memory envelope per (lane, scale) ===")
    g = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        g[(r["lane"], r["scale"])][r["backend"]].add(
            (str(r.get("heap")), str(r.get("mem_cap"))))
    bad = 0
    for key in sorted(g, key=str):
        per_be = g[key]
        envs = {e for s in per_be.values() for e in s}
        if len(envs) == 1:
            h, m = next(iter(envs))
            print(f"  ok   {key[0]:6} {key[1]:8} heap={h} mem={m} "
                  f"({len(per_be)} backends)")
            continue
        bad += 1
        print(f"  FAIL {key[0]:6} {key[1]:8} backends did NOT get the same "
              f"envelope:")
        for be, s in sorted(per_be.items()):
            for h, m in sorted(s):
                print(f"         {be:32} heap={h} mem={m}")
        note = DISCLOSED.get(key, {}).get("__note__")
        if note:
            print(f"         (disclosed override on record: {note})")
        print("         Raising a resource for one engine obliges a re-measure")
        print("         of every engine at that tier. See FAIRNESS.md.")
    return bad


def check_protocol_overlays():
    """F4: overlays that feed tables, and whether their protocol is stated.

    This cannot be fully automated: a protocol lives in a driver, not in the
    JSON. What CAN be checked is the tell that exposed both known cases, a
    single build_s shared by every rep. Five reps of one build_s means one
    build with repeated passes; five distinct values mean independent builds.
    Neither is wrong, but a table must not mix them.
    """
    print("\n=== F4: build protocol per CELL GROUP (one build vs per-rep builds) ===")
    import re
    groups = collections.defaultdict(list)
    for sub in sorted(os.listdir(RESULTS)):
        d = os.path.join(RESULTS, sub)
        if not os.path.isdir(d):
            continue
        for fp in glob.glob(os.path.join(d, "*.json")):
            try:
                obj = json.load(open(fp))
            except Exception:
                continue
            # A cell group is one arm at one tier, so strip the trailing rep
            # index and key on n_docs too. Lumping a whole directory made
            # every multi-tier overlay look "mixed" for innocent reasons, and
            # a check that cries wolf is a check nobody reads.
            stem = re.sub(r"(_rep|_r)\d+\.json$", "", os.path.basename(fp))
            for rec in (obj if isinstance(obj, list) else [obj]):
                if isinstance(rec, dict) and isinstance(
                        rec.get("build_s"), (int, float)):
                    key = (sub, stem, rec.get("n_docs") or rec.get("scale"))
                    groups[key].append(round(rec["build_s"], 1))
    shapes = {}
    for key, builds in sorted(groups.items(), key=str):
        n, distinct = len(builds), len(set(builds))
        if n < 2:
            continue
        shape = ("one-build" if distinct == 1
                 else "per-rep-builds" if distinct == n else "mixed")
        shapes.setdefault(shape, []).append(key)
    for shape in ("one-build", "per-rep-builds", "mixed"):
        keys = shapes.get(shape, [])
        if not keys:
            continue
        print(f"  {shape:15} {len(keys):3} cell group(s)")
        for k in keys[:6]:
            print(f"      {k[0]}/{k[1]}")
        if len(keys) > 6:
            print(f"      ... and {len(keys) - 6} more")
    print("  Neither shape is wrong on its own. It IS a defect when one sits")
    print("  beside the other in a table: T5's dense row prints ArcadeDB's")
    print("  one-build passes 2-5 next to comparators' per-rep-build single")
    print("  pass (#117). queue61 is re-measuring the comparators to match.")
    return 0


def main():
    try:
        rows = _canonical()
    except Exception as e:
        print(f"cannot load canonical rows: {e}")
        return 2
    bad = check_cpuset(rows) + check_envelope(rows)
    check_protocol_overlays()
    print(f"\n{bad} fairness invariant failure(s)")
    if bad:
        print("A comparison is only worth printing if both sides were given")
        print("the same thing. See FAIRNESS.md for the contract and the")
        print("standing list of known violations.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# F6b: published cells come from lane scripts, not bespoke drivers.
#
# FAIRNESS.md's structural finding is that both known protocol violations were
# rows produced by a bespoke driver rather than the lane script, and it states
# the rule "bespoke drivers investigate, lane scripts publish". Until now that
# rule lived only in prose, so honouring it per row was an act of memory by
# whoever promoted a driver's output to a cell. run_conditions() now stamps a
# "producer" field, which makes it checkable.
#
# A row with no producer is NOT passed. Silence is how the overlays got away
# with recording no conditions at all (#113); an unstamped row predates the
# stamp, which is exactly the population that needs looking at.
LANE_SCRIPT = {
    "l1": {"l1_tabular.py"},
    "l1_tpc": {"l1_tpc.py"},
    "l2": {"l2_graph.py", "ldbc_snb.py"},
    "l3s": {"l3_sparse.py"},
    "l3d": {"l3d_dense.py"},
    "l4": {"l4_tsbs.py"},
    "e2": {"e2_hybrid.py"},
    "e4_decomp": {"deployment_decomp_probe.py"},
}


def check_producers(rows):
    """Return (violations, unstamped) for rows that would feed a table."""
    violations, unstamped = [], []
    for r in rows:
        lane = r.get("lane")
        if lane not in LANE_SCRIPT:
            continue
        prod = r.get("producer")
        if not prod:
            unstamped.append((lane, r.get("backend"), r.get("scale")))
        elif prod not in LANE_SCRIPT[lane]:
            violations.append((lane, r.get("backend"), r.get("scale"), prod))
    return violations, unstamped
