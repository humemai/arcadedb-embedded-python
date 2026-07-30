#!/usr/bin/env python3
"""Report RETAINED bytes by owner from an `asprof -e alloc --live` profile.

Written ahead of queue37 landing, because we committed a number to upstream on
ArcadeData/arcadedb#5588 and it should be computed the same way whatever the
profile says. The issue's first acceptance criterion is a measured heap per
live vector for `VectorLocationIndex`, currently estimated at ~90 B from object
headers and map overheads rather than measured. Our 10M-vector DEEP index is
10x the 1M scale that criterion names.

Why `--live` and not a plain alloc profile: a plain one measures allocation
CHURN, which the collector reclaims. queue32's alloc arm did exactly that and
so could say nothing about a retained footprint, which was the question. With
`--live`, async-profiler reports only the samples whose objects were still
reachable at dump time.

    python3 analyze_live_profile.py FILE.collapsed [--per-vector 9990000]

Reports total retained, the top owners, and, when --per-vector is given, bytes
per live vector for the frames that matter to #5588.

Caveats printed with the result, because they change how it should be read:
allocation sampling is statistical, so a small owner is noise; and a shared
structure is attributed to whoever allocated it, not to whoever retains it.
"""
import argparse
import collections
import re
import sys

# Frames whose retained size #5588 turns on. Matched as substrings against the
# whole stack, so an inlined or renamed helper still lands in the right bucket.
OWNERS = [
    ("VectorLocationIndex", "location index (#5588 target)"),
    ("VectorCache", "shared search cache (#5412)"),
    ("ordinalToVectorId", "ordinal map"),
    ("jbellis/jvector", "JVector internals"),
    ("com/arcadedb/index/vector", "other ArcadeDB vector code"),
    ("com/arcadedb/engine", "page/storage layer"),
]


def load(path):
    """[(stack, weight)] from a collapsed profile."""
    out = []
    for line in open(path, errors="ignore"):
        stack, _, w = line.rstrip("\n").rpartition(" ")
        try:
            out.append((stack, int(w)))
        except ValueError:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--per-vector", type=int, default=0,
                    help="live vector count, to report bytes per vector")
    args = ap.parse_args()

    samples = load(args.path)
    if not samples:
        print(f"no samples in {args.path}")
        return 1
    total = sum(w for _, w in samples)
    print(f"{args.path}")
    print(f"  samples: {len(samples):,} stacks, total weight {total:,}\n")

    # Owner attribution: first matching bucket wins, so the specific frames are
    # listed before the general ones above.
    owned = collections.Counter()
    for stack, w in samples:
        for needle, label in OWNERS:
            if needle in stack:
                owned[label] += w
                break
        else:
            owned["(unattributed)"] += w

    print("  retained by owner")
    for label, w in owned.most_common():
        line = f"    {100*w/total:5.1f}%  {w:>14,}  {label}"
        if args.per_vector:
            line += f"   {w/args.per_vector:7.1f} B/vector"
        print(line)

    print("\n  top leaf frames")
    leaves = collections.Counter()
    for stack, w in samples:
        leaves[stack.split(";")[-1]] += w
    for f, w in leaves.most_common(12):
        print(f"    {100*w/total:5.1f}%  {f.split('/')[-1][:64]}")

    if args.per_vector:
        loc = owned.get("location index (#5588 target)", 0)
        print(f"\n  #5588: location index measures {loc/args.per_vector:.1f} B "
              f"per live vector against the ~90 B estimated in the issue")
        if loc == 0:
            print("    (zero: either the frame name differs in this build, or "
                  "the structure was allocated before the profile started, "
                  "which --live cannot see. Check before reporting.)")

    print("\n  read with these caveats:")
    print("    - allocation sampling is statistical; a small owner is noise")
    print("    - a shared structure is attributed to its allocator, not its "
          "retainer")
    print("    - --live sees only what was allocated while the profiler ran, so "
          "anything built before it started is invisible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
