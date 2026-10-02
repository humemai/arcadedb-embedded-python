# Timeseries SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_timeseries_sql.py){ .md-button }

These tests cover SQL-first timeseries behavior from the Python bindings.

## Covered Behavior

### 1) insert, range query, and bucket aggregation

Creates a `TIMESERIES TYPE`, inserts records, validates `BETWEEN` queries (3 rows; timestamps compared up to a constant offset), and checks `ts.timeBucket(...)` aggregation results.

### 2) tag filtering and empty ranges

Verifies tag-based filtering and the no-row case for non-overlapping time windows.

### 3) COMPACT TIMESERIES TYPE seals the tail

Appends 5,000 samples with `append_samples()`, runs `COMPACT TIMESERIES TYPE TempData`, and asserts the result names the type, reports `mutableSamples` 0, and a `mutableSamplesBefore` between 0 and 5,000 (the background pass may have sealed part of it first), and that all 5,000 samples still count. The statement is new in 26.10.1 (`ArcadeData/arcadedb#8574`); 26.9.1 rejects it as a syntax error.

## Runtime Guard

If the packaged runtime does not support `CREATE TIMESERIES TYPE`, these tests skip cleanly.
