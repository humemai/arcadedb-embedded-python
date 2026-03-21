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
    - async SQL vertex and edge creation
    - SQL `IMPORT DATABASE`
- Checks final vertex and edge count parity before trusting the timing result

## Current Repository Guidance

- This example exists because ingest winners are workload-dependent
- Current results show that `GraphBatch` is the best bulk graph ingest option in this
  repository
- Async SQL is still useful as a baseline comparison, but it is not the recommended
  bulk graph ingest path here
- SQL `IMPORT DATABASE` remains available, but it is not the preferred graph bulk-load
  path from Python

## Recent Benchmark Snapshot

For this shape:

- `vertices=2,000,000`
- `edges=2,000,000`
- `vertex-int-props=10`
- `vertex-str-props=10`
- `edge-int-props=10`
- `edge-str-props=10`
- `string-size=64`
- `batch-size=10,000`
- `heap-size=8g`

Measured times:

- `Transactional` (`single-threaded`): `253.615s`
- `GraphBatch` (`--parallel 1`): `177.150s`
- `GraphBatch` (`--parallel 4`): `187.681s`
- `GraphBatch` (`--parallel 8`): `134.836s`
- `Async SQL` (`--async-parallel 1`): `230.192s`
- `IMPORT DATABASE` (`--parallel 1`): `444.357s`
- `IMPORT DATABASE` (`--parallel 4`): `336.206s`

This is why the broader graph example set now treats `GraphBatch` as the default bulk
graph ingest path from Python.

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
- `--async-parallel`: async SQL worker count
- `--parallel`: SQL import worker count and GraphBatch parallel-flush toggle
- `--heap-size`: JVM heap size

## Parity Semantics

Timing comparisons only matter if all four modes produce matching final vertex and edge
counts.
