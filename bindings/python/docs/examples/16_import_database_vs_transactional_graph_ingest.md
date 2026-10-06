# Example 16: Import Database vs Transactional Graph Ingest

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/16_import_database_vs_transactional_graph_ingest.py){ .md-button }

This example compares four graph-ingest strategies against the same generated vertex
and edge dataset shape.

## Overview

Example 16 is the graph-ingest comparison harness for embedded Python.

- Generates synthetic graph CSV data for vertices and edges
- Runs four ingest modes:
    - transactional SQL vertex and edge creation
    - embedded `GraphBatch`
    - async SQL vertex and edge creation, pinned to one worker
    - SQL `IMPORT DATABASE`
- Checks final vertex and edge count parity before trusting the timing result

## Current Repository Guidance

- This example exists because ingest winners are workload-dependent
- `GraphBatch` is the repository's recommended bulk graph ingest path from Python
- `IMPORT DATABASE` is not the recommendation: its behavior varies by import path and
  data shape, `commitEvery` transaction splitting has not behaved as expected in some
  CSV-heavy runs, and very large imports can still hit transaction-buffer limits. Use it
  when its file-driven workflow is what you need, and when you have measured it on your own
  data
- Async SQL is a comparison arm only, and it is not a bulk graph ingest path

!!! warning "Why the async arm accepts only `--async-parallel 1`"

    Before 26.10.1, `async_executor().command(...)` could silently drop records above
    parallel level 1 (`ArcadeData/arcadedb#7615`, fixed in #7625); see
    [Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation).
    `run_async_sql_graph_load(...)` therefore raises `ValueError` for any
    `--async-parallel` other than 1, and counts stored vertices and edges against
    submitted vertices and edges so a short load fails instead of being reported as a
    fast one.

    `GraphBatch` flushes its edges through that same executor and is measured exact,
    with `parallel_flush` on or off.

## Run

From `bindings/python/examples`:

```bash
python 16_import_database_vs_transactional_graph_ingest.py \
  --vertices 100000 \
  --edges 300000 \
  --vertex-int-props 6 \
  --vertex-str-props 4 \
  --edge-int-props 2 \
  --edge-str-props 1 \
  --string-size 64 \
  --batch-size 10000 \
  --async-parallel 1 \
  --parallel 1 \
  --heap-size 4g
```

## Key Options

- `--vertices`: number of generated vertices
- `--edges`: number of generated edges
- `--vertex-int-props` / `--vertex-str-props`: vertex property counts
- `--edge-int-props` / `--edge-str-props`: edge property counts
- `--string-size`: generated string payload size
- `--batch-size`: ingest batch size
- `--async-parallel`: async SQL worker count; only `1` is accepted (see the warning above)
- `--parallel`: SQL import worker count and GraphBatch parallel-flush toggle
- `--heap-size`: JVM heap size

## Parity Semantics

Timing comparisons only matter if all four modes produce matching final vertex and edge
counts.
