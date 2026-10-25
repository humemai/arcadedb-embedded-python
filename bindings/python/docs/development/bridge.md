# Java Bridge (`arcadedb-python-bridge.jar`)

The bindings ship a small Java helper jar alongside the engine JARs. Its
sources live in `bindings/python/src/java/com/arcadedb/python/`:
| Class | Purpose |
|---|---|
| `RowBatcher` | Serializes up to N result rows into one JSON-array string per call (batched row transport) |
| `ColumnBatcher` | Encodes up to N rows into one `byte[]` of typed little-endian column buffers plus null bitmaps (binary columnar transport) |
| `DocumentBatcher` | Inserts a whole batch of documents from one JSON-rows string (transactional or async parallel writers), or from whole typed columns (`insertColumns`, one `long[]`, `double[]`, `boolean[]`, or `Object[]` per property); also boxes numpy numeric arrays for `append_samples`; a float vector of an `ARRAY_OF_FLOATS` property crosses as a binary `FloatVectors.Matrix` beside the JSON (`insertManyJson`) or as a whole 2-D `float32` column |
| `EdgeBatcher` | Buffers a whole batch of edges into `GraphBatch` from one call (RID strings, or JSON rows for edges with properties) |
| `VertexBatcher` | Creates a whole batch of vertices from one JSON-rows string, returning all RIDs as one joined string |
| `TimeSeriesBatcher` | Fills the engine's primitive `TimeSeriesBatch` one column per call, so numeric samples are never boxed |
| `RowAccess` | Hands a row's names and values to Python in one call (`namesAndValues`), and up to N such rows per call (`nextRows`, the fallback for `to_list()` when the bridge jar lacks `TypedRows`); the values are the engine's own objects, so Python converts them with full type fidelity. Also the first row of a result set with the set closed (`firstAndClose`, behind `ResultSet.first()`) and a property or null (`propertyOrNull`, behind `Result.get()`), each in one call instead of two or three. `ResultSet.one()` is `upToTwoAndClose` (the first two rows, which tell zero, one or several, with the set closed) and `ResultSet.count()` is `countAndClose` (the rows left, then the set drained and closed), each one call instead of one per row |
| `TypedRows` | Up to N rows per call as one JSON string, type-faithful (`nextRows`, which also reports whether the result set is drained): DECIMAL, BigInteger, DATE, DATETIME, Instant and zoned values, and sets are tagged and restored exactly by Python, and every other value (RIDs, embedded documents, `float[]` and `double[]`, non-finite floats, maps with non-String keys, years Python cannot hold) is returned in a side array as the engine's own object and converted by Python as before. Behind `ResultSet.to_list()` (up to 1,000 rows or 4 MiB of JSON per call, whichever comes first) and `ResultSet.iter_dicts()` (one row per call, so a lazy caller reads rows when it asks) |
| `FloatVectors` | Float vectors as one binary buffer instead of JSON text or a JPype call per element: `Matrix` (n vectors in one `float[]`, a row copied into each document), and `declared` (which properties of a type are `ARRAY_OF_FLOATS`); behind `insert_many()`, `insert_columns()` and `GraphBatch.create_vertices()` |
| `GraphCalls` | Every edge of `Vertex.getEdges(direction, labels)` in one call (`outEdges`, `inEdges`, `bothEdges`, behind `Vertex.get_out_edges()` and its siblings), and the record and score of every vector search hit in one call (`hits`, behind `LSMVectorIndex` search results), and the `allowed_rids` set of a vector search from RID strings in one call (`ridSet`) |
| `DbCalls` | One-row statements and lookups in one call: `commandNamed`, `queryNamed`, `commandPositional`, and `queryPositional` take the parameters as the varargs of a single non-overloaded method and build the map Java-side (behind `Database.command()` and `Database.query()`), and `lookupFirstKey` (one key, as scalars) and `lookupFirstKeys` (any number, the names and values as the varargs of one call) are the whole of `Database.lookup_by_key()`, with no Java array built through JPype (`lookupFirst`, which takes the arrays, stays for callers that already hold them). `stackMark` returns the transaction stack (active, nesting depth) as one number: the mark taken before every `begin()` of `with db.transaction()` and `run_in_transaction()` |
| `PythonFunctions` | Registers a Python callable as an engine `SQLFunction` in the process-wide function factory (so SQL and openCypher resolve it): the arity check, one `CommandExecutionException` naming the function for any failure of the callable, and a revoked flag so an unregistered function fails clearly. Behind `Database.register_function()` and `unregister_function()`. Each call is one JNI round trip |
| `PythonRecordEvents` | One listener class for the six write events (before and after create, update, delete) that forwards each to a Python callback; a `false` from a before event is the veto, and a failure is wrapped in a `DatabaseOperationException` naming the event. Behind `Database.on()` |

