import math
import os
import random
import shutil
import time

import arcadedb_embedded as arcadedb
from arcadedb_embedded import create_database

# Configuration
DB_PATH = "bench_accuracy_db"
DIMENSIONS_LIST = [4, 8, 16, 32]
NUM_VECTORS = 1000
NUM_QUERIES = 20
K = 10


def normalize(v):
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def generate_vector(dim):
    return normalize([random.gauss(0, 1) for _ in range(dim)])


def run_benchmark_for_dim(dim):
    print(f"\n==================================================")
    print(f"Benchmarking Accuracy: Dim={dim}, N={NUM_VECTORS}")
    print(f"==================================================")

    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

    db = create_database(DB_PATH)

    # Generate Data
    print("Generating data...")
    vectors = [generate_vector(dim) for _ in range(NUM_VECTORS)]

    # Generate Queries (use existing vectors to ensure matches)
    query_indices = random.sample(range(NUM_VECTORS), NUM_QUERIES)
    queries = [vectors[i] for i in query_indices]

    results = {"NONE": [], "INT8": [], "BINARY": []}

    for q_type in ["NONE", "INT8", "BINARY"]:
        print(f"\n--- Testing {q_type} (Dim={dim}) ---")
        type_name = f"Vector_{q_type}_{dim}"

        # Create Type
        if db.schema.exists_type(type_name):
            db.schema.drop_type(type_name)
        db.schema.create_vertex_type(type_name)
        db.schema.create_property(type_name, "vector", "ARRAY_OF_FLOATS")
        db.schema.create_property(type_name, "id", "INTEGER")

        # Insert Data
        print("Inserting data...")
        with db.transaction():
            for i, vec in enumerate(vectors):
                v = db.new_vertex(type_name)
                v.set("id", i)
                v.set("vector", arcadedb.to_java_float_array(vec))
                v.save()

        # Create Index
        print("Creating index...")
        kwargs = {"dimensions": dim}
        if q_type != "NONE":
            kwargs["quantization"] = q_type

        try:
            db.create_vector_index(type_name, "vector", **kwargs)
        except Exception as e:
            print(f"ERROR creating index for {q_type}: {e}")
            # Fill with empty results so we can continue
            results[q_type] = [set() for _ in range(NUM_QUERIES)]
            continue

        # Search
        print("Searching...")
        try:
            index = db.schema.get_vector_index(type_name, "vector")

            for i, query_vec in enumerate(queries):
                try:
                    res = index.find_nearest(query_vec, k=K)

                    # Extract IDs
                    ids = set()
                    for r in res:
                        try:
                            # r is a tuple (Vertex, score)
                            vertex = r[0]
                            ids.add(vertex.get("id"))
                        except Exception as e:
                            pass  # print(f"Warning: Could not get ID from result {r}: {e}")

                    results[q_type].append(ids)
                except Exception as e:
                    print(f"Error searching query {i}: {e}")
                    results[q_type].append(set())
        except Exception as e:
            print(f"Error getting index: {e}")
            results[q_type] = [set() for _ in range(NUM_QUERIES)]

    db.close()

    # Calculate Recall
    int8_recall_sum = 0
    binary_recall_sum = 0
    none_self_recall_sum = 0

    for i in range(NUM_QUERIES):
        ground_truth = results["NONE"][i]
        target_id = query_indices[i]

        # Check if NONE found the vector itself (Sanity Check)
        if target_id in ground_truth:
            none_self_recall_sum += 1

        if len(ground_truth) == 0:
            continue

        # INT8
        int8_res = results["INT8"][i]
        intersection_int8 = ground_truth.intersection(int8_res)
        recall_int8 = len(intersection_int8) / len(ground_truth)
        int8_recall_sum += recall_int8

        # BINARY
        binary_res = results["BINARY"][i]
        intersection_binary = ground_truth.intersection(binary_res)
        recall_binary = len(intersection_binary) / len(ground_truth)
        binary_recall_sum += recall_binary

    avg_none_self = (none_self_recall_sum / NUM_QUERIES) * 100
    avg_int8 = (int8_recall_sum / NUM_QUERIES) * 100
    avg_binary = (binary_recall_sum / NUM_QUERIES) * 100

    return avg_none_self, avg_int8, avg_binary


if __name__ == "__main__":
    summary = []
    for dim in DIMENSIONS_LIST:
        try:
            r_none, r_int8, r_binary = run_benchmark_for_dim(dim)
            summary.append((dim, r_none, r_int8, r_binary))
        except Exception as e:
            print(f"CRITICAL ERROR running dim {dim}: {e}")
            summary.append((dim, -1, -1, -1))

    print(
        "\n\n========================================================================"
    )
    print("FINAL SUMMARY (Recall@10)")
    print("NONE (Self): % of queries where the vector found itself")
    print("INT8/BINARY: % overlap with NONE results")
    print("========================================================================")
    print(
        f"{'Dim':<10} | {'NONE (Self)':<15} | {'INT8 (vs NONE)':<15} | {'BINARY (vs NONE)':<15}"
    )
    print("-" * 65)
    for dim, r_none, r_int8, r_binary in summary:
        s_none = f"{r_none:.2f}%" if r_none >= 0 else "ERROR"
        s_int8 = f"{r_int8:.2f}%" if r_int8 >= 0 else "ERROR"
        s_binary = f"{r_binary:.2f}%" if r_binary >= 0 else "ERROR"
        print(f"{dim:<10} | {s_none:<15} | {s_int8:<15} | {s_binary:<15}")
