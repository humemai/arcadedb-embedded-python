#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="$EXAMPLES_DIR/my_test_databases"
OUTPUT_DIR="$EXAMPLES_DIR/benchmark_results"
DATASET="${DATASET:-}"
LABEL_PREFIX="sweep11"

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
SUMMARY_MD="$OUTPUT_DIR/summary_11_vector_index_build_${DATASET_TAG}.md"

python3 - "$INPUT_DIR" "$SUMMARY_MD" "$DATASET" "$LABEL_PREFIX" << 'PY'
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

input_dir, summary_md, dataset, label_prefix = sys.argv[1:]
dataset_filter = dataset.strip()
dataset_label = dataset_filter or "all"

dataset_slug = dataset_filter.replace("-", "_")
dir_pattern = f"*dataset={dataset_filter}*" if dataset_filter else "*"
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

def bytes_to_mib(value):
    fvalue = to_float(value)
    if fvalue is None:
        return None
    return fvalue / (1024.0 ** 2)

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

def add_version(version_sets, key, value):
    if key in (None, "", "collected_at_utc"):
        return
    if value in (None, ""):
        return
    version_sets.setdefault(str(key), set()).add(str(value))

def collect_version_metadata(version_sets, data, run_dir):
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

def ensure_versions_for_backend_set(version_sets, backend_values):
    expected = set()
    backend_values = {str(v or "").strip() for v in backend_values}
    if any(v in backend_values for v in ("arcadedb", "arcadedb_sql", "arcadedb_cypher")):
        expected.add("arcadedb_embedded")
    if "faiss" in backend_values:
        expected.add("faiss_cpu")
    if "lancedb" in backend_values:
        expected.add("lancedb")
    if "pgvector" in backend_values:
        expected.add("pgvector_image")
    if "qdrant" in backend_values:
        expected.add("qdrant_image")
    if "milvus" in backend_values:
        expected.add("milvus_compose_version")
    for key in expected:
        if key not in version_sets or not version_sets[key]:
            version_sets[key] = {"unknown"}


def canonicalize_backend_label(label):
    label_s = str(label or "").strip().lower()
    if label_s == "arcadedb":
        return "arcadedb_sql"
    return label_s


def parse_mem_limit_from_dir_name(run_dir):
    base = os.path.basename(str(run_dir or "").rstrip("/"))
    if not base:
        return None
    match = re.search(r"(?:^|_)mem=([^_]+)", base)
    if match:
        return match.group(1)
    match = re.search(r"(?:^|_)mem([0-9][^_]*)", base)
    if match:
        return match.group(1)
    return None


def parse_mem_limit_from_run_label(run_label):
    run_label_s = str(run_label or "")
    if not run_label_s:
        return None
    match = re.search(r"_m([0-9][A-Za-z0-9]*)$", run_label_s)
    if match:
        return match.group(1)
    return None


def parse_run_dir_metadata(run_dir):
    base = os.path.basename(str(run_dir or "").rstrip("/"))
    if not base:
        return {}

    dataset_match = re.search(r"(?:^|_)dataset=([^_]+)", base)
    backend_match = re.search(r"(?:^|_)backend=([^_]+)", base)
    run_match = re.search(r"(?:^|_)run=(.+)$", base)

    run_label = run_match.group(1) if run_match else None
    seed = None
    if run_label:
        seed_match = re.search(r"_s(\d+)", run_label)
        if seed_match:
            seed = to_int(seed_match.group(1))

    mem_limit = parse_mem_limit_from_dir_name(run_dir)
    if mem_limit is None:
        mem_limit = parse_mem_limit_from_run_label(run_label)

    return {
        "dataset": dataset_match.group(1) if dataset_match else None,
        "backend": canonicalize_backend_label(backend_match.group(1) if backend_match else None),
        "run_label": run_label,
        "seed": seed,
        "mem_limit": mem_limit,
    }

