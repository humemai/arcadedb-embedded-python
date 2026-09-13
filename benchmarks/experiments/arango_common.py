"""ArangoDB 3.12 through python-arango, served only.

python-arango is an HTTP client; the engine has no in-process mode, so
ArangoDB gets one row per table, like MongoDB (2026-09-13, DECISIONS #78).
Every lane connects through here so the database is fresh, the version is
the server's own, and the vector index gets the same operating point.

The vector index is FAISS IVF (inverted lists over trained centroids), not
HNSW: it has no graph degree to match, so l3d_dense.degree_stamp names it
ivf_flat_no_degree and the row records nLists and nProbe instead. The
choice follows the FAISS guideline: about sqrt(n) lists, and a probe count
that is a fixed fraction of them, so the point moves with the corpus the
same way for every scale. The fraction is one knob, read once, recorded on
the row.
"""
from __future__ import annotations

import math
import os
import time

PASSWORD = "dbbenchpass"
DB = "bench"
NPROBE_FRAC = float(os.environ.get("BENCH_ARANGO_NPROBE_FRAC", "0.125"))
TRAINING_ITERATIONS = 25


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
    nlists = max(4, int(round(math.sqrt(n))))
    nprobe = max(1, int(math.ceil(nlists * NPROBE_FRAC)))
    return nlists, nprobe


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
