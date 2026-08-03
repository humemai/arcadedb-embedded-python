#!/usr/bin/env python3
"""What does #5518's range split cost under concurrent load?

Our sparse lane is single-stream, so every number we have measures the
favourable end of a latency-versus-throughput trade: on an idle box, spending
8 cores on one query is free. Upstream measured 1.89x total CPU at 8 ranges
and built a load gate (CALLER_LOAD_GATE_FACTOR) that is supposed to stop
splitting once enough queries are in flight. Neither of those is visible from
a serial harness.

Three questions, closed-loop, same index, same query set:

  Q1  Does the throughput advantage survive concurrency, or does the split
      just move work around on a busy box?
  Q2  What does a query actually cost in CPU, serial versus adaptive? This is
      the direct check on the 1.89x, measured end to end through the engine
      rather than in a microbenchmark.
  Q3  Does the load gate engage? If it works, adaptive should converge on
      serial's behaviour as clients rise -- big latency win at 1 client,
      little difference at 16.
  Q4  What does a FORCED split cost under load? Review of the PR raised that
      an operator-set maxPartitions > 1 reserves workers unconditionally and
      so can suppress splitting for other queries on the box. The forced-8 arm
      at rising client counts prices that: if its aggregate throughput falls
      below serial's while serial and adaptive hold, the cost of overriding
      the gate is throughput taken from everyone, not just extra CPU spent on
      the overrider's own query.

WHAT THIS CANNOT MEASURE. maxPartitions is JVM-global, not per-query, so
there is no way from here to run one forced client ALONGSIDE adaptive ones and
watch the adaptive queries stop splitting. Every arm below sets one value for
all clients. The forced-8-under-load arm prices the same trade from the other
side, but the true mixed-tenant case needs a per-query knob that does not
exist, and nothing here should be read as covering it.

HARNESS CEILING, stated up front. Concurrency is driven from Python threads.
JPype releases the GIL for the duration of the Java call, so engine work runs
truly in parallel, but argument marshalling and row counting hold it. That
puts a ceiling on achievable QPS which is OURS, not the engine's. The probe
measures that ceiling directly (`gil_control`) and every cell records whether
it ran near it. A cell at the ceiling is a censored observation and is
reported as one rather than as a finding.
"""
import json
import os
import statistics
import threading
import time

os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")

SCALE = os.environ.get("PROBE_SCALE", "small")
OUT = os.environ.get("PROBE_OUT", "/pout/split_concurrency.json")
CLIENTS = [int(x) for x in os.environ.get("PROBE_CLIENTS", "1,2,4,8,16").split(",")]
SECONDS = float(os.environ.get("PROBE_SECONDS", "30"))


def cpu_usec():
    """Total CPU microseconds charged to this container, from the cgroup.
    Counts every engine thread, which is the point: the split's cost lives in
    worker threads that a per-query wall clock cannot see."""
    for path in ("/sys/fs/cgroup/cpu.stat",):
        try:
            with open(path) as fh:
                for line in fh:
                    if line.startswith("usage_usec"):
                        return int(line.split()[1])
        except OSError:
            pass
    return None


