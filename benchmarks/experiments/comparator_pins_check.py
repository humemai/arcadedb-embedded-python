#!/usr/bin/env python3
"""Every published comparator number must come from the version we pin today.

WHY. On 2026-08-27 the pins in build_images.sh had drifted ahead of the frozen
results without anything noticing: ladybug 0.19.1 pinned against a published
0.18.1, lancedb 0.37.1 against 0.34.0, qdrant-client 1.19.0 against 1.18.0,
pymilvus 3.0.1 against 3.0.0. A campaign re-runs every backend in the lanes it
touches, so re-run lanes silently move to the newer comparator while lanes it
does not touch keep the older one -- and the page then compares ArcadeDB against
two different Qdrants in two different tables.

Nothing checked it. fairness_check.py has no version assertion at all, and the
identifiability gate in export_web deliberately exempted comparators.

WHAT THIS DOES. Reads the pins out of build_images.sh (the file the images are
actually built from, not a copy that can drift) and compares them against the
version recorded on every published comparator row. Reports three states:

  MATCHES  the row came from the pinned version
  STALE    the row predates a pin bump; the lane needs re-running
  UNKNOWN  the row records a name or a blank where a version belongs

Exit 1 if anything is STALE or UNKNOWN, because either means the page cannot say
what it compared against.

    python3 comparator_pins_check.py
    python3 comparator_pins_check.py --frozen results/runs_paper.csv
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(HERE, "build_images.sh")
FROZEN = os.path.join(HERE, "results", "runs_paper.csv")

# backend name in results -> the pypi package whose pin governs it. A backend
# absent here is one whose version does not come from a pinned python package
# (a server image, say), and is reported rather than silently skipped.
BACKEND_PKG = {
    "ladybug_graph": "ladybug",
    "neo4j_graph": "neo4j",
    "qdrant_dense": "qdrant-client",
    "qdrant_sparse": "qdrant-client",
    "milvus_dense": "pymilvus",
    "milvus_sparse": "pymilvus",
    "chroma_dense": "chromadb",
    "lancedb_dense": "lancedb",
    "sqlite_vec_dense": "sqlite-vec",
    "duckdb_vss_dense": "duckdb",
    "duckdb": "duckdb",
    "elasticsearch_sparse": "elasticsearch",
    "surrealdb_e2": "surrealdb",
}


def read_pins():
    """package -> pinned version, from the file the images are built from."""
    try:
        body = open(IMAGES).read()
    except OSError as exc:
        print(f"cannot read {IMAGES}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    pins = dict(re.findall(r"([a-zA-Z0-9_.\-]+)==([0-9][0-9a-zA-Z.\-]*)", body))
    if not pins:
        print("no ==pins found in build_images.sh; the format changed and this "
              "check would pass everything", file=sys.stderr)
        raise SystemExit(2)
    return pins


def classify(recorded, pinned):
    """MATCHES / STALE / UNKNOWN for one row's recorded version."""
    v = (recorded or "").strip()
    if not v or re.fullmatch(r"[a-z_\-]+|[?]|unset|none|null", v, re.I):
        return "UNKNOWN"
    # Versions are recorded in several shapes: bare (0.34.0), prefixed
    # (ladybug:0.18.1), or compound (milvus:2.6/pymilvus:3.0.1). Any occurrence
    # of the pinned string counts, so a compound that names it still matches.
    return "MATCHES" if pinned and pinned in v else "STALE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default=FROZEN)
    args = ap.parse_args()
    pins = read_pins()
    rows = list(csv.DictReader(open(args.frozen)))
    seen, bad = {}, 0
    for r in rows:
        be = str(r.get("backend") or "")
        if not be or be.startswith("arcadedb"):
            continue
        rec = r.get("engine_version") or r.get("version_name") or ""
        pkg = BACKEND_PKG.get(be)
        state = "NO PIN MAPPED" if pkg is None else classify(rec, pins.get(pkg))
        seen.setdefault((be, pkg, rec.strip() or "(blank)", state), 0)
        seen[(be, pkg, rec.strip() or "(blank)", state)] += 1
    print(f"pins from build_images.sh: {len(pins)} packages\n")
    order = {"STALE": 0, "UNKNOWN": 1, "NO PIN MAPPED": 2, "MATCHES": 3}
    for (be, pkg, rec, state), n in sorted(seen.items(), key=lambda kv: (order[kv[0][3]], kv[0][0])):
        want = pins.get(pkg, "-")
        print(f"  {state:<14}{be:<24}{rec[:30]:<32}pinned={want:<10}n={n}")
        if state in ("STALE", "UNKNOWN"):
            bad += n
    print(f"\n  {bad} published comparator rows cannot be traced to a current pin")
    if bad:
        print("  -> re-run those lanes, or record why the pin legitimately differs")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
