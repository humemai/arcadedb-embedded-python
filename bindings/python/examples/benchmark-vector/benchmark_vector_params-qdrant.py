#!/usr/bin/env python3
"""
Qdrant Vector Benchmark
======================

pip install qdrant-client==1.16.2

Qdrant HNSW benchmark aligned with ArcadeDB (JVector) and FAISS benchmarks.

Features:
- ANN-Benchmarks datasets
- Recall@k
- Latency
- Build time
- Warmup
- Persistence + restart (real disk-backed storage)

"""

import argparse
import os
import shutil
import time

import h5py
import numpy as np
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PointStruct,
    SearchParams,
    VectorParams,
)

# -----------------------------
# Dataset metadata
# -----------------------------

DATASETS = {
    "sift-128-euclidean": "http://ann-benchmarks.com/sift-128-euclidean.hdf5",
    "glove-100-angular": "http://ann-benchmarks.com/glove-100-angular.hdf5",
}

DATASET_METRICS = {
    "sift-128-euclidean": "euclidean",
    "glove-100-angular": "cosine",
}

DATASET_DESCRIPTIONS = {
    "sift-128-euclidean": """
**SIFT-128-Euclidean**
- Vectors: 1,000,000
- Dimensions: 128
- Queries: 10,000
- Metric: Euclidean
""",
    "glove-100-angular": """
**GloVe-100-Angular**
- Vectors: ~1.2M
- Dimensions: 100
- Queries: 10,000
- Metric: Cosine
""",
}

# -----------------------------
# Utilities
# -----------------------------


def download_dataset(url, path):
    if os.path.exists(path):
        return
    print(f"Downloading {url} -> {path}...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def load_ann_data(dataset, count, num_queries, k_values):
    path = f"{dataset}.hdf5"
    download_dataset(DATASETS[dataset], path)

    with h5py.File(path, "r") as f:
        train = np.array(f["train"][:count])
        test = np.array(f["test"][:num_queries])
        neighbors = f["neighbors"]
        total_train = f["train"].shape[0]

        metric = DATASET_METRICS[dataset]

        if metric == "cosine":
            train = train.astype(np.float32)
            test = test.astype(np.float32)
            train /= np.linalg.norm(train, axis=1, keepdims=True)
            test /= np.linalg.norm(test, axis=1, keepdims=True)

        ground_truth = None
        if train.shape[0] == total_train:
            ground_truth = {}
            for k in k_values:
                gt = neighbors[:num_queries, :k]
                ground_truth[k] = [set(row) for row in gt]

    return train, test, ground_truth, train.shape[1]


def compute_ground_truth(data, queries, k_values, metric):
    print("Computing ground truth (brute force)...")
    max_k = max(k_values)
    gt = {k: [] for k in k_values}

    if metric == "cosine":
        scores = np.dot(queries, data.T)
        for i in range(len(queries)):
            idx = np.argpartition(scores[i], -max_k)[-max_k:]
            idx = idx[np.argsort(scores[i][idx])[::-1]]
            for k in k_values:
                gt[k].append(set(idx[:k]))

    elif metric == "euclidean":
        data_sq = np.sum(data**2, axis=1)
        scores = -2 * np.dot(queries, data.T) + data_sq
        for i in range(len(queries)):
            idx = np.argpartition(scores[i], max_k)[:max_k]
            idx = idx[np.argsort(scores[i][idx])]
            for k in k_values:
                gt[k].append(set(idx[:k]))

    return gt


# -----------------------------
# Qdrant Core
# -----------------------------


def setup_qdrant_collection(
    path,
    collection,
    dim,
    metric,
    m,
    ef_construct,
    data,
):
    if os.path.exists(path):
        shutil.rmtree(path)

    distance = Distance.COSINE if metric == "cosine" else Distance.EUCLID

    client = QdrantClient(path=path)

    t0 = time.time()
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(
            size=dim,
            distance=distance,
            hnsw_config=HnswConfigDiff(
                m=m,
                ef_construct=ef_construct,
            ),
        ),
    )

    points = [PointStruct(id=i, vector=data[i].tolist()) for i in range(len(data))]

    client.upsert(collection_name=collection, points=points)
    build_time = time.time() - t0

    return client, build_time


def evaluate_qdrant(client, collection, queries, ground_truth, k_values, ef_search):
    max_k = max(k_values)
    latencies = []
    recalls = {k: [] for k in k_values}

    for i, q in enumerate(queries):
        t0 = time.time()
        res = client.query_points(
            collection_name=collection,
            query=q.tolist(),
            limit=max_k,
            search_params=SearchParams(hnsw_ef=ef_search),
        )
        hits = res.points

        latencies.append((time.time() - t0) * 1000)

        ids = [h.id for h in hits]

        for k in k_values:
            recall = len(set(ids[:k]) & ground_truth[k][i]) / k
            recalls[k].append(recall)

    return {
        k: {
            "recall": np.mean(recalls[k]),
            "recall_std": np.std(recalls[k]),
            "latency": np.mean(latencies),
            "latency_std": np.std(latencies),
        }
        for k in k_values
    }


# -----------------------------
# Experiment wrapper
# -----------------------------


