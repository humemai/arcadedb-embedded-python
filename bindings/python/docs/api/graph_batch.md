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
- `commit_retries`: retries for a vertex commit that hits a transient
  `NeedRetryException` (default 10, `0` fails fast)
- `commit_retry_delay_ms`: initial retry back-off, exponential thereafter and
  capped at 10000 ms (default 1000)
- `chunk_cache_capacity`: bound on each OUT/IN head-chunk RID cache, which keeps
  memory flat on a long-lived stream (default 1,000,000)
- `max_deferred_incoming_edges`: buffered deferred incoming edges before the
  connection pass runs early from `flush()` instead of once at `close()`
  (default 5,000,000, `0` defers everything to close)

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

### `new_edges(source_rids, edge_type, destination_rids, properties=None)`

Buffer many edges with one JPype crossing per call — the bulk counterpart of
`new_edge`, which pays one boundary crossing per edge. RIDs may be strings
(`"#1:0"`) or objects with a string representation; `properties` is an optional
same-length sequence of per-edge property dicts (JSON-representable values take
the bulk path, anything else falls back to per-edge buffering). Returns the
batch for chaining.

```python
with db.graph_batch(use_wal=False) as batch:
    rids = batch.create_vertices("Person", [{"id": i} for i in range(100)])
    batch.new_edges(rids[:-1], "Knows", rids[1:])
```

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
