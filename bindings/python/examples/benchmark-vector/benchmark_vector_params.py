#!/usr/bin/env python3
"""
Benchmark Vector Parameters
===========================

Runs a comprehensive benchmark of ArcadeDB's JVector index implementation
across multiple dataset sizes and index parameters.

Design:
- Build-Once, Sweep-Search
- Incremental Markdown Reporting
- Persistence Testing per Build Config
- Embedded API Only

dataset_sizes:
1. Small:  Count=1,000,     Queries=10
2. Medium: Count=10,000,    Queries=100
3. Large:  Count=100,000,   Queries=1,000
4. Full:   Count=1,000,000, Queries=10,000

Index Parameters Swept:
- max_connections: [16, 32, 64]
- beam_width: [128, 256, 512]


**1. SIFT-128-Euclidean (`sift-128-euclidean.hdf5`)**
*   **File Size:** 501 MB
*   **Total Vectors:** 1,000,000 (1 Million)
*   **Dimensions:** 128
*   **Test Queries:** 10,000

**2. GloVe-100-Angular (`glove-100-angular.hdf5`)**
*   **File Size:** 463 MB
*   **Total Vectors:** 1,183,514 (~1.2 Million)
*   **Dimensions:** 100
*   **Test Queries:** 10,000

"""

import argparse
import os
import shutil
import time

import h5py
import numpy as np
import requests

# -----------------------------
# Configuration
# -----------------------------

DATASETS = {
    "sift-128-euclidean": "http://ann-benchmarks.com/sift-128-euclidean.hdf5",
    "glove-100-angular": "http://ann-benchmarks.com/glove-100-angular.hdf5",
}

DATASET_DESCRIPTIONS = {
    "sift-128-euclidean": """
**1. SIFT-128-Euclidean (`sift-128-euclidean.hdf5`)**
*   **File Size:** 501 MB
*   **Total Vectors:** 1,000,000 (1 Million)
*   **Dimensions:** 128
*   **Test Queries:** 10,000
""",
    "glove-100-angular": """
**2. GloVe-100-Angular (`glove-100-angular.hdf5`)**
*   **File Size:** 463 MB
*   **Total Vectors:** 1,183,514 (~1.2 Million)
*   **Dimensions:** 100
*   **Test Queries:** 10,000
""",
}

DATASET_METRICS = {
    "sift-128-euclidean": "euclidean",
    "glove-100-angular": "cosine",
}

# Build parameters define the index structure and trigger a rebuild
BUILD_PARAMS = {
    # "max_connections": [16, 32, 64],
    "max_connections": [32],
    # "ef_construction_factors": [8, 16, 32],
    "ef_construction_factors": [8],
    "quantization": ["NONE"],
}

# Search parameters affect traversal only and are swept per build
SEARCH_PARAMS = {
    # "overquery_factors": [1, 4, 8, 16, 32, 64, 128],
    "overquery_factors": [16],
}


# -----------------------------
# Utilities
# -----------------------------


