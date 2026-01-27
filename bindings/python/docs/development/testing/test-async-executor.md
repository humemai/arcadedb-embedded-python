# AsyncExecutor Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_async_executor.py){ .md-button }

The file contains **8 tests** covering asynchronous operations and parallel execution.

## Overview

AsyncExecutor tests cover:

- ✅ **Parallel execution** – configurable worker threads
- ✅ **Auto-commit cadence** – `set_commit_every()` batching
- ✅ **Per-operation callbacks** – verifies callback counts
- ✅ **Status checks** – `is_pending()` used after completion
- ✅ **Baseline perf timing** – async vs sync insert timings (informational)

## Test Coverage

### Configuration Tests

#### test_async_executor_basic_create

Basic async record creation with 100 vertices (commit every 25).

**What it tests:**

- Getting async executor from database
- Creating records asynchronously
- `wait_completion()` blocks until done
- Closing executor shuts down workers

**Pattern:**
```python
async_exec = db.async_executor()
async_exec.set_commit_every(25)  # Batch writes into transactions

for i in range(100):
    vertex = db.new_vertex("User")
    vertex.set("id", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

#### test_async_executor_with_commit_every

Automatic commit batching every 50 records; verifies 200 created.

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

Uses 4 workers, 500 records; measures elapsed time (informational) and asserts count.

**What it tests:**

- `set_parallel_level(4)` sets 4 worker threads
- Creates 500 records with parallel execution
- Verifies all records created

**Pattern:**
```python
async_exec = db.async_executor()
async_exec.set_parallel_level(4)
async_exec.set_commit_every(100)

for i in range(500):
    vertex = db.new_vertex("Product")
    vertex.set("productId", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

---

#### test_async_executor_method_chaining

Chains `set_parallel_level(2)`, `set_commit_every(25)`, `set_back_pressure(75)`; asserts 100 created.

**What it tests:**

- Chaining `set_parallel_level()`, `set_commit_every()`, `set_back_pressure()`
- All configurations applied correctly
- Records created with chained settings

**Pattern:**
```python
async_exec = (db.async_executor()
    .set_parallel_level(2)
    .set_commit_every(25)
    .set_back_pressure(75)
)

# Use configured executor
for i in range(100):
    vertex = db.new_vertex("Task")
    vertex.set("id", i)
    async_exec.create_record(vertex)

async_exec.wait_completion()
async_exec.close()
```

### Status Tracking Tests

#### test_async_executor_is_pending

Queues 1000 records with `set_commit_every(100)` and uses `is_pending()` after `wait_completion()` to confirm the queue is empty (no assertion during in-flight phase due to timing variability).

### Callback Tests

#### test_async_executor_callback

Per-operation callback collects created IDs; asserts 10 callbacks fired and 10 records exist.

**Pattern:**
```python
created_count = 0

def on_created(record):
    nonlocal created_count
    created_count += 1

async_exec = db.async_executor()

for i in range(10):
    vertex = db.new_vertex("User")
    vertex.set("name", f"User{i}")
    async_exec.create_record(vertex, callback=on_created)

async_exec.wait_completion()
async_exec.close()

assert created_count == 10
```

---

#### test_async_executor_global_callback

Documents JPype proxy issues with global callbacks; uses per-operation callbacks as a workaround and asserts 20 successes.

### Performance Tests

#### test_async_vs_sync_performance

Times 1000 synchronous inserts vs async (4 workers, commit every 250); prints speedup but only sanity-checks that async run completes and records are present (no enforced speedup assertion).

## Test Pattern (mirrors `test_async_executor_basic_create`)

```python
db = arcadedb.create_database(str(db_path))
db.schema.create_vertex_type("User")

async_exec = db.async_executor().set_commit_every(25)
for i in range(100):
    v = db.new_vertex("User")
    v.set("id", i)
    v.set("name", f"User{i}")
    async_exec.create_record(v)

async_exec.wait_completion()
async_exec.close()
assert db.count_type("User") == 100
```

## Key Takeaways

1. Call `wait_completion()` before `close()` to flush worker threads.
2. Tune `set_commit_every()` and `set_parallel_level()` per workload (tests use 25/50/100/250 and 2–4 workers).
3. Prefer per-operation callbacks; global callbacks hit JPype proxy issues (documented in tests).
4. `is_pending()` is checked after completion to ensure queues are empty.
5. Performance test prints async vs sync timings but does not enforce a speedup assertion.

## See Also

- **[AsyncExecutor API](../../api/async_executor.md)**
- **[BatchContext Tests](test-batch-context.md)**
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)**
- **[Testing Overview](overview.md)**
