"""#5414 verification on mini: full 2.59M native-TS ingest, A/B last-point
queries on FRESH (unsealed) data, then close+reopen (seals/flushes the
in-memory series tail) and A/B again, with EXPLAIN capture for both
unbounded forms. Engine: 26.8.1.dev14 (contains 0477ee53a descending scan).
"""
import json
import os
import statistics
import time

os.environ.setdefault("TSBS_LP", "/data/tsbs/cpu_influx.lp")
from l4_tsbs import parse_lp, HOST
from l4_native_probe import ArcadeTSNative, SHARDS


def bench(db, queries, n=15):
    res = {}
    for name, q in queries.items():
        ts, rows = [], 0
        for _ in range(n):
            t = time.perf_counter()
            r = db.query("sql", q).to_list()
            ts.append((time.perf_counter() - t) * 1e3)
            rows = len(r)
        ts.sort()
        res[name] = {"p50_ms": round(statistics.median(ts), 2),
                     "min_ms": round(ts[0], 2), "max_ms": round(ts[-1], 2),
                     "rows": rows}
        print(f"  {name}: p50={res[name]['p50_ms']}ms "
              f"[{res[name]['min_ms']}-{res[name]['max_ms']}] rows={rows}",
              flush=True)
    return res


def main():
    import arcadedb_embedded as arcadedb
    pts = parse_lp()
    tmax = max(p[1] for p in pts) * 1000
    Q = {
        "unbounded_ts_last":
            f"SELECT ts.last(uu, ts) AS v FROM Point WHERE host='{HOST}'",
        "bounded_1h_ts_last":
            f"SELECT ts.last(uu, ts) AS v FROM Point WHERE host='{HOST}' "
            f"AND ts BETWEEN {tmax-3600_000} AND {tmax}",
        "order_desc_limit1":
            f"SELECT ts, uu FROM Point WHERE host='{HOST}' "
            f"ORDER BY ts DESC LIMIT 1",
        "bounded_order_desc":
            f"SELECT ts, uu FROM Point WHERE host='{HOST}' "
            f"AND ts BETWEEN {tmax-3600_000} AND {tmax} "
            f"ORDER BY ts DESC LIMIT 1",
    }
    out = {"n_points": len(pts), "shards": SHARDS,
           "engine": "26.8.1.dev14", "host_tag": HOST}
    b = ArcadeTSNative()
    b.connect()
    t0 = time.perf_counter()
    b.ingest(pts)
    out["ingest_s"] = round(time.perf_counter() - t0, 2)
    print(f"ingested {len(pts)} pts in {out['ingest_s']}s", flush=True)
    print("PHASE fresh_unsealed", flush=True)
    out["fresh_unsealed"] = bench(b.db, Q)
    b.close()

    db2 = arcadedb.open_database(os.environ.get("TS_DB_PATH",
                                                "/tmp/l4n_arcade"))
    for key, qn in (("explain_unbounded_ts_last", "unbounded_ts_last"),
                    ("explain_order_desc", "order_desc_limit1")):
        try:
            plan = db2.query("sql", "EXPLAIN " + Q[qn]).to_list()
            out[key] = str(plan)[:2000]
        except Exception as e:  # EXPLAIN support may vary; not fatal
            out[key] = f"EXPLAIN failed: {e}"
    print("PHASE after_reopen", flush=True)
    out["after_reopen"] = bench(db2, Q)
    db2.close()

    with open("/pout/ts5414_verify.json", "w") as f:
        json.dump(out, f, indent=1)
    print("RESULT " + json.dumps(out), flush=True)
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
