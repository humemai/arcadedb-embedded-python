# GraphBatch Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph_batch.py){ .md-button }

These tests cover the engine-backed `GraphBatch` helper used for bulk graph ingest.

## Covered Behavior

### 1) create vertices and edges

Creates `Person` vertices through `GraphBatch`, buffers `Knows` edges, and verifies the final outgoing traversal from `Alice`.

### 2) create_vertices returns RIDs

Verifies that `create_vertices(...)` returns RID strings for every requested row, including sparse property rows such as `None`.

### 3) invalid WAL flush mode

Confirms that invalid `wal_flush` values fail early with `ValueError` instead of being silently accepted.

### 4) parallel flush smoke

Exercises `parallel_flush=True` and verifies final vertex and edge counts plus graph connectivity.

## Why It Matters

`GraphBatch` is the repository's preferred bulk graph-ingest path from Python, so these tests protect the performance-oriented API surface and its configuration validation behavior.
