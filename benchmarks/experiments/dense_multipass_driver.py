#!/usr/bin/env python3
"""Give a dense comparator the SAME protocol the ArcadeDB rows get.

T5's ArcadeDB dense rows come from an overlay that builds once and then runs
five timed passes over that index, of which the table medians passes 2-5.
Every comparator, meanwhile, was measured by l3d_dense.py's campaign path:
five independent builds, each followed by 20 untimed warmups and exactly ONE
timed pass. So the overlay's first pass is the comparator protocol, and the
table puts our later passes beside their first one.

The gap is not small. ArcadeDB fp32 is 4.424 ms on its first pass and 0.723
on its later ones, and the table prints 0.723 next to Qdrant's 1.295.

What nobody has measured is what a second pass buys a comparator. If Qdrant
gains 4-6x too, the warm-versus-warm ranking may look like today's table; if
it gains nothing, today's table is wrong. This driver produces the missing
half: one build, then five passes of (20 untimed warmups + one timed pass),
per backend, so cold and warm exist for every engine on the same protocol.

    BENCH_MP_BACKEND=qdrant_dense PROBE_OUT=/pout/mp_qdrant.json \
        python -u dense_multipass_driver.py

Deliberately mirrors drivers/int8_dev20_driver.py's loop rather than
paraphrasing it, so the two sides differ in the engine and nothing else.
"""
import json
import os
import statistics
import time

from l3d_dense import (BACKENDS, load_dataset, K, canonical_quant_label,
                        degree_stamp)
from bench_common import run_conditions, SelfMemorySampler

# Read with .get, not [], so the module can be IMPORTED without the run
# environment. queue61's contract check does `import dense_multipass_driver`
# to prove the image can load it, and a module-level os.environ[...] turned
# that check into a KeyError that aborted the whole run. A contract check must
# be able to import the thing it is checking.
BACKEND = os.environ.get("BENCH_MP_BACKEND")
SCALE = os.environ.get("BENCH_MP_SCALE", "deep10m")
PASSES = int(os.environ.get("BENCH_MP_PASSES", "5"))
# Some engines are far enough off the pace that five passes of 1000 queries
# costs more than the answer is worth (sqlite-vec at 882 ms/query is 73
# minutes of pure query time). Capping is allowed; hiding the cap is not, so
# the count lands in the output and the runner logs it.
NQ = int(os.environ.get("BENCH_MP_NQUERIES", "0"))  # 0 = all


def main():
    if not BACKEND:
        raise SystemExit("BENCH_MP_BACKEND is required (e.g. qdrant_dense)")
    train, test, gt = load_dataset(SCALE)
    if NQ:
        test, gt = test[:NQ], gt[:NQ]
    b = BACKENDS[BACKEND]()
    b.connect()

    # Peak memory for the WHOLE cell, build included, matching what the
    # lane rows mean by peak_anon_mib_sum. Started here rather than
    # around the query passes because an index build is where a vector
    # engine's memory actually peaks, and T5's memory column would
    # otherwise report a steady state the lane column does not.
    mem = SelfMemorySampler().start()

    t0 = time.perf_counter()
    b.build(train)
    b.post_build()          # the vendor settle step, same as the campaign
    build_s = round(time.perf_counter() - t0, 2)
    print(f"BUILD-DONE {build_s}s", flush=True)

    out_reps = []
    WARM = 20
    timed_n = len(test) - WARM
    for rep in range(1, PASSES + 1):
        # HELD OUT, not the head of the timed set. This warmed on test[:20] and
        # then timed range(len(test)), so the first 20 queries of every pass -
        # including pass 0, the one published as COLD - had already been asked
        # and answered. A cold pass must answer only questions the engine has
        # never seen. sparse_multipass_driver.py already draws from a held-out
        # slice; this is the same fix.
        for q in test[timed_n:]:     # untimed warmup, held out of the timed set
            b.search(q, K)
        lats, recalls = [], []
        for qi in range(timed_n):
            t1 = time.perf_counter()
            ids = b.search(test[qi], K)
            lats.append((time.perf_counter() - t1) * 1e3)
            recalls.append(len(set(ids[:K]) & set(gt[qi].tolist())) / K)
        lats.sort()
        rec = {"rep": rep, "backend": BACKEND, "scale": SCALE,
               "build_s": build_s, "n_queries": timed_n,
               "warmup_held_out": WARM,
               # Read, not asserted. The dev20 drivers wrote "INT8"/"fp32" as
               # string literals regardless of what BENCH_DENSE_QUANT actually
               # said, which is the same self-assertion that let one of them
               # stamp a version it was not running.
               #
               # Through the lane's own normaliser, so this label and the DDL
               # the lane builds cannot disagree. It reported "fp32" for the
               # unset case while l3d_dense reported "none", and that split is
               # what made BENCH_DENSE_QUANT=fp32 look like a legal input.
               # From the ADAPTER, not the environment: the int8 arms declare
               # `quantization = "INT8"` on the class and set BENCH_DENSE_QUANT
               # only inside build(), so reading the env here stamped every
               # int8 multipass file as fp32 (the same defect l3d_dense.py
               # documents at its own stamping site).
               "quantization": (_q if isinstance((_q := getattr(b, "quantization", None)), str) and _q
                                else canonical_quant_label(os.environ.get("BENCH_DENSE_QUANT"))),
               "heap_asked": os.environ.get("ARCADEDB_HEAP"),
               # THE DEGREE, in this backend's own unit. Its absence is why F7
               # could not verify the published DEEP-10M cells and fell back to
               # passing on superseded rows: the lane stamps this and the
               # driver never did. Same function as the lane, so the two cannot
               # drift apart again.
               "degree_param": degree_stamp(BACKEND)[0],
               "degree_family": degree_stamp(BACKEND)[1],
               # The BACKEND's own version. run_conditions() reports the
               # arcadedb wheel, which is absent from dbbench:dense, so a
               # comparator row otherwise records "unknown" and nothing at all
               # about the engine it actually measured. l3d_dense sets
               # self.version in connect() for every backend.
               "lib_version": getattr(b, "version", None),
               "p50": round(lats[len(lats) // 2], 3),
               "p95": round(lats[int(0.95 * len(lats))], 3),
               "p99": round(lats[int(0.99 * len(lats))], 3),
               "recall_at_10": round(statistics.mean(recalls), 4)}
        rec.update(run_conditions(lane="l3d_mp"))
        out_reps.append(rec)
        print("RESULT " + json.dumps(rec), flush=True)

    # One peak for the cell, stamped onto every pass of it. finish()
    # is called ONCE: calling it inside the loop would stop the
    # sampler on pass 0 and freeze every later row at whatever the
    # peak happened to be before the warm passes ran.
    cell_mem = mem.finish()
    for _r in out_reps:
        _r.update(cell_mem)

    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        with open(outp, "w") as f:
            json.dump(out_reps, f, indent=1)
    # A dense backend can leave a JVM or a client thread alive; the campaign
    # has lost whole cells to a driver that finished and never exited.
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        os._exit(1)
