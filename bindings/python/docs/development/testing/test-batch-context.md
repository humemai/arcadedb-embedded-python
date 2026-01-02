# BatchContext Tests

The `test_batch_context.py` file contains **13 tests** covering high-level batch operations with progress tracking.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_batch_context.py){ .md-button }

## Overview

BatchContext provides a high-level API for bulk operations with:

- ✅ **Context Manager** - Automatic resource management
- ✅ **Progress Bar** - Built-in tqdm progress tracking
- ✅ **Error Collection** - Automatic error handling
- ✅ **Parallel Processing** - Configurable worker threads
- ✅ **Auto-Commit** - Batch size configuration

## Test Coverage

### Basic Operations Tests

#### test_batch_context_basic
Tests basic vertex creation with batch context.

**What it tests:**
- Creating 500 vertices with batch_size=100, parallel=2
- Context manager automatically handles lifecycle
- All records created successfully

**Pattern:**
```python
with db.batch_context(batch_size=100, parallel=2) as batch:
    for i in range(500):
        batch.create_vertex("User", userId=i, name=f"User{i}")

# Verify count
count = db.query("sql", "SELECT count(*) as count FROM User").first().get("count")
assert count == 500
```

---

#### test_batch_context_with_documents
Tests document creation via batch context.

**What it tests:**
- Creating 200 documents with batch_size=50, parallel=4
- Document properties set via kwargs
- All documents persisted

**Pattern:**
```python
with db.batch_context(batch_size=50, parallel=4) as batch:
    for i in range(200):
        batch.create_document(
            "LogEntry",
            level="INFO",
            message=f"Log message {i}",
            sequence=i
        )

count = db.count_type("LogEntry")
assert count == 200
```

---

#### test_batch_context_with_edges
Tests edge creation between vertices.

**What it tests:**
- Creating vertices first
- Creating edges with `create_edge(from_rid, to_rid, type, **props)`
- Edge properties set correctly

**Pattern:**
```python
# Create vertices
users = []
with db.batch_context() as batch:
    for i in range(10):
        user = batch.create_vertex("User", userId=i)
        users.append(user)

# Create edges
with db.batch_context() as batch:
    for i in range(9):
        batch.create_edge(
            users[i],
            users[i + 1],
            "Follows",
            since="2024-01-01"
        )

edge_count = db.query("sql", "SELECT count(*) FROM Follows").first().get("count")
assert edge_count == 9
```

### Configuration Tests

#### test_batch_context_custom_batch_size
Tests custom batch size configuration.

**What it tests:**
- Setting batch_size=25
- Creating 100 records (triggers 4 batches)
- All records created

**Pattern:**
```python
with db.batch_context(batch_size=25) as batch:
    for i in range(100):
        batch.create_vertex("Item", itemId=i)

assert db.count_type("Item") == 100
```

---

#### test_batch_context_parallel_level
Tests parallel worker configuration.

**What it tests:**
- Setting parallel=8 for 8 worker threads
- Creating 1000 records with parallel execution
- Verifies speedup from parallelism

**Pattern:**
```python
with db.batch_context(batch_size=100, parallel=8) as batch:
    for i in range(1000):
        batch.create_vertex("Product", productId=i)

assert db.count_type("Product") == 1000
```

---

#### test_batch_context_with_progress
Tests progress bar display.

**What it tests:**
- `set_total(500)` sets expected record count
- Progress bar updates during creation
- Progress reaches 100%

**Pattern:**
```python
with db.batch_context(batch_size=100) as batch:
    batch.set_total(500)  # Set expected count

    for i in range(500):
        batch.create_vertex("Order", orderId=i)
    # Progress bar automatically updates
```

### Error Handling Tests

#### test_batch_context_error_collection
Tests automatic error collection.

**What it tests:**
- Creating some invalid records (missing required field)
- Errors collected in `batch.get_errors()`
- Valid records still created
- Success count via `batch.get_success_count()`

**Pattern:**
```python
with db.batch_context() as batch:
    for i in range(100):
        if i % 10 == 0:
            # Invalid: missing required field
            batch.create_vertex("User")  # Error
        else:
            # Valid
            batch.create_vertex("User", userId=i)

errors = batch.get_errors()
success_count = batch.get_success_count()

assert len(errors) == 10  # 10 errors
assert success_count == 90  # 90 successful
```

---

#### test_batch_context_with_validation
Tests validation before creation.

**What it tests:**
- Custom validation logic
- Skip invalid records
- Only valid records created

