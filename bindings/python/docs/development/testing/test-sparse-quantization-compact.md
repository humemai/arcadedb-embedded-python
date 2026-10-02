# Sparse Precision And Compaction Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_sparse_quantization_compact.py)

Sparse index weight precision and the settle step, the dense search beam argument, and INT8 sparse rescoring: engine features the vector guide documents and the benchmark harness depends on (guide/vectors.md).

## Test Cases

### 1) sparse weight precision and compact

Parametrized over `quant`: no `weightQuantization`, and `"FP32"`. Inserts 200 documents under a 512-dimension `LSM_SPARSE_VECTOR` index, then queries doc 3's tokens with unit weights. Asserts 5 hits including id 3, both before and after `COMPACT INDEX`. It does not assert that the two hit lists are equal.

### 2) dense search beam argument

Inserts 300 seeded random 16-dimension vectors under a COSINE `LSM_VECTOR` index and queries vector 7 for k=10 at beam 16 and at beam 200. Asserts 10 rows at each beam; at beam 200 it also asserts id 7 is among them (at beam 16 that is not checked).

### 3) INT8 scores are rescored to the exact dot product

Loads 300 seeded documents twice into indexes with `"weightQuantization": "INT8"`, once at the default and once with `"rescoreOversample": 0`, compacts both, and compares each top-5 hit's score with the dot product computed in Python. The default index must be exact (relative error below 1e-5; the INT8 postings only pick candidates and the records' weights score them, `ArcadeData/arcadedb#8576`); the index without rescoring must not be, which proves the postings went through INT8 at all.

## Running

```bash
uv run pytest bindings/python/tests/test_sparse_quantization_compact.py -v
```
