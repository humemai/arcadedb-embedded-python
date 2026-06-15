# Transaction Configuration Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_transaction_config.py){ .md-button }

There are 9 tests covering WAL flush modes, read-your-writes, auto-transaction control, and combinations of these settings (plus error handling on a closed database).

## Key Config Options

- WAL flush: `set_wal_flush("no" | "yes_nometadata" | "yes_full")`
- Read-your-writes: `set_read_your_writes(bool)`
- Auto-transaction: `set_auto_transaction(bool)`

### test_set_wal_flush_modes

Tests all valid WAL flush modes.

**What it tests:**

- `set_wal_flush("no")` (default / maximum performance)
- `set_wal_flush("yes_nometadata")`
- `set_wal_flush("yes_full")` (maximum durability)
- Resetting back to `"no"`

**Pattern:**
```python
temp_db.set_wal_flush("no")
temp_db.set_wal_flush("yes_nometadata")
temp_db.set_wal_flush("yes_full")
temp_db.set_wal_flush("no")
```

---

### test_set_wal_flush_invalid_mode

Tests that invalid WAL flush modes raise `ValueError`.

**What it tests:**

- An unknown mode (`"invalid_mode"`) raises `ValueError` matching "Invalid WAL flush mode"
- An uppercase mode (`"YES_FULL"`) is rejected; the mode must be lowercase

**Pattern:**
```python
with pytest.raises(ValueError, match="Invalid WAL flush mode"):
    temp_db.set_wal_flush("invalid_mode")

with pytest.raises(ValueError, match="Invalid WAL flush mode"):
    temp_db.set_wal_flush("YES_FULL")  # Must be lowercase
```

---

### test_set_read_your_writes

Tests read-your-writes configuration.

**What it tests:**

- Enabling read-your-writes (`True`, the default)
- Disabling it (`False`, for better concurrency)
- Re-enabling it

**Pattern:**
```python
temp_db.set_read_your_writes(True)
temp_db.set_read_your_writes(False)
temp_db.set_read_your_writes(True)
```

---

### test_set_auto_transaction

Tests auto-transaction configuration.

**What it tests:**

- Enabling auto-transaction (`True`, the default)
- Disabling it (`False`, for manual control)
- Re-enabling it

**Pattern:**
```python
temp_db.set_auto_transaction(True)
temp_db.set_auto_transaction(False)
temp_db.set_auto_transaction(True)
```

---

### test_transaction_config_with_operations

Tests config methods alongside normal operations.

**What it tests:**

- Configuring durability (`set_wal_flush("yes_full")`, `set_read_your_writes(True)`) then writing inside a transaction
- Switching to performance mode (`set_wal_flush("no")`, `set_read_your_writes(False)`) and writing more
- Verifying counts via `SELECT count(*)` queries (2, then 3)

**Pattern:**
```python
temp_db.command("sql", "CREATE VERTEX TYPE ConfigTest")
temp_db.set_wal_flush("yes_full")
temp_db.set_read_your_writes(True)

with temp_db.transaction():
    temp_db.command("sql", "CREATE VERTEX ConfigTest SET name = 'test1'")
    temp_db.command("sql", "CREATE VERTEX ConfigTest SET name = 'test2'")

count = next(temp_db.query("sql", "SELECT count(*) as cnt FROM ConfigTest")).get("cnt")
assert count == 2
```

---

### test_manual_transaction_mode

Tests manual transaction control with auto-transaction disabled.

**What it tests:**

- `set_auto_transaction(False)` requires explicit `db.transaction()` contexts
- Writes inside the context are persisted (count == 2)
- Auto-transaction is re-enabled in a `finally` block

**Pattern:**
```python
temp_db.command("sql", "CREATE VERTEX TYPE ManualTest")
temp_db.set_auto_transaction(False)
try:
    with temp_db.transaction():
        temp_db.command("sql", "CREATE VERTEX ManualTest SET name = 'manual1'")
        temp_db.command("sql", "CREATE VERTEX ManualTest SET name = 'manual2'")
finally:
    temp_db.set_auto_transaction(True)
```