status_rows = []
status_by_run = {}
run_dir_by_run = {}
run_dirs_no_status = []
rows = []
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

    if isinstance(status, dict):
        status_rows.append(status)
        status_run_label = status.get("run_label")
        if status_run_label:
            status_by_run[str(status_run_label)] = status
            run_dir_by_run[str(status_run_label)] = run_dir
    else:
        run_dirs_no_status.append(run_dir)

    result_paths = sorted(glob.glob(os.path.join(run_dir, "results_*.json")))
    if not result_paths:
        continue

    du_mib = None
    du_path = os.path.join(run_dir, "disk_usage_du.json")
    if os.path.isfile(du_path):
        try:
            with open(du_path, "r", encoding="utf-8") as f:
                du_mib = bytes_to_mib((json.load(f) or {}).get("du_bytes"))
        except Exception:
            du_mib = None

    for result_path in result_paths:
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        dataset_name = ((data.get("dataset") or {}).get("name") if isinstance(data.get("dataset"), dict) else data.get("dataset"))
        config = data.get("config") if isinstance(data.get("config"), dict) else {}
        env = data.get("environment") if isinstance(data.get("environment"), dict) else {}

        run_label = config.get("run_label") or data.get("run_label")
        if label_prefix and (not run_label or not str(run_label).startswith(label_prefix)):
            continue
        if dataset_filter and dataset_name != dataset_filter:
            continue

        if run_label:
            run_dir_by_run[str(run_label)] = run_dir

        collect_version_metadata(version_sets, data, run_dir)

        status_for_run = status_by_run.get(str(run_label) if run_label else "", status if isinstance(status, dict) else {})
        backend = canonicalize_backend_label(
            config.get("backend") or env.get("backend") or (status_for_run or {}).get("backend")
        )

        phases = data.get("phases") if isinstance(data.get("phases"), dict) else {}
        runtime_versions = env.get("runtime_versions") if isinstance(env.get("runtime_versions"), dict) else {}

        rows.append(
            {
                "dataset": dataset_name,
                "backend": backend,
                "run_label": run_label,
                "seed": to_int(config.get("seed") or data.get("seed") or (status_for_run or {}).get("seed")),
                "threads": to_int(env.get("threads_limit") or (status_for_run or {}).get("threads")),
                "mem_limit": env.get("mem_limit") or config.get("mem_limit") or (status_for_run or {}).get("mem_limit") or parse_mem_limit_from_dir_name(run_dir) or parse_mem_limit_from_run_label(run_label),
                "batch_size": to_int(config.get("batch_size") or (status_for_run or {}).get("batch_size")),
                "count": to_int(config.get("count")),
                "rows": to_int(((data.get("dataset") or {}).get("rows") if isinstance(data.get("dataset"), dict) else None)),
                "run_total_s": to_float(((data.get("run") or {}).get("total_time_s") if isinstance(data.get("run"), dict) else None)),
                "create_db_s": to_float(((phases.get("create_db") or {}).get("time_sec") if isinstance(phases.get("create_db"), dict) else None)),
                "create_index_s": to_float(((phases.get("create_index") or {}).get("time_sec") if isinstance(phases.get("create_index"), dict) else None)),
                "ingest_s": to_float(((phases.get("ingest") or {}).get("time_sec") if isinstance(phases.get("ingest"), dict) else None)),
                "close_db_s": to_float(((phases.get("close_db") or {}).get("time_sec") if isinstance(phases.get("close_db"), dict) else None)),
                "peak_rss_mib": to_float(data.get("peak_rss_mb")),
                "db_size_mib": to_float(data.get("db_size_mb")),
                "du_mib": du_mib,
                "status": (status_for_run or {}).get("status") or ((data.get("telemetry") or {}).get("run_status") if isinstance(data.get("telemetry"), dict) else None) or "success",
                "exit_code": to_int((status_for_run or {}).get("exit_code")),
            }
        )

seen_result_run_labels = {str(row.get("run_label")) for row in rows if row.get("run_label")}

