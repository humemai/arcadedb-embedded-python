# Java Bridge (`arcadedb-python-bridge.jar`)

The bindings ship a small Java helper jar alongside the engine JARs. Its
sources live in `bindings/python/src/java/com/arcadedb/python/`:

| Class | Purpose |
|---|---|
| `RowBatcher` | Serializes up to N result rows into one JSON-array string per call (batched row transport) |
| `ColumnBatcher` | Encodes up to N rows into one `byte[]` of typed little-endian column buffers plus null bitmaps (binary columnar transport) |
| `DocumentBatcher` | Inserts a whole batch of documents from one JSON-rows string (transactional or async parallel writers), or from whole typed columns (`insertColumns`, one `long[]`, `double[]`, `boolean[]`, or `Object[]` per property); also boxes numpy numeric arrays for `append_samples` |
| `EdgeBatcher` | Buffers a whole batch of edges into `GraphBatch` from one call (RID strings, or JSON rows for edges with properties) |
| `VertexBatcher` | Creates a whole batch of vertices from one JSON-rows string, returning all RIDs as one joined string |
| `TimeSeriesBatcher` | Fills the engine's primitive `TimeSeriesBatch` one column per call, so numeric samples are never boxed |
| `RowAccess` | Hands a row's names and values to Python in one call (`namesAndValues`), and up to N such rows per call (`nextRows`); the values are the engine's own objects, so Python converts them with full type fidelity |

`RowBatcher.nextJsonBatch` and `RowAccess.nextRows` return fewer rows than asked for only when the result set is drained, and they close it before returning. Python therefore stops after a short batch and makes no further call into the bridge, not even `close()`: a one-row `to_list()` or `to_json_list()` costs one call into the bridge.

## Why it exists

Every JPype call from Python into the JVM pays a fixed boundary-crossing tax
(on the order of a microsecond). That is invisible for engine-bound work, but
it dominates loops: materializing a wide row costs 2+C crossings (hasNext/next
plus one `getProperty` per column), and `GraphBatch.newEdge()` costs one
crossing per edge. Measured, that made 100k-row scans 15–21× slower than
Java-native iteration and bulk edge ingest 24× slower.

The bridge inverts the shape: the loop runs Java-side, and Python pays **one
crossing per batch**, receiving a bulk payload it can decode at C speed: the
`json` module for `RowBatcher`/`EdgeBatcher`/`VertexBatcher`, and
`numpy.frombuffer` for `ColumnBatcher`. See the
[performance page](../guide/performance.md) for the resulting numbers.

## Which Python APIs use it

| Python API | Bridge class |
|---|---|
| `ResultSet.to_json_list()` / `iter_json_batches()` | `RowBatcher` |
| `ResultSet.to_list()` (rows in batches), `Result.to_dict()` (one row) | `RowAccess` |
| `ResultSet.to_columns()` / fast `to_dataframe()` / `to_arrow()` | `ColumnBatcher` |
| `Database.insert_many()` | `DocumentBatcher` |
| `Database.insert_columns()` | `DocumentBatcher` |
| `AsyncExecutor.append_samples()` (numpy numeric-column boxing) | `DocumentBatcher` |
| `AsyncExecutor.append_samples(..., primitive=True)` | `TimeSeriesBatcher` |
| `GraphBatch.new_edges()` (with and without properties) | `EdgeBatcher` |
| `GraphBatch.create_vertices()` bulk path | `VertexBatcher` |
| `Database.export_to_csv()` (streams JSON batches) | `RowBatcher` |

## How it builds and ships

Both wheel builds compile the bridge with `javac` against the packaged engine
JARs and jar it up as `arcadedb-python-bridge.jar`:

- `scripts/Dockerfile.build` (Linux wheels)
- `scripts/build-native.sh` (macOS/Windows wheels)

The jar lands in `arcadedb_embedded/jars/` inside the wheel, next to the
engine JARs, so it is on the classpath automatically when `jvm.py` starts the
JVM. There is no separate release artifact or version: it is rebuilt from
source on every wheel build.

## Design constraints

- **No engine code is modified.** The bridge is bindings-scoped glue over
  `Database`, `MutableDocument`, `ResultSet`, `Result`, `GraphBatch`, `RID`,
  the async `ErrorCallback`, and the engine's JSON serializer, so upstream
  syncs never conflict with it. `TimeSeriesBatcher` also depends on internal
  time-series classes (`TimeSeriesBatch`, `ColumnDefinition`, and
  `LocalTimeSeriesType`), so an upstream refactor of those can break it.
- **Most callers have a fallback.** Most Python APIs that ride the bridge
  fall back to a pure-JPype implementation if the jar (or a required method)
  is absent, so they still work, just slower. `to_columns()` and `to_arrow()`
  return `None` instead, as they do without NumPy or pyarrow. Three need the jar:
  `AsyncExecutor.append_samples()`, whose numpy-column path and `primitive=True`
  path load the bridge classes directly, `Database.insert_many()`, which loads
  `DocumentBatcher` for any JSON-serializable rows and raises `ArcadeDBError` if it
  is missing (its per-row path runs only for rows `json.dumps` rejects), and
  `Database.insert_columns()`, which always loads `DocumentBatcher` and raises the same
  error.
- **A missing jar is logged.** When a bridge class cannot be loaded, the
  `arcadedb_embedded.results` logger warns `bridge class <name> unavailable;
  falling back to the slow per-row path`. To see whether the jar is in an
  install, look for an entry named `arcadedb-python-bridge.jar` in
  `jar_fingerprint(per_jar=True)["jars"]`.
- `RowBatcher` serializes rows property by property rather than through
  `Result.toJSON()`, so it controls the JSON types (a `DATE` or `DATETIME` is an
  epoch-millisecond integer). It began as a workaround for upstream
  [#4967](https://github.com/ArcadeData/arcadedb/issues/4967) (primitive
  arrays rendered as `"[F@..."`), which the engine fixed in 26.7.2.
