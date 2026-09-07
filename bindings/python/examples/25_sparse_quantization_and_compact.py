#!/usr/bin/env python3
"""Example 25: Sparse Vectors, Weight Precision And Compaction.

Two things a sparse-retrieval workload should decide on purpose:

- weight precision: LSM_SPARSE_VECTOR quantizes posting weights to INT8 by
  default; "weightQuantization": "FP32" keeps them exact
- the settle step: COMPACT INDEX merges the LSM segments a bulk load leaves
  behind, and queries are faster afterwards

This builds the same synthetic corpus twice, once per precision, compacts both,
and reports index size, top-10 agreement between the two, and query time before
and after compaction.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import statistics
import time

import arcadedb_embedded as arcadedb
import jpype.types as jtypes

DIMENSIONS = 30_000
TOKENS_PER_DOC = 40
K = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--docs", type=int, default=20_000)
    p.add_argument("--queries", type=int, default=50)
    p.add_argument("--db-dir", default="./my_test_databases/sparse_precision")
    return p.parse_args()


def corpus(n: int, seed: int = 23) -> list[tuple[list[int], list[float]]]:
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        toks = sorted(rnd.sample(range(DIMENSIONS), TOKENS_PER_DOC))
        out.append((toks, [round(rnd.random(), 6) for _ in toks]))
    return out


def build(path: str, docs, quant: str | None):
    if os.path.exists(path):
        shutil.rmtree(path)
    db = arcadedb.create_database(path)
    db.command("sql", "CREATE DOCUMENT TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.id INTEGER")
    db.command("sql", "CREATE PROPERTY Doc.tokens ARRAY_OF_INTEGERS")
    db.command("sql", "CREATE PROPERTY Doc.weights ARRAY_OF_FLOATS")
    meta = (
        f'{{"dimensions": {DIMENSIONS}'
        + (f', "weightQuantization": "{quant}"' if quant else "")
        + "}"
    )
    db.command(
        "sql",
        f"CREATE INDEX ON Doc (tokens, weights) LSM_SPARSE_VECTOR METADATA {meta}",
    )
    with db.transaction():
        for i, (toks, wts) in enumerate(docs):
            db.command(
                "sql", f"INSERT INTO Doc SET id = {i}, tokens = {toks}, weights = {wts}"
            )
    return db


def search(db, toks, wts):
    rows = db.query(
        "sql",
        "SELECT id FROM (SELECT expand(`vector.sparseNeighbors`('Doc[tokens,weights]', ?, ?, ?)))",
        jtypes.JArray(jtypes.JInt)(toks),
        arcadedb.to_java_float_array(wts),
        K,
    ).to_list()
    return [int(r["id"]) for r in rows]


def timed_searches(db, queries):
    lat, hits = [], []
    for toks, wts in queries:
        t0 = time.perf_counter()
        hits.append(search(db, toks, wts))
        lat.append((time.perf_counter() - t0) * 1000)
    return statistics.median(lat), hits


def dir_size_mb(path: str) -> float:
    total = 0
    for root, _, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return total / 1e6


def main() -> None:
    args = parse_args()
    docs = corpus(args.docs)
    queries = docs[: args.queries]
    results = {}
    for label, quant in (("int8 (default)", None), ("fp32", "FP32")):
        path = os.path.join(args.db_dir, label.split()[0])
        db = build(path, docs, quant)
        before_ms, _ = timed_searches(db, queries)
        t0 = time.perf_counter()
        db.command("sql", "COMPACT INDEX `Doc[tokens,weights]`")
        compact_s = time.perf_counter() - t0
        after_ms, hits = timed_searches(db, queries)
        db.close()
        results[label] = {
            "size_mb": dir_size_mb(path),
            "before_ms": before_ms,
            "after_ms": after_ms,
            "compact_s": compact_s,
            "hits": hits,
        }
        print(
            f"{label:15} {args.docs:,} docs: on disk {results[label]['size_mb']:.1f} MB, "
            f"compact {compact_s:.2f}s, query p50 {before_ms:.2f} ms before -> {after_ms:.2f} ms after"
        )
    a, b = results["int8 (default)"]["hits"], results["fp32"]["hits"]
    overlap = statistics.mean(len(set(x) & set(y)) / K for x, y in zip(a, b))
    print(f"top-{K} agreement int8 vs fp32 over {len(a)} queries: {overlap:.3f}")
    print("Databases kept under", args.db_dir)


if __name__ == "__main__":
    main()
