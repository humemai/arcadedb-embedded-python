"""#5412 close-out: DEEP-10M fp32 on the auto-sized build cache (dev20).
Baselines: pre-#3144-cap INT8 capped-line build was 5,840s; warm query
p50 0.81ms / p99 1.22ms at 0.950 recall (must not regress).
Reports vectorFetchFromDocuments after the build (expected 0).
"""
import json
import os
import statistics
import time

from l3d_dense import BACKENDS, load_dataset, K

def _installed_version():
    """The wheel actually loaded, not the one this file was named after.

    These drivers hardcoded their version string, so the JSON they produced
    asserted a version rather than observing one: queue41 ran the dev20 image
    and the dev23 image and both results claimed "26.8.1.dev22". The published
    verify5412b overlay carries the same kind of self-assertion, which means
    provenance_check.py was validating a claim the producer made about itself.
    """
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

stats = {}
try:  # public API since 26.8.1.dev20
    idx = b.db.schema.get_vector_index("Article", "embedding")
    stats = idx.get_stats()
except Exception as e:
    try:
        raw = b.db._java_db.getSchema().getIndexByName("Article[embedding]").getStats()
        stats = {str(k): int(raw.get(k)) for k in raw.keySet()
                 if str(raw.get(k)).lstrip("-").isdigit()}
    except Exception as e2:
        stats = {"error": f"{e} / {e2}"}
keep = {k: stats.get(k) for k in (
    "vectorFetchFromDocuments", "vectorFetchFromGraph",
    "vectorFetchFromQuantized", "searchVectorCacheCapacity",
    "vectorCacheHits", "vectorCacheMisses", "totalVectors") if k in stats}
print("BUILD-STATS " + json.dumps(keep), flush=True)
with open("/pout/int8_dev20h24_buildstats.json", "w") as f:
    json.dump({"build_s": build_s, "stats": stats}, f, indent=1, default=str)

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
           "engine": _installed_version(),  # was hardcoded "26.8.1.dev20", "n_queries": len(test),
           "p50": round(lats[len(lats) // 2], 3),
           "p95": round(lats[int(0.95 * len(lats))], 3),
           "p99": round(lats[int(0.99 * len(lats))], 3),
           "recall_at_10": round(statistics.mean(recalls), 4)}
    with open(f"/pout/int8_dev20h24_rep{rep}.json", "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
os._exit(0)
