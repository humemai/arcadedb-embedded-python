# Vector Params Verification Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_params_verification.py){ .md-button }

Covers validation of vector index parameters passed into the Java layer and their persistence.

## What's Covered

- Quantization modes: `INT8`, `NONE`, `BINARY`, `PRODUCT`.
- `store_vectors_in_graph` and `add_hierarchy` flags.
- Per-index cache settings:
	- `location_cache_size`
	- `graph_build_cache_size`
	- `mutations_before_rebuild`
- Parameter persistence after database reopen.
- JVM heap sanity check via JPype runtime memory stats.

## Run

```bash
pytest tests/test_vector_params_verification.py -v
```
