# Batch Processing API

The Batch Processing API provides a high-level interface for bulk operations with automatic async executor configuration, progress tracking, and error handling.

## Overview

The `BatchContext` class simplifies bulk data operations by:

- **Automatic Configuration**: Sets up async executor with optimal defaults
- **Progress Tracking**: Optional progress bar with `tqdm` integration
- **Error Handling**: Collects errors without stopping execution
- **Context Manager**: Automatic cleanup and completion waiting
- **High Performance**: 50,000-200,000 records/sec throughput

## Class: BatchContext

High-level batch processing context manager.

### Constructor

```python
db.batch_context(
    batch_size: int = 5000,
    parallel: int = 4,
    use_wal: bool = True,
    back_pressure: int = 50,
    progress: bool = False,
    progress_desc: str = "Processing"
) -> BatchContext
```

**Parameters:**

- `batch_size` (int): Auto-commit every N operations (default: 5000)
- `parallel` (int): Number of parallel worker threads 1-16 (default: 4)
- `use_wal` (bool): Enable Write-Ahead Log for durability (default: True)
- `back_pressure` (int): Queue back-pressure threshold 0-100 (default: 50)
- `progress` (bool): Enable progress tracking with tqdm (default: False)
- `progress_desc` (str): Description for progress bar (default: "Processing")

**Returns:**

- `BatchContext`: Context manager for batch operations

## Basic Usage

### Simple Batch Processing

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb", create_if_not_exists=True)

# Create schema
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE User")

# Batch create vertices
with db.batch_context(batch_size=10000, parallel=8) as batch:
    for i in range(100000):
        batch.create_vertex("User", userId=i, name=f"User {i}")

# All operations complete automatically on context exit
db.close()
```

### With Progress Tracking

```python
# Enable progress bar (requires tqdm package)
with db.batch_context(batch_size=5000, progress=True) as batch:
    # Set total for accurate progress
    batch.set_total(len(dataset))

    for record in dataset:
        batch.create_vertex("User", **record)

# Progress bar closes automatically
```

### With Error Handling

```python
with db.batch_context(batch_size=5000) as batch:
    for record in dataset:
        batch.create_document("LogEntry", **record)

# Check for errors after completion
if batch.get_errors():
    print(f"Encountered {len(batch.get_errors())} errors")
    for error in batch.get_errors():
        print(f"Error: {error}")
else:
    print(f"Successfully processed {batch.get_success_count()} records")
```

## Methods

### create_vertex

```python
batch.create_vertex(
    type_name: str,
    callback: Optional[Callable] = None,
    **properties
)
```

Create a vertex asynchronously.

**Parameters:**

- `type_name` (str): Vertex type name
- `callback` (Optional[Callable]): Success callback
- `**properties`: Vertex properties as keyword arguments

**Example:**

```python
with db.batch_context() as batch:
    batch.create_vertex("Person", name="Alice", age=30)
    batch.create_vertex("Person", name="Bob", age=25)
```

---

### create_document

```python
batch.create_document(
    type_name: str,
    callback: Optional[Callable] = None,
    **properties
)
```

Create a document asynchronously.

**Parameters:**

- `type_name` (str): Document type name
- `callback` (Optional[Callable]): Success callback
- `**properties`: Document properties as keyword arguments

**Example:**

```python
with db.batch_context() as batch:
    for i in range(10000):
        batch.create_document(
            "LogEntry",
            timestamp=datetime.now(),
            level="INFO",
            message=f"Log {i}"
        )
```

---

### create_edge

```python
batch.create_edge(
    from_vertex,
    to_vertex,
    edge_type: str,
    callback: Optional[Callable] = None,
    **properties
)
```

Create an edge synchronously (edges persist immediately).

**Parameters:**

- `from_vertex`: Source vertex (Java vertex object)
- `to_vertex`: Destination vertex (Java vertex object)
- `edge_type` (str): Edge type name
- `callback` (Optional[Callable]): Success callback
- `**properties`: Edge properties as keyword arguments

**Example:**

```python
with db.batch_context() as batch:
    # First create vertices (async)
    alice = db.new_vertex("Person")
    alice.set("name", "Alice")
    alice.save()

    bob = db.new_vertex("Person")
    bob.set("name", "Bob")
    bob.save()

    # Then create edge (sync - persists immediately)
    batch.create_edge(alice, bob, "KNOWS", since=2020)
```

!!! note "Edge Creation is Synchronous"
    Unlike vertex/document creation, edge creation with `newEdge()` is synchronous and immediately persists the edge. The callback is called immediately after creation.

---

### delete_record

```python
batch.delete_record(
    record,
    callback: Optional[Callable] = None
)
```

Delete a record asynchronously.

**Parameters:**

- `record`: Java record object to delete
- `callback` (Optional[Callable]): Success callback

**Example:**

```python
# Query records to delete
to_delete = list(db.query("sql", "SELECT FROM User WHERE inactive = true"))

with db.batch_context() as batch:
    for result in to_delete:
        java_record = result._java_result.getElement().get()
        batch.delete_record(java_record)
