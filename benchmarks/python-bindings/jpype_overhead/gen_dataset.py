"""Generate the shared, deterministic vector dataset for the JPype-overhead benchmark.

Writes raw little-endian float32 files readable byte-identically from Java and
Python, mimicking VectorSearchLatencyBenchmark.generateClusteredVectors: cluster
centers plus gaussian noise, L2-normalized (COSINE similarity index).

Usage: uv run python gen_dataset.py <out_dir> [num_vectors] [dimensions]
"""

import json
import sys
from pathlib import Path

import numpy as np

SEED = 20260704
NUM_CLUSTERS = 100
NUM_QUERIES_WARMUP = 20
NUM_QUERIES_MEASURED = 100
K = 50
EF_SEARCH = 100


def generate(out_dir: Path, num_vectors: int, dims: int) -> None:
    rng = np.random.default_rng(SEED)
    centers = rng.standard_normal((NUM_CLUSTERS, dims), dtype=np.float32)

    assignments = rng.integers(0, NUM_CLUSTERS, size=num_vectors)
    vectors = centers[assignments] + 0.1 * rng.standard_normal(
        (num_vectors, dims), dtype=np.float32
    )
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    n_queries = NUM_QUERIES_WARMUP + NUM_QUERIES_MEASURED
    q_assign = rng.integers(0, NUM_CLUSTERS, size=n_queries)
    queries = centers[q_assign] + 0.1 * rng.standard_normal(
        (n_queries, dims), dtype=np.float32
    )
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    vectors.astype("<f4").tofile(out_dir / "vectors.bin")
    queries.astype("<f4").tofile(out_dir / "queries.bin")
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "num_vectors": num_vectors,
                "dimensions": dims,
                "num_queries_warmup": NUM_QUERIES_WARMUP,
                "num_queries_measured": NUM_QUERIES_MEASURED,
                "k": K,
                "ef_search": EF_SEARCH,
                "seed": SEED,
            },
            indent=2,
        )
    )
    print(f"wrote {num_vectors}x{dims} vectors + {n_queries} queries to {out_dir}")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 100_000
    d = int(sys.argv[3]) if len(sys.argv) > 3 else 384
    generate(out, n, d)
