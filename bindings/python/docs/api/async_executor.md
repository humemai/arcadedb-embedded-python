# AsyncExecutor API

The AsyncExecutor provides low-level async operations for parallel processing, automatic batching, and optimized WAL operations. It offers 3-5x faster bulk inserts compared to sequential operations.

!!! tip "Using Context Managers"
    For automatic resource cleanup, prefer using context managers:
    ```python
    with arcadedb.create_database("./mydb") as db:
        async_exec = db.async_executor()
        async_exec.set_parallel_level(8)
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
- **High Performance**: 50,000-200,000 records/sec throughput
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

# Use for bulk operations
for i in range(100000):
    vertex = db.new_vertex("User")
    vertex.set("userId", i)
    async_exec.create_record(vertex)

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
- **Default**: 4

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
async_exec.set_transaction_use_wal(enabled: bool) -> AsyncExecutor
```

Enable or disable Write-Ahead Log for transactions.

**Parameters:**

- `enabled` (bool): True to enable WAL (durability), False for speed

**Returns:**

- `AsyncExecutor`: Self for chaining

**Note:** Disabling WAL increases speed but reduces durability.

**Example:**

```python
# Disable WAL for maximum speed (less durable)
async_exec = db.async_executor().set_transaction_use_wal(False)
```

---

### set_back_pressure

```python
async_exec.set_back_pressure(threshold: int) -> AsyncExecutor
```

Set queue back-pressure threshold (0-100).

**Parameters:**

- `threshold` (int): Percentage (0=disabled, 100=always)

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

## Operation Methods

### create_record

```python
async_exec.create_record(
    record,
    callback: Optional[Callable] = None
)
```

Schedule asynchronous record creation.

**Parameters:**

- `record`: Document, Vertex, or Edge object to create
- `callback` (Optional[Callable]): Success callback

**Example:**

```python
async_exec = db.async_executor()

for i in range(10000):
    vertex = db.new_vertex("User")
    vertex.set("userId", i)
    vertex.set("name", f"User {i}")
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

### update_record

```python
async_exec.update_record(
    record,
    callback: Optional[Callable] = None
)
```

Schedule asynchronous record update.

**Parameters:**

- `record`: Document, Vertex, or Edge object to update
- `callback` (Optional[Callable]): Success callback

**Example:**

```python
# Query records
results = list(db.query("sql", "SELECT FROM User WHERE active = false"))

async_exec = db.async_executor()

for result in results:
    element = result.get_element()
    mutable = element.modify()
    mutable.set("active", True)
    async_exec.update_record(mutable)

async_exec.wait_completion()
async_exec.close()
```

---

### delete_record

```python
async_exec.delete_record(
    record,
    callback: Optional[Callable] = None
)
```

Schedule asynchronous record deletion.

**Parameters:**

- `record`: Document, Vertex, or Edge object to delete
- `callback` (Optional[Callable]): Success callback

**Example:**

```python
# Delete old records
to_delete = list(db.query("sql", "SELECT FROM LogEntry WHERE timestamp < ?",
                          cutoff_date))

async_exec = db.async_executor()

for result in to_delete:
    element = result.get_element()
    async_exec.delete_record(element)

async_exec.wait_completion()
async_exec.close()
```

---

### query

```python
async_exec.query(
    language: str,
    query: str,
    callback: Callable,
    **params
)
```

Execute async query.

**Parameters:**

- `language` (str): Query language ("sql", "cypher", etc.)
- `query` (str): Query string
- `callback` (Callable): Callback for query results
- `**params`: Query parameters

**Example:**

```python
def process_results(resultset):
    for result in resultset:
        print(result.get("name"))

async_exec = db.async_executor()
async_exec.query("sql", "SELECT FROM User WHERE age > 18", process_results)
async_exec.wait_completion()
async_exec.close()
```

---

### command

```python
async_exec.command(
    language: str,
    command: str,
    callback: Callable,
    **params
)
```

Execute async command.

**Parameters:**

- `language` (str): Command language ("sql", etc.)
- `command` (str): Command string
- `callback` (Callable): Callback for command results
- `**params`: Command parameters

## Status Methods

### wait_completion

```python
async_exec.wait_completion(timeout: Optional[float] = None)
```

Wait for all pending operations to complete.

**Parameters:**

- `timeout` (Optional[float]): Max wait time in seconds (None = forever)

**Note:** Always call before closing executor or database.

**Example:**

```python
async_exec = db.async_executor()

# Queue operations
for i in range(10000):
    vertex = db.new_vertex("User")
    vertex.set("userId", i)
    async_exec.create_record(vertex)

# Wait for all to complete
async_exec.wait_completion()

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

## Complete Example

```python
import arcadedb_embedded as arcadedb
import time

# Create database
db = arcadedb.create_database("./async_demo")

# Create schema
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE Product")

# Prepare async executor
async_exec = (db.async_executor()
    .set_parallel_level(8)
    .set_commit_every(10000)
    .set_back_pressure(75)
)

# Measure performance
start = time.time()

# Create 100K vertices asynchronously
for i in range(100000):
    vertex = db.new_vertex("Product")
    vertex.set("productId", i)
    vertex.set("name", f"Product {i}")
    vertex.set("price", i * 10.5)
    async_exec.create_record(vertex)

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
    vertex = db.new_vertex("User")
    vertex.set("userId", i)
    async_exec.create_record(vertex)
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

## Comparison with BatchContext

| Feature | AsyncExecutor | BatchContext |
|---------|---------------|-------------|
| **Control** | ✅ Full control | ⚠️ High-level API |
| **Complexity** | ⚠️ More complex | ✅ Simple |
| **Progress Bar** | ❌ Manual | ✅ Built-in |
| **Error Handling** | ⚠️ Callbacks | ✅ Automatic collection |
| **Use Case** | Advanced tuning | Most bulk ops |

**When to use AsyncExecutor:**
- Need fine-grained control
- Custom callbacks required
- Performance tuning critical

**When to use BatchContext:**
- Standard bulk operations
- Want progress tracking
- Prefer simple API

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

- **[BatchContext API](batch.md)** - High-level batch processing
- **[Transactions API](transactions.md)** - Transaction management
- **[Database API](database.md)** - Database operations
- **[Example 05: CSV Import](../examples/05_csv_import_graph.md)** - Real-world usage
- **[Testing Overview](../development/testing/overview.md)** - Testing patterns
