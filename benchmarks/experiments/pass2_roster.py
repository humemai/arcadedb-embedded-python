#!/usr/bin/env python3
"""The pass-2 roster (DECISIONS #164 item 5): which arms of a pin's rows file have finished reps 1 to 3 cleanly.

Pass 1 of the 26.10.1 measurement runs reps 1 to 3 of every arm. Pass 2 tops the arms up with reps 4 and 5, and its
roster comes from the rows, not from the stage list: an arm whose rep 1 left no clean row (a cell that hit its cap, an
out-of-memory kill, a crash) never repeats, because repeating it would spend its cap a second and third time to publish
the same censored cell. `make_2610_stages.py --rep-from 4 --roster ROSTER.json` reads this script's output.

What counts, stated so a reader can falsify it against a row:

  * A CLEAN ROW has rc == 0, no `error`, no OOM kill (`oom_killed`, `server_oom_killed`), the paper tier, and the serial
    cpuset (`0-11` or none), the same filter `make_paper_tables.load_canonical` applies before it dedupes. A row that
    finished but records censored queries is clean: it left a row inside the cap, and the table prints its censoring.
  * An arm CELL is (lane, scale, workload, backend, durability class, arm). The class is the durability class the cell asked
    for (`relaxed` when the row says nothing); the arm is the row's `backend_arm` (`nogav` for the no-view graph arm) or
    empty. Two rows of one cell are two repetitions of one arm, never two arms.
  * A cell is ELIGIBLE when reps 1, 2 and 3 each have at least one clean row. The roster lists the clean reps it found,
    including reps above 3, so a pass-2 stage that was stopped half way is regenerated without repeating a finished rep.
  * Everything else is listed under `ineligible` with the clean reps it has and the last error it recorded, so the outcome
    accounting (eligible plus ineligible equals every cell in the file) can be checked against the stage logs.

The wall time per repetition, for the pass-2 hours projection, comes from the rows alone. A row's `ts_utc` is the START of
its cell (runner.run_cell stamps it before the first container starts), and a stage runs one cell at a time, so the time
from the first row of a run of consecutive rows of one cell to the first row of the next cell, divided by the rows in the
run, is the cost of one repetition INCLUDING whatever the stage runs after the lane cell for that arm (the multipass
overlay of the dense and sparse lanes) and the stage's own overhead when the arm is the last of its stage. It is an
estimate, said so in the output, and a run that is longer than twice the cell's cap plus 30 minutes is not counted.

Usage:
  python3 pass2_roster.py results/runs_page_<pin>.jsonl -o roster.json
  python3 pass2_roster.py results/runs_page_<pin>.jsonl --summary
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import statistics
import sys
from datetime import datetime

FORMAT = "pass2-roster-1"
NEED_REPS = (1, 2, 3)
# a claim between 1/BAND and BAND is the kind a median of three cannot settle (DECISIONS #164: under about 1.3x waits for the top-up)
BAND = 1.3
SLACK_S = 1800.0
SERIAL_CPUSETS = ("0-11", "None")
# the metrics a lane's ArcadeDB-versus-comparator closeness is read from: every non-warm, non-cold p50, and the three build costs
METRIC_RE = re.compile(r"^(?!warm_|cold_).+_p50_ms$")
METRIC_NAMES = ("build_s", "ingest_s", "index_s")
# sensitivity arms are not part of the comparison the ordering is about
NOT_COMPARED = ("arcadedb_imgdefaults",)


def load_rows(path):
    """(rows, n_bad_lines) from a jsonl file. A line that does not parse is counted, never dropped silently."""
    rows, bad = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
    return rows, bad


def is_clean(r, cpusets=SERIAL_CPUSETS):
    """A row that left a measurement: rc 0, no error, no OOM kill, paper tier, serial cpuset, a repetition number."""
    rep = r.get("rep")
    return (r.get("rc") == 0 and not r.get("error") and not r.get("oom_killed") and not r.get("server_oom_killed")
            and r.get("tier", "paper") == "paper" and str(r.get("cpuset")) in cpusets
            and isinstance(rep, int) and not isinstance(rep, bool) and rep >= 1)


def cell_key(r):
    """(lane, scale, workload, backend, durability class, arm): the repetitions of one arm share it."""
    return (r.get("lane"), r.get("scale"), r.get("workload"), r.get("backend"),
            r.get("durability_class") or "relaxed", r.get("backend_arm") or "")


def _ts(r):
    return datetime.fromisoformat(str(r.get("ts_utc")))


def wall_per_rep(rows, caps=None):
    """{cell key: median seconds per repetition} from the gaps between consecutive cells (see the module docstring)."""
    stamped = [r for r in rows if r.get("ts_utc")]
    ordered = sorted(stamped, key=_ts)
    runs = []
    for r in ordered:
        k = cell_key(r)
        if runs and runs[-1][0] == k:
            runs[-1][1].append(r)
        else:
            runs.append((k, [r]))
    out = collections.defaultdict(list)
    for i in range(len(runs) - 1):
        key, members = runs[i]
        span = (_ts(runs[i + 1][1][0]) - _ts(members[0])).total_seconds()
        per = span / len(members)
        cap = (caps or {}).get(key[1])
        if per <= 0 or (cap is not None and per > 2 * float(cap) + SLACK_S):
            continue
        out[key].append(per)
    return {k: (statistics.median(v), len(v)) for k, v in out.items()}


def _medians(rows):
    """{(lane, scale, workload, class, backend, metric): median over the clean reps 1..3}, ArcadeDB's no-view arm left out."""
    vals = collections.defaultdict(list)
    for r in rows:
        if not is_clean(r) or r.get("rep") not in NEED_REPS or r.get("backend_arm"):
            continue
        for k, v in r.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0 or not math.isfinite(v):
                continue
            if METRIC_RE.match(k) or k in METRIC_NAMES:
                vals[(r["lane"], r["scale"], r["workload"], r.get("durability_class") or "relaxed", r["backend"], k)].append(v)
    return {k: statistics.median(v) for k, v in vals.items()}


