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
paths are the ones taken; since both are pure accelerators, the assertion is
that the answer is identical either way.

### 6) invalid knob values are rejected

Confirms the four knobs above reach the Java builder, by asserting its own
range validation fires. This is the test that discriminates a wired parameter
from an accepted-and-ignored one, because none of the four changes an
observable result. It asserts on `ArcadeDBError` and the engine's "must be"
wording rather than grepping for the parameter name: an unwired keyword raises
`TypeError: ... unexpected keyword argument 'commit_retries'`, whose message
contains the parameter name, so a name-substring check passes on exactly the
broken code it is meant to catch. The first version of this test did that.

## Why It Matters

`GraphBatch` is the repository's preferred bulk graph-ingest path from Python, so these tests protect the performance-oriented API surface and its configuration validation behavior.
