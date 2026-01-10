#!/usr/bin/env python3
"""
Plot parameter sweep results from sweep_results_* directories.

Shows the impact of location cache size and graph build cache size
on recall, latency, and memory usage.
"""

import argparse
import glob
import os
import re

import matplotlib.patheffects
import matplotlib.pyplot as plt
import pandas as pd

# Set larger font sizes for all plot elements
plt.rcParams.update(
    {
        "font.size": 20,
        "axes.titlesize": 24,
        "axes.labelsize": 22,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "legend.fontsize": 18,
        "figure.titlesize": 28,
    }
)


def format_memory(mb):
    """Format memory in MB/GB with friendly units."""
    if mb is None:
        return "n/a"
    if mb >= 1024:
        gb = mb / 1024
        return f"{gb:.2f} GB" if gb < 10 else f"{gb:.1f} GB"
    if mb >= 100:
        return f"{mb:.0f} MB"
    if mb >= 10:
        return f"{mb:.1f} MB"
    return f"{mb:.2f} MB"


def format_duration_seconds(sec):
    """Format a duration given in seconds using ms/s/min/h rules."""
    if sec is None:
        return "n/a"
    if sec < 1:
        return f"{sec * 1000:.0f} ms"
    if sec < 60:
        return f"{sec:.2f} s"
    if sec < 3600:
        return f"{sec / 60:.1f} min"
    return f"{sec / 3600:.2f} h"


def format_duration_ms(ms):
    """Format a duration given in milliseconds using ms/s/min/h rules."""
    if ms is None:
        return "n/a"
    if ms < 1000:
        return f"{ms:.1f} ms"
    sec = ms / 1000
    if sec < 60:
        return f"{sec:.2f} s"
    if sec < 3600:
        return f"{sec / 60:.1f} min"
    return f"{sec / 3600:.2f} h"


def parse_markdown_table(file_path):
    """Parse markdown table from benchmark results."""
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
    """Extract peak memory from memory log file."""
    if not os.path.exists(log_file):
        return None
    try:
        df = pd.read_csv(log_file)
        return df["RSS_MB"].max()
    except Exception as e:
        print(f"Warning: Error reading log file {log_file}: {e}")
        return None


def parse_config_from_filename(filename):
    """Extract configuration from filename.

    Example with explicit key=value format: benchmark_dataset=glove-100-angular_size=tiny_xmx=16g_loccache=500000_graphcache=50000_mutations=200_quant=NONE_store=OFF.md
    Also supports old formats for backward compatibility.
    Returns dict with parsed values.
    """
    # Try new explicit key=value format
    match = re.search(
        r"benchmark_dataset=(.+?)_size=([a-zA-Z0-9]+)_xmx=(\w+)_loccache=(-?\d+)_graphcache=(\d+)_mutations=(\d+)_quant=([a-zA-Z0-9]+)_store=(ON|OFF)",
        filename,
    )
    if match:
        return {
            "dataset_name": match.group(1),
            "dataset_size": match.group(2),
            "heap": match.group(3),
            "location_cache": int(match.group(4)),
            "graph_cache": int(match.group(5)),
            "mutations": int(match.group(6)),
            "quantization": match.group(7),
            "store_vectors": match.group(8) == "ON",
        }

    # Try fully detailed old format with quant and store
    match = re.search(
        r"benchmark_jvector_(.+?)_size_([a-zA-Z0-9]+)_xmx(\w+)_loc(-?\d+)_graph(\d+)_mut(\d+)(?:_quant([a-zA-Z0-9]+))?(?:_(storeVectors))?",
        filename,
    )
    if match:
        return {
            "dataset_name": match.group(1),
            "dataset_size": match.group(2),
            "heap": match.group(3),
            "location_cache": int(match.group(4)),
            "graph_cache": int(match.group(5)),
            "mutations": int(match.group(6)),
            "quantization": match.group(7) if match.group(7) else "NONE",
            "store_vectors": True if match.group(8) else False,
        }

    # Try old format without mutations (backward compatibility)
    match = re.search(r"benchmark_jvector_(.+?)_size_([a-zA-Z0-9]+)$", filename)
    if match:
        return {
            "dataset_name": match.group(1),
            "dataset_size": match.group(2),
            "heap": None,
            "location_cache": None,
            "graph_cache": None,
            "mutations": 100,
            "quantization": "NONE",
            "store_vectors": False,
        }

    return None


