# Database API Reference

Complete API reference for working with ArcadeDB databases in Python.

!!! note "DSL-first usage"
    For application code and examples, prefer SQL/OpenCypher via `db.command(...)` and `db.query(...)`.
    This page also documents wrapper/object methods for compatibility and low-level API completeness.

## Module Functions

### create_database

```python
arcadedb.create_database(path: str, jvm_kwargs: Optional[dict] = None) -> Database
```

Create a new database at the specified path.

**Parameters:**

- `path` (str): File system path where the database will be created
- `jvm_kwargs` (Optional[dict]): Optional JVM args passed to `start_jvm()` (e.g. `{"heap_size": "8g"}`)

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If database creation fails or path already exists

**Example:**

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
```

!!! tip "Use Context Manager"
    Prefer using `with` statement for automatic cleanup:

    ```python
    with arcadedb.create_database("./mydb") as db:
        # Database automatically closed on exit
        pass
    ```

---

### open_database

```python
arcadedb.open_database(path: str, jvm_kwargs: Optional[dict] = None) -> Database
```

Open an existing database.

**Parameters:**

- `path` (str): Path to the existing database
- `jvm_kwargs` (Optional[dict]): Optional JVM args passed to `start_jvm()` (e.g. `{"heap_size": "8g"}`)

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If database doesn't exist or can't be opened

**Example:**

```python
with arcadedb.open_database("./mydb") as db:
    result = db.query("sql", "SELECT FROM Person")
    print(f"Found {len(list(result))} records")
```

---

### database_exists

```python
arcadedb.database_exists(path: str) -> bool
```

Check if a database exists at the given path.

**Parameters:**

- `path` (str): Path to check

**Returns:**

- `bool`: True if database exists, False otherwise

!!! warning "Starts the JVM with default settings"
    `database_exists()` takes no `jvm_kwargs`. If the JVM is not running yet, it starts
    it with the default settings, and a later `create_database(..., jvm_kwargs=...)`,
    `open_database(..., jvm_kwargs=...)`, or `start_jvm(...)` with other settings
    raises `ArcadeDBError`. To size the JVM, call `start_jvm(...)` first (see the
    [JVM API](jvm.md)).

**Example:**

```python
if arcadedb.database_exists("./mydb"):
    db = arcadedb.open_database("./mydb")
else:
    db = arcadedb.create_database("./mydb")
```

---

## Database Class

The main database interface for executing queries, managing transactions, and issuing
schema/data commands.

!!! note "Recommended usage"
    Treat `db.command(...)` and `db.query(...)` as the default application-facing API.
    The record-wrapper helpers documented below are available for compatibility and
    targeted low-level workflows, but the docs standardize on SQL/OpenCypher for CRUD.

### Constructor

```python
Database(java_database)
```

**Parameters:**

- `java_database`: Java Database object (internal use - use factory functions instead)

!!! note "Direct Construction"
    Don't create `Database` instances directly. Use `create_database()`, `open_database()`, or `DatabaseFactory` instead.

---

### query

```python
db.query(language: str, command: str, *args) -> ResultSet
```

Execute a query and return results. Queries are read-only and don't require a transaction.

**Parameters:**

- `language` (str): Query language - `"sql"`, `"sqlscript"`, `"opencypher"` (or its alias `"cypher"`), `"graphql"`
- `command` (str): Query string
- `*args`: Optional positional parameters, or one mapping for named parameters
  A single list or tuple on its own is the positional-parameter array, one element per `?`, so `query("sql", "... ?", [0.9, 0.1, 0.0])` binds `?` to `0.9`. To bind one list as one parameter (a query vector, say), pass a NumPy array or `to_java_float_array(...)`, use a named parameter, or wrap it: `[[0.9, 0.1, 0.0]]`.

**Returns:**

- `ResultSet`: Iterable result set

**Raises:**

- `ArcadeDBError`: If query fails or database is closed

**Example:**

```python
# Simple query
result = db.query("sql", "SELECT FROM Person WHERE age > 25")
for record in result:
    print(record.get('name'))

# Parameterized query
result = db.query("sql", "SELECT FROM Person WHERE age > ?", 25)

# Named parameters
result = db.query(
    "sql",
    "SELECT FROM Person WHERE age IN :ages ORDER BY age",
    {"ages": [25, 30, 35]},
)

