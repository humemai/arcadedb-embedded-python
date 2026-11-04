"""Start engine_runner.py in a container (shared by gold_check.py and score.py). Host side, standard library only.

Images are the campaign's own (benchmarks/experiments/build_images.sh): `dbbench:duckdb` (duckdb==1.5.6) and
`dbbench:arcadedb-<version>` (the pinned ArcadeDB wheel and its JVM). This module never builds or pulls an image;
a missing one is an error with the build command named.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ARCADEDB_VERSION = os.environ.get("ARCADEDB_VERSION", "26.10.2")
DEFAULT_IMAGES = {"duckdb": os.environ.get("SQLEV_DUCKDB_IMAGE", "dbbench:duckdb"),
                  "arcadedb": os.environ.get("SQLEV_ARCADEDB_IMAGE", f"dbbench:arcadedb-{ARCADEDB_VERSION}")}


def image_id(image):
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"image {image} not found. Build it with benchmarks/experiments/build_images.sh "
                 f"(ARCADEDB_WHEEL=<the pinned wheel> for the arcadedb image).")
    return r.stdout.strip()


def run_engine(engine, jobs, data_dir, work_dir, tag, person_limit=0, timeout=60, cpuset="14,15", mem="4g",
               heap="2g", image=None):
    """Run `jobs` (list of {key, arm, query}) on `engine`; return the parsed out.json."""
    image = image or DEFAULT_IMAGES[engine]
    iid = image_id(image)
    os.makedirs(os.path.join(work_dir, "home"), exist_ok=True)
    jobs_path = os.path.join(work_dir, f"jobs_{tag}.json")
    out_path = os.path.join(work_dir, f"out_{tag}.json")
    with open(jobs_path, "w") as f:
        json.dump({"jobs": jobs}, f)
    if os.path.exists(out_path):
        os.remove(out_path)
    name = f"sqlev-{engine}-{tag}-{os.getpid()}-{int(time.time())}"
    cmd = ["docker", "run", "--rm", "--name", name, "-m", mem, "--memory-swap", mem, "--cpuset-cpus", cpuset,
           "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/work/home",
           "-v", f"{HERE}:/s:ro", "-v", f"{os.path.abspath(data_dir)}:/data:ro", "-v", f"{os.path.abspath(work_dir)}:/work",
           image, "python", "/s/engine_runner.py", "--engine", engine, "--data", "/data",
           "--jobs", f"/work/jobs_{tag}.json", "--out", f"/work/out_{tag}.json",
           "--person-limit", str(person_limit), "--timeout", str(timeout), "--heap", heap]
    log_path = os.path.join(work_dir, f"log_{tag}.txt")
    with open(log_path, "w") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0 or not os.path.exists(out_path):
        sys.exit(f"engine run {engine}/{tag} failed (rc={rc}); see {log_path}")
    out = json.load(open(out_path))
    out["image"] = image
    out["image_id"] = iid
    return out
