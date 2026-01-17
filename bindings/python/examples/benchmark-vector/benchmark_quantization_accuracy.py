import math
import os
import random
import shutil
import time

import arcadedb_embedded as arcadedb
from arcadedb_embedded import create_database

# Configuration
DB_PATH = "./my_test_databases/bench_quantization_accuracy_db"
# BINARY quantization requires higher dimensions to be effective
DIMENSIONS_LIST = [64, 128, 256, 768]
NUM_VECTORS = 2000
NUM_QUERIES = 50
K = 10

# Representative PQ parameter sweeps (must divide dimension)
QUANT_CONFIGS = [
    {"label": "NONE", "quantization": None, "pq": None},
    {"label": "INT8", "quantization": "INT8", "pq": None},
    {"label": "BINARY", "quantization": "BINARY", "pq": None},
    {
        "label": "PQ_M16_K256_center",
        "quantization": "PRODUCT",
        "pq": {
            "pqSubspaces": 16,
            "pqClusters": 256,
            "pqCenterGlobally": True,
            "pqTrainingLimit": 50000,
        },
    },
    {
        "label": "PQ_M32_K256_nocenter",
        "quantization": "PRODUCT",
        "pq": {
            "pqSubspaces": 32,
            "pqClusters": 256,
            "pqCenterGlobally": False,
            "pqTrainingLimit": 50000,
        },
    },
    {
        "label": "PQ_M64_K128_center",
        "quantization": "PRODUCT",
        "pq": {
            "pqSubspaces": 64,
            "pqClusters": 128,
            "pqCenterGlobally": True,
            "pqTrainingLimit": 100000,
        },
    },
]


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

    with arcadedb.create_database(DB_PATH) as db:

        # Generate Data
        print("Generating data...")
        vectors = [generate_vector(dim) for _ in range(NUM_VECTORS)]

        # Generate Queries (use existing vectors to ensure matches)
        query_indices = random.sample(range(NUM_VECTORS), NUM_QUERIES)
        queries = [vectors[i] for i in query_indices]

        results = {cfg["label"]: [] for cfg in QUANT_CONFIGS}

        for cfg in QUANT_CONFIGS:
            q_type = cfg["quantization"] or "NONE"
            label = cfg["label"]
            pq_cfg = cfg.get("pq")

            print(f"\n--- Testing {label} (Dim={dim}, quant={q_type}, pq={pq_cfg}) ---")
            type_name = f"Vector_{label}_{dim}".replace(" ", "_")

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
            import json

            metadata = {"dimensions": dim}
            if q_type != "NONE":
                metadata["quantization"] = q_type
            if pq_cfg:
                metadata.update(pq_cfg)

            try:
                sql = f"CREATE INDEX ON {type_name} (vector) LSM_VECTOR METADATA {json.dumps(metadata)}"
                db.command("sql", sql)
            except Exception as e:
                print(f"ERROR creating index for {q_type}: {e}")
                # Fill with empty results so we can continue
                results[label] = [set() for _ in range(NUM_QUERIES)]
                continue

            # Search
            print("Searching...")
            try:
                index = db.schema.get_vector_index(type_name, "vector")

                # Ensure PQ data is built and loaded for PRODUCT
                index.build_graph_now()

                for i, query_vec in enumerate(queries):
                    try:
                        if q_type == "PRODUCT":
                            res = index.find_nearest_approximate(query_vec, k=K)
                        else:
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

                        results[label].append(ids)
                    except Exception as e:
                        print(f"Error searching query {i}: {e}")
                        results[label].append(set())
            except Exception as e:
                print(f"Error getting index: {e}")
                results[label] = [set() for _ in range(NUM_QUERIES)]

    # Calculate Recall
    recall_sums = {label: 0.0 for label in results if label != "NONE"}
    none_self_recall_sum = 0

    for i in range(NUM_QUERIES):
        ground_truth = results["NONE"][i]
        target_id = query_indices[i]

        # Check if NONE found the vector itself (Sanity Check)
        if target_id in ground_truth:
            none_self_recall_sum += 1

        if len(ground_truth) == 0:
            continue

        for label, res_list in results.items():
            if label == "NONE":
                continue
            res = res_list[i]
            intersection = ground_truth.intersection(res)
            recall = len(intersection) / len(ground_truth)
            recall_sums[label] += recall

    avg_none_self = (none_self_recall_sum / NUM_QUERIES) * 100
    avg_recalls = {
        label: (recall_sums[label] / NUM_QUERIES) * 100 for label in recall_sums
    }

    return avg_none_self, avg_recalls


if __name__ == "__main__":
    summary = []
    for dim in DIMENSIONS_LIST:
        try:
            r_none, r_recalls = run_benchmark_for_dim(dim)
            summary.append((dim, r_none, r_recalls))
        except Exception as e:
            print(f"CRITICAL ERROR running dim {dim}: {e}")
            summary.append((dim, -1, {}))

    print(
        "\n\n========================================================================"
    )
    print("FINAL SUMMARY (Recall@10)")
    print("NONE (Self): % of queries where the vector found itself")
    print("INT8/BINARY/PQ configs: % overlap with NONE results")
    print("========================================================================")
    labels = [cfg["label"] for cfg in QUANT_CONFIGS if cfg["label"] != "NONE"]
    col_widths = [10, 14] + [max(len(lbl), 10) + 2 for lbl in labels]

    def fmt_row(values):
        return " | ".join(val.ljust(w) for val, w in zip(values, col_widths))

    header_vals = ["Dim", "NONE (Self)"] + labels
    print(fmt_row(header_vals))
    print("-" * (sum(col_widths) + 3 * (len(col_widths) - 1)))

    for dim, r_none, r_recalls in summary:
        s_none = f"{r_none:.2f}%" if r_none >= 0 else "ERROR"
        row_vals = [str(dim), s_none]
        for lbl in labels:
            val = r_recalls.get(lbl, -1)
            row_vals.append(f"{val:.2f}%" if val >= 0 else "ERROR")
        print(fmt_row(row_vals))