# OpenCypher query
result = db.query("opencypher", """
    MATCH (p:Person)-[:Knows]->(friend)
    WHERE p.age > $min_age
    RETURN friend.name
""", {"min_age": 25})
```

**Supported Languages:**

| Language | Notes |
|----------|-------|
| `sql` | ArcadeDB SQL |
| `sqlscript` | Several SQL statements separated by `;`, run as one script (`query()` and `command()`) |
| `opencypher` | OpenCypher graph query language |
| `cypher` | Alias of `opencypher` |
| `graphql` | GraphQL queries (the module ships in the wheel; no Python test exercises it) |

---

### command

```python
db.command(language: str, command: str, *args) -> Optional[ResultSet]
```

Execute a command (write operation). Data writes (`INSERT`, `UPDATE`, `DELETE`, `CREATE
VERTEX`, `CREATE EDGE`) **require a transaction**; schema commands (DDL) run without
one.

**Parameters:**

- `language` (str): Command language (usually `"sql"` or `"opencypher"`)
- `command` (str): Command string
- `*args`: Optional positional parameters, or one mapping for named parameters
  A single list or tuple on its own is the positional-parameter array, one element per `?`, so `query("sql", "... ?", [0.9, 0.1, 0.0])` binds `?` to `0.9`. To bind one list as one parameter (a query vector, say), pass a NumPy array or `to_java_float_array(...)`, use a named parameter, or wrap it: `[[0.9, 0.1, 0.0]]`.

**Returns:**

- `ResultSet` or `None`: Result set if command returns data, None otherwise

**Raises:**

- `ArcadeDBError`: If command fails, database is closed, or a data write runs with no active transaction

**Example:**

```python
# Schema operations
db.command("sql", "CREATE DOCUMENT TYPE Person")
db.command("sql", "CREATE PROPERTY Person.name STRING")
db.command("sql", "CREATE PROPERTY Person.age INTEGER")

# OpenCypher DDL also passes straight through to the engine
db.command("opencypher", "CREATE INDEX FOR (p:Person) ON (p.email)")
db.command(
    "opencypher",
    "CREATE CONSTRAINT FOR (p:Person) REQUIRE p.email IS TYPED STRING",
)

# Data operations must be in a transaction
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)
    db.command(
        "sql",
        "UPDATE Person SET age = :age WHERE name = :name",
        {"age": 31, "name": "Alice"},
    )
    db.command("sql", "DELETE FROM Person WHERE name = 'Alice'")
```

!!! warning "Transaction Required"
    Write operations must be wrapped in a transaction:

    ```python
    # ✅ Correct
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice'")

    # ❌ Will fail
    db.command("sql", "INSERT INTO Person SET name = 'Alice'")
    ```

---

### transaction

```python
db.transaction() -> TransactionContext
```

Create a transaction context manager.

**Returns:**

- `TransactionContext`: Context manager for transaction

**Example:**

```python
with db.transaction():
    for name in ["Alice", "Bob"]:
        db.command("sql", "INSERT INTO Person SET name = ?", name)
    # Automatic commit on success, rollback on exception
```

**Manual Transaction Control:**

```python
# Alternative: manual control
db.begin()
try:
    for name in ["Alice", "Bob"]:
        db.command("sql", "INSERT INTO Person SET name = ?", name)
    db.commit()
except Exception as e:
    db.rollback()
    raise
```

---

### begin

```python
db.begin()
```

Begin a new transaction. Prefer using `transaction()` context manager.

**Raises:**

- `ArcadeDBError`: If transaction cannot be started

---

### commit

```python
db.commit()
```

Commit the current transaction.

**Raises:**

- `ArcadeDBError`: If commit fails or no transaction is active

---

### rollback

```python
db.rollback()
```

Rollback the current transaction.

**Raises:**

- `ArcadeDBError`: If rollback fails

---

### run_in_transaction

```python
db.run_in_transaction(fn, retries: int = 12, backoff_s: float = 0.005)
```

Execute a callable inside a transaction with automatic retry on concurrent-modification
conflicts. Mirrors the Java API's `database.transaction(lambda)` semantics: on
`ConcurrentModificationException` / `NeedRetryException` the transaction is rolled back
and `fn` is re-executed, with linear backoff. The `with db.transaction():` context
manager cannot retry (a `with` block can't be re-entered), so use this for contended
multi-threaded writes.

Any other way out of `fn` rolls back too, and then propagates: a plain bug
(`TypeError`, `KeyError`) and `KeyboardInterrupt` / `SystemExit` included, matching the
Java side's `catch (final Throwable e)`. Nothing leaves an open transaction behind for
the next caller to inherit.

**Parameters:**

- `fn`: Zero-argument callable executed inside the transaction
- `retries` (int): Max retry attempts on conflict (default: 12)
- `backoff_s` (float): Base sleep between attempts, grows linearly (default: 0.005)

**Returns:**

- The return value of `fn`

**Raises:**

- `ArcadeDBError`: If `fn` fails with a non-retryable error, or retries are exhausted
- Anything else `fn` raises, re-raised unchanged after the rollback

**Example:**

```python
def transfer():
    db.command("sql", "UPDATE Account SET balance = balance - 10 WHERE id = 1")
    db.command("sql", "UPDATE Account SET balance = balance + 10 WHERE id = 2")

