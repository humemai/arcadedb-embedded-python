# Example 15: Import Database vs Transactional Table Ingest

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/15_import_database_vs_transactional_table_ingest.py){ .md-button }

This example compares four table-ingest strategies against the same generated dataset
shape.

## Overview

Example 15 is the table-ingest comparison harness for embedded Python.

- Generates synthetic multi-table CSV data
- Runs four ingest modes:
    - transactional SQL inserts in batches
    - async SQL inserts via the async executor
    - SQL `IMPORT DATABASE`
    - Python `db.import_documents(...)`
- Checks final row-count parity before treating the timing result as valid

## Current Repository Guidance

- This example exists because ingest winners are workload-dependent
- Both `IMPORT DATABASE` and `db.import_documents(...)` are possible ingestion paths
- Both importer-based paths have shown practical issues on larger real workloads,
  including memory pressure and possible OoM failure modes
- Async SQL insert is the recommended default for Python-managed bulk table/document
  ingest in this repository
- Keep async SQL on a single worker for this path; multi-threaded async insert has not
  been safe or reliable in the current Python examples
- The broader example set therefore standardizes on async SQL insert for document
  preloading

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

For this synthetic workload, `IMPORT DATABASE` remained the fastest option, but
increasing import parallelism from 1 to 4 did not provide a meaningful speedup.

That benchmark result should not be treated as the repository-wide recommendation. For
the real document-preload examples, single-worker async SQL insert is the preferred path
because it has been more reliable in practice than the importer-based paths.

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
- `--async-parallel`: async SQL worker count; keep this at `1` for the recommended path
- `--parallel`: SQL import worker count
- `--import-chunk-rows`: chunk size for the `import_documents` benchmark path
- `--heap-size`: JVM heap size

## Parity Semantics

Timing comparisons only matter if all four modes load the expected final row counts
across the generated tables.

The example also performs a lightweight post-run parity check over schema, aggregates,
and sampled rows so that major output differences are reported alongside the timing
results.
