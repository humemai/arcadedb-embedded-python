#!/usr/bin/env python3
"""ICDE-paper benchmark runner — implements experiments/PROTOCOL.md.

Descended from the SciPy-paper orchestrator (scipy_proceedings@arcadedb-2026
experiments/run.py) with the protocol extensions:

  * TOPOLOGIES: "embedded" (one container does engine+workload) and
    "client_server" (a long-lived server container + a client container).
    Per PROTOCOL: both containers share the SAME cpuset (CPU competition is
    natural/work-conserving); MEMORY is split explicitly (default 75/25) and
    the reported numbers are the SUM of both cgroups.
  * TIERS: tier2 (default) runs cells strictly serially with the full cpuset —
    every paper number comes from this tier. tier1 (--parallel N) is the
    exploration sweep: N workers on disjoint cpuset shards, shuffled job order,
    never two jobs of the same backend at once. Manifests record the tier.
  * MANIFESTS: results/manifest-<ts>.json records image digests, cpuset,
    memory caps, tier, repeats; every row in runs.jsonl carries run metadata.

Usage (smoke):    python3 runner.py --lanes l1 --scale tiny --reps 1
Paper (serial):   python3 runner.py --lanes l1,l2,l3s,l3d,l4 --scale medium --reps 5
Sweep (parallel): python3 runner.py --parallel 3 --tier sweep ...
"""
import argparse
import csv
import json
import os
import random
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.environ.get("BENCH_DATA", os.path.join(HERE, "data")))
RESULTS = os.path.join(HERE, "results")
RAW = os.path.join(RESULTS, "raw")
SAMPLE_INTERVAL = 0.25

# P-core threads on the i9-12900HK bench host; override for other hosts.
CPUSET = os.environ.get("BENCH_CPUSET", "0-11")
MEM_BY_SCALE = {"micro": "8g", "tiny": "8g", "small": "16g", "medium": "32g",
                "large": "48g"}
# Per-cell watchdog: a cell exceeding this is killed and recorded as a timeout.
# Generous by design (ingest included); real hangs run to infinity without it.
TIMEOUT_BY_SCALE = {"micro": 900, "tiny": 1800, "small": 7200,
                    "medium": 6 * 3600, "large": 24 * 3600}
HEAP_BY_SCALE = {"micro": "4g", "tiny": "4g", "small": "8g", "medium": "16g",
                 "large": "24g"}
SERVER_MEM_FRACTION = float(os.environ.get("BENCH_SERVER_MEM_FRACTION", "0.75"))

# ---------------------------------------------------------------- backends
# Each backend: image (bench image for the workload driver), topology, and for
# client_server: the server image + readiness probe + env.
BACKENDS = {
    "arcadedb_embedded": {
        "topology": "embedded",
        "image": "icde-bench:arcadedb",
    },
    "arcadedb_server": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "arcadedata/arcadedb:latest",
        # Heap parity with the embedded deployment (protocol: same JVM-heap
        # policy per scale tier) — the image's own default is -Xmx2G, which
        # starved the server vs embedded's per-scale heap. Setting JAVA_OPTS
        # also drops the image's ZGC default: both deployments run the same
        # default GC (G1) so the embedded-vs-server axis isolates transport,
        # not GC choice.
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=icdebench "
                             "-Darcadedb.server.defaultDatabases=bench[root]"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    "duckdb": {
        "topology": "embedded",
        "image": "icde-bench:duckdb",
    },
    "postgres": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "postgres:17",
        "server_env": ["-e", "POSTGRES_PASSWORD=icdebench", "-e", "POSTGRES_DB=bench"],
        "server_port": 5432,
        "ready_regex": r"database system is ready to accept connections",
    },
    # ---- L3 sparse lane ----
    "arcadedb_sparse_embedded": {
        "topology": "embedded",
        "image": "icde-bench:arcadedb",
    },
    "arcadedb_sparse_server": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "arcadedata/arcadedb:latest",
        # Heap parity with the embedded deployment (protocol: same JVM-heap
        # policy per scale tier) — the image's own default is -Xmx2G, which
        # starved the server vs embedded's per-scale heap. Setting JAVA_OPTS
        # also drops the image's ZGC default: both deployments run the same
        # default GC (G1) so the embedded-vs-server axis isolates transport,
        # not GC choice.
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=icdebench "
                             "-Darcadedb.server.defaultDatabases=bench[root]"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    "qdrant_sparse": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "qdrant/qdrant:latest",
        "server_port": 6333,
        "ready_regex": r"Qdrant (HTTP|gRPC) listening|Actix runtime found",
    },
    "milvus_sparse": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "milvusdb/milvus:latest",
        "server_env": ["-e", "DEPLOY_MODE=STANDALONE",
                       "-e", "ETCD_USE_EMBED=true",
                       "-e", "ETCD_DATA_DIR=/var/lib/milvus/etcd",
                       "-e", "ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml",
                       "-e", "COMMON_STORAGETYPE=local"],
        "server_volumes": ["-v", f"{HERE}/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml"],
        "server_cmd": ["milvus", "run", "standalone"],
        "server_port": 19530,
        "ready_regex": r"Proxy successfully started|successfully started",
    },
    "elasticsearch_sparse": {
        "topology": "client_server",
        "image": "icde-bench:client",
        "server_image": "docker.elastic.co/elasticsearch/elasticsearch:9.0.0",
        "server_env": ["-e", "discovery.type=single-node",
                       "-e", "xpack.security.enabled=false",
                       "-e", "ES_JAVA_OPTS=-Xms2g -Xmx4g"],
        "server_port": 9200,
        "ready_regex": r'"message":"started|current.health=\"GREEN\"',
    },
}

