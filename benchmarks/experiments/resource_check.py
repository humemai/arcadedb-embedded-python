#!/usr/bin/env python3
"""Refuse resource numbers that cannot be right (DECISIONS #193, issue #349).

equivalence_check proves the engines gave the same answer and degenerate_check
that the answer means something. Neither looks at the resource columns, and
those went wrong in ways nothing caught: FalkorDB's relaxed class persists only
when a snapshot rule fires, so a cell that ended first published 0.0 GiB of disk
beside 1.1 GiB for its neighbours; the lifecycle lane deleted each database
after measuring it, so its disk read 0.0 MB at ten million records; and QuestDB's
empty-start footprint holds preallocated files that later shrink, so its growth
went negative. Every one of those was visible in the rows.

What this flags, on the values the page shows (disk: the server container's
growth for a served row, the data written for an embedded one; memory: owned
memory, `peak_owned_mib_sum`, the anonymous plus the shared-memory peak, which is
the page's memory column since issue #353), per (lane, scale, workload,
durability class):

  LOW       an engine whose median is under 1/20 of the median of the group's
            engines (groups of 3 or more engines with a value)
  NEGATIVE  a disk growth below zero
  PRE_DISK  a row that carries `server_pre_disk` (the command the harness runs
            before the final disk reading, `redis-cli SAVE` for a relaxed
            FalkorDB cell) whose text does not contain `rc=0`: the reading was
            taken without the engine having persisted

A flag on a disk value prints the row's `disk_note` when it has one.

NOT FLAGGED, each for a reason the rows state:

  * Failed rows are skipped: the page prints the failure, not their numbers.
    A memory cap that was really hit is already a failed row (an OOM kill), so
    there is no separate cap rule; comparing the client's and the server's
    summed peak with one container's cap flagged every healthy served row.
  * The restart lane is skipped for both metrics: its page table
    (export_web.LANES["restart"]) has timing columns only. The lifecycle lane
    is skipped for disk only: its page table has no disk column (the lane
    removes each database after measuring it, and the embedded database lives
    on a bind mount the disk reading does not see; export_web's lifecycle
    builder says so), but it prints a peak memory column, which is checked.
  * A row that declares its situation or operation unexpressible (a field
    ending in `_unexpressible`, e.g. SurrealDB's lifecycle `graph_gav` and
    `sparse`: it has no analytical view and no sparse index) ran nothing, so
    its numbers are not a measurement and it is not checked. Before this rule
    those rows read about 33 MiB beside 1.3 to 11 GiB in their groups.
  * Every row is a 2026-11 row: a row of another instrument is refused, since
    only that instrument carries the fields this gate reads (`instrument`, and
    the disk fields of #350). The count of rows not checked, and why, is
    printed, so a gate that checked nothing says so.

A flag that has been understood and is right goes in BY_DESIGN with the
reason, so every flag is either a defect or a sentence someone wrote down.

    python3 resource_check.py                     # the canonical frozen set
    python3 resource_check.py --rows results/runs_paper.csv
"""
import argparse
import collections
import statistics
import sys

from equivalence_check import load_rows
from publish_instrument import refuse_other_instruments

LOW_RATIO = 20
MIN_ENGINES = 3
# (lane, backend, metric) -> why a flag is the right number
BY_DESIGN = {
    ("l3d", "sqlite_vec_dense", "memory"): "sqlite-vec reads its vector table through the page cache, which "
                                           "owned memory leaves out for every engine; its total peak is in the row",
    ("l3d", "sqlite_vec_dense_int8", "memory"): "sqlite-vec reads its int8 table through the page cache, which "
                                                "owned memory leaves out for every engine; its total peak is in the row",
}
# lane -> {metric: why it is not checked}. A lane that skips both metrics is
# not checked at all and its rows are counted as such.
SKIP_LANES = {
    "lifecycle": {"disk": "its page table has no disk column (the lane removes each database after measuring it)"},
    "restart": {"disk": "its page table has timing columns only",
                "memory": "its page table has timing columns only"},
}


def _engine(backend):
    """The engine an arm belongs to: the first word of its backend key (arcadedb_embedded and arcadedb_server are both arcadedb)."""
    return str(backend).split("_")[0]


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def failed(r):
    rc = r.get("rc")
    return bool(r.get("error")) or rc not in (None, "", 0, "0", 0.0, "0.0") \
        or str(r.get("oom_killed")) == "True" or str(r.get("server_oom_killed")) == "True"


def disk(r):
    if r.get("server_image"):
        sv, sb = _num(r.get("server_disk_mb")), _num(r.get("server_disk_baseline_mb"))
        return None if sv is None or sb is None else sv - sb
    return _num(r.get("disk_data_mb"))


