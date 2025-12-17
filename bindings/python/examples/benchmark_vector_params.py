#!/usr/bin/env python3
"""
Benchmark Vector Parameters
===========================

Runs a comprehensive benchmark of ArcadeDB's vector index implementations
(JVector vs HNSWLib) across multiple dataset sizes and index parameters.

Scenarios:
1. Small:  Dim=64,  Count=1000,  Queries=20
2. Medium: Dim=128, Count=5000,  Queries=50
3. Large:  Dim=384, Count=10000, Queries=100

Index Parameters Swept:
- m: [16, 32, 64]
- ef: [128, 256, 512]


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

**Important Note:**
Your current benchmark scenarios are capped at **10,000** vectors ("Large" scenario).
This means you are loading the 500MB file but only using the first 1% of the data.

If you want to benchmark the *real* performance of the index, we should probably add a
scenario that uses the full 1M vectors, though that will take significantly longer to
build and test.

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


def test_index(
    db,
    index_type,
    queries,
    ground_truth_dict,
    k_values,
    dim,
    count,
    m,
    ef,
    metric="cosine",
):
    print(f"    Testing {index_type} (m={m}, ef={ef})...")

    # Create Index
    start_build = time.time()

    if index_type == "JVECTOR":
        index = db.create_vector_index(
            vertex_type="VectorData",
            vector_property="vector",
            dimensions=dim,
            distance_function=metric,
            max_connections=m,
            beam_width=ef,
        )
    else:  # HNSWLIB
        index = db.create_legacy_vector_index(
            vertex_type="VectorData",
            vector_property="vector",
            dimensions=dim,
            max_items=count,
            id_property="id",
            distance_function=metric,
            m=m,
            ef=ef,
            ef_construction=200,
        )

        # Legacy index needs manual population
        print("    - Populating legacy index (paginated)...")
        last_rid = "#-1:-1"
        batch_size = 10000

        while True:
            query = f"SELECT FROM VectorData WHERE @rid > {last_rid} ORDER BY @rid LIMIT {batch_size}"
            chunk = list(db.query("sql", query))

            if not chunk:
                break

            with db.transaction():
                for record in chunk:
                    index.add_vertex(record.get_vertex())

            last_rid = chunk[-1].get_rid()

    # Force index build (JVector is lazy)
    print("    - Warming up index (forcing build)...")
    # Run a dummy query to trigger graph construction
    index.find_nearest(queries[0], k=k_values[0])

    build_time = time.time() - start_build

    results_by_k = {}
    max_k = max(k_values)

    # Query
    # We query with max_k once, then slice results for smaller k's
    # This is efficient but assumes the index returns ordered results (which it does)

    latencies = []

    # Pre-allocate lists for each k
    recalls_map = {k: [] for k in k_values}
    hits_map = {k: [] for k in k_values}

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

            hits_map[k].append(1 if intersection > 0 else 0)

    avg_latency = np.mean(latencies)
    std_latency = np.std(latencies)

    for k in k_values:
        results_by_k[k] = {
            "recall": np.mean(recalls_map[k]),
            "recall_std": np.std(recalls_map[k]),
            "hit": np.mean(hits_map[k]),
            "hit_std": np.std(hits_map[k]),
            "latency": avg_latency,
            "latency_std": std_latency,
            "build_time": build_time,
        }

    return results_by_k


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
            "This benchmark compares ArcadeDB's vector index implementations (JVector vs HNSWLib) across multiple dataset sizes and index parameters.\n\n"
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
        f.write(
            "| k      | Recall target | Hit target | Use case                   |\n"
        )
        f.write(
            "| ------ | ------------- | ---------- | -------------------------- |\n"
        )
        f.write(
            "| 10     | 0.85–0.95     | 0.90–0.95  | Small corpora only         |\n"
        )
        f.write(
            "| **50** | **≥ 0.95**    | **≥ 0.99** | **Default RAG**            |\n"
        )
        f.write(
            "| 100    | 0.90–0.93     | ≈ 1.0      | Very large / noisy corpora |\n\n"
        )
        f.write("As k increases, Recall@k can go down — but Hit@k must go up.\n\n")

        f.write("**Note:**\n")
        f.write(
            "- **Parameter Semantics**: `m` and `ef` are not exactly equivalent between implementations:\n"
        )
        f.write("  - **JVector**: `m` -> `max_connections`, `ef` -> `beam_width`.\n")
        f.write("  - **HNSWLib**: `m` -> `m`, `ef` -> `ef`.\n")
        f.write(
            "- **HNSWLib**: `ef_construction` is fixed at 200. `ef` controls search recall/speed dynamically.\n"
        )
        f.write("- **Metric Equations**:\n")
        f.write(
            "  - **Euclidean (JVector)**: Similarity = $1 / (1 + d^2)$ (Higher is better)\n"
        )
        f.write("  - **Euclidean (HNSWLib)**: Distance = $d^2$ (Lower is better)\n")
        f.write(
            "  - **Cosine (JVector)**: Distance = $(1 - \\cos(\\theta)) / 2$ (Lower is better)\n"
        )
        f.write(
            "  - **Cosine (HNSWLib)**: Distance = $1 - \\cos(\\theta)$ (Lower is better)\n"
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
            h_time = first_r.get("H_Total_Time", 0)

            if j_time > 0:
                f.write(
                    f"- **JVector Total Time**: {j_time/60:.2f} min ({j_time:.2f}s)\n"
                )
            if h_time > 0:
                f.write(
                    f"- **HNSWLib Total Time**: {h_time/60:.2f} min ({h_time:.2f}s)\n"
                )

            f.write("\n")

            # Get unique k values
            k_values = sorted(list(set(r["k"] for r in scen_results)))

            for k in k_values:
                f.write(f"### k = {k}\n\n")
                f.write(
                    "| m | ef | J_Recall (Avg±Std) | H_Recall (Avg±Std) | J_Hit (Avg) | H_Hit (Avg) | J_Build(s) | H_Build(s) | J_Lat(ms) | H_Lat(ms) |\n"
                )
                f.write("|---|---|---|---|---|---|---|---|---|---|\n")

                k_results = [r for r in scen_results if r["k"] == k]
                for r in k_results:
                    j_rec_str = format_std(r["J_Recall"], r["J_Std"])
                    h_rec_str = format_std(r["H_Recall"], r["H_Std"])
                    j_hit_str = format_val(r["J_Hit"])
                    h_hit_str = format_val(r["H_Hit"])
                    j_lat_str = format_std(r["J_Lat(ms)"], r["J_Lat_Std"], ".2f")
                    h_lat_str = format_std(r["H_Lat(ms)"], r["H_Lat_Std"], ".2f")
                    j_bld_str = format_val(r["J_Build(s)"])
                    h_bld_str = format_val(r["H_Build(s)"])

                    f.write(
                        f"| {r['m']} | {r['ef']} | {j_rec_str} | {h_rec_str} | {j_hit_str} | {h_hit_str} | {j_bld_str} | {h_bld_str} | {j_lat_str} | {h_lat_str} |\n"
                    )
                f.write("\n")
    print(f"  [Saved results to {filename}]")


# --- Benchmark Runner ---


def run_benchmark():
    parser = argparse.ArgumentParser(
        description="Benchmark ArcadeDB Vector Index Implementations"
    )
    parser.add_argument(
        "--impl",
        choices=["JVECTOR", "HNSWLIB", "ALL"],
        default="ALL",
        help="Implementation to test (JVECTOR, HNSWLIB, or ALL)",
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

    m_values = [8, 16, 32]
    ef_values = [32, 64, 128]

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
        h_results_map = {}
        j_total_time = 0
        h_total_time = 0

        try:
            # 1. Run JVector Tests
            if args.impl in ["JVECTOR", "ALL"]:
                print("  Running JVector Tests...")
                start_j = time.time()
                for m in m_values:
                    for ef in ef_values:
                        print(f"    - Params: m={m}, ef={ef}...", end="", flush=True)
                        temp_db_path = db_path + f"_temp_j_{m}_{ef}"
                        if os.path.exists(temp_db_path):
                            shutil.rmtree(temp_db_path)
                        shutil.copytree(db_path, temp_db_path)

                        try:
                            with arcadedb.open_database(temp_db_path) as db:
                                j_results_map[(m, ef)] = test_index(
                                    db,
                                    "JVECTOR",
                                    queries,
                                    ground_truth,
                                    k_values,
                                    scenario["dim"],
                                    scenario["count"],
                                    m,
                                    ef,
                                    metric=metric,
                                )
                        finally:
                            if os.path.exists(temp_db_path):
                                shutil.rmtree(temp_db_path)
                        print(" Done.")
                j_total_time = time.time() - start_j

            # 2. Run HNSWLib Tests
            if args.impl in ["HNSWLIB", "ALL"]:
                print("  Running HNSWLib Tests...")
                start_h = time.time()
                for m in m_values:
                    for ef in ef_values:
                        print(f"    - Params: m={m}, ef={ef}...", end="", flush=True)
                        temp_db_path = db_path + f"_temp_h_{m}_{ef}"
                        if os.path.exists(temp_db_path):
                            shutil.rmtree(temp_db_path)
                        shutil.copytree(db_path, temp_db_path)

                        try:
                            with arcadedb.open_database(temp_db_path) as db:
                                h_results_map[(m, ef)] = test_index(
                                    db,
                                    "HNSWLIB",
                                    queries,
                                    ground_truth,
                                    k_values,
                                    scenario["dim"],
                                    scenario["count"],
                                    m,
                                    ef,
                                    metric=metric,
                                )
                        finally:
                            if os.path.exists(temp_db_path):
                                shutil.rmtree(temp_db_path)
                        print(" Done.")
                h_total_time = time.time() - start_h

            # 3. Combine Results
            for m in m_values:
                for ef in ef_values:
                    j_results = j_results_map.get((m, ef))
                    h_results = h_results_map.get((m, ef))

                    for k in k_values:
                        # Extract JVector results for this k
                        (
                            j_rec,
                            j_std,
                            j_hit,
                            j_hit_std,
                            j_lat,
                            j_lat_std,
                            j_bld,
                        ) = (
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                        if j_results:
                            res = j_results[k]
                            j_rec = res["recall"]
                            j_std = res["recall_std"]
                            j_hit = res["hit"]
                            j_hit_std = res["hit_std"]
                            j_lat = res["latency"]
                            j_lat_std = res["latency_std"]
                            j_bld = res["build_time"]

                        # Extract HNSWLib results for this k
                        (
                            h_rec,
                            h_std,
                            h_hit,
                            h_hit_std,
                            h_lat,
                            h_lat_std,
                            h_bld,
                        ) = (
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                        if h_results:
                            res = h_results[k]
                            h_rec = res["recall"]
                            h_std = res["recall_std"]
                            h_hit = res["hit"]
                            h_hit_std = res["hit_std"]
                            h_lat = res["latency"]
                            h_lat_std = res["latency_std"]
                            h_bld = res["build_time"]

                        results.append(
                            {
                                "Scenario": scenario["name"],
                                "dim": scenario["dim"],
                                "count": scenario["count"],
                                "queries": scenario["queries"],
                                "m": m,
                                "ef": ef,
                                "k": k,
                                "Load(s)": load_time,
                                "GT_Calc(s)": gt_time,
                                "DB_Setup(s)": setup_time,
                                "J_Recall": j_rec,
                                "J_Std": j_std,
                                "J_Hit": j_hit,
                                "J_Hit_Std": j_hit_std,
                                "J_Build(s)": j_bld,
                                "J_Lat(ms)": j_lat,
                                "J_Lat_Std": j_lat_std,
                                "H_Recall": h_rec,
                                "H_Std": h_std,
                                "H_Hit": h_hit,
                                "H_Hit_Std": h_hit_std,
                                "H_Build(s)": h_bld,
                                "H_Lat(ms)": h_lat,
                                "H_Lat_Std": h_lat_std,
                                "J_Total_Time": j_total_time,
                                "H_Total_Time": h_total_time,
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
    print("\n" + "=" * 170)
    print(
        f"{'Scenario':<10} | {'m':<3} | {'ef':<4} | {'k':<3} | {'J_Recall (Avg±Std)':<20} | {'H_Recall (Avg±Std)':<20} | {'J_Hit (Avg)':<15} | {'H_Hit (Avg)':<15} | {'J_Build(s)':<10} | {'H_Build(s)':<10} | {'J_Lat(ms)':<15} | {'H_Lat(ms)':<15}"
    )
    print("-" * 170)

    for r in results:
        j_rec_str = format_std(r["J_Recall"], r["J_Std"])
        h_rec_str = format_std(r["H_Recall"], r["H_Std"])
        j_hit_str = format_val(r["J_Hit"])
        h_hit_str = format_val(r["H_Hit"])
        j_lat_str = format_std(r["J_Lat(ms)"], r["J_Lat_Std"], ".2f")
        h_lat_str = format_std(r["H_Lat(ms)"], r["H_Lat_Std"], ".2f")
        j_bld_str = format_val(r["J_Build(s)"])
        h_bld_str = format_val(r["H_Build(s)"])

        print(
            f"{r['Scenario']:<10} | {r['m']:<3} | {r['ef']:<4} | {r['k']:<3} | {j_rec_str:<20} | {h_rec_str:<20} | {j_hit_str:<15} | {h_hit_str:<15} | {j_bld_str:<10} | {h_bld_str:<10} | {j_lat_str:<15} | {h_lat_str:<15}"
        )
    print("=" * 200)


if __name__ == "__main__":
    run_benchmark()
