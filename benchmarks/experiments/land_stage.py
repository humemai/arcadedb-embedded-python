#!/usr/bin/env python3
"""Land a finished queue stage on the page: pull, filter, merge, gate, publish.

Landing by hand goes wrong in two ways: a partial in-progress lane merged into
the freeze, and a raw directory committed so every queued script aborts at its
pull. One script, one order, refuses by default.

    python land_stage.py --exclude-backends surrealdb_tpc,surrealdb_graph \\
        --message "Neo4j vector index joins the dense table (qDK)" [--apply]

Steps, in order:
  1. pull results/runs_page_<pin>_2611.jsonl from the bench host (and, with
     --overlay ARM, the dense multipass files mp_<ARM>_b*.json at both sizes);
  2. REFUSE the pulled file unless every row is stamped 2026-11 and sits at the
     pin (screen_pulled_rows), before anything is merged; then drop rows of the
     backends still running (--exclude-backends), so a stage in progress never
     reaches the freeze; also any row newer than
     --exclude-since for those backends only; and the rows a repair stage
     replaced (--drop-unless BACKEND:LANE:WORKLOAD:FIELD=VALUE drops that
     cell's rows whose FIELD is not the repair's stamp);
  3. merge (merge_campaign.py --from-file --apply);
  4. publish through refresh_web_page.py (page-only, no site build here) and
     stop unless every gate passed;
  5. show which page tables changed and how many rows each gained;
  6. build the site, commit the site and the bindings repo (frozen CSV,
     payload, generated tables, PAGE-SPEC inventory), push both.

Without --apply the script stops after step 5 and reverts the site payload,
so the merge and the diff can be read first. Raw directories (results/runs.jsonl,
dense_mp5_*, sparse_mp_*) are never added to git: they are the bench host's
own output and a tracked copy breaks its pull.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# BENCH_LAND_SITE moves the site checkout, the way BENCH_LAND_HOST moves the bench host: a rehearsal on a scratch clone must not
# write the real checkout's payload. Step 4 hands the same path to refresh_web_page (--site), so the two cannot disagree.
SITE = Path(os.environ.get("BENCH_LAND_SITE") or REPO.parent / "humem.ai")
sys.path.insert(0, str(HERE))
from make_2611_stages import ROWS_SUFFIX  # noqa: E402  (the stage generator names what a stage writes; one place)
from publish_instrument import PUBLISH_INSTRUMENT, refuse_other_instruments  # noqa: E402


def host_name(stem, pin, ext=""):
    """The name a stage writes on the bench host: `<stem>_<pin><suffix><ext>`. Locally the overlays keep `<stem>_<pin>`."""
    return f"{stem}_{pin}{ROWS_SUFFIX}{ext}"

# The checkout's own tracked results tree: a landing merges into it and commits from it, so it never runs under
# BENCH_RESULTS_DIR (which exists for tests).
RESULTS = HERE / "results"
PAYLOAD = RESULTS / "web_benchmarks.json"
# The site's copy of the payload, and the lane page source that names the tables. The landing commits both on the
# site; only the payload is a generated file (a dry run restores it, never the hand-written page source).
SITE_PAYLOAD = SITE / "src" / "data" / "dbbench-benchmarks.json"
SITE_PAGE_SOURCE = "src/lib/dbbench/lanes.ts"
SITE_FILES = ["src/data/dbbench-benchmarks.json", SITE_PAGE_SOURCE]
HOST = os.environ.get("BENCH_LAND_HOST", "mini")
REMOTE = os.environ.get("BENCH_LAND_REMOTE",
                        "~/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results")
# BENCH_LAND_PY names the interpreter every step runs under, for a rehearsal in a worktree that has no .venv (the default
# is the repository's own).
PY = os.environ.get("BENCH_LAND_PY") or str(REPO / ".venv" / "bin" / "python")
SCRATCH = Path(os.environ.get("BENCH_LAND_SCRATCH", "/tmp/claude-1000/land_stage"))
TRAILER = ("\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01Ubz3m6QXHESerCkehC1qgi")


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


# THE PULLED FILE IS SCREENED BEFORE IT IS MERGED (2026-10-25, found preparing the first 2026-11 landing). The instrument gates
# all sit DOWNSTREAM of the merge: the freeze refuses a row of another instrument, but by then merge_campaign has appended the
# whole pulled file to results/runs.jsonl, and "the merge stands" is the message a refused landing prints. A retired 2026-10
# file, or one that mixes instruments, would therefore leave its rows in the store and block every later landing at the freeze
# until someone edited the store by hand. The host file is named by instrument AND pin (runs_page_<pin>_2611.jsonl), so a
# stray stamp or a stray commit in it means a stage wrote to the wrong file: that is a refusal, not a row to drop.
def screen_pulled_rows(rows, pin, where):
    """SystemExit unless every pulled row is stamped PUBLISH_INSTRUMENT and, when it names an engine commit, names the pin's.

    The commit test is the exporter's (prefix either way: one side may be truncated). A row with no commit is left alone:
    overlay and host-side rows carry none, and the freeze's own pin gates read them by directory name."""
    refuse_other_instruments(rows, where)
    pin = (pin or "").strip().lower()
    wrong: dict = {}
    for r in rows:
        c = str(r.get("engine_commit") or "").strip().lower()
        if c and pin and not (c.startswith(pin) or pin.startswith(c)):
            wrong[c] = wrong.get(c, 0) + 1
    if wrong:
        found = ", ".join(f"{k}: {v}" for k, v in sorted(wrong.items()))
        raise SystemExit(f"REFUSING: {where} holds rows of another engine commit ({found}), not the pin {pin}. A stage wrote "
                         f"another build's rows into this pin's file; nothing was merged.")