def test_qdrant(
    data,
    queries,
    ground_truth,
    k_values,
    dim,
    metric,
    m,
    ef_construct,
    ef_search,
    base_path,
):
    collection = "vectors"
    path = f"{base_path}_qdrant"

    client, build_time = setup_qdrant_collection(
        path,
        collection,
        dim,
        metric,
        m,
        ef_construct,
        data,
    )

    # Warmup
    t0 = time.time()
    client.query_points(
        collection_name=collection,
        query=queries[0].tolist(),
        limit=k_values[0],
    )
    warmup_time = time.time() - t0

    before = evaluate_qdrant(
        client,
        collection,
        queries,
        ground_truth,
        k_values,
        ef_search,
    )

    # Restart (real persistence)
    del client
    t0 = time.time()
    client = QdrantClient(path=path)
    open_time = time.time() - t0

    after = evaluate_qdrant(
        client,
        collection,
        queries,
        ground_truth,
        k_values,
        ef_search,
    )

    shutil.rmtree(path)

    results = {}
    for k in k_values:
        results[k] = {
            "recall_before": before[k]["recall"],
            "recall_after": after[k]["recall"],
            "latency_before": before[k]["latency"],
            "latency_after": after[k]["latency"],
            "build_time": build_time,
            "warmup_time": warmup_time,
            "open_time": open_time,
        }
    return results


# -----------------------------
# Markdown Output
# -----------------------------


def save_markdown(results, dataset_info, filename):
    with open(filename, "w") as f:
        f.write("# Qdrant HNSW Benchmark\n\n")

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

            if "Total_Time" in first_r:
                f.write(
                    f"- **Total Time**: {first_r['Total_Time']/60:.2f} min ({first_r['Total_Time']:.2f}s)\n"
                )

            f.write("\n")

            # Get unique k values
            k_values = sorted(list(set(r["k"] for r in scen_results)))

            for k in k_values:
                f.write(f"### k = {k}\n\n")
                f.write(
                    "| m | ef_construct | ef_search | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) |\n"
                )
                f.write("|---|---|---|---|---|---|---|---|---|---|\n")

                k_results = [r for r in scen_results if r["k"] == k]
                for r in k_results:
                    f.write(
                        f"| {r['m']} | {r['ef_construct']} | {r['ef_search']} | "
                        f"{r['recall_before']:.4f} | {r['recall_after']:.4f} | "
                        f"{r['latency_before']:.2f} | {r['latency_after']:.2f} | "
                        f"{r['build_time']:.2f} | {r['warmup_time']:.4f} | {r['open_time']:.4f} |\n"
                    )
                f.write("\n")


# -----------------------------
# Main
# -----------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=DATASETS.keys())
    args = parser.parse_args()

    k_values = [10, 50, 100]
    scenarios = [
        ("Tiny", 1_000, 10),
        ("Small", 10_000, 100),
        ("Medium", 100_000, 1_000),
        ("Full", None, 10_000),
    ]

    ms = [8, 16, 32, 64]
    ef_construct = 200
    ef_search_values = [32, 64, 128, 256]

    results = []
    output_file = f"benchmark_qdrant_{args.dataset}.md"

    dataset_info = {
        "Name": args.dataset,
        "Source": DATASETS[args.dataset],
        "Metric": DATASET_METRICS[args.dataset].capitalize(),
        "K Values": str(k_values),
    }

    for name, count, nq in scenarios:
        print(f"--- Scenario: {name} ---")

        start_load = time.time()
        data, queries, gt, dim = load_ann_data(
            args.dataset,
            count=count if count else 10**9,
            num_queries=nq,
            k_values=k_values,
        )
        load_time = time.time() - start_load

        # Update count if it was None (Full)
        actual_count = len(data)

        gt_time = 0
        if gt is None:
            start_gt = time.time()
            gt = compute_ground_truth(
                data,
                queries,
                k_values,
                DATASET_METRICS[args.dataset],
            )
            gt_time = time.time() - start_gt

        start_scenario = time.time()

        # We need to capture DB Setup Time. In Qdrant script, setup happens inside test_qdrant for each param set.
        # But for the summary, we usually want to show one setup time.
        # However, since we rebuild for each param set, maybe we can just take the first one or average?
        # Or we can just report the build time of the first run as "DB Setup Time" for the scenario summary.
        # Let's use the first run's build time as representative or just 0 if we consider it per-test.
        # benchmark_vector_params.py does setup ONCE per scenario, then copies DB.
        # Here we rebuild every time.
        # I will use the build time from the first iteration as the "DB Setup Time" for the summary.

        first_build_time = 0
        is_first = True

        for m in ms:
            for ef in ef_search_values:
                print(f"  Running m={m}, ef={ef}...")
                res = test_qdrant(
                    data=data,
                    queries=queries,
                    ground_truth=gt,
                    k_values=k_values,
                    dim=dim,
                    metric=DATASET_METRICS[args.dataset],
                    m=m,
                    ef_construct=ef_construct,
                    ef_search=ef,
                    base_path=f"./qdrant_tmp_{args.dataset}_{name}_{m}_{ef}",
                )

                # Extract build time from one of the k results (they are all same for same m/ef)
                # res is dict k -> result dict
                current_build_time = res[k_values[0]]["build_time"]

                if is_first:
                    first_build_time = current_build_time
                    is_first = False

                for k in k_values:
                    results.append(
                        {
                            "Scenario": name,
                            "dim": dim,
                            "count": actual_count,
                            "queries": len(queries),
                            "Load(s)": load_time,
                            "GT_Calc(s)": gt_time,
                            "DB_Setup(s)": first_build_time,  # Using first run as representative
                            "m": m,
                            "ef_construct": ef_construct,
                            "ef_search": ef,
                            "k": k,
                            **res[k],
                        }
                    )

        total_time = time.time() - start_scenario

        # Update Total Time for all rows in this scenario
        for r in results:
            if r["Scenario"] == name:
                r["Total_Time"] = total_time

        save_markdown(results, dataset_info, output_file)

    save_markdown(results, dataset_info, output_file)
    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()
