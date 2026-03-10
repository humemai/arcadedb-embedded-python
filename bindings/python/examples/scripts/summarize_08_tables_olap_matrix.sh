#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep08"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Edit INPUT_DIR, OUTPUT_DIR, DATASET, and LABEL_PREFIX in this file instead." >&2
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Input directory not found: $INPUT_DIR" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

DATASET_TAG="${DATASET//-/_}"
if [[ -z "${DATASET_TAG// /}" ]]; then
    DATASET_TAG="all_datasets"
fi
SUMMARY_MD="$OUTPUT_DIR/summary_08_tables_olap_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix = sys.argv[1:]
dataset_filter = dataset.strip()
dataset_label = dataset_filter or "all"

dataset_slug = dataset_filter.replace("-", "_")
dir_pattern = f"{dataset_slug}_tables_olap_*" if dataset_filter else "*_tables_olap_*"
if label_prefix:
    dir_pattern += f"_{label_prefix}*"

run_dirs = sorted(glob.glob(os.path.join(input_dir, dir_pattern)))


def to_int(value):
    try:
        return int(value)
    except Exception:
        return None


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def parse_threads_from_run_label(run_label):
    if not run_label:
        return None
    match = re.search(r"_t(\d+)_", str(run_label))
    if not match:
        return None
    return to_int(match.group(1))