def memory(r):
    """The page's memory reading of a row: owned memory, or the anonymous peak for a row without it.

    The same rule as export_web._peak_mem. The rows this gate checks (the 2026-11 instrument) all
    carry peak_owned_mib_sum; the fallback only keeps a row without it from reading as no value.
    """
    v = _num(r.get("peak_owned_mib_sum"))
    return v if v is not None else _num(r.get("peak_anon_mib_sum"))


Flag = collections.namedtuple("Flag", "kind key backend metric value ctx")


def check(rows):
    """(flags, not_checked) where not_checked is a Counter of reason -> rows."""
    refuse_other_instruments(rows, "the rows to check")
    flags, not_checked = [], collections.Counter()
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        if failed(r):
            not_checked["the cell failed (its numbers are not printed)"] += 1
            continue
        if any(k.endswith("_unexpressible") and r.get(k) not in (None, "") for k in r):
            not_checked["the row declares its situation unexpressible (it ran nothing)"] += 1
            continue
        lane = r.get("lane")
        if lane in SKIP_LANES and {"disk", "memory"} <= set(SKIP_LANES[lane]):
            not_checked[f"{lane} lane (memory: {SKIP_LANES[lane]['memory']}; disk: {SKIP_LANES[lane]['disk']})"] += 1
            continue
        key = (lane, r.get("scale"), r.get("workload") or "", r.get("durability_class") or "")
        groups[key][r.get("backend")].append(r)
        d = disk(r)
        note = r.get("disk_note")
        if "disk" not in SKIP_LANES.get(lane, ()):
            if d is not None and d < 0:
                flags.append(Flag("NEGATIVE", key, r.get("backend"), "disk", round(d, 1),
                                  f"rep {r.get('rep')}" + (f"; {note}" if note else "")))
            if "server_pre_disk" in r and "rc=0" not in str(r.get("server_pre_disk")):
                flags.append(Flag("PRE_DISK", key, r.get("backend"), "disk", d if d is None else round(d, 1),
                                  f"rep {r.get('rep')}, pre-disk step: {str(r.get('server_pre_disk'))[:80]!r}"
                                  + (f"; {note}" if note else "")))
    for key, bes in groups.items():
        for metric, fn in (("disk", disk), ("memory", memory)):
            if metric in SKIP_LANES.get(key[0], ()):
                continue
            med, notes = {}, {}
            for be, rs in bes.items():
                vals = [v for v in (fn(r) for r in rs) if v is not None]
                if vals:
                    med[be] = statistics.median(vals)
                    notes[be] = next((r["disk_note"] for r in rs if r.get("disk_note")), None) \
                        if metric == "disk" else None
            # THREE ENGINES, NOT THREE ARMS. ArcadeDB's embedded and served arms (and the PQ and int8 siblings of any engine)
            # are one engine measured twice; counted as peers they outvote the group, and a JVM engine's two arms then
            # make an in-process Rust or C engine read as far below "the others" (SurrealDB's lifecycle memory against
            # ArcadeDB's two deployments). The comparison needs three engines before the median means anything.
            if len({_engine(be) for be in med}) < MIN_ENGINES:
                continue
            group = statistics.median(med.values())
            for be, v in med.items():
                if not (group > 0 and v < group / LOW_RATIO):
                    continue
                ctx = f"group median {group:.1f}" + (f"; {notes[be]}" if notes[be] else "")
                flags.append(Flag("LOW", key, be, metric, round(v, 1), ctx))
    return flags, not_checked


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", default="", help="a results .jsonl or .csv to check instead of the canonical set")
    args = ap.parse_args()
    try:
        rows, where = load_rows(args.rows or None)
    except Exception as e:  # noqa: BLE001
        print(f"cannot load rows: {e}")
        return 2
    flags, not_checked = check(rows)
    known = [f for f in flags if (f.key[0], f.backend, f.metric) in BY_DESIGN]
    bad = [f for f in flags if f not in known]
    print(f"rows: {len(rows)} from {where}; checked {len(rows) - sum(not_checked.values())}")
    for why, n in sorted(not_checked.items()):
        print(f"  not checked: {n} rows, {why}")
    for f in sorted(known, key=repr):
        print(f"  KNOWN {f.kind:8} {'/'.join(map(str, f.key)):40} {f.backend:28} {f.metric:6} {f.value!s:>10}  "
              f"{f.ctx}: {BY_DESIGN[(f.key[0], f.backend, f.metric)]}")
    for f in sorted(bad, key=repr):
        print(f"  FAIL  {f.kind:8} {'/'.join(map(str, f.key)):40} {f.backend:28} {f.metric:6} {f.value!s:>10}  {f.ctx}")
    print(f"{'FAIL' if bad else 'ok'}: {len(bad)} resource values that cannot be right, {len(known)} known")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
