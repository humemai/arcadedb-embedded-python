"""ArangoDB 3.12 through python-arango, served only.

python-arango is an HTTP client; the engine has no in-process mode, so
ArangoDB gets one row per table, like MongoDB (2026-09-13, DECISIONS #78).
Every lane connects through here so the database is fresh, the version is
the server's own, and the vector index gets the same operating point.

The vector index is FAISS IVF (inverted lists over trained centroids), not
HNSW: it has no graph degree to match, so l3d_dense.degree_stamp names it
ivf_flat_no_degree and the row records its operating point instead.

MATCHED BY EFFECT, not by parameter (FAIRNESS F7, 2026-09-13). nLists follows
FAISS's own guideline for 1M to 10M vectors, "between 4*sqrt(n) and
16*sqrt(n)" (faiss wiki, "Guidelines to choose an index"), at the low end:
round(4*sqrt(n)). nProbe is not typed: after the index is built and before
any timed pass, calibrate_nprobe() binary-searches the smallest nProbe whose
recall@10 on a held-out slice of 200 queries (fixture queries 1000:1200, never
the timed 1,000; l3d_dense.calibration_slice) reaches the target, and the target is the
frozen recall@10 of ArcadeDB's own embedded fp32 arm at the same scale
(results/runs_paper.csv, the tracked file the container sees at /work).
Matching our own arm is the neutral choice: a higher target slows them and
flatters us, a lower one speeds them and flatters them. Everything chosen is
recorded on the row: ivf_nlists, ivf_nprobe, ivf_recall_target,
ivf_calibration_recall, ivf_calibration_queries, ivf_calibration_slice.

trainingIterations stays at 25, FAISS's k-means default (niter=25); at
4*sqrt(n) lists the training set is the whole collection, and the
calibration recall is the check that the centroids converged well enough.
"""
from __future__ import annotations

import math
import os
import time

PASSWORD = "dbbenchpass"
DB = "bench"
# The starting probe fraction, used only where nothing calibrates (the
# cross-model lane, which measures no recall) and as the search's first guess.
NPROBE_FRAC = float(os.environ.get("BENCH_ARANGO_NPROBE_FRAC", "0.125"))
TRAINING_ITERATIONS = 25
CALIBRATION_QUERIES = 200
# Only when the frozen CSV has no ArcadeDB fp32 row at the scale: the DEEP-10M
# reading at the September pin, the lower of the two published scales.
FALLBACK_RECALL_TARGET = 0.95
FROZEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "runs_paper.csv")


def connect(fresh: bool = True, wait_s: int = 120):
    """(client, bench db, "arangodb:<server version>"), waiting for the server."""
    from arango import ArangoClient
    host = os.environ.get("BENCH_SERVER_HOST", "localhost")
    port = os.environ.get("BENCH_SERVER_PORT", "8529")
    # request_timeout=None: a 10M vector-index build and an SF10 analytics
    # query are single HTTP calls that outlive the client's 60 s default.
    cl = ArangoClient(hosts=f"http://{host}:{port}", request_timeout=None)
    last = None
    for _ in range(wait_s * 2):
        try:
            sysdb = cl.db("_system", username="root", password=PASSWORD, verify=True)
            ver = sysdb.version()
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5)
    else:
        raise RuntimeError(f"arangodb: no server at {host}:{port} after {wait_s}s: {last}")
    if fresh and sysdb.has_database(DB):
        sysdb.delete_database(DB)
    if not sysdb.has_database(DB):
        sysdb.create_database(DB)
    return cl, cl.db(DB, username="root", password=PASSWORD), f"arangodb:{ver}"


def ivf_params(n: int) -> tuple[int, int]:
    nlists = max(4, int(round(4 * math.sqrt(n))))
    nprobe = max(1, int(math.ceil(nlists * NPROBE_FRAC)))
    return nlists, nprobe


def recall_target(scale: str) -> tuple[float, str]:
    """(target, where it came from): the median frozen recall@10 of
    arcadedb_dense_embedded fp32 at this scale, else the fallback."""
    import csv
    import statistics
    env = os.environ.get("BENCH_ARANGO_RECALL_TARGET")
    if env:
        return float(env), "env BENCH_ARANGO_RECALL_TARGET"
    try:
        with open(FROZEN, newline="") as fh:
            vals = [float(r["recall_at_10"]) for r in csv.DictReader(fh)
                    if r.get("lane") == "l3d" and r.get("backend") == "arcadedb_dense_embedded"
                    and r.get("scale") == scale and r.get("recall_at_10")
                    and str(r.get("quantization", "fp32")).lower() in ("fp32", "none", "")]
    except OSError:
        vals = []
    if vals:
        return round(statistics.median(vals), 4), f"runs_paper.csv arcadedb_dense_embedded fp32 {scale} median of {len(vals)}"
    return FALLBACK_RECALL_TARGET, "fallback constant (no frozen row at this scale)"


def calibrate_nprobe(search_fn, queries, gt, target: float, nlists: int, k: int = 10):
    """Smallest nProbe in [1, nlists] whose recall@k on `queries` reaches
    `target`, by binary search (recall is monotone in nProbe for IVF). Returns
    (nprobe, recall at it). If even nlists misses the target, returns nlists
    and its recall, and the row shows the shortfall."""
    def recall(np_):
        hit = 0
        for q, g in zip(queries, gt):
            ids = search_fn(q, k, np_)
            hit += len(set(ids[:k]) & set(int(x) for x in g[:k]))
        return hit / (k * len(queries))
    lo, hi = 1, nlists
    best = (nlists, None)
    while lo <= hi:
        mid = (lo + hi) // 2
        r = recall(mid)
        if r >= target:
            best = (mid, r)
            hi = mid - 1
        else:
            lo = mid + 1
    if best[1] is None:
        best = (nlists, recall(nlists))
    return best


def vector_index(col, field: str, dim: int, n: int, metric: str = "l2") -> tuple[int, int]:
    """Create the IVF index after the load (it trains on what is there) and
    return (nLists, nProbe) for the row."""
    nlists, nprobe = ivf_params(n)
    col.add_index({"type": "vector", "fields": [field],
                   "params": {"metric": metric, "dimension": dim, "nLists": nlists,
                              "defaultNProbe": nprobe, "trainingIterations": TRAINING_ITERATIONS}})
    return nlists, nprobe


def close(cl):
    try:
        cl.close()
    except Exception:  # noqa: BLE001
        pass
