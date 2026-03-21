# Example 13: Stack Overflow Hybrid Queries

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/13_stackoverflow_hybrid_queries.py){ .md-button }

This example builds a standalone Stack Overflow pipeline combining document tables,
property graph data, embeddings, vector indexes, and hybrid queries.

## Overview

Example 13 runs four phases:

1. XML to document tables
2. XML to graph
3. Embeddings plus vector indexes on Question, Answer, and Comment
4. Hybrid queries combining SQL, OpenCypher, and vector search

## Current Repository Guidance

- The script is intentionally standalone and does not use Docker
- Phase 1 uses async SQL insert for document-table preload
- Keep that Phase 1 preload on a single async worker; do not rely on multi-threaded
  async insert for this workload in the current Python examples
- Phase 2 uses `GraphBatch` for the initial graph node and edge load
- `GraphBatch` is the repository's recommended bulk graph ingest path from Python
- Graph edge creation uses RID-based directed endpoints
- Traversal semantics are directional

## Run

From `bindings/python/examples`:

```bash
python 13_stackoverflow_hybrid_queries.py \
  --dataset stackoverflow-tiny \
  --batch-size 10000 \
  --encode-batch-size 256 \
  --model all-MiniLM-L6-v2 \
  --heap-size 4g \
  --top-k 10
```

## Key Options

- `--dataset`: dataset size from `stackoverflow-tiny` through `stackoverflow-full`
- `--batch-size`: load batch size
- `--encode-batch-size`: embedding batch size
- `--model`: sentence-transformers model name
- `--heap-size`: JVM heap size
- `--top-k`: hybrid/vector result count
- `--candidate-limit`: candidate pool size for hybrid ranking
