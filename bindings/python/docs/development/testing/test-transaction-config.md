# Transaction Configuration Tests

The `test_transaction_config.py` file contains **9 tests** covering transaction configuration options and behaviors.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_transaction_config.py){ .md-button }

## Overview

Transaction configuration tests cover:

- ✅ **Isolation Levels** - READ_COMMITTED, REPEATABLE_READ
- ✅ **WAL Configuration** - Write-Ahead Log settings
- ✅ **Retry Logic** - Automatic retry on conflicts
- ✅ **Timeout Configuration** - Transaction timeout settings
- ✅ **Read-Only Transactions** - Optimized read transactions
- ✅ **Nested Transactions** - Transaction nesting behavior
- ✅ **Rollback Handling** - Transaction rollback scenarios

## Test Coverage

### test_transaction_isolation_levels
Tests different isolation level configurations.

**What it tests:**
- READ_COMMITTED isolation
- REPEATABLE_READ isolation
- Isolation level effects on concurrent access

**Pattern:**
```python
# READ_COMMITTED
with db.transaction(isolation_level="READ_COMMITTED"):
    # Changes from other transactions visible
    pass

# REPEATABLE_READ
with db.transaction(isolation_level="REPEATABLE_READ"):
    # Consistent snapshot throughout transaction
    pass
```

---

### test_transaction_wal_configuration
Tests Write-Ahead Log settings.

**What it tests:**
- Enabling/disabling WAL
- WAL performance impact
- Durability vs speed tradeoff

**Pattern:**
```python
# With WAL (durable)
with db.transaction(use_wal=True):
    vertex = db.new_vertex("User")
    vertex.set("name", "Alice")
    vertex.save()

# Without WAL (faster, less durable)
with db.transaction(use_wal=False):
    for i in range(1000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
```

---

### test_transaction_retry_on_conflict
Tests automatic retry configuration.

**What it tests:**
- Retry on write conflicts
- Max retry attempts
- Exponential backoff
- Success after retries

**Pattern:**
```python
# Automatic retry on conflict
with db.transaction(retry_on_conflict=True, max_retries=3):
    vertex = db.new_vertex("Counter")

    # Read current value
    count = vertex.get("count") or 0

    # Increment (may conflict)
    vertex.set("count", count + 1)
    vertex.save()
```

---

### test_transaction_timeout
Tests transaction timeout configuration.

**What it tests:**
- Setting timeout in seconds
- Timeout exception raised
- Cleanup after timeout

**Pattern:**
```python
try:
    with db.transaction(timeout=5):  # 5 second timeout
        # Long-running operation
        time.sleep(10)
except TransactionTimeoutException:
    print("Transaction timed out")
```

---

### test_read_only_transaction
Tests read-only transaction optimization.

**What it tests:**
- Creating read-only transaction
- Attempts to write raise error
- Performance benefits

**Pattern:**
```python
# Read-only transaction (optimized)
with db.transaction(read_only=True):
    results = db.query("sql", "SELECT FROM User")
    users = list(results)

    # Write attempt raises error
    try:
        vertex = db.new_vertex("User")
        vertex.save()  # Error!
    except Exception as e:
        print(f"Write not allowed: {e}")
```

---

### test_transaction_rollback_on_error
Tests automatic rollback on exceptions.

**What it tests:**
- Exception triggers rollback
- No changes persisted
- Database state unchanged

**Pattern:**
```python
initial_count = db.count_type("User")

try:
    with db.transaction():
        # Create some records
        for i in range(10):
            vertex = db.new_vertex("User")
            vertex.set("userId", i)
            vertex.save()

        # Raise error
        raise ValueError("Something went wrong")
except ValueError:
    pass

# Verify rollback
assert db.count_type("User") == initial_count
```

---

### test_manual_rollback
Tests explicit rollback call.

**What it tests:**
- Manual `db.rollback()` call
- Changes discarded
- Transaction can continue after rollback

