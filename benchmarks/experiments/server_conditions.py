#!/usr/bin/env python3
"""Record what a SERVER container actually ran under, observed from the daemon.

THE PROBLEM THIS SOLVES. bench_common.run_conditions() reads the cgroup of the
process it runs in, which is right for an embedded cell and wrong for a served
one: there the driver is a separate container, so the row stamps the CLIENT's
cpuset, heap and memory cap while the engine under test sits elsewhere with
different ones. Its own docstring says so. The visible symptom is
mp_arcsrv_2681.json recording heap=None and mem_cap=9g, which is the client's
quarter of the 36g envelope, and F7 finding that the published dense cells
record no degree at all.

WHY NOT JUST PASS THE VALUES IN. Because that is assertion, and this codebase
has been bitten by assertion three times: a driver that stamped
"26.8.1.dev22" onto a dev20 run, adapters that hardcoded "server:latest" while
runner.py pinned a digest, and a hand-written sidecar (results/srv109/) whose
numbers nobody could re-derive. A launcher that writes down what it MEANT to
do cannot catch the case where it did something else.

So the values come from `docker inspect`, which is the daemon's account of the
container as created, plus the server's own answer over HTTP. What the caller
expected is passed in only to be CHECKED against that, never to be recorded in
its place. Disagreement is a failure, the same way the F5 version gate treats
a version mismatch.

    python3 server_conditions.py --server srv-l3d_arcadedb_server_deep10m \\
        --client cli-l3d_arcadedb_server_deep10m \\
        --expect-heap 24g --expect-cap 36g \\
        --out results/dense_mp_2681/server_conditions.json

Exit status is 1 if anything the caller expected disagrees with what the
daemon reports, or if the server could not be interrogated.
"""
import argparse
import json
import os
import re
import subprocess
import sys


def _inspect(name, fmt):
    p = subprocess.run(["docker", "inspect", "-f", fmt, name],
                       capture_output=True, text=True)
    if p.returncode != 0:
        return None
    v = p.stdout.strip()
    return v if v and v not in ("<no value>", "0", "") else None


def _gib(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    return f"{n // (1 << 30)}g" if n else None


def _heap_from_env(name):
    """-Xmx as the container was actually created with it.

    ArcadeDB takes the heap through ARCADEDB_OPTS_MEMORY or JAVA_OPTS, and the
    e3 harness learned the hard way that setting JAVA_OPTS drops the image's
    own defaults. Either may carry it, so read both and let the LAST -Xmx win,
    which is what the JVM itself does.
    """
    raw = _inspect(name, "{{json .Config.Env}}")
    if not raw:
        return None, None
    try:
        env = json.loads(raw)
    except Exception:
        return None, None
    joined = " ".join(env)
    hits = re.findall(r"-Xmx(\d+)([gGmM])", joined)
    if not hits:
        return None, joined
    val, unit = hits[-1]
    heap = f"{val}g" if unit in "gG" else f"{int(val) // 1024}g"
    return heap, joined


def _server_version(host, port, password):
    """Ask the server what it is. Host-side over the published port, because
    the release image ships no curl -- 90 silent probe failures established
    that once already."""
    import base64
    import urllib.request
    auth = "Basic " + base64.b64encode(f"root:{password}".encode()).decode()
    req = urllib.request.Request(f"http://{host}:{port}/api/v1/server")
    req.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return (json.load(r) or {}).get("version")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="server container name")
    ap.add_argument("--client", help="driver container name, if it still exists")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-heap", help="e.g. 24g; checked, not recorded")
    ap.add_argument("--expect-cap", help="e.g. 36g; checked, not recorded")
    ap.add_argument("--expect-cpuset", default="0-11")
    ap.add_argument("--http-host", default="localhost")
    ap.add_argument("--http-port")
    ap.add_argument("--password", default=os.environ.get("BENCH_SERVER_PASSWORD",
                                                         "dbbenchpass"))
    a = ap.parse_args()

    heap, env_joined = _heap_from_env(a.server)
    out = {
        "_note": "Observed from `docker inspect` and the server's own HTTP "
                 "reply, not from what the launching script intended. "
                 "run_conditions() inside the rep files describes the CLIENT "
                 "container; these are the ENGINE's conditions.",
        "server_container": a.server,
        "server_cpuset": _inspect(a.server, "{{.HostConfig.CpusetCpus}}"),
        "server_mem_cap": _gib(_inspect(a.server, "{{.HostConfig.Memory}}")),
        "server_heap": heap,
        "server_image": _inspect(a.server, "{{.Image}}"),
        "server_image_ref": _inspect(a.server, "{{.Config.Image}}"),
    }
    if a.client:
        out["client_cpuset"] = _inspect(a.client, "{{.HostConfig.CpusetCpus}}")
        out["client_mem_cap"] = _gib(_inspect(a.client, "{{.HostConfig.Memory}}"))

    if a.http_port:
        out["server_version"] = _server_version(a.http_host, a.http_port,
                                                a.password)

    # The envelope the CELL got, which is what F3 compares. A served cell
    # splits one envelope across two containers, so the total is the sum, and
    # reporting only one side is how a compliant 0.75/0.25 split reads as a
    # violation.
    def _g(x):
        return int(x[:-1]) if x and x.endswith("g") else None
    s, c = _g(out.get("server_mem_cap")), _g(out.get("client_mem_cap"))
    if s and c:
        out["cell_mem_cap"] = f"{s + c}g"
        out["mem_split_observed"] = round(s / (s + c), 3)

    bad = []
    for want, got, what in ((a.expect_heap, out["server_heap"], "heap"),
                            (a.expect_cap, out["server_mem_cap"], "mem cap"),
                            (a.expect_cpuset, out["server_cpuset"], "cpuset")):
        if want and got and str(want) != str(got):
            bad.append(f"  {what}: launcher expected {want}, docker reports {got}")
        elif want and not got:
            bad.append(f"  {what}: launcher expected {want}, could not observe it"
                       + (f" (env was: {env_joined[:120]})"
                          if what == "heap" and env_joined else ""))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))

    if bad:
        print("\nSERVER CONDITIONS DISAGREE WITH THE LAUNCHER:", file=sys.stderr)
        print("\n".join(bad), file=sys.stderr)
        print("The sidecar is written anyway, because the observation is the "
              "fact and the expectation is the claim. But this cell is not "
              "publishable until they agree.", file=sys.stderr)
        sys.exit(1)
    print(f"\nwrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
