#!/usr/bin/env python3
"""
Quick mock vector search over the generated embeddings.

- Supports single memmaps or sharded outputs (msmarco-passages-<label>.shardXXXX.f32).
- Uses corpus-sampled queries from the GT JSONL (query_id is a global row index).
- Computes top-k via shard+chunk streaming and per-query heaps to bound memory.

Usage:
    python mock_search.py --datasets datasets/MSMARCO-10M --k 50 --limit-queries 3
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import re
from pathlib import Path
from typing import List, Tuple

import numpy as np

META_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.meta\.json")
GT_FILENAME_RE = re.compile(r"msmarco-passages-(.+?)\.gt")


def infer_rows(npy_path: Path, dim: int) -> int:
    byte_size = os.path.getsize(npy_path)
    elem_count = byte_size // 4  # float32
    return elem_count // dim


def load_queries(gt_path: Path, limit: int | None) -> List[int]:
    query_ids: List[int] = []
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and len(query_ids) >= limit:
                break
            obj = json.loads(line)
            query_ids.append(int(obj["query_id"]))
    return query_ids


def _match_label(pattern: re.Pattern[str], name: str) -> str | None:
    match = pattern.match(name)
    if match:
        return match.group(1)
    return None


def _sort_key(path: Path, pattern: re.Pattern[str]) -> tuple[int, object]:
    label = _match_label(pattern, path.name)
    if label is None:
        return (2, path.name)
    if label.isdigit():
        return (0, int(label))
    return (1, label)


def resolve_dataset_inputs(
    dataset_dir: Path,
) -> tuple[Path, Path, str | None, int | None]:
    if not dataset_dir.is_dir():
        raise SystemExit(f"{dataset_dir} is not a directory")

    meta_files = sorted(
        dataset_dir.glob("msmarco-passages-*.meta.json"),
        key=lambda p: _sort_key(p, META_FILENAME_RE),
    )
    if not meta_files:
        raise SystemExit(
            "No dataset metadata (.meta.json) found in the specified directory"
        )

    meta_path = meta_files[-1]
    label = _match_label(META_FILENAME_RE, meta_path.name)
    meta = json.loads(meta_path.read_text())
    dim = meta.get("dim")

    gt_path = None
    if label:
        candidate = dataset_dir / f"msmarco-passages-{label}.gt.jsonl"
        if candidate.exists():
            gt_path = candidate

    if gt_path is None:
        gt_candidates = sorted(
            dataset_dir.glob("msmarco-passages-*.gt.jsonl"),
            key=lambda p: _sort_key(p, GT_FILENAME_RE),
        )
        if not gt_candidates:
            raise SystemExit("No GT jsonl file found in the specified directory")
        gt_path = gt_candidates[-1]
        label = label or _match_label(GT_FILENAME_RE, gt_path.name)

    return dataset_dir, gt_path, label, dim


def discover_sources(
    emb: Path, dim: int, label: str | None = None
) -> Tuple[List[dict], int]:
    """Return list of shard specs with path/start/count and total rows.

    - If emb is a directory, use files matching the label-specific pattern if provided, otherwise all msmarco-passages-*.shard*.f32 (fallback to .npy).
    - If emb is a shard file or single npy/f32, use that one file.
    """
    sources: List[dict] = []
    total = 0

    candidates: List[Path]
    if emb.is_dir():
        pattern = (
            "msmarco-passages-*.shard*.f32"
            if label is None
            else f"msmarco-passages-{label}.shard*.f32"
        )
        candidates = sorted(emb.glob(pattern))
        if not candidates:
            fallback = (
                "msmarco-passages-*.shard*.npy"
                if label is None
                else f"msmarco-passages-{label}.shard*.npy"
            )
            candidates = sorted(emb.glob(fallback))
        if not candidates:
            candidates = sorted(emb.glob("*.f32")) or sorted(emb.glob("*.npy"))
    else:
        candidates = [emb]

    for path in candidates:
        rows = infer_rows(path, dim)
        sources.append({"path": path, "start": total, "count": rows})
        total += rows

    return sources, total


def materialize_queries(
    sources: List[dict], query_ids: List[int], dim: int
) -> np.ndarray:
    queries = np.empty((len(query_ids), dim), dtype=np.float32)

    # Map queries to shards
    shard_map: dict[Path, List[Tuple[int, int]]] = {}
    for qi, qid in enumerate(query_ids):
        for s in sources:
            start = s["start"]
            end = start + s["count"]
            if start <= qid < end:
                shard_map.setdefault(s["path"], []).append((qi, qid - start))
                break

    for s in sources:
        assigns = shard_map.get(s["path"])
        if not assigns:
            continue
        mm = np.memmap(s["path"], mode="r", dtype=np.float32, shape=(s["count"], dim))
        for qi, local_idx in assigns:
            queries[qi] = mm[local_idx]
        del mm

    return queries


def streaming_topk(
    sources: List[dict],
    queries: np.ndarray,
    k: int,
    chunk: int,
) -> List[List[Tuple[int, float]]]:
    q_count, dim = queries.shape
    heaps: List[List[Tuple[float, int]]] = [[] for _ in range(q_count)]

    for s in sources:
        mm = np.memmap(s["path"], mode="r", dtype=np.float32, shape=(s["count"], dim))
        for start in range(0, s["count"], chunk):
            end = min(start + chunk, s["count"])
            block = mm[start:end]
            sims = block @ queries.T  # (block_size, q_count)
            for qi in range(q_count):
                col = sims[:, qi]
                heap = heaps[qi]
                for i, score in enumerate(col):
                    doc_id = s["start"] + start + i
                    if len(heap) < k:
                        heapq.heappush(heap, (score, doc_id))
                    else:
                        heapq.heappushpop(heap, (score, doc_id))
        del mm

    results: List[List[Tuple[int, float]]] = []
    for heap in heaps:
        hits = sorted(heap, key=lambda x: x[0], reverse=True)
        results.append([(doc_id, float(score)) for score, doc_id in hits])
    return results


def main():
    ap = argparse.ArgumentParser(description="Mock vector search over MSMARCO memmaps")
    ap.add_argument(
        "--datasets",
        help="Directory that contains msmarco-passages-*.shard*.f32, meta.json, and gt.jsonl",
    )
    ap.add_argument(
        "--emb",
        help="Path to the embeddings npy or directory containing shard*.npy (legacy)",
    )
    ap.add_argument("--gt", help="Path to GT jsonl (for query IDs, legacy)")
    ap.add_argument("--k", type=int, default=50, help="Top-k to retrieve")
    ap.add_argument(
        "--limit-queries", type=int, default=3, help="Number of queries to run"
    )
    ap.add_argument(
        "--chunk", type=int, default=50_000, help="Chunk size for dot products"
    )
    ap.add_argument("--dim", type=int, default=1024, help="Embedding dimension")
    args = ap.parse_args()

    dim = args.dim
    emb_path: Path
    gt_path: Path
    label: str | None = None

    if args.datasets:
        emb_path, gt_path, label, dataset_dim = resolve_dataset_inputs(
            Path(args.datasets)
        )
        if dataset_dim is not None:
            dim = dataset_dim
        print(
            f"[dataset] using {args.datasets} | gt={gt_path.name} | dim={dim} | label={label or 'unknown'}"
        )
    else:
        if not args.emb or not args.gt:
            ap.error("Provide either --datasets or both --emb and --gt")
        emb_path = Path(args.emb)
        gt_path = Path(args.gt)
        label = infer_label_from_gt_path(gt_path)

    sources, total = discover_sources(emb_path, dim, label=label)
    if not sources or total == 0:
        print("No embeddings found.")
        return

    query_ids = load_queries(gt_path, args.limit_queries)
    if not query_ids:
        print("No queries found in GT file.")
        return

    # filter out-of-range queries
    query_ids = [qid for qid in query_ids if qid < total]
    if not query_ids:
        print("All queries out of range for embeddings.")
        return

    queries = materialize_queries(sources, query_ids, dim)

    print(f"Loaded embeddings: {total}x{dim} across {len(sources)} file(s)")
    print(f"Running {len(query_ids)} queries, k={args.k}, chunk={args.chunk}")

    results = streaming_topk(sources, queries, k=args.k, chunk=args.chunk)

    for qi, qid in enumerate(query_ids):
        hits = results[qi]
        if not hits:
            print(f"query_id={qid} no hits")
            continue
        print(f"query_id={qid} topk={hits}")


if __name__ == "__main__":
    main()
