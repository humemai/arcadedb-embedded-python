# Example 13: Stack Overflow Hybrid Queries

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/13_stackoverflow_hybrid_queries.py){ .md-button }

This example builds a standalone Stack Overflow pipeline combining document tables,
property graph data, embeddings, vector indexes, hybrid queries, and a derived
time-series activity layer.

## Overview

Example 13 runs five phases:

1. XML to document tables
2. XML to graph
3. Embeddings plus vector indexes on Question, Answer, and Comment
4. Hybrid queries combining SQL, OpenCypher, and vector search
5. Derived time-series analytics from existing timestamped events

## Current Repository Guidance

- The script is intentionally standalone and does not use Docker
- Phase 1 uses async SQL insert for document-table preload
- Keep that Phase 1 preload on a single async worker; do not rely on multi-threaded
  async insert for this workload in the current Python examples
- Phase 2 uses `GraphBatch` for the initial graph node and edge load
- `GraphBatch` is the repository's recommended bulk graph ingest path from Python
- Graph edge creation uses RID-based directed endpoints
- Traversal semantics are directional
- Phase 5 does not replace the document or graph models; it builds a compact
  `ActivitySeries` projection from existing `CreationDate` / `Date` fields

## Run

From `bindings/python/examples`:

```bash
python 13_stackoverflow_hybrid_queries.py \
  --dataset stackoverflow-tiny \
  --batch-size 10000 \
  --encode-batch-size 256 \
  --model all-MiniLM-L6-v2 \
  --heap-size 4g \
  --top-k 10 \
  --timeseries-top-tags 5
```

## Key Options

- `--dataset`: dataset size from `stackoverflow-tiny` through `stackoverflow-full`
- `--batch-size`: load batch size
- `--encode-batch-size`: embedding batch size
- `--model`: sentence-transformers model name
- `--heap-size`: JVM heap size
- `--top-k`: hybrid/vector result count
- `--candidate-limit`: candidate pool size for hybrid ranking
- `--timeseries-top-tags`: number of top tags projected into the derived
  time-series activity layer

## Time-Series Layer

The script now adds a compact derived TimeSeries type after the main hybrid phases:

- `ActivitySeries`
- timestamp: daily bucket timestamp
- tags: `event_type`, `scope`, `tag`
- fields: `event_count`, `total_score`, `avg_score`

The source data comes from the timestamps already present on:

- `Question.CreationDate`
- `Answer.CreationDate`
- `Comment.CreationDate`
- `Badge.Date`

That means the example stays faithful to the Stack Overflow domain model while also
demonstrating how ArcadeDB can project graph/document events into a time-series view
for trend analysis.
