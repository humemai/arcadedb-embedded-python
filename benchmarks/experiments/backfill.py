#!/usr/bin/env python3
"""Derive fields the campaign did not record, from artifacts it did keep.

Two fields were missing from rows and are recoverable without re-measuring
anything, because the information was written down elsewhere at the time:

  cell_wall_s   the runner prints every cell's wall time to its job log
                ("l3d_..._r5 3809.7s"), and the token is the run_id. Nothing
                copied it into the row, so `phases_accounted_s` had no
                denominator and the monitor's phase-accounting rule could
                never fire against real data -- a check that looks like a
                clean campaign because it is inert.

  image         the runner writes a manifest per invocation holding every
                image it resolved AND its digest. l3d and l3s stamp the image
                onto their rows; l1, l1tpc and l2 do not, so for three lanes
                the paper's "comparators are pinned by image digest" claim was
                true of the config and unprovable from the artifact.

WHAT THIS IS NOT. It does not re-measure, and it never edits runs.jsonl.
runs.jsonl is the append-only record of what ran; rewriting it would destroy
the thing that makes a backfill auditable. Output goes to a sidecar keyed by
run_id, and every derived field carries a *_source naming where it came from,
so a derived value can never be mistaken for an instrument reading.

NOT RECOVERABLE, and deliberately not attempted here:
  reopen_s              needs a built database, and docker rm -fv destroys it
                        at cell end. Measuring it means building again, which
                        is what lifecycle_probe.py is for.
  phases_accounted_s    needs in-process timers that were not there.
  durability/storage    configuration facts, not measurements. Stamping a
                        config assertion into a field that looks measured is
                        worse than disclosing it in prose. See CAMPAIGN.md.

Usage:
    python3 backfill.py                 # report coverage, write the sidecar
    python3 backfill.py --dry-run       # report only
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(RESULTS, "runs_backfill.jsonl")

# "  [12/40] l3d_arcadedb_dense_server_search_deep10m_r5 3809.7s (0-11) -> ok"
_CELL = re.compile(r"^\s*\[\d+/\d+\]\s+(\S+)\s+([\d.]+)s\s+\(([^)]*)\)\s*->\s*(\S+)")


def wall_times(log_glob):
    """run_id -> wall seconds, from every job log.

    LAST WINS, deliberately. A run_id can appear more than once when a cell was
    re-run, and runs.jsonl keys canonical rows on the latest timestamp, so the
    later log line is the one describing the row that survives.
    """
    out = {}
    for path in sorted(glob.glob(log_glob)):
        try:
            with open(path, errors="ignore") as fh:
                for line in fh:
                    m = _CELL.match(line)
                    if m and m.group(4) == "ok":
                        out[m.group(1)] = (float(m.group(2)), os.path.basename(path))
        except OSError:
            continue
    return out


def manifests():
    """Sorted (ts, images-dict) for every manifest the runner wrote."""
    out = []
    for path in sorted(glob.glob(os.path.join(RESULTS, "manifest-*.json"))):
        ts = os.path.basename(path)[len("manifest-"):-len(".json")]
        # 20260816T160448Z -> 2026-08-16T16:04:48
        iso = (f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}")
        try:
            with open(path) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        out.append((iso, d.get("images") or {}, os.path.basename(path)))
    return out


def manifest_for(ts_utc, mans):
    """The manifest of the invocation a row belongs to: the latest one at or
    before the row's timestamp. A row is always written after its run's
    manifest, so a later manifest belongs to a later invocation."""
    best = None
    for iso, images, name in mans:
        if iso <= (ts_utc or ""):
            best = (images, name)
        else:
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--logs", default=os.path.expanduser("~/q*.log"))
    args = ap.parse_args()

    with open(os.path.join(RESULTS, "runs.jsonl")) as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    walls = wall_times(args.logs)
    mans = manifests()
    print(f"{len(rows)} rows, {len(walls)} cell timings in logs, "
          f"{len(mans)} manifests")

    # VALIDATE THE IMAGE JOIN AGAINST ROWS THAT ALREADY KNOW THE ANSWER.
    # l3d and l3s stamp image themselves. If the manifest join does not
    # reproduce those, the join is wrong and must not be trusted on the lanes
    # that cannot check it. This is the whole reason to backfill image rather
    # than assert it.
    checked = agreed = 0
    for r in rows:
        if not r.get("image"):
            continue
        m = manifest_for(r.get("ts_utc"), mans)
        if not m:
            continue
        checked += 1
        agreed += r["image"] in m[0]
    if checked:
        pct = 100.0 * agreed / checked
        print(f"image-join validation: {agreed}/{checked} rows that already "
              f"record an image find it in their manifest ({pct:.1f}%)")
        if pct < 99.0:
            print("REFUSING: the manifest join does not reproduce known-good "
                  "rows, so it cannot be trusted on rows that cannot check it.")
            return 1
    else:
        print("REFUSING: no rows carry an image, so the join cannot be validated")
        return 1

    # run_id IS NOT UNIQUE ACROSS TIME. It is lane_backend_workload_scale_rep,
    # so every campaign that re-runs a cell writes another row under the same
    # id. A naive join therefore sprays ONE campaign's wall time across every
    # historical row of that cell: 444 log timings "covered" 1767 rows on the
    # first attempt, which is how the defect showed itself.
    #
    # Only the LATEST row per run_id gets a derived wall time. That is exactly
    # the row load_canonical keeps, so the tables get their denominator, and
    # superseded rows keep an honest gap instead of a borrowed number.
    latest = {}
    for r in rows:
        rid = r.get("run_id")
        if rid and (rid not in latest
                    or (r.get("ts_utc") or "") > (latest[rid].get("ts_utc") or "")):
            latest[rid] = r
    canonical_ids = {id(r) for r in latest.values()}

    out = []
    have = defaultdict(int)
    for r in rows:
        rid = r.get("run_id")
        rec = {"run_id": rid, "ts_utc": r.get("ts_utc")}
        w = walls.get(rid) if id(r) in canonical_ids else None
        if w and r.get("cell_wall_s") is None:
            rec["cell_wall_s"] = w[0]
            rec["cell_wall_s_source"] = f"runner log {w[1]}"
            have["cell_wall_s"] += 1
        if not r.get("image"):
            m = manifest_for(r.get("ts_utc"), mans)
            if m:
                # The images dict maps image -> digest. Record the digest map
                # for the whole invocation: which of them a given backend used
                # is knowable from runner.BACKENDS, and asserting one here
                # would be a guess dressed as a measurement.
                rec["image_digests"] = m[0]
                rec["image_digests_source"] = m[1]
                have["image_digests"] += 1
        if len(rec) > 2:
            out.append(rec)

    print()
    for k, v in sorted(have.items()):
        print(f"  {k:20} derived for {v} rows")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    with open(OUT, "w") as fh:
        for rec in out:
            fh.write(json.dumps(rec) + "\n")
    print(f"\nwrote {len(out)} records to {OUT}")
    print("runs.jsonl untouched; join on run_id when reading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
