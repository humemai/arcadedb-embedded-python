# Example 15: Import Database vs Transactional Table Ingest

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/15_import_database_vs_transactional_table_ingest.py){ .md-button }

This example compares four table-ingest strategies against the same generated dataset
shape.

## Overview

Example 15 is the table-ingest comparison harness for embedded Python.

- Generates synthetic multi-table CSV data
- Runs four ingest modes:
    - transactional SQL inserts in batches
    - async SQL inserts via the async executor, pinned to one worker
    - SQL `IMPORT DATABASE`
    - Python `db.import_documents(...)`
- Checks final row-count parity before treating the timing result as valid

## Current Repository Guidance

- This example exists because ingest winners are workload-dependent
- Both `IMPORT DATABASE` and `db.import_documents(...)` are possible ingestion paths
- Both importer-based paths have shown practical issues on larger real workloads,
  including memory pressure and possible OoM failure modes
- The recommended path for Python-managed bulk table/document ingest is
  `db.insert_many(...)`, which crosses the Python/Java boundary once per batch and
  loops Java-side. It is not one of the four arms here
- The async SQL arm is a comparison arm, not a recommendation. Do not read its time in
  the snapshot below as an endorsement of it
- The broader example set uses `db.insert_many(...)` for document preloading

!!! warning "Why the async arm accepts only `--async-parallel 1`"

    The async executor's SQL command path, `db.async_executor().command(...)`, silently
    discarded records once the parallel level was above 1, before 26.10.1
    (`ArcadeData/arcadedb#7615`, fixed in #7625: a failed periodic commit is now retried
    and otherwise reported through the error callback). Observed on arcadedb-engine
    26.9.1 and 26.6.1, measured 2026-09-15. How much was lost varied by run and by
    workload shape: 9,742 single-record `INSERT` commands submitted at parallel level 4
    stored 2,436, 5,742, and 7,742 rows across runs. No error reached the per-command
    callback, nothing was
    logged, and `wait_completion()` returned normally. Only the executor-wide `on_error`
    handler saw anything, one `ConcurrentModificationException` per rolled-back batch.
    At parallel level 1 nothing was lost. Filed upstream as `ArcadeData/arcadedb#7615`.

    `run_async_sql_load(...)` therefore raises `ValueError` for any `--async-parallel`
    other than 1, and counts stored rows against submitted rows per table so a short
    load fails instead of being reported as a fast one.

## Recent Benchmark Snapshot

For this shape:

- `tables=10`
- `rows-per-table=1,000,000`
- `columns=20` plus `id`
- `string-size=128`
- `batch-size=10,000`
- `heap-size=8g`

Measured times:

- `Transactional INSERT`: `189.921s`
- `Async SQL INSERT`: `146.670s`
- `IMPORT DATABASE` with `--parallel 1`: `58.281s`
- `IMPORT DATABASE` with `--parallel 4`: `59.868s`

The run parameters recorded above do not name an `--async-parallel` value. The flag
defaulted to 1 at the time, and 1 is the only level the arm now accepts, so the
`Async SQL INSERT` figure is most likely a one-worker time. Treat it as unverified
rather than as a like-for-like comparison until the arm is re-run.

For this synthetic workload, `IMPORT DATABASE` remained the fastest option, but
increasing import parallelism from 1 to 4 did not provide a meaningful speedup.

That benchmark result should not be treated as the repository-wide recommendation, and
neither should the async time. For the real document-preload examples the path to use is
`db.insert_many(...)`, which has no arm here and therefore no time in this table.

## Run

From `bindings/python/examples`:

```bash
python 15_import_database_vs_transactional_table_ingest.py \
  --tables 4 \
  --rows-per-table 100000 \
  --columns 20 \
  --string-size 64 \
  --batch-size 10000 \
  --async-parallel 1 \
  --parallel 8 \
  --heap-size 4g
```

## Key Options

- `--tables`: number of generated tables
- `--rows-per-table`: rows per table
- `--columns`: extra columns per table in addition to `id`
- `--string-size`: generated string payload size
- `--batch-size`: ingest batch size
- `--async-parallel`: async SQL worker count; only `1` is accepted (#7615)
- `--parallel`: SQL import worker count
- `--import-chunk-rows`: chunk size for the `import_documents` benchmark path
- `--heap-size`: JVM heap size

## Parity Semantics

Timing comparisons only matter if all four modes load the expected final row counts
across the generated tables.

The example also performs a lightweight post-run parity check over schema, aggregates,
and sampled rows so that major output differences are reported alongside the timing
results.
