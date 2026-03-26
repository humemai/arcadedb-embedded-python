# Timeseries SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_timeseries_sql.py){ .md-button }

These tests cover SQL-first timeseries behavior from the Python bindings.

## Covered Behavior

### 1) insert, range query, and bucket aggregation

Creates a `TIMESERIES TYPE`, inserts records, validates `BETWEEN` queries, and checks `ts.timeBucket(...)` aggregation results.

### 2) tag filtering and empty ranges

Verifies tag-based filtering and the no-row case for non-overlapping time windows.

## Runtime Guard

If the packaged runtime does not support `CREATE TIMESERIES TYPE`, these tests skip cleanly.