# THE PYTHON-COST TABLE'S FILE (CAMPAIGN section 7 row 29). The stage is host-side, not runner
# cells: it writes $HOME/pycost/mini_results_<pin>.csv OUTSIDE the tree (a file the laptop later commits must not sit
# untracked on the bench host, BUGS F19), and the landing is what puts it where export_web reads it, named by the pin
# (`mini_results_<pin>.csv` beside the tracked file, which wins when it exists) and committed with the rest. Without this
# step a landing published the table from a stale file, with every gate green.
PYCOST_DIR = REPO / "benchmarks" / "python-bindings" / "jpype_overhead" / "results"
PYCOST_REMOTE = "~/pycost"


def pull_pycost(pin, lanes, host=None, run=None):
    """Pull the pin's Python-cost file from the bench host. The Path when it landed here (non-empty, with RESULT
    lines), None when the host has none yet or this landing is scoped away from it. `lanes` is the --only-lanes set."""
    if lanes and "pycost" not in lanes:
        return None
    run = run or sh
    dest = PYCOST_DIR / f"mini_results_{pin}.csv"
    run(["scp", "-q", f"{host or HOST}:{PYCOST_REMOTE}/mini_results_{pin}.csv", str(dest)], check=False)
    if not dest.exists() or not dest.read_text(encoding="utf-8", errors="replace").strip():
        if dest.exists():
            dest.unlink()
        print(f"  pycost: no mini_results_{pin}.csv on {host or HOST} yet (the pycost stage has not run at this pin); "
              f"the table keeps reading the tracked file")
        return None
    n = sum(1 for l in dest.read_text(encoding="utf-8", errors="replace").splitlines() if ",RESULT," in l)
    print(f"  pycost: mini_results_{pin}.csv, {n} RESULT line(s)")
    return dest


