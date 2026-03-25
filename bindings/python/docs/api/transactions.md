# Transactions API

The `TransactionContext` class and `Database.transaction()` method provide ACID-compliant transaction management with automatic commit/rollback via Python context managers.

## Overview

ArcadeDB transactions provide:

- **Atomicity**: All changes commit together or none commit
- **Consistency**: Schema validation and constraint enforcement
- **Isolation**: Read committed isolation level
- **Durability**: Changes persisted to disk on commit

**Key Concepts:**

- **Auto-commit** queries read latest data but don't create transactions
- **Explicit transactions** required for write operations
- **Context managers** automatically handle commit/rollback
- **Rollback on exception** ensures data integrity

## Transaction Scope

It is important to distinguish between operations that require explicit transactions and those that are auto-transactional:

| Operation Type | Examples | Transaction Requirement |
| :--- | :--- | :--- |
| **Schema Operations** | `create_vertex_type()`, `create_property()`, `create_index()`, `db.command("sql", "DROP INDEX...")` | **Auto-transactional** (Do NOT wrap in `with db.transaction():`) |
| **Data Write** | `db.command("sql", "INSERT...")`, `db.command("sql", "UPDATE...")`, `db.command("sql", "DELETE...")`, `db.command("opencypher", "CREATE ...")` | **Required** (Wrap in `with db.transaction():`) |
| **Bulk Operations** | `db.command("sql", "IMPORT DATABASE...")`, `db.import_documents(...)`, `db.graph_batch(...)` | **Auto-transactional / auto-managed** (Built-in transaction management) |
| **Data Read** | `db.query()`, `db.command("sql", "SELECT...")`, `db.lookup_by_rid()` | **Optional** (Can run outside transaction for better performance) |
| **Vector Operations** | `db.create_vector_index()` | **Auto-transactional** (Do NOT wrap) |

### Key Distinction: `db.query()` vs `db.command()`

- **`db.query()`**: Always used for **read-only queries**. Returns a `ResultSet` with read-only results. **Does NOT require a transaction.**
- **`db.command()`**: Used for **both DDL and DML operations**. For read statements such
    as `SELECT`, it returns a `ResultSet` and can run outside a transaction. For write
    statements such as `INSERT`, `UPDATE`, and `DELETE`, wrap it in
    `with db.transaction():`. DDL such as `CREATE TYPE`, `CREATE PROPERTY`, `CREATE INDEX`,
    `DROP`, plus bulk commands such as `IMPORT DATABASE` and `MOVE`, remain
    auto-transactional.
- **`db.import_documents()`**: Runs the Java importer through the narrow document-import
    wrapper. It manages its own importer/async lifecycle, so you should not wrap it in
    `with db.transaction():`.
- **`db.graph_batch()`**: Creates the engine-backed bulk graph-ingest helper. It manages
    its own flush/commit lifecycle, so you should not wrap it in `with db.transaction():`.

### Best Practice Pattern

```python
# ✅ CORRECT: Queries outside transaction
results = db.query("SELECT * FROM Person")
for result in results:
    name = result.get("name")  # Safe, read-only

# ✅ CORRECT: Write operations inside transaction
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = ?", "Alice")

# ❌ INCORRECT: Write operation without transaction
db.command("sql", "INSERT INTO Person SET name = ?", "Alice")  # Will fail
```

## Transaction Methods

All transaction methods are on the `Database` class:

### `Database.transaction() -> TransactionContext`

Create a transaction context manager.

**Returns:**

- `TransactionContext`: Context manager for transaction scope

**Example:**

```python
import arcadedb_embedded as arcadedb

db = arcadedb.open_database("./mydb")

# Context manager handles begin/commit/rollback
with db.transaction():
    # All operations in this block are transactional
    db.command(
        "sql",
        "INSERT INTO Person SET name = ?, age = ?",
        "Alice",
        30,
    )

# Automatically commits on successful exit
# Automatically rolls back on exception
```

---

### `Database.begin()`

Manually begin a transaction.

**Raises:**

- `ArcadeDBError`: If transaction already active