db.run_in_transaction(transfer)
```

---

### new_vertex

```python
db.new_vertex(type_name: str) -> Vertex
```

Create a new, unsaved vertex (graph node) through the wrapper API. Creating it needs no
transaction; **its `save()` does**. Outside a transaction, `save()` raises the Java
`com.arcadedb.exception.TransactionException` ("Transaction not begun"), not
`ArcadeDBError`.

**Parameters:**

- `type_name` (str): Vertex type name (must be defined in schema)

**Returns:**

- `Vertex`: Python `Vertex` wrapper with `.set()`, `.save()` methods

**Raises:**

- `ArcadeDBError`: If the type doesn't exist

**Compatibility example:**

```python
with db.transaction():
    vertex = db.new_vertex("Person")
    vertex.set("name", "Alice")
    vertex.set("age", 30)
    vertex.save()

    print(f"Created: {vertex.get_rid()}")
```

**Preferred application pattern:**

```python
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Person SET name = ?, age = ?",
        "Alice",
        30,
    )
```

!!! info "Creating Edges"
    There is no `db.new_edge()` method. For application code, prefer SQL/OpenCypher edge
    creation instead of wrapper-level `vertex.new_edge(...)` calls:

    ```python
    db.command(
        "sql",
        "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name = 'Alice') TO (SELECT FROM Person WHERE name = 'Bob')",
    )
    ```
    See [Graph Operations](../guide/graphs.md) for details.

---

### new_document

```python
db.new_document(type_name: str) -> Document
```

Create a new, unsaved document (non-graph record) through the wrapper API. Creating it
needs no transaction; **its `save()` does**, and raises the Java `TransactionException`
outside one, as for [`new_vertex`](#new_vertex).

**Parameters:**

- `type_name` (str): Document type name

**Returns:**

- `Document`: Python `Document` wrapper

**Compatibility example:**

```python
with db.transaction():
    doc = db.new_document("Person")
    doc.set("name", "Alice")
    doc.set("email", "alice@example.com")
    doc.save()
```

**Preferred application pattern:**

```python
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Person SET name = ?, email = ?",
        "Alice",
        "alice@example.com",
    )
```

---

### insert_many

```python
db.insert_many(type_name: str, rows, commit_every: int = 10_000,
               parallel: bool = False) -> int
```

Bulk-insert documents with **one FFI crossing per batch** instead of several
JNI calls per row. Rows are serialized to a single JSON string and looped
Java-side, which makes this the fastest document-ingest path from Python
(measured ~3x over a per-row SQL loop and ~1.7x over per-row async
creation). Manages its own transactions unless one is already active.
For data that already lives in columns, [`insert_columns`](#insert_columns) is
faster still (2.24x on the same rows).

**Parameters:**

- `type_name` (str): Target document type (must exist)
- `rows` (iterable of dict): One dict per document; values must be
  JSON-representable (str/int/float/bool/None, nested lists/dicts). Rows
  with other types (e.g. `datetime`, `bytes`) fall back transparently to
  the per-row path, and so do values the JSON text would change on the way
  to the engine: an integer beyond 64 bits, NaN or Infinity, a dict key that
  is not a `str`, and a string with a lone surrogate. The per-row path stores
  such a value exactly or raises, as `Document.set` does.
- `commit_every` (int): Transaction batch size in synchronous mode
  (0 = single transaction; ignored when a transaction is already open).
- `parallel` (bool): Route rows through the async executor's parallel
  bucket writers and wait for completion (out-of-order writes). On a laptop
  (4 performance cores, parallel level 3, 1,000,000 rows, 6 runs per arm,
  engine `b22b5e9954`, 2026-10-04) it was 1.11x to 1.14x faster than the
  synchronous mode at 1, 3, 4, and 8 buckets alike
  (`CREATE DOCUMENT TYPE T BUCKETS n`); 8 buckets were no faster than 1.
  The maintainers' rule
  (ArcadeData/arcadedb#8478): a bucket count equal to, or a multiple of, the
  executor's parallel level (`async_executor().get_parallel_level()`, default
  cores - 1), decided when the type is created. Each writer commits every
  `arcadedb.asyncTxBatchSize` records (default 10,240); `commit_every` does
  not apply to this mode. Each bucket carries its own sub-index, so on a
  multi-bucket type every index lookup, and every unique-key check on insert,
  runs once per bucket; for a type you load or look up by a key, route records
  by that key with the partitioned strategy (it needs a UNIQUE index on the
  key): ``ALTER TYPE T BucketSelectionStrategy `partitioned('id')` ``. The
  same laptop, 400,000 rows, 4 buckets, UNIQUE `id`, 6 runs per arm: the
  parallel load 3.15 s against 2.53 s partitioned, a keyed lookup 16.2
  against 14.6 us.

**Returns:**

- `int`: Number of documents inserted

**Raises:**

- `ArcadeDBError`: If the load fails; in the parallel mode also when the
  writers report any record they could not store (a duplicate key, a failed
  batch commit), once the load completes. Records other than the failed ones
  may have been stored.

**Example:**

```python
db.command("sql", "CREATE DOCUMENT TYPE Order")
n = db.insert_many(
    "Order",
    ({"oid": i, "amount": i * 1.5} for i in range(1_000_000)),
)
```

---

### insert_columns

```python
db.insert_columns(type_name: str, columns, commit_every: int = 10_000,
                  parallel: bool = False) -> int
