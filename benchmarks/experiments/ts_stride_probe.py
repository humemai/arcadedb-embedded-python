#!/usr/bin/env python3
"""Size ArcadeDB #5519 (TIMESERIES row-stride padding) on real TSBS data.

Luca measured that TimeSeriesBucket.calculateRowSize() reserves 2 + MAX_STRING_BYTES
(258 B) per STRING column, so a 10-tag schema strides 2612 B to carry ~110 B of data,
and asked us to re-run our ingest arm with the tags collapsed into one column.

Our campaign harness already uses ONE tag (hostname) and three fields, so it is
already the collapsed case and there is nothing to collapse. The informative
experiment is the inverse: expand to the schema real TSBS actually ships (10 tags,
10 fields) and measure the penalty on our host. That also tells us how much our
own reduced schema has been flattering the lane.

Arms (same data, same host, alternating):
  tags1   1 STRING tag  + 3 DOUBLE fields   <- what the paper currently reports
  tags10  10 STRING tags + 3 DOUBLE fields  <- real TSBS tag cardinality
  tags10f10  10 STRING tags + 10 DOUBLE fields <- full TSBS row
"""
import json
import os
import statistics
import time

LP = os.environ.get("TSBS_LP", "/data/tsbs/cpu_influx.lp")
LIMIT = int(os.environ.get("TSBS_LIMIT", "0"))
CHUNK = 50_000
SHARDS = int(os.environ.get("TS_SHARDS", "4"))
REPS = int(os.environ.get("TS_REPS", "3"))

TAGS = ["hostname", "region", "datacenter", "rack", "os", "arch", "team",
        "service", "service_version", "service_environment"]
FIELDS = ["usage_user", "usage_system", "usage_idle", "usage_nice",
          "usage_iowait", "usage_irq", "usage_softirq", "usage_steal",
          "usage_guest", "usage_guest_nice"]


def parse_full():
    """Every tag and field, so each arm can take the slice it needs."""
    rows = []
    with open(LP) as f:
        for i, line in enumerate(f):
            if LIMIT and i >= LIMIT:
                break
            try:
                head, fields, ts = line.rsplit(" ", 2)
                tagpart = head.split(",", 1)[1]
                tv = dict(kv.split("=", 1) for kv in tagpart.split(","))
                fv = dict(kv.split("=", 1) for kv in fields.split(","))
                rows.append((
                    [tv[t] for t in TAGS],
                    int(ts) // 1_000_000_000,
                    [float(fv[c].rstrip("i")) for c in FIELDS],
                ))
            except Exception:
                continue
    return rows


def run_arm(rows, n_tags, n_fields, label):
    import shutil
    import numpy as np
    import arcadedb_embedded as arcadedb

    path = f"/tmp/ts_stride_{label}"
    shutil.rmtree(path, ignore_errors=True)
    heap = os.environ.get("ARCADEDB_HEAP", "8g")
    db = arcadedb.create_database(
        path, jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})

    tagcols = ", ".join(f"{TAGS[i]} STRING" for i in range(n_tags))
    fieldcols = ", ".join(f"f{i} DOUBLE" for i in range(n_fields))
    db.command("sql",
               f"CREATE TIMESERIES TYPE P TIMESTAMP ts "
               f"TAGS ({tagcols}) FIELDS ({fieldcols}) SHARDS {SHARDS}")

    ex = db.async_executor()
    t0 = time.perf_counter()
    for lo in range(0, len(rows), CHUNK):
        chunk = rows[lo:lo + CHUNK]
        ts = np.asarray([r[1] * 1000 for r in chunk], dtype=np.int64)
        cols = [[r[0][i] for r in chunk] for i in range(n_tags)]
        cols += [np.asarray([r[2][i] for r in chunk], dtype=np.float64)
                 for i in range(n_fields)]
        ex.append_samples("P", ts, *cols, primitive=True)
    ex.wait_completion()
    elapsed = time.perf_counter() - t0

    n = int(db.query("sql", "SELECT count(*) AS n FROM P").to_list()[0]["n"])
    # Row stride, 8 bytes for the timestamp plus each column's slot.
    #
    # There are now TWO layouts and the probe must not assume one. Before
    # #5574 a STRING TAG reserved 2 + MAX_STRING_BYTES = 258 bytes inline;
    # after it, a TAG holds a 4-byte dictionary id. Reporting only the v0
    # formula against a v1 engine would print a stride the engine does not
    # use and make a real improvement look like a measurement error.
    #
    # Which layout is live is a property of the TYPE, not the build: #5574
    # versions the row format per type and does not migrate in place, so a
    # type created by an older build keeps the inline layout even on a new
    # engine. This probe issues CREATE TIMESERIES TYPE into a fresh database
    # every arm, so it always exercises whatever the running build creates.
    stride_v0 = 8 + 258 * n_tags + 8 * n_fields
    stride_v1 = 8 + 4 * n_tags + 8 * n_fields
    db.close()
    return {"label": label, "n_tags": n_tags, "n_fields": n_fields,
            "rows": n, "ingest_s": round(elapsed, 3),
            "pts_per_s": round(len(rows) / elapsed, 1),
            "predicted_stride_bytes_inline_v0": stride_v0,
            "predicted_rows_per_64k_page_v0": 65536 // stride_v0,
            "predicted_stride_bytes_tagdict_v1": stride_v1,
            "predicted_rows_per_64k_page_v1": 65536 // stride_v1}


def main():
    rows = parse_full()
    print(f"parsed {len(rows):,} samples, {len(TAGS)} tags, {len(FIELDS)} fields",
          flush=True)
    arms = [(1, 3, "tags1"), (10, 3, "tags10"), (10, 10, "tags10f10")]
    out = []
    for rep in range(1, REPS + 1):
        for n_tags, n_fields, label in arms:
            r = run_arm(rows, n_tags, n_fields, f"{label}_r{rep}")
            r["rep"] = rep
            r["label"] = label
            out.append(r)
            print("ARM " + json.dumps(r), flush=True)

    # WRITE THE ARTIFACT FIRST. Every arm has already run by this point: the
    # summary below is formatting, and a KeyError in a format string used to
    # destroy a completed set of runs (default 9 arms of full TSBS ingest,
    # 2.59M points each) because json.dump came after it. Formatting must never
    # be able to lose measurement.
    outp_early = os.environ.get("PROBE_OUT", "")
    if outp_early:
        os.makedirs(os.path.dirname(outp_early) or ".", exist_ok=True)
        with open(outp_early, "w") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {len(out)} rows -> {outp_early}", flush=True)

    print()
    base = None
    for _, _, label in arms:
        v = [r["pts_per_s"] for r in out if r["label"] == label]
        s = [r for r in out if r["label"] == label][0]
        m = statistics.median(v)
        if base is None:
            base = m
        print(f"  {label:<10} {s['n_tags']:>2} tags {s['n_fields']:>2} fields  "
              f"stride {s.get('predicted_stride_bytes', s.get('predicted_stride_bytes_inline_v0', '?')):>5} B  "
              f"{s.get('predicted_rows_per_64k_page', '?'):>4} rows/page  "
              f"{m:>10,.0f} pts/s  {m/base:.2f}x")

    outp = os.environ.get("PROBE_OUT", "")
    if outp:
        json.dump(out, open(outp, "w"))
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        os._exit(1)
