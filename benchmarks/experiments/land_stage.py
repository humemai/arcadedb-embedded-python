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
# --preview (DECISIONS #83): land on /projects/arcadedb/next instead; only the
# preview's payload, images, and prose are committed on the site, and the
# bindings commit carries results/generated/preview-tables.md instead of PAGE-SPEC.
PREVIEW_PAYLOAD = SITE / "src" / "data" / "arcadedb-benchmarks-next.json"
SITE_FILES = {
    "live": ["src/data/arcadedb-benchmarks.json", "public/images/projects/arcadedb",
             "src/lib/projects/items/arcadedb.ts"],
    "preview": ["src/data/arcadedb-benchmarks-next.json", "public/images/projects/arcadedb-next",
                "src/lib/projects/items/arcadedb-next.ts"],
}
HOST = os.environ.get("BENCH_LAND_HOST", "mini")
REMOTE = os.environ.get("BENCH_LAND_REMOTE",
                        "~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results")
PY = str(REPO / ".venv" / "bin" / "python")
SCRATCH = Path(os.environ.get("BENCH_LAND_SCRATCH", "/tmp/claude-1000/land_stage"))
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01JB6Hg77dQVqABoTJmiUnV2")


def sh(cmd, cwd=None, check=True, capture=False, env=None, quiet=False):
    """Run a command, echoing it so the transcript shows what was done.

    `quiet` suppresses the echo for probes whose answer is the point and whose
    command is noise -- asking git whether each of three paths is tracked is
    three lines that say nothing a reader of the log wants.
    """
    if not quiet:
        print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True,
                          capture_output=capture or quiet, env=env)


def _warn_rows_predate_lane_changes(lanes, pin):
    """Say when a lane's rows were measured before its own script changed.

    THE GATES CANNOT SEE THIS. On 2026-09-22 an l4 landing passed all six with
    DuckDB rows measured three days before the commit that gave DuckDB the
    `(host, ts)` index every other arm on that lane has (BUGS F98). The rows
    and their index declaration agreed with each other; what changed
    afterwards was the DECISION, and nothing in the payload records that a
    decision has a date. Publishing would have handicapped a comparator by an
    omission we had already fixed -- flattering our own engine, which is the
    direction that costs the most credibility.

    A WARNING AND NOT A REFUSAL, because materiality needs judgment that this
    cannot do. Adding a field to a row is harmless; changing which index an
    arm builds is not, and both look identical from here. What it can do is
    make sure nobody has to notice on their own: it lists the commits, newest
    last, and leaves the call to the person reading.
    """
    if not lanes:
        return
    sys.path.insert(0, str(HERE))
    try:
        import runner as _R
    except Exception:  # noqa: BLE001
        return
    rows_path = RESULTS / "runs.jsonl"
    if not rows_path.exists():
        return
    newest = {}
    with rows_path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if str(r.get("instrument") or "") != "2026-10":
                continue
            if pin and not str(r.get("engine_commit") or "").startswith(pin):
                continue
            lane = r.get("lane")
            if lane in lanes:
                newest[lane] = max(newest.get(lane, ""), str(r.get("ts_utc") or ""))
    for lane in sorted(newest):
        spec = _R.LANES.get(lane)
        if not spec:
            continue
        out = sh(["git", "log", f"--since={newest[lane]}", "--format=%h %cI %s",
                  "--", f"benchmarks/experiments/{spec[0]}"],
                 cwd=REPO, check=False, capture=True, quiet=True).stdout.strip()
        commits = [l for l in out.splitlines() if l.strip()]
        if not commits:
            continue
        print(f"\n  NOTE {lane}: its newest row is {newest[lane][:16]} and "
              f"{spec[0]} has changed {len(commits)} time(s) since. These rows "
              f"were measured under an earlier version of their own lane:")
        for c in reversed(commits):
            print(f"       {c[:110]}")
        print(f"       Additive fields are harmless; a changed DECISION is not "
              f"(BUGS F98 shipped past all six gates this way).")


