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

A database runs one `GraphBatch` at a time: while one is open, `db.graph_batch(...)`
raises `ArcadeDBError` ("A GraphBatch is already in progress on this database"). Close
the open batch first, or use one batch with `parallel_flush` for parallel work.

## Entry Point

### `db.graph_batch(...) -> GraphBatch`

Create a configured batch helper tied to the current database.

**Common options:**

- `batch_size`: buffered edge batch size before flush; usually leave it unset and
  give `expected_edge_count` instead
- `expected_edge_count`: the number of edges you are about to load; with no
  `batch_size`, the batch size is tuned to it (clamped to 100,000-5,000,000), and
  a single flush is the optimal shape
- `edge_list_initial_size`: initial size in bytes of each vertex's edge segment
- `light_edges`: create property-less light edges when appropriate
- `bidirectional`: store each edge on both vertices (the default) or on its source only.
  Pass `False` only for an edge type declared one-way (`CREATE EDGE TYPE ...
  UNIDIRECTIONAL`). From 26.10.1 a one-way edge in a two-way type (the default
  `CREATE EDGE TYPE`) is refused: `new_edge` raises `ArcadeDBError` naming the type and
  writes nothing. Before 26.10.1 it was accepted, and every query the planner walked from
  the target end returned 0 rows with no error (ArcadeData/arcadedb#8625). What a one-way
  edge is visible to is in [Graphs](../guide/graphs.md)
- `commit_every`: commit cadence during batch work
- `use_wal`: write-ahead log during the import. **Off by default**: a crash in
  the middle of the import can lose its tail, with nothing to replay. Pass
  `use_wal=True` for an import that must survive a crash
- `wal_flush`: flush policy such as `no`, `yes_nometadata`, `yes_full`
- `pre_allocate_edge_chunks`: allocate the edge chunks when `create_vertex()` creates
  the vertex
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

## Transactions

Call the batch outside your own transactions. `create_vertices()`, `flush()`, and `close()`
commit the transaction that is open on the thread, yours included, and so do `new_edge()`
and `new_edges()` when the buffer reaches `batch_size` and flushes. Leaving a
`with db.graph_batch()` block calls `close()`. This is ArcadeDB
[#9242](https://github.com/ArcadeData/arcadedb/issues/9242), open; see
[Known Engine Issues](../guide/known-issues.md) for what it does to a transaction of yours.
Commit your own writes before the batch's first call, or write them after it closes:

```python
with db.transaction():
    db.new_document("Note").set("text", "mine").save()

with db.graph_batch() as batch:
    rids = batch.create_vertices("Person", [{"id": i} for i in range(1000)])
    batch.new_edges(rids[:-1], "Knows", rids[1:])
```

`create_vertex()` and `new_vertex()` are the exceptions. Inside your transaction,
`create_vertex()` saves the vertex in it and does not commit, so your `rollback()` undoes
both; outside one, it commits its own. `new_edge()` and `new_edges()` with room left in the
buffer only buffer.

While a batch is open, from its first call until `close()`, every commit on that thread uses
the batch's WAL setting, yours too: with the default `use_wal=False`, a transaction of yours
committed in that time writes no WAL record. `close()` restores the previous setting.

## Common Operations

### `create_vertex(type_name, **properties)`

Create and persist a single vertex.

### `new_vertex(type_name)`

Return an unsaved `Vertex` of that type from the batch; set its properties and call
`save()` inside a transaction, and end that transaction before the batch's next call that
commits (see [Transactions](#transactions)).

### `create_vertices(type_name, count_or_properties)`

Create many vertices efficiently and return their RIDs as strings. The call commits, in
the transaction open on the thread if there is one: call it outside your own transactions
(see [Transactions](#transactions)).
`count_or_properties` is either an `int`, the number of vertices to create without
properties, or an iterable of property dicts (`None` or `{}` for a vertex without
properties). Only rows whose values are all scalars (`str`, `int`, `float`, `bool`, or
`None`) take the JSON bulk path, which sends them in chunks of 100,000 rows; a row with
any other value, a list or a Java array included, sends the whole call through the
per-value path, which converts each value on its own. So does a scalar the JSON text would
change on the way to the engine: an integer beyond 64 bits, NaN or Infinity, or a string with
a lone surrogate. The per-value path stores such a value exactly or raises.

**Vector properties: pass `to_java_float_array(vec)`, not a Python list.** A plain
list is converted element by element (and, on a type with no declared vector property,
stored as a `LIST` rather than `ARRAY_OF_FLOATS`): 100,000 vectors of 128 floats loaded
at 3.6k vectors/s as lists against 31k/s as `to_java_float_array` values, 8.6x
(measured 2026-09-24 on 26.10.1-dev, same data, stored vectors identical). The list form
was also slower than inserting one vector per `db.command(...)`.

### `new_edge(source, edge_type, destination, **properties)`

Buffer an edge for creation during flush/close.

!!! note "Declared edge properties before 26.10.1"
    Up to engine 26.9.1 an edge buffered with properties skipped the declared property's
    conversion and the type's constraints: a `None` followed by another property was stored as
    `-1` in an `INTEGER`, and `40000` in a `SHORT` as `-25536`. From 26.10.1 a batched edge
    stores a null as null and converts or refuses a declared value as `Vertex.new_edge` does;
    on an older engine, write edges with declared properties through `Vertex.new_edge`. See
    [Known Engine Issues](../guide/known-issues.md).

### `new_edges(source_rids, edge_type, destination_rids, properties=None)`

Buffer many edges with one JPype crossing per call: the bulk counterpart of
`new_edge`, which pays one boundary crossing per edge. RIDs may be strings
(`"#1:0"`) or objects with a string representation; `properties` is an optional
same-length sequence of per-edge property dicts. When every value is a scalar (`str`,
`int`, `float`, `bool`, or `None`) the call takes the bulk path; any other value,
a list included, sends the whole call through per-edge buffering, and so does a scalar the
JSON text would change (an integer beyond 64 bits, NaN or Infinity, a lone surrogate), which
per-edge buffering stores exactly or refuses. Returns the batch for chaining.

```python
with db.graph_batch(use_wal=False) as batch:
    rids = batch.create_vertices("Person", [{"id": i} for i in range(100)])
    batch.new_edges(rids[:-1], "Knows", rids[1:])
```

### `flush()`

Force buffered edge work to disk early. Commits the transaction open on the thread, yours
included (see [Transactions](#transactions)).

### `close()`

Flush remaining work and finalize the batch. A second `close()` does nothing. Commits the
transaction open on the thread, yours included (see [Transactions](#transactions)).

### Counters

The helper also exposes counters such as:

- `get_total_edges_created()`
- `get_buffered_edge_count()`
- `get_deferred_incoming_edge_count()`

After `close()`, the counters and every other method except `close()` raise
`ArcadeDBError` ("GraphBatch is closed"). Read the counters before the batch closes.

## Notes

- Prefer `GraphBatch` over importer-based graph loading for Python-managed bulk ingest.
- `wal_flush` validation is intentionally strict and raises `ValueError` for invalid modes.
- See the graph-ingest examples and tests for realistic usage patterns.