def plot_location_cache_sweep(sweep_dir, output_dir):
    """Plot results for location cache size sweep (fixed graph cache)."""
    print("\nProcessing location cache sweep...")

    # We now have multiple files due to quantization variations.
    # Let's filter for standard config: NONE quant, Store OFF
    # Or iterate through all combinations if desired.
    # For simplicity, we plot the "Standard" config (Quant=NONE, Store=False)

    # Support both old (benchmark_jvector_*) and new (benchmark_dataset=*) naming formats
    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*.md"))
    md_files += glob.glob(os.path.join(sweep_dir, "benchmark_dataset=*.md"))

    # Organize data by configuration key (quant, store)
    configs = {}

    for md_file in md_files:
        filename = os.path.basename(md_file)
        config = parse_config_from_filename(filename)
        if not config:
            continue

        key = (
            config["quantization"],
            config["store_vectors"],
            config["dataset_name"],
            config["dataset_size"],
        )
        if key not in configs:
            configs[key] = []

        # Only take files matching our target fixed graph cache criterion for this specific plot type
        # In the original code, this was hardcoded to graph50000.
        # We need to ensure we are comparing apples to apples.
        if (
            config["graph_cache"] != 50000
            and config["dataset_size"] != "tiny"
            and config["graph_cache"] != 500
        ):  # Heuristic adjustment
            # Let's just filter later
            pass

        configs[key].append((md_file, config))

    # Generate plots for each variation
    for (quant, store, dataset_name, dataset_size), files in configs.items():
        store_lbl = "ON" if store else "OFF"
        suffix_label = f"Dataset={dataset_name}, Size={dataset_size}, Quant={quant}, Store={store_lbl}"
        file_suffix = f"_dataset={dataset_name}_size={dataset_size}_quant={quant}_store={store_lbl}"

        # Filter for the specific graph cache size used in the original sweep logic
        # Original logic: glob.glob("...graph50000.md").
        # We need to be adaptive based on dataset size likely found in the file
        target_files = []
        for f, c in files:
            # We want to vary Location Cache, fixing everything else.
            # We fix graph cache to a 'reasonable' value present in the sweep.
            # 50000 was used for medium/full. For tiny it was 500. For small it was 3000.
            # Let's dynamically pick the middle graph cache value if possible, or just plot all data points found.
            # Easier: Just stick to the original filter if applicable, or skip if empty.
            if c["graph_cache"] in [
                500,
                3000,
                10000,
                50000,
            ]:  # Common "medium" settings
                target_files.append((f, c))

        if not target_files:
            continue

        print(f"  Generating plot for {suffix_label}...")

        sweep_data = []
        for md_file, config in target_files:
            df = parse_markdown_table(md_file)
            if df.empty:
                continue

            # Find log file
            heap_str = config["heap"] if config["heap"] else "*"
            dataset_size_label = config["dataset_size"]

            # Construct log pattern matching the new complex naming
            # RUN_NAME="dataset=${DATASET}_size=${DATASET_SIZE}_heap=${HEAP}_loccache=${LOCATION_CACHE}_graphcache=${GRAPH_BUILD_CACHE}_quant=${QUANTIZATION}_store=${STORE_VECTORS}"
            store_str = "ON" if config["store_vectors"] else "OFF"

            # Use * for dataset part as config doesn't have it explicitly as a key sometimes (parsed from filename),
            # but we can assume we match the one we are processing.

            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-dataset=*{dataset_name}*_size={dataset_size_label}_heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_quant={config['quantization']}_store={store_str}_*_memory.log",
            )

            log_files = sorted(glob.glob(log_pattern))

            # Fallback to old patterns if needed
            if not log_files:
                log_pattern = os.path.join(
                    sweep_dir,
                    "benchmark_logs",
                    f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_{config['quantization']}_store{store_str}_*_duration.txt",
                ).replace("_duration.txt", "_memory.log")
                log_files = sorted(glob.glob(log_pattern))
            peak_mem = None
            if log_files:
                peak_mem = get_peak_memory(log_files[-1])

            build_time = 0
            if "Build (s)" in df.columns:
                build_time = df["Build (s)"].mean()

            sweep_data.append(
                {
                    "location_cache": config["location_cache"],
                    "graph_cache": config["graph_cache"],
                    "df": df,
                    "peak_memory": peak_mem,
                    "build_time": build_time,
                }
            )

        if not sweep_data:
            continue

        # Sort and Plot logic (reused)
        sweep_data.sort(
            key=lambda x: (
                x["location_cache"] if x["location_cache"] != -1 else float("inf")
            )
        )

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        cache_sizes = []
        peak_memories = []
        build_times = []
        labels = []

        for data in sweep_data:
            loc_cache = data["location_cache"]
            peak_mem = data["peak_memory"]
            build_time = data["build_time"]

            label = f"{loc_cache:,}" if loc_cache != -1 else "Unlimited"
            # Avoid duplicates in labels if multiple graph sizes slipped in
            if label in labels:
                continue

            labels.append(label)
            cache_sizes.append(loc_cache if loc_cache != -1 else 1500000)
            peak_memories.append(peak_mem if peak_mem else 0)
            build_times.append(build_time)

        # Skip empty plots
        if not labels:
            plt.close()
            continue

        x_pos = range(len(labels))
        colors = plt.cm.viridis(
            [i / max(1, (len(labels) - 1)) for i in range(len(labels))]
        )

        # Plot 1: Memory
        bars1 = ax1.bar(x_pos, peak_memories, color=colors, alpha=0.7)
        ax1.set_title(f"Peak Memory ({suffix_label})")
        ax1.set_xlabel("Location Cache Size")
        ax1.set_ylabel("Peak Memory (MB)")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(labels, rotation=45, ha="right")
        ax1.grid(True, axis="y", alpha=0.2)

        for bar, val in zip(bars1, peak_memories):
            if val > 0:
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    val,
                    format_memory(val),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        # Plot 2: Build Time
        bars2 = ax2.bar(x_pos, build_times, color=colors, alpha=0.7)
        ax2.set_title(f"Build Time ({suffix_label})")
        ax2.set_xlabel("Location Cache Size")
        ax2.set_ylabel("Seconds")
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(labels, rotation=45, ha="right")
        ax2.grid(True, axis="y", alpha=0.2)

        for bar, val in zip(bars2, build_times):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                val,
                f"{val:.1f}s",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        plt.suptitle(f"Location Cache Impact ({suffix_label})", fontsize=16)
        plt.tight_layout()

        # Save with suffix
        output_prefix = os.path.join(output_dir, f"plot_sweep_loccache{file_suffix}")
        plt.savefig(f"{output_prefix}.pdf", bbox_inches="tight")
        print(f"  Saved: {output_prefix}.pdf")
        plt.close()


