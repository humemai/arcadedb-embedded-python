# GraphBatch API

The `GraphBatch` helper exposes ArcadeDB's high-throughput graph-ingest path from Python.

## Overview

Use `GraphBatch` when you need to load many vertices and edges efficiently.

This is the repository's current recommended bulk graph-ingest path from Python.

You typically create it through `db.graph_batch(...)` rather than constructing the class directly.

## Entry Point

### `db.graph_batch(...) -> GraphBatch`

Create a configured batch helper tied to the current database.

**Common options:**

- `batch_size`: buffered edge batch size before flush
- `expected_edge_count`: sizing hint for large runs
- `light_edges`: create property-less light edges when appropriate
- `commit_every`: commit cadence during batch work
- `use_wal`: enable WAL for stronger durability
- `wal_flush`: flush policy such as `no`, `yes_nometadata`, `yes_full`
- `parallel_flush`: flush deferred work in parallel

**Example:**

```python
with db.graph_batch(batch_size=1000, expected_edge_count=50000) as batch:
    alice = batch.create_vertex("Person", name="Alice")
    bob = batch.create_vertex("Person", name="Bob")
    batch.new_edge(alice, "Knows", bob, since=2024)
```

## Common Operations

### `create_vertex(type_name, **properties)`

Create and persist a single vertex.

### `create_vertices(type_name, count_or_properties)`

Create many vertices efficiently and return their RIDs.

### `new_edge(source, edge_type, destination, **properties)`

Buffer an edge for creation during flush/close.

### `flush()`

Force buffered edge work to disk early.

### `close()`

Flush remaining work and finalize the batch.

### Counters

The helper also exposes counters such as:

- `get_total_edges_created()`
- `get_buffered_edge_count()`
- `get_deferred_incoming_edge_count()`

## Notes

- Prefer `GraphBatch` over importer-based graph loading for Python-managed bulk ingest.
- `wal_flush` validation is intentionally strict and raises `ValueError` for invalid modes.
- See the graph-ingest examples and tests for realistic usage patterns.
