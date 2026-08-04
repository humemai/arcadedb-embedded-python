#!/usr/bin/env python3
"""Merge a campaign's rows from the bench host into the canonical store.

WHY THIS IS A SCRIPT AND NOT A SCP. Twice on 2026-08-04 a campaign finished and
its data then sat unused while the paper kept printing superseded numbers: q8's
30 sparse cells were complete for 90 minutes before anything read them, and
T5's dense block was hand-built from files that had never left the bench host.
Measuring is not the last step; being READ is. This closes that gap in a way
that can be re-run at every re-pin instead of remembered.

WHY APPEND, NEVER REPLACE. runner.py opens runs.jsonl in append mode, so the
bench host accumulates only the rows from the current campaign. The canonical
store on the workstation holds the full history, including every comparator
(Qdrant, Milvus, Elasticsearch, Neo4j, Ladybug, DuckDB, Postgres) that this
campaign did not re-run. Replacing would delete all of them. Appending is also
sufficient: the canonical-row rule is newest ts_utc per
(lane, backend, scale, workload, rep), so a fresh 26.8.1 row supersedes its
dev-era predecessor automatically. "Remove the dev runs" therefore needs no
deletion at all, which is the only version of that instruction that cannot
lose data.

SAFETY: refuses to write if the merge would reduce the canonical row count, and
always writes a timestamped backup first.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANON = os.path.join(HERE, "results", "runs.jsonl")


def load(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def key(r):
    return (r.get("lane"), r.get("backend"), r.get("scale"),
            r.get("workload"), r.get("rep"))


def canonicalise(rows):
    """Newest ts_utc wins per cell. The rule the tables already apply."""
    best = {}
    for r in rows:
        k = key(r)
        if k not in best or str(r.get("ts_utc")) > str(best[k].get("ts_utc")):
            best[k] = r
    return best


def version_of(r):
    return str(r.get("engine_version") or r.get("wheel_version") or "?")


# The (lane, scale) pairs the paper actually prints. Everything else is an
# exploration tier whose version nobody reads, and reporting it alongside makes
# a clean re-pin look dirty: l2 keeps dev-era rows at micro/tiny/small/medium
# forever, because T3 prints sf1 and sf10 and those tiers are never re-run.
PUBLISHED = {("l1", "medium"), ("l1tpc", "tpch1"), ("l1tpc", "tpch10"),
             ("l2", "sf1"), ("l2", "sf10"), ("e2", "e2")}

# l3s and l3d are deliberately absent. Their released measurements live in
# results/sparse_2681/ and results/dense_mp_2681/, which make_paper_tables reads
# directly and which never enter runs.jsonl. Their rows here are dead weight,
# and reporting them as "still on dev" would be true and misleading at once.
OUT_OF_STORE = {"l3s", "l3d"}


def report(before, after):
    lanes = sorted({k[0] for k in after if k[0]})
    print("  %-7s %-30s %s" % ("lane", "arcadedb version BEFORE", "AFTER"))
    for lane in lanes:
        if lane in OUT_OF_STORE:
            print("  %-7s %s" % (lane, "(not in this store; reads "
                                       "results/{sparse,dense_mp}_2681)"))
            continue
        def vers(d):
            return sorted({version_of(r) for k, r in d.items()
                           if k[0] == lane and (k[0], k[2]) in PUBLISHED
                           and "arcade" in str(k[1]).lower()})
        b, a = vers(before), vers(after)
        if not b and not a:
            continue
        mark = "" if b == a else "   <-- moved"
        print("  %-7s %-30s %s%s" % (lane, ", ".join(b)[:30] or "-",
                                     ", ".join(a)[:36] or "-", mark))
    print("  (published tiers only: %s)" % ", ".join(
        sorted(f"{l}/{s}" for l, s in PUBLISHED)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="mini")
    ap.add_argument("--remote", default="~/repos/humemai/arcadedb-embedded-python/"
                                        "benchmarks/experiments/results/runs.jsonl")
    ap.add_argument("--from-file", help="skip scp, merge this local file instead")
    ap.add_argument("--apply", action="store_true",
                    help="write the merge; default is a dry run")
    a = ap.parse_args()

    if a.from_file:
        incoming_path = a.from_file
    else:
        incoming_path = "/tmp/incoming_runs.jsonl"
        rc = subprocess.run(["scp", "-q", f"{a.host}:{a.remote}", incoming_path])
        if rc.returncode != 0:
            sys.exit(f"scp from {a.host} failed")

    incoming = load(incoming_path)
    existing = load(CANON)
    if not incoming:
        sys.exit("nothing to merge: incoming file is empty")

    before = canonicalise(existing)
    after = canonicalise(existing + incoming)

    print(f"canonical store : {len(existing)} raw rows, {len(before)} cells")
    print(f"incoming        : {len(incoming)} raw rows")
    print(f"after merge     : {len(existing) + len(incoming)} raw rows, "
          f"{len(after)} cells")
    superseded = sum(1 for k in after
                     if k in before and after[k] is not before[k])
    print(f"cells superseded: {superseded}   new cells: {len(after) - len(before)}")
    print()
    report(before, after)

    if len(after) < len(before):
        sys.exit("\nREFUSING: the merge would reduce the canonical cell count. "
                 "That can only mean the incoming file is not what it claims.")

    if not a.apply:
        print("\ndry run. re-run with --apply to write.")
        return

    stamp = max((str(r.get("ts_utc")) for r in incoming if r.get("ts_utc")),
                default="unknown")[:19].replace(":", "").replace("-", "")
    backup = f"{CANON}.before-merge-{stamp}"
    shutil.copy2(CANON, backup)
    with open(CANON, "a") as f:
        for r in incoming:
            f.write(json.dumps(r) + "\n")
    print(f"\nappended {len(incoming)} rows. backup at {os.path.basename(backup)}")


if __name__ == "__main__":
    main()
