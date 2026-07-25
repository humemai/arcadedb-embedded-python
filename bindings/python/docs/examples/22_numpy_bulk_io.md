# 22 - numpy Bulk I/O Workflow

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/22_numpy_bulk_io.py){ .md-button }

Every path in this example crosses the Python/Java boundary once per batch
instead of once per value. Per-row FFI calls cap document ingest around
30k rows/s regardless of engine speed; the batched paths below reach
hundreds of thousands of rows or points per second on the same machine.

It covers:

- bulk document ingest with `Database.insert_many()` (rows serialized as one
  JSON batch, looped Java-side), in both transactional-batch and async
  parallel-writer modes
- time-series ingest straight from numpy arrays via
  `AsyncExecutor.append_samples()` - timestamps and numeric field columns
  cross the boundary as one buffer copy per column
- time-bucketed aggregation over the native `TIMESERIES` type
  (`ts.timeBucket` with a bounded `WHERE ts BETWEEN` range)
- columnar export with `to_columns()`: scalar columns come back as 1-D numpy
  arrays and embedding columns as one contiguous 2-D `float32` array, ready
  for scikit-learn or faiss without per-row conversion

Run it:

```bash
uv run python examples/22_numpy_bulk_io.py
# reduced scale:
uv run python examples/22_numpy_bulk_io.py --rows 50000 --points 100000 --vectors 5000
```
