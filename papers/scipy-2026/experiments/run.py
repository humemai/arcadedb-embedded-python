#!/usr/bin/env python3
"""Official benchmark orchestrator: all lanes, resource-capped, repeated, with memory tracking.

For each (lane, backend, dataset[, workload]) cell it runs the backend's container N times under
identical limits (--cpuset-cpus + --memory), one at a time (no concurrency), while a host-side
sidecar samples the container's cgroup memory over time and reads the exact kernel peak.

Lanes:
  vector  : arcadedb, chroma            (vector_bench.py; uses <ds>/vectors)
  tabular : sqlite, duckdb, arcadedb    (tabular_bench.py; uses <ds>/prepared) x {oltp,olap}
  graph   : ladybug, arcadedb          (graph_bench.py;   uses <ds>/prepared) x {oltp,olap}

Outputs: results/runs.csv, results/mem/<run>.csv, results/manifest.json, results/ENV.md.
Validate on laptop:  python run.py --datasets tiny --reps 2
Official (mini):     python run.py --datasets tiny,small,medium --reps 5
"""
import argparse
import csv
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.environ.get("BENCH_DATA", os.path.join(
    HERE, "..", "..", "..", "bindings", "python", "examples", "data")))
RESULTS = os.path.join(HERE, "results")
MEMDIR = os.path.join(RESULTS, "mem")

CPUSET = "0-7"
MEM_BY_TIER = {"tiny": "8g", "small": "8g", "medium": "32g"}   # ceiling; we report actual peak
HEAP_BY_TIER = {"tiny": "6g", "small": "6g", "medium": "16g"}  # JVM -Xmx (arcadedb only); default 4g OOMs at 1.24M
SAMPLE_INTERVAL = 0.25

LANE_BACKENDS = {
    "vector": ["arcadedb", "chroma"],
    "tabular": ["sqlite", "duckdb", "arcadedb"],
    "graph": ["ladybug", "arcadedb"],
}
LANE_WORKLOADS = {"vector": [None], "tabular": ["oltp", "olap"], "graph": ["oltp", "olap"]}


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def cgroup_dir(cid):
    p = f"/sys/fs/cgroup/system.slice/docker-{cid}.scope"
    if os.path.isdir(p):
        return p
    return sh(["bash", "-c", f"find /sys/fs/cgroup -name '*{cid}*' -type d 2>/dev/null | head -1"]) or None


