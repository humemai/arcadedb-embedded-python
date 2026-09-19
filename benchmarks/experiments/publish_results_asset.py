#!/usr/bin/env python3
"""Publish the data behind the page as a checkable artifact (DECISIONS #97).

Most readers who doubt a benchmark do not want to run it; they want the rows.
This bundles what the page was generated from, the frozen per-cell CSV and the
payload the site renders, with a manifest naming the engine pin, the comparator
pins, and the gate status at publish time, and attaches it to a GitHub release
so a table can be checked against its own data without a machine, a corpus, or
a container.

    python publish_results_asset.py --tag bench-2026-09-15 [--publish]

Without --publish it writes the bundle and prints what it would upload, which
is the same dry-run-then-apply shape land_stage.py uses.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REPO = HERE.parents[1]

# SEPTEMBER ONLY, and deliberately so: this bundles what the LIVE page serves,
# so it names runs_paper.csv, web_benchmarks.json and results/generated
# literally and reads no BENCH_INSTRUMENT. It is the one place under results/
# that is not campaign-switched (make_paper_tables.GENERATED_NAME), because a
# release asset for a campaign that has not been promoted would describe a
# page nobody can open. Its own two outputs under generated/ -- the manifest
# and the tarball -- are gitignored. When October is promoted, the live names
# become October's and this script follows them there, not before.


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="release tag to attach to, created if absent")
    ap.add_argument("--publish", action="store_true", help="upload; default writes and prints only")
    ap.add_argument("--out", default=str(RESULTS / "generated"))
    args = ap.parse_args()

    payload = RESULTS / "web_benchmarks.json"
    frozen = RESULTS / "runs_paper.csv"
    for p in (payload, frozen):
        if not p.exists():
            print(f"missing {p}; run refresh_web_page.py first", file=sys.stderr)
            return 2

    doc = json.loads(payload.read_text())
    manifest = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": doc.get("arcadedb_engines"),
        "arcadedb_commits": doc.get("arcadedb_commits"),
        "tables": [t["id"] for t in doc.get("tables", [])],
        "rows_in_frozen_csv": sum(1 for _ in open(frozen)) - 1,
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": _sha256(p)}
                  for p in (payload, frozen)},
        "gates": (RESULTS / "generated" / "GATE_STATUS.txt").read_text().strip()
                 if (RESULTS / "generated" / "GATE_STATUS.txt").exists() else None,
        "how_to_check": (
            "Every table on https://humem.ai/projects/arcadedb is generated from "
            "web_benchmarks.json, which is aggregated from runs_paper.csv, one row per "
            "cell per repetition. A published cell is the median across repetitions of "
            "the rows sharing its lane, scale, backend, and workload."),
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"benchmark-results-{args.tag}.tar.gz"
    man_path = out_dir / "results_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with tarfile.open(bundle, "w:gz") as tar:
        for p in (payload, frozen, man_path):
            tar.add(p, arcname=p.name)
    print(f"bundle {bundle} ({bundle.stat().st_size/1e6:.1f} MB)")
    print(f"  engine {manifest['engine']}  tables {len(manifest['tables'])}  "
          f"rows {manifest['rows_in_frozen_csv']}")
    if not args.publish:
        print("dry run: pass --publish to attach it to the release")
        return 0
    have = subprocess.run(["gh", "release", "view", args.tag, "--repo", "humemai/arcadedb-embedded-python"],
                          capture_output=True, text=True).returncode == 0
    if not have:
        subprocess.run(["gh", "release", "create", args.tag, "--repo", "humemai/arcadedb-embedded-python",
                        "--title", f"Benchmark results {args.tag}", "--notes",
                        "The rows and the payload behind the tables at https://humem.ai/projects/arcadedb, "
                        "with the pins and the gate status they were published under."],
                       check=True)
    subprocess.run(["gh", "release", "upload", args.tag, str(bundle), "--clobber",
                    "--repo", "humemai/arcadedb-embedded-python"], check=True)
    print(f"attached to release {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
