# AsyncExecutor API

!!! note "Recommended usage"
    For application code, prefer async SQL/OpenCypher via `async_exec.command(...)`
    and `async_exec.query(...)`. Record-level helpers remain available for lower-level
    workflows and tests.

!!! warning "Bulk ingest guidance"
    For bulk table/document ingest in this repository, keep async SQL on a single
    worker unless you have workload-specific evidence to do otherwise. Multi-threaded
    async insert has not been safe or reliable in the current Python benchmarks.

The AsyncExecutor provides low-level async operations for parallel processing,
automatic batching, and optimized WAL operations.

!!! tip "Using Context Managers"
    For automatic resource cleanup, prefer using context managers:

    ```python
    with arcadedb.create_database("./mydb") as db:
        async_exec = db.async_executor()
        async_exec.set_parallel_level(1)
        # Use for bulk operations...
        async_exec.wait_completion()
    # Database automatically closed
    ```
    Examples below show explicit `db.close()` for clarity, but context managers are recommended in production.

## Overview

The `AsyncExecutor` class enables:

- **Parallel Execution**: 1-16 worker threads for concurrent operations
- **Automatic Batching**: Auto-commit every N operations
- **Optimized WAL**: Configurable Write-Ahead Log settings
- **High Performance**: for measured bulk throughput paths, see `Database.insert_many` (documents) and [`append_samples`](#append_samples) (time series)
- **Fluent Interface**: Method chaining for configuration

## Getting AsyncExecutor

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")

# Get async executor
async_exec = db.async_executor()

# Configure (all methods return self for chaining)
async_exec.set_parallel_level(8)       # 8 worker threads
async_exec.set_commit_every(5000)      # Auto-commit every 5K ops
async_exec.set_back_pressure(75)       # Queue back-pressure at 75%

# Use for bulk SQL operations
for i in range(100000):
    async_exec.command(
        "sql",
        "INSERT INTO User SET userId = :id, name = :name",
        callback=lambda rs: None,
        id=i,
        name=f"User {i}",
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

- **CPU-bound**: Match CPU cores (4-8)
- **I/O-bound**: Can exceed cores (8-16)
- **Default**: Number of CPU cores
- Raises `ValueError` if `level` is not between 1 and 16

**Example:**

```python
# Configure for 8-core CPU
async_exec = db.async_executor().set_parallel_level(8)
```

---

### set_commit_every

```python
async_exec.set_commit_every(count: int) -> AsyncExecutor
```

Set auto-commit batch size. Commits transaction every N operations.

**Parameters:**

- `count` (int): Number of operations before commit (0 = no auto-commit)

**Returns:**

- `AsyncExecutor`: Self for chaining

**Guidelines:**

- **Small datasets** (< 10K): 1000-2000
- **Medium datasets** (10K-100K): 5000
- **Large datasets** (> 100K): 10000-20000

**Example:**

```python
# Auto-commit every 10K operations
async_exec = db.async_executor().set_commit_every(10000)
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
    .set_parallel_level(8)
    .set_commit_every(10000)
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
SQL. For bulk ingest of many uniform documents, prefer
`Database.insert_many(..., parallel=True)`.

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

**Example:**

```python
async_exec = db.async_executor()

# Async inserts via SQL (see also create_record and db.insert_many for bulk)
for i in range(10000):
    async_exec.command(
        "sql",
        "INSERT INTO User SET userId = :id, name = :name",
        id=i,
        name=f"User {i}",
    )

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
ex.append_samples(type_name: str, timestamps, *column_values)
```

Columnar bulk append into a native `TIMESERIES` type: one call per batch,
columns ordered as tags then fields per the type declaration. Timestamps
are epoch values in the type's precision (ms by default).

numpy fast path: an `ndarray` for timestamps or for a numeric field column
crosses the FFI as a single buffer copy (with Java-side boxing), instead of
per-element conversion. Lists work too, converted per element.

**Example:**

```python
ts = base_ms + np.arange(n, dtype=np.int64) * 1000
ex = db.async_executor()
ex.append_samples("Sensor", ts, hosts, cpu_ndarray, mem_ndarray)
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
async_exec = db.async_executor()

# Queue operations via SQL
for i in range(10000):
    async_exec.command("sql", "INSERT INTO User SET userId = :id", id=i)

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

Check whether the executor is currently processing queued operations. Similar to
`is_pending()`, but also falls back to a zero-timeout `waitCompletion(0)` probe when
the engine's `isProcessing()` call is unavailable.

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
import time

# Create database
db = arcadedb.create_database("./async_demo")

# Create schema (ArcadeDB SQL DDL)
db.command("sql", "CREATE VERTEX TYPE Product")
db.command("sql", "CREATE PROPERTY Product.productId LONG")
db.command("sql", "CREATE PROPERTY Product.name STRING")
db.command("sql", "CREATE PROPERTY Product.price DECIMAL")
db.command("sql", "CREATE INDEX ON Product (productId) UNIQUE")

# Prepare async executor
async_exec = (db.async_executor()
    .set_parallel_level(8)
    .set_commit_every(10000)
    .set_back_pressure(75)
)

# Measure performance
start = time.time()

# Create 100K vertices asynchronously via SQL
for i in range(100000):
    async_exec.command(
        "sql",
        "INSERT INTO Product SET productId = :id, name = :name, price = :price",
        id=i,
        name=f"Product {i}",
        price=i * 10.5,
    )

# Wait for completion
async_exec.wait_completion()

elapsed = time.time() - start
throughput = 100000 / elapsed

print(f"✅ Created 100,000 vertices")
print(f"⏱️  Time: {elapsed:.2f}s")
print(f"🚀 Throughput: {throughput:,.0f} records/sec")

# Clean up
async_exec.close()
db.close()
```

## Performance Comparison

```python
import time

# Synchronous (baseline)
start = time.time()
with db.transaction():
    for i in range(10000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
sync_time = time.time() - start

# Asynchronous
start = time.time()
async_exec = db.async_executor().set_parallel_level(8)
for i in range(10000):
    async_exec.command("sql", "INSERT INTO User SET userId = :id", id=i)
async_exec.wait_completion()
async_exec.close()
async_time = time.time() - start

print(f"Synchronous: {10000 / sync_time:,.0f} records/sec")
print(f"Asynchronous: {10000 / async_time:,.0f} records/sec")
print(f"Speedup: {sync_time / async_time:.1f}x")
```

**Typical Results:**
- Synchronous: 15,000-30,000 records/sec
- Asynchronous: 50,000-200,000 records/sec
- **Speedup: 3-5x**

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

### 3. Use Appropriate Batch Size

```python
# ✅ Good: Tune for dataset size
if record_count < 10000:
    async_exec.set_commit_every(2000)
elif record_count < 100000:
    async_exec.set_commit_every(5000)
else:
    async_exec.set_commit_every(20000)
```

### 4. Match Parallelism to Hardware

```python
import os

# ✅ Good: Match CPU cores
cpu_count = os.cpu_count() or 4
async_exec.set_parallel_level(min(cpu_count, 16))
```

## Troubleshooting

### Out of Memory Errors

```python
# Reduce back-pressure threshold
async_exec.set_back_pressure(50)  # Slow down enqueue

# Or reduce parallel level
async_exec.set_parallel_level(4)  # Fewer workers
```

### Slow Performance

```python
# Increase parallelism
async_exec.set_parallel_level(16)

# Increase batch size
async_exec.set_commit_every(20000)

# Consider disabling WAL (less durable!)
async_exec.set_transaction_use_wal(False)
```

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