def read_int(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return None


def read_anon(cg):
    try:
        for line in open(os.path.join(cg, "memory.stat")):
            if line.startswith("anon "):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def read_cpu_stat(cg):
    """cgroup v2 cpu.stat: cumulative usage/user/system in microseconds (per-container totals)."""
    out = {}
    try:
        for line in open(os.path.join(cg, "cpu.stat")):
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("usage_usec", "user_usec", "system_usec"):
                out[parts[0]] = int(parts[1])
    except Exception:
        pass
    return out


def sample_memory(cid, stop, series, peak_box, cpu_box):
    cg, t0 = None, time.time()
    while not stop.is_set():
        cg = cg or cgroup_dir(cid)
        if cg:
            cur, anon, pk = (read_int(os.path.join(cg, "memory.current")),
                             read_anon(cg), read_int(os.path.join(cg, "memory.peak")))
            if cur is not None:
                series.append((round(time.time() - t0, 3), cur, anon or 0))
            if pk is not None:
                peak_box[0] = max(peak_box[0], pk)
            if anon is not None:
                peak_box[1] = max(peak_box[1], anon)
            cpu = read_cpu_stat(cg)  # cumulative; keep the latest non-empty reading
            if cpu:
                cpu_box[0] = cpu
        time.sleep(SAMPLE_INTERVAL)


def build_jobs(datasets, lanes):
    jobs = []
    for ds in datasets:
        for lane in lanes:
            for be in LANE_BACKENDS[lane]:
                for wl in LANE_WORKLOADS[lane]:
                    if lane == "vector":
                        args = ["vector_bench.py", "--backend", be,
                                "--vectors-dir", f"/data/stackoverflow-{ds}/vectors",
                                "--name", f"stackoverflow-{ds}"]
                    else:
                        script = "tabular_bench.py" if lane == "tabular" else "graph_bench.py"
                        args = [script, "--backend", be,
                                "--data-dir", f"/data/stackoverflow-{ds}/prepared",
                                "--workload", wl]
                    rid = f"{lane}_{be}_{ds}" + (f"_{wl}" if wl else "")
                    jobs.append({"lane": lane, "be": be, "ds": ds, "wl": wl,
                                 "args": args, "run_id": rid})
    return jobs


def run_one(job, rep, mem, heap, image_ids):
    run_id = f"{job['run_id']}_r{rep}"
    image = f"scipy-bench:{job['be']}"
    image_ids.setdefault(image, sh(["docker", "inspect", "--format", "{{.Id}}", image]))
    cmd = ["docker", "run", "-d", "--cpuset-cpus", CPUSET, "--memory", mem, "--memory-swap", mem,
           "-e", f"ARCADEDB_HEAP={heap}", "-e", f"RUN_LABEL={run_id}", "-e", "LAT_DIR=/work/results/lat",
           "-v", f"{HERE}:/work", "-w", "/work", "-v", f"{DATA}:/data:ro", image, "python"] + job["args"]
    cid = sh(cmd)
    if len(cid) < 12:
        print(f"  [{run_id}] FAILED to start"); return None
    series, peak_box, cpu_box, stop = [], [0, 0], [{}], threading.Event()
    sampler = threading.Thread(target=sample_memory, args=(cid, stop, series, peak_box, cpu_box))
    sampler.start()
    rc = int(sh(["docker", "wait", cid]) or "1")
    stop.set(); sampler.join()
    lp = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
    logs = lp.stdout + "\n" + lp.stderr
    sh(["docker", "rm", "-f", cid])

    m = re.search(r"RESULT (\{.*\})", logs)
    if rc != 0 or not m:
        print(f"  [{run_id}] rc={rc} no RESULT:\n    " + logs[-280:].replace("\n", "\n    "))
        return None
    res = json.loads(m.group(1))
    os.makedirs(MEMDIR, exist_ok=True)
    with open(os.path.join(MEMDIR, f"{run_id}.csv"), "w") as f:
        f.write("t_s,current_mib,anon_mib\n")
        for t, cur, anon in series:
            f.write(f"{t},{cur / 1048576:.1f},{anon / 1048576:.1f}\n")
    cpu = cpu_box[0]
    res.update({"dataset": job["ds"], "rep": rep, "cpuset": CPUSET, "mem_limit": mem,
                "peak_mib": round(peak_box[0] / 1048576, 1),
                "peak_anon_mib": round(peak_box[1] / 1048576, 1),
                "cpu_total_s": round(cpu.get("usage_usec", 0) / 1e6, 3),
                "cpu_user_s": round(cpu.get("user_usec", 0) / 1e6, 3),
                "cpu_system_s": round(cpu.get("system_usec", 0) / 1e6, 3),
                "image_id": image_ids[image][:19], "mem_series": f"mem/{run_id}.csv",
                "ts_utc": datetime.now(timezone.utc).isoformat()})
    if job["be"] == "arcadedb":
        res["arcadedb_heap"] = heap
    tag = f"{job['lane']}/{job['be']}/{job['ds']}" + (f"/{job['wl']}" if job['wl'] else "")
    extra = (f"recall@10={res.get('recall@10')}" if job["lane"] == "vector"
             else f"oltp={res.get('oltp_ops_per_s')}ops/s" if job["wl"] == "oltp"
             else f"olap={res.get('olap_total_ms')}ms")
    print(f"  [{tag} r{rep}] {extra} peak={res['peak_mib']}MiB "
          f"build/load={res.get('load_s', res.get('build_s'))}s")
    return res


def capture_meta(rows, args, image_ids):
    os.makedirs(RESULTS, exist_ok=True)
    backends = {}
    for r in rows:
        backends.setdefault(r["backend"], {"lib_version": r.get("lib_version", "?"),
                                           "image_id": r.get("image_id", "?")})
    manifest = {
        "run_ts_utc": datetime.now(timezone.utc).isoformat(),
        "host": sh(["hostname"]), "os": sh(["bash", "-c", "uname -srm"]),
        "cpu": sh(["bash", "-c", "lscpu | grep -m1 'Model name' | cut -d: -f2 | xargs"]),
        "nproc": sh(["nproc"]), "mem_total": sh(["bash", "-c", "free -h | awk '/^Mem:/{print $2}'"]),
        "docker": sh(["docker", "--version"]),
        "git_commit": sh(["git", "-C", HERE, "rev-parse", "HEAD"]),
        "git_dirty": bool(sh(["git", "-C", HERE, "status", "--porcelain"])),
        "caps": {"cpuset": CPUSET, "mem_by_tier": MEM_BY_TIER, "sample_interval_s": SAMPLE_INTERVAL},
        "lanes": args.lanes, "datasets": args.datasets.split(","), "reps": args.reps,
        "backends": backends, "n_rows": len(rows),
    }
    json.dump(manifest, open(os.path.join(RESULTS, "manifest.json"), "w"), indent=2)
    env = [f"# Benchmark environment\n", f"- ts: {manifest['run_ts_utc']}",
           f"- host: {manifest['host']}", f"- os: {manifest['os']}", f"- cpu: {manifest['cpu']}",
           f"- nproc: {manifest['nproc']}  mem: {manifest['mem_total']}",
           f"- docker: {manifest['docker']}",
           f"- git: {manifest['git_commit'][:12]} (dirty={manifest['git_dirty']})",
           f"- caps: cpuset={CPUSET} mem_by_tier={MEM_BY_TIER}", "", "## DB versions"]
    for be, info in backends.items():
        env.append(f"- {be}: {info['lib_version']}  ({info['image_id']})")
    open(os.path.join(RESULTS, "ENV.md"), "w").write("\n".join(env) + "\n")
    print(f"wrote manifest + ENV.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="tiny")
    ap.add_argument("--lanes", default="vector,tabular,graph")
    ap.add_argument("--reps", type=int, default=5)
    args = ap.parse_args()
    datasets, lanes = args.datasets.split(","), args.lanes.split(",")

    jobs = build_jobs(datasets, lanes)
    # skip tabular/graph cells whose prepared parquet is missing
    jobs = [j for j in jobs if j["lane"] == "vector"
            or os.path.isdir(os.path.join(DATA, f"stackoverflow-{j['ds']}", "prepared"))]
    print(f"{len(jobs)} cells x {args.reps} reps = {len(jobs) * args.reps} runs "
          f"(cpuset={CPUSET}, datasets={datasets}, lanes={lanes})")

    rows, image_ids = [], {}
    os.makedirs(RESULTS, exist_ok=True)
    jsonl = open(os.path.join(RESULTS, "runs.jsonl"), "a")  # crash-safe incremental log
    for job in jobs:
        mem = MEM_BY_TIER.get(job["ds"], "8g")
        heap = HEAP_BY_TIER.get(job["ds"], "6g")
        for rep in range(1, args.reps + 1):
            r = run_one(job, rep, mem, heap, image_ids)
            if r:
                rows.append(r)
                jsonl.write(json.dumps(r) + "\n"); jsonl.flush()

    capture_meta(rows, args, image_ids)
    if rows:
        cols = sorted({k for r in rows for k in r})
        path = os.path.join(RESULTS, "runs.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader(); w.writerows(rows)
        print(f"wrote {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
