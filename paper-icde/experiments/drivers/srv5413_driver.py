"""#5413 matched-configuration server cell: DEEP-10M fp32 over HTTP against
a server on the same engine line, same 24g heap, gc logging on the server.
One build + 5 single-stream query passes (mirrors the embedded driver)."""
import json
import os
import statistics
import time

from l3d_dense import BACKENDS, load_dataset, K
from bench_common import run_conditions

train, test, gt = load_dataset("deep10m")
b = BACKENDS["arcadedb_dense_server"]()
b.connect()
t0 = time.perf_counter()
b.build(train)
if hasattr(b, "post_build"):
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
    out = {"rep": rep, "build_s": build_s, "deployment": "server_http",
           "server_version": getattr(b, "version", "?"),
           "n_queries": len(test),
           "p50": round(lats[len(lats) // 2], 3),
           "p95": round(lats[int(0.95 * len(lats))], 3),
           "p99": round(lats[int(0.99 * len(lats))], 3),
           "recall_at_10": round(statistics.mean(recalls), 4)}
    out.update(run_conditions())
    with open(f"/pout/srv5413_rep{rep}.json", "w") as f:
        json.dump(out, f)
    print("RESULT " + json.dumps(out), flush=True)
os._exit(0)
