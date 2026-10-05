# 17 - Time Series End-to-End

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/17_timeseries_end_to_end.py){ .md-button }

This example drives time series through plain ArcadeDB SQL from Python: DDL, writes,
and queries all go through `db.command()` and `db.query()`. For bulk writes the bindings
also have a columnar append, `db.async_executor().append_samples(...)`, which Example 22
demonstrates.

It covers:

- creating a `TIMESERIES TYPE` with multiple tags and numeric fields and
  `COMPACTION_INTERVAL 1 HOURS`, the bucket of the hourly aggregates it runs
- generating deterministic telemetry for six building sensors
- inserting hundreds of samples transactionally
- sealing the mutable tail with `COMPACT TIMESERIES TYPE` before reading, embedded and
  over HTTP (26.10.1, `ArcadeData/arcadedb#8574`), instead of waiting for the 60-second
  background pass
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
    a database created before 26.8.1 measures the old layout and shows no
    change. Recreate the type against a fresh database to see the difference.

    TAGs are for low-cardinality values by definition;
    `arcadedb.timeSeriesTagDictionaryMaxSize` (default 1M distinct values)
    turns a mis-declared high-cardinality TAG into a clear error rather than
    unbounded growth. High-cardinality text belongs in a STRING *field*, which
    stays inline.

!!! tip "Match COMPACTION_INTERVAL to your aggregation"

    A type whose main query is an hourly aggregate declares `COMPACTION_INTERVAL 1 HOURS`
    and leaves `SHARDS` at its default (the number of cores minus one, not the CPU
    count). Sealed blocks are then cut at the hour boundary, which gave the engine
    maintainers a 12-hour hourly average of 1.8 ms against 0.9 ms on 2.59 million
    samples (100 hosts, 4 shards), with ingest no slower. The price is more and smaller
    blocks (40 became 173), so pick the bucket of your most frequent aggregation
    (ArcadeDB [#9166](https://github.com/ArcadeData/arcadedb/issues/9166)). More
    shards means more fragmentation and one more stream to merge.

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

## Server mode: the same type over HTTP

The last step starts the bundled server (`create_server()`), creates the same
`SensorReading` TIMESERIES type there, and writes every generated sample through
`POST /api/v1/ts/{db}/write` in InfluxDB line protocol, one sample per line,
timestamps in milliseconds (`?precision=ms`), then reads back the stored sample count and
each sensor's newest timestamp with SQL over HTTP. That is the path a client without the
wheel gets; in-process, `db.async_executor().append_samples(...)` skips the parse
and the socket. Example 24 covers transactions and database commands over HTTP.

## Why SQL-First?

The bindings already expose a stable generic interface through `db.command()` and
`db.query()`, so this example keeps the type definition, the writes, and the queries in
SQL, where the time-series semantics are defined upstream. The one time-series-specific
Python call is `append_samples(...)`, a columnar bulk-write path; there is no Python
object model for time-series types.