```

Bulk-insert documents **from whole columns**, the recommended path when the data
already lives in columns (a pandas `DataFrame`, a parquet batch, numpy arrays).
Each column crosses the bridge once as one typed array (a `long[]` or `double[]`
copied from the numpy buffer, a `boolean[]`, a `String[]` from a list) and the
documents are built Java-side, instead of one JSON text per batch that the
engine parses and copies key by key. Measured on a laptop on the first
2,000,000 TPC-H SF1 line items (nine typed properties, commit every 10,000,
same rows, cores, and engine, p50 of 3): 8.21 s against 18.42 s for
`insert_many` (2.24x); every arm stored the same sums and count. Cheaper
row-wise bridges gained only 2-12% (tuples plus `dict(zip())`, `DataFrame.to_json`).
Same failure contract as `insert_many`: the transaction the call opened is
rolled back on any failure, a transaction the caller opened is left to the caller.

**Parameters:**

- `type_name` (str): Target document type (must exist)
- `columns` (mapping or `DataFrame`): `{property name: column}`, every column
  the same length. A numpy array of an integer, float, or bool kind crosses as
  one buffer copy; a string or object array and any other sequence convert per
  element (`None` is a null; a `str` reuses one Java String per distinct value).
  A float `NaN` in a numpy float column is stored as NaN, not as null: use a
  sequence with `None` for nulls. A pandas nullable column (`Int64`, `string`)
  converts with its `<NA>` as null. `datetime64`, `timedelta64`, and complex
  columns do not cross natively (`TypeError`): convert them to Python values or
  use `insert_many`.
- `commit_every` (int): Transaction batch size in synchronous mode (ignored
  when a transaction is already open)
- `parallel` (bool): Hand the documents to the async executor's parallel bucket
  writers and wait for completion, exactly as `insert_many(parallel=True)`
  does: the same bucket-count rule (`CREATE DOCUMENT TYPE T BUCKETS n`, a count
  equal to or a multiple of `async_executor().get_parallel_level()`,
  ArcadeData/arcadedb#8478), the same out-of-order writes, `commit_every` does
  not apply. Only the transport differs.

**Returns:**

- `int`: Number of documents inserted

**Raises:**

- `ValueError`: no columns, columns of different lengths, a name that is not a
  string, a 2-D array, or an unsigned value beyond the signed 64-bit range;
  raised before anything is written
- `TypeError`: a numpy column of a dtype that does not cross natively
- `ArcadeDBError`: the load fails (a duplicate key, a value the declared
  property type refuses); in the parallel mode also when the writers report any
  record they could not store, once the load completes

**Example:**

```python
import numpy as np

db.command("sql", "CREATE DOCUMENT TYPE Reading")
n = db.insert_columns("Reading", {
    "id": np.arange(1_000_000, dtype=np.int64),
    "value": np.random.random(1_000_000),
    "label": ["a", "b"] * 500_000,
})
```

---

### lookup_by_rid

```python
db.lookup_by_rid(rid: str) -> Any
```

Lookup a record by its RID.

**Parameters:**

- `rid` (str): Record ID string (e.g. "#10:5")

**Returns:**

- `Record` object (Vertex, Document, or Edge)

**Raises:**

- `ArcadeDBError`: If no record has that RID (the message names the engine's
  `RecordNotFoundException`)

**Example:**

```python
try:
    record = db.lookup_by_rid("#10:5")
    print(record.get("name"))
