import os, time, statistics
os.environ.setdefault("TSBS_LP", "/data/tsbs/cpu_influx.lp")
from l4_tsbs import parse_lp, HOST
from l4_native_probe import ArcadeTSNative
b = ArcadeTSNative(); b.connect()
pts = parse_lp(); b.ingest(pts)
tmax = max(p[1] for p in pts) * 1000
variants = {
  "unbounded_ts_last": f"SELECT ts.last(uu, ts) AS v FROM Point WHERE host='{HOST}'",
  "bounded_1h_ts_last": f"SELECT ts.last(uu, ts) AS v FROM Point WHERE host='{HOST}' AND ts BETWEEN {tmax-3600_000} AND {tmax}",
  "order_desc_limit1": f"SELECT ts, uu FROM Point WHERE host='{HOST}' ORDER BY ts DESC LIMIT 1",
  "bounded_order_desc": f"SELECT ts, uu FROM Point WHERE host='{HOST}' AND ts BETWEEN {tmax-3600_000} AND {tmax} ORDER BY ts DESC LIMIT 1",
}
for name, q in variants.items():
    ts=[]
    for _ in range(10):
        t=time.perf_counter(); r=b.db.query("sql", q).to_list(); ts.append((time.perf_counter()-t)*1e3)
    print(f"{name}: p50={statistics.median(ts):.2f}ms rows={len(r)}")
os._exit(0)
