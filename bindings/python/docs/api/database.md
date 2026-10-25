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
arcadedb.open_database(path: str, jvm_kwargs: Optional[dict] = None, read_only: bool = False) -> Database
```

Open an existing database.

**Parameters:**

- `path` (str): Path to the existing database
- `jvm_kwargs` (Optional[dict]): Optional JVM args passed to `start_jvm()` (e.g. `{"heap_size": "8g"}`)
- `read_only` (bool): Open in `ComponentFile.MODE.READ_ONLY`. Reads, queries and scans work; every write and schema change raises `ArcadeDBError` ("read only database"). `begin()` and `with db.transaction():` do not raise on entry: the first write does, and so does the commit; reads and queries need no transaction. Default `False`

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If database doesn't exist or can't be opened

**Example:**

```python
with arcadedb.open_database("./mydb") as db:
    result = db.query("sql", "SELECT FROM Person")
    print(f"Found {len(list(result))} records")

# Inspect a database that must not change
with arcadedb.open_database("./mydb", read_only=True) as db:
    assert db.is_read_only()
    db.query("sql", "SELECT count(*) AS n FROM Person").first().get("n")
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

Begin a new transaction. Prefer using `transaction()` context manager. The transaction runs at `READ_COMMITTED`; to choose `REPEATABLE_READ`, see [Isolation level](transactions.md#isolation-level).

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

Float vectors take a binary path: for a property declared `ARRAY_OF_FLOATS` whose value in every row of a chunk is a list or a numpy array of numbers of one length, the vectors of the chunk cross as one `float32` matrix beside the JSON, instead of as text. The stored values are the list's (the engine converts a list for such a property to float). A property that is not declared `ARRAY_OF_FLOATS`, or a vector that is ragged, missing or null in a row, stays in the JSON.

Bulk-insert documents with **one FFI crossing per chunk of rows** instead of
several JNI calls per row. The iterable is read 10,000 rows at a time and each
chunk is serialized to one JSON string and looped Java-side, so memory stays
bounded by the chunk whatever the row count (a generator of any length loads;
before #294 the whole input was held at once, about 1.5 KB per row). This is
the fastest document-ingest path from Python
(measured ~3x over a per-row SQL loop and ~1.7x over per-row async
creation). Manages its own transactions unless one is already active.
For data that already lives in columns, [`insert_columns`](#insert_columns) is
faster still (2.24x on the same rows).

**Parameters:**

- `type_name` (str): Target type (must exist). A document type gets documents and a vertex type gets vertices (use `graph_batch()` when edges follow); an edge type raises `ArcadeDBError`, because an edge needs both endpoints
- `rows` (iterable of dict): One dict per document, read lazily one chunk at
  a time; values must be JSON-representable (str/int/float/bool/None, nested
  lists/dicts). A chunk with other types (e.g. `datetime`, `bytes`) falls back
  transparently to the per-row path, and so do values the JSON text would change on the way
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

- `int`: Number of records inserted

**Raises:**

- `ArcadeDBError`: If the load fails; in the parallel mode also when the
  writers report any record they could not store (a duplicate key, a failed
  batch commit), once the load completes. Records other than the failed ones
  may have been stored.
- Any exception raised by `rows` itself propagates unchanged: the open batch
  is rolled back and the batches committed before it stay (in the parallel
  mode, rows already handed to the writers are waited for and may be stored).

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

A column can also be a 2-D numpy `float32` array: a column of vectors. The whole matrix crosses as one `float[]` (one buffer copy) and each document gets one row of it, which is what an `ARRAY_OF_FLOATS` property stores; no list, no JSON text. Another dtype (cast with `astype(np.float32)`), or a matrix with no columns, raises `ValueError`.

**Parameters:**

- `type_name` (str): Target type (must exist). A document type gets documents and a vertex type gets vertices (use `graph_batch()` when edges follow); an edge type raises `ArcadeDBError`, because an edge needs both endpoints
- `columns` (mapping or `DataFrame`): `{property name: column}`, every column
  the same length. A numpy array of an integer, float, or bool kind crosses as
  one buffer copy; a string or object array and any other sequence convert per
  element (`None` is a null; a `str` reuses one Java String per distinct value).
  A float `NaN` in a numpy float column is stored as NaN, not as null: use a
  sequence with `None` for nulls. A pandas nullable column (`Int64`, `string`)
  converts with its `<NA>` as null. `datetime64`, `timedelta64`, and complex
  columns do not cross natively (`TypeError`): convert them to Python values, use
  `insert_many`, or load the frame with [`insert_dataframe`](#insert_dataframe), which
  maps timestamps.
- `commit_every` (int): Transaction batch size in synchronous mode, any int as
  for `insert_many` (0 = single transaction; ignored when a transaction is already
  open)
- `parallel` (bool): Hand the documents to the async executor's parallel bucket
  writers and wait for completion, exactly as `insert_many(parallel=True)`
  does: the same bucket-count rule (`CREATE DOCUMENT TYPE T BUCKETS n`, a count
  equal to or a multiple of `async_executor().get_parallel_level()`,
  ArcadeData/arcadedb#8478), the same out-of-order writes, `commit_every` does
  not apply. Only the transport differs.

**Returns:**

- `int`: Number of records inserted

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

### insert_dataframe

```python
db.insert_dataframe(type_name: str, df, *, batch_size: int = 10_000,
                    parallel: bool = False) -> int
```

Load a **pandas or Polars `DataFrame`** into a type, in batches. The frame is read as an
Arrow table, so [`insert_arrow`](#insert_arrow) has the type mapping and the rules for
declared properties. What the two libraries do differently:

- A pandas `NaN` in a float column is pandas' missing value, so it loads as a null. A
  Polars `NaN` stays a `NaN`, because Polars keeps null and NaN apart.
- The pandas index is not loaded: `df.reset_index()` makes it a column. Pandas column
  names must be strings.
- A Polars `LazyFrame` is refused (`TypeError`): call `.collect()` first.
- Any other object that speaks the Arrow PyCapsule interface (`__arrow_c_stream__`)
  also loads.

A **document type** gets documents, through the same typed-array path as
[`insert_columns`](#insert_columns) (integers, floats, and booleans without nulls cross as
one buffer copy; timestamps, dates, decimals, lists, and strings convert per element). A
**vertex type** gets vertices, through `GraphBatch.create_vertices()`. An **edge type** is
refused (`ArcadeDBError`): load the vertices, then buffer the edges with
[`graph_batch().new_edges()`](graph_batch.md), because an edge needs the RIDs of its two
vertices and no column convention for them is fixed here.

**Parameters:**

- `type_name` (str): Target type (must exist, with or without declared properties)
- `df`: A pandas or Polars `DataFrame`
- `batch_size` (int): Rows per batch (default `10_000`). A batch is converted, written,
  and committed on its own, so memory stays bounded for a large frame
- `parallel` (bool): Documents only: hand each batch to the async executor's parallel
  bucket writers, as `insert_columns(parallel=True)` does. A vertex type raises
  `ValueError`

**Returns:**

- `int`: Number of records written

**Raises:**

- `ImportError`: pyarrow is not installed (`pip install 'arcadedb-embedded[arrow]'`)
- `ValueError`: no columns, duplicate or non-string column names, a `batch_size` that is
  not a positive integer, or `parallel` with a vertex type
- `TypeError`: a column type with no mapping (time of day, duration, map), a type that
  does not load into the property the type declares for it, a `LazyFrame`, or an object
  that is not a frame or an Arrow table. Raised before anything is written
- `ArcadeDBError`: the type does not exist or is an edge type, or the load fails (a
  duplicate key, a value past a declared property's range). The batch in flight is rolled
  back, the batches before it stay committed, and the message says how many rows that is.
  A transaction the caller opened is left to the caller (a vertex load refuses to run
  inside one, as `GraphBatch` does): the batches join it, the message then says the rows
  were written in your transaction, not committed, and a rollback removes them

**Example:**

```python
import pandas as pd

db.command("sql", "CREATE DOCUMENT TYPE Trip")
df = pd.DataFrame({
    "id": [1, 2, 3],
    "fare": [12.5, None, 7.25],
    "picked_up": pd.to_datetime(["2026-01-01 08:00", "2026-01-01 09:30", None]),
})
db.insert_dataframe("Trip", df)  # 3
```

---

### insert_arrow

```python
db.insert_arrow(type_name: str, table, *, batch_size: int = 10_000,
                parallel: bool = False) -> int
```

Load an **Arrow table** (`pyarrow.Table`, `RecordBatch`, `RecordBatchReader`, or any object
with `__arrow_c_stream__`) into a type, in batches. A reader is read whole before the
load starts. The parameters, return value, and exceptions are those of
[`insert_dataframe`](#insert_dataframe).

It is one function per source kind rather than one function that takes everything,
because the two sources differ in a way the caller should see in the name: a DataFrame has
library-specific missing-value rules (pandas `NaN` versus Polars `NaN`), an Arrow table
has none. `insert_dataframe` converts to Arrow and calls the same code.

**Arrow type to stored type.** A property the type does not declare takes the stored type
below; a declared property converts to its declared type (next table).

| Arrow type | Stored as |
|---|---|
| `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32` | `LONG` |
| `uint64` | `LONG`, up to 2\*\*63 - 1 (a larger value raises `ValueError` before anything is written) |
| `float16`, `float32`, `float64` | `DOUBLE` (`float32` widens exactly) |
| `bool` | `BOOLEAN` |
| `string`, `large_string`, `string_view` | `STRING` |
| `dictionary` (a pandas categorical, a Polars `Categorical`) | its value type |
| `binary`, `large_binary` | `byte[]`, read back as a list of signed ints |
| `timestamp`, no time zone, unit `s`, `ms`, `us`, or `ns` | a UTC date-time: the wall clock as it shows, with the input's precision (see below) |
| `timestamp` with a time zone, any unit | a UTC date-time: converted to UTC |
| `date32`, `date64` | `DATE` |
| `decimal128`, `decimal256` | `DECIMAL`, every digit kept |
| `list`, `large_list`, `fixed_size_list` | `LIST` (an `ARRAY_OF_*` when declared so) |
| `struct` | `MAP` |
| `null` (a column of only nulls) | no value |
| `time32`, `time64`, `duration`, `map`, `interval`, `union`, `extension` | no mapping: `TypeError` |

A null is stored as a missing property.

**DATETIME precisions.** A `DATETIME` is a UTC wall clock, whatever the host's time zone. A
timestamp with a zone is converted to UTC; one without is taken as the wall clock it
shows (the rule `Document.set()` applies to a `datetime`). The value is read from the
integer epoch count, so a `ns` column is not cut to microseconds on the way in. For a
declared property what is kept is what the property's type keeps: `DATETIME`
milliseconds, `DATETIME_MICROS` microseconds, `DATETIME_NANOS` nanoseconds,
`DATETIME_SECOND` seconds. A column the type does not declare keeps the input's own
precision (a `ns` column is stored with its nanoseconds).

**Reading timestamps back is coarser than storing them.** `Result.get()` returns a Python
`datetime`, which holds microseconds at most. `to_arrow()`, `to_polars()`, `to_dataframe()`
and `to_columns()` return milliseconds (`timestamp[ms]`, `datetime64[ms]`), also for
`DATETIME_MICROS` and `DATETIME_NANOS` properties and for `DATE`. Nanoseconds do not
come back through the bindings: keep an integer epoch-nanosecond column if you need them.

**Declared properties.** A property the type declares converts, but only along the pairs
below, checked before a row is written. Anything else raises `TypeError` that names the
column, the Arrow type, and the declared type, because the engine would otherwise
truncate or guess (a float into an `INTEGER` property keeps the integer part; a string
into a `LONG` property is parsed).

| Arrow kind | Loads into a declared |
|---|---|
| integer | `BYTE`, `SHORT`, `INTEGER`, `LONG`, `FLOAT`, `DOUBLE`, `DECIMAL`, `STRING` |
| floating | `FLOAT`, `DOUBLE`, `DECIMAL`, `STRING` |
| bool | `BOOLEAN`, `STRING` |
| string | `STRING`, `LINK` (RID text) |
| binary | `BINARY` |
| timestamp | `DATETIME`, `DATETIME_SECOND`, `DATETIME_MICROS`, `DATETIME_NANOS`, `STRING` |
| date | `DATE`, any `DATETIME*`, `STRING` |
| decimal | `DECIMAL`, `DOUBLE`, `FLOAT`, `STRING` |
| list | `LIST`, `ARRAY_OF_SHORTS`, `ARRAY_OF_INTEGERS`, `ARRAY_OF_LONGS`, `ARRAY_OF_FLOATS`, `ARRAY_OF_DOUBLES` |
| struct | `MAP`, `EMBEDDED` |

The engine still refuses a value past the declared type's range (an integer of 2\*\*40 into
an `INTEGER` property): the load fails with `ArcadeDBError` and the batch is rolled back.
A property on a parent type counts as declared.

**Example:**

```python
import pyarrow as pa

db.command("sql", "CREATE VERTEX TYPE Station")
db.command("sql", "CREATE PROPERTY Station.id INTEGER")
table = pa.table({"id": [1, 2], "name": ["Central", "North"]})
db.insert_arrow("Station", table)  # 2 vertices; the int64 column converts to INTEGER
```

---

### lookup_by_rid

```python
db.lookup_by_rid(rid: str) -> Any
```

Lookup a record by its RID.

**Parameters:**

- `rid` (str | RID): Record ID string (e.g. "#10:5"), or the RID object a row holds (see
  [Record ids in rows](results.md#record-ids-in-rows))

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

### register_function

```python
db.register_function(
    name: str,
    fn: Callable,
    *,
    min_args: int | None = None,
    max_args: int | None = None,
    deterministic: bool = False,
    replace: bool = False,
) -> None
```

Register a Python function that SQL and openCypher statements can call. Python is the
only way to do this: no statement can define a function whose body is Python.

```python
db.register_function("slugify", lambda s: None if s is None else s.lower().replace(" ", "-"))
db.query("sql", "SELECT slugify(name) AS slug FROM Person WHERE slugify(name) = 'ann-lee'")

# openCypher accepts a function name it does not know only when it has a namespace
db.register_function("py.slugify", lambda s: s.lower().replace(" ", "-"))
db.query("opencypher", "MATCH (p:Person) RETURN py.slugify(p.name) AS slug")
```

**Parameters:**

- `name` (str): letters, digits and underscores, optionally joined by dots (`py.slugify`).
  SQL names are case-insensitive. A name the engine already has (`abs`, `count`, `toUpper`,
  `id`, ...) raises `ArcadeDBError`. Use a dotted name to call the function from openCypher:
  its validator rejects a bare name it does not know.
- `fn` (callable): called with positional arguments only
- `min_args`, `max_args` (int, optional): the argument counts a call may pass. They default
  to what the signature of `fn` allows (parameters without a default, all positional
  parameters, unlimited with `*args`). A call with another count fails with an error that
  names the function.
- `deterministic` (bool): `True` only when `fn` returns the same result for the same
  arguments and reads nothing else. The planner may then fold a call over constants at plan
  time and cache plans that contain it. Leave it `False` for anything that reads the clock, a
  random source, a counter, or the database.
- `replace` (bool): replace a Python function already registered under this name
  (otherwise `ArcadeDBError`)

**Conversion:** arguments reach `fn` through
[`convert_java_to_python`](type_conversion.md) (SQL `NULL` is `None`; a record argument
arrives as a `Document`, `Vertex` or `Edge`) and the return value goes back through
[`convert_python_to_java`](type_conversion.md), so `None`, numbers, strings, bools,
`Decimal`, `datetime`, lists and dicts work.

**Errors:** an exception raised in `fn` (any `BaseException`) fails the statement with an
`ArcadeDBError` whose text names the function and the Python exception, for example
`Python function 'explode' failed: ValueError: bad input`. The JVM never sees a Python
exception. The traceback goes to the `arcadedb_embedded.callbacks` debug log. As for any
query, an error raised while the rows are produced surfaces when you read the result set.
A `KeyboardInterrupt` (Ctrl-C) in `fn`, or a signal that lands while the statement runs, is
the one exception: the statement is aborted and the caller gets a `KeyboardInterrupt`,
chained from the `ArcadeDBError`, whether the signal landed in `fn`, in the engine, or
between the two, or while JPype converts the engine's exception (JPype then fails with
`RuntimeError: Fatal error occurred`, which the bindings report as that `KeyboardInterrupt`,
with the `ArcadeDBError` that holds the JPype text as its cause). The database works as before. A return value that cannot be converted
(a numpy array, an integer past 2\*\*63) fails the statement with a `TypeError` or
`OverflowError` in the `ArcadeDBError` text.

**Threading:** the engine may call `fn` on its own threads (an async executor's writers, a
parallel scan). JPype attaches each such thread, and the GIL serializes the calls, so `fn`
never runs in parallel with other Python code and does not need to be thread-safe against
itself. A function that blocks on another thread's database work can deadlock the statement
that called it.

**Scope:** the engine registers functions for the whole process, not for one database: every
database in this process sees the function. A `Database` removes the functions it registered
when it is closed. Register before concurrent statements start: the engine's function table
is not safe to change while another thread resolves a name. An aggregate (one result per
group) cannot be written this way.

**Cost:** each call is one round trip between the engine and Python, paid once per row a
statement calls `fn` on (see [Python functions](../guide/core/queries.md#python-functions-in-sql-and-opencypher));
compute in SQL where a SQL expression can do the work.

**Raises:**

- `ValueError`: invalid name or argument counts
- `TypeError`: `fn` is not callable
- `ArcadeDBError`: the name is an engine function, a Python function with this name exists and
  `replace` is false, or `fn` has a keyword-only parameter without a default

---

### unregister_function

```python
db.unregister_function(name: str) -> None
```

Remove a function registered through this database. A statement that calls it afterwards
fails with an unknown-function error, including one whose text ran before.

**Raises:**

- `ArcadeDBError`: this database did not register a function with this name

---

### on

```python
db.on(
    event: str,
    fn: Callable,
    type_name: str | None = None,
) -> EventHandle
```

Call `fn(record)` when a record is created, updated, or deleted. The record is a
`Document`, `Vertex` or `Edge`. Python is the only way to do this: no statement can run
Python on a change.

```python
audit = []
handle = db.on("after_create", lambda rec: audit.append(rec.get_rid()), type_name="Person")

# a before_* callback that returns False vetoes the change
db.on("before_delete", lambda rec: rec.get("name") != "root", type_name="Person")

handle.remove()
```

**Events:** `before_create`, `after_create`, `before_update`, `after_update`,
`before_delete`, `after_delete`. Each fires once per record changed, whether the change came
from SQL, openCypher, or a record's `save()` and `delete()`.

**Veto:** a `before_*` callback that returns `False` stops the change: the record is not
written, and the statement or `save()` goes on without it, as with the engine's own
listeners. Any other return value (including `None`) allows it. The return value of an
`after_*` callback is ignored.

**Timing:** a `before_*` event fires before the record is written. An `after_*` event
fires right after the write and before the commit, so a transaction that later rolls back
has already fired its `after_*` callbacks; do not use them for side effects outside the
database unless you commit first.

**Errors:** an exception raised in a callback is not swallowed. It fails the operation that
fired the event with an `ArcadeDBError` that names the event and the Python exception, and
the surrounding transaction does not commit.

**Type filter:** with `type_name`, the callback fires only for records of exactly that type
(not its subtypes) and keeps firing after schema changes. Without it, the callback fires for
every record of the database.

**Threading:** a callback runs inside the operation that fired the event, on the thread
that runs it. That is the engine's thread for an async write; the GIL serializes the calls.
Keep it quick: it adds to every change of that type.

**Raises:**

- `ValueError`: `event` is not one of the six
- `TypeError`: `fn` is not callable
- `ArcadeDBError`: `type_name` does not exist

#### EventHandle

Returned by `db.on()`.

| Member | Meaning |
|---|---|
| `remove()` | Unregister the callback. Calling it again does nothing |
| `active` | `True` until `remove()` |
| `event`, `type_name` | What it was registered for |

An `EventHandle` is also a context manager: `with db.on("after_create", fn): ...` removes the
callback on exit. Closing the database drops its callbacks.

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
  Warning: from ArcadeDB 26.10.2, `light_edges=True` raises `ArcadeDBError` from `new_edge` for an edge type that is not declared `LIGHTWEIGHT`; declare it with `CREATE EDGE TYPE ... LIGHTWEIGHT` or leave the option out. On 26.10.1 and earlier the load succeeds but an openCypher one-hop `count(*)` over those edges answers 0, and a graph loaded that way stays wrong; see [Known Engine Issues](../guide/known-issues.md#fixed-in-26102).
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
- `quantization` (str | None): `"INT8"`, `"BINARY"`, `"PRODUCT"` for PQ,
  or `None` for full precision (default: `"INT8"`, a choice of this helper; a SQL
  `CREATE INDEX` without `"quantization"` in its `METADATA` builds a full-precision index,
  the engine's `NONE`). No finished study shows `"INT8"` is the best choice; see
  [Quantization](../guide/vectors.md#quantization). `"PRODUCT"` walks the graph on PQ codes and re-ranks on
  the stored vectors from ArcadeDB 26.11.1 on; the measured size and recall are in
  [Product quantization (PQ) in SQL](../guide/vectors.md#product-quantization-pq-in-sql),
  which also says no timing of PQ search exists yet. On the 26.10.x wheels it scores every
  candidate on the full-precision vectors and writes PQ codes nothing reads
  ([ArcadeDB #10514](https://github.com/ArcadeData/arcadedb/issues/10514)). `"PRODUCT"` also requires
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
  The default is a deliberate choice of these bindings. The engine itself defaults to
  `false`, so a SQL `CREATE INDEX` without `"addHierarchy"` builds a flat graph. Pass `None` to
  take the engine default. See
  [Graph build settings in SQL](../guide/vectors.md#graph-build-settings-in-sql).
- `pq_subspaces` (int | None): PQ subspaces (M). Requires `quantization="PRODUCT"`.
- `pq_clusters` (int | None): PQ clusters per subspace (K). Requires
  `quantization="PRODUCT"`. In current ArcadeDB engine builds, this should not exceed
  the number of indexed vectors available for PQ training in a bucket.
- `pq_center_globally` (bool | None): PQ global centering flag. Requires `quantization="PRODUCT"`.
- `pq_training_limit` (int | None): PQ training sample cap (the codebook is trained on a random
  sample of this size; the engine caps it at 128000). Requires `quantization="PRODUCT"`.
- `rerank_oversample` (int | None): Candidates per requested neighbour a PQ search scores again
  on the stored vectors (index setting `rerankOversample`; engine default 10; `0` returns the
  PQ scores alone; negative is refused). Requires `quantization="PRODUCT"`. A query overrides
  it with the `rerank` option of `vectorNeighbors`.
- `fused_pq` (bool | None): Store the PQ codes of every node's neighbours in the graph file
  (index setting `fusedPQ`; off by default; ignored unless `pq_clusters` is 256). Requires
  `quantization="PRODUCT"`. Both new settings need ArcadeDB 26.11.1 or later.
  Current engine builds ignore it ([ArcadeDB #10514](https://github.com/ArcadeData/arcadedb/issues/10514)).
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

### is_read_only

```python
db.is_read_only() -> bool
```

Return `True` if the database was opened with `read_only=True`.

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
factory.open(read_only: bool = False) -> Database
```

Open an existing database. With `read_only=True` the files open in `ComponentFile.MODE.READ_ONLY`, as for [`open_database`](#open_database).

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

## SQL for Constraints, Scans, and Maintenance

The bindings are query-first: what a SQL statement does, `db.command()` and `db.query()` run. Every statement below has a test in `tests/test_sql_constraints_and_maintenance.py` (`COMPACT INDEX` in `tests/test_sparse_quantization_compact.py`).

| Task | Statement |
| --- | --- |
| Property constraints | `CREATE PROPERTY T.p INTEGER (mandatory true, notnull true, readonly true, min 0, max 100, regexp '[A-Z]+', default 5)` |
| Change a constraint | `ALTER PROPERTY T.p MAX 200` (refused while a stored record violates it) |
| Scan a type with its subtypes | `SELECT FROM T` |
| Isolation level | `BEGIN ISOLATION REPEATABLE_READ`, see [Transactions](transactions.md#isolation-level) |
| Backup | `BACKUP DATABASE 'name.zip'` |
| Integrity check | `CHECK DATABASE` (`CHECK DATABASE FIX` repairs) |
| Rebuild an index | `REBUILD INDEX \`Type[prop]\`` or `REBUILD INDEX *` |
| Compact an index | `COMPACT INDEX \`Type[prop]\`` or `COMPACT INDEX *` |

```python
db.command("sql", "CREATE DOCUMENT TYPE Item")
db.command("sql", "CREATE PROPERTY Item.qty INTEGER (mandatory true, notnull true, min 0, max 100)")
db.command("sql", "CREATE PROPERTY Item.code STRING (regexp '[A-Z]+', default 'AB')")

with db.transaction():
    db.command("sql", "INSERT INTO Item SET qty = 500")  # ArcadeDBError: ValidationException
```

A constraint refuses the write with an `ArcadeDBError` whose message names the `ValidationException`. Schema statements apply at once, not in the transaction.

`SELECT FROM Animal` returns the records of `Animal` and of every type that extends it, one row at a time through the `ResultSet`. `AsyncExecutor.scan_type(type_name, callback, polymorphic=True)` is the callback form, with `polymorphic=False` for one type only.

Each admin statement returns one row that `first().to_dict()` turns into a dict:

```python
report = db.command("sql", "CHECK DATABASE").first().to_dict()
assert report.get("totalErrors", 0) == 0  # the key is absent when there is no error

db.command("sql", "REBUILD INDEX *").first().to_dict()   # {'operation': 'rebuild index', 'indexes': [...], 'totalIndexed': 20, ...}
db.command("sql", "COMPACT INDEX *").first().to_dict()   # {'operation': 'compact index', 'indexes': [...], 'compacted': True}
```

`REBUILD INDEX` replaces the index files, so the file-level names in `indexes` change; address one index by its schema name, `` `Type[prop]` ``.

`BACKUP DATABASE 'name.zip'` takes a file name, not a path. The archive goes to `<arcadedb.server.backupDirectory>/<database name>/name.zip`, so set the directory when the JVM starts, and unzip the archive into an empty directory to open it:

```python
db = arcadedb.open_database(path, jvm_kwargs={"jvm_args": "-Darcadedb.server.backupDirectory=/data/backups"})
db.command("sql", "BACKUP DATABASE 'nightly.zip'")  # /data/backups/<database name>/nightly.zip
```

`CHECK DATABASE` rolls back an open transaction first, so run it outside one. A read-only database refuses `db.command()` for `CREATE ...` and for `CHECK DATABASE` with an `ArcadeDBError`; read it with `db.query()`.

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
