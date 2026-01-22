#!/usr/bin/env python3
"""
Summarize ArcadeDB MSMARCO search-only (overquery) runs into markdown tables.

Reads: arcadedb_runs/*/results.json produced by run_overquery_sweep.py.
Writes: summaries/arcadedb_search_study_<dataset>.md

Focuses on search metrics and heap sizing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path("arcadedb_runs_search")
OUT_DIR = Path("summaries")
EVAL_K = 50


def find_results(root: Path) -> List[Path]:
    return sorted(root.glob("*/results.json"))


def run_dir_value(run_dir_name: str, key: str) -> str | None:
    prefix = f"{key}="
    for part in run_dir_name.split("_"):
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def _peak_rss(phases: Dict[str, dict]) -> float | None:
    vals = [
        v.get("rss_after_mb")
        for v in phases.values()
        if v.get("rss_after_mb") is not None
    ]
    return max(vals) if vals else None


def parse_record(path: Path) -> Dict | None:
    data = json.loads(path.read_text())
    cfg = data.get("config", {})
    phases = data.get("phases", {})
    recall = data.get("recall", {})
    latency = data.get("latency_ms", {})

    run_dir_name = path.parent.name
    if run_dir_value(run_dir_name, "study") != "search":
        return None

    dataset_tag = run_dir_value(run_dir_name, "dataset") or run_dir_name
    heap_tag = run_dir_value(run_dir_name, "heap")
    overquery = cfg.get("overquery_factor")

    total_duration = sum(
        v
        for v in [
            phases.get("load_queries", {}).get("time_sec"),
            phases.get("open_db", {}).get("time_sec"),
            phases.get("warmup", {}).get("time_sec"),
            phases.get("search", {}).get("time_sec"),
            phases.get("close_db_final", {}).get("time_sec"),
        ]
        if v is not None
    )

    recall_entry = recall.get("search", {}) or {}
    latency_entry = latency.get("search", {}) or {}

    return {
        "dataset": dataset_tag,
        "heap": heap_tag,
        "overquery_factor": overquery,
        "quantization": cfg.get("quantization"),
        "max_connections": cfg.get("max_connections"),
        "beam_width": cfg.get("beam_width"),
        "search_s": phases.get("search", {}).get("time_sec"),
        "warmup_s": phases.get("warmup", {}).get("time_sec"),
        "open_db_s": phases.get("open_db", {}).get("time_sec"),
        "load_queries_s": phases.get("load_queries", {}).get("time_sec"),
        "close_db_s": phases.get("close_db_final", {}).get("time_sec"),
        "recall@50": recall_entry.get("mean"),
        "latency_ms_mean": latency_entry.get("mean"),
        "latency_ms_p95": latency_entry.get("p95"),
        "peak_rss_mb": _peak_rss(phases),
        "db_size_mb": data.get("db_size_mb"),
        "total_duration": total_duration,
        "reuse": run_dir_value(run_dir_name, "reuse"),
    }


def load_dataframe(root: Path) -> pd.DataFrame:
    rows = []
    for p in find_results(root):
        try:
            rec = parse_record(p)
            if rec is not None:
                rows.append(rec)
        except Exception as exc:  # pragma: no cover
            print(f"Skip {p}: {exc}")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    num_cols = [
        "overquery_factor",
        "max_connections",
        "beam_width",
        "load_queries_s",
        "open_db_s",
        "warmup_s",
        "search_s",
        "close_db_s",
        "recall@50",
        "latency_ms_mean",
        "latency_ms_p95",
        "peak_rss_mb",
        "db_size_mb",
        "total_duration",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def df_to_markdown(df: pd.DataFrame) -> str:
    cols = [
        "heap",
        "overquery_factor",
        "quantization",
        "max_connections",
        "beam_width",
        "recall@50",
        "latency_ms_mean",
        "latency_ms_p95",
        "load_queries_s",
        "open_db_s",
        "warmup_s",
        "search_s",
        "close_db_s",
        "peak_rss_mb",
        "db_size_mb",
        "total_duration",
    ]
    df = df.loc[:, [c for c in cols if c in df.columns]].copy()
    for c in df.columns:
        if c in ("heap", "quantization"):
            continue
        if c == "recall@50":
            df[c] = df[c].round(4)
        else:
            df[c] = df[c].round(3)
    return df.to_markdown(index=False)


def write_markdown(df: pd.DataFrame, dataset: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"arcadedb_search_study_{dataset}.md"
    header = f"# ArcadeDB search study {dataset} (1000 queries, Recall@{EVAL_K})\n"
    sections: List[str] = []
    for heap, sub in df.groupby("heap", dropna=False):
        heap_label = "unknown" if heap is None or pd.isna(heap) else str(heap)
        sub = sub.sort_values(["recall@50", "latency_ms_mean"], ascending=[False, True])
        if "heap" in sub.columns:
            sub = sub.drop(columns=["heap"])
        sections.append(f"## Heap {heap_label}\n\n{df_to_markdown(sub)}")

    body = "\n\n".join(sections)
    md_path.write_text(f"{header}\n{body}\n")
    print(f"Wrote {md_path}")


def main() -> None:
    df = load_dataframe(ROOT)
    if df.empty:
        print("No results found.")
        return

    for dataset, sub in df.groupby("dataset"):
        write_markdown(sub, dataset, OUT_DIR)


if __name__ == "__main__":
    main()
