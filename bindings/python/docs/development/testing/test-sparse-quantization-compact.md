# Sparse Precision And Compaction Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_sparse_quantization_compact.py)

Sparse index weight precision and the settle step, plus the dense search beam argument: three engine features the vector guide documents and the benchmark harness depends on (guide/vectors.md, 2026-09-07).

There are 2 tests.

## Test Cases

### 1) sparse weight precision and compact

See the source for the exact assertions.

### 2) dense search beam argument

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_sparse_quantization_compact.py -v
```