**Pattern:**
```python
with db.transaction():
    vertex = db.new_vertex("User")
    vertex.set("name", "Alice")
    vertex.save()

    # Decide to rollback
    db.rollback()

    # Continue with different operation
    vertex = db.new_vertex("User")
    vertex.set("name", "Bob")
    vertex.save()

# Only Bob saved
```

---

### test_nested_transaction_behavior
Tests nested transaction handling.

**What it tests:**
- Nested transactions not supported (or use savepoints)
- Inner transaction behavior
- Rollback scope

**Pattern:**
```python
with db.transaction():
    vertex1 = db.new_vertex("User")
    vertex1.set("name", "Alice")
    vertex1.save()

    # Nested transaction (may not be supported)
    try:
        with db.transaction():
            vertex2 = db.new_vertex("User")
            vertex2.set("name", "Bob")
            vertex2.save()
    except Exception as e:
        print(f"Nested transactions: {e}")
```

---

### test_transaction_performance_impact
Tests performance of different configurations.

**What it tests:**
- WAL enabled vs disabled speed
- Batch size impact
- Read-only performance

**Pattern:**
```python
import time

# With WAL
start = time.time()
with db.transaction(use_wal=True):
    for i in range(1000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
wal_time = time.time() - start

# Without WAL
start = time.time()
with db.transaction(use_wal=False):
    for i in range(1000):
        vertex = db.new_vertex("User")
        vertex.set("userId", i)
        vertex.save()
no_wal_time = time.time() - start

print(f"WAL: {wal_time:.2f}s, No WAL: {no_wal_time:.2f}s")
print(f"Speedup: {wal_time / no_wal_time:.1f}x")
```

## Test Patterns

### Basic Configuration
```python
with db.transaction(
    isolation_level="READ_COMMITTED",
    use_wal=True,
    timeout=30
):
    # Operations
    pass
```

### Retry on Conflict
```python
with db.transaction(retry_on_conflict=True, max_retries=5):
    # Operations that may conflict
    pass
```

### Read-Only
```python
with db.transaction(read_only=True):
    # Only read operations
    results = db.query("sql", "SELECT FROM User")
```

### Performance Tuning
```python
# Fast bulk insert (no WAL)
with db.transaction(use_wal=False):
    for item in large_dataset:
        vertex = db.new_vertex("Type")
        # Set properties
        vertex.save()
```

## Common Assertions

```python
# Transaction committed
initial = db.count_type("User")
with db.transaction():
    vertex = db.new_vertex("User")
    vertex.save()
assert db.count_type("User") == initial + 1

# Transaction rolled back
initial = db.count_type("User")
try:
    with db.transaction():
        vertex = db.new_vertex("User")
        vertex.save()
        raise ValueError()
except ValueError:
    pass
assert db.count_type("User") == initial  # No change

# Read-only enforcement
with db.transaction(read_only=True):
    try:
        vertex = db.new_vertex("User")
        vertex.save()
        assert False, "Should have raised error"
    except Exception:
        pass  # Expected
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `isolation_level` | str | READ_COMMITTED | Isolation level |
| `use_wal` | bool | True | Enable Write-Ahead Log |
| `retry_on_conflict` | bool | False | Auto-retry on conflicts |
| `max_retries` | int | 3 | Max retry attempts |
| `timeout` | int | None | Timeout in seconds |
| `read_only` | bool | False | Read-only transaction |

## Key Takeaways

1. **Use WAL for durability** - Disable only for bulk loads
2. **Set timeouts** - Prevent long-running transactions
3. **Retry on conflicts** - For concurrent workloads
4. **Read-only for reads** - Performance optimization
5. **Handle rollbacks** - Always check transaction success

## See Also

- **[Transactions API](../../api/transactions.md)** - Full API reference
- **[Concurrency Tests](test-concurrency.md)** - Concurrent access patterns
- **[Database API](../../api/database.md)** - Database operations
- **[Testing Overview](overview.md)** - Testing strategies
