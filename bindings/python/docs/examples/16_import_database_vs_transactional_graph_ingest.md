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
- `IMPORT DATABASE` with `--parallel 4` was the fastest arm on the 5M/5M benchmark
  shape below, and `GraphBatch` with `--parallel 4` was the fastest non-import arm.
  Fastest here does not make `IMPORT DATABASE` the recommendation: its behavior varies
  by import path and data shape, `commitEvery` transaction splitting has not behaved as
  expected in some CSV-heavy runs, and very large imports can still hit
  transaction-buffer limits. Use it when its file-driven workflow is what you need, and
  when you have measured it on your own data
- Async SQL is a comparison arm only, and it is not a bulk graph ingest path

!!! warning "Why the async arm accepts only `--async-parallel 1`"

    The async executor's SQL command path, `db.async_executor().command(...)`, silently
    discards records once the parallel level is above 1. Observed on arcadedb-engine
    26.9.1 and 26.6.1, measured 2026-09-15. How much is lost varies by run and by
    workload shape: 9,742 single-record `INSERT` commands submitted at parallel level 4
    stored 2,436, 5,742, and 7,742 rows across runs. No error reaches the per-command
    callback, nothing is
    logged, and `wait_completion()` returns normally. Only the executor-wide `on_error`
    handler sees anything, one `ConcurrentModificationException` per rolled-back batch.
    At parallel level 1 nothing is lost. Filed upstream as `ArcadeData/arcadedb#7615`.

    `run_async_sql_graph_load(...)` therefore raises `ValueError` for any
    `--async-parallel` other than 1, and counts stored vertices and edges against
    submitted vertices and edges so a short load fails instead of being reported as a
    fast one.

    `GraphBatch` flushes its edges through that same executor and is measured exact,
    with `parallel_flush` on or off.

## Recent Benchmark Snapshot

For this shape:

- `vertices=5,000,000`
- `edges=5,000,000`
- `vertex-int-props=10`
- `vertex-str-props=10`
- `edge-int-props=10`
- `edge-str-props=10`
- `string-size=64`
- `batch-size=10,000`
- `heap-size=8g`

Measured times:

- `Transactional` (`1 thread`): `575.078s`
- `Async SQL` (`--async-parallel 1`): `701.080s`
- `GraphBatch` (`--parallel 1`): `507.983s`
- `GraphBatch` (`--parallel 4`): `359.672s`
- `IMPORT DATABASE` (`--parallel 1`): `453.481s`
- `IMPORT DATABASE` (`--parallel 4`): `275.325s`

All four methods produced the same final graph output for this benchmark shape.

The `Async SQL` figure was measured at one worker, which is the only level the arm now
accepts, so it is still a valid time for the work it describes.

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
- `--async-parallel`: async SQL worker count; only `1` is accepted (#7615)
- `--parallel`: SQL import worker count and GraphBatch parallel-flush toggle
- `--heap-size`: JVM heap size

## Parity Semantics

Timing comparisons only matter if all four modes produce matching final vertex and edge
counts.
