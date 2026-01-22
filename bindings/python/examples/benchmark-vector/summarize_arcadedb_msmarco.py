#!/usr/bin/env python3
"""
Summarize ArcadeDB MSMARCO runs into markdown tables (one file per dataset).

Reads: arcadedb_runs/*/results.json produced by benchmark_arcadedb_msmarco.py.
Writes: summaries/arcadedb_msmarco_<dataset>.md

Sorted by recall desc, then latency asc.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

ROOT = Path("arcadedb_runs")
OUT_DIR = Path("summaries")
EVAL_K = 50


def format_duration(seconds: float | int | None) -> str | None:
    if seconds is None or pd.isna(seconds):
        return None
    total = float(seconds)
    minutes, secs = divmod(total, 60)
    if total < 60:
        return f"{total:.3f}s"
    if minutes < 60:
        return f"{int(minutes)}m {secs:.3f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {secs:.3f}s"


def find_results(root: Path) -> List[Path]:
    return sorted(root.glob("*/results.json"))


def _run_dir_value(run_dir_name: str, key: str) -> str | None:
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


def parse_record(path: Path) -> Dict:
    data = json.loads(path.read_text())
    cfg = data.get("config", {})
    phases = data.get("phases", {})
    recall = data.get("recall", {})
    latency = data.get("latency_ms", {})

    create_phase = phases.get("create_index") or phases.get("build_index") or {}

    # dataset tag from dir name
    run_dir_name = path.parent.name
    dataset_tag = _run_dir_value(run_dir_name, "dataset") or run_dir_name
    heap_tag = _run_dir_value(run_dir_name, "heap")

    recall_after = recall.get("search_after_reopen", {}) or {}
    recall_before = recall.get("search", {}) or {}
    if recall_after.get("mean") is None:
        recall_after = recall_before

    latency_after = latency.get("search_after_reopen", {}) or {}
    latency_before = latency.get("search", {}) or {}
    if latency_after.get("mean") is None:
        latency_after = latency_before

    # Total duration across measured phases (skip None)
    total_duration = sum(
        v
        for v in [
            phases.get("load_queries", {}).get("time_sec"),
            phases.get("create_db", {}).get("time_sec"),
            phases.get("load_corpus", {}).get("time_sec"),
            phases.get("ingest", {}).get("time_sec"),
            create_phase.get("time_sec"),
            phases.get("build_graph_now", {}).get("time_sec"),
            phases.get("warmup", {}).get("time_sec"),
            phases.get("search", {}).get("time_sec"),
            phases.get("close_db", {}).get("time_sec"),
            phases.get("open_db", {}).get("time_sec"),
            phases.get("warmup_after_reopen", {}).get("time_sec"),
            phases.get("search_after_reopen", {}).get("time_sec"),
            phases.get("close_db_final", {}).get("time_sec"),
        ]
        if v is not None
    )

    return {
        "dataset": dataset_tag,
        "batch_size": cfg.get("batch_size"),
        "heap": heap_tag,
        "quantization": cfg.get("quantization"),
        "store_vectors_in_graph": cfg.get("store_vectors_in_graph"),
        "add_hierarchy": cfg.get("add_hierarchy"),
        "max_connections": cfg.get("max_connections"),
        "beam_width": cfg.get("beam_width"),
        "overquery_factor": cfg.get("overquery_factor"),
        "load_corpus_s": phases.get("load_corpus", {}).get("time_sec"),
        "load_corpus_rss_mb": phases.get("load_corpus", {}).get("rss_delta_mb"),
        "ingest_s": phases.get("ingest", {}).get("time_sec"),
        "ingest_rss_mb": phases.get("ingest", {}).get("rss_delta_mb"),
        "create_index_s": create_phase.get("time_sec"),
        "create_index_rss_mb": create_phase.get("rss_delta_mb"),
        "warmup_s": phases.get("warmup", {}).get("time_sec"),
        "warmup_rss_mb": phases.get("warmup", {}).get("rss_delta_mb"),
        "build_graph_now_s": phases.get("build_graph_now", {}).get("time_sec"),
        "build_graph_now_rss_mb": phases.get("build_graph_now", {}).get("rss_delta_mb"),
        "search_s": phases.get("search", {}).get("time_sec"),
        "search_rss_mb": phases.get("search", {}).get("rss_delta_mb"),
        "close_db_s": phases.get("close_db", {}).get("time_sec"),
        "close_db_rss_mb": phases.get("close_db", {}).get("rss_delta_mb"),
        "open_db_s": phases.get("open_db", {}).get("time_sec"),
        "open_db_rss_mb": phases.get("open_db", {}).get("rss_delta_mb"),
        "warmup_after_reopen_s": phases.get("warmup_after_reopen", {}).get("time_sec"),
        "warmup_after_reopen_rss_mb": phases.get("warmup_after_reopen", {}).get(
            "rss_delta_mb"
        ),
        "search_after_reopen_s": phases.get("search_after_reopen", {}).get("time_sec"),
        "search_after_reopen_rss_mb": phases.get("search_after_reopen", {}).get(
            "rss_delta_mb"
        ),
        "recall@50_before_close": recall_before.get("mean"),
        "recall@50_after_reopen": recall_after.get("mean"),
        "latency_ms_mean_before_close": latency_before.get("mean"),
        "latency_ms_mean_after_reopen": latency_after.get("mean"),
        "total_duration": total_duration,
        "db_size_mb": data.get("db_size_mb"),
        "peak_rss_mb": _peak_rss(phases),
    }


def load_dataframe(root: Path) -> pd.DataFrame:
    rows = []
    for p in find_results(root):
        try:
            rows.append(parse_record(p))
        except Exception as exc:  # pragma: no cover
            print(f"Skip {p}: {exc}")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    num_cols = [
        "max_connections",
        "beam_width",
        "overquery_factor",
        "batch_size",
        "load_corpus_s",
        "load_corpus_rss_mb",
        "ingest_s",
        "ingest_rss_mb",
        "create_index_s",
        "create_index_rss_mb",
        "build_graph_now_s",
        "build_graph_now_rss_mb",
        "warmup_s",
        "warmup_rss_mb",
        "search_s",
        "search_rss_mb",
        "close_db_s",
        "close_db_rss_mb",
        "open_db_s",
        "open_db_rss_mb",
        "warmup_after_reopen_s",
        "warmup_after_reopen_rss_mb",
        "search_after_reopen_s",
        "search_after_reopen_rss_mb",
        "recall@50_before_close",
        "recall@50_after_reopen",
        "latency_ms_mean_before_close",
        "latency_ms_mean_after_reopen",
        "peak_rss_mb",
        "total_duration",
        "db_size_mb",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def df_to_markdown(df: pd.DataFrame) -> str:
    cols = [
        "heap",
        "quantization",
        "store_vectors_in_graph",
        "add_hierarchy",
        "max_connections",
        "beam_width",
        "overquery_factor",
        "batch_size",
        "load_corpus_s",
        "load_corpus_rss_mb",
        "ingest_s",
        "ingest_rss_mb",
        "create_index_s",
        "create_index_rss_mb",
        "build_graph_now_s",
        "build_graph_now_rss_mb",
        "warmup_s",
        "warmup_rss_mb",
        "search_s",
        "search_rss_mb",
        "recall@50_before_close",
        "close_db_s",
        "close_db_rss_mb",
        "open_db_s",
        "open_db_rss_mb",
        "warmup_after_reopen_s",
        "warmup_after_reopen_rss_mb",
        "search_after_reopen_s",
        "search_after_reopen_rss_mb",
        "recall@50_after_reopen",
        "peak_rss_mb",
        "db_size_mb",
        "total_duration",
    ]
    df = df.loc[:, cols].copy()
    for c in cols:
        if c not in df.columns:
            continue
        if c in ("quantization", "store_vectors_in_graph", "add_hierarchy", "heap"):
            continue
        if c in ("recall@50_before_close", "recall@50_after_reopen"):
            df[c] = df[c].round(4)
        elif c != "total_duration":
            df[c] = df[c].round(3)
    if "total_duration" in df.columns:
        df["total_duration"] = df["total_duration"].apply(format_duration)
    return df.to_markdown(index=False)


def write_markdown(df: pd.DataFrame, dataset: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"arcadedb_msmarco_{dataset}.md"
    header = f"# ArcadeDB MSMARCO {dataset} (1000 queries, Recall@{EVAL_K})\n"
    body = df_to_markdown(df)
    md_path.write_text(f"{header}\n{body}\n")
    print(f"Wrote {md_path}")


def main() -> None:
    df = load_dataframe(ROOT)
    if df.empty:
        print("No results found.")
        return

    for dataset, sub in df.groupby("dataset"):
        sub = sub.sort_values(
            [
                "recall@50_after_reopen",
                "search_after_reopen_s",
            ],
            ascending=[False, True],
        )
        write_markdown(sub, dataset, OUT_DIR)


if __name__ == "__main__":
    main()