def download_dataset(url, dest_path):
    if os.path.exists(dest_path):
        return

    print(f"  Downloading dataset from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("  Download complete.")


def load_ann_benchmark_data(dataset_name, count, num_queries, k_values):
    url = DATASETS.get(dataset_name)
    if not url:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    if not os.path.exists("datasets"):
        os.makedirs("datasets")
    filename = os.path.join("datasets", f"{dataset_name}.hdf5")
    download_dataset(url, filename)

    print(f"  Loading {dataset_name} from {filename}...")
    with h5py.File(filename, "r") as f:
        train_ds = f["train"]
        test_ds = f["test"]
        neighbors_ds = f["neighbors"]

        total_train = train_ds.shape[0]
        total_test = test_ds.shape[0]

        # Handle "None" for full dataset
        if count is None or count > total_train:
            count = total_train

        if num_queries is None or num_queries > total_test:
            num_queries = total_test

        print(f"    - Train: {count}/{total_train}")
        print(f"    - Test:  {num_queries}/{total_test}")

        # Load train data
        data = np.array(train_ds[:count])
        dim = data.shape[1]

        # Load test queries
        queries = np.array(test_ds[:num_queries])

        # Ground Truth
        ground_truth = None
        if count == total_train:
            print("    - Using pre-computed ground truth from dataset")
            ground_truth = {}
            for k in k_values:
                gt_indices = np.array(neighbors_ds[:num_queries, :k])
                ground_truth[k] = [set(indices) for indices in gt_indices]
        else:
            print("    - Subset of data selected; Ground Truth must be re-computed")

        # Normalize if needed
        metric = DATASET_METRICS[dataset_name]
        if metric == "cosine":
            print("  Normalizing data for Cosine similarity...")
            data = data.astype(np.float32)
            data /= np.linalg.norm(data, axis=1, keepdims=True)

            queries = queries.astype(np.float32)
            queries /= np.linalg.norm(queries, axis=1, keepdims=True)

    return data, queries, ground_truth, dim


def compute_ground_truth(
    data, queries, k_values, metric="cosine", precomputed_ground_truth=None
):
    if precomputed_ground_truth is not None:
        return precomputed_ground_truth

    print(f"  Computing Ground Truth ({metric})...")
    start = time.perf_counter()

    max_k = max(k_values)
    ground_truth = {k: [] for k in k_values}

    if metric == "cosine":
        scores = np.dot(queries, data.T)
        for i in range(len(queries)):
            top_k_indices = np.argpartition(scores[i], -max_k)[-max_k:]
            top_k_indices = top_k_indices[np.argsort(scores[i][top_k_indices])[::-1]]
            for k in k_values:
                ground_truth[k].append(set(top_k_indices[:k]))

    elif metric == "euclidean":
        data_sq = np.sum(data**2, axis=1)
        term1 = -2 * np.dot(queries, data.T)
        scores = term1 + data_sq

        for i in range(len(queries)):
            top_k_indices = np.argpartition(scores[i], max_k)[:max_k]
            top_k_indices = top_k_indices[np.argsort(scores[i][top_k_indices])]
            for k in k_values:
                ground_truth[k].append(set(top_k_indices[:k]))
    else:
        raise ValueError(f"Unsupported metric: {metric}")

    print(f"  Ground Truth computed in {time.perf_counter() - start:.4f}s")
    return ground_truth


# -----------------------------
# Database & Index Operations
# -----------------------------


def setup_database(db, data):
    start_setup = time.perf_counter()

    print("  Importing data into ArcadeDB...")
    # Schema operations are auto-transactional
    db.schema.create_vertex_type("VectorData")
    db.schema.create_property("VectorData", "id", "INTEGER")
    db.schema.create_property("VectorData", "vector", "ARRAY_OF_FLOATS")

    with db.batch_context(batch_size=10000) as batch:
        for i, vec in enumerate(data):
            batch.create_vertex("VectorData", id=i, vector=vec)

    setup_time = time.perf_counter() - start_setup
    print(f"  Database setup completed in {setup_time:.4f}s")

    return setup_time


def build_index(db, dim, metric, max_connections, beam_width, quantization="NONE"):
    print(
        f"    Creating Index (max_connections={max_connections}, beam={beam_width}, quant={quantization})..."
    )
    start_build = time.perf_counter()

    index = db.create_vector_index(
        vertex_type="VectorData",
        vector_property="vector",
        dimensions=dim,
        distance_function=metric,
        max_connections=max_connections,
        beam_width=beam_width,
        quantization=quantization if quantization != "NONE" else None,
    )

    build_time = time.perf_counter() - start_build
    print(f"    Index created in {build_time:.4f}s")
    return index, build_time


def evaluate_index(
    index,
    queries,
    ground_truth_dict,
    k_values,
    overquery_factor=1,
):
    """
    Runs queries against the index and calculates Recall and Latency.
    """
    max_k = max(k_values)
    latencies = []
    recalls_map = {k: [] for k in k_values}

    for i, query_vec in enumerate(queries):
        t0 = time.perf_counter()

        # Embedded API
        results = index.find_nearest(
            query_vec, k=max_k, overquery_factor=overquery_factor
        )

        latencies.append((time.perf_counter() - t0) * 1000)

        result_ids_ordered = []
        for idx, item_tuple in enumerate(results):
            item = item_tuple[0]

            # Use .get() method from Pythonic API
            vid = item.get("id")
            if vid is not None:
                result_ids_ordered.append(vid)

        for k in k_values:
            top_k_ids = set(result_ids_ordered[:k])
            gt_set = ground_truth_dict[k][i]
            intersection = len(top_k_ids.intersection(gt_set))
            recall = intersection / k
            recalls_map[k].append(recall)

    avg_latency = np.mean(latencies)
    std_latency = np.std(latencies)

    results = {}
    for k in k_values:
        results[k] = {
            "recall": np.mean(recalls_map[k]),
            "recall_std": np.std(recalls_map[k]),
            "latency": avg_latency,
            "latency_std": std_latency,
        }
    return results


# -----------------------------
# Markdown Reporting
# -----------------------------


def ensure_table_header(f, algo="jvector"):
    headers = [
        "max_connections",
        "beam_width",
        "overquery",
        "Recall (Before)",
        "Recall (After)",
        "Latency (ms) (Before)",
        "Latency (ms) (After)",
        "Build (s)",
        "Warmup (s) (Before)",
        "Warmup (s) (After)",
        "Open (s)",
    ]
    f.write("| " + " | ".join(headers) + " |\n")
    f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")


def append_markdown_row(
    filename,
    dataset_info,
    dataset_size,
    k,
    algo,
    row,
):
    file_exists = os.path.exists(filename)

    with open(filename, "a") as f:
        if not file_exists:
            # File header
            f.write(f"# ArcadeDB JVector Benchmark\n\n")
            f.write("## Dataset Information\n\n")
            for k0, v0 in dataset_info.items():
                f.write(f"- **{k0}**: {v0}\n")
            f.write("\n")

        # dataset_size section
        dataset_size_header = f"## dataset_size: {dataset_size['name']}"
        k_header = f"### k = {k}"

        content = ""
        if file_exists:
            with open(filename, "r") as rf:
                content = rf.read()

        if dataset_size_header not in content:
            f.write(f"\n{dataset_size_header}\n\n")
            f.write(f"- **Dimensions**: {dataset_size['dim']}\n")
            f.write(f"- **Vectors**: {dataset_size['count']}\n")
            f.write(f"- **Queries**: {dataset_size['queries']}\n\n")

            # If we write a new dataset_size, we definitely need the K header for this first row
            f.write(f"\n{k_header}\n\n")
            ensure_table_header(f, algo)
        else:
            # dataset_size exists. Check if K header exists *after* the last dataset_size header.
            last_dataset_size_idx = content.rfind(dataset_size_header)
            if content.find(k_header, last_dataset_size_idx) == -1:
                f.write(f"\n{k_header}\n\n")
                ensure_table_header(f, algo)

        # Row
        f.write(
            f"| {row['max_connections']} "
            f"| {row['beam_width']} "
            f"| {row['overquery_factor']} "
            f"| {row['recall_before']:.4f} "
            f"| {row['recall_after']:.4f} "
            f"| {row['latency_before']:.2f} "
            f"| {row['latency_after']:.2f} "
            f"| {row['build_time']:.2f} "
            f"| {row['warmup_time']:.4f} "
            f"| {row['warmup_time_after']:.4f} "
            f"| {row['open_time']:.4f} |\n"
        )


# -----------------------------
# Main Benchmark Runner
# -----------------------------


def run_benchmark():
    parser = argparse.ArgumentParser(
        description="Benchmark ArcadeDB Vector Index Implementations"
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        required=True,
        help="Use a standard ANN-Benchmark dataset (e.g., sift-128-euclidean)",
    )
    parser.add_argument(
        "--dataset-size",
        choices=["tiny", "small", "medium", "full"],
        default="medium",
        help="Benchmark dataset size",
    )
    parser.add_argument(
        "--xmx",
        type=str,
        default="16g",
        help="JVM max heap size (e.g., 16g, 32g)",
    )
    parser.add_argument(
        "--xms",
        type=str,
        default="16g",
        help="JVM initial heap size (e.g., 16g, 32g)",
    )
    parser.add_argument(
        "--max-direct-memory",
        type=str,
        default="16g",
        help="JVM MaxDirectMemorySize (e.g., 16g, 32g)",
    )
    parser.add_argument(
        "--location-cache-size",
        type=str,
        default="500000",
        help="Vector index locationCacheSize (-1 for unlimited)",
    )
    parser.add_argument(
        "--graph-build-cache-size",
        type=str,
        default="50000",
        help="Vector index graphBuildCacheSize",
    )
    parser.add_argument(
        "--mutations-before-rebuild",
        type=str,
        default="100",
        help="Vector index mutationsBeforeRebuild (default: 100)",
    )
    args = parser.parse_args()

    # Configure JVM before importing arcadedb
    jvm_args = (
        f"-Xmx{args.xmx} -Xms{args.xms} "
        f"-XX:MaxDirectMemorySize={args.max_direct_memory} "
        f"-Darcadedb.vectorIndex.locationCacheSize={args.location_cache_size} "
        f"-Darcadedb.vectorIndex.graphBuildCacheSize={args.graph_build_cache_size} "
        f"-Darcadedb.vectorIndex.mutationsBeforeRebuild={args.mutations_before_rebuild}"
    )
    os.environ["ARCADEDB_JVM_ARGS"] = jvm_args
    print(f"JVM Configuration: {jvm_args}\n")

    # Import arcadedb after setting JVM args and make it global
    global arcadedb
    import arcadedb_embedded as arcadedb

    # Create config suffix for naming
    config_suffix = f"xmx{args.xmx}_loc{args.location_cache_size}_graph{args.graph_build_cache_size}_mut{args.mutations_before_rebuild}"

    db_base_path = f"./jvector_{args.dataset}_size_{args.dataset_size}_{config_suffix}"
    k_values = [10]

    # Output file
    md_file = (
        f"benchmark_jvector_{args.dataset}_size_{args.dataset_size}_{config_suffix}.md"
    )

    all_dataset_sizes = {
        "tiny": {"name": "tiny", "count": 1000, "queries": 10},
        "small": {"name": "small", "count": 10000, "queries": 100},
        "medium": {"name": "medium", "count": 100000, "queries": 1000},
        "full": {"name": "full", "count": None, "queries": 10000},
    }

    dataset_sizes = []
    if args.dataset_size:
        dataset_sizes.append(all_dataset_sizes[args.dataset_size])

    metric = DATASET_METRICS[args.dataset]

    dataset_info = {
        "Name": args.dataset,
        "Source": DATASETS[args.dataset],
        "Metric": metric.capitalize(),
        "K Values": str(k_values),
        "JVM Heap": f"-Xmx{args.xmx} -Xms{args.xms}",
        "JVM Direct Memory": f"-XX:MaxDirectMemorySize={args.max_direct_memory}",
        "Location Cache Size": args.location_cache_size,
        "Graph Build Cache Size": args.graph_build_cache_size,
        "Mutations Before Rebuild": args.mutations_before_rebuild,
    }

    print("Starting Benchmark...")
    print("=" * 80)

    for dataset_size in dataset_sizes:
        print(f"\n--- dataset_size: {dataset_size['name']} ---")

        # Load Data
        start_load = time.perf_counter()
        data, queries, ground_truth, dim = load_ann_benchmark_data(
            args.dataset, dataset_size["count"], dataset_size["queries"], k_values
        )
        load_time = time.perf_counter() - start_load

        dataset_size["dim"] = dim
        dataset_size["count"] = len(data)

        # Compute GT
        start_gt = time.perf_counter()
        ground_truth = compute_ground_truth(
            data,
            queries,
            k_values,
            metric=metric,
            precomputed_ground_truth=ground_truth,
        )
        gt_time = time.perf_counter() - start_gt

        # Iterate Build Configs
        for max_connections in BUILD_PARAMS["max_connections"]:
            for ef_c in BUILD_PARAMS["ef_construction_factors"]:
                beam_width = ef_c * max_connections
                quantization = "NONE"  # Fixed for now

                # Unique DB path for this build config
                db_path = f"{db_base_path}_{max_connections}_{beam_width}"

                print(
                    f"\n  [Build Config] max_connections={max_connections}, beam={beam_width}"
                )

                if os.path.exists(db_path):
                    shutil.rmtree(db_path)

                # 1. Setup & Build inside managed lifecycle
                results_before = {}
                warmup_time = 0.0
                build_time = 0.0
                warmup_time_after = 0.0
                open_time = 0.0
                setup_time = 0.0

                with arcadedb.create_database(db_path) as db:
                    setup_time = setup_database(db, data)

                    index, build_time = build_index(
                        db, dim, metric, max_connections, beam_width, quantization
                    )

                    # 2. Warmup
                    print("    Warming up...")
                    t0 = time.perf_counter()
                    for i in range(min(5, len(queries))):
                        index.find_nearest(queries[i], k=k_values[0])
                    warmup_time = time.perf_counter() - t0

                    # 3. Run "Before" Queries
                    print("    Running 'Before' queries...")
                    for oq in SEARCH_PARAMS["overquery_factors"]:
                        results_before[oq] = evaluate_index(
                            index, queries, ground_truth, k_values, overquery_factor=oq
                        )

                    print("    Persisting (Closing DB)...")

                # 5. Reload (Open)
                print("    Reloading (Opening DB)...")
                t0 = time.perf_counter()
                with arcadedb.open_database(db_path) as db:
                    open_time = time.perf_counter() - t0

                    # Re-acquire index
                    # Note: We assume only one vector index exists on VectorData.vector
                    index = db.schema.get_vector_index("VectorData", "vector")

                    # 5.5 Warmup AFTER reload
                    print("    Warming up AFTER reload...")
                    t0 = time.perf_counter()
                    for i in range(min(5, len(queries))):
                        index.find_nearest(queries[i], k=k_values[0])
                    warmup_time_after = time.perf_counter() - t0

                    # 6. Run "After" Queries & Report
                    print("    Running 'After' queries & Reporting...")
                    for oq in SEARCH_PARAMS["overquery_factors"]:
                        metrics_after = evaluate_index(
                            index, queries, ground_truth, k_values, overquery_factor=oq
                        )
                        metrics_before = results_before[oq]

                        for k in k_values:
                            row = {
                                "max_connections": max_connections,
                                "beam_width": beam_width,
                                "overquery_factor": oq,
                                "recall_before": metrics_before[k]["recall"],
                                "recall_after": metrics_after[k]["recall"],
                                "latency_before": metrics_before[k]["latency"],
                                "latency_after": metrics_after[k]["latency"],
                                "build_time": build_time,
                                "warmup_time": warmup_time,
                                "warmup_time_after": warmup_time_after,
                                "open_time": open_time,
                            }

                            append_markdown_row(
                                filename=md_file,
                                dataset_info=dataset_info,
                                dataset_size=dataset_size,
                                k=k,
                                algo="jvector",
                                row=row,
                            )
                            print(
                                f"      -> k={k}, oq={oq}: Recall={row['recall_after']:.4f}, Latency={row['latency_after']:.2f}ms"
                            )

                if os.path.exists(db_path):
                    shutil.rmtree(db_path)

    print(f"\nBenchmark complete. Results saved to {md_file}")


if __name__ == "__main__":
    run_benchmark()