LANES = {
    # lane -> (bench script, backends, workloads)
    "l1": ("l1_tabular.py",
           ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres"],
           ["oltp", "olap"]),
    "l3s": ("l3_sparse.py",
            ["arcadedb_sparse_embedded", "arcadedb_sparse_server",
             "qdrant_sparse", "milvus_sparse", "elasticsearch_sparse"],
            ["search"]),
    # l2 graph, l3d dense, l4 timeseries: added as adapters land.
}


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw).stdout.strip()


def cgroup_dir(cid):
    p = f"/sys/fs/cgroup/system.slice/docker-{cid}.scope"
    if os.path.isdir(p):
        return p
    return sh(["bash", "-c",
               f"find /sys/fs/cgroup -name '*{cid}*' -type d 2>/dev/null | head -1"]) or None


def read_int(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return None


def read_cpu_stat(cg):
    out = {}
    try:
        for line in open(os.path.join(cg, "cpu.stat")):
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("usage_usec", "user_usec", "system_usec"):
                out[parts[0]] = int(parts[1])
    except Exception:
        pass
    return out


class CgroupSampler(threading.Thread):
    """Samples one container's cgroup: memory series, kernel peak, cpu totals."""

    def __init__(self, cid):
        super().__init__(daemon=True)
        self.cid, self.stop_evt = cid, threading.Event()
        self.series, self.peak, self.cpu = [], 0, {}

    def run(self):
        cg, t0 = None, time.time()
        while not self.stop_evt.is_set():
            cg = cg or cgroup_dir(self.cid)
            if cg:
                cur = read_int(os.path.join(cg, "memory.current"))
                pk = read_int(os.path.join(cg, "memory.peak"))
                if cur is not None:
                    self.series.append((round(time.time() - t0, 3), cur))
                if pk is not None:
                    self.peak = max(self.peak, pk)
                cpu = read_cpu_stat(cg)
                if cpu:
                    self.cpu = cpu
            time.sleep(SAMPLE_INTERVAL)

    def finish(self):
        self.stop_evt.set()
        self.join(timeout=5)


def mem_bytes(spec):
    m = re.fullmatch(r"(\d+)([gm])", spec)
    n, u = int(m.group(1)), m.group(2)
    return n * (1024 ** 3 if u == "g" else 1024 ** 2)


def image_digest(image):
    return sh(["docker", "inspect", "--format", "{{.Id}}", image])


def wait_ready(cid, regex, timeout_s=120):
    pat, t0 = re.compile(regex), time.time()
    while time.time() - t0 < timeout_s:
        logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
        if pat.search(logs.stdout + logs.stderr):
            return True
        time.sleep(1.0)
    return False


def docker_rm(cid):
    subprocess.run(["docker", "rm", "-f", cid], capture_output=True)


def run_cell(job, rep, scale, cpuset, tier, net_name):
    """Run one cell (backend x workload x scale, one repeat). Returns row dict."""
    be = BACKENDS[job["backend"]]
    run_id = f"{job['run_id']}_r{rep}"
    total_mem = mem_bytes(MEM_BY_SCALE[scale])
    heap = HEAP_BY_SCALE[scale]
    row = {"run_id": run_id, "lane": job["lane"], "backend": job["backend"],
           "workload": job["workload"], "scale": scale, "rep": rep, "tier": tier,
           "cpuset": cpuset, "topology": be["topology"], "heap": heap,
           "mem_cap": MEM_BY_SCALE[scale],
           "ts_utc": datetime.now(timezone.utc).isoformat()}

    server_cid, samplers = None, []
    try:
        if be["topology"] == "client_server":
            server_mem = int(total_mem * SERVER_MEM_FRACTION)
            client_mem = total_mem - server_mem
            row["mem_split"] = f"{SERVER_MEM_FRACTION:.2f}"
            server_cid = sh(["docker", "run", "-d", "--network", net_name,
                             "--label", "icde-bench=1",
                             "--name", f"srv-{run_id}",
                             "--cpuset-cpus", cpuset,
                             "--memory", str(server_mem), "--memory-swap", str(server_mem)]
                            + [s.format(heap=heap) for s in be.get("server_env", [])]
                            + be.get("server_volumes", [])
                            + [be["server_image"]]
                            + be.get("server_cmd", []))
            if len(server_cid) < 12 or not wait_ready(server_cid, be["ready_regex"]):
                row["error"] = "server_not_ready"
                return row
            s_srv = CgroupSampler(server_cid)
            s_srv.start()
            samplers.append(("server", s_srv))
            client_caps = ["--memory", str(client_mem), "--memory-swap", str(client_mem)]
            bench_env = ["-e", f"BENCH_SERVER_HOST=srv-{run_id}",
                         "-e", f"BENCH_SERVER_PORT={be['server_port']}"]
        else:
            client_caps = ["--memory", str(total_mem), "--memory-swap", str(total_mem)]
            bench_env = []

        cmd = (["docker", "run", "-d", "--network", net_name,
                "--label", "icde-bench=1",
                "--name", f"cli-{run_id}", "--cpuset-cpus", cpuset]
               + client_caps + bench_env
               + ["-e", f"ARCADEDB_HEAP={heap}", "-e", f"RUN_LABEL={run_id}",
                  "-v", f"{HERE}:/work", "-w", "/work", "-v", f"{DATA}:/data:ro",
                  be["image"], "python", job["script"],
                  "--backend", job["backend"], "--workload", job["workload"],
                  "--scale", scale, "--out", f"/work/results/raw/{run_id}.json"])
        cli_cid = sh(cmd)
        if len(cli_cid) < 12:
            row["error"] = "client_failed_to_start"
            return row
        s_cli = CgroupSampler(cli_cid)
        s_cli.start()
        samplers.append(("client", s_cli))

        timeout_s = TIMEOUT_BY_SCALE[scale]
        try:
            wait = subprocess.run(["docker", "wait", cli_cid], capture_output=True,
                                  text=True, timeout=timeout_s)
            rc = int(wait.stdout.strip() or "1")
        except subprocess.TimeoutExpired:
            rc = -1
            row["error"] = f"timeout_after_{timeout_s}s"
        logs = subprocess.run(["docker", "logs", cli_cid], capture_output=True, text=True)
        docker_rm(cli_cid)
        row["rc"] = rc
        if rc != 0 and "error" not in row:
            row["error"] = (logs.stderr or logs.stdout)[-800:]

        out_path = os.path.join(RAW, f"{run_id}.json")
        if os.path.exists(out_path):
            row.update(json.load(open(out_path)))
    finally:
        for name, s in samplers:
            s.finish()
            row[f"{name}_peak_mib"] = round(s.peak / 2**20, 1)
            row[f"{name}_cpu_usec"] = s.cpu.get("usage_usec")
        if len(samplers) == 2:
            row["peak_mib_sum"] = round(sum(s.peak for _, s in samplers) / 2**20, 1)
            row["cpu_usec_sum"] = sum((s.cpu.get("usage_usec") or 0) for _, s in samplers)
        elif samplers:
            row["peak_mib_sum"] = row.get("client_peak_mib")
            row["cpu_usec_sum"] = row.get("client_cpu_usec")
        if server_cid:
            docker_rm(server_cid)
    return row


def sweep_orphans():
    """Reap containers left by a previous crashed/killed runner. Safe because
    the protocol allows exactly one runner per host."""
    ids = sh(["docker", "ps", "-aq", "--filter", "label=icde-bench=1"]).split()
    if ids:
        print(f"sweeping {len(ids)} orphaned bench container(s): "
              + sh(["docker", "ps", "-a", "--filter", "label=icde-bench=1",
                    "--format", "{{.Names}}"]).replace("\n", " "))
        subprocess.run(["docker", "rm", "-f"] + ids, capture_output=True)


def split_cpuset(cpuset, n):
    """Split a 'a-b' cpuset into n disjoint contiguous shards ('a-m', ...)."""
    lo, hi = (int(x) for x in cpuset.split("-"))
    cpus = list(range(lo, hi + 1))
    if n > len(cpus):
        raise ValueError(f"{n} workers > {len(cpus)} cpus in {cpuset}")
    size = len(cpus) // n
    shards = []
    for w in range(n):
        chunk = cpus[w * size:(w + 1) * size] if w < n - 1 else cpus[(n - 1) * size:]
        shards.append(f"{chunk[0]}-{chunk[-1]}")
    return shards


def build_jobs(lanes, _workloads_arg):
    jobs = []
    for lane in lanes:
        script, backends, workloads = LANES[lane]
        for be in backends:
            for wl in workloads:
                jobs.append({"lane": lane, "backend": be, "workload": wl,
                             "script": script,
                             "run_id": f"{lane}_{be}_{wl}"})
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", default="l1")
    ap.add_argument("--backends", default="",
                    help="comma list to restrict backends (default: all in lane)")
    ap.add_argument("--workloads", default="oltp,olap")
    ap.add_argument("--scale", default="tiny", choices=list(MEM_BY_SCALE))
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--tier", default="paper", choices=["paper", "sweep"])
    ap.add_argument("--workers", type=int, default=0,
                    help="parallel workers on disjoint cpuset shards "
                         "(sweep tier only; 0 = 1 for paper, 2 for sweep)")
    ap.add_argument("--timeout", type=int, default=0,
                    help="per-cell timeout override in seconds (0 = scale default)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.timeout:
        for k in TIMEOUT_BY_SCALE:
            TIMEOUT_BY_SCALE[k] = args.timeout

    workers = args.workers or (1 if args.tier == "paper" else 2)
    if args.tier == "paper" and workers != 1:
        ap.error("paper tier is strictly serial: one cell at a time, full cpuset")
    if workers > 1:
        host_ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        need = workers * mem_bytes(MEM_BY_SCALE[args.scale])
        if need > host_ram * 0.85:
            ap.error(f"{workers} workers x {MEM_BY_SCALE[args.scale]} = "
                     f"{need/2**30:.0f}g exceeds 85% of host RAM "
                     f"({host_ram/2**30:.0f}g) — this scale runs serially")
    shards = split_cpuset(CPUSET, workers)

    lanes = args.lanes.split(",")
    workloads = args.workloads.split(",")
    os.makedirs(RAW, exist_ok=True)

    net_name = "icde-bench"
    subprocess.run(["docker", "network", "create", net_name], capture_output=True)
    sweep_orphans()

    jobs = build_jobs(lanes, workloads)
    if args.backends:
        keep = set(args.backends.split(","))
        jobs = [j for j in jobs if j["backend"] in keep]
    cells = [(j, r) for j in jobs for r in range(1, args.reps + 1)]
    random.Random(args.seed).shuffle(cells)  # shuffled order even in serial tier

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {"ts": ts, "tier": args.tier, "scale": args.scale, "cpuset": CPUSET,
                "workers": workers, "shards": shards,
                "reps": args.reps, "seed": args.seed,
                "mem": MEM_BY_SCALE[args.scale], "heap": HEAP_BY_SCALE[args.scale],
                "server_mem_fraction": SERVER_MEM_FRACTION,
                "images": {}}
    for j in jobs:
        be = BACKENDS[j["backend"]]
        for img in filter(None, [be.get("image"), be.get("server_image")]):
            manifest["images"].setdefault(img, image_digest(img))
    json.dump(manifest, open(os.path.join(RESULTS, f"manifest-{ts}.json"), "w"), indent=2)

    rows = []
    jsonl = open(os.path.join(RESULTS, "runs.jsonl"), "a")
    total = len(cells)
    print(f"{total} cell-runs (tier={args.tier}, scale={args.scale}, "
          f"workers={workers}, shards={shards})")

    pending = list(cells)
    active_backends = set()
    cv = threading.Condition()
    done = [0]

    def worker(shard):
        while True:
            with cv:
                idx = next((i for i, (j, _) in enumerate(pending)
                            if j["backend"] not in active_backends), None)
                if idx is None:
                    if not pending:
                        return
                    cv.wait(5)  # all queued backends busy elsewhere; re-check
                    continue
                job, rep = pending.pop(idx)
                active_backends.add(job["backend"])
            t0 = time.time()
            try:
                row = run_cell(job, rep, args.scale, shard, args.tier, net_name)
            finally:
                with cv:
                    active_backends.discard(job["backend"])
                    cv.notify_all()
            row["manifest"] = ts
            status = row.get("error", "ok")[:60]
            with cv:
                rows.append(row)
                jsonl.write(json.dumps(row) + "\n")
                jsonl.flush()
                done[0] += 1
                print(f"  [{done[0]}/{total}] {row['run_id']} "
                      f"{time.time()-t0:.1f}s ({shard}) -> {status}")

    threads = [threading.Thread(target=worker, args=(s,)) for s in shards]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if rows:
        cols = sorted({k for r in rows for k in r})
        path = os.path.join(RESULTS, f"runs-{ts}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
