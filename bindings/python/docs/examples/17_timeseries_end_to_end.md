# 17 - Time Series End-to-End

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/17_timeseries_end_to_end.py){ .md-button }

This example demonstrates the current Python-bindings posture for time series:
use plain ArcadeDB SQL from Python rather than a dedicated Python object API.

It covers:

- creating a `TIMESERIES TYPE` with multiple tags and numeric fields
- generating deterministic telemetry for six building sensors
- inserting hundreds of samples transactionally
- running raw window queries with multiple tag filters
- grouping into hourly buckets with `ts.timeBucket()`
- aggregating at sensor, building, and region levels
- deriving alert-style views from SQL aggregates
- reading back the latest sample per sensor

!!! note "TAG storage changed in 26.8.1"

    A mutable TimeSeries row is fixed-stride, so a `STRING` TAG used to reserve
    258 bytes inline whatever the value was. Since 26.8.1 a TAG holds a
    4-byte dictionary id instead
    ([#5574](https://github.com/ArcadeData/arcadedb/pull/5574)), which for a
    ten-tag schema takes the row stride from 2,612 B to 72 B.

    **The row format is versioned per type and there is no in-place
    migration.** A type created by an earlier build keeps the inline layout;
    only a newly created type gets the encoding. Existing databases keep
    working, but they do not get the smaller stride, and a benchmark pointed at
    a database created before dev23 measures the old layout and shows no
    change. Recreate the type against a fresh database to see the difference.

    TAGs are for low-cardinality values by definition;
    `arcadedb.timeSeriesTagDictionaryMaxSize` (default 1M distinct values)
    turns a mis-declared high-cardinality TAG into a clear error rather than
    unbounded growth. High-cardinality text belongs in a STRING *field*, which
    stays inline.

## Run

From `bindings/python/examples`:

```bash
python3 17_timeseries_end_to_end.py
```

With a longer synthetic run:

```bash
python3 17_timeseries_end_to_end.py --hours 12 --interval-minutes 5
```

## Notes

- The example is intentionally SQL-first.
- If the packaged ArcadeDB runtime does not include TimeSeries SQL support,
  the script prints a short explanation and exits.
- The database is created under `./my_test_databases/timeseries_demo_db` and is kept for inspection.
- The generated data models smart-building telemetry with tags for region, building,
  zone, and sensor id plus fields for temperature, humidity, power, CO2, and occupancy.

## Why SQL-First?

The bindings already expose a stable generic interface through `db.command()` and
`db.query()`. For time series, that keeps Python maintenance low while avoiding a
premature public object API around upstream-owned semantics.