except ArcadeDBError:
    print("no record with that RID")
```

---

### lookup_by_key

```python
db.lookup_by_key(type_name: str, keys: List[str], values: List[Any]) -> Optional[Document]
```

Lookup a record by an indexed key (index-based: O(1) for a hash index, O(log n) for an
`LSM_TREE` index).

**Parameters:**

- `type_name` (str): Type name
- `keys` (List[str]): Indexed property names
- `values` (List[Any]): Values for the indexed properties

**Returns:**

- Python record wrapper (`Document`, `Vertex`, or `Edge`, matching the underlying
  record type) or `None` if not found

**Example:**

```python
db.command("sql", "CREATE VERTEX TYPE User")
db.command("sql", "CREATE PROPERTY User.email STRING")
# lookup_by_key is an equality lookup, so a hash index serves it (see "Index choice" in the queries guide)
db.command("sql", "CREATE INDEX ON User (email) UNIQUE_HASH")

with db.transaction():
    db.new_vertex("User").set("email", "alice@example.com").save()

found = db.lookup_by_key("User", ["email"], ["alice@example.com"])
if found:
    print(found.get("email"))
```

---

### to_java_rid

```python
db.to_java_rid(value) -> Any
```

Convert a Python-side value into a Java `RID` object suitable for low-level Java API
calls. Accepts a RID string (e.g. `"#10:5"`), a Python record wrapper
(`Document`/`Vertex`/`Edge`), or a Java record/identifiable; values that are already
Java RIDs pass through unchanged.

**Parameters:**

- `value`: RID string, record wrapper, or Java record/RID object

**Returns:**

- Java `com.arcadedb.database.RID` object (or the input's identity)

**Example:**

```python
java_rid = db.to_java_rid("#10:5")
```

---

### count_type

```python
db.count_type(type_name: str) -> int
```

Count records of a specific type (polymorphic). Returns 0 if the type is missing.

---

### drop

```python
db.drop()
```

Drop the entire database (irreversible).

---

### is_transaction_active

```python
db.is_transaction_active() -> bool
```

Check if a transaction is currently active.

---

### set_wal_flush

```python
db.set_wal_flush(mode: str)
```

Configure WAL flush strategy. Modes: `"no"` (the default: a commit survives a process
crash but not a power cut), `"yes_nometadata"` (flush the data at commit), and
`"yes_full"` (flush data and metadata at commit). The setting covers the commits of
every thread on this database and no other database. Any other mode raises
`ValueError`.

---

### set_read_your_writes

```python
db.set_read_your_writes(enabled: bool)
```

Toggle read-your-writes consistency for the current connection. When enabled,
uncommitted changes in the current transaction are visible in subsequent reads.
Disabling can improve concurrency but may show stale data.

---

### is_read_your_writes

```python
db.is_read_your_writes() -> bool
```

Return whether read-your-writes consistency is currently enabled.

**Returns:**

- `bool`: True if read-your-writes is enabled

---

### set_auto_transaction

```python
db.set_auto_transaction(enabled: bool)
```

Enable or disable automatic transaction management for this database handle.

It is **off by default**: a data write outside a transaction (`db.command("sql",
"INSERT ...")`, or a wrapper's `save()`) raises "Transaction not begun". With
`set_auto_transaction(True)`, such a write runs in a transaction of its own that
commits when the statement ends. The setting does not persist: a database opened again
starts with it off. Prefer `with db.transaction():` for writes.

---

### async_executor

```python
db.async_executor() -> AsyncExecutor
```

The executor runs individual statements, queries, and record operations off the calling
thread. It is not the bulk-write path: use [`insert_many`](#insert_many) (whose
`parallel=True` mode runs on this executor's writers) or [`graph_batch`](#graph_batch)
for bulk loads. See
[Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation) and the
[AsyncExecutor API](async_executor.md).

---

### graph_batch

```python
db.graph_batch(...) -> GraphBatch
```

Create a `GraphBatch` helper for high-throughput graph ingestion.

This is the repository's recommended bulk graph-ingest path from Python when you need to
load many vertices and edges efficiently.

**Common options:**

- `batch_size`: buffered edge batch size
- `expected_edge_count`: tuning hint for large graph loads
- `light_edges`: create property-less edges as light edges
  Warning: `light_edges=True` into an edge type that is not declared `LIGHTWEIGHT` makes an openCypher one-hop `count(*)` answer 0 on the 26.10.1 engine, an open upstream bug; see [Known Engine Issues](../guide/known-issues.md#an-opencypher-one-hop-count-answers-0-for-edges-loaded-with-light_edgestrue-into-a-type-that-is-not-lightweight) for the workaround.
- `commit_every`: commit cadence during flush
- `use_wal`: enable WAL for higher durability
- `parallel_flush`: parallelize flush/close work
- `commit_retries` / `commit_retry_delay_ms`: retry budget and initial back-off
  for a vertex commit that hits a transient `NeedRetryException`
- `chunk_cache_capacity`: bound on each OUT/IN head-chunk RID cache
- `max_deferred_incoming_edges`: run the incoming-edge pass early from `flush()`
  rather than once at `close()`

**Example:**

```python
with db.graph_batch(expected_edge_count=50000) as batch:
    alice = batch.create_vertex("Person", name="Alice")
    bob = batch.create_vertex("Person", name="Bob")
    batch.new_edge(alice, "Knows", bob, since=2024)