def _published_lanes(payload_path, pin=None):
    """The lanes whose tables are already on the page being republished.

    Derived from the payload's own table ids through export_web's table->lane
    map, so it cannot drift from what the exporter builds. Tables with no lane
    in that map are derived or artifact-backed -- `durability` and
    `multimodel` are summaries over the others, `e4` and `pycost` read pinned
    artifacts -- and contribute no lane, which is right: they are rebuilt from
    whatever lanes are in scope rather than pinning a lane themselves.
    """
    try:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    # export_web REFUSES TO IMPORT without a pin -- it resolves the dense
    # overlay's artifact path at module scope -- and this process does not set
    # one, because the pin travels to the gates in the subprocess `env` dict.
    # Lend it the landing's own pin for the duration of the import, and put
    # the environment back: a helper must not leave a variable behind that
    # something later reads as configuration.
    sys.path.insert(0, str(HERE))
    _had = os.environ.get("BENCH_ENGINE_COMMIT")
    if pin and not _had:
        os.environ["BENCH_ENGINE_COMMIT"] = pin
    try:
        from export_web import _TABLE_LANE
    except Exception:  # noqa: BLE001  (a landing must not die on this helper)
        return set()
    finally:
        if pin and not _had:
            os.environ.pop("BENCH_ENGINE_COMMIT", None)
    out = set()
    for t in payload.get("tables") or []:
        got = _TABLE_LANE.get(t.get("id"))
        if got:
            out.add(got[0])
    return out


def _dirty_results():
    """Tracked, modified paths under the results tree, as a set.

    Used to tell what a rehearsal wrote from what was already in flight, so
    the restore can be exact. Tracked only: the raw row files are deliberately
    untracked (a `git checkout` over them once reverted runs.jsonl mid-campaign
    and lost rows), and nothing here may touch them.
    """
    out = sh(["git", "status", "--porcelain", "--", "benchmarks/experiments/results"],
             cwd=REPO, check=False, capture=True, quiet=True)
    got = set()
    for line in (out.stdout or "").splitlines():
        # Porcelain v1 is exactly two status characters, a space, then the
        # path. Splitting on the FIRST space instead keeps the "M " on the
        # front of every path for a " M file" line, and git then refuses the
        # whole checkout with "did not match any file(s)".
        if len(line) < 4 or line.startswith("??"):
            continue
        path = line[3:].strip()
        # A rename prints "old -> new"; the new name is the one on disk.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            got.add(path.strip('"'))
    return got


def step(n, title):
    print(f"\n[{n}] {title}", flush=True)


