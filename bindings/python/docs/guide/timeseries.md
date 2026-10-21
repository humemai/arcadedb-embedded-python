# Time Series Guide

!!! warning "Known engine issues"
    Open ArcadeDB bugs can return a wrong answer or refuse a lookup; see
    [Known Engine Issues](known-issues.md).

A `TIMESERIES` type is a native ArcadeDB type for samples that arrive in time order:
sensor readings, metrics, events with a value. It stores a timestamp, a few **tags**
(low-cardinality strings that identify the source, such as a sensor id) and numeric
**fields** in compressed, time-sharded blocks, and it answers range and bucket queries
without a table scan.

The Python bindings have no TIMESERIES class. You declare the type and read it with
`db.command()` and `db.query()` in SQL (the [DSL-first](../api-access-methods.md)
path), and for bulk writes there is one helper, `db.async_executor().append_samples()`.

Every example below runs against the type in the next section, and the test that runs
them is `tests/test_guide_timeseries.py`. They were measured on engine 26.10.2.

## Declare a type

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./ts_db")

db.command("sql", "CREATE TIMESERIES TYPE Reading TIMESTAMP ts PRECISION MILLISECOND TAGS (sensor STRING) FIELDS (temp DOUBLE, hum DOUBLE) SHARDS 2 RETENTION 90 DAYS COMPACTION_INTERVAL 1 HOURS DOWNSAMPLING POLICY AFTER 7 DAYS GRANULARITY 1 HOURS AFTER 30 DAYS GRANULARITY 1 DAYS")
```

| Clause | Meaning |
| --- | --- |
| `TIMESTAMP ts` | The timestamp column. One per type. |
| `PRECISION` | `SECOND`, `MILLISECOND`, `MICROSECOND` or `NANOSECOND`. The unit of the numbers you write. |
| `TAGS (name STRING, ...)` | Identifying columns. Keep the number of distinct values small. |
| `FIELDS (name TYPE, ...)` | The measured values. |
| `SHARDS n` | Parallel write shards. |
| `RETENTION n DAYS` | Samples older than this are eligible for removal (`HOURS`, `MINUTES` and `SECONDS` also work). |
| `COMPACTION_INTERVAL n HOURS` | The time bucket one sealed block covers. |
| `DOWNSAMPLING POLICY AFTER x GRANULARITY y ...` | Replace samples older than `x` by one aggregate per `y`. One tier per `AFTER` clause. |

Only the timestamp, tags and fields are needed; every other clause has a default.
A second declaration with `IF NOT EXISTS` after the name (`CREATE TIMESERIES TYPE Reading IF NOT EXISTS TIMESTAMP ts TAGS (sensor STRING) FIELDS (temp DOUBLE)`) answers
`created: False` and leaves the type alone. The declaration is stored and can be read back:

```python
row = db.query("sql", "SELECT FROM schema:types WHERE name = 'Reading'").first()
row.get("shardCount"), row.get("retentionMs"), len(row.get("downsamplingTiers"))
# (2, 7776000000, 2)
```

Retention and downsampling are background jobs that the engine runs. This page checks
that the policy is stored, not that the engine has applied it to old data. To change
the policy later:

```python
db.command("sql", "ALTER TIMESERIES TYPE Reading DROP DOWNSAMPLING POLICY")
db.command("sql", "ALTER TIMESERIES TYPE Reading ADD DOWNSAMPLING POLICY AFTER 7 DAYS GRANULARITY 1 HOURS")
```

## Write samples

The timestamp is a number in the type's precision, epoch milliseconds here
(`1767225600000` is 2026-01-01T00:00:00Z). Three insert forms work:

```python
T0 = 1_767_225_600_000

db.command("sql", "INSERT INTO Reading SET ts = ?, sensor = 'a', temp = 20.0, hum = 40.0", T0)
db.command("sql", "INSERT INTO Reading (ts, sensor, temp, hum) VALUES (?, 'a', 21.0, 41.0), (?, 'b', 30.0, 50.0)", T0 + 60_000, T0 + 60_000)
db.command("sql", 'INSERT INTO Reading CONTENT {"ts": 1767225780000, "sensor": "a", "temp": 22.0, "hum": 42.0}')
```

A text timestamp is refused on insert:

```python
db.command("sql", "INSERT INTO Reading SET ts = '2026-01-01T00:02:00Z', sensor = 'b', temp = 31.0, hum = 51.0")
# ArcadeDBError: ... Cannot convert type 'class java.lang.String' to 'LONG' found in property 'ts'
```

Each insert into a TIMESERIES type commits by itself, so wrapping a batch in
`db.transaction()` does not make it atomic.

For thousands of samples or more, use the columnar append. The columns are positional,
in declaration order: the timestamps, then the tags, then the fields. numpy arrays cross
into the engine as one buffer per column.

```python
import numpy as np