```

See [Graph Operations](../guide/graphs.md) and the graph benchmark examples for guidance.

---

### import_documents

```python
db.import_documents(source: str, document_type: str = "Document", ...) -> ImportResult
```

Import document-shaped data through ArcadeDB's Java importer framework.

This is a narrow wrapper for file-based document imports such as CSV into a document
type. It is supported, but it is not the recommended default for large Python-managed
bulk ingest.

**Common options:**

- `file_type`: importer file type such as `"csv"`
- `delimiter`: delimiter override for delimited formats
- `commit_every`: importer transaction split interval
- `parallel`: importer worker count
- `wal`: WAL override during import
- `extra_settings`: additional raw importer settings

Every parameter, the side effects while it runs, and the returned `ImportResult` are in
the [Import API](importer.md#dbimport_documents).

**Example:**

```python
db.import_documents("./movies.csv", document_type="Movie", file_type="csv")
```

For bulk ingest from Python, prefer [`insert_many`](#insert_many) for documents and
[`graph_batch`](#graph_batch) for graphs (see
[Bulk Ingest Recommendation](../guide/import.md#bulk-ingest-recommendation)).

---

### export_database

```python
db.export_database(
    file_path: str,
    format: str = "jsonl",
    overwrite: bool = False,
    include_types: Optional[List[str]] = None,
    exclude_types: Optional[List[str]] = None,
    verbose: int = 1,
) -> dict
```

Export the database to JSONL (backup/restore). `format="graphml"` and
`format="graphson"` raise `ArcadeDBError`: their exporters come from the
`arcadedb-gremlin` module, which the wheel does not bundle. See the
[Exporter API](exporter.md).

---

### export_to_csv

```python
db.export_to_csv(query: str, file_path: str, language: str = "sql", fieldnames: Optional[List[str]] = None)
```

Run a query and write results to CSV. `fieldnames` sets the header and the column
order; it cannot rename columns. It must name every column the query returns (a name
the rows lack is written empty): a missing column raises `ArcadeDBError` ("dict contains
fields not in fieldnames") after the header is written, which leaves a header-only file.
To rename, alias the columns in the query (`SELECT userId AS user ...`). `DATE` and
`DATETIME` values are written as epoch-millisecond integers. See the
[Exporter API](exporter.md#export_to_csv).

---

### create_vector_index

```python
db.create_vector_index(
    vertex_type: str,
    vector_property: str,
    dimensions: int,
    id_property: str | None = None,
    distance_function: str = "cosine",
    max_connections: int = 32,
    beam_width: int = 100,
    quantization: str = "INT8",
    encoding: str | None = None,
    location_cache_size: int | None = None,  # removed: any value raises ValueError
    graph_build_cache_size: int | None = None,
    mutations_before_rebuild: int | None = None,
    store_vectors_in_graph: bool = False,
    add_hierarchy: bool | None = True,
    pq_subspaces: int | None = None,
    pq_clusters: int | None = None,
    pq_center_globally: bool | None = None,
    pq_training_limit: int | None = None,
    build_graph_now: bool = True,
) -> VectorIndex
```

Create a vector index for similarity search (JVector implementation). Existing records
are indexed automatically when the index is created. By default, graph preparation is
performed immediately (`build_graph_now=True`).

For normal application code and documentation examples, prefer SQL `CREATE INDEX ...
LSM_VECTOR METADATA {...}` because it is cleaner and aligns with the SQL-first workflow.
Keep `create_vector_index()` for Python-driven setup, tests, or manual control when you
specifically need that surface.

**Parameters:**

- `vertex_type` (str): Vertex type containing vectors
- `vector_property` (str): Property storing vector arrays
- `dimensions` (int): Vector dimensionality
- `id_property` (str | None): Optional property used for key-based vector lookup.
- `distance_function` (str): `"cosine"`, `"euclidean"`, or `"dot_product"`
- `max_connections` (int): Per-layer graph degree (default: 32; Vamana degree, use 2*M to match an hnswlib M). Maps to
  `maxConnections` in HNSW (JVector).
- `beam_width` (int): Beam width for search/construction (default: 100). Maps to
  `beamWidth` in HNSW (JVector).
- `quantization` (str | None): `"INT8"` (recommended), `"BINARY"`, `"PRODUCT"` for PQ,
  or `None` for full precision (default: `"INT8"`). Prefer `"INT8"` for current
  production usage in these bindings; `"PRODUCT"`/PQ is currently not recommended for
  production workloads. In current ArcadeDB engine builds, `"PRODUCT"` also requires
  enough indexed vectors per bucket for PQ training. For tiny corpora, set `pq_clusters`
  explicitly to a small value or prefer another quantization mode.
- `encoding` (str | None): Optional storage encoding for the document property.
    Use `"INT8"` when the underlying property is `BINARY` and stores pre-quantized
    bytes. Do not combine `encoding="INT8"` with `quantization="INT8"`; use
    `quantization="NONE"` for native INT8 storage.
- `location_cache_size` (int | None): **removed** (ArcadeDB #5559, #5568). Passing a
  value raises `ValueError`; the engine no longer accepts the setting because bounding
  the vector-location index drops vectors from searches rather than spilling to disk.
- `graph_build_cache_size` (int | None): Override the number of vectors cached while the graph is built (default: `None`, the engine's automatic sizing; leave it unset, see [Build-time cache](../guide/vectors.md#build-time-cache-use-the-default)).
- `mutations_before_rebuild` (int | None): Override rebuild threshold (default: `None`, uses engine default).
- `store_vectors_in_graph` (bool): Persist vectors inline in graph file (faster reopen/search, larger graph).
- `add_hierarchy` (bool | None): Force enabling/disabling HNSW hierarchy (default: `True`).
- `pq_subspaces` (int | None): PQ subspaces (M). Requires `quantization="PRODUCT"`.
- `pq_clusters` (int | None): PQ clusters per subspace (K). Requires
  `quantization="PRODUCT"`. In current ArcadeDB engine builds, this should not exceed
  the number of indexed vectors available for PQ training in a bucket.
- `pq_center_globally` (bool | None): PQ global centering flag. Requires `quantization="PRODUCT"`.
- `pq_training_limit` (int | None): PQ training sample cap. Requires `quantization="PRODUCT"`.
- `build_graph_now` (bool): If `True` (default), eagerly builds/loads the vector graph immediately after index creation. Set to `False` to defer graph preparation to first query.

**Returns:**

- `VectorIndex`: Index object for similarity search

**Example:**

```python
import numpy as np

