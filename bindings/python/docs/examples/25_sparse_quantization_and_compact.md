# 25 - Sparse Vectors, Weight Precision And Compaction

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/25_sparse_quantization_and_compact.py)

Two decisions a sparse-retrieval workload should make on purpose, shown on the
same synthetic SPLADE-style corpus built twice:

- **weight precision**: `LSM_SPARSE_VECTOR` stores posting weights as INT8 by
  default; `"weightQuantization": "FP32"` in the index metadata keeps them exact
- **the settle step**: `COMPACT INDEX` merges the LSM segments a bulk load leaves
  behind; queries are faster afterwards, so compact after loading and before
  timing anything

## Run

```bash
uv run python examples/25_sparse_quantization_and_compact.py --docs 20000
```

## What you should see

Per precision: size on disk, compaction time, and query p50 before and after
compaction. Then the top-10 agreement between the int8 and fp32 indexes over the
query set, which is how much recall the default precision costs on this corpus.

## Notes

- The compaction statement works the same over the server's HTTP API, so a
  served deployment gets the same settle step.
- See the [Sparse Vectors](../guide/vectors.md#sparse-vectors) section of the
  guide for the weight-precision and settle-step details.
