"""THE CAP RULE (DECISIONS #188, 2026-10-18): one rule for how long any engine may take at a cell, the same for every engine.

    cell cap = min(the cell's tier cap, max(1800 s, 10 x ref))
    ref      = the slower of (a) the slowest ArcadeDB arm's median cell wall time and (b) the median over all engines'
               medians, for the cell (lane, scale, workload, durability class), from pass-1 timings.

Only ArcadeDB rows define (a) (an arm whose name starts with `arcadedb`), so no ArcadeDB arm is censored by the rule and a
cap never rises. An arm censored (a TIMEOUT, not another failure) at a smaller scale of a lane is censored at every larger
scale of the same lane, workload and class (SCALE_CHAINS says which scales are smaller), and its overlay is not run where its
lane cell was censored. At report time the same rule applies to rows already measured (`over_rule`).

This file computes the rule from the bench host's log (the cell lines `  [i/n] <cell> <secs>s (<cpuset>) -> <status>`) and
writes cap_rule_2610.json, which make_2610_stages.py (run-time caps and seeding) and export_web.py (report-time censoring)
read. Run:  python3 cap_rule.py --status STATUS.txt --from-line 45558 --out cap_rule_2610.json
"""
import argparse
import collections
import json
import pathlib
import re
import statistics

HERE = pathlib.Path(__file__).resolve().parent
RULE_JSON = HERE / "cap_rule_2610.json"
K, FLOOR_S = 10, 1800
DECISION = "DECISIONS #188"

# Which scales of a lane are smaller than which: a scale is smaller than another only inside one chain. The restart lane runs
# four corpora, each with its own two sizes, and tpch1 is not "smaller" than ts1000.
SCALE_CHAINS = {
    "l1tpc": [["tpch1", "tpch10"]],
    "l2": [["sf1", "sf10", "sf1full"]],
    "l3d": [["small", "deep10m"]],
    "l3s": [["tiny", "small", "medium"]],
    "l4": [["ts100", "ts1000"]],
    "lifecycle": [["lc10k", "lc100k", "lc1m", "lc10m"]],
    "restart": [["tpch1", "tpch10"], ["sf1", "sf10"], ["small", "deep10m"], ["ts100", "ts1000"]],
    "e2": [["e2", "e2_500k"]],
    "e4": [["e2"]],
}
LANES = ("lifecycle", "restart", "l1tpc", "l2", "l3d", "l3s", "l4", "e2", "e4")
CELL_LINE = re.compile(r"^\s+\[\d+/\d+\] (\S+) ([\d.]+)s \([^)]*\) -> (\S+)")


def is_arcadedb(backend):
    return backend.startswith("arcadedb")


def key_of(lane, scale, workload, cls):
    return f"{lane}|{scale}|{workload}|{cls}"


def smaller_scales(lane, scale):
    """The scales of the lane that are smaller than `scale`, in the chain `scale` is in."""
    for chain in SCALE_CHAINS.get(lane, []):
        if scale in chain:
            return chain[:chain.index(scale)]
    return []


def known_backends():
    import make_2610_stages as G   # the registry of every arm any stage runs
    out = set()
    for spec in G.STAGES:
        out |= set(G.stage_backends(spec))
    return sorted(out | {"surrealdb_lifecycle"}, key=len, reverse=True)


def parse_cells(lines, backends):
    """One dict per `[i/n]` cell line: lane, backend, workload, scale, rep, class ("" or "strict"), secs, status."""
    scales = sorted({s for chains in SCALE_CHAINS.values() for c in chains for s in c}, key=len, reverse=True)
    cells = []
    for ln in lines:
        m = CELL_LINE.match(ln)
        if not m:
            continue
        name, secs, status = m.group(1), float(m.group(2)), m.group(3)
        lane = next((l for l in LANES if name.startswith(l + "_")), None)
        if not lane:
            continue
        rest = name[len(lane) + 1:]
        be = next((b for b in backends if rest.startswith(b + "_")), None)
        if not be:
            continue
        rest = rest[len(be) + 1:]
        mm = re.match(r"(.*?)_?(" + "|".join(map(re.escape, scales)) + r")_r(\d+)(.*)$", rest)
        if not mm:
            continue
        cells.append(dict(lane=lane, backend=be, workload=mm.group(1), scale=mm.group(2), rep=int(mm.group(3)),
                          cls="strict" if mm.group(4) == "_dstrict" else "", secs=secs, status=status))
    return cells