# Create schema (applies immediately)
db.command("sql", "CREATE VERTEX TYPE Document")
db.command("sql", "CREATE PROPERTY Document.embedding ARRAY_OF_FLOATS")
db.command("sql", "CREATE PROPERTY Document.id STRING")

# Secondary/manual option: create vector index from Python
index = db.create_vector_index("Document", "embedding", dimensions=384)

# Add vectors
with db.transaction():
    for i, embedding in enumerate(embeddings):
        vertex = db.new_vertex("Document")
        vertex.set("id", f"doc_{i}")
        vertex.set("embedding", arcadedb.to_java_float_array(embedding))
        vertex.save()

# Preferred query path: SQL search, with the query vector bound as a parameter
query_vector = np.random.rand(384).astype(np.float32)
rows = db.query(
    "sql",
    (
        "SELECT id, distance, (1 - distance) AS score "
        "FROM (SELECT expand(vectorNeighbors('Document[embedding]', ?, 5))) "
        "ORDER BY distance"
    ),
    arcadedb.to_java_float_array(query_vector),
).to_list()
```

See [Vector Search Guide](../guide/vectors.md) for details.

---

### close

```python
db.close()
```

Close the database connection. It also closes the async executor
([`async_executor`](#async_executor)) if this handle handed it out, and a `Database`
that is garbage-collected closes itself.

A result set, a result, or a record read from the database keeps its `Database` alive,
so a function can open a database, query it, and return the result without closing
anything: the database closes when the last of them is freed. While one is alive the
engine refuses a second `open_database()` of the same path ("already in use"). After
`close()`, reading a record, a record row (`SELECT FROM T`), or a result set that was not
read to its end raises `ArcadeDBError` ("Database is closed"), as `db.query()` does; a
projection or command `Result` that was already returned keeps its own values and stays
readable. Earlier versions returned empty rows or `None` values and the engine logged
`Possible corrupted record` for each read (humemai/arcadedb-embedded-python#117).

A handle from `ArcadeDBServer.get_database()` or `ArcadeDBServer.create_database()`
belongs to the server: `close()` only marks that handle closed, and the database stays open for the
server and its other handles until `server.stop()`.

**Example:**

```python
db = arcadedb.create_database("./mydb")
try:
    # Use database
    pass
