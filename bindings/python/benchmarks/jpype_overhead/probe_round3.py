"""Round-3 probe: batched JSON row transport vs per-row materialization.
Usage: uv run python probe_round3.py <docs_db_dir>"""

import json
import sys
import time

import arcadedb_embedded as arcadedb

with arcadedb.open_database(sys.argv[1]) as db:
    import jpype

    RowBatcher = jpype.JClass("RowBatcher")
    sql = "SELECT id, score, name, category, active, created, counts FROM Doc LIMIT 100000"

    # current path: iterate + .get per column (best current layer)
    cols = ["id", "score", "name", "category", "active", "created", "counts"]
    for rep in range(3):
        s = time.perf_counter()
        n = 0
        for row in db.query("sql", sql):
            for c in cols:
                row.get(c)
            n += 1
        cur = time.perf_counter() - s
    print(f"PROBE3,current_get_100k,{cur*1e3:.0f}ms,rows={n}", flush=True)

    # batched: one Java crossing per 10k rows + C-fast json parse
    for batch_size in (1_000, 10_000, 100_000):
        for rep in range(3):
            s = time.perf_counter()
            rs = db.query("sql", sql)
            jrs = rs._java_result_set
            rows = []
            while True:
                chunk = str(RowBatcher.nextJsonBatch(jrs, batch_size))
                parsed = json.loads(chunk)
                if not parsed:
                    break
                rows.extend(parsed)
            batched = time.perf_counter() - s
        print(
            f"PROBE3,batched_json_bs{batch_size},{batched*1e3:.0f}ms,rows={len(rows)}",
            flush=True,
        )
    # sanity: same content shape
    print(f"PROBE3,sample_row_keys,{sorted(rows[0].keys())}")
