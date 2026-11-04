"""Start engine_runner.py in a container (shared by gold_check.py, score.py and score_portability.py). Host side, standard library only.

Images: `sqlev:duckdb-2.0.0` for DuckDB (this harness's own image, docker/duckdb.Dockerfile: duckdb==2.0.0 and the DuckPGQ
community extension baked in at build time) and the campaign's `dbbench:arcadedb-<version>` (the pinned ArcadeDB wheel and
its JVM, benchmarks/experiments/build_images.sh). This module never builds or pulls an image; a missing one is an error with
the build command named.

Container recovery (README, "Engine restarts"). An engine container can die in the middle of a run: DuckPGQ has a known
out-of-memory bug (cwida/duckpgq-extension#335, fixed in DuckDB 2.0.1), and any engine can be OOM-killed (exit 137). The
runner flushes one JSON line per finished job to a partial file, so after every container exit this module knows which jobs
reported. When some did not, the first unreported job is the one that was in flight: it is recorded as a failed job with
reason `engine_killed` (exit code and the last stderr lines kept), and a fresh container runs the jobs after it. Later
queries are executed, never scored as failures of a container that was already dead. At most MAX_RESTARTS restarts per run
(SQLEV_MAX_RESTARTS, default 5); past that the run exits, because the remaining jobs would not be measured. A container that
dies before it reported anything (during the load) is a setup failure and exits at once.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ARCADEDB_VERSION = os.environ.get("ARCADEDB_VERSION", "26.10.2")
DUCKDB_VERSION = "2.0.0"
DEFAULT_IMAGES = {"duckdb": os.environ.get("SQLEV_DUCKDB_IMAGE", f"sqlev:duckdb-{DUCKDB_VERSION}"),
                  "arcadedb": os.environ.get("SQLEV_ARCADEDB_IMAGE", f"dbbench:arcadedb-{ARCADEDB_VERSION}")}
MAX_RESTARTS = int(os.environ.get("SQLEV_MAX_RESTARTS", "5"))
TAIL_LINES = 20


FALLBACK_DUCKDB_IMAGE = "dbbench:duckdb"  # the campaign image, DuckDB 1.5.6 (build_images.sh hold of 2026-10-23: DuckPGQ on 2.0.0 did not parse)


def default_image(engine):
    """The image for an engine. DuckDB: SQLEV_DUCKDB_IMAGE if set, else this harness's 2.0.0 image if it was built (its build
    fails unless DuckPGQ parses CREATE PROPERTY GRAPH and GRAPH_TABLE on 2.0.0), else the campaign's 1.5.6 image, so both DuckDB
    arms always share one DuckDB version; the version actually used is read at runtime and recorded in every output."""
    if engine != "duckdb" or "SQLEV_DUCKDB_IMAGE" in os.environ:
        return DEFAULT_IMAGES[engine]
    want = DEFAULT_IMAGES["duckdb"]
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", want], capture_output=True, text=True)
    if r.returncode == 0:
        return want
    print(f"note: {want} is not built (its DuckPGQ parse gate failed, or sqlev-image-duckdb did not run); "
          f"both DuckDB arms use {FALLBACK_DUCKDB_IMAGE} (DuckDB 1.5.6, the campaign's hold until a DuckPGQ build for 2.x parses)",
          file=sys.stderr)
    return FALLBACK_DUCKDB_IMAGE


def image_id(image):
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    if r.returncode != 0:
        if image.startswith("sqlev:duckdb-"):
            how = (f"Build it with: docker build -t {image} -f {HERE}/docker/duckdb.Dockerfile {HERE}/docker "
                   f"(the line sqlev-image-duckdb in MEASURE-LINES.txt).")
        else:
            how = ("Build it with benchmarks/experiments/build_images.sh "
                   "(ARCADEDB_WHEEL=<the pinned wheel> for the arcadedb image).")
        sys.exit(f"image {image} not found. {how}")
    return r.stdout.strip()


def read_partial(path):
    """(header or None, [result lines]) from a runner's partial file. A torn last line (the process died mid-write) is skipped."""
    header, results = None, []
    if not os.path.exists(path):
        return header, results
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if "header" in d:
                header = d["header"]
            else:
                results.append(d)
    return header, results


def tail_lines(path, n=TAIL_LINES):
    if not os.path.exists(path):
        return []
    with open(path, errors="replace") as f:
        return [ln.rstrip("\n") for ln in f.readlines()[-n:]]


def killed_job_result(job, rc, tail):
    """The record of the job that was in flight when its container exited: a failed job, caused by its own query."""
    why = {137: " (SIGKILL, most likely out of memory)", 139: " (SIGSEGV)"}.get(rc, "")
    msg = (f"engine_killed: the engine container exited with code {rc}{why} while this query was running; "
           f"last stderr: {' | '.join(tail) if tail else '(empty)'}")
    return {"key": job["key"], "arm": job.get("arm"), "parse_ok": False, "exec_ok": False, "error": msg[:600], "rows": [],
            "n_rows": 0, "truncated": False, "ms": None, "reason": "engine_killed", "exit_code": rc, "stderr_tail": tail}


