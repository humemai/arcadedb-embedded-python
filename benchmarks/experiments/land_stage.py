#!/usr/bin/env python3
"""Land a finished queue stage on the page: pull, filter, merge, gate, publish.

The procedure this replaces was typed by hand for every stage of the
September 2026 chain and went wrong twice (a partial in-progress lane merged
into the freeze; a raw directory committed and every queued script aborted at
its pull). One script, one order, refuses by default.

    python land_stage.py --exclude-backends surrealdb_tpc,surrealdb_graph \\
        --message "Neo4j vector index joins the dense table (qDK)" [--apply]

Steps, in order:
  1. pull results/runs_page_<pin>.jsonl from the bench host (and, with
     --overlay ARM, the dense multipass files mp_<ARM>_b*.json at both sizes);
  2. drop rows of the backends still running (--exclude-backends), so a
     stage in progress never reaches the freeze; also any row newer than
     --exclude-since for those backends only;
  3. merge (merge_campaign.py --from-file --apply);
  4. publish through refresh_web_page.py (page-only, no site build here) and
     stop unless every gate passed;
  5. show which page tables changed and how many rows each gained;
  6. build the site, commit the site and the bindings repo (frozen CSV,
     payload, generated tables, PAGE-SPEC inventory), push both.

Without --apply the script stops after step 5 and reverts the site payload,
so the merge and the diff can be read first. Raw directories (results/runs.jsonl,
dense_mp5_*, sparse_mp_*) are never added to git: they are the bench host's
own output and a tracked copy breaks its pull (HANDOFF 2026-09-12).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SITE = REPO.parent / "humem.ai"
RESULTS = HERE / "results"
PAYLOAD = RESULTS / "web_benchmarks.json"
SITE_PAYLOAD = SITE / "src" / "data" / "arcadedb-benchmarks.json"
HOST = os.environ.get("BENCH_LAND_HOST", "mini")
REMOTE = os.environ.get("BENCH_LAND_REMOTE",
                        "~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results")
PY = str(REPO / ".venv" / "bin" / "python")
SCRATCH = Path(os.environ.get("BENCH_LAND_SCRATCH", "/tmp/claude-1000/land_stage"))
TRAILER = ("\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01JB6Hg77dQVqABoTJmiUnV2")


def sh(cmd, cwd=None, check=True, capture=False):
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True,
                          capture_output=capture)


def step(n, title):
    print(f"\n[{n}] {title}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pin", default=os.environ.get("BENCH_ENGINE_COMMIT", "8d6af9475"))
    ap.add_argument("--exclude-backends", default="",
                    help="comma list of backends still running on the host; their rows are dropped")
    ap.add_argument("--exclude-since", default="",
                    help="ISO UTC timestamp; rows of the excluded backends newer than this are dropped "
                         "(default: every row of those backends)")
    ap.add_argument("--overlay", action="append", default=[],
                    help="dense multipass arm token to pull at both sizes (e.g. neo4jvec, pgvector)")
    ap.add_argument("--message", required=True, help="one-line commit subject for both repos")
    ap.add_argument("--apply", action="store_true", help="build, commit and push; default stops after the diff")
    args = ap.parse_args()

    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, BENCH_ENGINE_COMMIT=args.pin)
    env.pop("BENCH_PAPER_DIR", None)

    step(1, f"pull runs_page_{args.pin}.jsonl from {HOST}")
    pulled = SCRATCH / "runs_page_host.jsonl"
    sh(["scp", "-q", f"{HOST}:{REMOTE}/runs_page_{args.pin}.jsonl", str(pulled)])
    for arm in args.overlay:
        for d in (f"dense_mp5_{args.pin}", f"dense_mp5_small_{args.pin}"):
            (RESULTS / d).mkdir(exist_ok=True)
            sh(["scp", "-q", f"{HOST}:{REMOTE}/{d}/mp_{arm}_b*.json", str(RESULTS / d)], check=False)
            have = sorted((RESULTS / d).glob(f"mp_{arm}_b*.json"))
            print(f"  {d}: {len(have)} files for {arm}")

    step(2, "drop rows of the backends still running")
    excl = {b.strip() for b in args.exclude_backends.split(",") if b.strip()}
    rows = [json.loads(l) for l in pulled.read_text().splitlines() if l.strip()]
    keep, dropped = [], []
    for r in rows:
        be = str(r.get("backend", ""))
        hit = any(be == x or be.startswith(x) for x in excl)
        if hit and (not args.exclude_since or str(r.get("ts_utc", "")) >= args.exclude_since):
            dropped.append(r)
        else:
            keep.append(r)
    filtered = SCRATCH / "runs_page_filtered.jsonl"
    filtered.write_text("".join(json.dumps(r) + "\n" for r in keep))
    print(f"  {len(rows)} rows pulled, {len(dropped)} dropped ({sorted({r.get('backend') for r in dropped})})")
    errs = [r for r in keep if r.get("error")]
    if errs:
        print(f"  NOTE {len(errs)} rows carry an error and will merge as failures: "
              f"{sorted({(r.get('lane'), r.get('backend')) for r in errs})}")

    step(3, "merge into results/runs.jsonl")
    before = SITE_PAYLOAD.read_text() if SITE_PAYLOAD.exists() else "{}"
    sh([PY, str(HERE / "merge_campaign.py"), "--from-file", str(filtered), "--apply"], cwd=HERE)

    step(4, "publish through the gates (page-only, no site build)")
    log = SCRATCH / "refresh.log"
    with open(log, "w") as fh:
        rc = subprocess.run([PY, str(HERE / "refresh_web_page.py"), "--no-build"],
                            cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode
    text = log.read_text()
    for line in text.splitlines():
        if "_check " in line or "STALE" in line or "LOST" in line or "UNFLAGGED" in line or "Traceback" in line:
            print("  " + line.strip()[:160])
    if rc != 0 or "_check  FAIL" in text.replace("   ", " ") or " FAIL " in text:
        print(f"\nREFUSED: refresh rc={rc}; read {log}. The merge stands; nothing was pushed.")
        return 1

    step(5, "what changed on the page")
    try:
        old = {t["id"]: t for t in json.loads(before).get("tables", [])}
    except json.JSONDecodeError:
        old = {}
    new = {t["id"]: t for t in json.loads(SITE_PAYLOAD.read_text())["tables"]}
    changed = 0
    for tid, t in new.items():
        n_old = len(old.get(tid, {}).get("entries", []))
        n_new = len(t["entries"])
        rows_old = {(e["backend"], str(e.get("scale"))) for e in old.get(tid, {}).get("entries", [])}
        rows_new = {(e["backend"], str(e.get("scale"))) for e in t["entries"]}
        added = sorted(rows_new - rows_old)
        if n_new != n_old or added or json.dumps(t, sort_keys=True) != json.dumps(old.get(tid), sort_keys=True):
            changed += 1
            print(f"  {tid}: {n_old} -> {n_new} rows" + (f", new: {added[:6]}" if added else ", cells changed"))
    if not changed:
        print("  no table changed; the stage was not page material or its rows were excluded")

    if not args.apply:
        # Put the site's payload back so the working tree is what the last
        # publish left; the merge into runs.jsonl stands (it is idempotent).
        SITE_PAYLOAD.write_text(before)
        sh(["git", "checkout", "--", "src/data", "public/images/projects/arcadedb"], cwd=SITE, check=False)
        print("\nDRY RUN: stopping before build and commit; site payload restored. Re-run with --apply to publish.")
        return 0

    step(6, "build the site, commit both repos, push")
    sh(["npm", "run", "build"], cwd=SITE)
    sh(["git", "add", "-A", "src", "public"], cwd=SITE)
    sh(["git", "commit", "-q", "-m", f"arcadedb: {args.message}{TRAILER}"], cwd=SITE, check=False)
    sh(["git", "push", "-q", "origin", "main"], cwd=SITE)
    tracked = ["benchmarks/experiments/results/runs_paper.csv",
               "benchmarks/experiments/results/web_benchmarks.json",
               "benchmarks/experiments/results/generated",
               "benchmarks/experiments/PAGE-SPEC.md"]
    sh(["git", "add"] + tracked, cwd=REPO)
    sh(["git", "commit", "-q", "-m", f"results: {args.message}{TRAILER}"], cwd=REPO, check=False)
    sh(["git", "push", "-q", "origin", "main"], cwd=REPO)
    print("\nLANDED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