def closeness(rows, band=BAND):
    """{'lane|scale|workload': {comparator: {comparisons, within_band, closest}}}: the ArcadeDB-versus-comparator ratios of
    the rows so far, per comparator, so a pass can count only the comparators it runs. `within_band` counts the ratios inside
    the band a median of three cannot settle; `closest` is the ratio nearest 1. A group with no comparison is absent."""
    med = _medians(rows)
    groups = collections.defaultdict(lambda: collections.defaultdict(dict))
    for (lane, scale, wl, cls, be, metric), v in med.items():
        groups[(lane, scale, wl)][(cls, metric)][be] = v
    out = {}
    for (lane, scale, wl), by in groups.items():
        per = {}
        for (cls, metric), per_be in by.items():
            ours = {b: v for b, v in per_be.items() if b.startswith("arcadedb") and not b.startswith(NOT_COMPARED)}
            theirs = {b: v for b, v in per_be.items() if not b.startswith("arcadedb")}
            for a, va in ours.items():
                for c, vc in theirs.items():
                    ratio = va / vc
                    rec = per.setdefault(c, {"comparisons": 0, "within_band": 0, "closest": None})
                    rec["comparisons"] += 1
                    rec["within_band"] += 1 if 1 / band <= ratio <= band else 0
                    cl = rec["closest"]
                    if cl is None or abs(math.log(ratio)) < abs(math.log(cl["ratio"])):
                        rec["closest"] = {"ratio": round(ratio, 3), "arcadedb": a, "metric": metric, "class": cls}
        if per:
            out[f"{lane}|{scale}|{wl}"] = per
    return out



def normalize_engine_version(value):
    """The bare version of an engine_version field. Embedded arms record '26.10.1'; served arms record
    'server:26.10.1 (build <sha>/<ts>/main)': one version, two spellings (the pin check counts versions, not spellings)."""
    text = str(value)
    if text.startswith("server:"):
        text = text[len("server:"):]
    return text.split(" (", 1)[0].strip()


