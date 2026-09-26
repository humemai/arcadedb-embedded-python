# AsyncExecutor API

!!! note "Recommended usage"
    For individual statements in application code, prefer async SQL/OpenCypher via
    `async_exec.command(...)` and `async_exec.query(...)`. Record-level helpers remain
    available for lower-level workflows and tests. For bulk ingest, see the warning
    below.

!!! warning "Async SQL commands silently lost records above parallel level 1 before 26.10.1"
    The async executor's SQL command path, `async_exec.command(...)`, discarded records
    once the parallel level was above 1, before 26.10.1 (`ArcadeData/arcadedb#7615`,
    fixed in #7625: a failed periodic commit is now retried and otherwise reported
    through the error callback). Observed on arcadedb-engine 26.9.1 and 26.6.1,
    measured 2026-09-15. How much was lost varied by run and by workload shape: 9,742
    single-record `INSERT` commands submitted at parallel level 4 stored 2,436, 5,742,
    and 7,742 rows across runs. Nothing was raised and nothing was logged: the
    per-command callback reported no error, and `wait_completion()` returned normally.
    Only the executor-wide `on_error` handler saw anything, one
    `ConcurrentModificationException` per rolled-back batch. At parallel level 1 no
    records were lost. Filed upstream as `ArcadeData/arcadedb#7615`.

    Treat `command()` as a way to run individual statements asynchronously, not as a
    bulk-write path, at any parallel level. For bulk graph loading use
    `db.graph_batch(...)`, and for bulk document loading use `db.insert_many(...)` or a
    plain batched transaction.

The AsyncExecutor provides low-level async operations for parallel processing,
automatic batching, and optimized WAL operations.

!!! tip "Using Context Managers"
    For automatic resource cleanup, prefer using context managers:

    ```python
    with arcadedb.create_database("./mydb") as db:
        async_exec = db.async_executor()
        async_exec.set_parallel_level(1)
        # Queue async statements, queries, or record operations...
        async_exec.wait_completion()
    # Database automatically closed
    ```
    Examples below show explicit `db.close()` for clarity, but context managers are recommended in production.

## Overview

The `AsyncExecutor` class enables:

