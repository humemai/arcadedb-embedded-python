#!/usr/bin/env python3
"""E4 as a runner lane: the deployment decomposition through the same
container plumbing every other cell gets (2026-09-07).

The runner starts the pinned server container on the cell network and hands
this script BENCH_SERVER_HOST; the cell's client image is the wheel image, so
the in-process arms run here and the served arm talks to the container. The
probe itself is unchanged (deployment_decomp_probe.py); this wrapper maps the
runner's arguments onto it, then writes the artifact where export_web reads
E4 from: results/e4decomp_<pin>/decomp3m_<pin>_rep<r>.json.

The client image has no `requests`; the probe gets a stdlib shim.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _shim_requests():
    """requests.Session-alike over urllib, enough for the probe."""
    import base64
    import urllib.request

    class _Resp:
        def __init__(self, status, body, headers):
            self.status_code, self._body, self.headers = status, body, headers
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}: {self._body[:200]!r}")
        def json(self):
            return json.loads(self._body or "{}")

    class Session:
        auth = None
        def _do(self, method, url, auth=None, json_body=None, headers=None, timeout=300):
            data = json.dumps(json_body).encode() if json_body is not None else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Content-Type", "application/json")
            a = auth or self.auth
            if a:
                req.add_header("Authorization", "Basic " + base64.b64encode(f"{a[0]}:{a[1]}".encode()).decode())
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return _Resp(r.status, r.read().decode(), dict(r.headers))
            except urllib.error.HTTPError as e:
                return _Resp(e.code, e.read().decode(errors="replace"), dict(e.headers))
        def get(self, url, auth=None, timeout=300, headers=None):
            return self._do("GET", url, auth, None, headers, timeout)
        def post(self, url, auth=None, json=None, timeout=300, headers=None):
            return self._do("POST", url, auth, json, headers, timeout)
        def close(self):
            pass

    import types
    m = types.ModuleType("requests")
    m.Session = Session
    sys.modules["requests"] = m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--workload", required=True)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        import requests  # noqa: F401
    except ImportError:
        _shim_requests()
    host = os.environ["BENCH_SERVER_HOST"]
    port = os.environ.get("BENCH_SERVER_PORT", "2480")
    heap = os.environ.get("ARCADEDB_HEAP", "6g")
    os.environ.setdefault("REPS", "15")
    os.environ.setdefault("WARMUP", "3")
    sys.path.insert(0, HERE)
    import deployment_decomp_probe as probe
    sys.argv = ["deployment_decomp_probe.py", "--docker", f"http://{host}:{port}",
                "--docker-password", "dbbenchpass", "--heap", heap,
                "--out", args.out, "--root", "/tmp/e4_root"]
    probe.main()
    payload = json.load(open(args.out))
    meta = payload.get("meta", {})
    # The runner's row: what the lane measured, in fields a reader of runs.jsonl
    # expects; the full artifact stays in the file.
    from importlib.metadata import version as _v
    payload["engine_version"] = _v("arcadedb-embedded")
    for n, d in payload.get("results", {}).get("embedded", {}).items():
        payload[f"embedded_{n}_p50_ms"] = d.get("p50_ms")
    json.dump(payload, open(args.out, "w"))
    pin = os.environ.get("ARCADEDB_ENGINE_COMMIT", "").strip()
    m = re.search(r"_r(\d+)$", os.environ.get("RUN_LABEL", ""))
    if pin and m:
        dst_dir = os.path.join(HERE, "results", f"e4decomp_{pin}")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, f"decomp3m_{pin}_rep{m.group(1)}.json")
        shutil.copyfile(args.out, dst)
        print(f"artifact -> {dst}", flush=True)
    print(f"E4 rep done: rows={meta.get('rows')} arms={sorted(payload.get('results', {}))}", flush=True)


if __name__ == "__main__":
    main()
