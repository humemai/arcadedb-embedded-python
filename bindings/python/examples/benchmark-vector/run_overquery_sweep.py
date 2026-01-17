#!/usr/bin/env python3
"""
Run search-only sweeps on an existing ArcadeDB MSMARCO database to compare
different `overquery_factor` values without rebuilding the index.

For each factor, we:
- load the 1,000 query vectors and ground-truth labels
- open the existing DB
- warm up once
- run a full search pass (recall + latency)
- write results.json / results.md under an output directory that the
  existing summarizer can consume.

Place the outputs under `arcadedb_runs/*/results.json` (default) so
`summarize_arcadedb_msmarco.py` will include them in its markdown tables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import arcadedb_embedded as arcadedb
import numpy as np
from benchmark_arcadedb_msmarco import (
    dir_size_mb,
    load_ground_truth,
    load_queries,
    materialize_queries,
    resolve_dataset,
    rss_mb,
    search_index,
    timed_section,
    warmup,
)


def parse_overqueries(raw: str) -> List[int]:
    vals: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = int(part)
        except ValueError:
            raise SystemExit(f"Invalid overquery value: {part}") from None
        if v <= 0:
            raise SystemExit("overquery values must be positive")
        vals.append(v)
    if not vals:
        raise SystemExit("No overquery values provided")
    return vals


def load_existing_config(db_path: Path) -> Dict:
    cfg: Dict = {}
    res_json = db_path / "results.json"
    if res_json.exists():
        try:
            cfg = json.loads(res_json.read_text()).get("config", {})
        except Exception:
            cfg = {}
    return cfg


def record(
    phases: Dict[str, dict],
    name: str,
    result,
    dur: float,
    rss_start: float,
    rss_end: float,
) -> None:
    phases[name] = {
        "time_sec": dur,
        "rss_before_mb": rss_start,
        "rss_after_mb": rss_end,
        "rss_delta_mb": rss_end - rss_start,
    }
    if isinstance(result, dict):
        phases[name].update(result)


def run_single(
    db_path: Path,
    dataset_dir: Path,
    overquery: int,
    k: int,
    quantization: str,
    output_root: Path,
    tag: str | None,
    base_config: Dict,
) -> Path:
    sources, gt_path, dim, label = resolve_dataset(dataset_dir)
    total_rows = sum(s["count"] for s in sources)
    gt_full = load_ground_truth(gt_path)

    qids = load_queries(gt_path, limit=1000)
    qids = [qid for qid in qids if qid < total_rows][:1000]
    qids = [qid for qid in qids if qid in gt_full][:1000]
    if not qids:
        raise SystemExit("No valid query IDs with ground truth found")

    phases: Dict[str, dict] = {}

    (queries, dur, r0, r1) = timed_section(
        "load_queries", lambda: materialize_queries(sources, qids, dim=dim)
    )
    record(phases, "load_queries", {"queries": len(queries)}, dur, r0, r1)

    (db, dur, r0, r1) = timed_section(
        "open_db", lambda: arcadedb.open_database(str(db_path))
    )
    record(phases, "open_db", {}, dur, r0, r1)

    index = db.schema.get_vector_index("VectorData", "vector")

    (warm_info, dur, r0, r1) = timed_section(
        "warmup",
        lambda: warmup(index, queries, overquery, k, quantization),
    )
    record(phases, "warmup", warm_info, dur, r0, r1)

    (search_stats, dur, r0, r1) = timed_section(
        "search",
        lambda: search_index(
            index,
            queries,
            qids,
            gt_full,
            k=k,
            overquery_factor=overquery,
            quantization=quantization,
        ),
    )
    record(phases, "search", search_stats, dur, r0, r1)

    try:
        (_, dur, r0, r1) = timed_section("close_db_final", lambda: db.close())
        record(phases, "close_db_final", {}, dur, r0, r1)
    except Exception:
        pass

    rss_after_vals = [
        v.get("rss_after_mb")
        for v in phases.values()
        if v.get("rss_after_mb") is not None
    ]
    peak_rss = max(rss_after_vals) if rss_after_vals else None

    recall_stats = {
        "search": {
            "mean": phases.get("search", {}).get("recall_mean"),
            "n": phases.get("search", {}).get("recall_count"),
        },
        "search_after_reopen": {"mean": None, "n": None},
    }

    latency_ms = {
        "search": {
            "mean": phases.get("search", {}).get("latency_ms_mean"),
            "p95": phases.get("search", {}).get("latency_ms_p95"),
        },
        "search_after_reopen": {"mean": None, "p95": None},
    }

    dataset_info = {
        "label": label or "dataset",
        "dim": dim,
        "shards": len(sources),
        "rows": total_rows,
    }

    config_info = {
        **{k: v for k, v in base_config.items() if v is not None},
        "overquery_factor": overquery,
        "quantization": quantization,
        "queries": len(qids),
        "k": k,
    }

    results = {
        "dataset": dataset_info,
        "config": config_info,
        "phases": phases,
        "recall": recall_stats,
        "latency_ms": latency_ms,
        "db_path": str(db_path),
        "db_size_mb": dir_size_mb(db_path),
    }

    run_dir_name_parts = [
        f"dataset={dataset_dir.name}",
        f"label={label or 'dataset'}",
        f"oq={overquery}",
        f"reuse={db_path.name}",
    ]
    if tag:
        run_dir_name_parts.append(f"tag={tag}")
    run_dir = output_root / "_".join(run_dir_name_parts)
    run_dir.mkdir(parents=True, exist_ok=True)

    results_json = run_dir / "results.json"
    results_json.write_text(json.dumps(results, indent=2))

    md_lines = [
        f"# ArcadeDB overquery sweep ({dataset_info['label']})",
        "",
        "## Config",
        f"- overquery_factor: {overquery}",
        f"- quantization: {quantization}",
        f"- k: {k}",
        f"- db_path: {db_path}",
        "",
        "## Recall",
        (
            f"- search: {recall_stats['search']['mean']:.4f} (n={recall_stats['search']['n']})"
            if recall_stats["search"]["mean"] is not None
            else "- search: n/a"
        ),
        "",
        "## Latency (ms)",
        (
            f"- search mean: {latency_ms['search']['mean']:.2f} | p95: {latency_ms['search']['p95']:.2f}"
            if latency_ms["search"]["mean"] is not None
            else "- search: n/a"
        ),
        "",
        "## Phases (time sec / RSS MB)",
    ]

    for name in ("load_queries", "open_db", "warmup", "search", "close_db_final"):
        if name not in phases:
            continue
        p = phases[name]
        line = (
            f"- {name}: time={p['time_sec']:.3f}s, rss_before={p['rss_before_mb']:.1f} MB, "
            f"rss_after={p['rss_after_mb']:.1f} MB, delta={p['rss_delta_mb']:.1f} MB"
        )
        if "recall_mean" in p:
            line += f", recall@{k}={p['recall_mean']:.4f}"
        if "latency_ms_mean" in p and p["latency_ms_mean"] is not None:
            line += f", latency_ms={p['latency_ms_mean']:.2f}"
        md_lines.append(line)

    def fmt(val: float | None) -> str:
        return "nan" if val is None else f"{val:.1f}"

    md_lines.extend(
        [
            "",
            f"- db_size_mb: {fmt(results['db_size_mb'])}",
            f"- peak_rss_mb: {fmt(peak_rss)}",
        ]
    )

    results_md = run_dir / "results.md"
    results_md.write_text("\n".join(md_lines))
    print(f"Wrote {results_json}")
    print(f"Wrote {results_md}")

    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run overquery sweeps against an existing ArcadeDB MSMARCO DB"
    )
    ap.add_argument("--db-path", required=True, help="Path to existing ArcadeDB DB")
    ap.add_argument("--dataset-dir", required=True, help="Path to MSMARCO dataset dir")
    ap.add_argument(
        "--overquery-factors",
        required=True,
        help="Comma-separated overquery values (e.g., 1,2,4,8,16)",
    )
    ap.add_argument(
        "--output-root",
        default="arcadedb_runs",
        help="Where to place per-factor results (default: arcadedb_runs)",
    )
    ap.add_argument("--k", type=int, default=50, help="Top-K for recall/latency")
    ap.add_argument(
        "--quantization",
        choices=["NONE", "INT8", "BINARY", "PRODUCT"],
        help="Override quantization (default: from existing results.json or NONE)",
    )
    ap.add_argument("--tag", help="Optional tag appended to output directory name")

    args = ap.parse_args()

    overqueries = parse_overqueries(args.overquery_factors)
    db_path = Path(args.db_path)
    dataset_dir = Path(args.dataset_dir)
    output_root = Path(args.output_root)

    if not db_path.exists():
        raise SystemExit(f"DB path not found: {db_path}")

    base_config = load_existing_config(db_path)
    quant = (args.quantization or base_config.get("quantization") or "NONE").upper()

    created: List[Path] = []
    for oq in overqueries:
        created.append(
            run_single(
                db_path=db_path,
                dataset_dir=dataset_dir,
                overquery=oq,
                k=args.k,
                quantization=quant,
                output_root=output_root,
                tag=args.tag,
                base_config=base_config,
            )
        )

    print("\nCompleted runs:")
    for p in created:
        print(f"- {p}")


if __name__ == "__main__":
    main()