def plot_graph_cache_sweep(sweep_dir, output_dir):
    """Plot results for graph build cache size sweep (fixed location cache)."""
    print("\nProcessing graph cache sweep...")

    # Support both old (benchmark_jvector_*) and new (benchmark_dataset=*) naming formats
    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*.md"))
    md_files += glob.glob(os.path.join(sweep_dir, "benchmark_dataset=*.md"))

    # Organize data by configuration key (quant, store)
    configs = {}

    for md_file in md_files:
        filename = os.path.basename(md_file)
        config = parse_config_from_filename(filename)
        if not config:
            continue

        key = (
            config["quantization"],
            config["store_vectors"],
            config["dataset_name"],
            config["dataset_size"],
        )
        if key not in configs:
            configs[key] = []

        # Only take files matching our target fixed location cache criterion
        # Fixed Loc=500,000 was used in original script.
        # But for 'tiny' usually loc=1000 is max.
        # We can try to be smart or just filter for the fixed value used in script (500000)
        # Original: glob.glob("benchmark_jvector_*_loc500000_graph*.md")
        # Let's keep logic simple: If loc_cache is 500000 OR (tiny/small and loc_cache is their max)

        if config["location_cache"] == 500000:
            configs[key].append((md_file, config))
        # Additional heuristics for smaller datasets where 500k is overkill/not present?
        # For tiny/small, reasonable fixed loc might be 1000 or 10000.
        # But let's stick to the original script logic which looked for 500000.
        # If that excludes tiny/small, so be it (original script did too effectively).

    if not configs:
        print("  No graph cache sweep files found matching loc=500000")
        # Fallback: try different fixed location sizes?
        # Let's just proceed with what we have.

    for (quant, store, dataset_name, dataset_size), files in configs.items():
        store_lbl = "ON" if store else "OFF"
        suffix_label = f"Dataset={dataset_name}, Size={dataset_size}, Quant={quant}, Store={store_lbl}"
        file_suffix = f"_dataset={dataset_name}_size={dataset_size}_quant={quant}_store={store_lbl}"

        print(f"  Generating graph cache plot for {suffix_label}...")

        sweep_data = []
        for md_file, config in files:
            df = parse_markdown_table(md_file)
            if df.empty:
                continue

            build_time = 0
            if "Build (s)" in df.columns:
                build_time = df["Build (s)"].mean()

            heap_str = config["heap"] if config["heap"] else "*"
            dataset_size_label = config["dataset_size"]
            store_str = "ON" if config["store_vectors"] else "OFF"

            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-dataset=*{dataset_name}*_size={dataset_size_label}_heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_quant={config['quantization']}_store={store_str}_*_memory.log",
            )
            log_files = sorted(glob.glob(log_pattern))

            if not log_files:
                log_pattern = os.path.join(
                    sweep_dir,
                    "benchmark_logs",
                    f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_{config['quantization']}_store{store_str}_*_memory.log",
                )
                log_files = sorted(glob.glob(log_pattern))
            if log_files:
                peak_mem = get_peak_memory(log_files[-1])

            sweep_data.append(
                {
                    "location_cache": config["location_cache"],
                    "graph_cache": config["graph_cache"],
                    "df": df,
                    "build_time": build_time,
                    "peak_memory": peak_mem,
                }
            )

        if not sweep_data:
            continue

        # Sort by graph cache size
        sweep_data.sort(key=lambda x: x["graph_cache"])

        # Plot: Build time and Memory usage
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        graph_cache_sizes = []
        build_times = []
        peak_memories = []
        labels = []

        for data in sweep_data:
            graph_cache = data["graph_cache"]
            build_time = data["build_time"]
            peak_mem = data["peak_memory"]

            label = f"{graph_cache:,}"
            # Deduplicate labels
            if label in labels:
                continue

            labels.append(label)
            graph_cache_sizes.append(graph_cache)
            build_times.append(build_time)
            peak_memories.append(peak_mem if peak_mem else 0)

        if not labels:
            plt.close()
            continue

        x_pos = range(len(labels))
        colors = plt.cm.plasma(
            [i / max(1, (len(labels) - 1)) for i in range(len(labels))]
        )

        # Plot 1: Build time
        bars1 = ax1.bar(x_pos, build_times, color=colors, alpha=0.7)
        ax1.set_title(f"Build Time ({suffix_label})")
        ax1.set_xlabel("Graph Cache Size")
        ax1.set_ylabel("Seconds")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(labels, rotation=45, ha="right")
        ax1.grid(True, axis="y", alpha=0.2)

        for bar, val in zip(bars1, build_times):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                val,
                f"{val:.1f}s",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        # Plot 2: Memory usage
        bars2 = ax2.bar(x_pos, peak_memories, color=colors, alpha=0.7)
        ax2.set_title(f"Peak Memory ({suffix_label})")
        ax2.set_xlabel("Graph Cache Size")
        ax2.set_ylabel("MB")
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(labels, rotation=45, ha="right")
        ax2.grid(True, axis="y", alpha=0.2)

        for bar, val in zip(bars2, peak_memories):
            if val > 0:
                ax2.text(
                    bar.get_x() + bar.get_width() / 2,
                    val,
                    format_memory(val),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        plt.suptitle(f"Graph Cache Impact (Loc: 500K) - {suffix_label}", fontsize=16)
        plt.tight_layout()

        # Save
        output_prefix = os.path.join(output_dir, f"plot_sweep_graphcache{file_suffix}")
        plt.savefig(f"{output_prefix}.pdf", bbox_inches="tight")
        print(f"  Saved: {output_prefix}.pdf")
        plt.close()


def verify_consistency(sweep_dir):
    """Verify that recall and latency are consistent across cache configurations."""
    print("\n" + "=" * 70)
    print("VERIFYING RECALL/LATENCY CONSISTENCY ACROSS CACHE CONFIGURATIONS")
    print("=" * 70)

    # Location cache sweep verification
    print("\n1. Location Cache Sweep (fixed graph cache = 50K):")
    # Support both old and new naming formats
    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*_graph50000.md"))
    md_files += glob.glob(
        os.path.join(sweep_dir, "benchmark_dataset=*_graphcache=50000*.md")
    )

    if md_files:
        sweep_data = []
        for md_file in md_files:
            filename = os.path.basename(md_file)
            config = parse_config_from_filename(filename)
            if not config:
                continue
            df = parse_markdown_table(md_file)
            if df.empty:
                continue
            sweep_data.append({"location_cache": config["location_cache"], "df": df})

        if sweep_data:
            sweep_data.sort(
                key=lambda x: (
                    x["location_cache"] if x["location_cache"] != -1 else float("inf")
                )
            )
            ref_data = sweep_data[len(sweep_data) // 2]
            ref_df = ref_data["df"]

            for data in sweep_data:
                if data == ref_data:
                    continue
                df = data["df"]
                if len(df) == len(ref_df):
                    recall_diff = abs(
                        df["Recall (After)"].values - ref_df["Recall (After)"].values
                    ).max()
                    latency_diff = abs(
                        df["Latency (ms) (After)"].values
                        - ref_df["Latency (ms) (After)"].values
                    ).max()
                    cache_label = (
                        f"{data['location_cache']:,}"
                        if data["location_cache"] != -1
                        else "Unlimited"
                    )
                    print(
                        f"   Cache {cache_label:>12}: Max recall diff={recall_diff:.4f}, Max latency diff={latency_diff:.2f}ms"
                    )

    # Graph cache sweep verification
    print("\n2. Graph Cache Sweep (fixed location cache = 500K):")
    # Support both old and new naming formats
    md_files = glob.glob(
        os.path.join(sweep_dir, "benchmark_jvector_*_loc500000_graph*.md")
    )
    md_files += glob.glob(
        os.path.join(sweep_dir, "benchmark_dataset=*_loccache=500000_graphcache=*.md")
    )

    if md_files:
        sweep_data = []
        for md_file in md_files:
            filename = os.path.basename(md_file)
            config = parse_config_from_filename(filename)
            if not config:
                continue
            df = parse_markdown_table(md_file)
            if df.empty:
                continue
            sweep_data.append({"graph_cache": config["graph_cache"], "df": df})

        if sweep_data:
            sweep_data.sort(key=lambda x: x["graph_cache"])
            ref_data = sweep_data[len(sweep_data) // 2]
            ref_df = ref_data["df"]

            for data in sweep_data:
                if data == ref_data:
                    continue
                df = data["df"]
                if len(df) == len(ref_df):
                    recall_diff = abs(
                        df["Recall (After)"].values - ref_df["Recall (After)"].values
                    ).max()
                    latency_diff = abs(
                        df["Latency (ms) (After)"].values
                        - ref_df["Latency (ms) (After)"].values
                    ).max()
                    print(
                        f"   Graph Cache {data['graph_cache']:>8,}: Max recall diff={recall_diff:.4f}, Max latency diff={latency_diff:.2f}ms"
                    )

    print("\n" + "=" * 70 + "\n")


def plot_memory_summary(sweep_dir, output_dir):
    """Plot comprehensive summary: memory, latency, duration, and recall."""
    print("\nGenerating comprehensive metric plots...")

    DATASET_COUNTS = {
        "tiny": "1K",
        "small": "10K",
        "medium": "100K",
        "full": "~1.2M",
    }

    # Support both old (benchmark_jvector_*) and new (benchmark_dataset=*) naming formats
    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*.md"))
    md_files += glob.glob(os.path.join(sweep_dir, "benchmark_dataset=*.md"))
    if not md_files:
        print("  No benchmark files found")
        return

    data_points = []

    # We will gather all data, then group by (dataset_size, quant, store)

    for md_file in md_files:
        filename = os.path.basename(md_file)
        config = parse_config_from_filename(filename)
        if not config:
            continue

        # Parse benchmark results for recall and latency
        df = parse_markdown_table(md_file)
        if df.empty:
            continue

        # Get average recall and latency (both before and after)
        avg_recall_before = (
            df["Recall (Before)"].mean() if "Recall (Before)" in df.columns else None
        )
        avg_recall_after = (
            df["Recall (After)"].mean() if "Recall (After)" in df.columns else None
        )
        avg_latency_before = (
            df["Latency (ms) (Before)"].mean()
            if "Latency (ms) (Before)" in df.columns
            else None
        )
        avg_latency_after = (
            df["Latency (ms) (After)"].mean()
            if "Latency (ms) (After)" in df.columns
            else None
        )

        # Find memory log using cache parameters
        # Extract heap size from config for pattern matching
        heap_str = config["heap"] if config["heap"] else "*"
        dataset_size_label = config["dataset_size"]
        store_str = "ON" if config["store_vectors"] else "OFF"

        # Try new naming format first: jvector-dataset=..._size=...
        # Must match run_all_sweeps.sh RUN_NAME structure which now uses xmx= and includes mutations=
        mutations_str = str(config.get("mutations", 100))

        log_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"jvector-dataset=*{config['dataset_name']}*_size={dataset_size_label}_xmx={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_mutations={mutations_str}_quant={config['quantization']}_store={store_str}_*_memory.log",
        )
        log_files = sorted(glob.glob(log_pattern))

        if not log_files:
            # Try without mutations (older runs) but with xmx (if changed recently) or heap
            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-dataset=*{config['dataset_name']}*_size={dataset_size_label}_heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_quant={config['quantization']}_store={store_str}_*_memory.log",
            )
            log_files = sorted(glob.glob(log_pattern))

        if not log_files:
            # Fallback to older new format: jvector-heap=1g_loccache=100_graphcache=200_size=tiny_quant=NONE_store=OFF_*_memory.log
            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_size={dataset_size_label}_quant={config['quantization']}_store={store_str}_*_memory.log",
            )
            log_files = sorted(glob.glob(log_pattern))

        # Fallback to old naming format: *heap{heap}_loc{location}_graph{graph}_{dataset_size}_{quant}_store{store}_*_memory.log
        if not log_files:
            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_{config['quantization']}_store{store_str}_*_memory.log",
            )
            log_files = sorted(glob.glob(log_pattern))

        # Fallback logic for legacy file naming (without quant/store in filename)
        if (
            not log_files
            and config["quantization"] == "NONE"
            and not config["store_vectors"]
        ):
            log_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_*_memory.log",
            )
            log_files = sorted(glob.glob(log_pattern))

        if not log_files:
            continue

        peak_mem = get_peak_memory(log_files[-1])  # Take most recent
        if peak_mem is None:
            continue

        duration = None
        # Try to find duration log with same parameters
        # Try newest naming format first: jvector-dataset=... with xmx and mutations
        mutations_str = str(config.get("mutations", 100))

        duration_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"jvector-dataset={config['dataset_name']}_size={dataset_size_label}_xmx={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_mutations={mutations_str}_quant={config['quantization']}_store={store_str}_duration.txt",
        )
        duration_files = sorted(glob.glob(duration_pattern))

        if not duration_files:
            # Try without mutations and with heap=
            duration_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-dataset={config['dataset_name']}_size={dataset_size_label}_heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_quant={config['quantization']}_store={store_str}_duration.txt",
            )
            duration_files = sorted(glob.glob(duration_pattern))

        if not duration_files:
            # Try intermediate naming format: jvector-heap=...
            duration_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"jvector-heap={heap_str}_loccache={config['location_cache']}_graphcache={config['graph_cache']}_size={dataset_size_label}_quant={config['quantization']}_store={store_str}_duration.txt",
            )
            duration_files = sorted(glob.glob(duration_pattern))

        # Fallback to old naming format
        if not duration_files:
            duration_pattern = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_{config['quantization']}_store{store_str}_duration.txt",
            )
            duration_files = sorted(glob.glob(duration_pattern))

        if duration_files:
            try:
                with open(duration_files[-1], "r") as f:
                    duration = int(f.read().strip())
            except (ValueError, IOError):
                pass

        # Fallback for duration if using legacy naming
        if (
            duration is None
            and config["quantization"] == "NONE"
            and not config["store_vectors"]
        ):
            legacy_duration = os.path.join(
                sweep_dir,
                "benchmark_logs",
                f"*heap{heap_str}_loc{config['location_cache']}_graph{config['graph_cache']}_{dataset_size_label}_duration.txt",
            )
            duration_files = sorted(glob.glob(legacy_duration))
            if duration_files:
                try:
                    with open(duration_files[-1], "r") as f:
                        duration = int(f.read().strip())
                except (ValueError, IOError):
                    pass

        data_points.append(
            {
                "dataset_name": config["dataset_name"],
                "dataset_size": config["dataset_size"],
                "loc": config["location_cache"],
                "graph": config["graph_cache"],
                "mem": peak_mem,
                "duration": duration,
                "recall_before": avg_recall_before,
                "recall_after": avg_recall_after,
                "latency_before": avg_latency_before,
                "latency_after": avg_latency_after,
                "quantization": config.get("quantization", "NONE"),
                "store_vectors": config.get("store_vectors", False),
            }
        )

    if not data_points:
        print("  No data points found")
        return

    # Prepare data for plotting
    df_all = pd.DataFrame(data_points)

    # Filter out old-format results (which have None for loc/graph) if any slipped through
    df_all = df_all.dropna(subset=["loc", "graph"])

    # Use fillna for grouping cols just in case
    if "quantization" not in df_all.columns:
        df_all["quantization"] = "NONE"
    if "store_vectors" not in df_all.columns:
        df_all["store_vectors"] = False

    # Group by dataset_size AND config (quant, store)
    # This ensures we generate separate plots for INT8 vs NONE, etc.
    grouped = df_all.groupby(
        ["dataset_name", "dataset_size", "quantization", "store_vectors"]
    )

    for (ds_name, ds_size, quant, store), df in grouped:
        print(
            f"  Generating plot for dataset: {ds_name}, size: {ds_size}, Quant: {quant}, Store: {store}"
        )

        if df.empty:
            continue

        # Create 6-row subplot
        fig, axes = plt.subplots(6, 1, figsize=(14, 48))

        # Prepare X axis (Location Cache)
        unique_locs = sorted(df["loc"].unique())
        if -1 in unique_locs:
            unique_locs.remove(-1)
            unique_locs.append(-1)

        loc_map = {val: i for i, val in enumerate(unique_locs)}
        df["plot_x"] = df["loc"].map(loc_map)

        tick_labels_x = ["Unlimited" if x == -1 else f"{x:,}" for x in unique_locs]

        # Prepare Y axis (Graph Cache)
        unique_graphs = sorted(df["graph"].unique())
        graph_map = {val: i for i, val in enumerate(unique_graphs)}
        df["plot_y"] = df["graph"].map(graph_map)

        tick_labels_y = [f"{x:,}" for x in unique_graphs]

        # Helper for common scatter plot logic
        def draw_scatter(ax, column, cmap, label_fmt, title, cbar_label, data_df):
            if column not in data_df.columns or data_df[column].isna().all():
                return

            sc = ax.scatter(
                data_df["plot_x"],
                data_df["plot_y"],
                c=data_df[column],
                s=4000,
                cmap=cmap,
                alpha=0.9,
                edgecolors="black",
                linewidth=1,
            )
            cbar = plt.colorbar(sc, ax=ax)
            cbar.set_label(cbar_label, fontsize=16)
            ax.set_title(title, fontsize=20)
            ax.set_ylabel("Graph Build Cache Size", fontsize=18)

            for _, row in data_df.iterrows():
                if pd.notna(row[column]):
                    val_str = label_fmt(row[column])
                    ax.annotate(
                        val_str,
                        (row["plot_x"], row["plot_y"]),
                        xytext=(0, 0),
                        textcoords="offset points",
                        ha="center",
                        va="center",
                        fontsize=12,
                        fontweight="bold",
                        color="white",
                        path_effects=[
                            matplotlib.patheffects.withStroke(
                                linewidth=2, foreground="black"
                            )
                        ],
                    )

        # Plot 1: Peak Memory
        draw_scatter(
            axes[0], "mem", "RdYlGn_r", format_memory, "Peak Memory Usage", "MB", df
        )

        # Plot 2: Duration
        draw_scatter(
            axes[1],
            "duration",
            "RdYlGn_r",
            format_duration_seconds,
            "Benchmark Duration",
            "Seconds",
            df,
        )

        # Plot 3: Latency Before
        draw_scatter(
            axes[2],
            "latency_before",
            "RdYlGn_r",
            format_duration_ms,
            "Search Latency (Before Close)",
            "ms",
            df,
        )

        # Plot 4: Latency After
        draw_scatter(
            axes[3],
            "latency_after",
            "RdYlGn_r",
            format_duration_ms,
            "Search Latency (After Reload)",
            "ms",
            df,
        )

        # Plot 5: Recall Before
        draw_scatter(
            axes[4],
            "recall_before",
            "RdYlGn",
            lambda x: f"{x:.4f}",
            "Recall (Before Close)",
            "Recall",
            df,
        )

        # Plot 6: Recall After
        draw_scatter(
            axes[5],
            "recall_after",
            "RdYlGn",
            lambda x: f"{x:.4f}",
            "Recall (After Reload)",
            "Recall",
            df,
        )

        # Common formatting
        for row_idx in range(6):
            ax = axes[row_idx]
            ax.set_xticks(range(len(unique_locs)))
            ax.set_xticklabels(tick_labels_x, rotation=45, fontsize=14, ha="right")
            ax.set_yticks(range(len(unique_graphs)))
            ax.set_yticklabels(tick_labels_y, fontsize=14)
            ax.set_xlim(-0.5, len(unique_locs) - 0.5)
            ax.set_ylim(-0.5, len(unique_graphs) - 0.5)
            ax.grid(True, linestyle="--", alpha=0.3)

        dataset_name = df["dataset_name"].iloc[0]
        count_label = DATASET_COUNTS.get(ds_size, ds_size)
        store_lbl = "ON" if store else "OFF"

        plt.suptitle(
            f"{dataset_name} ({ds_size.upper()} - {count_label})\nQuant: {quant} | StoreVectors: {store_lbl}\nGreen = Good  |  Red = Bad",
            fontsize=28,
            y=0.995,
        )
        plt.tight_layout()

        # Save with detailed filename
        output_path = os.path.join(
            output_dir,
            f"comprehensive_metrics_dataset={ds_name}_size={ds_size}_quant={quant}_store={store_lbl}",
        )
        plt.savefig(f"{output_path}.pdf", bbox_inches="tight")
        print(f"  Saved: {output_path}.pdf")
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Plot parameter sweep results from sweep_results_* directories"
    )
    parser.add_argument(
        "sweep_dir",
        nargs="?",
        help="Path to sweep_results_* directory (default: most recent)",
    )
    parser.add_argument(
        "--output-dir",
        default="figures",
        help="Output directory for plots (default: figures)",
    )
    args = parser.parse_args()

    # Find sweep directory
    if args.sweep_dir:
        sweep_dir = args.sweep_dir
    else:
        # Find most recent sweep_results_* directory
        sweep_dirs = glob.glob("sweep_results_*")
        if not sweep_dirs:
            print("No sweep_results_* directories found!")
            return
        sweep_dir = sorted(sweep_dirs)[-1]

    if not os.path.exists(sweep_dir):
        print(f"Directory not found: {sweep_dir}")
        return

    print(f"Processing sweep results from: {sweep_dir}")

    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Verify consistency
    verify_consistency(sweep_dir)

    # Generate plots
    plot_memory_summary(sweep_dir, output_dir)

    print("\n✓ All plots generated successfully!")


if __name__ == "__main__":
    main()