`RowBatcher.nextJsonBatch` and `RowAccess.nextRows` return fewer rows than asked for only when the result set is drained, and they close it before returning. `TypedRows.nextRows` also ends a batch early, once its JSON text reaches 4 MiB of characters (`MAX_BATCH_CHARS`), so rows of any width cross in bounded pieces; it therefore returns a third element, `drained`, and closes the result set only when that is true. Python stops after a drained batch (a short one, for `nextJsonBatch` and `RowAccess.nextRows`) and makes no further call into the bridge, not even `close()`: a one-row `to_list()` or `to_json_list()` costs one call into the bridge.

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
| `ResultSet.to_list()` (rows in batches), `ResultSet.iter_dicts()` (one row per call) | `TypedRows` |
| `Result.to_dict()` (one row) | `RowAccess` |
| `ResultSet.first()` / `one()` / `count()` | `RowAccess` |
| `Database.lookup_by_key()`, the transaction mark of `Database.transaction()` / `run_in_transaction()` | `DbCalls` |
| `Vertex.get_out_edges()` / `get_in_edges()` / `get_both_edges()`, vector search results and their `allowed_rids` set | `GraphCalls` |
| `ResultSet.to_columns()` / fast `to_dataframe()` / `to_arrow()` | `ColumnBatcher` |
| `Database.insert_many()` | `DocumentBatcher`, `FloatVectors` (vector properties) |
| `Database.insert_columns()` | `DocumentBatcher`, `FloatVectors` (a 2-D `float32` column) |
| `Database.insert_dataframe()` / `insert_arrow()` | `DocumentBatcher` (document types, through `insert_columns()`), `VertexBatcher` (vertex types, through `GraphBatch.create_vertices()`); the Arrow-to-column conversion is Python (`dataframe.py`) |
| `ResultSet.to_polars()` | `ColumnBatcher` (through `to_arrow()`) |
| `AsyncExecutor.append_samples()` (numpy numeric-column boxing) | `DocumentBatcher` |
| `AsyncExecutor.append_samples(..., primitive=True)` | `TimeSeriesBatcher` |
| `GraphBatch.new_edges()` (with and without properties) | `EdgeBatcher` |
| `GraphBatch.create_vertices()` bulk path | `VertexBatcher` |
| `Database.export_to_csv()` (streams JSON batches) | `RowBatcher` |
| `Database.register_function()` | `PythonFunctions` |
| `Database.on()` | `PythonRecordEvents` |

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
  syncs never conflict with it. `PythonFunctions` also depends on the engine's function registries
  (`DefaultSQLFunctionFactory`, `FunctionRegistry`, `CypherFunctionRegistry`, `CypherBuiltinFunctions`),
  so an upstream refactor of those can break it. `TimeSeriesBatcher` also depends on internal
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
  error. `Database.register_function()` and `Database.on()` also need the jar (`PythonFunctions`,
  `PythonRecordEvents`) and raise `ArcadeDBError` without it.
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
