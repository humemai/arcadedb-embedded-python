# Database Utilities Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_database_utils.py){ .md-button }

There are 5 tests covering the `count_type`, `is_transaction_active`, and `drop` database utility methods, an integration test combining several methods, and error handling on a closed database.

### test_count_type

Tests `Database.count_type()`.

**What it tests:**

- Counting records for a populated type (`User` == 10, `Product` == 5)
- Counting a non-existent type returns `0`

**Pattern:**
```python
with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE DOCUMENT TYPE User")
    with db.transaction():
        for i in range(10):
            db.command("sql", f"INSERT INTO User SET name = 'User{i}'")

    assert db.count_type("User") == 10
    assert db.count_type("NonExistent") == 0
```

---

### test_is_transaction_active

Tests `Database.is_transaction_active()`.

**What it tests:**

- `False` before any transaction
- `True` inside a `db.transaction()` context
- `False` again after the transaction completes

**Pattern:**
```python
with arcadedb.create_database(temp_db_path) as db:
    assert not db.is_transaction_active()
    with db.transaction():
        assert db.is_transaction_active()
    assert not db.is_transaction_active()
```

---

### test_drop_database

Tests `Database.drop()`.

**What it tests:**

- Creating and populating a type, then verifying the count
- `db.drop()` removes the database
- The database reports `is_open()` as `False` after the drop

**Pattern:**
```python
db = arcadedb.create_database(temp_db_path)
db.command("sql", "CREATE DOCUMENT TYPE Test")
with db.transaction():
    db.command("sql", "INSERT INTO Test SET value = 1")

db.drop()
assert not db.is_open()
```

---

### test_database_methods_integration

Exercises several utility methods together.

**What it tests:**

- Creating `VERTEX TYPE Person` and `EDGE TYPE Knows`
- `count_type("Person")` == 2 after inserting two vertices
- `ResultSet.first()` returns the first ordered row
- `ResultSet.to_list()` materializes the rows into a list

**Pattern:**
```python
with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")
    with db.transaction():
        db.command("sql", "CREATE VERTEX Person SET name = 'Alice'")
        db.command("sql", "CREATE VERTEX Person SET name = 'Bob'")

    assert db.count_type("Person") == 2
    first = db.query("sql", "SELECT FROM Person ORDER BY name").first()
    assert first.get("name") == "Alice"

    people = db.query("sql", "SELECT FROM Person ORDER BY name").to_list()
    assert len(people) == 2
```

---

### test_error_handling_new_methods

Tests error handling on a closed database.

**What it tests:**

- Calling `count_type(...)` on a closed database raises `ArcadeDBError`
- Calling `is_transaction_active()` on a closed database raises `ArcadeDBError`

**Pattern:**
```python
db = arcadedb.create_database(temp_db_path)
db.close()

with pytest.raises(arcadedb.ArcadeDBError):
    db.count_type("Test")

with pytest.raises(arcadedb.ArcadeDBError):
    db.is_transaction_active()
```

## Common Assertions

```python
# Type counting
assert db.count_type("User") == 10
assert db.count_type("NonExistent") == 0

# Transaction state
assert not db.is_transaction_active()

# Dropped database is closed
db.drop()
assert not db.is_open()

# ResultSet helpers
assert db.query("sql", "SELECT FROM Person ORDER BY name").first().get("name") == "Alice"
assert len(db.query("sql", "SELECT FROM Person ORDER BY name").to_list()) == 2
```

## Key Takeaways

1. **`count_type`** - Returns `0` for unknown types instead of raising
2. **`is_transaction_active`** - Tracks the active transaction state
3. **`drop`** - Closes the database; `is_open()` returns `False` afterward
4. **`ResultSet.first()` / `to_list()`** - Convenient row access helpers
5. **Closed database** - Utility methods raise `ArcadeDBError` once closed

## See Also

- **[Database API](../../api/database.md)** - Database operations
- **[Testing Overview](overview.md)** - Testing strategies
- **[Core Tests](test-core.md)** - Core functionality tests
