#!/usr/bin/env python3
"""Diagnostic (non-paper tier): ArcadeDB dense recall-latency curves at 10M.

Hypothesis under test: JVector's maxConnections (Vamana degree) is not
equivalent to hnswlib's M (which yields 2*M base-layer links), so the
matched-nominal-parameter comparison starves ArcadeDB's graph. Build the
DEEP-10M index at maxConnections in {16, 32}, then sweep efSearch per
query (vectorNeighbors takes ef as an argument) and record recall/p50.

Output: one JSON line per (maxConnections, efSearch) to --out.
"""
import argparse
import json
import os
import statistics
import time

import numpy as np

import l3d_dense as base


def run(mc, out_path):
    import arcadedb_embedded as arcadedb
    train, test, gt = base.load_dataset("deep10m")
    heap = os.environ.get("ARCADEDB_HEAP", "16g")
    db = arcadedb.create_database(f"/tmp/probe_arcade_mc{mc}",
                                  jvm_kwargs={"heap_size": heap,
                                              "jvm_args": f"-Xms{heap}"})
    db.command("sql", "CREATE VERTEX TYPE Article")
    db.command("sql", "CREATE PROPERTY Article.vid INTEGER")
    db.command("sql", "CREATE PROPERTY Article.embedding ARRAY_OF_FLOATS")
    t0 = time.time()
    db.begin()
    for vid in range(len(train)):
        db.command("sql", "INSERT INTO Article SET vid = :v, embedding = :e",
                   {"v": vid, "e": arcadedb.to_java_float_array(train[vid])})
        if (vid + 1) % 10_000 == 0:
            db.commit()
            db.begin()
    db.commit()
    db.command("sql", f'''CREATE INDEX ON Article (embedding) LSM_VECTOR
               METADATA {{ "dimensions": {base.DIM}, "similarity": "EUCLIDEAN",
               "maxConnections": {mc}, "beamWidth": 100,
               "storeVectorsInGraph": false, "addHierarchy": true }}''')
    build_s = round(time.time() - t0, 1)
    print(f"mc={mc} built in {build_s}s", flush=True)

    # WARM BEFORE EVERY ef, held out of the timed set.
    #
    # The sweep had no warmup at all, so the ef=50 point (always first) absorbed
    # the entire cold-index cost and every later point ran warm: at deep10m the
    # same engine reads 8.9-10.0 ms on its first pass and 0.9-1.2 ms afterwards,
    # which inverts or flattens the low end of the very curve this probe draws.
    # Warming at each ef rather than once keeps the points comparable to each
    # other, since a new ef changes how much of the graph is touched.
    _warm = test[-20:] if len(test) > 40 else test[:1]

    def _warmup(ef_value):
        for wq in _warm:
            db.query("sql",
                     "SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?)))",
                     "Article[embedding]",
                     arcadedb.to_java_float_array(wq), base.K, ef_value).to_list()

    timed = range(len(test) - 20) if len(test) > 40 else range(len(test))
    for ef in (50, 100, 200, 400, 800):
        _warmup(ef)
        lat, hits = [], 0
        for qi in timed:
            q = arcadedb.to_java_float_array(test[qi])
            t = time.time()
            rows = db.query(
                "sql",
                "SELECT vid FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
                "ORDER BY distance",
                "Article[embedding]", q, base.K, ef).to_list()
            lat.append((time.time() - t) * 1000)
            got = [int(r["vid"]) for r in rows]
            hits += len(set(got) & set(gt[qi].tolist()))
        # DENOMINATOR MUST MATCH WHAT WAS TIMED. The warmup slice is held out of
        # `timed`, so dividing by len(test) would under-report recall by exactly
        # the held-out fraction and the error would look like a real recall loss
        # at every ef.
        n_timed = len(timed)
        rec = hits / (n_timed * base.K)
        lat.sort()
        row = {"maxConnections": mc, "efSearch": ef, "build_s": build_s,
               "recall_at_10": round(rec, 4),
               "p50_ms": round(statistics.median(lat), 3),
               "p95_ms": round(lat[int(len(lat) * 0.95)], 3)}
        print(json.dumps(row), flush=True)
        with open(out_path, "a") as f:
            f.write(json.dumps(row) + "\n")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(args.mc, args.out)