def bytes_to_mib(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue / (1024.0 ** 2)


def kib_to_mib(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue / 1024.0


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    return str(value)


def percentile(values, p):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    k = (len(values) - 1) * p
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


def add_version(version_sets, key, value):
    if key in (None, "", "collected_at_utc"):
        return
    if value in (None, ""):
        return
    version_sets.setdefault(str(key), set()).add(str(value))


def postgres_version_number(value):
    if value in (None, ""):
        return None
    text = str(value)
    marker = "PostgreSQL "
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.split(" ", 1)[0]


def collect_version_metadata(version_sets, data, run_dir):
    add_version(version_sets, "postgresql_version", postgres_version_number(data.get("postgres_version")))
    add_version(version_sets, "sqlite_version", data.get("sqlite_version"))
    add_version(version_sets, "duckdb_runtime_version", data.get("duckdb_runtime_version"))

    wheel_meta = data.get("arcadedb_wheel_metadata")
    if isinstance(wheel_meta, dict):
        for key, value in wheel_meta.items():
            add_version(version_sets, key, value)

    runtime_versions = data.get("runtime_versions")
    if not isinstance(runtime_versions, dict):
        env_obj = data.get("environment")
        if isinstance(env_obj, dict):
            runtime_versions = env_obj.get("runtime_versions")
    if isinstance(runtime_versions, dict):
        for key, value in runtime_versions.items():
            add_version(version_sets, key, value)

    dep_path = os.path.join(run_dir, "dependency_versions.json")
    if os.path.isfile(dep_path):
        try:
            with open(dep_path, "r", encoding="utf-8") as f:
                dep_data = json.load(f)
            if isinstance(dep_data, dict):
                for key, value in dep_data.items():
                    add_version(version_sets, key, value)
        except Exception:
            pass

    wheel_path = os.path.join(run_dir, "arcadedb_wheel_build.json")
    if os.path.isfile(wheel_path):
        try:
            with open(wheel_path, "r", encoding="utf-8") as f:
                wheel_data = json.load(f)
            if isinstance(wheel_data, dict):
                for key, value in wheel_data.items():
                    add_version(version_sets, key, value)
        except Exception:
            pass


def format_version_summary_lines(version_sets, max_values=3):
    out = []
    for key in sorted(version_sets.keys()):
        if key == "postgresql_image" and (version_sets.get("postgresql_version") or set()):
            continue
        if key == "sqlite" and (version_sets.get("sqlite_version") or set()):
            continue
        values = sorted(version_sets.get(key) or [])
        if len(values) > 1 and "auto" in values:
            values = [value for value in values if value != "auto"]
        if not values:
            continue
        shown = ", ".join(values[:max_values])
        extra = len(values) - max_values
        if extra > 0:
            shown += f", ... (+{extra} more)"
        out.append(f"{key}: {shown}")
    return out


def ensure_versions_for_db_set(version_sets, db_values):
    expected = set()
    db_values = {str(v or "").strip() for v in db_values}
    if any(v in db_values for v in ("arcadedb", "arcadedb_sql", "arcadedb_cypher")):
        expected.add("arcadedb_embedded")
    if "duckdb" in db_values:
        expected.add("duckdb")
    if "postgresql" in db_values:
        expected.add("postgresql_image")
    if "sqlite" in db_values:
        expected.add("sqlite")
    for key in expected:
        if key not in version_sets or not version_sets[key]:
            version_sets[key] = {"unknown"}


status_rows = []
result_rows = []
query_rows = []
status_by_run = {}
version_sets = {}

for run_dir in run_dirs:
    status_path = os.path.join(run_dir, "run_status.json")
    status = None
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            status = None

    if status is not None:
        status_rows.append(status)
        run_label = status.get("run_label")
        if run_label:
            status_by_run[str(run_label)] = status

    result_paths = sorted(glob.glob(os.path.join(run_dir, "results_*.json")))
    if not result_paths:
        continue

    for result_path in result_paths:
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        result_dataset = data.get("dataset")
        run_label = data.get("run_label")
        if dataset_filter and result_dataset != dataset_filter:
            continue
        if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
            continue

        collect_version_metadata(version_sets, data, run_dir)

        du_path = os.path.join(run_dir, "disk_usage_du.json")
        du_mib = None
        if os.path.isfile(du_path):
            try:
                with open(du_path, "r", encoding="utf-8") as f:
                    du_mib = bytes_to_mib((json.load(f) or {}).get("du_bytes"))
            except Exception:
                du_mib = None

        row = {
            "dataset": data.get("dataset"),
            "db": data.get("db"),
            "run_label": data.get("run_label"),
            "seed": to_int(data.get("seed")),
            "threads": to_int(data.get("threads"))
            or to_int((status_by_run.get(str(data.get("run_label")) or "") or {}).get("threads"))
            or parse_threads_from_run_label(data.get("run_label")),
            "batch_size": to_int(data.get("batch_size"))
            or to_int((status_by_run.get(str(data.get("run_label")) or "") or {}).get("batch_size")),
            "query_runs": to_int(data.get("query_runs"))
            or to_int((status_by_run.get(str(data.get("run_label")) or "") or {}).get("query_runs")),
            "query_order": data.get("query_order")
            or (status_by_run.get(str(data.get("run_label")) or "") or {}).get("query_order"),
            "mem_limit": data.get("mem_limit"),
            "ingest_mode": data.get("ingest_mode") or "xml_batch",
            "load_time_s": to_float((data.get("load") or {}).get("total_s")),
            "index_time_s": to_float((data.get("index") or {}).get("total_s")),
            "query_time_s": to_float((data.get("queries") or {}).get("total_s")),
            "rss_peak_mib": kib_to_mib(data.get("rss_peak_kb")),
            "du_mib": du_mib,
            "queries": (data.get("queries") or {}).get("items") or [],
        }
        result_rows.append(row)

        for query in row["queries"]:
            elapsed_runs_s = query.get("elapsed_runs_s")
            if isinstance(elapsed_runs_s, list) and elapsed_runs_s:
                for sample_idx, sample_s in enumerate(elapsed_runs_s, start=1):
                    sample_s_float = to_float(sample_s)
                    if sample_s_float is None:
                        continue
                    query_rows.append(
                        {
                            "dataset": row["dataset"],
                            "db": row["db"],
                            "run_label": row["run_label"],
                            "query_name": query.get("name"),
                            "run": sample_idx,
                            "elapsed_ms": sample_s_float * 1000.0,
                            "row_count": to_int(query.get("row_count")),
                            "result_hash": query.get("result_hash"),
                        }
                    )
            else:
                elapsed_s = to_float(query.get("elapsed_s"))
                elapsed_ms = (elapsed_s * 1000.0) if elapsed_s is not None else None
                query_rows.append(
                    {
                        "dataset": row["dataset"],
                        "db": row["db"],
                        "run_label": row["run_label"],
                        "query_name": query.get("name"),
                        "run": to_int(query.get("run")),
                        "elapsed_ms": elapsed_ms,
                        "row_count": to_int(query.get("row_count")),
                        "result_hash": query.get("result_hash"),
                    }
                )

if not result_rows:
    print("No matching results_*.json files found.", file=sys.stderr)
    sys.exit(2)

result_rows.sort(key=lambda r: (str(r["dataset"]), str(r["db"]), str(r["run_label"])))
query_rows.sort(key=lambda r: (str(r["dataset"]), str(r["query_name"]), str(r["db"]), str(r["run_label"]), r["run"] or 0))

# Status summary (if run_status exists)
status_scoped = []
for status in status_rows:
    ds = status.get("dataset")
    rl = status.get("run_label")
    if dataset_filter and ds != dataset_filter:
        continue
    if label_prefix and (not rl or not str(rl).startswith(label_prefix)):
        continue
    status_scoped.append(status)

status_total = len(status_scoped)
status_success = sum(1 for s in status_scoped if s.get("status") == "success")
status_failed = sum(1 for s in status_scoped if s.get("status") == "failed")

# Aggregate by DB
by_db = defaultdict(list)
for row in result_rows:
    by_db[
        (
            row["dataset"],
            row["db"],
            row.get("threads"),
            row.get("query_runs"),
            row.get("query_order"),
            row.get("ingest_mode"),
        )
    ].append(row)

db_agg_rows = []
for (
    dataset_name,
    db,
    threads,
    query_runs,
    query_order,
    ingest_mode,
), rows in sorted(by_db.items()):
    load_vals = [r["load_time_s"] for r in rows if r["load_time_s"] is not None]
    index_vals = [r["index_time_s"] for r in rows if r["index_time_s"] is not None]
    query_vals = [r["query_time_s"] for r in rows if r["query_time_s"] is not None]
    rss_vals = [r["rss_peak_mib"] for r in rows if r["rss_peak_mib"] is not None]
    du_vals = [r["du_mib"] for r in rows if r["du_mib"] is not None]

    db_agg_rows.append(
        {
            "dataset": dataset_name,
            "db": db,
            "runs": len(rows),
            "run_labels": sorted({str(r.get("run_label") or "") for r in rows if r.get("run_label")}),
            "seeds": sorted({r.get("seed") for r in rows if r.get("seed") is not None}),
            "threads": threads,
            "query_runs": query_runs,
            "query_order": query_order,
            "ingest_mode": ingest_mode,
            "load_mean_s": statistics.mean(load_vals) if load_vals else None,
            "index_mean_s": statistics.mean(index_vals) if index_vals else None,
            "query_mean_s": statistics.mean(query_vals) if query_vals else None,
            "rss_peak_mean_mib": statistics.mean(rss_vals) if rss_vals else None,
            "du_mean_mib": statistics.mean(du_vals) if du_vals else None,
        }
    )

has_multi_runs = any(row["runs"] > 1 for row in db_agg_rows)
load_col = "load_mean_s" if has_multi_runs else "load_s"
index_col = "index_mean_s" if has_multi_runs else "index_s"
query_col = "query_mean_s" if has_multi_runs else "query_s"
rss_col = "rss_peak_mean_mib" if has_multi_runs else "rss_peak_mib"
du_col = "du_mean_mib" if has_multi_runs else "du_mib"

# Aggregate query latency per DB/query
by_query_db = defaultdict(list)
for row in query_rows:
    threads_for_run = None
    run_status = status_by_run.get(str(row.get("run_label")) or "") or {}
    threads_for_run = to_int(run_status.get("threads")) or parse_threads_from_run_label(
        row.get("run_label")
    )
    by_query_db[(row["dataset"], row["db"], threads_for_run, row["query_name"])].append(row)

query_agg_rows = []
for (dataset_name, db, threads, query_name), rows in sorted(by_query_db.items()):
    elapsed_vals = [r["elapsed_ms"] for r in rows if r["elapsed_ms"] is not None]
    row_counts = sorted({r["row_count"] for r in rows if r["row_count"] is not None})
    hashes = sorted({str(r["result_hash"]) for r in rows if r["result_hash"] is not None})

    query_agg_rows.append(
        {
            "dataset": dataset_name,
            "db": db,
            "threads": threads,
            "query": query_name,
            "samples": len(rows),
            "elapsed_mean_ms": statistics.mean(elapsed_vals) if elapsed_vals else None,
            "elapsed_p95_ms": percentile(elapsed_vals, 0.95) if elapsed_vals else None,
            "row_counts": row_counts,
            "hash_stable_within_db": len(hashes) <= 1,
            "hashes": hashes,
        }
    )

# Cross-DB hash equality by dataset/query
by_query_cross = defaultdict(list)
for row in query_rows:
    by_query_cross[(row["dataset"], row["query_name"])].append(row)

cross_hash_rows = []
for (dataset_name, query_name), rows in sorted(by_query_cross.items()):
    db_hashes = defaultdict(set)
    for row in rows:
        if row["db"] and row["result_hash"] is not None:
            db_hashes[str(row["db"])].add(str(row["result_hash"]))

    all_hashes = sorted({h for hs in db_hashes.values() for h in hs})
    cross_hash_rows.append(
        {
            "dataset": dataset_name,
            "query": query_name,
            "dbs": sorted(db_hashes.keys()),
            "hash_equal_across_dbs": len(all_hashes) <= 1,
            "all_hashes": all_hashes,
        }
    )

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")
generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ensure_versions_for_db_set(version_sets, {row.get("db") for row in result_rows})
version_summary_lines = format_version_summary_lines(version_sets)

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 08 Tables OLAP Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total result files: {len(result_rows)}")
if version_summary_lines:
    lines.append("- Versions/digest observed:")
    for item in version_summary_lines:
        lines.append(f"  - {item}")
if status_total > 0:
    lines.append(f"- Run status files: total={status_total}, success={status_success}, failed={status_failed}")
lines.append("- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.")
if has_multi_runs:
    lines.append("- DB summary timing/memory/disk columns are means across runs in each DB group.")
else:
    lines.append("- DB summary timing/memory/disk columns are single-run values (no averaging).")
lines.append("- `run_label` identifies the benchmark run(s) included in each DB summary row.")
lines.append("")

datasets = sorted({str(row.get("dataset") or "") for row in result_rows})
for current_dataset in datasets:
    lines.append(f"## Dataset: {current_dataset}")
    lines.append("")

    lines.append("### DB summary")
    lines.append("")
    lines.append(
        f"| db | run_label | seed | runs | threads | query_runs | query_order | ingest_mode | {load_col} | {index_col} | {query_col} | {rss_col} | {du_col} |"
    )
    lines.append("|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|")
    for row in db_agg_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        labels = row.get("run_labels") or []
        run_label_value = labels[0] if len(labels) == 1 else ", ".join(labels)
        seeds = row.get("seeds") or []
        seed_value = seeds[0] if len(seeds) == 1 else ", ".join(str(seed) for seed in seeds)
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["db"]),
                    fmt(run_label_value),
                    fmt(seed_value),
                    fmt(row["runs"]),
                    fmt(row["threads"]),
                    fmt(row["query_runs"]),
                    fmt(row["query_order"]),
                    fmt(row["ingest_mode"]),
                    fmt(row["load_mean_s"]),
                    fmt(row["index_mean_s"]),
                    fmt(row["query_mean_s"]),
                    fmt(row["rss_peak_mean_mib"]),
                    fmt(row["du_mean_mib"]),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("### Per-query latency (aggregated)")
    lines.append("")
    lines.append("| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |")
    lines.append("|---|---:|---|---:|---:|---:|---|---|")
    for row in query_agg_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["db"]),
                    fmt(row["threads"]),
                    fmt(row["query"]),
                    fmt(row["samples"]),
                    fmt(row["elapsed_mean_ms"]),
                    fmt(row["elapsed_p95_ms"]),
                    fmt(", ".join(str(v) for v in row["row_counts"])),
                    fmt(row["hash_stable_within_db"]),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("### Cross-DB hash checks")
    lines.append("")
    lines.append("| query | dbs | hash_equal_across_dbs | all_hashes |")
    lines.append("|---|---|---|---|")
    for row in cross_hash_rows:
        if str(row["dataset"] or "") != current_dataset:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["query"]),
                    fmt(", ".join(row["dbs"])),
                    fmt(row["hash_equal_across_dbs"]),
                    fmt(", ".join(row["all_hashes"])),
                ]
            )
            + " |"
        )
    lines.append("")

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
