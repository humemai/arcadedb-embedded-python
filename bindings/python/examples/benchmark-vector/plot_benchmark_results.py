import glob
import os
import re

import matplotlib.pyplot as plt
import pandas as pd

# Set larger font sizes for all plot elements
plt.rcParams.update(
    {
        "font.size": 14,
        "axes.titlesize": 18,
        "axes.labelsize": 16,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 12,
        "figure.titlesize": 20,
    }
)

RESULTS_DIR = "results"
LOGS_DIR = "benchmark_logs"
FIGURES_DIR = "figures"

if not os.path.exists(FIGURES_DIR):
    os.makedirs(FIGURES_DIR)

DATASETS = {
    "sift-128-euclidean": "SIFT-128-Euclidean",
    "glove-100-angular": "GloVe-100-Angular",
}

ALGORITHMS = {
    "jvector": "JVector",
    "faiss_hnsw": "FAISS HNSW Flat",
    "faiss_ivf_flat": "FAISS IVF Flat",
    "faiss_ivf_pq": "FAISS IVF PQ",
    "faiss_hnsw_pq": "FAISS HNSW PQ",
}


def parse_markdown_table(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find the table
    table_lines = [line.strip() for line in lines if line.strip().startswith("|")]

    if not table_lines:
        return pd.DataFrame()

    # Parse header
    header = [c.strip() for c in table_lines[0].strip("|").split("|")]

    # Parse rows
    data = []
    for line in table_lines[2:]:  # Skip header and separator
        values = [c.strip() for c in line.strip("|").split("|")]
        if len(values) != len(header):
            continue
        row = dict(zip(header, values))
        data.append(row)

    df = pd.DataFrame(data)

    # Convert numeric columns
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except ValueError:
            pass

    return df


def get_peak_memory(log_file):
    if not os.path.exists(log_file):
        return None
    try:
        df = pd.read_csv(log_file)
        return df["RSS_MB"].max()
    except Exception as e:
        print(f"Error reading log file {log_file}: {e}")
        return None


def plot_dataset(dataset_key, dataset_name):
    plt.figure(figsize=(12, 8))

    # Find all result files for this dataset
    # Pattern: benchmark_{algo}_{dataset}_{params}.md
    # But the filenames are like: benchmark_jvector_sift-128-euclidean_size_full.md
    # benchmark_faiss_sift-128-euclidean_hnsw_full.md

    # We need to map filename patterns to algorithms

    files = glob.glob(os.path.join(RESULTS_DIR, f"*{dataset_key}*.md"))

    colors = plt.cm.tab10.colors

    plot_data = []

    for file_path in files:
        filename = os.path.basename(file_path)

        # Determine algorithm
        algo_name = "Unknown"
        is_jvector = False

        if "jvector" in filename:
            algo_name = "JVector"
            is_jvector = True
            log_pattern = f"jvector-*-full_*_memory.log"  # Simplified pattern matching
            # Need to be more specific to match dataset
            if "euclidean" in dataset_key:
                log_pattern = "jvector-euclidean-full_*_memory.log"
            else:
                log_pattern = "jvector-angular-full_*_memory.log"

        elif "faiss" in filename:
            dataset_type = "euclidean" if "euclidean" in dataset_key else "angular"

            if "hnsw_pq" in filename:
                algo_name = "FAISS HNSW PQ"
                log_pattern = f"faiss-{dataset_type}-hnsw_pq-full_*_memory.log"
            elif "ivf_pq" in filename:
                algo_name = "FAISS IVF PQ"
                log_pattern = f"faiss-{dataset_type}-ivf_pq-full_*_memory.log"
            elif "ivf_flat" in filename:
                algo_name = "FAISS IVF Flat"
                log_pattern = f"faiss-{dataset_type}-ivf_flat-full_*_memory.log"
            elif "hnsw" in filename:  # Check this last as hnsw_pq contains hnsw
                algo_name = "FAISS HNSW Flat"
                log_pattern = f"faiss-{dataset_type}-hnsw-full_*_memory.log"

        df = parse_markdown_table(file_path)
        if df.empty:
            continue

        # Get Peak Memory
        log_files = glob.glob(os.path.join(LOGS_DIR, log_pattern))
        peak_mem = "N/A"
        if log_files:
            # Pick the most recent one or just the first one
            log_file = sorted(log_files)[-1]
            mem = get_peak_memory(log_file)
            if mem:
                peak_mem = f"{mem:.0f} MB"

        # Calculate Build Time
        # For JVector: Build + Warmup (Before)
        # For FAISS: Build
        # We take the mean build time if there are multiple rows, or just the first one
        # since build time is per index Actually, build time is constant for the same
        # build parameters. But here we might have different build parameters in the
        # same file (e.g. JVector has max_connections, beam_width). So Build Time
        # varies. We can't put a single Build Time in the legend if it varies. Let's
        # check if it varies significantly. For FAISS HNSW, Build Time depends on M and
        # efConstruction. So it varies. So we can't put it in the legend easily unless
        # we average it or show a range. Or maybe just "Avg Build: ...".

        if is_jvector:
            df["Total Build"] = 0.0
            if "Build (s)" in df.columns:
                df["Total Build"] += df["Build (s)"]
            if "Warmup (s) (Before)" in df.columns:
                df["Total Build"] += df["Warmup (s) (Before)"]
        else:
            df["Total Build"] = 0.0
            if "Build (s)" in df.columns:
                df["Total Build"] += df["Build (s)"]

        avg_build = df["Total Build"].mean()
        build_str = f"{avg_build:.1f}s"

        # Prepare data for plotting
        # We want the Pareto frontier (best recall for given latency or best latency for
        # given recall)
        # But simply plotting all points is also fine to see the spread.
        # Usually benchmarks plot the line connecting the best points.

        # Sort by Recall
        df = df.sort_values(by="Recall (Before)")

        recall = df["Recall (Before)"]
        latency = df["Latency (ms) (Before)"]

        # Filter out very bad points if necessary, but let's plot all first.

        label = f"{algo_name} (Mem: {peak_mem}, Build: ~{build_str})"

        print(f"  {algo_name}: Peak Mem={peak_mem}, Avg Build={build_str}")

        plot_data.append(
            {
                "recall": recall,
                "latency": latency,
                "label": label,
                "avg_build": avg_build,
            }
        )

    # Sort by avg_build descending
    plot_data.sort(key=lambda x: x["avg_build"], reverse=True)

    for data in plot_data:
        # Plot points
        plt.plot(
            data["recall"],
            data["latency"],
            "o",
            label=data["label"],
            markersize=8,
            alpha=0.7,
        )

    # Add dashed lines for Recall
    for r in [0.80, 0.85, 0.90, 0.95]:
        plt.axvline(x=r, color="gray", linestyle="--", alpha=0.5)
        plt.text(
            r, plt.ylim()[1] * 0.01, f"{r}", rotation=90, verticalalignment="bottom"
        )

    plt.title(f"Recall vs Latency - {dataset_name} Dataset")
    plt.xlabel("Recall@10 (Higher is Better)")
    plt.ylabel("Latency (ms) (Lower is Better)")
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.legend()
    plt.yscale("log")  # Latency often spans orders of magnitude

    # Save plot
    output_png = os.path.join(FIGURES_DIR, f"plot_{dataset_key}.png")
    output_pdf = os.path.join(FIGURES_DIR, f"plot_{dataset_key}.pdf")
    plt.savefig(output_png)
    plt.savefig(output_pdf)
    print(f"Saved plots to {output_png} and {output_pdf}")


def main():
    for key, name in DATASETS.items():
        print(f"Processing {name} dataset...")
        plot_dataset(key, name)


if __name__ == "__main__":
    main()