**Example:**

```python
db.begin()

try:
    db.command("sql", "INSERT INTO Person SET name = ?", "Bob")

    db.commit()
except Exception as e:
    db.rollback()
    raise
```

**Recommendation:** Use `db.transaction()` context manager instead for automatic handling.

---

### `Database.commit()`

Commit the current transaction and persist changes.

**Raises:**

- `ArcadeDBError`: If no active transaction or commit fails

**Example:**

```python
db.begin()

db.command("sql", "INSERT INTO Item SET value = ?", 42)

db.commit()  # Changes persisted
```

---

### `Database.rollback()`

Roll back the current transaction and discard all changes.

**Raises:**

- `ArcadeDBError`: If no active transaction

**Example:**

```python
db.begin()

db.command("sql", "INSERT INTO Test SET data = ?", "temporary")

# Oops, need to undo
db.rollback()  # Changes discarded
```

---

## TransactionContext Class

Context manager returned by `db.transaction()`. Automatically manages transaction lifecycle.

### Behavior

```python
with db.transaction():
    # db.begin() called automatically

    # ... your code ...

    # On normal exit: db.commit() called
    # On exception: db.rollback() called
```

### Implementation

The `TransactionContext` class is simple but powerful:

```python
class TransactionContext:
    def __enter__(self):
        self.database.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.database.commit()  # Success
        else:
            self.database.rollback()  # Exception occurred
```

---

## Usage Patterns

### Basic Transaction

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./txn_demo")

# Create schema
db.command("sql", "CREATE DOCUMENT TYPE Account")
db.command("sql", "CREATE PROPERTY Account.name STRING")
db.command("sql", "CREATE PROPERTY Account.balance DECIMAL")

# Insert data
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Account SET name = ?, balance = ?",
        "Alice",
        1000.00,
    )

db.close()
```

---

### Multiple Operations in Transaction

```python
with db.transaction():
    # All these operations are atomic

    # Create multiple records
    for i in range(10):
        db.command(
            "sql",
            "INSERT INTO Item SET id = ?, value = ?",
            f"item_{i}",
            i * 10,
        )

    # Query within transaction (sees uncommitted changes)
    result = db.query("sql", "SELECT COUNT(*) as cnt FROM Item")
    count = result.next().get("cnt")
    print(f"Created {count} items")

# All commits together or none commit
```

---

### Conditional Commit

```python
with db.transaction():
    account_rec = db.query("sql", "SELECT FROM Account WHERE name = 'Alice'").first()

    if not account_rec:
        raise ValueError("Account not found")

    account_doc = account_rec.get_element()
    current_balance = float(account_doc.get("balance"))
    withdrawal = 500.00

    if current_balance >= withdrawal:
        new_balance = current_balance - withdrawal
        db.command(
            "sql",
            "UPDATE Account SET balance = ? WHERE name = ?",
            new_balance,
            "Alice",
        )
        print(f"Withdrawal successful. New balance: {new_balance}")
    else:
        # Raise exception to trigger rollback
        raise ValueError(f"Insufficient funds: {current_balance}")
```

---

### Nested Context (Not Nested Transactions)

**Important:** ArcadeDB doesn't support true nested transactions. Nested contexts use the same transaction:

```python
# This uses ONE transaction
with db.transaction():
    db.command("sql", "INSERT INTO Outer SET layer = ?", "outer")

    # This does NOT create a new transaction
    # It uses the same transaction as above
    with db.transaction():
        db.command("sql", "INSERT INTO Inner SET layer = ?", "inner")

    # Both doc1 and doc2 commit together

# Both commits together or both roll back
```

**Recommendation:** Avoid nesting `db.transaction()` - it's confusing and doesn't create nested transactions.

---

### Manual Transaction Control

For more control, use `begin()`, `commit()`, `rollback()` directly:

```python
db.begin()

try:
    # Operation 1
    db.command("sql", "INSERT INTO Step1 SET status = ?", "processing")

    # Operation 2 (may fail)
    result = db.command("sql", "UPDATE Step1 SET status = 'complete'")

    # Check condition
    if not result:
        raise Exception("Update failed")

    # Success - commit
    db.commit()
    print("Transaction committed")

