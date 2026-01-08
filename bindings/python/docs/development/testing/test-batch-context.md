# BatchContext Tests

The `test_batch_context.py` file contains **13 tests** covering high-level batch operations with progress tracking.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_batch_context.py){ .md-button }

## Overview

BatchContext tests cover:

- ✅ **Context manager lifecycle** – create/update/delete within `with db.batch_context(...)`
- ✅ **Parallel + batch sizing** – tested with batch sizes 10–5000 and parallel up to 8
- ✅ **Callbacks and success counts** – per-record callbacks, `get_success_count()`
- ✅ **Mixed operations** – create/update/delete in one batch
- ✅ **Performance smoke checks** – prints throughput vs synchronous (informational)

## Test Coverage

### Key Tests (matched to code)

- `test_batch_context_basic`: 500 vertices via `batch_context(batch_size=100, parallel=2)`; count checked via SQL.
- `test_batch_context_with_documents`: 200 documents with `batch_size=50, parallel=4`; count checked via SQL.
- `test_batch_context_with_edges`: vertices created in a transaction; edges created inside `with db.transaction(): with db.batch_context(batch_size=10)`; count==3.
- `test_batch_context_with_callbacks`: per-record callback collects 100 Item IDs; count==100.
- `test_batch_context_success_count`: `batch.get_success_count()` returns 250 after `batch.wait_completion()`.
- `test_batch_context_create_record`: creates 150 pre-built Vertex records via `create_record`.
- `test_batch_context_is_pending`: queues 5000 ops (batch_size=1000, parallel=2); `is_pending()` may be True in-flight, False after exit.
- `test_batch_context_wait_completion`: 2000 events (batch_size=500, parallel=4); `wait_completion()` then `not is_pending()`.
- `test_batch_context_performance`: 10k vertices (batch_size=5000, parallel=8); prints throughput vs sync (no assertion on speedup).
- `test_batch_context_different_batch_sizes`: 50 records with batch_size=10 and 50 with 5000; total 100.
- `test_batch_context_update_record`: updates 100 counters via `modify()` and `update_record`; sum==9900.
- `test_batch_context_delete_record`: deletes half the records with `delete_record`; count==100.
- `test_batch_context_mixed_operations`: create 50 new, update 25, delete 25; final counts: total 75, updated 25, new 50.

### Example Snippet (mirrors `test_batch_context_basic`)
```python
with db.batch_context(batch_size=100, parallel=2) as batch:
    for i in range(500):
        batch.create_vertex("User", userId=i, name=f"User{i}")

count = next(db.query("sql", "SELECT count(*) as count FROM User")).get("count")
assert count == 500
```

### Edge Creation (from `test_batch_context_with_edges`)
```python
with db.transaction():
    a = db.new_vertex("Person"); a.set("name", "Alice"); a.save()
    b = db.new_vertex("Person"); b.set("name", "Bob"); b.save()
    c = db.new_vertex("Person"); c.set("name", "Charlie"); c.save()

people = list(db.query("sql", "SELECT FROM Person"))
with db.transaction():
    with db.batch_context(batch_size=10) as batch:
        batch.create_edge(people[0].get_vertex(), people[1].get_vertex(), "KNOWS", since=2020)
        batch.create_edge(people[1].get_vertex(), people[2].get_vertex(), "KNOWS", since=2021)
        batch.create_edge(people[2].get_vertex(), people[0].get_vertex(), "KNOWS", since=2022)

edge_count = next(db.query("sql", "SELECT count(*) as count FROM KNOWS")).get("count")
assert edge_count == 3
```

### Performance (informational)
```python
with db.batch_context(batch_size=5000, parallel=8) as batch:
    for i in range(10000):
        batch.create_vertex("Benchmark", value=i)

# Synchronous comparison runs separately; prints rec/sec but no speedup assertion
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
