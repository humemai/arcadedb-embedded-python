"""#5412 verification: DEEP-10M fp32 dense on the shared warm search cache
(eec94cd16) + pooled searchers (4b62ab376). One build, 5 query passes.
Paper baseline (pre-fix): build 2796s, p50 5.5ms, p99 17.9ms, recall 0.950.
"""
import json
import os
import statistics
import time

from l3d_dense import BACKENDS, load_dataset, K
from bench_common import run_conditions

def _installed_version():
    """The wheel actually loaded, not the one this file was named after.
    See provenance_check._asserted_versions for why a hardcoded version is a
    claim rather than provenance."""
    try:
        from importlib.metadata import version
        return version("arcadedb-embedded")
    except Exception as e:
        return "unknown (%s)" % e.__class__.__name__



train, test, gt = load_dataset("deep10m")
b = BACKENDS["arcadedb_dense_embedded"]()
b.connect()
t0 = time.perf_counter()
b.build(train)
b.post_build()
build_s = round(time.perf_counter() - t0, 2)
print(f"BUILD-DONE {build_s}s", flush=True)

for rep in range(1, 6):
    for q in test[:20]:
        b.search(q, K)
    lats, recalls = [], []
    for qi in range(len(test)):
        t1 = time.perf_counter()
        ids = b.search(test[qi], K)
        lats.append((time.perf_counter() - t1) * 1e3)
        recalls.append(len(set(ids[:K]) & set(gt[qi].tolist())) / K)
    lats.sort()
    out = {"rep": rep, "build_s": build_s, "quantization": "INT8",
           "engine": _installed_version(),  # was hardcoded "26.8.1.dev16-line (c885235c7)", "n_queries": len(test),
           "p50": round(lats[len(lats) // 2], 3),
           "p95": round(lats[int(0.95 * len(lats))], 3),
           "p99": round(lats[int(0.99 * len(lats))], 3),
           "recall_at_10": round(statistics.mean(recalls), 4)}
    out.update(run_conditions())
    with open(f"/pout/int8_dev16_rep{rep}.json", "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)

try:
    idx = b.db._java_db.getSchema().getIndexByName("Article[embedding]")
    stats = idx.getStats()
    keep = {}
    for k in ("searchVectorCacheCapacity", "vectorCacheHits",
              "vectorCacheMisses"):
        try:
            keep[k] = int(stats.get(k))
        except Exception:
            pass
    print("STATS " + json.dumps(keep), flush=True)
    with open("/pout/int8_dev16_stats.json", "w") as f:
        json.dump(keep, f)
except Exception as e:
    print(f"STATS unavailable: {e}", flush=True)
os._exit(0)