# September's campaign pin: the right default for a LIVE landing, refused for a
# preview one (see main()).
PIN_DEFAULT = "8d6af9475"

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pin", default=os.environ.get("BENCH_ENGINE_COMMIT", PIN_DEFAULT))
    ap.add_argument("--only-lanes", default="",
                    help="comma list of lanes to land (e.g. l4,e4); rows of every other lane "
                         "are left on the host for a later landing. A STAGED LANDING NEEDS "
                         "THIS: the gates read the whole freeze and have no notion of which "
                         "tables a landing publishes, so merging every lane's rows fails a "
                         "landing on lanes it was not trying to publish. Empty lands everything.")
    ap.add_argument("--exclude-backends", default="",
                    help="comma list of backends still running on the host; their rows are dropped")
    ap.add_argument("--exclude-since", default="",
                    help="ISO UTC timestamp; rows of the excluded backends newer than this are dropped "
                         "(default: every row of those backends)")
    ap.add_argument("--overlay", action="append", default=[],
                    help="dense multipass arm token to pull at both sizes (e.g. neo4jvec, pgvector)")
    ap.add_argument("--message", required=True, help="one-line commit subject for both repos")
    ap.add_argument("--apply", action="store_true", help="build, commit and push; default stops after the diff")
    ap.add_argument("--dry-run", action="store_true",
                    help="pull and filter, then STOP before the merge. Without this, "
                         "a run with no --apply still merges: --apply governs the "
                         "publish, not the merge.")
    ap.add_argument("--preview", action="store_true",
                    help="land on the preview page (/projects/arcadedb/next); the live page is not touched")
    args = ap.parse_args()

    # --pin DEFAULTS TO SEPTEMBER'S COMMIT, which is right for a live landing
    # and wrong for every preview one. Step 1 pulls `runs_page_<pin>.jsonl` by
    # exact name, so a preview landing that took the default would fetch
    # SEPTEMBER's rows, merge them, and then fail somewhere downstream when
    # October's freeze filtered them all out -- an obscure failure a long way
    # from its cause. Refuse instead of guessing an October pin: the campaign
    # names its own, and a wrong one here is a wrong page.
    if args.preview and args.pin == PIN_DEFAULT and not os.environ.get("BENCH_ENGINE_COMMIT"):
        sys.exit("REFUSING: --preview lands an OCTOBER stage, and --pin is still "
                 f"the September default ({PIN_DEFAULT}). Pass --pin <october commit> "
                 "or set BENCH_ENGINE_COMMIT.")

    global SITE_PAYLOAD
    if args.preview:
        SITE_PAYLOAD = PREVIEW_PAYLOAD
    site_files = SITE_FILES["preview" if args.preview else "live"]
    refresh_flags = ["--no-build"] + (["--preview"] if args.preview else [])

    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, BENCH_ENGINE_COMMIT=args.pin)
    env.pop("BENCH_PAPER_DIR", None)
    # AND THE FREEZE HEARS ABOUT --only-lanes TOO. It filtered the PULL alone
    # until 2026-09-22, so a landing scoped to one lane still froze and gated
    # the whole store: five undurable e4 rows blocked an e2 landing that had
    # nothing to do with them. It must go in THIS dict, not os.environ -- step
    # 4 hands the subprocess `env=env` explicitly, so a variable set on our own
    # environment never reaches the gates, which is how the first attempt at
    # this fix passed every local test and still failed the real landing.
    _lanes = {l.strip() for l in args.only_lanes.split(",") if l.strip()}
    # A LANDING IS CUMULATIVE. The page is built fresh from the scoped freeze
    # every time, so a scope of exactly one lane does not ADD that lane to the
    # page -- it rebuilds the page as if no other lane existed. Landing `l2`
    # over this morning's `e2` publish would have dropped `e2` and `e2atom`
    # from the payload entirely, and the pending-table mechanism would then
    # have labelled them "Still being measured at this version": a false
    # statement about two tables measured, gated and published hours earlier.
    #
    # It also emptied the cross-lane tables. The durability table is one row
    # per timed write across every lane; scoped to l2 it holds the three graph
    # writes alone, while its own condition sentence says it holds "the six
    # document operations, the three graph writes, and the cross-model
    # transaction".
    #
    # So the scope is the lane being landed PLUS every lane already on the
    # page, read from the published payload rather than remembered. Every
    # published row therefore passes every gate on every landing, which is the
    # property that makes republishing safe at all.
    if _lanes:
        _already = _published_lanes(PREVIEW_PAYLOAD if args.preview else SITE_PAYLOAD,
                                    pin=args.pin)
        if _already - _lanes:
            print(f"  cumulative: landing {','.join(sorted(_lanes))} and keeping "
                  f"{','.join(sorted(_already - _lanes))} already on the page")
        _lanes |= _already
        env["BENCH_ONLY_LANES"] = ",".join(sorted(_lanes))
    if args.preview:
        # THE SWITCH TRAVELS WITH THE PUBLISH (DECISIONS #84). `env` is what
        # step 4 hands refresh_web_page.py, and that script sets the same
        # variable for itself from --preview -- but this is the only dict a
        # step added here would inherit, and a second landing step that shells
        # out without it would silently regenerate from September's freeze.
        # Stated where the environment is built, not left to one callee.
        env["BENCH_INSTRUMENT"] = "2026-10"

    step(1, f"pull runs_page_{args.pin}.jsonl from {HOST}")
    pulled = SCRATCH / "runs_page_host.jsonl"
    sh(["scp", "-q", f"{HOST}:{REMOTE}/runs_page_{args.pin}.jsonl", str(pulled)])
    for arm in args.overlay:
        for d in (f"dense_mp5_{args.pin}", f"dense_mp5_small_{args.pin}"):
            (RESULTS / d).mkdir(exist_ok=True)
            sh(["scp", "-q", f"{HOST}:{REMOTE}/{d}/mp_{arm}_b*.json", str(RESULTS / d)], check=False)
            have = sorted((RESULTS / d).glob(f"mp_{arm}_b*.json"))
            print(f"  {d}: {len(have)} files for {arm}")

    # THE E4 TABLE IS A DIRECTORY OF ARTIFACTS, NOT ROWS IN THE JSONL, and
    # nothing pulled it. `export_web` aborts outright when
    # results/e4decomp_<pin>/ is not there, so a landing would have died at
    # the export step with "e4decomp_417314c18 missing" -- after pulling,
    # filtering and merging. September's directory is on this laptop because
    # somebody scp'd it by hand once and it is untracked, which is exactly
    # the kind of step that works until the person who knew about it is not
    # the one doing the landing.
    _e4 = RESULTS / f"e4decomp_{args.pin}"
    _e4.mkdir(exist_ok=True)
    sh(["scp", "-q", f"{HOST}:{REMOTE}/e4decomp_{args.pin}/decomp3m_*.json", str(_e4)],
       check=False)
    _reps = sorted(_e4.glob("decomp3m_*_rep*.json"))
    if _reps:
        print(f"  e4decomp_{args.pin}: {len(_reps)} rep file(s)")
    else:
        # An EMPTY directory is worse than no directory: export_web's check is
        # `is_dir()`, so an empty one passes it and the failure moves
        # somewhere less obvious. Leave the clear error in place.
        _e4.rmdir()
        print(f"  e4decomp_{args.pin}: none on {HOST} yet (the e4 lane has not run "
              f"at this pin); the export will say so")

    step(2, "drop rows of the backends still running")
    excl = {b.strip() for b in args.exclude_backends.split(",") if b.strip()}
    lanes = {l.strip() for l in args.only_lanes.split(",") if l.strip()}
    rows = [json.loads(l) for l in pulled.read_text().splitlines() if l.strip()]
    keep, dropped, other_lane = [], [], []
    for r in rows:
        if lanes and str(r.get("lane") or "") not in lanes:
            other_lane.append(r)
            continue
        be = str(r.get("backend", ""))
        hit = any(be == x or be.startswith(x) for x in excl)
        if hit and (not args.exclude_since or str(r.get("ts_utc", "")) >= args.exclude_since):
            dropped.append(r)
        else:
            keep.append(r)
    if lanes:
        _held = sorted({str(r.get("lane")) for r in other_lane})
        print(f"  landing lanes {sorted(lanes)}; {len(other_lane)} row(s) of {_held} "
              f"stay on the host for a later landing")
    filtered = SCRATCH / "runs_page_filtered.jsonl"
    filtered.write_text("".join(json.dumps(r) + "\n" for r in keep))
    print(f"  {len(rows)} rows pulled, {len(dropped)} dropped ({sorted({r.get('backend') for r in dropped})})")
    errs = [r for r in keep if r.get("error")]
    if errs:
        print(f"  NOTE {len(errs)} rows carry an error and will merge as failures: "
              f"{sorted({(r.get('lane'), r.get('backend')) for r in errs})}")

    if args.dry_run:
        # STOP BEFORE ANYTHING WRITES. Without --apply this script still runs
        # steps 2 and 3, and step 3 MERGES: "dry run" in the docstring above
        # describes the PUBLISH, not the merge, and on 2026-09-19 I read it as
        # covering both and came within a closed pipe of merging an
        # in-progress stage's rows into the canonical log while testing an
        # unrelated guard. A pipeline that writes needs a mode that does not.
        n = sum(1 for _ in open(filtered)) if filtered.exists() else 0
        print(f"\n  DRY RUN: {n} row(s) would be merged into results/runs.jsonl,"
              f"\n           then the gates would run and the diff would print."
              f"\n           Nothing was written. Drop --dry-run to proceed.")
        return 0

    step(3, "merge into results/runs.jsonl")
    before = SITE_PAYLOAD.read_text() if SITE_PAYLOAD.exists() else "{}"
    # WHAT WAS ALREADY DIRTY IN THE RESULTS TREE, so a rehearsal can put back
    # what IT wrote without touching what someone else was mid-way through.
    # Same rule as the site restore below and the same reason: this run
    # regenerates the payload, the October freeze and the .tex tables, and on
    # a dry run or a failed gate it leaves them behind. On 2026-09-22 an l2
    # rehearsal that FAILED its gates left `web_benchmarks_next.json` holding
    # the l2 payload while the published page carried the e2 one, so the file
    # a reader opens to ask "what is on the page?" answered with a payload
    # that was refused.
    _dirty_before = _dirty_results()
    # AN EMPTY FILTERED FILE IS NOT A BROKEN PULL WHEN WE DID THE EMPTYING.
    #
    # merge_campaign refuses an empty incoming file, and it is right to: an
    # empty pull usually means the copy failed, and merging nothing silently
    # would hide that. But under --only-lanes it is THIS script that emptied
    # the file, by keeping only the rows of a lane the bench host has not
    # measured yet -- and that is the normal state when rehearsing a landing
    # BEFORE its data arrives, which is the whole point of rehearsing.
    #
    # Rehearsing l3s and l3d on 2026-09-22 died here with a traceback out of
    # subprocess, which reads like a broken tool rather than "that lane has no
    # rows yet". Since "every incoming row was already present" is not an
    # error one line down, "there were no incoming rows for this lane" should
    # not be either. The pull itself is still checked, above.
    _n_in = sum(1 for _ in open(filtered)) if filtered.exists() else 0
    if _n_in == 0 and lanes:
        print(f"  no incoming rows for {','.join(sorted(lanes))} at this pin; "
              f"the store is unchanged and the gates run over what it holds")
    else:
        sh([PY, str(HERE / "merge_campaign.py"), "--from-file", str(filtered), "--apply"], cwd=HERE)

    _warn_rows_predate_lane_changes(lanes, args.pin)

    step(4, "publish through the gates (page-only, no site build)")
    log = SCRATCH / "refresh.log"
    with open(log, "w") as fh:
        rc = subprocess.run([PY, str(HERE / "refresh_web_page.py")] + refresh_flags,
                            cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode
    text = log.read_text()
    for line in text.splitlines():
        # REFUSING/REFUSED too: a step that declines with a reason is the most
        # useful line in the log, and it was the one line not surfaced here.
        # It mattered once tracebacks stopped being printed -- before that the
        # traceback was the only signal, and it named the file rather than the
        # cause.
        if ("_check " in line or "STALE" in line or "LOST" in line
                or "UNFLAGGED" in line or "Traceback" in line
                or line.lstrip().startswith(("REFUSING", "REFUSED"))):
            print("  " + line.strip()[:160])
    if rc != 0 or "_check  FAIL" in text.replace("   ", " ") or " FAIL " in text:
        print(f"\nREFUSED: refresh rc={rc}; read {log}. The merge stands; nothing was pushed.")
        # A REFUSED RUN MUST NOT LEAVE ITS PAYLOAD IN THE TREE. This is the
        # path a rehearsal actually takes -- it fails at a gate, which returns
        # here and not through the dry-run block below -- and step 1 has
        # already regenerated the payload, the freeze and the .tex tables from
        # the scoped rows. Leaving them means the file a reader opens to ask
        # what is published answers with a payload the gates just refused.
        _refused = sorted(_dirty_results() - _dirty_before)
        if _refused:
            sh(["git", "checkout", "--"] + _refused, cwd=REPO)
            print(f"  restored {len(_refused)} regenerated artifact(s); the refused "
                  f"payload is not left in the tree")
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
    # A TABLE THAT VANISHES IS THE CHANGE MOST WORTH PRINTING, and this loop
    # walked the NEW payload only, so it could not see one. A scoped landing
    # used to rebuild the page as if no other lane existed; that is fixed
    # above, and this is the net under it, because "the page lost a table" is
    # the one diff nobody would accept by accident.
    gone = sorted(set(old) - set(new))
    if gone:
        for tid in gone:
            print(f"  {tid}: {len(old[tid].get('entries', []))} -> GONE")
        print(f"\n  REFUSING: {len(gone)} table(s) on the page would disappear: "
              f"{gone}. A landing adds to the page; it does not replace it.",
              file=sys.stderr)
        return 1
    if not changed:
        print("  no table changed; the stage was not page material or its rows were excluded")

    if not args.apply:
        # Put the site's payload back so the working tree is what the last
        # publish left; the merge into runs.jsonl stands (it is idempotent).
        #
        # RESTORE WHAT THIS RUN TOUCHED, not a fixed slice. Two bugs lived in
        # the old two lines. `before` is read from SITE_PAYLOAD, which is the
        # LIVE payload, so a --preview dry run wrote the live file and left the
        # preview one to a positional `site_files[:2]` that happened to include
        # it. And that slice named `public/images/projects/arcadedb-next`,
        # a directory holding no tracked files, so git answered "pathspec did
        # not match" and returned non-zero for the whole command -- a restore
        # that announces "site payload restored" while reporting an error is
        # the shape where one day it restores nothing and still says that.
        #
        # git checkout only restores TRACKED paths, so ask git which of them
        # are tracked and pass exactly those. An untracked or empty directory
        # is then not an error, because nothing in it could have been changed.
        # RESTORE ONLY WHAT THIS RUN WROTE. `site_files` is the COMMIT list --
        # payload, images, and the hand-written prose -- and a dry run writes
        # only the first two. Reverting the third threw away uncommitted prose
        # edits twice in one session, silently, while printing "site payload
        # restored"; the second time it discarded the rewrite that stopped the
        # page claiming its numbers came from a development laptop.
        #
        # A dry run must leave the tree as it found it, and that cuts both
        # ways: it may not keep what it wrote, and it may not drop what it did
        # not write. The prose file is never written here, so it is never
        # restored here.
        # The bindings tree first: same rule, other repo.
        _now = _dirty_results()
        _ours = sorted(_now - _dirty_before)
        if _ours:
            sh(["git", "checkout", "--"] + _ours, cwd=REPO)
            print(f"  restored {len(_ours)} regenerated artifact(s) this run rewrote")

        _written = [f for f in site_files if "/items/" not in f]
        _tracked = [f for f in _written
                    if sh(["git", "ls-files", "--error-unmatch", f], cwd=SITE,
                          check=False, quiet=True).returncode == 0]
        if _tracked:
            sh(["git", "checkout", "--"] + _tracked, cwd=SITE)
        print("\nDRY RUN: stopping before build and commit; site payload restored. Re-run with --apply to publish.")
        return 0

    step(6, "build the site, commit both repos, push")
    # The gate build writes to its own dist directory (next.config.ts distDir),
    # so it never replaces what a running dev server in the checkout serves from.
    sh(["npm", "run", "build"], cwd=SITE, env=dict(os.environ, NEXT_DIST_DIR=".next-gate"))
    sh(["git", "add"] + site_files, cwd=SITE)
    sh(["git", "commit", "-q", "-m", f"arcadedb{' preview' if args.preview else ''}: {args.message}{TRAILER}"], cwd=SITE, check=False)
    sh(["git", "push", "-q", "origin", "main"], cwd=SITE)
    # COMMIT THE ARTIFACTS THIS PUBLISH WROTE, not September's. A preview
    # landing regenerates runs_paper_oct.csv and web_benchmarks_next.json and
    # leaves the live pair exactly as it found them (DECISIONS #84), so
    # committing the live pair here would add nothing and the October freeze
    # would stay untracked -- the page serving numbers whose frozen rows are
    # in no commit.
    #
    # THE GENERATED DIRECTORY IS THE THIRD ARTIFACT, and it was the one still
    # pointing at September. It used to stage results/generated whichever
    # route this landing was for, which did two wrong things at once on a
    # preview landing: October's tables (results/generated_oct, since
    # make_paper_tables.GENERATED_NAME) went into no commit, and anything that
    # had touched September's published set got committed as part of an
    # October landing without being read. Staging only what this publish wrote
    # means a September artifact showing up dirty during an October landing
    # stays dirty and visible, instead of being swept into the commit.
    #
    # results/generated_oct is allowlisted in .gitignore. It has to be: under
    # the allowlist an unnamed path is ignored and `git add` on it commits
    # NOTHING, silently, which is exactly where a landing would stop -- the
    # site pushed, the tables in no commit.
    _frozen, _payload, _generated = (
        ("runs_paper_oct.csv", "web_benchmarks_next.json", "generated_oct") if args.preview
        else ("runs_paper.csv", "web_benchmarks.json", "generated"))
    tracked = [f"benchmarks/experiments/results/{_frozen}",
               f"benchmarks/experiments/results/{_payload}",
               f"benchmarks/experiments/results/{_generated}",
               # the preview route's inventory, which stays under
               # results/generated beside PAGE-SPEC's own (refresh_web_page
               # .PREVIEW_INVENTORY says why)
               "benchmarks/experiments/results/generated/preview-tables.md" if args.preview
               else "benchmarks/experiments/PAGE-SPEC.md"]
    # THE COMMIT MUST BE VERIFIED, NOT ASSUMED. 2026-09-18 (BUGS F56): the
    # pre-commit hook rewrote a staged JSON file, git aborted the commit, this
    # script printed LANDED and pushed nothing, and the frozen rows sat staged
    # and uncommitted while the site had already moved. A hook that rewrites a
    # file aborts the commit; the fix is to re-add and commit once more, and
    # to refuse the LANDED line unless HEAD actually moved.
    before_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                                 capture_output=True).stdout.strip()
    for attempt in (1, 2):
        sh(["git", "add"] + tracked, cwd=REPO)
        rc = sh(["git", "commit", "-q", "-m", f"results: {args.message}{TRAILER}"],
                cwd=REPO, check=False).returncode
        after_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                                    capture_output=True).stdout.strip()
        if after_head != before_head:
            break
        dirty = subprocess.run(["git", "status", "--short"] + tracked, cwd=REPO, text=True,
                               capture_output=True).stdout.strip()
        if not dirty:
            print("  nothing to commit in the bindings repo (rows unchanged)")
            break
        print(f"  commit attempt {attempt} did not move HEAD (rc={rc}); a hook rewrote a staged file, retrying")
    else:
        print("\nREFUSED: the bindings commit did not land after two attempts; the site is pushed "
              "but the frozen rows are not. Commit them by hand before anything else.")
        return 1
    sh(["git", "push", "-q", "origin", "main"], cwd=REPO)
    pushed = subprocess.run(["git", "rev-parse", "origin/main"], cwd=REPO, text=True,
                            capture_output=True).stdout.strip()
    if pushed != after_head:
        print(f"\nREFUSED: push did not land (origin/main {pushed[:10]} != HEAD {after_head[:10]}).")
        return 1
    print(f"\nLANDED. bindings {after_head[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
