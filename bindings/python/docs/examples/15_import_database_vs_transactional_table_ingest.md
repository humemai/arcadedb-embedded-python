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
- The recommended path for Python-managed bulk table/document ingest is
  `db.insert_many(...)`, which crosses the Python/Java boundary once per batch and
  loops Java-side. It is not one of the four arms here
- The async SQL arm is a comparison arm, not a recommendation
- The broader example set uses `db.insert_many(...)` for document preloading

!!! warning "Why the async arm accepts only `--async-parallel 1`"

    Before 26.10.1, `async_executor().command(...)` could silently drop records above
    parallel level 1 (`ArcadeData/arcadedb#7615`, fixed in #7625); see
    [Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation).
    `run_async_sql_load(...)` raises `ValueError` for any `--async-parallel` other than 1,
    and counts stored rows against submitted rows per table so a short load fails instead
    of being reported as a fast one.

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