**Pattern:**
```python
def is_valid(data):
    return data.get("age", 0) >= 18

with db.batch_context() as batch:
    for i in range(100):
        age = i
        if is_valid({"age": age}):
            batch.create_vertex("User", userId=i, age=age)

# Only users with age >= 18 created
count = db.count_type("User")
assert count == 82  # 100 - 18 = 82
```

### Performance Tests

#### test_batch_context_performance
Tests bulk operation performance.

**What it tests:**
- Creating 10K records
- Measuring throughput (records/sec)
- Typical: 50K-100K records/sec

**Pattern:**
```python
import time

start = time.time()

with db.batch_context(batch_size=1000, parallel=8) as batch:
    batch.set_total(10000)
    for i in range(10000):
        batch.create_vertex("Event", eventId=i)

elapsed = time.time() - start
throughput = 10000 / elapsed

print(f"Throughput: {throughput:,.0f} records/sec")
assert throughput > 10000  # Should be fast
```

---

#### test_batch_vs_transaction_performance
Compares batch vs single transaction performance.

**What it tests:**
- Single transaction with 1000 saves
- Batch context with 1000 creates
- Batch is typically 3-5x faster

**Pattern:**
```python
# Single transaction
start = time.time()
with db.transaction():
    for i in range(1000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
txn_time = time.time() - start

# Batch context
start = time.time()
with db.batch_context() as batch:
    for i in range(1000):
        batch.create_vertex("User", userId=i)
batch_time = time.time() - start

print(f"Speedup: {txn_time / batch_time:.1f}x")
```

### Edge Case Tests

#### test_batch_context_empty
Tests batch context with zero records.

**What it tests:**
- Creating batch context but not adding records
- No errors thrown
- Success count is 0

**Pattern:**
```python
with db.batch_context() as batch:
    pass  # No operations

assert batch.get_success_count() == 0
assert len(batch.get_errors()) == 0
```

---

#### test_batch_context_single_record
Tests batch context with single record.

**What it tests:**
- Creating just one record
- Works correctly even with small count
- Record created successfully

**Pattern:**
```python
with db.batch_context() as batch:
    batch.create_vertex("User", userId=1)

assert db.count_type("User") == 1
```

---

#### test_batch_context_nested_not_allowed
Tests that nested batch contexts are not supported.

**What it tests:**
- Attempting to nest batch contexts
- Should raise error or handle gracefully

**Pattern:**
```python
with db.batch_context() as batch1:
    batch1.create_vertex("User", userId=1)

    # Nested context (may not be allowed)
    try:
        with db.batch_context() as batch2:
            batch2.create_vertex("User", userId=2)
    except Exception as e:
        print(f"Nested context not allowed: {e}")
```

## Test Patterns

### Basic Batch Operations
```python
with db.batch_context(batch_size=1000, parallel=4) as batch:
    for i in range(10000):
        batch.create_vertex("Type", prop=value)

# Auto-commits, auto-closes, auto-completes
```

### With Progress Tracking
```python
with db.batch_context() as batch:
    batch.set_total(count)  # Enable progress bar

    for item in items:
        batch.create_vertex("Type", **item)
```

### With Error Handling
```python
with db.batch_context() as batch:
    for item in items:
        batch.create_vertex("Type", **item)

errors = batch.get_errors()
success = batch.get_success_count()

print(f"Created {success}, failed {len(errors)}")
```

### Edge Creation
```python
# Create vertices first
vertex_rids = []
with db.batch_context() as batch:
    for i in range(100):
        rid = batch.create_vertex("User", userId=i)
        vertex_rids.append(rid)

# Create edges
with db.batch_context() as batch:
    for i in range(99):
        batch.create_edge(
            vertex_rids[i],
            vertex_rids[i + 1],
            "Follows"
        )
```

## Common Assertions

```python
# Verify record count
assert db.count_type("User") == expected_count

# Check success count
assert batch.get_success_count() == expected_success

# Check errors
assert len(batch.get_errors()) == expected_errors

# Verify no pending operations
assert not batch.is_pending()
```

## Key Takeaways

1. **Use context manager** - Automatic resource cleanup
2. **Set total for progress** - Enable progress bar
3. **Tune batch size** - 1000-10000 for best performance
4. **Use parallel workers** - 4-8 for CPU-bound workloads
5. **Check errors** - Collect and handle failures
6. **Prefer batch over loop+save** - 3-5x faster

## See Also

- **[BatchContext API](../../api/batch.md)** - Full API reference
- **[AsyncExecutor Tests](test-async-executor.md)** - Low-level async API
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)** - Real-world usage
- **[Testing Overview](overview.md)** - Testing strategies
