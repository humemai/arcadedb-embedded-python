# AsyncExecutor Tests

The `test_async_executor.py` file contains **8 tests** covering asynchronous operations and parallel execution.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/python-embedded/bindings/python/tests/test_async_executor.py){ .md-button }

## Overview

AsyncExecutor enables high-performance bulk operations with:

- ✅ **Parallel Execution** - 1-16 worker threads
- ✅ **Auto-Commit** - Configurable batch commits
- ✅ **Performance** - 3-5x faster than sequential
- ✅ **Callbacks** - Per-operation and global callbacks
- ✅ **Status Tracking** - `is_pending()` check

## Test Coverage

### Configuration Tests

#### test_async_executor_basic_create
Basic async record creation with 100 vertices.

**What it tests:**
- Getting async executor from database
- Creating records asynchronously
- `wait_completion()` blocks until done
- Closing executor shuts down workers

**Pattern:**
```python
async_exec = db.async_executor()

for i in range(100):
    vertex = db.new_vertex("User")
    vertex.set("id", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

#### test_async_executor_with_commit_every
Tests automatic commit batching.

**What it tests:**
- `set_commit_every(50)` commits every 50 records
- Creating 200 records triggers 4 auto-commits
- All records persisted after completion

**Pattern:**
```python
async_exec = db.async_executor()
async_exec.set_commit_every(50)

for i in range(200):
    vertex = db.new_vertex("Item")
    vertex.set("id", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

#### test_async_executor_with_parallel_level
Tests parallel worker configuration.

**What it tests:**
- `set_parallel_level(4)` sets 4 worker threads
- Creates 1000 records with parallel execution
- Verifies all records created

**Pattern:**
```python
async_exec = db.async_executor()
async_exec.set_parallel_level(4)

for i in range(1000):
    vertex = db.new_vertex("Product")
    vertex.set("productId", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

#### test_async_executor_method_chaining
Tests fluent interface method chaining.

**What it tests:**
- Chaining `set_parallel_level()`, `set_commit_every()`, `set_back_pressure()`
- All configurations applied correctly
- Records created with chained settings

**Pattern:**
```python
async_exec = (db.async_executor()
    .set_parallel_level(8)
    .set_commit_every(100)
    .set_back_pressure(75)
)

# Use configured executor
for i in range(500):
    vertex = db.new_vertex("Order")
    vertex.set("orderId", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

### Status Tracking Tests

#### test_async_executor_is_pending
Tests pending operation tracking.

**What it tests:**
- `is_pending()` returns True while operations running
- Returns False after completion
- Can poll status during execution

**Pattern:**
```python
async_exec = db.async_executor()

# Queue operations
for i in range(500):
    vertex = db.new_vertex("Task")
    vertex.set("taskId", i)
    async_exec.create_record(vertex)

# Check status
while async_exec.is_pending():
    time.sleep(0.1)  # Wait for completion

async_exec.close()
```

### Callback Tests

#### test_async_executor_callback
Tests per-operation callbacks.

**What it tests:**
- Callback invoked for each successful operation
- Callback receives created record
- Can track progress via callbacks

**Pattern:**
```python
created_count = 0

def on_created(record):
    nonlocal created_count
    created_count += 1

async_exec = db.async_executor()

for i in range(100):
    vertex = db.new_vertex("Item")
    vertex.set("id", i)
    async_exec.create_record(vertex, callback=on_created)

async_exec.wait_completion()
async_exec.close()

assert created_count == 100
```

---

#### test_async_executor_global_callback
Tests global callback for all operations.

**What it tests:**
- Setting global callback for all operations
- Callback invoked for every create/update/delete
- Useful for logging or progress tracking

**Pattern:**
```python
operations = []

def track_operation(record):
    operations.append(record)

async_exec = db.async_executor()
async_exec.set_global_callback(track_operation)

# All operations invoke callback
for i in range(50):
    vertex = db.new_vertex("Event")
    vertex.set("eventId", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()

assert len(operations) == 50
```

### Performance Tests

#### test_async_vs_sync_performance
Compares async vs synchronous performance.

**What it tests:**
- Async executor significantly faster than sequential
- Measures time for 1000 records
- Typically 3-5x speedup

**Pattern:**
```python
# Synchronous
start = time.time()
with db.transaction():
    for i in range(1000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
sync_time = time.time() - start

# Asynchronous
start = time.time()
async_exec = db.async_executor()
async_exec.set_parallel_level(8)
for i in range(1000):
    vertex = db.new_vertex("User")
    vertex.set("userId", i)
    async_exec.create_record(vertex)
async_exec.wait_completion()
async_exec.close()
async_time = time.time() - start

print(f"Speedup: {sync_time / async_time:.1f}x")
```

## Test Patterns

### Basic Async Creation
```python
async_exec = db.async_executor()

for i in range(100):
    record = db.new_vertex("Type")
    record.set("prop", value)
    async_exec.create_record(record)

async_exec.wait_completion()
async_exec.close()
```

### Configured Executor
```python
async_exec = (db.async_executor()
    .set_parallel_level(8)
    .set_commit_every(1000)
)

# Queue operations
async_exec.wait_completion()
async_exec.close()
```

### With Callbacks
```python
def callback(record):
    print(f"Created: {record.get('id')}")

async_exec = db.async_executor()

for i in range(100):
    record = db.new_vertex("Type")
    record.set("id", i)
    async_exec.create_record(record, callback=callback)

async_exec.wait_completion()
async_exec.close()
```

## Common Assertions

```python
# Verify record count
count = db.count_type("User")
assert count == 1000

# Check pending status
assert not async_exec.is_pending()

# Verify callback invocations
assert callback_count == expected_count
```

## Key Takeaways

1. **Always close executor** - Shutdown worker threads
2. **Wait before closing** - Call `wait_completion()` first
3. **Configure for workload** - Tune parallel level and commit size
4. **Use callbacks** - Track progress or handle errors
5. **Test performance** - Async is 3-5x faster for bulk ops

## See Also

- **[AsyncExecutor API](../../api/async_executor.md)** - Full API reference
- **[BatchContext Tests](test-batch-context.md)** - High-level batch API
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)** - Real-world usage
- **[Testing Overview](overview.md)** - Testing strategies
