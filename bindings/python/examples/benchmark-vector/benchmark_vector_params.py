#!/usr/bin/env python3
"""
Benchmark Vector Parameters
===========================

Runs a comprehensive benchmark of ArcadeDB's JVector index implementation
across multiple dataset sizes and index parameters.

Scenarios:
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

import arcadedb_embedded as arcadedb
import h5py
import numpy as np
import requests

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


def download_dataset(url, dest_path):
    if os.path.exists(dest_path):
        print(f"  Dataset already exists at {dest_path}")
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

    filename = f"{dataset_name}.hdf5"
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
            # neighbors contains indices of nearest neighbors
            ground_truth = {}
            for k in k_values:
                gt_indices = np.array(neighbors_ds[:num_queries, :k])
                ground_truth[k] = [set(indices) for indices in gt_indices]
        else:
            print("    - Subset of data selected; Ground Truth must be re-computed")

        # Normalize if needed (Angular datasets like GloVe need normalization for Cosine)
        metric = DATASET_METRICS[dataset_name]
        if metric == "cosine":
            print("  Normalizing data for Cosine similarity...")
            data = data.astype(np.float32)
            data /= np.linalg.norm(data, axis=1, keepdims=True)

            queries = queries.astype(np.float32)
            queries /= np.linalg.norm(queries, axis=1, keepdims=True)
        else:
            print(f"  Using {metric} metric (no normalization).")

    return data, queries, ground_truth, dim


# --- Core Logic from internal_test_vector_accuracy.py ---


def compute_ground_truth(
    data, queries, k_values, metric="cosine", precomputed_ground_truth=None
):
    if precomputed_ground_truth is not None:
        return precomputed_ground_truth

    print(f"  Computing Ground Truth ({metric})...")
    start = time.time()

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
        # Squared Euclidean distance: x^2 + y^2 - 2xy
        # We only need ranking, so squared is fine.

        data_sq = np.sum(data**2, axis=1)
        term1 = -2 * np.dot(queries, data.T)
        scores = term1 + data_sq

        for i in range(len(queries)):
            # Smallest scores are best
            top_k_indices = np.argpartition(scores[i], max_k)[:max_k]
            top_k_indices = top_k_indices[np.argsort(scores[i][top_k_indices])]

            for k in k_values:
                ground_truth[k].append(set(top_k_indices[:k]))
    else:
        raise ValueError(f"Unsupported metric: {metric}")

    print(f"  Ground Truth computed in {time.time() - start:.4f}s")
    return ground_truth


def setup_database(db_path, data):
    start_setup = time.time()

    if os.path.exists(db_path):
        shutil.rmtree(db_path)

    db = arcadedb.create_database(db_path)

    print("  Importing data into ArcadeDB...")
    with db.transaction():
        db.schema.create_vertex_type("VectorData")
        db.schema.create_property("VectorData", "id", "INTEGER")
        db.schema.create_property("VectorData", "vector", "ARRAY_OF_FLOATS")

    with db.batch_context(batch_size=10000) as batch:
        for i, vec in enumerate(data):
            batch.create_vertex("VectorData", id=i, vector=vec)

    setup_time = time.time() - start_setup
    print(f"  Database setup completed in {setup_time:.4f}s")

    return db, setup_time


def evaluate_index(index, queries, ground_truth_dict, k_values):
    """
    Runs queries against the index and calculates Recall and Latency.
    """
    max_k = max(k_values)
    latencies = []

    # Pre-allocate lists for each k
    recalls_map = {k: [] for k in k_values}

    for i, query_vec in enumerate(queries):
        t0 = time.time()

        # Use Python API
        results = index.find_nearest(query_vec, k=max_k)

        latencies.append((time.time() - t0) * 1000)

        result_ids_ordered = []
        for item, score in results:
            try:
                # Handle both Record (JVector) and Vertex (Legacy)
                vertex = item
                # If item is a Result wrapper (from results.py), get the underlying vertex
                if hasattr(item, "get_vertex"):
                    vertex = item.get_vertex()
                elif hasattr(item, "asVertex"):
                    vertex = item.asVertex()

                vid = vertex.getInteger("id")
                result_ids_ordered.append(vid)
            except Exception:
                pass

        # Calculate metrics for each k
        for k in k_values:
            # Take top k from the results
            top_k_ids = set(result_ids_ordered[:k])

            # Ground truth for this k
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


def test_index(
    db_path,
    queries,
    ground_truth_dict,
    k_values,
    dim,
    count,
    max_connections,
    beam_width,
    metric="cosine",
):
    print(
        f"    Testing JVector (max_connections={max_connections}, beam_width={beam_width})..."
    )

    # 1. Open DB to create index
    start_build = time.time()
    count_before = 0
    actual_index_name = None
    results_before = None

    with arcadedb.open_database(db_path) as db:
        print("    - DB Opened. Creating index...")
        index = db.create_vector_index(
            vertex_type="VectorData",
            vector_property="vector",
            dimensions=dim,
            distance_function=metric,
            max_connections=max_connections,
            beam_width=beam_width,
        )
        print("    - Index created.")

        # Force index build (JVector is lazy)
        print("    - Warming up index (forcing build)...")
        start_warmup = time.time()
        # Run a dummy query to trigger graph construction
        try:
            index.find_nearest(queries[0], k=k_values[0])
            print("    - Warmup query successful.")
        except Exception as e:
            print(f"    - Warmup query FAILED: {e}")
            raise
        warmup_time = time.time() - start_warmup

        actual_index_name = index._java_index.getName()

        count_before = db.count_type("VectorData")
        print(f"    - Vectors before close: {count_before}")

        print("    - Running queries BEFORE restart...")
        results_before = evaluate_index(index, queries, ground_truth_dict, k_values)

    build_time = time.time() - start_build

    # 2. Reopen DB to verify persistence and query
    print("    - Restarting Database...")
    count_after = 0
    results_after = None

    start_open = time.time()
    with arcadedb.open_database(db_path) as db:
        open_time = time.time() - start_open
        print(f"    - Database opened in {open_time:.4f}s")

        count_after = db.count_type("VectorData")
        print(f"    - Vectors after open: {count_after}")

        # Re-acquire index object
        try:
            raw_index = db.schema.get_index_by_name(actual_index_name)

            # Import wrappers
            from arcadedb_embedded.vector import VectorIndex

            index = VectorIndex(raw_index, db)

        except Exception as e:
            print(
                f"    - Warning: Could not retrieve index '{actual_index_name}' by name: {e}"
            )
            pass

        print("    - Running queries AFTER restart...")
        results_after = evaluate_index(index, queries, ground_truth_dict, k_values)

    # Merge results
    final_results = {}
    for k in k_values:
        rb = results_before[k]
        ra = results_after[k]

        final_results[k] = {
            "recall": ra["recall"],  # Default to After for main metric
            "recall_std": ra["recall_std"],
            "latency": ra["latency"],
            "latency_std": ra["latency_std"],
            "recall_before": rb["recall"],
            "recall_after": ra["recall"],
            "latency_before": rb["latency"],
            "latency_after": ra["latency"],
            "build_time": build_time,
            "warmup_time": warmup_time,
            "open_time": open_time,
            "count_before": count_before,
            "count_after": count_after,
        }

    return final_results


def format_val(val, fmt=".4f"):
    return f"{val:{fmt}}" if val is not None else "N/A"


def format_std(val, std, fmt=".4f"):
    return f"{val:{fmt}}±{std:{fmt}}" if val is not None else "N/A"


def save_results_to_markdown(
    results, filename="benchmark_results.md", dataset_info=None
):
    with open(filename, "w") as f:
        f.write("# Benchmark Results\n\n")
        f.write(
            "This benchmark evaluates ArcadeDB's JVector index implementation across multiple dataset sizes and index parameters.\n\n"
        )

        if dataset_info:
            f.write("## Dataset Information\n\n")

            desc = DATASET_DESCRIPTIONS.get(dataset_info.get("Name"))
            if desc:
                f.write(desc.strip() + "\n\n")

            for key, value in dataset_info.items():
                f.write(f"- **{key}**: {value}\n")
            f.write("\n")

        f.write("## Targets & Use Cases\n\n")
        f.write("| k      | Recall target | Use case                   |\n")
        f.write("| ------ | ------------- | -------------------------- |\n")
        f.write("| 10     | 0.85–0.95     | Small corpora only         |\n")
        f.write("| **50** | **≥ 0.95**    | **Default RAG**            |\n")
        f.write("| 100    | 0.90–0.93     | Very large / noisy corpora |\n\n")
        f.write("As k increases, Recall@k can go down.\n\n")

        f.write("**Note:**\n")
        f.write("- **Metric Equations**:\n")
        f.write("  - **Euclidean**: Similarity = $1 / (1 + d^2)$ (Higher is better)\n")
        f.write(
            "  - **Cosine**: Distance = $(1 - \\cos(\\theta)) / 2$ (Lower is better)\n"
        )

        if not dataset_info:
            f.write(
                "- **Ground Truth**: Computed via exact brute-force matrix multiplication (numpy) in Python.\n"
            )
            f.write(
                "- **Data Distribution**: Clustered data (simulating topics) on unit hypersphere. Queries are perturbed data points.\n"
            )

        # Group results by Scenario
        scenarios = []
        seen_scenarios = set()
        for r in results:
            if r["Scenario"] not in seen_scenarios:
                scenarios.append(r["Scenario"])
                seen_scenarios.add(r["Scenario"])

        for scen_name in scenarios:
            scen_results = [r for r in results if r["Scenario"] == scen_name]
            first_r = scen_results[0]

            f.write(f"\n## Scenario: {scen_name}\n\n")
            f.write(f"- **Dimensions**: {first_r['dim']}\n")
            f.write(f"- **Vector Count**: {first_r['count']}\n")
            f.write(f"- **Queries**: {first_r['queries']}\n")
            f.write(f"- **Data Load Time**: {first_r['Load(s)']:.4f}s\n")
            f.write(f"- **Ground Truth Time**: {first_r['GT_Calc(s)']:.4f}s\n")
            f.write(f"- **DB Setup Time**: {first_r['DB_Setup(s)']:.4f}s\n")

            j_time = first_r.get("J_Total_Time", 0)

            if j_time > 0:
                f.write(
                    f"- **JVector Total Time**: {j_time/60:.2f} min ({j_time:.2f}s)\n"
                )

            f.write("\n")

            # Get unique k values
            k_values = sorted(list(set(r["k"] for r in scen_results)))

            for k in k_values:
                f.write(f"### k = {k}\n\n")
                f.write(
                    "| max_connections | beam_width | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) | Count (Before) | Count (After) |\n"
                )
                f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")

                k_results = [r for r in scen_results if r["k"] == k]
                for r in k_results:
                    # Format Recall Before/After
                    j_rb = format_val(r.get("J_Recall_Before"))
                    j_ra = format_val(r.get("J_Recall_After"))

                    # Format Latency Before/After
                    j_lb = format_val(r.get("J_Lat_Before"), ".2f")
                    j_la = format_val(r.get("J_Lat_After"), ".2f")

                    j_bld_str = format_val(r["J_Build(s)"])
                    j_warmup_str = format_val(r.get("J_Warmup(s)"))
                    j_open_str = format_val(r.get("J_Open(s)"))

                    j_cb = r.get("J_Count_Before", "N/A")
                    j_ca = r.get("J_Count_After", "N/A")

                    f.write(
                        f"| {r['max_connections']} | {r['beam_width']} | {j_rb} | {j_ra} | {j_lb} | {j_la} | {j_bld_str} | {j_warmup_str} | {j_open_str} | {j_cb} | {j_ca} |\n"
                    )
                f.write("\n")
    print(f"  [Saved results to {filename}]")


# --- Benchmark Runner ---


def run_benchmark():
    parser = argparse.ArgumentParser(
        description="Benchmark ArcadeDB Vector Index Implementations"
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default=None,
        help="Use a standard ANN-Benchmark dataset (e.g., sift-128-euclidean)",
    )
    args = parser.parse_args()

    if not args.dataset:
        raise ValueError("Dataset must be specified. Use --dataset.")

    # Ensure JVM is started and logs are silenced

    db_path = f"./my_test_databases/benchmark_db_{args.dataset}"
    k_values = [10, 50, 100]

    scenarios = [
        {"name": "Tiny", "count": 1000, "queries": 10},
        {"name": "Small", "count": 10000, "queries": 100},
        {"name": "Medium", "count": 100000, "queries": 1000},
        {"name": "Full", "count": None, "queries": 10000},  # None = All available
    ]

    metric = DATASET_METRICS[args.dataset]

    dataset_info = {
        "Name": args.dataset,
        "Source": DATASETS[args.dataset],
        "Metric": metric.capitalize(),
        "K Values": str(k_values),
    }

    max_connections_values = [8, 16, 32, 64]
    beam_width_values = [32, 64, 128, 256]

    results = []

    print("Starting Benchmark...")
    print("=" * 80)

    for scenario in scenarios:
        scenario_start_time = time.time()
        # Generate Data & Setup DB once per scenario
        load_time = 0
        gt_time = 0

        if args.dataset:
            start_load = time.time()
            data, queries, ground_truth, dim = load_ann_benchmark_data(
                args.dataset, scenario["count"], scenario["queries"], k_values
            )
            load_time = time.time() - start_load

            scenario["dim"] = dim
            scenario["count"] = len(data)  # Update count if it was None

            start_gt = time.time()
            ground_truth = compute_ground_truth(
                data,
                queries,
                k_values,
                metric=metric,
                precomputed_ground_truth=ground_truth,
            )
            gt_time = time.time() - start_gt
        else:
            raise ValueError(
                "Dataset must be specified. Random generation is deprecated."
            )

        print(
            f"\nScenario: {scenario['name']} (Dim={scenario['dim']}, Count={scenario['count']})"
        )

        db, setup_time = setup_database(db_path, data)
        db.close()

        j_results_map = {}
        j_total_time = 0

        try:
            # 1. Run JVector Tests
            print("  Running JVector Tests...")
            start_j = time.time()
            for max_connections in max_connections_values:
                for beam_width in beam_width_values:
                    print(
                        f"    - Params: max_connections={max_connections}, beam_width={beam_width}...",
                        end="",
                        flush=True,
                    )
                    temp_db_path = db_path + f"_temp_j_{max_connections}_{beam_width}"
                    if os.path.exists(temp_db_path):
                        shutil.rmtree(temp_db_path)
                    shutil.copytree(db_path, temp_db_path)

                    try:
                        j_results_map[(max_connections, beam_width)] = test_index(
                            temp_db_path,
                            queries,
                            ground_truth,
                            k_values,
                            scenario["dim"],
                            scenario["count"],
                            max_connections,
                            beam_width,
                            metric=metric,
                        )
                    finally:
                        if os.path.exists(temp_db_path):
                            shutil.rmtree(temp_db_path)
                    print(" Done.")
            j_total_time = time.time() - start_j

            # 3. Combine Results
            for max_connections in max_connections_values:
                for beam_width in beam_width_values:
                    j_results = j_results_map.get((max_connections, beam_width))

                    for k in k_values:
                        # Extract JVector results for this k
                        j_res = {}
                        if j_results:
                            j_res = j_results[k]

                        results.append(
                            {
                                "Scenario": scenario["name"],
                                "dim": scenario["dim"],
                                "count": scenario["count"],
                                "queries": scenario["queries"],
                                "max_connections": max_connections,
                                "beam_width": beam_width,
                                "k": k,
                                "Load(s)": load_time,
                                "GT_Calc(s)": gt_time,
                                "DB_Setup(s)": setup_time,
                                # JVector
                                "J_Recall": j_res.get("recall"),
                                "J_Std": j_res.get("recall_std"),
                                "J_Build(s)": j_res.get("build_time"),
                                "J_Warmup(s)": j_res.get("warmup_time"),
                                "J_Open(s)": j_res.get("open_time"),
                                "J_Lat(ms)": j_res.get("latency"),
                                "J_Lat_Std": j_res.get("latency_std"),
                                "J_Count_Before": j_res.get("count_before"),
                                "J_Count_After": j_res.get("count_after"),
                                "J_Recall_Before": j_res.get("recall_before"),
                                "J_Recall_After": j_res.get("recall_after"),
                                "J_Lat_Before": j_res.get("latency_before"),
                                "J_Lat_After": j_res.get("latency_after"),
                                "J_Total_Time": j_total_time,
                            }
                        )

        finally:
            if os.path.exists(db_path):
                shutil.rmtree(db_path)

        scenario_duration = time.time() - scenario_start_time
        for r in results:
            if r["Scenario"] == scenario["name"]:
                r["Scenario_Duration"] = scenario_duration

        save_results_to_markdown(
            results,
            filename=f"benchmark_results_{args.dataset}.md",
            dataset_info=dataset_info,
        )

    # Print Results Table
    print("\n" + "=" * 160)
    print(
        f"{'Scenario':<10} | {'max_connections':<15} | {'beam_width':<10} | {'k':<3} | {'Recall (Before)':<15} | {'Recall (After)':<15} | {'Lat (ms) (Before)':<18} | {'Lat (ms) (After)':<18} | {'Build (s)':<10} | {'Warmup (s)':<10} | {'Open (s)':<10} | {'Count (B)':<10} | {'Count (A)':<10}"
    )
    print("-" * 160)

    for r in results:
        # Format Recall Before/After
        j_rb = format_val(r.get("J_Recall_Before"))
        j_ra = format_val(r.get("J_Recall_After"))

        # Format Latency Before/After
        j_lb = format_val(r.get("J_Lat_Before"), ".2f")
        j_la = format_val(r.get("J_Lat_After"), ".2f")

        j_bld_str = format_val(r["J_Build(s)"])
        j_warmup_str = format_val(r.get("J_Warmup(s)"))
        j_open_str = format_val(r.get("J_Open(s)"))

        j_cb = str(r.get("J_Count_Before", "N/A"))
        j_ca = str(r.get("J_Count_After", "N/A"))

        print(
            f"{r['Scenario']:<10} | {r['max_connections']:<15} | {r['beam_width']:<10} | {r['k']:<3} | {j_rb:<15} | {j_ra:<15} | {j_lb:<18} | {j_la:<18} | {j_bld_str:<10} | {j_warmup_str:<10} | {j_open_str:<10} | {j_cb:<10} | {j_ca:<10}"
        )
    print("=" * 160)


if __name__ == "__main__":
    run_benchmark()
