"""Columnar-lite probe: binary column transport vs to_json_list vs to_list.
Usage: uv run python probe_columnar.py <docs_db_dir>"""

import json
import sys
import time

import numpy as np

import arcadedb_embedded as arcadedb

COLS = ["id", "score", "name", "category", "active", "created"]
SQL = "SELECT id, score, name, category, active, created FROM Doc LIMIT 100000"


def decode(buf: memoryview):
    hlen = int.from_bytes(buf[:4], "little")
    header = json.loads(bytes(buf[4 : 4 + hlen]))
    out = {}
    pos = 4 + hlen
    count = header["count"]
    for col in header["cols"]:
        pos += col["nulls"]  # skip null bitmap in the probe timing (kept in format)
        data = buf[pos : pos + col["bytes"]]
        t = col["type"]
        if t in ("i8", "dt"):
            out[col["name"]] = np.frombuffer(data, dtype="<i8")
        elif t == "f8":
            out[col["name"]] = np.frombuffer(data, dtype="<f8")
        elif t == "b1":
            out[col["name"]] = np.frombuffer(data, dtype=np.uint8).astype(bool)
        else:  # strings
            offs = np.frombuffer(data[: (count + 1) * 4], dtype="<i4")
            chars = bytes(data[(count + 1) * 4 :])
            out[col["name"]] = (offs, chars)  # decoded lazily in real impl
        pos += col["bytes"]
    return count, out


with arcadedb.open_database(sys.argv[1]) as db:
    import jpype

    ColumnProbe = jpype.JClass("ColumnProbe")
    jcols = jpype.JArray(jpype.JString)(COLS)

    for rep in range(3):
        s = time.perf_counter()
        rs = db.query("sql", SQL)
        total = 0
        while True:
            buf = memoryview(ColumnProbe.nextColumnBatch(rs._java_result_set, 25_000, jcols))
            count, cols = decode(buf)
            if count == 0:
                break
            total += count
        t_col = time.perf_counter() - s
    print(f"PROBE,columnar_100k_ms,{t_col*1e3:.0f},rows={total}")

    for rep in range(3):
        s = time.perf_counter()
        rows = db.query("sql", SQL).to_json_list()
        t_json = time.perf_counter() - s
    print(f"PROBE,to_json_list_100k_ms,{t_json*1e3:.0f},rows={len(rows)}")

    # full string materialization variant for fairness (columnar strings -> list[str])
    s = time.perf_counter()
    rs = db.query("sql", SQL)
    total = 0
    while True:
        buf = memoryview(ColumnProbe.nextColumnBatch(rs._java_result_set, 25_000, jcols))
        count, cols = decode(buf)
        if count == 0:
            break
        for name in ("name", "category"):
            offs, chars = cols[name]
            cols[name] = [
                chars[offs[i] : offs[i + 1]].decode() for i in range(count)
            ]
        total += count
    t_col_str = time.perf_counter() - s
    print(f"PROBE,columnar_strings_decoded_100k_ms,{t_col_str*1e3:.0f},rows={total}")