```

---

### set_total

```python
batch.set_total(total: int)
```

Set total number of operations for progress tracking.

**Parameters:**

- `total` (int): Total number of operations

**Example:**

```python
with db.batch_context(progress=True) as batch:
    batch.set_total(len(dataset))
    for item in dataset:
        batch.create_vertex("Item", **item)
```

---

### wait_completion

```python
batch.wait_completion(timeout: Optional[float] = None)
```

Manually wait for all operations to complete.

**Parameters:**

- `timeout` (Optional[float]): Max wait time in seconds (None = wait forever)

**Note:** Usually not needed as context manager waits automatically on exit.

---

### is_pending

```python
batch.is_pending() -> bool
```

Check if there are pending operations.

**Returns:**

- `bool`: True if operations are still pending

**Example:**

```python
with db.batch_context() as batch:
    for i in range(1000):
        batch.create_vertex("Task", taskId=i)

    if batch.is_pending():
        print("Operations still in progress...")
```

---

### get_errors

```python
batch.get_errors() -> List[Exception]
```

Get list of errors collected during batch processing.

**Returns:**

- `List[Exception]`: List of exceptions that occurred

---

### get_success_count

```python
batch.get_success_count() -> int
```

Get count of successful operations.

**Returns:**

- `int`: Number of successful operations

## Performance Optimization

### Tuning Parameters

```python
# For maximum throughput
with db.batch_context(
    batch_size=10000,    # Larger batches = fewer commits
    parallel=16,         # More workers (match CPU cores)
    back_pressure=75     # Higher back-pressure tolerance
) as batch:
    # Your bulk operations
    pass
```

### Choosing Batch Size

| Records | Recommended batch_size |
|---------|----------------------|
| < 10K   | 1000-2000 |
| 10K-100K | 5000 |
| 100K-1M | 10000-20000 |
| > 1M    | 20000+ |

### Choosing Parallel Level

- **CPU-bound**: Set to number of CPU cores (4-16)
- **I/O-bound**: Can exceed CPU cores (8-32)
- **Default**: 4 (good for most cases)

## Complete Example

```python
import arcadedb_embedded as arcadedb
import time

db = arcadedb.create_database("./bulk_db", create_if_not_exists=True)

# Create schema
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE Product")
    db.command("sql", "CREATE INDEX ON Product(productId) UNIQUE")

# Generate sample data
products = [
    {"productId": i, "name": f"Product {i}", "price": i * 10.5}
    for i in range(100000)
]

start = time.time()

# Batch import with progress
with db.batch_context(
    batch_size=10000,
    parallel=8,
    progress=True,
    progress_desc="Importing products"
) as batch:
    batch.set_total(len(products))

    for product in products:
        batch.create_vertex("Product", **product)

elapsed = time.time() - start
throughput = len(products) / elapsed

print(f"\n✅ Imported {len(products):,} products")
print(f"⏱️  Time: {elapsed:.2f}s")
print(f"🚀 Throughput: {throughput:,.0f} records/sec")

# Verify
count = db.count_type("Product")
print(f"✓ Verified: {count:,} products in database")

db.close()
```

## Comparison with AsyncExecutor

| Feature | BatchContext | AsyncExecutor |
|---------|-------------|---------------|
| **Ease of Use** | ✅ Simple API | ⚠️ More complex |
| **Progress Bar** | ✅ Built-in | ❌ Manual |
| **Error Collection** | ✅ Automatic | ⚠️ Manual callbacks |
| **Auto-Cleanup** | ✅ Context manager | ⚠️ Manual close |
| **Fine Control** | ⚠️ Limited | ✅ Full control |
| **Use Case** | Most bulk operations | Advanced tuning |

## Best Practices

### 1. Create Schema First

```python
# ✅ Good: Schema defined before batch
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE User")
    db.command("sql", "CREATE INDEX ON User(userId) UNIQUE")

with db.batch_context() as batch:
    # Batch operations
    pass
```

### 2. Use Context Manager

```python
# ✅ Good: Automatic cleanup
with db.batch_context() as batch:
    # Operations
    pass

# ❌ Bad: Manual management
batch = db.batch_context()
batch.__enter__()
# Operations
batch.__exit__(None, None, None)  # Easy to forget!
```

### 3. Check for Errors

```python
with db.batch_context() as batch:
    for record in dataset:
        batch.create_vertex("User", **record)

# ✅ Always check for errors
if batch.get_errors():
    print(f"Failed: {len(batch.get_errors())} errors")
    # Handle errors
```

### 4. Enable Progress for Long Operations

```python
# ✅ Good: User feedback for long operations
with db.batch_context(progress=True) as batch:
    batch.set_total(len(large_dataset))
    for item in large_dataset:
        batch.create_vertex("Item", **item)
```

## See Also

- **[AsyncExecutor API](async_executor.md)** - Lower-level async operations
- **[Transactions API](transactions.md)** - Transaction management
- **[Database API](database.md)** - Database operations
- **[Importer API](importer.md)** - CSV/XML import utilities
- **[Example 04: CSV Import](../examples/04_csv_import_documents.md)** - Batch import example
- **[Example 05: Graph Import](../examples/05_csv_import_graph.md)** - Graph bulk loading
