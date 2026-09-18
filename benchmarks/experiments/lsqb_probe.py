#!/usr/bin/env python3
"""LSQB dialect probe: build one graph engine's capped SF1 slice once, then
answer query texts on demand until told to stop (DECISIONS #92, #104).

Run through the runner's --driver hook so the cell is the real one (image,
server container, cpuset, env caps):

    BENCH_GRAPH_SOURCE=ldbc BENCH_GRAPH_MSG_LIMIT=30000 BENCH_GRAPH_PERSON_LIMIT=2000 \
    python runner.py --lanes l2 --backends surrealdb_graph --workloads olap --scale sf1 \
      --reps 1 --tier sweep --workers 1 --results-file runs_probe_lsqb.jsonl \
      --driver lsqb_probe.py --driver-out-dir lsqb_probe

The driver loads the adapter exactly as l2_graph.main does for the olap
workload, runs the adapter's own nine LSQB texts (each under try/except, the
error text kept verbatim), writes PROBE_OUT, and then polls
results/lsqb_probe/<backend>.req.json for more texts to run:

    [{"name": "q1-alt", "text": "..."}]              # Cypher/AQL/SurrealQL/SQL
    [{"name": "q1-alt", "coll": "x", "pipeline": [...]}]   # MongoDB

Each request is answered in <backend>.resp.json (rows or the error, with the
wall time), the request file is removed, and a <backend>.stop file ends the
session. Every answer is what the engine returned, never interpreted here.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import l2_graph  # noqa: E402
from graph_common import LSQB_QUERIES, OLAP_QUERIES  # noqa: E402

PROBE_DIR = "/work/results/lsqb_probe"
MAX_S = float(os.environ.get("LSQB_PROBE_MAX_S") or 3000)


def _raw(ad, req):
    """Run one request through the adapter's native execution path."""
    name = ad.name
    if "pipeline" in req:
        return list(ad.db[req["coll"]].aggregate(req["pipeline"], allowDiskUse=True))
    text = req["text"]
    if name == "duckpgq_graph":
        return ad.cx.execute(text).fetchall()
    if name.startswith("surrealdb"):
        return ad._rows(ad.db.query(text))
    if name == "arangodb_graph":
        return ad._n(text)
    if name == "mongodb_graph":
        raise ValueError("MongoDB requests need coll + pipeline")
    return ad.run_cypher(text)


def _answer(fn):
    t0 = time.perf_counter()
    try:
        rows = fn()
        rows = [list(r) if isinstance(r, (list, tuple)) else r for r in rows]
        return {"rows": rows[:20], "n_rows": len(rows), "s": round(time.perf_counter() - t0, 3)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {e}",
                "trace": traceback.format_exc()[-2000:],
                "s": round(time.perf_counter() - t0, 3)}


def main():
    backend = os.environ["BENCH_MP_BACKEND"]
    scale = os.environ["BENCH_MP_SCALE"]
    out_path = os.environ["PROBE_OUT"]
    os.makedirs(PROBE_DIR, exist_ok=True)
    ad = l2_graph.ADAPTERS[backend]()
    t0 = time.perf_counter()
    ad.connect()
    ad._scale = scale
    ad._load_messages = True
    n_persons = l2_graph.SCALE_PERSONS[scale]
    if l2_graph._GRAPH_SOURCE == "ldbc":
        l2_graph.gen_persons = lambda _n: l2_graph._ldbc.gen_persons(scale)
        l2_graph.gen_edges = lambda _n: l2_graph._ldbc.gen_edges(scale)
    ad.build(n_persons)
    ad.build_messages()
    ad.post_build("olap")
    build_s = round(time.perf_counter() - t0, 1)
    result = {"backend": backend, "version": ad.version, "build_s": build_s,
              "msg_counts": getattr(ad, "msg_counts", None), "queries": {}}
    print(json.dumps({"built": build_s, "msg": result["msg_counts"]}), flush=True)
    only = [q for q in os.environ.get("LSQB_PROBE_ONLY", "").split(",") if q]
    for q in list(LSQB_QUERIES) + [q for q in OLAP_QUERIES if q not in LSQB_QUERIES]:
        if only and q not in only:
            continue
        reason = getattr(ad, "UNEXPRESSIBLE", {}).get(q)
        if reason:
            result["queries"][q] = {"unexpressible": reason}
            continue
        result["queries"][q] = _answer(lambda: ad.run_olap(q))
        print(q, json.dumps(result["queries"][q])[:300], flush=True)
        with open(out_path, "w") as f:
            json.dump([result], f)
    with open(out_path, "w") as f:
        json.dump([result], f)
    req = os.path.join(PROBE_DIR, f"{backend}.req.json")
    resp = os.path.join(PROBE_DIR, f"{backend}.resp.json")
    stop = os.path.join(PROBE_DIR, f"{backend}.stop")
    print("probe ready; waiting for requests", flush=True)
    t_start = time.time()
    # results/lsqb_probe/autostop (host-side) ends the session as soon as the
    # adapter's own nine are answered: the unattended queue's mode.
    if os.path.exists(os.path.join(PROBE_DIR, "autostop")):
        t_start -= MAX_S
    while time.time() - t_start < MAX_S and not os.path.exists(stop):
        if os.path.exists(req):
            try:
                reqs = json.load(open(req))
            except Exception as e:  # noqa: BLE001
                reqs = []
                print("bad request file:", e, flush=True)
            os.remove(req)
            answers = {}
            for r in reqs:
                answers[r["name"]] = _answer(lambda r=r: _raw(ad, r))
                print(r["name"], json.dumps(answers[r["name"]])[:300], flush=True)
            with open(resp + ".tmp", "w") as f:
                json.dump(answers, f)
            os.replace(resp + ".tmp", resp)
        time.sleep(1)
    if os.path.exists(stop):
        os.remove(stop)
    ad.close()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
