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

### 5) retry and memory knobs

Exercises `commit_retries`, `commit_retry_delay_ms`, `chunk_cache_capacity` and
`max_deferred_incoming_edges` on a five-vertex chain. The bounds are set
deliberately tiny (a 2-entry chunk cache, a 1-edge deferred cap) so the bounded
paths are the ones taken. Both are pure accelerators, so the test asserts the
correct answer (5 vertices, 4 edges, and vertex 4 as the only incoming neighbour
of vertex 5); it does not run a second, unbounded load to compare against.

### 6) invalid knob values are rejected

Confirms the four knobs above reach the Java builder, by asserting its own
range validation fires. This is the test that discriminates a wired parameter
from an accepted-and-ignored one, because none of the four changes an
observable result. It asserts on `ArcadeDBError` and the engine's "must be"
wording rather than grepping for the parameter name: an unwired keyword raises
`TypeError: ... unexpected keyword argument 'commit_retries'`, whose message
contains the parameter name, so a name-substring check passes on exactly the
broken code it is meant to catch.

### 7) a one-way edge in a two-way type is refused

`test_graph_batch_refuses_one_way_edges_in_a_two_way_type`: with
`bidirectional=False`, `new_edge` on an edge type declared two-way (the
`CREATE EDGE TYPE` default) raises `ArcadeDBError` naming the type and the word
"bidirectional", and the type holds 0 edges; on a type declared
`UNIDIRECTIONAL` the same batch writes its edge (1). Fails on 26.9.1, which
accepted the edge (ArcadeData/arcadedb#8625).

### 8) what sees a one-way edge

`test_one_way_edges_are_seen_by_patterns_not_by_in`: 50 questions each tagged
twice through a `UNIDIRECTIONAL` type (100 edges). Cypher counts 100 written
from the source, from the target, and undirected; SQL `MATCH` from the target
returns 100 rows; `in()`, `inE()`, `both()`, and `bothE()` from the target
return 0, `out()` from the source 100, and the target vertex's
`get_in_edges()` is empty. Fails on 26.9.1, where the incoming Cypher pattern
returned 0.

### 9) a failed create_vertices leaves no transaction open

`test_graph_batch_create_vertices_failure_rolls_back` (JSON-bulk and
property-matrix paths): two rows with the same key on a unique index make
`create_vertices` raise `ArcadeDBError`, `db.is_transaction_active()` is `False`
afterwards, the batch still creates the next vertex, and an `INSERT` outside any
transaction is refused. Fails before humemai/arcadedb-embedded-python#121, where
the transaction stayed active and the insert was accepted and lost at close.
`test_graph_batch_create_vertices_keeps_the_callers_transaction` checks the other
half: a transaction the caller opened before the call is still active after the
failure. `test_graph_batch_create_vertices_keyboard_interrupt_rolls_back` raises
`KeyboardInterrupt` after the engine's transaction has begun and expects the
rollback to run.

## Why It Matters

`GraphBatch` is the repository's preferred bulk graph-ingest path from Python, so these tests protect the performance-oriented API surface and its configuration validation behavior.
