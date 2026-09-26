# Vector Delta Visibility Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_delta_visibility.py)

Vectors written after an index build are searchable before any rebuild.

`LSM_VECTOR` does not patch a built graph. A write goes into an in-memory delta buffer, and the graph is only rebuilt when pending mutations cross `max(100, min(graphSize * 0.2, 50_000))`. Between rebuilds the query path merges the graph's approximate results with an exhaustive scan of the buffer and filters out deleted entries. Both tests stay below the rebuild threshold, the only place the delta path can be told apart: above it a rebuild fires and a passing search proves nothing about the buffer.

## Test Cases

### 1) delta vectors are searchable before any rebuild

Builds an index, then writes more vectors in a later transaction. Where the engine reports its counters, asserts no rebuild fired, the graph node count did not move, and the delta buffer is not empty. Then asserts every buffered vector is its own nearest neighbour: the buffer scan is brute force, so it cannot miss.

### 2) deleted vectors are filtered from delta results

A deleted vector must not come back from `find_nearest`, buffer or no buffer.

## Running

```bash
uv run pytest bindings/python/tests/test_vector_delta_visibility.py -v
```