n = 1_000
executor = db.async_executor()
executor.append_samples(
    "Reading",
    T0 + np.arange(n, dtype=np.int64) * 1_000,    # ts
    [f"s{i % 2}" for i in range(n)],              # sensor (tag)
    np.arange(n, dtype=np.float64),               # temp
    np.full(n, 50.0),                             # hum
)
executor.wait_completion()   # the samples are not visible before this returns
```

After a bulk load, seal what is still in the mutable tail instead of waiting for the
background pass (26.10.1 and later):

```python
db.command("sql", "COMPACT TIMESERIES TYPE Reading").first().to_dict()
# {'operation': 'compact timeseries type', 'typeName': 'Reading',
#  'mutableSamplesBefore': 1004, 'mutableSamples': 0}
```

`mutableSamplesBefore` can be lower than the number you wrote when the background pass
already sealed part of it. The tags are read back as written:

```python
db.query("sql", "SELECT sensor, count(*) AS n FROM Reading GROUP BY sensor ORDER BY sensor").to_list()
# [{'sensor': 's0', 'n': 500}, {'sensor': 's1', 'n': 500}]
```

## Read samples

The next examples use the six samples below (the three above plus three more for
sensor `b`) and not the 1,000 bulk rows: a fresh type with sensor `a` at minutes 0, 1 and
3 and sensor `b` at minutes 1, 2 and 3.

A query returns `ts` as a naive `datetime` in UTC. A filter takes epoch numbers or
ISO-8601 text:

```python
rows = db.query("sql", "SELECT count(*) AS n FROM Reading").to_list()
# [{'n': 6}]
db.query("sql", "SELECT FROM Reading WHERE sensor = 'a' ORDER BY ts").to_list()
# ts 00:00, 00:01, 00:03 with temp 20.0, 21.0, 22.0
db.query("sql", "SELECT FROM Reading WHERE ts BETWEEN ? AND ? AND sensor = 'a' ORDER BY ts", T0, T0 + 120_000).to_list()
# the samples at 00:00 and 00:01
db.query("sql", "SELECT FROM Reading WHERE ts >= '2026-01-01T00:01:00Z' AND ts < '2026-01-01T00:03:00Z' ORDER BY ts, sensor").to_list()
# a at 00:01, b at 00:01, b at 00:02
```

### Aggregate by time bucket

`ts.timeBucket(interval, ts)` returns the start of the bucket a sample falls in
(`'1s'`, `'5s'`, `'1m'`, `'5m'`, `'1h'`, `'1d'`, `'1w'` and so on). Group by it:

```python
db.query("sql", "SELECT ts.timeBucket('2m', ts) AS slot, sensor, avg(temp) AS t, max(temp) AS peak, count(*) AS n FROM Reading GROUP BY slot, sensor ORDER BY slot, sensor").to_list()
# slot 00:00  a  t=20.5  peak=21.0  n=2
# slot 00:00  b  t=30.0  peak=30.0  n=1
# slot 00:02  a  t=22.0  peak=22.0  n=1
# slot 00:02  b  t=31.5  peak=32.0  n=2
```

Buckets are counted from the Unix epoch in UTC, so `'1d'` starts at 00:00 UTC and
`'1w'` on a Thursday. A third argument moves the grid:

```python
db.query("sql", "SELECT ts.timeBucket('1d', ts, {timezone: '+08:00'}) AS day, count(*) AS n FROM Reading GROUP BY day").to_list()
# [{'day': datetime(2025, 12, 31, 16, 0), 'n': 6}]   local midnight in UTC+8, shown in UTC
```

`{offset: '-8h'}` shifts the grid by a duration and `{origin: '2024-01-01T00:00:00Z'}`
makes weeks start on Monday. A zone with daylight saving is refused.

### First, last, change and rate

```python
db.query("sql", "SELECT sensor, ts.first(temp, ts) AS first, ts.last(temp, ts) AS last, ts.delta(temp, ts) AS delta, ts.rate(temp, ts) AS per_second FROM Reading GROUP BY sensor ORDER BY sensor").to_list()
# a  first=20.0  last=22.0  delta=2.0  per_second=2/180 = 0.0111
# b  first=30.0  last=32.0  delta=2.0  per_second=2/120 = 0.0167
```

`ts.first` and `ts.last` pick the value at the earliest and latest timestamp of the
group, `ts.delta` is last minus first, and `ts.rate` is that change per second. Pass
`true` as a third argument to `ts.rate` to treat a drop as a counter reset.

```python
db.query("sql", "SELECT sensor, ts.percentile(temp, 0.5) AS median FROM Reading GROUP BY sensor ORDER BY sensor").to_list()
# [{'sensor': 'a', 'median': 21.0}, {'sensor': 'b', 'median': 31.0}]
```

The engine has more `ts.*` functions (`ts.interpolate`, `ts.correlate`, `ts.lag`,
`ts.lead`, `ts.rank`, `ts.rowNumber`, `ts.movingAvg`). In a plain `SELECT` the window
ones return one row holding the whole array, not one value per sample:

```python
db.query("sql", "SELECT ts.movingAvg(temp, 2) AS ma FROM Reading WHERE sensor = 'a' ORDER BY ts").to_list()
# one row: ma = [20.0, 20.5, 21.5]
```

### Into pandas or Arrow

A bucketed result is already small, so hand it to a DataFrame or Arrow table directly:

```python
table = db.query("sql", "SELECT ts.timeBucket('2m', ts) AS slot, avg(temp) AS t FROM Reading GROUP BY slot ORDER BY slot").to_arrow()
table.schema.field("slot").type     # timestamp[ms]
```

`to_arrow()` needs `pyarrow`; `to_dataframe()` needs `pandas`. See the
[Results API](../api/results.md).

## Keep an aggregate current

A continuous aggregate stores the result of a bucketed query and updates it as new
samples arrive.

```python
db.command("sql", "CREATE CONTINUOUS AGGREGATE hourly AS SELECT ts.timeBucket('1h', ts) AS hour, sensor, avg(temp) AS t FROM Reading GROUP BY hour, sensor")
db.query("sql", "SELECT FROM hourly ORDER BY hour, sensor").to_list()
# hour 00:00  a  t=21.0
# hour 00:00  b  t=31.0
db.command("sql", "REFRESH CONTINUOUS AGGREGATE hourly")   # catch up now
db.command("sql", "DROP CONTINUOUS AGGREGATE hourly")
```

While the aggregate exists, `DROP TIMESERIES TYPE Reading` raises `ArcadeDBError`
and tells you to drop the aggregate first.

## Caveats

- `bucket` is a reserved word: `SELECT ts.timeBucket('2m', ts) AS bucket, count(*) AS n FROM Reading GROUP BY bucket`
  is a SQL syntax error. Use another alias (`slot`, `hour`).
- `INSERT` takes a number for the timestamp; a filter in `WHERE` also takes ISO text.
- Tags are strings and should be few in kind. A tag with a new value per sample (a
  request id) defeats the dictionary the engine keeps for them.
- A TIMESERIES type owns no document buckets, so it cannot be an `IMPORT DATABASE`
  target; see [Data Import](import.md). Over HTTP the write endpoint is
  `/api/v1/ts/{db}/write`; see [Server Mode](server.md).
- Left out of this page because they were not run here: retention and downsampling
  actually removing or rolling up old samples, `PRECISION NANOSECOND` round trips,
  `ts.promql`, and `ts.interpolate`, `ts.correlate`, `ts.lag` and `ts.lead` beyond the
  syntax in the engine reference.

## References

- [ArcadeDB documentation](https://docs.arcadedb.com/) for the time series chapter
  and the full `ts.*` list.
- The grammar of the statements:
  [`SQLParser.g4`](https://github.com/ArcadeData/arcadedb/blob/main/engine/src/main/antlr4/com/arcadedb/query/sql/grammar/SQLParser.g4)
  (search for `TIMESERIES`).
- [Example 17: Time Series End to End](../examples/17_timeseries_end_to_end.md) and
  [`append_samples`](../api/async_executor.md#append_samples).
