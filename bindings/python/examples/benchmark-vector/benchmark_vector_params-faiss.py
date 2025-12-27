#!/usr/bin/env python3
"""
FAISS Vector Benchmark
=====================

pip install faiss-cpu==1.13.1

FAISS HNSW benchmark matching ArcadeDB JVector experiments.

Datasets:
- sift-128-euclidean
- glove-100-angular

dataset_sizes:
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
# Algorithm Configurations
# -----------------------------

ALGO_CONFIGS = {
    # -------------------------------------------------
    # FAISS HNSW (graph-based, non-quantized)
    # -------------------------------------------------
    "hnsw": {
        # Graph degree
        "Ms": [16, 32, 64],
        # efConstruction = ef_c * M
        "ef_construction_factors": [8, 16, 32],
        # Search depth (≈ efSearch)
        "efs": [32, 64, 128, 256],
    },
    # -------------------------------------------------
    # FAISS IVF-Flat (coarse quantization only)
    # -------------------------------------------------
    "ivf_flat": {
        # Number of coarse centroids
        "nlists": [64, 128, 256, 512, 1024],
        # Number of probed lists
        "nprobes": [16, 32, 64, 128],
    },
    # -------------------------------------------------
    # FAISS IVF-PQ (coarse + product quantization)
    # -------------------------------------------------
    "ivf_pq": {
        # Coarse centroids
        "nlists": [64, 128, 256, 512, 1024, 2048],
        # PQ subquantizers (dim must be divisible by m)
        "pq_m": [8, 10, 16, 20, 32, 50],  # 8/16/32 for 128d, 10/20/50 for 100d
        # Bits per subvector
        "nbits": 8,
        # Probed lists (must be large for high recall)
        "nprobes": [16, 32, 64, 128, 256],
    },
    # -------------------------------------------------
    # FAISS HNSW + PQ (graph + compression)
    # -------------------------------------------------
    "hnsw_pq": {
        # Graph degree
        "Ms": [16, 32, 64],
        # efConstruction = ef_c * M
        "ef_construction_factors": [8, 16, 32],
        # PQ subquantizers
        "pq_m": [8, 10, 16, 20, 32, 50],  # 8/16/32 for 128d, 10/20/50 for 100d
        # Bits per subvector
        "nbits": 8,
        # Search depth
        "efs": [64, 128, 256, 512],
    },
}


# -----------------------------
# FAISS Builders
# -----------------------------


def build_ivf_flat(data, metric, nlist):
    d = data.shape[1]
    quantizer = faiss.IndexFlatIP(d) if metric == "cosine" else faiss.IndexFlatL2(d)

    index = faiss.IndexIVFFlat(
        quantizer,
        d,
        nlist,
        faiss.METRIC_INNER_PRODUCT if metric == "cosine" else faiss.METRIC_L2,
    )

    t0 = time.perf_counter()
    index.train(data)
    index.add(data)
    return index, time.perf_counter() - t0


def build_ivf_pq(data, metric, nlist, m, nbits=8):
    d = data.shape[1]
    quantizer = faiss.IndexFlatIP(d) if metric == "cosine" else faiss.IndexFlatL2(d)

    index = faiss.IndexIVFPQ(
        quantizer,
        d,
        nlist,
        m,
        nbits,
        faiss.METRIC_INNER_PRODUCT if metric == "cosine" else faiss.METRIC_L2,
    )

    t0 = time.perf_counter()
    index.train(data)
    index.add(data)
    return index, time.perf_counter() - t0


def build_hnsw_index(data, metric, M, ef_construction_factor):
    d = data.shape[1]
    if metric == "cosine":
        index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
    else:
        index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_L2)

    index.hnsw.efConstruction = ef_construction_factor * M

    t0 = time.perf_counter()
    index.add(data)
    build_time = time.perf_counter() - t0

    return index, build_time


def build_hnsw_pq(data, metric, M, pq_m, ef_construction_factor, nbits=8):
    d = data.shape[1]
    index = faiss.IndexHNSWPQ(
        d,
        pq_m,
        M,
        nbits,
        faiss.METRIC_INNER_PRODUCT if metric == "cosine" else faiss.METRIC_L2,
    )

    index.hnsw.efConstruction = ef_construction_factor * M

    t0 = time.perf_counter()
    index.train(data)
    index.add(data)
    return index, time.perf_counter() - t0


# -----------------------------
# FAISS Core
# -----------------------------


def evaluate_faiss(index, queries, ground_truth, k_values, search_params):
    if hasattr(index, "hnsw") and "efSearch" in search_params:
        index.hnsw.efSearch = search_params["efSearch"]
    if hasattr(index, "nprobe") and "nprobe" in search_params:
        index.nprobe = search_params["nprobe"]

    max_k = max(k_values)

    latencies = []
    recalls = {k: [] for k in k_values}

    for i, q in enumerate(queries):
        t0 = time.perf_counter()
        _, ids = index.search(q.reshape(1, -1), max_k)
        latencies.append((time.perf_counter() - t0) * 1000)

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


def run_experiment(
    build_func,
    search_params,
    data,
    queries,
    ground_truth,
    k_values,
    index_path="faiss.index",
):
    # Cleanup before
    if os.path.exists(index_path):
        os.remove(index_path)

    index, build_time = build_func()

    # warmup
    t0 = time.time()
    index.search(queries[0].reshape(1, -1), k_values[0])
    warmup_time = time.time() - t0

    before = evaluate_faiss(index, queries, ground_truth, k_values, search_params)

    # Persist and Reload
    faiss.write_index(index, index_path)
    del index  # Force release

    t0 = time.time()
    index = faiss.read_index(index_path)
    open_time = time.time() - t0

    after = evaluate_faiss(index, queries, ground_truth, k_values, search_params)

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


def save_markdown(results, dataset_info, filename, algo):
    with open(filename, "w") as f:
        f.write(f"# FAISS {algo.upper()} Benchmark\n\n")

        if dataset_info:
            f.write("## Dataset Information\n\n")
            desc = DATASET_DESCRIPTIONS.get(dataset_info.get("Name"))
            if desc:
                f.write(desc.strip() + "\n\n")
            for key, value in dataset_info.items():
                f.write(f"- **{key}**: {value}\n")
            f.write("\n")

        f.write("**Note:**\n")
        f.write("- **Metric Equations**:\n")
        f.write("  - **Euclidean**: Similarity = $1 / (1 + d^2)$ (Higher is better)\n")
        f.write(
            "  - **Cosine**: Distance = $(1 - \\cos(\\theta)) / 2$ (Lower is better)\n"
        )

        # Group results by dataset_size
        dataset_sizes = []
        seen_dataset_sizes = set()
        for r in results:
            if r["dataset_size"] not in seen_dataset_sizes:
                dataset_sizes.append(r["dataset_size"])
                seen_dataset_sizes.add(r["dataset_size"])

        for size_name in dataset_sizes:
            size_results = [r for r in results if r["dataset_size"] == size_name]
            first_r = size_results[0]

            f.write(f"\n## dataset_size: {size_name}\n\n")
            f.write(f"- **Dimensions**: {first_r['dim']}\n")
            f.write(f"- **Vector Count**: {first_r['count']}\n")
            f.write(f"- **Queries**: {first_r['queries']}\n")
            f.write(f"- **Data Load Time**: {first_r['Load(s)']:.4f}s\n")
            f.write(f"- **Ground Truth Time**: {first_r['GT_Calc(s)']:.4f}s\n")
            f.write(f"- **Index Build Time**: {first_r['Index_Build(s)']:.4f}s\n")

            if "Total_Time" in first_r:
                f.write(
                    f"- **Total Time**: {first_r['Total_Time']/60:.2f} min ({first_r['Total_Time']:.2f}s)\n"
                )

            f.write("\n")

            # Get unique k values
            k_values = sorted(list(set(r["k"] for r in size_results)))

            # Determine columns based on algo
            base_cols = [
                "Recall (Before)",
                "Recall (After)",
                "Latency (ms) (Before)",
                "Latency (ms) (After)",
                "Build (s)",
                "Warmup (s)",
                "Open (s)",
            ]

            algo_cols = []
            if algo == "hnsw":
                algo_cols = ["M", "efConstruction", "efConstructionFactor", "efSearch"]
            elif algo == "ivf_flat":
                algo_cols = ["nlist", "nprobe"]
            elif algo == "ivf_pq":
                algo_cols = ["nlist", "m", "nbits", "nprobe"]
            elif algo == "hnsw_pq":
                algo_cols = [
                    "M",
                    "m",
                    "nbits",
                    "efConstruction",
                    "efConstructionFactor",
                    "efSearch",
                ]

            header = "| " + " | ".join(algo_cols + base_cols) + " |"
            separator = (
                "| " + " | ".join(["---"] * (len(algo_cols) + len(base_cols))) + " |"
            )

            for k in k_values:
                f.write(f"### k = {k}\n\n")
                f.write(header + "\n")
                f.write(separator + "\n")

                k_results = [r for r in size_results if r["k"] == k]
                for r in k_results:
                    row_vals = []
                    for col in algo_cols:
                        val = r.get(col, "-")
                        row_vals.append(str(val))

                    row_vals.append(f"{r['recall_before']:.4f}")
                    row_vals.append(f"{r['recall_after']:.4f}")
                    row_vals.append(f"{r['latency_before']:.2f}")
                    row_vals.append(f"{r['latency_after']:.2f}")
                    row_vals.append(f"{r['build_time']:.2f}")
                    row_vals.append(f"{r['warmup_time']:.4f}")
                    row_vals.append(f"{r['open_time']:.4f}")

                    f.write("| " + " | ".join(row_vals) + " |\n")
                f.write("\n")


# -----------------------------
# Main
# -----------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=DATASETS.keys())
    parser.add_argument(
        "--algo",
        required=True,
        choices=["hnsw", "ivf_flat", "ivf_pq", "hnsw_pq"],
        help="FAISS index type to benchmark",
    )
    parser.add_argument(
        "--dataset-size",
        choices=["tiny", "small", "medium", "full"],
        default="medium",
        help="Benchmark dataset_size size",
    )
    args = parser.parse_args()

    k_values = [10]

    all_dataset_sizes = {
        "tiny": (1_000, 10),
        "small": (10_000, 100),
        "medium": (100_000, 1_000),
        "full": (None, 10_000),
    }

    dataset_sizes = []
    if args.dataset_size:
        count, nq = all_dataset_sizes[args.dataset_size]
        dataset_sizes.append((args.dataset_size, count, nq))

    results = []
    output_file = f"benchmark_faiss_{args.dataset}_{args.algo}_{args.dataset_size}.md"

    dataset_info = {
        "Name": args.dataset,
        "Source": DATASETS[args.dataset],
        "Metric": DATASET_METRICS[args.dataset].capitalize(),
        "K Values": str(k_values),
        "Algorithm": args.algo,
    }

    algo = args.algo
    cfg = ALGO_CONFIGS[algo]

    for name, count, nq in dataset_sizes:
        if "dataset_sizes" in cfg and name not in cfg["dataset_sizes"]:
            continue

        print(f"--- dataset_size: {name} ---")
        print(f"Loading data for {args.dataset}...")

        start_load = time.perf_counter()
        data, queries, gt, dim = load_ann_data(
            args.dataset,
            count=count if count else 10**9,
            num_queries=nq,
            k_values=k_values,
        )
        load_time = time.perf_counter() - start_load

        actual_count = len(data)

        gt_time = 0
        if gt is None:
            start_gt = time.perf_counter()
            gt = compute_ground_truth(
                data,
                queries,
                k_values,
                DATASET_METRICS[args.dataset],
            )
            gt_time = time.perf_counter() - start_gt

        print(f"Data loaded. Train: {data.shape}, Queries: {queries.shape}")

        start_dataset_size = time.perf_counter()
        first_build_time = 0
        is_first = True

        metric = DATASET_METRICS[args.dataset]

        # Dispatch logic
        experiments = []

        if algo == "hnsw":
            for M in cfg["Ms"]:
                for ef_c in cfg["ef_construction_factors"]:
                    for ef in cfg["efs"]:
                        experiments.append(
                            (
                                {"M": M, "ef_construction_factor": ef_c},
                                {"efSearch": ef},
                                {
                                    "M": M,
                                    "efConstruction": ef_c * M,
                                    "efConstructionFactor": ef_c,
                                    "efSearch": ef,
                                },
                            )
                        )

        elif algo == "ivf_flat":
            for nlist in cfg["nlists"]:
                if nlist > actual_count // 40:
                    continue
                for nprobe in cfg["nprobes"]:
                    if nprobe > nlist:
                        continue
                    experiments.append(
                        (
                            {"nlist": nlist},
                            {"nprobe": nprobe},
                            {"nlist": nlist, "nprobe": nprobe},
                        )
                    )

        elif algo == "ivf_pq":
            for nlist in cfg["nlists"]:
                if nlist > actual_count // 40:
                    continue
                for m in cfg["pq_m"]:
                    if dim % m != 0:
                        continue
                    for nprobe in cfg["nprobes"]:
                        if nprobe > nlist:
                            continue
                        experiments.append(
                            (
                                {"nlist": nlist, "m": m, "nbits": cfg["nbits"]},
                                {"nprobe": nprobe},
                                {
                                    "nlist": nlist,
                                    "m": m,
                                    "nbits": cfg["nbits"],
                                    "nprobe": nprobe,
                                },
                            )
                        )

        elif algo == "hnsw_pq":
            for M in cfg["Ms"]:
                for ef_c in cfg["ef_construction_factors"]:
                    for m in cfg["pq_m"]:
                        if dim % m != 0:
                            continue
                        for ef in cfg["efs"]:
                            experiments.append(
                                (
                                    {
                                        "M": M,
                                        "pq_m": m,
                                        "ef_construction_factor": ef_c,
                                        "nbits": cfg["nbits"],
                                    },
                                    {"efSearch": ef},
                                    {
                                        "M": M,
                                        "m": m,
                                        "nbits": cfg["nbits"],
                                        "efConstruction": ef_c * M,
                                        "efConstructionFactor": ef_c,
                                        "efSearch": ef,
                                    },
                                )
                            )

        # Group experiments by build configuration to avoid rebuilding
        grouped_experiments = {}
        for build_kwargs, search_params, log_params in experiments:
            # Create a hashable key for build_kwargs
            build_key = tuple(sorted(build_kwargs.items()))
            if build_key not in grouped_experiments:
                grouped_experiments[build_key] = {
                    "build_kwargs": build_kwargs,
                    "searches": [],
                }
            grouped_experiments[build_key]["searches"].append(
                (search_params, log_params)
            )

        total_builds = len(grouped_experiments)
        current_build_idx = 0

        for build_key, group in grouped_experiments.items():
            current_build_idx += 1
            build_kwargs = group["build_kwargs"]
            searches = group["searches"]

            print(
                f"  [{current_build_idx}/{total_builds}] Building index: {build_kwargs}"
            )

            # Build index
            try:
                if algo == "hnsw":
                    index, build_time = build_hnsw_index(data, metric, **build_kwargs)
                elif algo == "ivf_flat":
                    index, build_time = build_ivf_flat(data, metric, **build_kwargs)
                elif algo == "ivf_pq":
                    index, build_time = build_ivf_pq(data, metric, **build_kwargs)
                elif algo == "hnsw_pq":
                    index, build_time = build_hnsw_pq(data, metric, **build_kwargs)
            except Exception as e:
                print(f"Build failed: {e}")
                continue

            # Warmup
            t0 = time.perf_counter()
            index.search(queries[0].reshape(1, -1), k_values[0])
            warmup_time = time.perf_counter() - t0

            if is_first:
                first_build_time = build_time
                is_first = False

            # Persist and Reload
            index_path = f"faiss_{args.dataset}_size_{name}_{algo}.index"
            if os.path.exists(index_path):
                os.remove(index_path)

            faiss.write_index(index, index_path)

            t0 = time.perf_counter()
            reloaded_index = faiss.read_index(index_path)
            open_time = time.perf_counter() - t0

            # Run searches
            for search_params, log_params in searches:
                print(f"    Searching with {search_params}...")

                metrics_before = evaluate_faiss(
                    index, queries, gt, k_values, search_params
                )
                metrics_after = evaluate_faiss(
                    reloaded_index, queries, gt, k_values, search_params
                )

                for k in k_values:
                    results.append(
                        {
                            "dataset_size": name,
                            "dim": dim,
                            "count": actual_count,
                            "queries": len(queries),
                            "Load(s)": load_time,
                            "GT_Calc(s)": gt_time,
                            "Index_Build(s)": build_time,
                            "k": k,
                            **log_params,
                            "recall_before": metrics_before[k]["recall"],
                            "recall_after": metrics_after[k]["recall"],
                            "latency_before": metrics_before[k]["latency"],
                            "latency_after": metrics_after[k]["latency"],
                            "build_time": build_time,
                            "warmup_time": warmup_time,
                            "open_time": open_time,
                        }
                    )

            save_markdown(results, dataset_info, output_file, algo)

            # Clean up index to free memory
            del index
            del reloaded_index
            if os.path.exists(index_path):
                os.remove(index_path)

        total_time = time.perf_counter() - start_dataset_size
        for r in results:
            if r["dataset_size"] == name:
                r["Total_Time"] = total_time

        save_markdown(results, dataset_info, output_file, algo)

    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    faiss.omp_set_num_threads(1)
    main()
