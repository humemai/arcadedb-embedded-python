#!/usr/bin/env python3
"""
FAISS Vector Benchmark
=====================

pip install faiss-cpu==1.13.1

FAISS HNSW benchmark matching ArcadeDB JVector experiments.

Datasets:
- sift-128-euclidean
- glove-100-angular

Scenarios:
- Tiny
- Small
- Medium
- Full

Metrics:
- Recall@k
- Latency (ms)
- Build time
- Warmup time
- Persistence reload time
"""

import argparse
import os
import time

import faiss
import h5py
import numpy as np
import requests

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
# FAISS Core
# -----------------------------


def build_faiss_index(data, metric, M):
    d = data.shape[1]
    if metric == "cosine":
        index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
    else:
        index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_L2)

    index.hnsw.efConstruction = 200

    t0 = time.time()
    index.add(data)
    build_time = time.time() - t0

    return index, build_time


def evaluate_faiss(index, queries, ground_truth, k_values, ef_search):
    index.hnsw.efSearch = ef_search
    max_k = max(k_values)

    latencies = []
    recalls = {k: [] for k in k_values}

    for i, q in enumerate(queries):
        t0 = time.time()
        _, ids = index.search(q.reshape(1, -1), max_k)
        latencies.append((time.time() - t0) * 1000)

        ids = ids[0]
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


def test_faiss(
    data, queries, ground_truth, k_values, M, ef, metric, index_path="faiss.index"
):
    # Cleanup before
    if os.path.exists(index_path):
        os.remove(index_path)

    index, build_time = build_faiss_index(data, metric, M)

    # warmup
    t0 = time.time()
    index.search(queries[0].reshape(1, -1), k_values[0])
    warmup_time = time.time() - t0

    before = evaluate_faiss(index, queries, ground_truth, k_values, ef)

    # Persist and Reload
    faiss.write_index(index, index_path)
    del index  # Force release

    t0 = time.time()
    index = faiss.read_index(index_path)
    open_time = time.time() - t0

    after = evaluate_faiss(index, queries, ground_truth, k_values, ef)

    # Cleanup after
    if os.path.exists(index_path):
        os.remove(index_path)

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
        f.write("# FAISS HNSW Benchmark\n\n")

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
                    "| M | efConstruction | efSearch | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) |\n"
                )
                f.write("|---|---|---|---|---|---|---|---|---|---|\n")

                k_results = [r for r in scen_results if r["k"] == k]
                for r in k_results:
                    f.write(
                        f"| {r['M']} | {r['efConstruction']} | {r['efSearch']} | "
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

    Ms = [8, 16, 32, 64]
    efs = [32, 64, 128, 256]
    efConstruction = 200

    results = []
    output_file = f"benchmark_faiss_{args.dataset}.md"

    dataset_info = {
        "Name": args.dataset,
        "Source": DATASETS[args.dataset],
        "Metric": DATASET_METRICS[args.dataset].capitalize(),
        "K Values": str(k_values),
    }

    for name, count, nq in scenarios:
        print(f"--- Scenario: {name} ---")
        print(f"Loading data for {args.dataset}...")

        start_load = time.time()
        data, queries, gt, dim = load_ann_data(
            args.dataset,
            count=count if count else 10**9,
            num_queries=nq,
            k_values=k_values,
        )
        load_time = time.time() - start_load

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

        print(f"Data loaded. Train: {data.shape}, Queries: {queries.shape}")

        start_scenario = time.time()
        first_build_time = 0
        is_first = True

        for M in Ms:
            for ef in efs:
                print(f"  Running M={M}, ef={ef}...")
                res = test_faiss(
                    data=data,
                    queries=queries,
                    ground_truth=gt,
                    k_values=k_values,
                    M=M,
                    ef=ef,
                    metric=DATASET_METRICS[args.dataset],
                    index_path=f"faiss_{args.dataset}_{name}.index",
                )

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
                            "DB_Setup(s)": first_build_time,
                            "M": M,
                            "efConstruction": efConstruction,
                            "efSearch": ef,
                            "k": k,
                            **res[k],
                        }
                    )

                save_markdown(results, dataset_info, output_file)

        total_time = time.time() - start_scenario
        for r in results:
            if r["Scenario"] == name:
                r["Total_Time"] = total_time

        save_markdown(results, dataset_info, output_file)

    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    faiss.omp_set_num_threads(1)
    main()
