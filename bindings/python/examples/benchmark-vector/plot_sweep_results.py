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

    Example with mutations (new format): benchmark_jvector_glove-100-angular_size_tiny_xmx16g_loc500000_graph50000_mut200.md
    Example without mutations (old format): benchmark_jvector_glove-100-angular_size_tiny.md
    Returns: {'dataset_name': 'glove-100-angular', 'dataset_size': 'tiny', 'heap': '16g', 'location_cache': 500000, 'graph_cache': 50000, 'mutations': 100}
    """
    # Try new format with mutations first (sweep results)
    match = re.search(
        r"benchmark_jvector_(.+?)_size_([a-zA-Z0-9]+)_xmx(\w+)_loc(-?\d+)_graph(\d+)_mut(\d+)",
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
        }

    # Try old format without mutations
    match = re.search(r"benchmark_jvector_(.+?)_size_([a-zA-Z0-9]+)$", filename)
    if match:
        return {
            "dataset_name": match.group(1),
            "dataset_size": match.group(2),
            "heap": None,
            "location_cache": None,
            "graph_cache": None,
            "mutations": 100,  # Default mutations value for old format
        }

    return None


def plot_location_cache_sweep(sweep_dir, output_dir):
    """Plot results for location cache size sweep (fixed graph cache)."""
    print("\nProcessing location cache sweep...")

    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*_graph50000.md"))

    if not md_files:
        print("  No location cache sweep files found")
        return

    # Collect data
    sweep_data = []
    for md_file in md_files:
        filename = os.path.basename(md_file)
        config = parse_config_from_filename(filename)
        if not config:
            continue

        df = parse_markdown_table(md_file)
        if df.empty:
            continue

        # Find corresponding memory log
        log_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"*_loc{config['location_cache']}_graph{config['graph_cache']}_*_memory.log",
        )
        log_files = glob.glob(log_pattern)
        peak_mem = None
        if log_files:
            peak_mem = get_peak_memory(log_files[0])

        # Calculate average build time
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
        print("  No valid data found")
        return

    # Verify consistency: Check if recall/latency are similar for same parameters
    print("\n  Verifying recall/latency consistency across cache sizes...")
    # Take a reference configuration (middle one)
    ref_data = sweep_data[len(sweep_data) // 2]
    ref_df = ref_data["df"]

    for data in sweep_data:
        if data == ref_data:
            continue
        df = data["df"]

        # Compare recall and latency for matching rows
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
                f"    Cache {cache_label}: Max recall diff={recall_diff:.4f}, Max latency diff={latency_diff:.2f}ms"
            )

    # Sort by location cache size
    sweep_data.sort(
        key=lambda x: x["location_cache"] if x["location_cache"] != -1 else float("inf")
    )

    # Plot: Memory usage and Build time
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
        labels.append(label)
        cache_sizes.append(
            loc_cache if loc_cache != -1 else 1500000
        )  # For plotting unlimited

        if peak_mem:
            peak_memories.append(peak_mem)
        else:
            peak_memories.append(0)

        build_times.append(build_time)

    x_pos = range(len(labels))
    colors = plt.cm.viridis([i / (len(labels) - 1) for i in range(len(labels))])

    # Plot 1: Memory usage
    bars1 = ax1.bar(x_pos, peak_memories, color=colors, alpha=0.7)
    ax1.set_title("Peak Memory Usage by Location Cache Size")
    ax1.set_xlabel("Location Cache Size")
    ax1.set_ylabel("Peak Memory (MB)")
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.grid(True, axis="y", alpha=0.2)

    # Add values on bars
    for i, (bar, val) in enumerate(zip(bars1, peak_memories)):
        if val > 0:
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                val + 50,
                f"{val:.0f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

    # Plot 2: Build time
    bars2 = ax2.bar(x_pos, build_times, color=colors, alpha=0.7)
    ax2.set_title("Build Time by Location Cache Size")
    ax2.set_xlabel("Location Cache Size")
    ax2.set_ylabel("Build Time (seconds)")
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.grid(True, axis="y", alpha=0.2)

    # Add values on bars
    for i, (bar, val) in enumerate(zip(bars2, build_times)):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.5,
            f"{val:.1f}s",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    plt.suptitle("Location Cache Size Impact (Graph Cache: 50K)", fontsize=18, y=1.02)
    plt.tight_layout()

    # Save
    output_prefix = os.path.join(output_dir, "location_cache_sweep")
    plt.savefig(f"{output_prefix}.png", dpi=150, bbox_inches="tight")
    plt.savefig(f"{output_prefix}.pdf", bbox_inches="tight")
    print(f"  Saved: {output_prefix}.png and .pdf")
    plt.close()


def plot_graph_cache_sweep(sweep_dir, output_dir):
    """Plot results for graph build cache size sweep (fixed location cache)."""
    print("\nProcessing graph cache sweep...")

    md_files = glob.glob(
        os.path.join(sweep_dir, "benchmark_jvector_*_loc500000_graph*.md")
    )

    if not md_files:
        print("  No graph cache sweep files found")
        return

    # Collect data
    sweep_data = []
    for md_file in md_files:
        filename = os.path.basename(md_file)
        config = parse_config_from_filename(filename)
        if not config:
            continue

        df = parse_markdown_table(md_file)
        if df.empty:
            continue

        # Calculate build time
        build_time = 0
        if "Build (s)" in df.columns:
            build_time = df["Build (s)"].mean()

        # Find corresponding memory log
        log_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"*_loc{config['location_cache']}_graph{config['graph_cache']}_*_memory.log",
        )
        log_files = glob.glob(log_pattern)
        peak_mem = None
        if log_files:
            peak_mem = get_peak_memory(log_files[0])

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
        print("  No valid data found")
        return

    # Verify consistency: Check if recall/latency are similar for same parameters
    print("\n  Verifying recall/latency consistency across graph cache sizes...")
    # Take a reference configuration (middle one)
    ref_data = sweep_data[len(sweep_data) // 2]
    ref_df = ref_data["df"]

    for data in sweep_data:
        if data == ref_data:
            continue
        df = data["df"]

        # Compare recall and latency for matching rows
        if len(df) == len(ref_df):
            recall_diff = abs(
                df["Recall (After)"].values - ref_df["Recall (After)"].values
            ).max()
            latency_diff = abs(
                df["Latency (ms) (After)"].values
                - ref_df["Latency (ms) (After)"].values
            ).max()

            print(
                f"    Graph Cache {data['graph_cache']:,}: Max recall diff={recall_diff:.4f}, Max latency diff={latency_diff:.2f}ms"
            )

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
        labels.append(label)
        graph_cache_sizes.append(graph_cache)
        build_times.append(build_time)

        if peak_mem:
            peak_memories.append(peak_mem)
        else:
            peak_memories.append(0)

    x_pos = range(len(labels))
    colors = plt.cm.plasma([i / (len(labels) - 1) for i in range(len(labels))])

    # Plot 1: Build time
    bars1 = ax1.bar(x_pos, build_times, color=colors, alpha=0.7)
    ax1.set_title("Build Time by Graph Cache Size")
    ax1.set_xlabel("Graph Cache Size")
    ax1.set_ylabel("Build Time (seconds)")
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.grid(True, axis="y", alpha=0.2)

    # Add values on bars
    for i, (bar, val) in enumerate(zip(bars1, build_times)):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.5,
            f"{val:.1f}s",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    # Plot 2: Memory usage
    bars2 = ax2.bar(x_pos, peak_memories, color=colors, alpha=0.7)
    ax2.set_title("Peak Memory Usage by Graph Cache Size")
    ax2.set_xlabel("Graph Cache Size")
    ax2.set_ylabel("Peak Memory (MB)")
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.grid(True, axis="y", alpha=0.2)

    # Add values on bars
    for i, (bar, val) in enumerate(zip(bars2, peak_memories)):
        if val > 0:
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                val + 50,
                f"{val:.0f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

    plt.suptitle("Graph Cache Size Impact (Location Cache: 500K)", fontsize=18, y=1.02)
    plt.tight_layout()

    # Save
    output_prefix = os.path.join(output_dir, "graph_cache_sweep")
    plt.savefig(f"{output_prefix}.png", dpi=150, bbox_inches="tight")
    plt.savefig(f"{output_prefix}.pdf", bbox_inches="tight")
    print(f"  Saved: {output_prefix}.png and .pdf")
    plt.close()


def verify_consistency(sweep_dir):
    """Verify that recall and latency are consistent across cache configurations."""
    print("\n" + "=" * 70)
    print("VERIFYING RECALL/LATENCY CONSISTENCY ACROSS CACHE CONFIGURATIONS")
    print("=" * 70)

    # Location cache sweep verification
    print("\n1. Location Cache Sweep (fixed graph cache = 50K):")
    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*_graph50000.md"))

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
    md_files = glob.glob(
        os.path.join(sweep_dir, "benchmark_jvector_*_loc500000_graph*.md")
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

    md_files = glob.glob(os.path.join(sweep_dir, "benchmark_jvector_*.md"))
    if not md_files:
        print("  No benchmark files found")
        return

    data_points = []

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

        # Find memory log
        log_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"*_loc{config['location_cache']}_graph{config['graph_cache']}_*_memory.log",
        )
        log_files = glob.glob(log_pattern)
        if not log_files:
            continue

        peak_mem = get_peak_memory(log_files[0])
        if peak_mem is None:
            continue

        # Find duration log
        duration_pattern = os.path.join(
            sweep_dir,
            "benchmark_logs",
            f"*_loc{config['location_cache']}_graph{config['graph_cache']}_*_duration.txt",
        )
        duration_files = glob.glob(duration_pattern)
        duration = None
        if duration_files:
            try:
                with open(duration_files[0], "r") as f:
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
            }
        )

    if not data_points:
        print("  No data points found")
        return

    # Prepare data for plotting
    df_all = pd.DataFrame(data_points)

    # Filter out old-format results (which have None for loc/graph)
    df_all = df_all.dropna(subset=["loc", "graph"])

    if not data_points:
        print("  No data points found")
        return

    # Group by dataset_size and plot for each
    for ds_size, df in df_all.groupby("dataset_size"):
        print(f"  Generating plot for dataset size: {ds_size}")

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

        # Plot 1: Peak Memory Usage
        ax = axes[0]
        sc1 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["mem"],
            s=4000,
            cmap="RdYlGn_r",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar1 = plt.colorbar(sc1, ax=ax)
        cbar1.set_label("Peak Memory (MB)", fontsize=16)
        ax.set_title("Peak Memory Usage", fontsize=20)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["mem"]):
                mem_str = f"{row['mem']:.0f}MB"
                ax.annotate(
                    mem_str,
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

        # Plot 2: Duration
        ax = axes[1]
        sc2 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["duration"],
            s=4000,
            cmap="RdYlGn_r",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar2 = plt.colorbar(sc2, ax=ax)
        cbar2.set_label("Duration (s)", fontsize=16)
        ax.set_title("Benchmark Duration", fontsize=20)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["duration"]):
                dur_str = f"{row['duration']:.0f}s"
                ax.annotate(
                    dur_str,
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

        # Plot 3: Latency (Before)
        ax = axes[2]
        sc3 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["latency_before"],
            s=4000,
            cmap="RdYlGn_r",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar3 = plt.colorbar(sc3, ax=ax)
        cbar3.set_label("Latency (ms)", fontsize=16)
        ax.set_title("Search Latency Before Close", fontsize=20)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["latency_before"]):
                latency = row["latency_before"]
                if latency < 1000:
                    lat_str = f"{latency:.1f}ms"
                else:
                    lat_str = f"{latency/1000:.2f}s"
                ax.annotate(
                    lat_str,
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

        # Plot 4: Latency (After)
        ax = axes[3]
        sc4 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["latency_after"],
            s=4000,
            cmap="RdYlGn_r",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar4 = plt.colorbar(sc4, ax=ax)
        cbar4.set_label("Latency (ms)", fontsize=16)
        ax.set_title("Search Latency After Close/Reopen", fontsize=20)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["latency_after"]):
                latency = row["latency_after"]
                if latency < 1000:
                    lat_str = f"{latency:.1f}ms"
                else:
                    lat_str = f"{latency/1000:.2f}s"
                ax.annotate(
                    lat_str,
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

        # Plot 5: Recall (Before)
        ax = axes[4]
        sc5 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["recall_before"],
            s=4000,
            cmap="RdYlGn",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar5 = plt.colorbar(sc5, ax=ax)
        cbar5.set_label("Recall", fontsize=16)
        ax.set_title("Search Recall Before Close", fontsize=20)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["recall_before"]):
                recall_str = f"{row['recall_before']:.4f}"
                ax.annotate(
                    recall_str,
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

        # Plot 6: Recall (After)
        ax = axes[5]
        sc6 = ax.scatter(
            df["plot_x"],
            df["plot_y"],
            c=df["recall_after"],
            s=4000,
            cmap="RdYlGn",
            alpha=0.9,
            edgecolors="black",
            linewidth=1,
        )
        cbar6 = plt.colorbar(sc6, ax=ax)
        cbar6.set_label("Recall", fontsize=16)
        ax.set_title("Search Recall After Close/Reopen", fontsize=20)
        ax.set_xlabel("Location Cache Size", fontsize=18)
        ax.set_ylabel("Graph Build Cache Size", fontsize=18)

        # Annotations
        for _, row in df.iterrows():
            if pd.notna(row["recall_after"]):
                recall_str = f"{row['recall_after']:.4f}"
                ax.annotate(
                    recall_str,
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

        # Common formatting for all axes
        for row_idx in range(6):
            ax = axes[row_idx]
            ax.set_xticks(range(len(unique_locs)))
            ax.set_xticklabels(tick_labels_x, rotation=45, fontsize=14, ha="right")
            ax.set_yticks(range(len(unique_graphs)))
            ax.set_yticklabels(tick_labels_y, fontsize=14)
            ax.set_xlim(-0.5, len(unique_locs) - 0.5)
            ax.set_ylim(-0.5, len(unique_graphs) - 0.5)
            ax.grid(True, linestyle="--", alpha=0.3)

        dataset_name = df_all["dataset_name"].iloc[0]
        count_label = DATASET_COUNTS.get(ds_size, ds_size)
        plt.suptitle(
            f"{dataset_name} ({ds_size.upper()} - {count_label} Vectors)\nGreen = Good  |  Red = Bad",
            fontsize=28,
            y=0.995,
        )
        plt.tight_layout()

        # Save
        output_path = os.path.join(output_dir, f"comprehensive_metrics_{ds_size}")
        plt.savefig(f"{output_path}.png", dpi=150, bbox_inches="tight")
        plt.savefig(f"{output_path}.pdf", bbox_inches="tight")
        print(f"  Saved: {output_path}.png and .pdf")
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