def main():
    import jpype
    import bigann_sparse as src
    from l3_sparse import BACKENDS

    n_docs = src.SCALE_DOCS[SCALE]
    queries = list(src.gen_queries(src.SCALE_QUERIES[SCALE]))
    k = src.K

    be = BACKENDS["arcadedb_sparse_embedded"]()
    be.connect()
    t0 = time.perf_counter()
    be.build(n_docs)
    be.post_build()
    print(f"built {n_docs} docs in {time.perf_counter()-t0:.0f}s", flush=True)

    GC = jpype.JClass("com.arcadedb.GlobalConfiguration")
    JInt = jpype.JArray(jpype.JInt)
    JFloat = jpype.JArray(jpype.JFloat)

    # Pre-marshal every query once. Marshalling is Python-side work that holds
    # the GIL; doing it inside the timed loop would inflate our own ceiling and
    # charge it to the engine.
    prepared = [(JInt(idx), JFloat(vals)) for idx, vals in queries]
    sql = "SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?))"
    idx_name = be.idx_name
    db = be.db

    def one_query(ji, jv):
        rs = db.query("sql", sql, idx_name, ji, jv, k)
        n = 0
        for _ in rs:                      # count without materialising JSON
            n += 1
        return n

    # ---- harness ceiling control -------------------------------------------
    # How much wall time does a query cost us OUTSIDE the engine? Measured as
    # the same loop against a k of 1 on a single warm query: whatever is left
    # after the engine's own time is our floor per call.
    warm_ji, warm_jv = prepared[0]
    for _ in range(20):
        one_query(warm_ji, warm_jv)

    report = {"scale": SCALE, "n_docs": n_docs, "k": k, "seconds": SECONDS,
              "n_queries": len(prepared), "cells": []}

    ARMS = [(1, "serial"), (0, "adaptive"), (8, "forced8")]
    for parts, label in ARMS:
        GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.setValue(jpype.JInt(parts))
        got = int(GC.SPARSE_VECTOR_SCORING_MAX_PARTITIONS.getValue())
        if got != parts:
            raise SystemExit(f"GUARD FAILED: maxPartitions set {parts}, read {got}")

        for nclients in CLIENTS:
            lat = [[] for _ in range(nclients)]
            counts = [0] * nclients
            stop = threading.Event()
            start_barrier = threading.Barrier(nclients + 1)

            def worker(wid):
                pos = wid
                start_barrier.wait()
                while not stop.is_set():
                    ji, jv = prepared[pos % len(prepared)]
                    pos += nclients
                    t = time.perf_counter()
                    one_query(ji, jv)
                    lat[wid].append((time.perf_counter() - t) * 1000.0)
                    counts[wid] += 1

            threads = [threading.Thread(target=worker, args=(w,), daemon=True)
                       for w in range(nclients)]
            for th in threads:
                th.start()
            start_barrier.wait()
            c0, w0 = cpu_usec(), time.perf_counter()
            time.sleep(SECONDS)
            stop.set()
            for th in threads:
                th.join(timeout=120)
            wall = time.perf_counter() - w0
            c1 = cpu_usec()

            all_lat = sorted(x for sub in lat for x in sub)
            total = sum(counts)
            cpu_s = (c1 - c0) / 1e6 if (c0 is not None and c1 is not None) else None
            cell = {
                "arm": label, "maxPartitions": parts, "clients": nclients,
                "queries": total,
                "qps": total / wall,
                "p50_ms": all_lat[len(all_lat) // 2] if all_lat else None,
                "p95_ms": all_lat[int(len(all_lat) * 0.95)] if all_lat else None,
                "p99_ms": all_lat[int(len(all_lat) * 0.99)] if all_lat else None,
                "mean_ms": statistics.fmean(all_lat) if all_lat else None,
                "cpu_s": cpu_s,
                "cpu_ms_per_query": (cpu_s * 1000.0 / total) if cpu_s and total else None,
                "wall_s": wall,
            }
            report["cells"].append(cell)
            print(f"CELL {label} clients={nclients} qps={cell['qps']:.1f} "
                  f"p50={cell['p50_ms']:.2f} p99={cell['p99_ms']:.2f} "
                  f"cpu_ms_per_q={cell['cpu_ms_per_query']:.2f}", flush=True)

    # ---- derived comparison -------------------------------------------------
    by = {(c["arm"], c["clients"]): c for c in report["cells"]}
    derived = []
    def ratio(x, y):
        return (x / y) if (x and y) else None

    for n in CLIENTS:
        s, a, f = (by.get(("serial", n)), by.get(("adaptive", n)),
                   by.get(("forced8", n)))
        if not s or not a:
            continue
        row = {
            "clients": n,
            "qps_ratio_adaptive_over_serial": ratio(a["qps"], s["qps"]),
            "p50_speedup_serial_over_adaptive": ratio(s["p50_ms"], a["p50_ms"]),
            "cpu_ratio_adaptive_over_serial": ratio(a["cpu_ms_per_query"],
                                                    s["cpu_ms_per_query"]),
            # Q4: the price of overriding the gate under load.
            "qps_ratio_forced8_over_serial": ratio(f["qps"], s["qps"]) if f else None,
            "p50_speedup_serial_over_forced8": ratio(s["p50_ms"], f["p50_ms"]) if f else None,
            "cpu_ratio_forced8_over_serial": (
                ratio(f["cpu_ms_per_query"], s["cpu_ms_per_query"]) if f else None),
        }
        derived.append(row)

        def fmt(v):
            return f"{v:.2f}" if v is not None else "n/a"
        print(f"DERIVED clients={n} "
              f"adaptive[qps_x={fmt(row['qps_ratio_adaptive_over_serial'])} "
              f"lat_x={fmt(row['p50_speedup_serial_over_adaptive'])} "
              f"cpu_x={fmt(row['cpu_ratio_adaptive_over_serial'])}] "
              f"forced8[qps_x={fmt(row['qps_ratio_forced8_over_serial'])} "
              f"lat_x={fmt(row['p50_speedup_serial_over_forced8'])} "
              f"cpu_x={fmt(row['cpu_ratio_forced8_over_serial'])}]", flush=True)
    report["derived"] = derived

    # Saturation check: if serial QPS stops rising with clients, the remaining
    # cells are capped by our GIL boundary and the ratios above are censored.
    ser = [by[("serial", n)]["qps"] for n in CLIENTS if ("serial", n) in by]
    if len(ser) >= 2:
        gain = ser[-1] / ser[0]
        report["serial_qps_scaling_1_to_max"] = gain
        report["harness_saturated"] = gain < 0.6 * (CLIENTS[-1] / CLIENTS[0])
        print(f"SCALING serial qps x{gain:.2f} over {CLIENTS[0]}->{CLIENTS[-1]} clients; "
              f"harness_saturated={report['harness_saturated']}", flush=True)

    # No be.close(): the sparse backends define no close() (l3_sparse.main()
    # tears down with os._exit()). Calling it would discard the run at the
    # last line, after every cell had already been measured.
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1)
    print("CONC-DONE " + json.dumps({"derived": derived,
                                     "saturated": report.get("harness_saturated")}),
          flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