except Exception as e:
    # Failure - rollback
    db.rollback()
    print(f"Transaction rolled back: {e}")
```

---

## Error Handling

### Automatic Rollback

```python
try:
    with db.transaction():
        db.command("sql", "INSERT INTO Test SET value = ?", "data")

        # Simulate error
        raise ValueError("Something went wrong!")

        # This won't execute
        db.command("sql", "UPDATE Test SET value = 'updated'")

except ValueError as e:
    # Transaction automatically rolled back
    print(f"Error: {e}")
    print("Changes were rolled back")
```

---

### Partial Success Handling

```python
from arcadedb_embedded import ArcadeDBError

success_count = 0
error_count = 0

records = [
    {"name": "Valid1", "age": 30},
    {"name": "Valid2", "age": 25},
    {"name": "Invalid", "age": "not_a_number"},  # Will fail
    {"name": "Valid3", "age": 35},
]

for record in records:
    try:
        with db.transaction():
            db.command(
                "sql",
                "INSERT INTO Person SET name = ?, age = ?",
                record["name"],
                record["age"],
            )

        success_count += 1

    except (ArcadeDBError, ValueError) as e:
        error_count += 1
        print(f"Failed to insert {record['name']}: {e}")

print(f"Success: {success_count}, Errors: {error_count}")
```

---

### Validation Before Commit

```python
with db.transaction():
    for i in range(5):
        db.command(
            "sql",
            "INSERT INTO Product SET sku = ?, price = ?",
            f"PROD-{i:03d}",
            i * 10.0,
        )

    # Validation check
    result = db.query("sql", "SELECT COUNT(*) as cnt FROM Product")
    count = result.next().get("cnt")

    if count < 5:
        # Trigger rollback by raising exception
        raise AssertionError(f"Expected 5 products, got {count}")

    # Validation passed, commit happens automatically
```

---

## ACID Guarantees

### Atomicity Example

```python
# Transfer money between accounts (atomic)
with db.transaction():
    # Debit from Alice
    db.command("sql",
               "UPDATE Account SET balance = balance - 100 "
               "WHERE name = 'Alice'")

    # Credit to Bob
    db.command("sql",
               "UPDATE Account SET balance = balance + 100 "
               "WHERE name = 'Bob'")

# Both updates commit together or neither commits
```

---

### Consistency Example

```python
# Schema constraints enforced in transactions
db.command("sql", "CREATE DOCUMENT TYPE User")
db.command("sql", "CREATE PROPERTY User.email STRING")
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")

# This will fail - email is mandatory
try:
    with db.transaction():
    db.command("sql", "INSERT INTO User SET name = 'Alice'")
except Exception as e:
    print(f"Constraint violation: {e}")
    # Transaction rolled back automatically

# This will fail - email must be unique
try:
    with db.transaction():
    db.command("sql", "INSERT INTO User SET email = 'alice@example.com'")
    db.command("sql", "INSERT INTO User SET email = 'alice@example.com'")  # Duplicate!
except Exception as e:
    print(f"Unique constraint violation: {e}")
    # Both user1 and user2 rolled back
```

---

### Isolation Example

```python
import threading
import time

def writer_thread():
    """Writer updates balance."""
    with db.transaction():
        time.sleep(0.5)  # Simulate slow operation
        db.command("sql", "UPDATE Account SET balance = 2000 WHERE name = 'Alice'")

def reader_thread():
    """Reader sees consistent data."""
    # Read before transaction commits
    result = db.query("sql", "SELECT balance FROM Account WHERE name = 'Alice'")
    balance = result.next().get("balance")
    print(f"Balance: {balance}")  # Sees old value (1000)

    time.sleep(1)  # Wait for writer to commit

    # Read after transaction commits
    result = db.query("sql", "SELECT balance FROM Account WHERE name = 'Alice'")
    balance = result.next().get("balance")
    print(f"Balance: {balance}")  # Sees new value (2000)

