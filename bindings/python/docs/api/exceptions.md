# Exceptions API

The `ArcadeDBError` exception is the base class for all errors raised by the ArcadeDB Python bindings. It wraps underlying Java exceptions and provides Pythonic error handling.

## Overview

Most errors from ArcadeDB operations raise `ArcadeDBError` (there are no subclasses yet). When it is raised from a Java exception, its `str()` ends with `(caused by <Java class>: <message>)` naming the Java root cause, unless that message is already in the text. The engine computes rows lazily, so a statement's error can come while its result set is read rather than from `query()`; every way of reading a result set raises it as `ArcadeDBError` too. Some calls raise other exceptions:

- `ValueError`: invalid arguments, for example `ResultSet.one()` with zero or several rows, an unknown `set_wal_flush()` mode, or `AsyncExecutor.set_commit_every()` with a count below 1
- `AttributeError`: `set()` on an immutable record, such as one returned by a query; call `.modify()` first
- `TimeoutError`: `AsyncExecutor.wait_completion(timeout_ms)` when the timeout expires (at once for `timeout_ms=0` while work is pending)
- `TypeError`: a value that JPype cannot convert, for example a `datetime.time` passed to `set()`
- Java exceptions, not wrapped: `Schema` calls that go directly to Java, such as `exists_type()`, `get_types()`, `get_indexes()`, and `exists_index()`; a wrapper's `save()` outside a transaction (`com.arcadedb.exception.TransactionException: Transaction not begun`; `db.new_vertex()` and `db.new_document()` themselves work outside one); and a vector of the wrong dimension saved to an indexed property (`java.lang.IllegalArgumentException`, raised by `save()`)

**Error Sources:**

- **Schema violations**: Type mismatches, constraint failures, missing properties
- **Transaction errors**: Concurrent modifications, commit failures, rollbacks
- **Query errors**: Syntax errors, invalid queries, type errors
- **Database errors**: File I/O errors, corruption, not found
- **Server errors**: Connection failures, authentication errors, port conflicts
- **Resource errors**: Out of memory, too many open files

## ArcadeDBError Class

```python
class ArcadeDBError(Exception):
    """Base exception for ArcadeDB errors."""

    def __str__(self):
        # The message, followed by "(caused by <Java class>: <message>)" naming
        # the Java root cause when that message is not already in the text
        ...
```

**Inheritance:** `Exception` → `ArcadeDBError`

**Usage:**

!!! note "CRUD style in this page"
    Prefer SQL/OpenCypher for normal application writes. Where this page still shows
    wrapper objects, it is to discuss exception behavior around record-level APIs or
    to keep examples close to the API being documented.

```python
from arcadedb_embedded import ArcadeDBError

try:
    # ArcadeDB operation
    db.query("sql", "INVALID SYNTAX")
except ArcadeDBError as e:
    print(f"Database error: {e}")
```

---

## Common Error Patterns

### Database Not Found

```python
from arcadedb_embedded import ArcadeDBError, open_database

try:
    db = open_database("./nonexistent_db")
except ArcadeDBError as e:
    print(f"Error: {e}")
    # Error: Failed to open database: com.arcadedb.exception.DatabaseNotFoundException:
    # Database '/abs/path/to/nonexistent_db' does not exist
```

**Solution:** Use `database_exists()` to check first, or use `create_database()`.

---

### Query Syntax Error

```python
try:
    result = db.query("sql", "SELCT FROM Person")  # Typo: SELCT
except ArcadeDBError as e:
    print(f"Query error: {e}")
    # Query error: ... syntax error near 'SELCT'
```

**Solution:** Check query syntax, use proper SQL/OpenCypher.

---

### Schema Constraint Violation

```python
# Assuming User.email has UNIQUE constraint
try:
    with db.transaction():
        db.command("sql", "INSERT INTO User SET email = ?", "alice@example.com")
        db.command("sql", "INSERT INTO User SET email = ?", "alice@example.com")

except ArcadeDBError as e:
    print(f"Constraint violation: {e}")
    # Constraint violation: ... duplicate key ... email
```

