# Sparse Precision And Compaction Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_sparse_quantization_compact.py)

Sparse index weight precision and the settle step, plus the dense search beam argument: three engine features the vector guide documents and the benchmark harness depends on (guide/vectors.md, 2026-09-07).

There are 3 tests, which collect as 4 cases: the first is parametrized over `quant` (no `weightQuantization`, and `"FP32"`).

## Test Cases

### 1) sparse weight precision and compact

See the source for the exact assertions.

### 2) dense search beam argument

See the source for the exact assertions.

### 3) INT8 scores are rescored to the exact dot product

Loads 300 seeded documents twice into indexes with `"weightQuantization": "INT8"`, once at the default and once with `"rescoreOversample": 0`, compacts both, and compares each top-5 hit's score with the dot product computed in Python. The default index must be exact (relative error below 1e-5; from 26.10.1 the INT8 postings only pick candidates and the records' weights score them, `ArcadeData/arcadedb#8576`); the index without rescoring must not be, which proves the postings went through INT8 at all. On 26.9.1 it fails at the metadata key, and there the scores were exact only because `compact()` left a corpus this small in the in-memory table.

## Running

```bash
uv run pytest bindings/python/tests/test_sparse_quantization_compact.py -v
```