for status in status_rows:
    ds = status.get("dataset")
    rl = status.get("run_label")
    if dataset_filter and ds != dataset_filter:
        continue
    if label_prefix and (not rl or not str(rl).startswith(label_prefix)):
        continue
    if rl and str(rl) in seen_result_run_labels:
        continue

    run_dir = run_dir_by_run.get(str(rl) if rl else "")
    rows.append(
        {
            "dataset": ds,
            "backend": canonicalize_backend_label(status.get("backend")),
            "run_label": rl,
            "seed": to_int(status.get("seed")),
            "threads": to_int(status.get("threads")),
            "mem_limit": status.get("mem_limit") or parse_mem_limit_from_dir_name(run_dir) or parse_mem_limit_from_run_label(rl),
            "batch_size": to_int(status.get("batch_size")),
            "count": to_int(status.get("count")),
            "rows": None,
            "run_total_s": None,
            "create_db_s": None,
            "create_index_s": None,
            "ingest_s": None,
            "close_db_s": None,
            "peak_rss_mib": None,
            "db_size_mib": None,
            "du_mib": None,
            "status": "no_result",
            "exit_code": to_int(status.get("exit_code")),
        }
    )

for run_dir in run_dirs_no_status:
    if glob.glob(os.path.join(run_dir, "results_*.json")):
        continue
    meta = parse_run_dir_metadata(run_dir)
    ds = meta.get("dataset")
    rl = meta.get("run_label")
    if dataset_filter and ds != dataset_filter:
        continue
    if label_prefix and (not rl or not str(rl).startswith(label_prefix)):
        continue
    if rl and str(rl) in seen_result_run_labels:
        continue

    rows.append(
        {
            "dataset": ds,
            "backend": canonicalize_backend_label(meta.get("backend")),
            "run_label": rl,
            "seed": meta.get("seed"),
            "threads": None,
            "mem_limit": meta.get("mem_limit"),
            "batch_size": None,
            "count": None,
            "rows": None,
            "run_total_s": None,
            "create_db_s": None,
            "create_index_s": None,
            "ingest_s": None,
            "close_db_s": None,
            "peak_rss_mib": None,
            "db_size_mib": None,
            "du_mib": None,
            "status": "no_result",
            "exit_code": None,
        }
    )

if not rows:
    print("No matching run_status.json or results_*.json files found.", file=sys.stderr)
    sys.exit(2)

rows.sort(key=lambda r: (str(r.get("dataset") or ""), str(r.get("backend") or ""), str(r.get("run_label") or "")))

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

dataset_size_profile = dataset_filter.split("-")[-1] if dataset_filter and "-" in dataset_filter else (dataset_filter or "all")
generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ensure_versions_for_backend_set(version_sets, {row.get("backend") for row in rows})
version_summary_lines = format_version_summary_lines(version_sets)

COLUMNS = [
    "backend",
    "run_label",
    "seed",
    "threads",
    "mem_limit",
    "batch_size",
    "count",
    "rows",
    "run_total_s",
    "create_db_s",
    "create_index_s",
    "ingest_s",
    "close_db_s",
    "peak_rss_mib",
    "db_size_mib",
    "du_mib",
    "status",
    "exit_code",
]

lines = []
title_suffix = dataset_filter if dataset_filter else "All Dataset Sizes"
lines.append(f"# 11 Vector Index Build Matrix Summary — {title_suffix}")
lines.append("")
lines.append(f"- Generated (UTC): {generated_at_utc}")
lines.append(f"- Dataset: {dataset_label}")
lines.append(f"- Dataset size profile: {dataset_size_profile}")
lines.append(f"- Label prefix: {label_prefix}")
lines.append(f"- Total runs: {len(rows)}")
no_result_rows = sum(1 for row in rows if row.get("status") == "no_result")
if no_result_rows > 0:
    lines.append(f"- Runs without result JSON: {no_result_rows}")
if version_summary_lines:
    lines.append("- Versions/digest observed:")
    for item in version_summary_lines:
        lines.append(f"  - {item}")
if status_total > 0:
    lines.append(f"- Run status files: total={status_total}, success={status_success}, failed={status_failed}")
lines.append("- Note: times are phase-level benchmark timings from each run result.")
lines.append("- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.")
lines.append("")

datasets = sorted({str(row.get("dataset") or "") for row in rows})
for current_dataset in datasets:
    lines.append(f"## Dataset: {current_dataset}")
    lines.append("")
    lines.append("| " + " | ".join(COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(COLUMNS)) + "|")
    for row in rows:
        if str(row.get("dataset") or "") != current_dataset:
            continue
        values = [fmt(row.get(column)) for column in COLUMNS]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote: {summary_md}")
PY