finally:
    db.close()
```

!!! tip "Context Manager"
    Prefer using `with` statement for automatic cleanup

---

### is_open

```python
db.is_open() -> bool
```

Check if database connection is open.

**Returns:**

- `bool`: True if database is open

---

### get_name

```python
db.get_name() -> str
```

Get the database name.

**Returns:**

- `str`: Database name

---

### get_database_path

```python
db.get_database_path() -> str
```

Get the file system path to the database.

**Returns:**

- `str`: Database path

---

### schema

```python
db.schema -> Schema
```

Property that returns the database's [`Schema`](schema.md) wrapper, for creating and
inspecting types, properties, and indexes: `db.schema.create_vertex_type("User")`.

---

### get_java_database

```python
db.get_java_database() -> Any
```

Expose the wrapped Java `Database` object for low-level integrations. Use this only
when you need direct access to the underlying Java API (camelCase JPype methods);
normal application code should stay on the Python wrapper.

**Returns:**

- Java `com.arcadedb.database.Database` object

**Example:**

```python
java_db = db.get_java_database()
print(java_db.getSchema().getTypes().size())
```

---

## DatabaseFactory Class

Factory for creating and opening databases with custom configuration.

### Constructor

```python
DatabaseFactory(path: str, jvm_kwargs: Optional[dict] = None)
```

**Parameters:**

- `path` (str): Database path
- `jvm_kwargs` (Optional[dict]): Optional JVM args passed to `start_jvm()` (e.g. `{"heap_size": "8g"}`)

**Example:**

```python
factory = arcadedb.DatabaseFactory("./mydb")
if factory.exists():
    db = factory.open()
else:
    db = factory.create()
```

---

### create

```python
factory.create() -> Database
```

Create a new database.

---

### open

```python
factory.open() -> Database
```

Open an existing database.

---

### exists

```python
factory.exists() -> bool
```

Check if database exists.

---

## Context Manager Support

All database objects support context managers:

```python
# Database
with arcadedb.create_database("./mydb") as db:
    # Automatic cleanup
    pass

# Transaction
with db.transaction():
    # Auto commit/rollback
    pass
```

---

## Query Languages

### SQL

ArcadeDB's extended SQL with graph and document support:

```python
# Documents
db.query("sql", "SELECT FROM Person WHERE age > 25")

# Graph traversal
db.query("sql", "SELECT expand(out('Knows')) FROM Person WHERE name = 'Alice'")

# Aggregation
db.query("sql", "SELECT count(*) as total, avg(age) as avg_age FROM Person")
```

### OpenCypher

OpenCypher graph query language:

```python
db.query("opencypher", """
    MATCH (person:Person)-[:Knows]->(friend)
    WHERE person.age > 25
    RETURN friend.name, friend.age
""")
```

---

## Best Practices

### 1. Use Context Managers

```python
# ✅ Good - automatic cleanup
with arcadedb.create_database("./mydb") as db:
    pass

# ❌ Avoid - manual cleanup
db = arcadedb.create_database("./mydb")
db.close()
```

### 2. Always Use Transactions for Writes

```python
# ✅ Good
with db.transaction():
    person = db.new_document("Person")
    person.set("name", "Alice").save()

# ❌ Will fail
db.command("sql", "INSERT INTO Person SET name = 'Alice'")
```

### 3. Use Parameterized Queries

```python
# ✅ Good - safe from injection
name = user_input
db.query("sql", "SELECT FROM Person WHERE name = ?", name)

# ❌ Dangerous - SQL injection risk
db.query("sql", f"SELECT FROM Person WHERE name = '{user_input}'")
```

### 4. Check Database Existence

```python
if arcadedb.database_exists("./mydb"):
    db = arcadedb.open_database("./mydb")
else:
    db = arcadedb.create_database("./mydb")
```

---

## See Also

- [Graph Operations](../guide/graphs.md): Working with vertices and edges
- [Vector Search](../guide/vectors.md): Similarity search with HNSW (JVector) indexes
- [Quick Start](../getting-started/quickstart.md): Getting started guide
