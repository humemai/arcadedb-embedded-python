# GraphBatch API

The `GraphBatch` helper exposes ArcadeDB's high-throughput graph-ingest path from Python.

## Overview

Use `GraphBatch` when you need to load many vertices and edges efficiently.

This is the repository's current recommended bulk graph-ingest path from Python, and
the reason is not only throughput. The alternative of submitting per-record SQL through
`db.async_executor().command(...)` silently discarded records above parallel level 1
before 26.10.1 (`ArcadeData/arcadedb#7615`, fixed in #7625: a failed periodic commit is
now retried and otherwise reported through the error callback). `GraphBatch` dispatches
its edge flush through that same
executor and is measured exact: 20,000 vertices and 40,000 edges landed in full, with
and without `parallel_flush`.

You typically create it through `db.graph_batch(...)` rather than constructing the class directly.

## Entry Point

### `db.graph_batch(...) -> GraphBatch`

Create a configured batch helper tied to the current database.

**Common options:**

- `batch_size`: buffered edge batch size before flush; usually leave it unset and
  give `expected_edge_count` instead
- `expected_edge_count`: the number of edges you are about to load; with no
  `batch_size`, the batch size is tuned to it (clamped to 100,000-5,000,000), and
  a single flush is the optimal shape
- `light_edges`: create property-less light edges when appropriate
- `commit_every`: commit cadence during batch work
- `use_wal`: write-ahead log during the import. **Off by default**: a crash in
  the middle of the import can lose its tail, with nothing to replay. Pass
  `use_wal=True` for an import that must survive a crash
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

**Recommended settings for a crash-safe bulk load** (ArcadeDB's maintainers,
`ArcadeData/arcadedb#8287`): `use_wal=True` and `expected_edge_count`, with
`batch_size`, `commit_every`, and `parallel_flush` left at their defaults
(`commit_every` is 50,000 with the WAL on and one commit per flush with it off;
`parallel_flush` is on). Measured on 26.10.1-dev with 50,000 vertices and
1,045,738 edges: about 7.5 s with the WAL on, against about 30 s for the same
graph through `newVertex`/`newEdge` one element at a time. The size hint made
no measurable difference at that size. The same options exist for a server as
query parameters of `POST /api/v1/batch/{db}` (`wal=true`,
`expectedEdgeCount=...`), the served bulk path.

**Example:**

```python
with db.graph_batch(use_wal=True, expected_edge_count=50000) as batch:
    alice = batch.create_vertex("Person", name="Alice")
    bob = batch.create_vertex("Person", name="Bob")
    batch.new_edge(alice, "Knows", bob, since=2024)
```

## Common Operations

### `create_vertex(type_name, **properties)`

Create and persist a single vertex.

### `create_vertices(type_name, count_or_properties)`

Create many vertices efficiently and return their RIDs.

**Vector properties: pass `to_java_float_array(vec)`, not a Python list.** A plain
list of floats is JSON-representable, so it takes the JSON bulk path, and for a
vector that path is the slow one: 100,000 vectors of 128 floats loaded at 3.6k
vectors/s as lists against 31k/s as `to_java_float_array` values, 8.6x (measured
2026-09-24 on 26.10.1-dev, same data, stored vectors identical). The list form
was also slower than inserting one vector per `db.command(...)`.

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