# Start threads
t1 = threading.Thread(target=writer_thread)
t2 = threading.Thread(target=reader_thread)
t1.start()
t2.start()
t1.join()
t2.join()
```

---

### Durability Example

```python
# Changes survive process crash
with db.transaction():
    db.command("sql", "INSERT INTO Critical SET data = ?", "important")

# After commit, data is on disk
# Even if process crashes here, data is safe

db.close()

# Reopen database
db = arcadedb.open_database("./mydb")

# Data is still there
result = db.query("sql", "SELECT FROM Critical WHERE data = 'important'")
assert result.has_next()
print("Data survived!")
```

---

## Performance Considerations

### Batch Operations

```python
# Inefficient: Many small transactions
for i in range(1000):
    with db.transaction():
        db.command("sql", "INSERT INTO Item SET value = ?", i)
# 1000 commits = slow

# Efficient: One large transaction
with db.transaction():
    for i in range(1000):
        db.command("sql", "INSERT INTO Item SET value = ?", i)
# 1 commit = fast
```

**Guideline:** Batch related operations in a single transaction for better performance.

---

### Transaction Size Limits

```python
# For very large batches, commit periodically
batch_size = 10000
count = 0

db.begin()
try:
    for i in range(100000):
        db.command("sql", "INSERT INTO BigData SET `index` = ?", i)

        count += 1
        if count >= batch_size:
            db.commit()
            db.begin()
            count = 0

    # Commit remaining
    if count > 0:
        db.commit()

except Exception as e:
    db.rollback()
    raise
```

**Guideline:** Commit every 10K-100K records for very large imports.

---

## Common Patterns

### Read-Modify-Write

```python
with db.transaction():
    # Read
    result = db.query("sql", "SELECT FROM Counter WHERE name = 'page_views'")
    counter = result.next()

    # Modify
    current_value = counter.get("value")
    new_value = current_value + 1

    # Write
    rid = counter.get("@rid")
    db.command("sql", f"UPDATE {rid} SET value = {new_value}")
```

---

### Conditional Create

```python
with db.transaction():
    # Check if exists
    result = db.query("sql", "SELECT FROM User WHERE email = 'alice@example.com'")

    if result.has_next():
        print("User already exists")
    else:
        # Create if not exists
        db.command(
            "sql",
            "INSERT INTO User SET email = ?, name = ?",
            "alice@example.com",
            "Alice",
        )
        print("User created")
```

---

### Optimistic Locking

```python
def update_with_retry(db, rid, new_value, max_retries=3):
    """Update with optimistic locking and retry."""
    for attempt in range(max_retries):
        try:
            with db.transaction():
                # Read current version
                result = db.query("sql", f"SELECT FROM {rid}")
                if not result.has_next():
                    raise ValueError("Record not found")

                record = result.next()

                # Update (ArcadeDB handles version checking)
                db.command("sql", f"UPDATE {rid} SET value = '{new_value}'")

                return True

        except Exception as e:
            if "concurrent" in str(e).lower() and attempt < max_retries - 1:
                # Retry on concurrent modification
                time.sleep(0.1 * (attempt + 1))
                continue
            raise

    return False
```

---

## Best Practices

1. **Use Context Managers**: Prefer `with db.transaction()` over manual `begin()`/`commit()`
2. **Keep Transactions Short**: Long-running transactions can block other operations
3. **Batch Related Operations**: Group related writes in one transaction
4. **Handle Exceptions**: Always handle exceptions to ensure rollback
5. **Avoid Nested Contexts**: Don't nest `db.transaction()` - it's confusing
6. **Don't Hold Transactions**: Don't keep transactions open during I/O or network calls
7. **Commit Regularly for Large Batches**: For imports >100K records, commit periodically

---

## See Also

- [Database API](database.md) - Database operations
- [Getting Started](../index.md) - Basic transaction examples
- [Graph Operations Guide](../guide/graphs.md) - Transactions with graphs
- [Import Workflow Reference](importer.md) - Bulk import with transactions