def compute(cells):
    arms = collections.defaultdict(lambda: collections.defaultdict(list))   # cell key -> backend -> [(rep, secs, status)]
    for c in cells:
        arms[key_of(c["lane"], c["scale"], c["workload"], c["cls"])][c["backend"]].append((c["rep"], c["secs"], c["status"]))
    caps, over, timeouts = {}, [], []
    for key in sorted(arms):
        lane, scale, wl, cls = key.split("|")
        med = {}
        for be, reps in arms[key].items():
            ok = [s for _, s, st in reps if st.startswith("ok")]
            if ok:
                med[be] = statistics.median(ok)
            first = [st for r, _, st in sorted(reps) if r == 1]
            if first and first[0].startswith("timeout_after_"):
                timeouts.append(dict(lane=lane, scale=scale, backend=be, workload=wl, cls=cls,
                                     cap_s=int(first[0].rsplit("_", 1)[1].rstrip("s"))))
        arc = [m for b, m in med.items() if is_arcadedb(b)]
        if not arc:
            continue    # no ArcadeDB reference, no rule for the cell
        ref_arc, ref_med = max(arc), statistics.median(list(med.values()))
        cap = int(round(max(FLOOR_S, K * max(ref_arc, ref_med))))
        caps[key] = dict(cap_s=cap, arcadedb_max_median_s=round(ref_arc, 1), engine_median_s=round(ref_med, 1),
                         n_engines=len(med))
        for be, m in sorted(med.items()):
            if not is_arcadedb(be) and m > cap:
                over.append(dict(lane=lane, scale=scale, backend=be, workload=wl, cls=cls, median_s=round(m, 1), cap_s=cap))
    return dict(rule=dict(k=K, floor_s=FLOOR_S, decision=DECISION), caps=caps, over_rule=over,
                timeouts=sorted(timeouts, key=lambda t: (t["lane"], t["workload"], t["backend"], t["cls"], t["scale"])))


_CACHE = {}


def load(path=None):
    """The committed rule data, or None when the file is absent (a checkout that predates it behaves as before)."""
    p = pathlib.Path(path) if path else RULE_JSON
    if p not in _CACHE:
        _CACHE[p] = json.loads(p.read_text()) if p.exists() else None
    return _CACHE[p]


def rule_cap(lane, scale, workload, cls="", data=None):
    data = data if data is not None else load()
    if not data:
        return None
    c = data["caps"].get(key_of(lane, scale, workload, cls))
    return c["cap_s"] if c else None


def censored_scales(data=None):
    """{(lane, backend, workload, cls): [scale, ...]} for every arm-cell the rule censored in pass 1: a timeout of rep 1 or a
    median over the rule cap. The smallest is the one a larger scale cites."""
    data = data if data is not None else load()
    out = collections.defaultdict(set)
    if data:
        for e in list(data["over_rule"]) + list(data["timeouts"]):
            out[(e["lane"], e["backend"], e["workload"], e["cls"])].add(e["scale"])
    return {k: sorted(v) for k, v in out.items()}


def censored_before(lane, scale, backend, workload, cls="", data=None):
    """The smallest scale below `scale`, in its chain, at which the arm is censored in the rule data, else None."""
    have = censored_scales(data).get((lane, backend, workload, cls), [])
    for s in smaller_scales(lane, scale):
        if s in have:
            return s
    return None


def applies_to(data, pin):
    """The rule data is for one pin's pass 1 (its `rule.pin`); a publish for another pin does not read it."""
    if not data:
        return False
    want = str(data["rule"].get("pin") or "")
    pin = str(pin or "").strip()
    return not want or (bool(pin) and (pin.startswith(want) or want.startswith(pin)))


def over_rule_cells(data):
    """{(lane, scale, backend, workload): rule cap in seconds} of the relaxed-class arm-cells whose pass-1 median is over the rule cap (what a
    table, which prints the relaxed class, withholds; a strict-class cell belongs to the durability table)."""
    return {(e["lane"], e["scale"], e["backend"], e["workload"]): e["cap_s"] for e in data["over_rule"] if not e["cls"]}


def larger_scales(lane, scale):
    for chain in SCALE_CHAINS.get(lane, []):
        if scale in chain:
            return chain[chain.index(scale) + 1:]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--status", required=True)
    ap.add_argument("--from-line", type=int, default=1, help="1-based first line of the log to read (pass 1 starts at the qP01 START line)")
    ap.add_argument("--out", default=str(RULE_JSON))
    ap.add_argument("--pin", default="d36b4ca3a", help="the engine pin of the pass-1 rows (export_web reads the data only for it)")
    a = ap.parse_args(argv)
    lines = pathlib.Path(a.status).read_text(errors="replace").splitlines()[a.from_line - 1:]
    cells = parse_cells(lines, known_backends())
    data = compute(cells)
    data["rule"].update(pin=a.pin, source="pass-1 cell lines of the bench host's STATUS.txt", cell_runs=len(cells))
    pathlib.Path(a.out).write_text(json.dumps(data, indent=0, sort_keys=True) + "\n")
    print(f"{len(cells)} cell runs, {len(data['caps'])} capped cells, {len(data['over_rule'])} over the rule, "
          f"{len(data['timeouts'])} timeouts -> {a.out}")


if __name__ == "__main__":
    main()