---

### test_wal_flush_with_bulk_operations

Tests WAL flush modes with chunked bulk inserts.

**What it tests:**

- Bulk inserting with `set_wal_flush("yes_full")` in 200-record chunks up to 500
- Switching to `set_wal_flush("no")` and continuing up to 1000
- Verifying counts (500, then 1000)

**Pattern:**
```python
temp_db.command("sql", "CREATE VERTEX TYPE BatchTest")
temp_db.set_wal_flush("yes_full")

chunk_size = 200
total = 500
for start in range(0, total, chunk_size):
    with temp_db.transaction():
        for i in range(start, min(start + chunk_size, total)):
            temp_db.command(
                "sql", "CREATE VERTEX BatchTest SET value = :value", {"value": i}
            )
```

---

### test_config_methods_on_closed_database

Tests that config methods raise on a closed database.

**What it tests:**

- `set_wal_flush(...)`, `set_read_your_writes(...)`, and `set_auto_transaction(...)`
    each raise `ArcadeDBError` matching "closed" after `db.close()`

**Pattern:**
```python
db = create_database(temp_db_path)
db.close()

with pytest.raises(ArcadeDBError, match="closed"):
    db.set_wal_flush("no")
```

---

### test_combined_config_changes

Tests changing multiple config settings together.

**What it tests:**

- Starting with durability settings (`yes_full`, read-your-writes on, auto-transaction on)
- Switching to performance settings (`no`, read-your-writes off) and writing more
- Verifying the final count (2) and restoring durability settings

**Pattern:**
```python
temp_db.set_wal_flush("yes_full")
temp_db.set_read_your_writes(True)
temp_db.set_auto_transaction(True)
temp_db.command("sql", "CREATE VERTEX TYPE Combined")

with temp_db.transaction():
    temp_db.command("sql", "CREATE VERTEX Combined SET value = 1")

temp_db.set_wal_flush("no")
temp_db.set_read_your_writes(False)

with temp_db.transaction():
    temp_db.command("sql", "CREATE VERTEX Combined SET value = 2")
```

## Common Assertions

```python
# Invalid WAL mode rejected
with pytest.raises(ValueError, match="Invalid WAL flush mode"):
    db.set_wal_flush("invalid_mode")

# Config methods raise on a closed database
with pytest.raises(ArcadeDBError, match="closed"):
    db.set_wal_flush("no")

# Records written under any flush mode are persisted
count = next(db.query("sql", "SELECT count(*) as cnt FROM ConfigTest")).get("cnt")
assert count == 2
```

## Configuration Methods

| Method | Argument | Notes |
|--------|----------|-------|
| `set_wal_flush(mode)` | `"no"`, `"yes_nometadata"`, `"yes_full"` | Lowercase only; invalid modes raise `ValueError` |
| `set_read_your_writes(flag)` | `bool` | Default `True` |
| `set_auto_transaction(flag)` | `bool` | Default `True`; when `False`, use explicit `db.transaction()` |

## Key Takeaways

1. **WAL flush modes** - `"yes_full"` for durability, `"no"` for performance
2. **Lowercase modes only** - Uppercase or unknown modes raise `ValueError`
3. **Read-your-writes** - Toggle for concurrency vs immediate visibility
4. **Manual transactions** - Disable auto-transaction and use `db.transaction()` contexts
5. **Closed database** - Config methods raise `ArcadeDBError` once closed

## See Also

- **[Transactions API](../../api/transactions.md)** - Full API reference
- **[Concurrency Tests](test-concurrency.md)** - Concurrent access patterns
- **[Database API](../../api/database.md)** - Database operations
- **[Testing Overview](overview.md)** - Testing strategies
