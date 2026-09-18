#!/usr/bin/env python3
"""F55 diagnostic: what ArangoDB's IVF index holds and answers at deep10m.

BUGS.md F55: the arangodb_dense arm at deep10m (9,990,000 DEEP vectors, 96
dims, fp32) calibrated nProbe up to every one of its 12,643 lists and still
answered recall@10 of 0.0000 or 0.0001 on five repetitions, while the same
adapter scores 0.986 to 0.990 at the one-million tier. Nothing in the row
says WHY: n_docs is len(train), never the server's count; the adapter never
reads the index definition back; the answers were never compared with an
exact scan of the same collection. This probe checks all of that, without
timing anything, and prints one JSON line per check so the cell log is the
artifact.

It runs inside the campaign's client image against a running ArangoDB
server, as a runner.py --driver cell:

    python3 -u runner.py --lanes dense --backends arangodb_dense --scale deep10m \
        --reps 1 --driver probe_arango_deep10m.py --driver-out-dir probe_f55 \
        --results-file probe_f55.jsonl

The runner starts a FRESH server for the cell, so the probe loads the corpus
through the existing adapter (l3d_dense.ArangoDense.build: the same
import_bulk batches and the same vector_index call the campaign used) unless
the collection is already there. It then checks, in order:

  1. counts: the collection's own count against the corpus; how many
     documents have an `embedding` of exactly `dim` numeric entries; how many
     have `vid` != TO_NUMBER(_key); min and max of `vid`.
  2. samples: ten documents fetched by _key, their `vid` and the first three
     entries of `embedding` against the corpus row, and the max abs
     difference over the whole vector.
  3. the index as the server reports it, every parameter, with the hidden
     fields (trainingState, errorMessage, resolvedNLists) from
     GET /_api/index?withHidden=true.
  4. for PROBE_NQ queries (default 5): the shipped ground truth, a numpy
     exact scan over the corpus file (does the ground-truth file match the
     corpus file at all?), an exact AQL scan over the collection WITHOUT the
     index (L2_DISTANCE, SORT, LIMIT 10), the index's answer at the
     defaultNProbe the adapter chose, and the index's answer at nProbe =
     nLists (every list, which for IVF-Flat must equal the exact scan). Each
     answer is scored against the ground truth and, for the index answers,
     the true distances of what it returned are printed next to the true
     top-10 distances.

Output: JSON lines on stdout, prefixed PROBE, and the same records as a list
in PROBE_OUT when the runner sets it (the --driver contract; the first record
carries build_s and recall_at_10 so the row is self-describing).

Environment: BENCH_SERVER_HOST/PORT (the runner sets them), BENCH_MP_SCALE
(default deep10m), BENCH_DENSE_DATA (the lane's default), PROBE_NQ,
PROBE_SAMPLES, PROBE_SKIP_AQL_SCAN=1 to skip the exact AQL scans (each is a
full pass over the collection).

run_probe() takes the corpus, queries and ground truth as arrays so the same
checks run on a synthetic corpus on the laptop (the F55 bisect).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

import arango_common
import l3d_dense
from l3d_dense import ArangoDense, K

COL = "article"
FIELD = "embedding"


def emit(rec: dict, sink: list):
    sink.append(rec)
    print("PROBE " + json.dumps(rec, default=float), flush=True)


def _http_get(host, port, path):
    """GET against the server with the campaign's root credentials; the
    hidden index fields are not reachable through python-arango."""
    import requests
    r = requests.get(f"http://{host}:{port}{path}", auth=("root", arango_common.PASSWORD),
                     timeout=600)
    r.raise_for_status()
    return r.json()


def index_definition(host, port, dbname=arango_common.DB, col=COL):
    """Every index on the collection as the server reports it, hidden fields
    and per-shard training state included (3.12.10+ reports trainingState,
    errorMessage and resolvedNLists)."""
    data = _http_get(host, port, f"/_db/{dbname}/_api/index?collection={col}&withHidden=true&withStats=true")
    return [ix for ix in data.get("indexes", []) if ix.get("type") == "vector"], data.get("indexes", [])


def aql_one(db, query, bind):
    return list(db.aql.execute(query, bind_vars=bind, ttl=3600))


def counts(db, n_expected: int, dim: int) -> dict:
    total = db.collection(COL).count()
    shape = aql_one(db,
                    f"FOR d IN {COL} "
                    f"COLLECT ok = (IS_ARRAY(d.{FIELD}) AND LENGTH(d.{FIELD}) == @dim "
                    f"AND LENGTH(d.{FIELD}[* FILTER !IS_NUMBER(CURRENT)]) == 0) "
                    f"WITH COUNT INTO c RETURN {{ok, c}}", {"dim": dim})
    good = sum(r["c"] for r in shape if r["ok"])
    bad = sum(r["c"] for r in shape if not r["ok"])
    ids = aql_one(db,
                  f"FOR d IN {COL} COLLECT AGGREGATE mn = MIN(d.vid), mx = MAX(d.vid), "
                  f"mismatched = SUM(TO_NUMBER(d._key) == d.vid ? 0 : 1), "
                  f"nonint = SUM(d.vid == FLOOR(d.vid) ? 0 : 1) "
                  f"RETURN {{mn, mx, mismatched, nonint}}", {})[0]
    return {"check": "counts", "collection_count": total, "n_expected": n_expected,
            "count_matches_corpus": total == n_expected,
            "docs_with_exact_dim_numeric_vector": good, "docs_with_other_vector": bad,
            "vid_min": ids["mn"], "vid_max": ids["mx"],
            "docs_vid_ne_key": ids["mismatched"], "docs_vid_not_integer": ids["nonint"]}


def samples(db, corpus, n: int, how_many: int) -> dict:
    rng = np.random.default_rng(7)
    picks = sorted(set([0, 1, n // 2, n - 2, n - 1] + [int(x) for x in rng.integers(0, n, how_many)]))[:how_many]
    col = db.collection(COL)
    rows = []
    for i in picks:
        d = col.get(str(i))
        if d is None:
            rows.append({"key": str(i), "present": False})
            continue
        emb = d.get(FIELD)
        row = {"key": str(i), "present": True, "vid": d.get("vid"), "vid_eq_key": d.get("vid") == i,
               "len": (len(emb) if isinstance(emb, list) else None),
               "first3_server": (emb[:3] if isinstance(emb, list) else emb),
               "first3_corpus": [float(x) for x in corpus[i][:3]]}
        if isinstance(emb, list) and len(emb) == corpus.shape[1]:
            row["max_abs_diff"] = float(np.max(np.abs(np.asarray(emb, dtype=np.float32) - corpus[i])))
        rows.append(row)
    return {"check": "samples", "rows": rows}


def true_dists(corpus, q, ids):
    """Squared L2 (what FAISS ranks by) from q to corpus[ids]; None for an id
    the corpus does not have."""
    out = []
    for i in ids:
        if 0 <= i < len(corpus):
            out.append(float(np.sum((corpus[i] - q) ** 2)))
        else:
            out.append(None)
    return out


def score(ids, g):
    return len(set(int(x) for x in ids[:K]) & set(int(x) for x in g[:K])) / K


def query_checks(db, adapter, corpus, queries, gt, nlists, nprobe_default, dim, skip_aql):
    recs = []
    # numpy exact scan over the corpus file for the probe queries: the check
    # that the ground-truth file describes this corpus file.
    np_gt = l3d_dense._exact_gt(np.asarray(queries, dtype=np.float32), corpus, len(corpus))
    for qi, q in enumerate(queries):
        g = [int(x) for x in gt[qi][:K]]
        rec = {"check": "query", "qi": qi, "gt": g,
               "gt_true_dists": true_dists(corpus, q, g),
               "numpy_exact": [int(x) for x in np_gt[qi]],
               "numpy_exact_vs_gt": score(np_gt[qi], g)}
        if not skip_aql:
            exact = aql_one(db, f"FOR d IN {COL} LET s = L2_DISTANCE(d.{FIELD}, @q) "
                                f"SORT s LIMIT @k RETURN {{vid: d.vid, s: s}}",
                            {"q": q.tolist(), "k": K})
            rec["aql_exact_no_index"] = [int(r["vid"]) for r in exact]
            rec["aql_exact_dists"] = [float(r["s"]) ** 2 for r in exact]
            rec["aql_exact_vs_gt"] = score(rec["aql_exact_no_index"], g)
        for label, np_ in (("index_default_nprobe", nprobe_default), ("index_all_lists", nlists)):
            try:
                ids = adapter.search(q, K, nprobe=np_)
                rec[label] = ids
                rec[label + "_nprobe"] = np_
                rec[label + "_vs_gt"] = score(ids, g)
                rec[label + "_true_dists"] = true_dists(corpus, q, ids)
            except Exception as e:  # noqa: BLE001
                rec[label + "_error"] = f"{type(e).__name__}: {e}"
        recs.append(rec)
    return recs


def run_probe(adapter, corpus, queries, gt, dim, host, port, nq=5, nsamples=10,
              skip_aql=False, sink=None) -> list:
    """All checks against an adapter whose build() has run (or whose
    collection already exists). Returns the records; emits each as it goes."""
    sink = [] if sink is None else sink
    db = adapter.db
    n = len(corpus)
    emit(counts(db, n, dim), sink)
    emit(samples(db, corpus, n, nsamples), sink)
    vec_ix, all_ix = index_definition(host, port)
    emit({"check": "indexes", "vector_indexes": vec_ix, "all_index_types": sorted({ix.get("type") for ix in all_ix})}, sink)
    nlists = None
    nprobe_default = None
    if vec_ix:
        p = vec_ix[0].get("params", {})
        nlists = vec_ix[0].get("resolvedNLists") or p.get("nLists")
        nprobe_default = p.get("defaultNProbe")
    # the adapter's own operating point wins where it ran in this process
    nlists = getattr(adapter, "ivf_nlists", None) or nlists
    nprobe_default = getattr(adapter, "ivf_nprobe", None) or nprobe_default or 1
    if not nlists:
        emit({"check": "abort", "reason": "no vector index reported and the adapter built none"}, sink)
        return sink
    for rec in query_checks(db, adapter, corpus, queries[:nq], gt[:nq], int(nlists),
                            int(nprobe_default), dim, skip_aql):
        emit(rec, sink)
    summary = {"check": "summary", "n": n, "dim": dim, "nlists": int(nlists),
               "nprobe_default": int(nprobe_default),
               "mean_recall_index_all_lists": float(np.mean([r["index_all_lists_vs_gt"] for r in sink
                                                             if r.get("check") == "query" and "index_all_lists_vs_gt" in r] or [float("nan")])),
               "mean_recall_index_default": float(np.mean([r["index_default_nprobe_vs_gt"] for r in sink
                                                           if r.get("check") == "query" and "index_default_nprobe_vs_gt" in r] or [float("nan")])),
               "mean_recall_aql_exact": float(np.mean([r["aql_exact_vs_gt"] for r in sink
                                                       if r.get("check") == "query" and "aql_exact_vs_gt" in r] or [float("nan")])),
               "mean_recall_numpy_exact": float(np.mean([r["numpy_exact_vs_gt"] for r in sink
                                                         if r.get("check") == "query"] or [float("nan")]))}
    emit(summary, sink)
    return sink


def main():
    scale = os.environ.get("BENCH_MP_SCALE", "deep10m")
    host = os.environ.get("BENCH_SERVER_HOST", "localhost")
    port = os.environ.get("BENCH_SERVER_PORT", "8529")
    nq = int(os.environ.get("PROBE_NQ", "5"))
    nsamples = int(os.environ.get("PROBE_SAMPLES", "10"))
    skip_aql = os.environ.get("PROBE_SKIP_AQL_SCAN") == "1"
    sink: list = []
    train, test, gt = l3d_dense.load_dataset(scale)
    dim = l3d_dense.DIM
    emit({"check": "dataset", "scale": scale, "n": len(train), "dim": dim, "nq_available": len(test)}, sink)

    b = ArangoDense()
    cl, db, ver = arango_common.connect(fresh=False)
    have = db.has_collection(COL) and db.collection(COL).count() > 0
    if have:
        b.cl, b.db, b.version = cl, db, ver
        emit({"check": "load", "loaded_here": False, "engine_version": ver,
              "note": "collection already present; the adapter's build() was not run"}, sink)
        build_s = None
    else:
        arango_common.close(cl)
        b.connect()                       # fresh database, as the campaign cell had
        t0 = time.perf_counter()
        b.build(train)                    # the adapter's own import_bulk + vector_index
        build_s = round(time.perf_counter() - t0, 2)
        emit({"check": "load", "loaded_here": True, "engine_version": b.version, "build_s": build_s,
              "ivf_nlists": b.ivf_nlists, "ivf_nprobe_initial": b.ivf_nprobe}, sink)
    run_probe(b, train, test, gt, dim, host, port, nq=nq, nsamples=nsamples, skip_aql=skip_aql, sink=sink)
    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        first = {"probe": "probe_arango_deep10m", "scale": scale, "build_s": build_s,
                 "recall_at_10": next((r["mean_recall_index_all_lists"] for r in sink if r.get("check") == "summary"), None),
                 "quantization": "fp32", "records": sink}
        with open(outp, "w") as f:
            json.dump([first], f, indent=1, default=float)
    b.close()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    os._exit(0)
