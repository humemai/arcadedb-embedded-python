#!/usr/bin/env python3
"""
Chunked insertion for the full dataset (embedded). BatchContext is not recommended
for embedded ingest at the moment; use explicit chunked transactions instead.
"""

import os
import shutil
import time

import arcadedb_embedded as arcadedb
import h5py
import numpy as np
import requests
from arcadedb_embedded.vector import to_java_float_array

DATASET_NAME = "glove-100-angular"
DATASET_URL = "http://ann-benchmarks.com/glove-100-angular.hdf5"
DATASET_PATH = os.path.join("datasets", f"{DATASET_NAME}.hdf5")

BATCH_SIZE = 50_000
DB_BASE = "./ingest_compare_full"


def download_dataset():
    os.makedirs("datasets", exist_ok=True)
    if os.path.exists(DATASET_PATH):
        return
    print(f"Downloading dataset from {DATASET_URL}...")
    with requests.get(DATASET_URL, stream=True) as r:
        r.raise_for_status()
        with open(DATASET_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print("Dataset download complete.")


def load_data():
    download_dataset()
    print("Loading dataset into memory...")
    with h5py.File(DATASET_PATH, "r") as f:
        data = np.array(f["train"][:], dtype=np.float32)
    print(f"Loaded data shape: {data.shape}")
    return data


def verify_basic(db):
    """Return basic verification info: total count and one sample vector dimension."""
    count = db.count_type("VectorData")
    sample_dim = None
    sample_id = None
    try:
        rs = db.query("sql", "SELECT id, vector FROM VectorData LIMIT 1")
        first = rs.first()
        if first:
            sample_id = first.get("id")
            vec = first.get("vector")
            if vec is not None:
                sample_dim = len(vec)
    except Exception:
        pass
    print(f"verify: count={count}, sample_id={sample_id}, sample_dim={sample_dim}")
    return count, sample_dim


def prep_db(db_path):
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    db = arcadedb.create_database(db_path)
    db.schema.create_vertex_type("VectorData")
    db.schema.create_property("VectorData", "id", "INTEGER")
    db.schema.create_property("VectorData", "vector", "ARRAY_OF_FLOATS")
    return db


def mode_chunk_tx(data):
    db_path = f"{DB_BASE}_chunk"
    with prep_db(db_path) as db:
        total_start = time.perf_counter()
        for start in range(0, len(data), BATCH_SIZE):
            end = start + BATCH_SIZE
            chunk_start = time.perf_counter()
            with db.transaction():
                for i, vec in enumerate(data[start:end], start=start):
                    v = db.new_vertex("VectorData")
                    v.set("id", i)
                    v.set("vector", to_java_float_array(vec))
                    v.save()
            chunk_time = time.perf_counter() - chunk_start
            chunk_count = end - start
            if chunk_time > 0:
                print(
                    f"chunk_tx segment [{start:,}-{end-1:,}] -> {chunk_count:,} vecs in {chunk_time:.2f}s "
                    f"({chunk_count/chunk_time:,.0f} vec/s)"
                )

        total_time = time.perf_counter() - total_start
        if total_time > 0:
            print(
                f"chunk_tx total -> {len(data):,} vecs in {total_time:.2f}s "
                f"({len(data)/total_time:,.0f} vec/s)"
            )

        count, sample_dim = verify_basic(db)
        return count


def timed(label, fn):
    t0 = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t0
    print(f"{label} completed in {dt:.2f}s")
    return result


def main():
    data = load_data()
    timed("chunk_tx", lambda: mode_chunk_tx(data))


if __name__ == "__main__":
    main()
