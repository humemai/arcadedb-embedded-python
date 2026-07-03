"""Empirical validation of the report's two key claims (measure-only, no src changes).

1. Decompose P-SQL: time db.query(...).first() alone vs + row.get("res") conversion.
2. Fix-1 feasibility: bulk-convert a Java float[] via numpy vs convert_java_to_python.

Usage: uv run python validate_attribution.py <dataDir> <dbDir>
"""

import json
import statistics
import sys
import time
import timeit
from pathlib import Path

import numpy as np

import arcadedb_embedded as arcadedb
from arcadedb_embedded.type_conversion import convert_java_to_python

data_dir, db_dir = Path(sys.argv[1]), sys.argv[2]
meta = json.loads((data_dir / "meta.json").read_text())
warm, measured = meta["num_queries_warmup"], meta["num_queries_measured"]
k, ef, dims = meta["k"], meta["ef_search"], meta["dimensions"]
queries = np.fromfile(data_dir / "queries.bin", dtype="<f4").reshape(
    warm + measured, dims
)


def stats_ms(lat_ns):
    s = sorted(lat_ns)
    return (
        statistics.fmean(s) / 1e6,
        s[len(s) // 2] / 1e6,
        s[int(len(s) * 0.95)] / 1e6,
    )


with arcadedb.open_database(db_dir) as db:
    index_name = "VectorData[vector]"

    def query_only(vec):
        return db.query(
            "sql",
            "SELECT vectorNeighbors(?, ?, ?, ?) as res",
            index_name,
            vec,
            int(k),
            int(ef),
        ).first()

    # trigger graph load
    query_only(queries[0])

    # Layer 1: query + first() only — engine work + one row crossing, NO conversion
    for i in range(warm):
        query_only(queries[i])
    lat_q = []
    rows = []
    for q in range(measured):
        s = time.perf_counter_ns()
        row = query_only(queries[warm + q])
        lat_q.append(time.perf_counter_ns() - s)
        rows.append(row)

    # Layer 2: the conversion alone — row.get("res") on the already-fetched rows
    lat_c = []
    for row in rows:
        s = time.perf_counter_ns()
        res = row.get("res")
        lat_c.append(time.perf_counter_ns() - s)

    mq, mq50, mq95 = stats_ms(lat_q)
    mc, mc50, mc95 = stats_ms(lat_c)
    print(f"VALIDATE,sql_query_first_only_ms,mean={mq:.2f},p50={mq50:.2f},p95={mq95:.2f}")
    print(f"VALIDATE,get_res_conversion_ms,mean={mc:.2f},p50={mc50:.2f},p95={mc95:.2f}")

    # ---- Fix-1 feasibility: bulk float[] conversion ----
    import jpype

    jarr = jpype.JArray(jpype.JFloat)([float(i) / dims for i in range(dims)])

    def t(name, fn, number=2000):
        per = timeit.timeit(fn, number=number) / number * 1e6
        print(f"VALIDATE,{name},{per:.2f}us")

    t("convert_java_to_python_float384", lambda: convert_java_to_python(jarr), 500)
    t("np_frombuffer_float384", lambda: np.frombuffer(memoryview(jarr), dtype=np.float32))
    t("jarray_to_list_float384", lambda: list(jarr))
    t(
        "np_asarray_float384",
        lambda: np.asarray(jarr, dtype=np.float32),
    )