**Solution:** Check for existing records before insert, handle duplicates gracefully.

---

### Type Mismatch

```python
# Assuming Person.age is INTEGER
try:
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET age = ?", "not a number")

except ArcadeDBError as e:
    print(f"Type error: {e}")
    # Type error: ... cannot convert 'not a number' to INTEGER
```

**Solution:** Ensure data types match schema definitions.

---

### Transaction Error

```python
try:
    # Commit without a transaction (not allowed)
    db.commit()  # Error: Transaction not begun

except ArcadeDBError as e:
    print(f"Transaction error: {e}")
```

**Solution:** Use context managers (`with db.transaction()`) to avoid manual transaction management errors.

---

### Property Not Found

Reading a property that does not exist is not an error: `get()` returns `None`.

```python
person = db.query("sql", "SELECT FROM Person LIMIT 1").first()

# A missing property (or a typo in its name) returns None; nothing is raised
phone = person.get("phone_number")
if phone is None:
    print("phone_number is not set")
```

**Solution:** Use `has_property()` when you need to tell a missing property from one
stored as `null`.

---

### Server Already Running

```python
from arcadedb_embedded import create_server, ArcadeDBError

server = create_server(root_password="password123")
server.start()

try:
    server.start()  # Already started!
except ArcadeDBError as e:
    print(f"Server error: {e}")
    # Server error: Server is already started
finally:
    server.stop()
```

**Solution:** Check `server.is_started()` before calling `start()`.

---

### Port Already in Use

```python
try:
    server = create_server(root_password="password123", config={"http_port": 2480})
    server.start()
except ArcadeDBError as e:
    if "bind" in str(e).lower() or "port" in str(e).lower():
        print("Port 2480 is already in use")
        print("Try a different port or stop conflicting process")
    else:
        print(f"Server error: {e}")
```

**Solution:** Use a different port or stop the process using port 2480.

---

## Error Handling Best Practices

### Specific Error Handling

```python
from arcadedb_embedded import ArcadeDBError

try:
    db = open_database("./mydb")
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")

except ArcadeDBError as e:
    error_msg = str(e).lower()

    if "does not exist" in error_msg:
        print("Database not found - creating new one")
        db = create_database("./mydb")

    elif "syntax" in error_msg:
        print("Query syntax error - check your SQL")

    elif "constraint" in error_msg:
        print("Constraint violation - check your data")

    else:
        print(f"Unknown error: {e}")
        raise
```

---

### Transaction Error Handling

`db.run_in_transaction(fn, retries=12, backoff_s=0.005)` runs `fn` in a transaction,
rolls back on any error, and retries on `ConcurrentModificationException` and
`NeedRetryException` with a linear backoff. Any other error, or a conflict after the
last retry, is raised.

```python
from arcadedb_embedded import ArcadeDBError

def safe_insert(db, record_data):
    """Insert with automatic retry on concurrent modification."""
    assignments = ", ".join(f"{key} = ?" for key in record_data)

    def write():
        db.command(
            "sql",
            f"INSERT INTO Record SET {assignments}",
            *record_data.values(),
        )

    db.run_in_transaction(write)

# Usage
try:
    safe_insert(db, {"name": "Alice", "age": 30})
    print("Insert successful")
except ArcadeDBError as e:
    print(f"Insert failed: {e}")
```

---

## Debugging Tips

### Check Java Exception

```python
from arcadedb_embedded import ArcadeDBError

try:
    # Operation that might fail
    db.query("sql", "SELECT FROM NonExistentType")
except ArcadeDBError as e:
    print(f"Python error: {e}")

    # The __cause__ attribute contains the original Java exception
    if e.__cause__:
        print(f"Java cause: {e.__cause__}")
        print(f"Java type: {type(e.__cause__).__name__}")
```

---

## See Also

- [Database API](database.md) - Database operations that may raise errors
- [Transactions API](transactions.md) - Transaction error handling
- [Server API](server.md) - Server-related errors
- [Troubleshooting Guide](../development/troubleshooting.md) - Common issues and solutions
