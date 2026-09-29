# 25 - Sparse Vectors, Weight Precision, And Compaction

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/25_sparse_quantization_and_compact.py)

Two decisions a sparse-retrieval workload should make on purpose, shown on the
same synthetic SPLADE-style corpus built three times:

- **weight precision**: `LSM_SPARSE_VECTOR` stores posting weights as INT8 by
  default; `"weightQuantization": "FP32"` in the index metadata keeps them exact.
  From 26.10.1 the INT8 index only picks the candidates and ranks
  `k × rescoreOversample` of them (2 by default) by the exact score from the
  records' own weights (`ArcadeData/arcadedb#8576`); `"rescoreOversample": 0`
  turns that off, and the third build shows what it buys
- **the settle step**: `COMPACT INDEX` merges the LSM segments a bulk load leaves
  behind; queries are faster afterwards, so compact after loading and before
  timing anything

## Run

From `bindings/python/examples`:

```bash
python 25_sparse_quantization_and_compact.py --docs 20000
```

The databases are created under `./my_test_databases/sparse_precision` (`--db-dir`).

## What you should see

Per build (INT8 rescored, INT8 without rescoring, FP32): size on disk, compaction
time, and query p50 before and after compaction. Then each INT8 index's top-10
agreement with FP32 over the query set. With 20,000 documents on 26.10.1 the
rescored index agrees on 1.000 and the one without rescoring on 0.996; before
26.10.1 the default behaved like the second.

## Notes

- The compaction statement works the same over the server's HTTP API, so a
  served deployment gets the same settle step.
- See the [Sparse Vectors](../guide/vectors.md#sparse-vectors) section of the
  guide for the weight-precision and settle-step details.