def build_roster(rows, source="", need=NEED_REPS, caps=None, bad_lines=0):
    """The roster document: eligible cells per lane per backend, the ineligible ones with why, the wall estimates and the
    closeness table. Pure function of the rows."""
    need = tuple(need)
    clean = collections.defaultdict(set)
    seen = collections.defaultdict(set)
    last_error = {}
    for r in rows:
        k = cell_key(r)
        if r.get("rep") is not None:
            seen[k].add(r.get("rep"))
        if is_clean(r):
            clean[k].add(r["rep"])
        elif r.get("error"):
            last_error[k] = " ".join(str(r["error"]).split())[:120]
    wall = wall_per_rep(rows, caps)
    lanes = collections.defaultdict(lambda: collections.defaultdict(list))
    inel = collections.defaultdict(lambda: collections.defaultdict(list))
    for k in sorted(set(clean) | set(seen), key=str):
        lane, scale, wl, be, cls, arm = k
        have = sorted(clean.get(k, ()))
        rec = {"scale": scale, "workload": wl, "durability_class": cls, "arm": arm, "clean_reps": have}
        if set(need) <= set(have):
            w = wall.get(k)
            rec["wall_s_per_rep"] = round(w[0], 1) if w else None
            rec["wall_obs"] = w[1] if w else 0
            lanes[lane][be].append(rec)
        else:
            rec["reps_seen"] = sorted(seen.get(k, ()))
            rec["last_error"] = last_error.get(k)
            inel[lane][be].append(rec)
    version = collections.Counter(
        normalize_engine_version(r.get("engine_version")) for r in rows
        if str(r.get("backend", "")).startswith("arcadedb") and r.get("engine_version") is not None)
    return {
        "format": FORMAT, "source": source, "n_rows": len(rows), "bad_lines": bad_lines, "need_reps": list(need),
        "clean_rule": "rc == 0, no error, no OOM kill, paper tier, cpuset 0-11 or unset",
        "engine_commits": dict(collections.Counter(str(r.get("engine_commit")) for r in rows)),
        "arcadedb_engine_versions": dict(version),
        "wall_estimate_note": "seconds per repetition from the gaps between consecutive cells' ts_utc (an estimate, "
                              "overlay and stage overhead included)",
        "band": BAND,
        "lanes": {l: {b: v for b, v in sorted(d.items())} for l, d in sorted(lanes.items())},
        "ineligible": {l: {b: v for b, v in sorted(d.items())} for l, d in sorted(inel.items())},
        "closeness": closeness(rows),
    }


def summary(roster):
    lines = [f"roster from {roster['source'] or '(rows)'}: {roster['n_rows']} rows, "
             f"{sum(len(v) for d in roster['lanes'].values() for v in d.values())} eligible cells "
             f"(reps {roster['need_reps']} all clean), "
             f"{sum(len(v) for d in roster['ineligible'].values() for v in d.values())} ineligible"]
    for lane in sorted(set(roster["lanes"]) | set(roster["ineligible"])):
        e = roster["lanes"].get(lane, {})
        i = roster["ineligible"].get(lane, {})
        lines.append(f"  {lane:10} eligible {sum(len(v) for v in e.values()):4} cells in {len(e):2} arms; "
                     f"ineligible {sum(len(v) for v in i.values()):4} cells")
        for be, cells in sorted(i.items()):
            for c in cells[:3]:
                lines.append(f"      not topped up: {be} {c['scale']}/{c['workload']}/{c['durability_class']}"
                             f"{'/' + c['arm'] if c['arm'] else ''} clean reps {c['clean_reps']}"
                             f"{', ' + c['last_error'] if c.get('last_error') else ''}")
    return "\n".join(lines)


def _caps():
    """runner.TIMEOUT_BY_SCALE when the harness is importable; the estimate then drops runs longer than a cell can last."""
    try:
        import runner
        return dict(runner.TIMEOUT_BY_SCALE)
    except Exception:  # noqa: BLE001 - a missing harness only loses a sanity bound
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rows", help="a pin's rows file, results/runs_page_<pin>.jsonl")
    ap.add_argument("-o", "--out", help="write the roster JSON here")
    ap.add_argument("--min-reps", type=int, default=3, help="reps 1..N must each have a clean row (default 3)")
    ap.add_argument("--summary", action="store_true", help="print the per-lane counts and the cells left out")
    a = ap.parse_args(argv)
    rows, bad = load_rows(a.rows)
    if not rows:
        raise SystemExit(f"{a.rows} holds no rows")
    roster = build_roster(rows, source=a.rows.rsplit("/", 1)[-1], need=range(1, a.min_reps + 1), caps=_caps(), bad_lines=bad)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(roster, fh, indent=1, sort_keys=True)
            fh.write("\n")
    if a.summary or not a.out:
        print(summary(roster))
    if bad:
        print(f"WARNING: {bad} line(s) of {a.rows} did not parse", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