- **Parallel Execution**: 1-16 worker threads for concurrent operations (a level above 1
  lost records submitted through `command()` before 26.10.1, see the warning above and
  #7615)
- **Automatic Batching**: Auto-commit every N operations
- **Optimized WAL**: Configurable Write-Ahead Log settings
- **High Performance**: for measured bulk throughput paths, see `Database.insert_many` (documents), `Database.graph_batch` (graphs), and [`append_samples`](#append_samples) (time series)
- **Fluent Interface**: Method chaining for configuration

## Getting AsyncExecutor

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")

# Get async executor
async_exec = db.async_executor()

# Configure (all methods return self for chaining)
async_exec.set_parallel_level(1)       # 1 worker thread; above 1 command() loses records
async_exec.set_commit_every(5000)      # Auto-commit every 5K ops
async_exec.set_back_pressure(75)       # Queue back-pressure at 75%

# Run a statement without blocking the calling thread
async_exec.command(
    "sql",
    "UPDATE User SET active = false WHERE lastLogin < :cutoff",
    callback=lambda rs: None,
    cutoff=cutoff_date,
)

# Wait for completion
async_exec.wait_completion()

# Clean up worker threads
async_exec.close()

db.close()
```

## Configuration Methods

All configuration methods return `self` for method chaining.

### set_parallel_level

```python
async_exec.set_parallel_level(level: int) -> AsyncExecutor
```

Set number of parallel worker threads (1-16).

**Parameters:**

- `level` (int): Number of worker threads

**Returns:**

- `AsyncExecutor`: Self for chaining

**Guidelines:**

- **Default**: Number of CPU cores
- Raises `ValueError` if `level` is not between 1 and 16
- Any level above 1 is what triggered the record loss described in the warning at the top
  of this page (#7615, fixed in #7625) for work submitted through `command()`. Keep the
  level at 1 when
  the executor runs SQL commands that write.
- `create_record`, `append_samples`, `Database.insert_many`, and `Database.graph_batch`
  are unaffected and can run above level 1.

**Example:**

```python
# Single worker: required for correctness of command() writes
async_exec = db.async_executor().set_parallel_level(1)
```

---

### set_commit_every

```python
async_exec.set_commit_every(count: int) -> AsyncExecutor
```

Set auto-commit batch size. Commits transaction every N operations.

**Parameters:**

- `count` (int): Number of operations before commit (must be at least 1;
  a smaller value raises `ValueError`)

**Returns:**

- `AsyncExecutor`: Self for chaining

**Guidelines:**

- Set a non-zero value whenever the executor writes, so queued operations are grouped
  into transactions instead of committing one at a time.
- A larger value lowers commit overhead and raises the amount of work a single
  rollback discards; a smaller value does the opposite.
- This is a commit cadence for queued async work. It does not make `command()` usable as
  a bulk-ingest path, see the warning at the top of this page.

**Example:**

```python
# Auto-commit every 5K operations
async_exec = db.async_executor().set_commit_every(5000)
```

---

### set_transaction_use_wal

```python
async_exec.set_transaction_use_wal(use_wal: bool) -> AsyncExecutor
```

Enable or disable Write-Ahead Log for transactions.

**Parameters:**

- `use_wal` (bool): True to enable WAL (durability), False for speed

**Returns:**

- `AsyncExecutor`: Self for chaining

**Note:** Disabling WAL increases speed but reduces durability.

**Example:**

```python
# Disable WAL for maximum speed (less durable)
async_exec = db.async_executor().set_transaction_use_wal(False)
```

---

### set_transaction_sync

```python
async_exec.set_transaction_sync(sync_mode: str) -> AsyncExecutor
```

Set the WAL flush strategy for the durability vs. performance trade-off.

**Parameters:**

- `sync_mode` (str): One of:
    - `"no"` - No fsync (fastest, least durable)
    - `"yes_nometadata"` - Sync data but not metadata
    - `"yes_full"` - Full fsync (slowest, most durable)

**Returns:**

- `AsyncExecutor`: Self for chaining

**Raises:**

- `ValueError`: If `sync_mode` is invalid

**Example:**

```python
# Use no-sync for maximum performance
async_exec = db.async_executor().set_transaction_sync("no")
```

---

### set_back_pressure

```python
async_exec.set_back_pressure(percentage: int) -> AsyncExecutor
```

Set queue back-pressure threshold (0-100).

**Parameters:**

- `percentage` (int): Percentage (0-100). Raises `ValueError` if outside 0-100

**Returns:**

- `AsyncExecutor`: Self for chaining

**How it works:**

- Queue fills up → Back-pressure kicks in
- Slows down enqueue operations
- Prevents memory overflow
- 0 = disabled, 50-75 = recommended

**Example:**

```python
# Set back-pressure at 75% full
async_exec = db.async_executor().set_back_pressure(75)
```

---

### Method Chaining

```python
# Chain all configurations
async_exec = (db.async_executor()
    .set_parallel_level(1)
    .set_commit_every(5000)
    .set_transaction_use_wal(True)
    .set_back_pressure(75)
)
```

---

### Configuration Getters

Each setter has a read-only counterpart that returns the current value:

| Method | Returns | Description |
|--------|---------|-------------|
| `get_parallel_level()` | `int` | Current number of worker threads |
| `get_commit_every()` | `int` | Current auto-commit batch size |
| `get_back_pressure()` | `int` | Current back-pressure threshold (0-100) |
| `is_transaction_use_wal()` | `bool` | Whether WAL is enabled for async transactions |
| `get_transaction_sync()` | `str` | Current WAL flush mode (`"no"`, `"yes_nometadata"`, or `"yes_full"`) |
| `get_thread_count()` | `int` | Number of executor threads actually spawned |

**Example:**

```python
async_exec = db.async_executor().set_parallel_level(8).set_commit_every(5000)
print(async_exec.get_parallel_level())   # 8
print(async_exec.get_commit_every())     # 5000
print(async_exec.is_transaction_use_wal())  # True
```

## Operation Methods

The async executor schedules SQL/OpenCypher work and a small set of record-level graph
and time-series operations. Record creation is available via
[`create_record`](#create_record); updates and deletes go through `command(...)` with
SQL. For bulk ingest, use `Database.insert_many(..., parallel=True)` for documents and
`Database.graph_batch(...)` for graphs; `command(...)` is not a bulk-write path (#7615,
see the warning at the top of this page).

### command

```python
async_exec.command(
    language: str,
    command_text: str,
    callback: Optional[Callable[[Any], None]] = None,
    args: Optional[Sequence[Any]] = None,
    error_callback: Optional[Callable[[Exception], None]] = None,
    **params,
)
```

Execute an async command (INSERT/UPDATE/DELETE/DDL). The callback is optional.

**Parameters:**

- `language` (str): Command language (`"sql"`, `"opencypher"`, etc.)
- `command_text` (str): Command string
- `callback` (Optional[Callable]): Optional callback invoked with each result row
- `args` (Optional[Sequence]): Positional parameters (use `?` placeholders)
- `error_callback` (Optional[Callable]): Optional per-operation error callback
- `**params`: Named parameters (use `:name` placeholders)

!!! note "args vs. params"
    Pass either positional `args` or named `**params`, not both. Mixing them raises
    `ValueError`.

!!! note "One statement at a time, not a bulk loader"
    Submitting a `command()` per row lost records above parallel level 1 before 26.10.1
    (#7615, fixed in #7625, see the warning at the top of this page). Load many rows with
    `db.insert_many(...)` or
    `db.graph_batch(...)` instead.

**Example:**

```python
async_exec = db.async_executor().set_parallel_level(1)

# Async DDL
async_exec.command("sql", "CREATE INDEX ON User (userId) UNIQUE")

# Async update
async_exec.command("sql", "UPDATE User SET active = true WHERE active = false")

# Async delete with positional args
async_exec.command(
    "sql",
    "DELETE FROM LogEntry WHERE timestamp < ?",
    args=[cutoff_date],
)

async_exec.wait_completion()
async_exec.close()
```

---

### query

```python
async_exec.query(
    language: str,
    query_text: str,
    callback: Callable[[Any], None],
    args: Optional[Sequence[Any]] = None,
    error_callback: Optional[Callable[[Exception], None]] = None,
    **params,
)
```

Execute an async query with a callback invoked for each result row.

**Parameters:**

- `language` (str): Query language (`"sql"`, `"opencypher"`, etc.)
- `query_text` (str): Query string
- `callback` (Callable): Callback receiving each result row
- `args` (Optional[Sequence]): Positional parameters
- `error_callback` (Optional[Callable]): Optional per-operation error callback
- `**params`: Named parameters

**Example:**

```python
def process_row(row):
    print(row.get("name"))

async_exec = db.async_executor()
async_exec.query("sql", "SELECT FROM User WHERE age > 18", process_row)
async_exec.wait_completion()
async_exec.close()
```

---

### append_samples

```python
ex.append_samples(type_name: str, timestamps, *column_values, primitive: bool = False)
```

Columnar bulk append into a native `TIMESERIES` type: one call per batch,
columns ordered as tags then fields per the type declaration. Timestamps
are epoch values in the type's precision (ms by default).

numpy fast path: an `ndarray` for timestamps or for a numeric field column
crosses the FFI as a single buffer copy (with Java-side boxing), instead of
per-element conversion. Lists work too, converted per element.

`primitive=True` routes the batch through the engine's `TimeSeriesBatch`,
which carries each column as a primitive array and so never boxes a numeric
sample (ArcadeDB issue #5474, where the boxed path allocated a dead `Double`
per value only to unbox it again). Each column still crosses the FFI exactly
once: the per-row loop runs Java-side, because filling the batch from Python
would cost one JNI call per value and lose far more than the boxing costs.
Measured 1.38x faster on a 300k-sample, three-field ingest. It needs an engine
that ships the batch API, so the default stays on the `Object[]` path.

**Example:**

```python
ts = base_ms + np.arange(n, dtype=np.int64) * 1000
ex = db.async_executor()
ex.append_samples("Sensor", ts, hosts, cpu_ndarray, mem_ndarray)
ex.wait_completion()

# same data, no per-sample boxing
ex.append_samples("Sensor", ts, hosts, cpu_ndarray, mem_ndarray, primitive=True)
ex.wait_completion()
```

---

### create_record

```python
ex.create_record(document, callback=None)
```

Queue a document (built with `db.new_document`, not yet saved) for
asynchronous creation by the engine's parallel bucket writers. Call
`wait_completion()` before relying on visibility. For many uniform rows
prefer `db.insert_many(..., parallel=True)`, which crosses the FFI boundary
once per batch instead of per document.

**Parameters:**

- `document` (Document): Unsaved document from `db.new_document`
- `callback` (callable, optional): Invoked with the created record

**Example:**

```python
ex = db.async_executor()
for i in range(100_000):
    doc = db.new_document("Event")
    doc.set("seq", i)
    ex.create_record(doc)
ex.wait_completion()
```

---

### new_edge

```python
async_exec.new_edge(
    source_vertex,
    edge_type: str,
    destination_vertex_or_rid,
    light: bool = False,
    callback: Optional[Callable[[Any, bool, bool], None]] = None,
    **properties,
)
```

Asynchronously create an edge between an existing source vertex and a destination
vertex (or RID string). The optional callback receives `(edge, created_source_vertex,
created_dest_vertex)`.

---

### new_edge_by_keys

```python
async_exec.new_edge_by_keys(
    source_vertex_type: str,
    source_key_names: Union[str, Sequence[str]],
    source_key_values: Union[Any, Sequence[Any]],
    destination_vertex_type: str,
    destination_key_names: Union[str, Sequence[str]],
    destination_key_values: Union[Any, Sequence[Any]],
    create_vertex_if_not_exist: bool,
    edge_type: str,
    bidirectional: bool,
    light: bool,
    callback: Optional[Callable[[Any, bool, bool], None]] = None,
    **properties,
)
```

Asynchronously create an edge by looking up both endpoint vertices via indexed keys
instead of RIDs. Key names/values may be a single string/value or parallel sequences
for composite keys (name and value sequences must have the same length, otherwise
`ValueError` is raised).

**Parameters:**

- `source_vertex_type` (str): Source vertex type name
- `source_key_names`: Indexed property name(s) identifying the source vertex
- `source_key_values`: Value(s) for the source key properties
- `destination_vertex_type` (str): Destination vertex type name
- `destination_key_names`: Indexed property name(s) identifying the destination vertex
- `destination_key_values`: Value(s) for the destination key properties
- `create_vertex_if_not_exist` (bool): Create missing endpoint vertices on the fly
- `edge_type` (str): Edge type name
- `bidirectional` (bool): Store back-pointers on the destination vertex
- `light` (bool): Create a property-less light edge
- `callback` (Optional[Callable]): Receives `(edge, created_source_vertex, created_dest_vertex)`
- `**properties`: Edge properties

**Example:**

```python
async_exec.new_edge_by_keys(
    "Person", "email", "alice@example.com",
    "Person", "email", "bob@example.com",
    False,          # don't create missing vertices
    "Knows",
    True,           # bidirectional
    False,          # regular (non-light) edge
    since=2024,
)
async_exec.wait_completion()
```

---

### transaction

```python
async_exec.transaction(
    tx_block: Callable[[], None],
    retries: Optional[int] = None,
    ok_callback: Optional[Callable[[], None]] = None,
    error_callback: Optional[Callable[[Exception], None]] = None,
    slot: Optional[int] = None,
)
```

Run `tx_block` inside an async transaction scope, optionally with automatic retries and
completion callbacks.

---

### scan_type

```python
async_exec.scan_type(
    type_name: str,
    callback: Callable[[Any], bool],
    polymorphic: bool = True,
    error_callback: Optional[Callable[[Any, Exception], bool]] = None,
)
```

Asynchronously scan all records of a type, invoking `callback` per record. Returning
`False` from the callback stops the scan.

## Global Callbacks

### on_ok

```python
async_exec.on_ok(callback: Callable[[], None]) -> AsyncExecutor
```

Set a global success callback for all operations.

**Note:** Global callbacks have JPype proxy compatibility issues. Prefer per-operation
callbacks on async SQL/Cypher commands:

```python
async_exec.command(
    "sql", "INSERT INTO Log SET id = :id", callback=on_success, id=1
)
```

**Parameters:**

- `callback` (Callable): Success callback, no arguments

**Returns:**

- `AsyncExecutor`: Self for chaining

---

### on_error

```python
async_exec.on_error(callback: Callable[[Exception], None]) -> AsyncExecutor
```

Set a global error callback for all operations. Called for every failed operation if no
per-operation error callback was provided.

**Parameters:**

- `callback` (Callable): Error callback, receives the exception

**Returns:**

- `AsyncExecutor`: Self for chaining

**Example:**

```python
async_exec.on_error(lambda e: print(f"Error: {e}"))
```

## Status Methods

### wait_completion

```python
async_exec.wait_completion(timeout_ms: Optional[int] = None)
```

Wait for all pending operations to complete.

**Parameters:**

- `timeout_ms` (Optional[int]): Max wait time in milliseconds (None = forever)

**Raises:**

- `TimeoutError`: If the timeout elapses before completion

**Note:** Always call before closing executor or database.

**Example:**

```python
async_exec = db.async_executor().set_parallel_level(1)

# Queue operations
async_exec.command("sql", "DELETE FROM LogEntry WHERE timestamp < :cutoff",
                   cutoff=cutoff_date)
async_exec.query("sql", "SELECT FROM User WHERE age > 18", process_row)

# Wait for all to complete (wait forever, or pass milliseconds)
async_exec.wait_completion()
async_exec.wait_completion(30000)  # wait at most 30 seconds

# Now safe to close
async_exec.close()
```

---

### is_pending

```python
async_exec.is_pending() -> bool
```

Check if operations are still pending.

A non-blocking poll, delegating to `is_processing()`. It does not call the engine's
`waitCompletion(0)`: a timeout of zero is clamped to an infinite wait rather than read
as "poll", so using it here would block until the queue drained.

**Returns:**

- `bool`: True if operations in progress

**Example:**

```python
while async_exec.is_pending():
    print("Still processing...")
    time.sleep(1)
```

---

### is_processing

```python
async_exec.is_processing() -> bool
```

Check whether the executor is currently processing queued operations. Reports the
engine's own `isProcessing()` state, and `False` if that call raises. `is_pending()`
is the same answer under another name.

**Returns:**

- `bool`: True if operations are still being processed

---

### is_closed

```python
async_exec.is_closed() -> bool
```

Return True once the executor has been closed.

**Returns:**

- `bool`: True if `close()` has been called

---

### close

```python
async_exec.close()
```

Shutdown worker threads and clean up resources.

**Note:** Always call after `wait_completion()`.

**Example:**

```python
try:
    async_exec = db.async_executor()
    # Operations
    async_exec.wait_completion()
finally:
    async_exec.close()
```

---

### kill

```python
async_exec.kill()
```

Forcibly stop the executor's worker threads without waiting for queued operations to
complete. Prefer `wait_completion()` followed by `close()` for orderly shutdown; use
`kill()` only to abort a runaway workload (queued but unprocessed operations are lost).

## Complete Example

```python
import arcadedb_embedded as arcadedb

# Create database
db = arcadedb.create_database("./async_demo")

# Create schema (ArcadeDB SQL DDL)
db.command("sql", "CREATE DOCUMENT TYPE Product")
db.command("sql", "CREATE PROPERTY Product.productId LONG")
db.command("sql", "CREATE PROPERTY Product.name STRING")
db.command("sql", "CREATE PROPERTY Product.price DECIMAL")
db.command("sql", "CREATE INDEX ON Product (productId) UNIQUE")

# Load the rows with insert_many, not with the async executor
inserted = db.insert_many(
    "Product",
    (
        {"productId": i, "name": f"Product {i}", "price": i * 10.5}
        for i in range(100000)
    ),
    commit_every=10000,
)
print(f"Inserted {inserted} products")

# Prepare async executor for statements and queries that should not block the caller
async_exec = (db.async_executor()
    .set_parallel_level(1)
    .set_commit_every(5000)
    .set_back_pressure(75)
)
async_exec.on_error(lambda e: print(f"Async error: {e}"))

# One async statement, not one statement per row
async_exec.command("sql", "UPDATE Product SET price = price * 1.1 WHERE price < 100")

# Async read with a per-row callback
cheap = []
async_exec.query(
    "sql",
    "SELECT FROM Product WHERE price < 50",
    lambda row: cheap.append(row.get("productId")),
)

async_exec.wait_completion()
print(f"{len(cheap)} products priced under 50")

# Clean up
async_exec.close()
db.close()
```

## Best Practices

### 0. Set a Commit Cadence

```python
async_exec = db.async_executor()
async_exec.set_commit_every(500)  # Ensures async writes are persisted transactionally
```

- Configure `set_commit_every()` for every async workload so writes are grouped into transactions.
- Tune the batch size to balance commit overhead and memory.

### 1. Always Close the Executor

```python
# ✅ Good: Use try/finally
async_exec = db.async_executor()
try:
    # Operations
    async_exec.wait_completion()
finally:
    async_exec.close()
```

### 2. Wait Before Closing

```python
# ✅ Good: Wait first
async_exec.wait_completion()
async_exec.close()

# ❌ Bad: Close without waiting
async_exec.close()  # Operations may be lost!
```

### 3. Keep `command()` Submissions on One Worker

```python
# ✅ Good: async SQL writes on a single worker (#7615)
async_exec.set_parallel_level(1)
async_exec.command("sql", "DELETE FROM LogEntry WHERE timestamp < :cutoff",
                   cutoff=cutoff_date)
```

### 4. Load Bulk Data Outside the Executor

```python
# ✅ Good: documents
db.insert_many("Event", rows)

# ✅ Good: graphs
with db.graph_batch(expected_edge_count=50000) as batch:
    ...

# ❌ Bad: one async SQL INSERT per row
for row in rows:
    async_exec.command("sql", "INSERT INTO Event SET seq = :seq", seq=row["seq"])
```

## Troubleshooting

### Out of Memory Errors

```python
# Reduce back-pressure threshold
async_exec.set_back_pressure(50)  # Slow down enqueue

# Or reduce parallel level
async_exec.set_parallel_level(1)  # Fewer workers
```

### Slow Performance

```python
# Increase batch size
async_exec.set_commit_every(20000)

# Consider disabling WAL (less durable!)
async_exec.set_transaction_use_wal(False)
```

Raising `set_parallel_level` is not the fix here: above 1 it lost records submitted
through `command()` before 26.10.1 (#7615, fixed in #7625). If the slow workload is a
bulk load, move it to
`db.insert_many(...)` or `db.graph_batch(...)`.

### Operations Not Completing

```python
# Always call wait_completion()
async_exec.wait_completion()

# Check for pending operations
if async_exec.is_pending():
    print("Still processing...")
```

## See Also

- **[Transactions API](transactions.md)** - Transaction management
- **[Database API](database.md)** - Database operations
- **[Example 05: CSV Import](../examples/05_csv_import_graph.md)** - Real-world usage
- **[Testing Overview](../development/testing/overview.md)** - Testing patterns
