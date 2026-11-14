#!/usr/bin/env python3
"""Smoke check of the `engine_backend` stamp and of the two lanes that run on the native build (l3 sparse, l5 lifecycle).

Run it with the SAME wheel that produced the row (`uv run --no-project --python 3.12 --with <wheel> --with numpy python
smoke_backend_rows.py l3|l5 ROW.json native|jvm`): it asserts the row, and for l3 it reopens the lane's database and checks what
the Python-API ingest stored. Exits nonzero on any failed assertion, so a queue line chained with `&&` fails loudly.

  l3  the row says engine_backend, every document was ingested (n_docs_ingested == n_docs), the stored property types are
      ARRAY_OF_INTEGERS / ARRAY_OF_FLOATS (read back through SQL), the stored arrays equal the generator's (tokens exactly, weights
      to float32), and a top-10 sparse search with plain Python lists as parameters reaches recall >= 0.9 against a brute-force dot
      product over the generator's own corpus (the default INT8 posting quantization keeps it below 1). The lane's database
      (/tmp/l3_arcade) is removed at the end, so the queue line must start with `test ! -e /tmp/l3_arcade`.
  l5  the row says engine_backend and carries the cold row: import_ms, engine_load_ms, first_open_ms, cold_process_ms,
      cold_first_query_ms, cold_query_process_ms all positive; jvm_start_ms is null on native and equals engine_load_ms on the JVM.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

L3_DB = "/tmp/l3_arcade"  # nosec B108 - the lane's own fixed scratch path (l3_sparse.ArcadeEmbedded.connect)


def fail(msg):
    print("SMOKE FAIL: " + msg, flush=True)
    sys.exit(1)


def ok(msg):
    print("ok  " + msg, flush=True)


def check_l3(row, expected):
    if row.get("engine_backend") != expected:
        fail(f"engine_backend {row.get('engine_backend')!r}, expected {expected!r}")
    ok(f"engine_backend = {expected}")
    if row.get("n_docs_ingested") != row.get("n_docs"):
        fail(f"n_docs_ingested {row.get('n_docs_ingested')} != n_docs {row.get('n_docs')}")
    ok(f"ingested {row['n_docs_ingested']} documents")
    import sparse_common as sc
    import _arcadedb_import
    if _arcadedb_import.backend() != expected:
        fail(f"this process runs the {_arcadedb_import.backend()} build, the row says {expected}")
    arcadedb = _arcadedb_import.load()
    n = row["n_docs"]
    docs = list(sc.gen_docs(n))
    db = arcadedb.open_database(L3_DB)
    try:
        for prop, want in (("tokens", "ARRAY_OF_INTEGERS"), ("weights", "ARRAY_OF_FLOATS")):
            got = db.query("sql", f"SELECT {prop}.type() AS t FROM Doc WHERE id = 7").to_json_list()[0]["t"]
            if got != want:
                fail(f"stored type of Doc.{prop} is {got}, expected {want}")
            ok(f"Doc.{prop} stored as {got}")
        cnt = db.query("sql", "SELECT count(*) AS c FROM Doc").to_json_list()[0]["c"]
        if int(cnt) != n:
            fail(f"count(*) = {cnt}, expected {n}")
        import numpy as np
        for i in (0, 7, n // 2, n - 1):
            r = db.query("sql", "SELECT tokens, weights FROM Doc WHERE id = ?", i).to_json_list()[0]
            _, idx, vals = docs[i]
            if list(r["tokens"]) != list(idx):
                fail(f"tokens of doc {i} differ from the generator's")
            if not np.array_equal(np.asarray(r["weights"], np.float32), np.asarray(vals, np.float32)):
                fail(f"weights of doc {i} differ from the generator's beyond float32 rounding")
        ok("stored tokens equal the generator's, weights equal at float32")
        queries = sc.gen_queries(50)
        sql = "SELECT id, score FROM (SELECT expand(`vector.sparseNeighbors`(?, ?, ?, ?)))"
        hits = total = 0
        for qi, qv in queries:
            q = dict(zip(qi, qv))
            scores = [(sum(q.get(t, 0.0) * w for t, w in zip(idx, vals)), i) for i, idx, vals in docs]
            truth = {i for s, i in sorted(scores, key=lambda x: (-x[0], x[1]))[:10] if s > 0}
            rows = db.query("sql", sql, "Doc[tokens,weights]", qi, qv, 10).to_json_list()
            got = {int(r["id"]) for r in rows}
            hits += len(got & truth)
            total += len(truth)
        recall = hits / total
        if recall < 0.9:
            fail(f"recall@10 against brute force is {recall:.3f} (lists as parameters), expected >= 0.9")
        ok(f"recall@10 vs brute force {recall:.3f} over {len(queries)} queries (list parameters)")
        if "build_s" in row:
            ok(f"row build_s {row['build_s']}")
    finally:
        db.close()
        shutil.rmtree(L3_DB, ignore_errors=True)


def check_l5(row, expected):
    if row.get("engine_backend") != expected:
        fail(f"engine_backend {row.get('engine_backend')!r}, expected {expected!r}")
    ok(f"engine_backend = {expected}")
    for k in ("import_ms", "engine_load_ms", "first_open_ms", "cold_process_ms", "cold_query_process_ms"):
        if not isinstance(row.get(k), (int, float)) or row[k] <= 0:
            fail(f"{k} = {row.get(k)!r}, expected a positive number")
    if row.get("workload") != "empty" and not (isinstance(row.get("cold_first_query_ms"), (int, float)) and row["cold_first_query_ms"] > 0):
        fail(f"cold_first_query_ms = {row.get('cold_first_query_ms')!r}, expected a positive number")
    if expected == "native":
        if row.get("jvm_start_ms") is not None:
            fail(f"jvm_start_ms = {row['jvm_start_ms']!r} on native, expected null")
    elif row.get("jvm_start_ms") != row.get("engine_load_ms"):
        fail(f"jvm_start_ms {row.get('jvm_start_ms')!r} != engine_load_ms {row.get('engine_load_ms')!r} on the JVM build")
    ok("cold row: " + ", ".join(f"{k}={row.get(k)}" for k in ("import_ms", "jvm_start_ms", "engine_load_ms", "first_open_ms",
                                                              "cold_process_ms", "cold_first_query_ms", "cold_query_process_ms")))
    for k in ("cold_open_ms", "cold_close_ms", "clean_open_ms", "read_session_ms"):
        if not isinstance(row.get(k), (int, float)):
            fail(f"{k} missing from the row")
    ok("warm and evicted-cache columns present")


def main(argv):
    if len(argv) != 4 or argv[1] not in ("l3", "l5") or argv[3] not in ("native", "jvm"):
        print(__doc__)
        return 2
    with open(argv[2]) as f:
        row = json.load(f)
    {"l3": check_l3, "l5": check_l5}[argv[1]](row, argv[3])
    print("SMOKE PASS", argv[1], argv[3], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
