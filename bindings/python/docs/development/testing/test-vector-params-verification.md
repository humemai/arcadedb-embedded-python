# Vector Params Verification Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_params_verification.py){ .md-button }

Covers validation of vector index parameters passed into the Java layer.

There are 13 tests, all in `TestVectorParams`.

## What's Covered

- Quantization modes: `INT8`, `NONE`, `BINARY`, `PRODUCT`.
- `store_vectors_in_graph` and `add_hierarchy` flags.
- Native `INT8` encoding, and its guard against the default `INT8` quantization.
- Per-index cache settings:
    - `graph_build_cache_size`
    - `mutations_before_rebuild`
- The `max_connections` default, which must equal the engine's.
- Reopening a database that holds a configured index.
- JVM heap sanity check via JPype runtime memory stats.

## Test Cases

- **test_quantization_param**: `create_vector_index(..., quantization="INT8")` gives an index whose `get_quantization()` and Java metadata `quantizationType` are both `INT8`.
- **test_quantization_none**, **test_quantization_binary**, **test_quantization_product**: the same two checks for `NONE`, `BINARY`, and `PRODUCT`.
- **test_store_vectors_in_graph_param**: `store_vectors_in_graph=True` shows up as `storeVectorsInGraph` true in the index metadata.
- **test_add_hierarchy_param**: `add_hierarchy=True` shows up as `addHierarchy` true in the index metadata.
- **test_encoding_param**: an index on a `BINARY` property with `quantization="NONE", encoding="INT8"` has metadata `encoding == INT8` and `quantizationType == NONE`. It skips if the engine build does not support or expose encoding.
- **test_encoding_int8_rejects_default_int8_quantization**: `encoding="INT8"` without an explicit quantization raises `ArcadeDBError` naming `encoding='INT8'` and `quantization='INT8'`.
- **test_per_index_cache_params**: `location_cache_size=123` raises `ValueError` ("no longer supported", removed by the engine in #5559 and #5568); `graph_build_cache_size=456` and `mutations_before_rebuild=789` reach the index metadata as `graphBuildCacheSize == 456` and `mutationsBeforeRebuild == 789`.
- **test_wrapper_default_matches_engine_default**: the default of `create_vector_index(max_connections=...)` equals `maxConnections` on a freshly constructed engine `LSMVectorIndexMetadata`.
- **test_omitted_max_connections_reaches_the_index**: an index created without `max_connections` has the engine default in its metadata.
- **test_params_persistence**: creates an `INT8` index with `store_vectors_in_graph` and `add_hierarchy`, closes, reopens, and asserts that `schema:indexes` lists an index on the type and that a `vectorNeighbors` query returns a row. It does not read the parameters back after the reopen.
- **test_jvm_heap_check**: the JVM's `Runtime.maxMemory()` is above 1 GB (the default heap is 4 GB).

## Run

```bash
uv run pytest bindings/python/tests/test_vector_params_verification.py -v
```