def _warn_rows_predate_lane_changes(lanes, pin):
    """Say when a lane's rows were measured before its own script changed.

    THE GATES CANNOT SEE THIS. An l4 landing passed all six with
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
            if str(r.get("instrument") or "") != PUBLISH_INSTRUMENT:
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
    except Exception as exc:  # noqa: BLE001
        # AN EMPTY ANSWER HERE IS NOT HARMLESS. It used to return set() "so a
        # landing does not die on this helper", and a landing then scoped the
        # page to its own lane, rebuilt it without every lane already
        # published, and was refused two steps later for tables that "would
        # disappear" -- after merging, and with the cause (here: export_web
        # imports numpy, and the interpreter had none) nowhere in the output.
        # There is no safe way to land without this answer.
        raise SystemExit(
            f"REFUSING: cannot read which lanes {payload_path} already carries: "
            f"export_web did not import ({type(exc).__name__}: {exc}). Run land_stage.py "
            f"with the repository's environment ({PY}).") from exc
    finally:
        if pin and not _had:
            os.environ.pop("BENCH_ENGINE_COMMIT", None)
    out = set()
    for t in payload.get("tables") or []:
        got = _TABLE_LANE.get(t.get("id"))
        if got:
            out.add(got[0])
    return out


def _restore_this_runs_writes(dirty_before, site_files, site_new=()):
    """Put back what a publish that is NOT going ahead regenerated, in both repos.

    The bindings side is exact: only results paths that became dirty during
    this run (`dirty_before` is the set taken before the merge). The site side
    is the generated files the publish writes -- payload, never the
    hand-written page source -- restricted to tracked paths, because
    `git checkout` fails the whole command on an untracked one. Shared by the
    dry run, a refused gate, and the step-5 refusal.
    """
    ours = sorted(_dirty_results() - dirty_before)
    if ours:
        sh(["git", "checkout", "--"] + ours, cwd=REPO)
        print(f"  restored {len(ours)} regenerated artifact(s) this run rewrote")
    written = [f for f in site_files if f != SITE_PAGE_SOURCE]
    tracked = [f for f in written
               if sh(["git", "ls-files", "--error-unmatch", f], cwd=SITE,
                     check=False, quiet=True).returncode == 0]
    if tracked:
        sh(["git", "checkout", "--"] + tracked, cwd=SITE)
        print(f"  restored the site's generated file(s): {', '.join(tracked)}")
    # THE FIRST LANDING CREATES THE PAYLOAD. src/data/dbbench-benchmarks.json is not in the site's tree until the first 2026-11
    # landing (the site renders no number before it), so there is nothing to `git checkout` it back to: a rehearsal that
    # stopped at the diff left an untracked payload in the real checkout. The paths that did not exist when the run began
    # (`site_new`, taken at step 3) are removed.
    gone = [f for f in site_new if f in written and (SITE / f).exists() and f not in tracked]
    for f in gone:
        (SITE / f).unlink()
    if gone:
        print(f"  removed the site's new generated file(s): {', '.join(gone)}")


def _dirty_results():
    """Tracked, modified paths under the results tree (and PAGE-SPEC.md), as a set.

    Used to tell what a rehearsal wrote from what was already in flight, so
    the restore can be exact. Tracked only: the raw row files are deliberately
    untracked (a `git checkout` over them once reverted runs.jsonl mid-campaign
    and lost rows), and nothing here may touch them.
    """
    # PAGE-SPEC.md rides along: refresh_web_page regenerates its "Published tables" block on every publish (before the gates),
    # so a rehearsal or a refused landing rewrote a tracked file the restore never knew about.
    out = sh(["git", "status", "--porcelain", "--", "benchmarks/experiments/results", "benchmarks/experiments/PAGE-SPEC.md"],
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



def current_pin(payload_path=None):
    """The one engine commit the current payload was built from, or None.

    `--pin` defaults to it, so a stage landed on top of a published payload names the same
    build without being told. None when there is no payload yet or it carries several
    commits: a first landing, or a mixed freeze, has no pin to guess."""
    try:
        payload = json.loads(Path(payload_path or PAYLOAD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pins = payload.get("arcadedb_commits") or []
    return str(pins[0]) if len(pins) == 1 else None


def parse_drop_unless(spec):
    """BACKEND:LANE:WORKLOAD:FIELD=VALUE -> (backend, lane, workload, field, value). A malformed spec ends the run:
    a landing that silently dropped nothing would publish the rows the repair replaced."""
    try:
        backend, lane, workload, cond = spec.split(":", 3)
        field, value = cond.split("=", 1)
    except ValueError:
        raise SystemExit(f"--drop-unless {spec!r}: expected BACKEND:LANE:WORKLOAD:FIELD=VALUE")
    if not all((backend, lane, workload, field)):
        raise SystemExit(f"--drop-unless {spec!r}: every part must be non-empty")
    return backend, lane, workload, field, value


def replaced_by_repair(row, u):
    """True when the row is BACKEND on LANE and WORKLOAD and its FIELD is not VALUE (absent counts as not VALUE)."""
    backend, lane, workload, field, value = u
    return (str(row.get("backend")) == backend and str(row.get("lane")) == lane
            and str(row.get("workload")) == workload and str(row.get(field)) != value)


def main():
    # RUN UNDER THE REPOSITORY'S ENVIRONMENT, whatever interpreter started us.
    # Every step this script shells out to already uses PY; the one piece that
    # runs in-process, _published_lanes' import of export_web, needs that
    # environment's packages too (numpy, through e2_hybrid). Started with the
    # system python3 it silently lost the published lanes.
    if Path(PY).exists() and Path(sys.prefix).resolve() != Path(PY).parent.parent.resolve():
        print(f"(re-running under {PY})", flush=True)
        os.execv(PY, [PY, str(Path(__file__).resolve())] + sys.argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pin", default=os.environ.get("BENCH_ENGINE_COMMIT") or current_pin(),
                    help="engine commit whose rows are pulled (default: BENCH_ENGINE_COMMIT, else the one commit "
                         "the current payload was built from)")
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
    ap.add_argument("--drop-unless", action="append", default=[], metavar="BACKEND:LANE:WORKLOAD:FIELD=VALUE",
                    help="drop the rows of BACKEND on LANE and WORKLOAD whose FIELD is not VALUE (compared as text); "
                         "repeatable. For rows a repair stage replaced, keyed on the stamp only the repair carries: "
                         "qP01's served graph OLTP rows lack server_http_body_max_bytes=68719476736 (DECISIONS #172)")
    ap.add_argument("--overlay", action="append", default=[],
                    help="dense multipass arm token to pull at both sizes (e.g. neo4jvec, pgvector)")
    ap.add_argument("--message", required=True, help="one-line commit subject for both repos")
    ap.add_argument("--apply", action="store_true", help="build, commit and push; default stops after the diff")
    ap.add_argument("--dry-run", action="store_true",
                    help="pull and filter, then STOP before the merge. Without this, "
                         "a run with no --apply still merges: --apply governs the "
                         "publish, not the merge.")
    args = ap.parse_args()

    # Step 1 pulls `runs_page_<pin>_2611.jsonl` by exact name, so a landing with no pin would fetch nothing, and a
    # guessed one would fetch another build's rows. Refuse instead of guessing.
    if not args.pin:
        sys.exit("REFUSING: no --pin, no BENCH_ENGINE_COMMIT, and the current payload does not name exactly one "
                 "engine commit. Pass --pin <commit> or set BENCH_ENGINE_COMMIT.")
    if os.environ.get("BENCH_INSTRUMENT", PUBLISH_INSTRUMENT) != PUBLISH_INSTRUMENT:
        sys.exit(f"REFUSING: BENCH_INSTRUMENT={os.environ['BENCH_INSTRUMENT']!r}; this tooling lands "
                 f"{PUBLISH_INSTRUMENT} rows only (DECISIONS #196).")
    site_files = SITE_FILES

    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, BENCH_ENGINE_COMMIT=args.pin)
    env.pop("BENCH_PAPER_DIR", None)
    # AND THE FREEZE HEARS ABOUT --only-lanes TOO. If it filtered the PULL
    # alone, a landing scoped to one lane would still freeze and gate the whole
    # store: undurable e4 rows would block an e2 landing that had nothing to do
    # with them. It must go in THIS dict, not os.environ -- step
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
        _already = _published_lanes(SITE_PAYLOAD, pin=args.pin)
        if _already - _lanes:
            print(f"  cumulative: landing {','.join(sorted(_lanes))} and keeping "
                  f"{','.join(sorted(_already - _lanes))} already on the page")
        _lanes |= _already
        env["BENCH_ONLY_LANES"] = ",".join(sorted(_lanes))
    step(1, f"pull {host_name('runs_page', args.pin, '.jsonl')} from {HOST}")
    pulled = SCRATCH / "runs_page_host.jsonl"
    sh(["scp", "-q", f"{HOST}:{REMOTE}/{host_name('runs_page', args.pin, '.jsonl')}", str(pulled)])
    for arm in args.overlay:
        for d in (f"dense_mp5_{args.pin}", f"dense_mp5_small_{args.pin}"):
            (RESULTS / d).mkdir(exist_ok=True)
            sh(["scp", "-q", f"{HOST}:{REMOTE}/{host_name(d.rsplit('_', 1)[0], args.pin)}/mp_{arm}_b*.json", str(RESULTS / d)],
               check=False)
            have = sorted((RESULTS / d).glob(f"mp_{arm}_b*.json"))
            print(f"  {d}: {len(have)} files for {arm}")

    # THE E4 TABLE IS A DIRECTORY OF ARTIFACTS, NOT ROWS IN THE JSONL, and
    # nothing pulled it. `export_web` aborts outright when
    # results/e4decomp_<pin>/ is not there, so a landing would have died at
    # the export step with "e4decomp_417314c18 missing" -- after pulling,
    # filtering and merging. A directory somebody scp'd by hand once and left
    # untracked is exactly the kind of step that works until the person who knew
    # about it is not the one doing the landing.
    # THE SPARSE SECOND-PASS TABLE IS A DIRECTORY OF ARTIFACTS TOO, and this
    # step must pull it too.
    # export_web reads results/sparse_mp_<pin>/sp_<arm>_<tier>.json and treats
    # an ABSENT directory as a lane not yet run, so a sparse landing without it
    # would have published the sparse table and silently left its second-pass
    # table off the page. Pulled whenever sparse is part of what lands.
    if not _lanes or "l3s" in _lanes:
        _sp = RESULTS / f"sparse_mp_{args.pin}"
        _sp.mkdir(exist_ok=True)
        sh(["scp", "-q", f"{HOST}:{REMOTE}/{host_name('sparse_mp', args.pin)}/sp_*.json", str(_sp)],
           check=False)
        _files = sorted(_sp.glob("sp_*.json"))
        if _files:
            print(f"  sparse_mp_{args.pin}: {len(_files)} file(s)")
        else:
            # Same reason as e4 below: an empty directory would read as
            # present and move the failure somewhere less obvious.
            _sp.rmdir()

    _pycost = pull_pycost(args.pin, {l.strip() for l in args.only_lanes.split(",") if l.strip()})

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
    # Before the --exclude filters and before any merge: the whole file is one instrument at one pin or it is not landed.
    screen_pulled_rows(rows, args.pin, host_name("runs_page", args.pin, ".jsonl") + f" on {HOST}")
    unless = [parse_drop_unless(x) for x in args.drop_unless]
    keep, dropped, other_lane = [], [], []
    for r in rows:
        if lanes and str(r.get("lane") or "") not in lanes:
            other_lane.append(r)
            continue
        if any(replaced_by_repair(r, u) for u in unless):
            dropped.append(r)
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
    # FAILED AND CENSORED CELLS LAND AS WHAT THEY ARE, and this says how many of each. A row with an error or rc != 0 is a
    # failed cell: it merges as a failure and the freeze skips it (make_paper_tables keeps rc == 0 only), so no number is
    # published for it. A row with a `*_censored` flag set is a cell that hit its budget: the flag travels to the page, which
    # shows it as censored. Neither is rewritten here; the rows are merged exactly as the host wrote them.
    errs = [r for r in keep if r.get("error") or r.get("rc") not in (0, None)]
    if errs:
        print(f"  NOTE {len(errs)} rows are failed cells (an error or rc != 0); they merge as failures and the freeze skips "
              f"them: {sorted({(r.get('lane'), r.get('backend')) for r in errs})}")
    cens = [r for r in keep if r not in errs and any(k.endswith("_censored") and r[k] is True for k in r)]
    if cens:
        print(f"  NOTE {len(cens)} rows carry a censored query (budget hit); they land with the flag and the page shows "
              f"them as censored: {sorted({(r.get('lane'), r.get('backend')) for r in cens})}")

    if args.dry_run:
        # STOP BEFORE ANYTHING WRITES. Without --apply this script still runs
        # steps 2 and 3, and step 3 MERGES: "dry run" in the docstring above
        # describes the PUBLISH, not the merge, and reading it as covering both
        # risks merging an in-progress stage's rows into the canonical log. A
        # pipeline that writes needs a mode that does not.
        n = sum(1 for _ in open(filtered)) if filtered.exists() else 0
        print(f"\n  DRY RUN: {n} row(s) would be merged into results/runs.jsonl,"
              f"\n           then the gates would run and the diff would print."
              f"\n           Nothing was written. Drop --dry-run to proceed.")
        return 0

    step(3, "merge into results/runs.jsonl")
    before = SITE_PAYLOAD.read_text() if SITE_PAYLOAD.exists() else "{}"
    _site_new = [f for f in site_files if not (SITE / f).exists()]   # what this run creates, so a dry run can remove it
    # WHAT WAS ALREADY DIRTY IN THE RESULTS TREE, so a rehearsal can put back
    # what IT wrote without touching what someone else was mid-way through.
    # Same rule as the site restore below and the same reason: this run
    # regenerates the payload, the freeze and the .tex tables, and on a dry run
    # or a failed gate it leaves them behind: the file a reader opens to ask
    # "what is on the page?" would answer with a payload that was refused.
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
    # Rehearsing a landing before its data arrives died here with a traceback
    # out of subprocess, which reads like a broken tool rather than "that lane has no
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
        rc = subprocess.run([PY, str(HERE / "refresh_web_page.py"), "--no-build", "--site", str(SITE)],
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
        _restore_this_runs_writes(_dirty_before, site_files, _site_new)
        return 1

    step(5, "what changed on the page")
    try:
        old = {t["id"]: t for t in json.loads(before).get("tables", [])}
    except json.JSONDecodeError:
        old = {}
    new_payload = json.loads(SITE_PAYLOAD.read_text())
    new = {t["id"]: t for t in new_payload["tables"]}

    def _differs(a, b):
        return json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)

    changed = 0
    for tid, t in new.items():
        n_old = len(old.get(tid, {}).get("entries", []))
        n_new = len(t["entries"])
        rows_old = {(e["backend"], str(e.get("scale"))) for e in old.get(tid, {}).get("entries", [])}
        rows_new = {(e["backend"], str(e.get("scale"))) for e in t["entries"]}
        added = sorted(rows_new - rows_old)
        if n_new != n_old or added or _differs(t, old.get(tid)):
            changed += 1
            # SAY WHAT CHANGED. "cells changed" for any difference in the
            # table's JSON would make a landing that only rewrote the notes
            # under a table read as if its numbers had moved.
            o = old.get(tid) or {}
            what = sorted(k for k in set(t) | set(o) if _differs(t.get(k), o.get(k)))
            if added:
                tail = f", new: {added[:6]}"
            elif "entries" in what:
                rest = [k for k in what if k != "entries"]
                tail = ", cells changed" + (f"; also {', '.join(rest)}" if rest else "")
            else:
                tail = f", no cell changed; {', '.join(what)} changed"
            print(f"  {tid}: {n_old} -> {n_new} rows{tail}")
    # The page-level fields (the notes above every table, the provenance of
    # generated sentences) are part of what a landing publishes too.
    try:
        old_payload = json.loads(before)
    except json.JSONDecodeError:
        old_payload = {}
    page_level = sorted(k for k in set(old_payload) | set(new_payload)
                        if k != "tables" and _differs(old_payload.get(k), new_payload.get(k)))
    if page_level:
        print(f"  page level: {', '.join(page_level)} changed")
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
        _restore_this_runs_writes(_dirty_before, site_files, _site_new)
        return 1
    if not changed and not page_level:
        print("  no table changed; the stage was not page material or its rows were excluded")

    if not args.apply:
        # Put the site's payload back so the working tree is what the last
        # publish left; the merge into runs.jsonl stands (it is idempotent).
        #
        # RESTORE ONLY WHAT THIS RUN WROTE, and only TRACKED paths: git checkout
        # fails the whole command on an untracked one. `site_files` is the
        # COMMIT list -- payload and the hand-written page source -- and a dry
        # run writes only the payload; reverting the page source would throw
        # away uncommitted edits while printing "site payload restored". A dry
        # run must leave the tree as it found it, which cuts both ways: it may
        # not keep what it wrote, and it may not drop what it did not write.
        _restore_this_runs_writes(_dirty_before, site_files, _site_new)
        print("\nDRY RUN: stopping before build and commit; site payload restored. Re-run with --apply to publish.")
        return 0

    step(6, "build the site, commit both repos, push")
    # The gate build writes to its own dist directory (next.config.ts distDir),
    # so it never replaces what a running dev server in the checkout serves from.
    sh(["npm", "run", "build"], cwd=SITE, env=dict(os.environ, NEXT_DIST_DIR=".next-gate"))
    sh(["git", "add"] + site_files, cwd=SITE)
    sh(["git", "commit", "-q", "-m", f"dbbench: {args.message}{TRAILER}"], cwd=SITE, check=False)
    sh(["git", "push", "-q", "origin", "main"], cwd=SITE)
    # COMMIT THE ARTIFACTS THIS PUBLISH WROTE: the freeze, the payload and the
    # generated tables, so the page never serves numbers whose frozen rows are in
    # no commit. results/generated is allowlisted in .gitignore; under the
    # allowlist an unnamed path is ignored and `git add` on it commits NOTHING,
    # silently.
    tracked = ([str(_pycost.relative_to(REPO))] if _pycost else []) + [
               "benchmarks/experiments/results/runs_paper.csv",
               "benchmarks/experiments/results/web_benchmarks.json",
               "benchmarks/experiments/results/generated",
               "benchmarks/experiments/PAGE-SPEC.md"]
    # THE COMMIT MUST BE VERIFIED, NOT ASSUMED (BUGS F56): the
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
