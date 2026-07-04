# Java Bridge (`arcadedb-python-bridge.jar`)

The bindings ship a small Java helper jar alongside the engine JARs. Its
sources live in `bindings/python/src/java/com/arcadedb/python/` — four
classes, ~450 lines total:

| Class | Purpose |
|---|---|
| `RowBatcher` | Serializes up to N result rows into one JSON-array string per call (batched row transport) |
| `ColumnBatcher` | Encodes up to N rows into one `byte[]` of typed little-endian column buffers plus null bitmaps (binary columnar transport) |
| `EdgeBatcher` | Buffers a whole batch of edges into `GraphBatch` from one call (RID strings, or JSON rows for edges with properties) |
| `VertexBatcher` | Creates a whole batch of vertices from one JSON-rows string, returning all RIDs as one joined string |

## Why it exists

Every JPype call from Python into the JVM pays a fixed boundary-crossing tax
(on the order of a microsecond). That is invisible for engine-bound work, but
it dominates loops: materializing a wide row costs 2+C crossings (hasNext/next
plus one `getProperty` per column), and `GraphBatch.newEdge()` costs one
crossing per edge. Measured, that made 100k-row scans 15–21× slower than
Java-native iteration and bulk edge ingest 24× slower.

The bridge inverts the shape: the loop runs Java-side, and Python pays **one
crossing per batch**, receiving a bulk payload it can decode at C speed — the
`json` module for `RowBatcher`/`EdgeBatcher`/`VertexBatcher`, and
`numpy.frombuffer` for `ColumnBatcher`. See the
[performance page](../guide/performance.md) for the resulting numbers.

## Which Python APIs use it

| Python API | Bridge class |
|---|---|
| `ResultSet.to_json_list()` / `iter_json_batches()` | `RowBatcher` |
| `ResultSet.to_columns()` / fast `to_dataframe()` | `ColumnBatcher` |
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
JVM. There is no separate release artifact or version — it is rebuilt from
source on every wheel build.

## Design constraints

- **Public engine APIs only.** The bridge is bindings-scoped glue over
  `ResultSet`, `Result`, `GraphBatch`, `RID`, and the engine's JSON
  serializer. No engine code is modified, so upstream syncs never conflict
  with it.
- **Every caller has a fallback.** Each Python API that rides the bridge
  falls back to a pure-JPype implementation if the jar (or a required method)
  is absent — a source checkout without the jar still works, just slower.
- `RowBatcher` serializes rows property-by-property rather than via
  `Result.toJSON()` to work around upstream
  [#4967](https://github.com/ArcadeData/arcadedb/issues/4967) (primitive
  arrays rendered as `"[F@..."`).