def supervise(jobs, launch, label, killed_result=killed_job_result, max_restarts=None):
    """Run `jobs` (dicts with a `key`, executed in order) through containers until every job has a result.

    launch(attempt, remaining) starts a container for `remaining` and blocks until it exits; it returns
    (exit_code, stderr_tail_lines, partial_file_path). Returns (header of the first attempt, results in job order,
    {"restarts": n, "engine_killed": [keys], "exit_codes": [exit code of every launch]})."""
    max_restarts = MAX_RESTARTS if max_restarts is None else max_restarts
    if not jobs:
        sys.exit(f"{label}: no jobs")
    done, killed, codes, headers = {}, [], [], []
    remaining = list(jobs)
    attempt = 0
    while remaining:
        rc, tail, part = launch(attempt, remaining)
        codes.append(rc)
        header, results = read_partial(part)
        if header is None:
            sys.exit(f"{label}: the engine container exited with code {rc} before it finished loading (attempt {attempt}); "
                     f"setup failure, not a killed query. Last stderr:\n  " + "\n  ".join(tail))
        headers.append(header)
        for r in results:
            done[r["key"]] = r
        remaining = [j for j in remaining if j["key"] not in done]
        if not remaining:
            break
        # The container exited (non-zero, killed, or silently) before every job reported: the first unreported job was running.
        victim = remaining.pop(0)
        done[victim["key"]] = killed_result(victim, rc, tail)
        killed.append(victim["key"])
        print(f"{label}: container exited with code {rc} in job {victim['key']} (attempt {attempt}); recorded as engine_killed, "
              f"{len(remaining)} jobs left", file=sys.stderr, flush=True)
        if not remaining:
            break
        attempt += 1
        if attempt > max_restarts:
            sys.exit(f"{label}: {max_restarts} restarts used and {len(remaining)} jobs still not run; stopping "
                     f"(killed jobs so far: {killed}). Not scoring jobs that were never executed.")
    return headers[0], [done[j["key"]] for j in jobs], {"restarts": len(codes) - 1, "engine_killed": killed, "exit_codes": codes}


def run_engine(engine, jobs, data_dir, work_dir, tag, person_limit=0, timeout=60, cpuset="14,15", mem="4g",
               heap="2g", image=None):
    """Run `jobs` (list of {key, arm, query}) on `engine`; return an out.json-shaped dict (header fields, `results` in job
    order, `restarts`, `engine_killed`, `exit_codes`, `image`, `image_id`). A killed container is recovered as described above."""
    image = image or default_image(engine)
    iid = image_id(image)
    os.makedirs(os.path.join(work_dir, "home"), exist_ok=True)

    def launch(attempt, remaining):
        sfx = tag if attempt == 0 else f"{tag}.r{attempt}"
        jobs_path = os.path.join(work_dir, f"jobs_{sfx}.json")
        part_path = os.path.join(work_dir, f"part_{sfx}.jsonl")
        out_path = os.path.join(work_dir, f"out_{sfx}.json")
        log_path = os.path.join(work_dir, f"log_{sfx}.txt")
        err_path = os.path.join(work_dir, f"err_{sfx}.txt")
        with open(jobs_path, "w") as f:
            json.dump({"jobs": remaining}, f)
        for p in (part_path, out_path):
            if os.path.exists(p):
                os.remove(p)
        name = f"sqlev-{engine}-{sfx}-{os.getpid()}-{int(time.time())}"
        cmd = ["docker", "run", "--rm", "--name", name, "-m", mem, "--memory-swap", mem, "--cpuset-cpus", cpuset,
               "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/work/home",
               "-v", f"{HERE}:/s:ro", "-v", f"{os.path.abspath(data_dir)}:/data:ro", "-v", f"{os.path.abspath(work_dir)}:/work",
               image, "python", "/s/engine_runner.py", "--engine", engine, "--data", "/data",
               "--jobs", f"/work/jobs_{sfx}.json", "--out", f"/work/out_{sfx}.json", "--partial", f"/work/part_{sfx}.jsonl",
               "--person-limit", str(person_limit), "--timeout", str(timeout), "--heap", heap]
        with open(log_path, "w") as log, open(err_path, "w") as err:
            rc = subprocess.run(cmd, stdout=log, stderr=err).returncode
        return rc, tail_lines(err_path) or tail_lines(log_path), part_path

    header, results, stats = supervise(jobs, launch, f"engine run {engine}/{tag}")
    out = dict(header)
    out["results"] = results
    out.update(stats)
    out["image"] = image
    out["image_id"] = iid
    return out
