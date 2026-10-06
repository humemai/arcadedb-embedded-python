# Transactions API

The `TransactionContext` class and `Database.transaction()` method provide ACID-compliant transaction management with automatic commit/rollback via Python context managers.

## Overview

ArcadeDB transactions provide:

- **Atomicity**: All changes commit together or none commit
- **Consistency**: Schema validation and constraint enforcement
- **Isolation**: Read committed isolation level
- **Durability**: A committed transaction survives a process crash. With the default
  WAL flush mode (`'no'`) it does not survive a power cut; call
  `db.set_wal_flush('yes_nometadata')` (or `'yes_full'`) for that (see
  [set_wal_flush](database.md#set_wal_flush))

**Key Concepts:**

- **Auto-commit** queries read latest data but don't create transactions
- **Explicit transactions** required for write operations
- **Context managers** automatically handle commit/rollback
- **Rollback on exception** ensures data integrity

## Transaction Scope

It is important to distinguish between operations that require explicit transactions and those that do not:

| Operation Type | Examples | Transaction Requirement |
| :--- | :--- | :--- |
| **Schema Operations** | `create_vertex_type()`, `create_property()`, `create_index()`, `db.command("sql", "DROP INDEX...")` | **Apply immediately; not transactional** (a rollback does not undo them). Not needed for one statement; for many, one `with db.transaction():` or one `sqlscript` writes the schema once |
| **Data Write** | `db.command("sql", "INSERT...")`, `db.command("sql", "UPDATE...")`, `db.command("sql", "DELETE...")`, `db.command("opencypher", "CREATE ...")` | **Required** (Wrap in `with db.transaction():`) |
| **Bulk Operations** | `db.command("sql", "IMPORT DATABASE...")`, `db.import_documents(...)`, `db.graph_batch(...)` | **Auto-transactional / auto-managed** (Built-in transaction management) |
| **Data Read** | `db.query()`, `db.command("sql", "SELECT...")`, `db.lookup_by_rid()` | **Optional**, and better outside one: a filtered scan runs in parallel only outside a transaction ([Queries](../guide/core/queries.md)) |
| **Vector Operations** | `CREATE INDEX ... LSM_VECTOR` | **Applies immediately; not transactional**, like the schema operations above (one index needs no transaction) |

### Key Distinction: `db.query()` vs `db.command()`

- **`db.query()`**: Always used for **read-only queries**. Returns a `ResultSet` with read-only results. **Does NOT require a transaction.**
- **`db.command()`**: Used for **both DDL and DML operations**. For read statements such
    as `SELECT`, it returns a `ResultSet` and can run outside a transaction. For write
    statements such as `INSERT`, `UPDATE`, and `DELETE`, wrap it in
    `with db.transaction():`. DDL such as `CREATE TYPE`, `CREATE PROPERTY`, `CREATE INDEX`,
    `DROP` apply immediately and are not transactional (a rollback does not undo them), and
    bulk commands such as `IMPORT DATABASE` and `MOVE` manage their own transactions.
- **`db.import_documents()`**: Runs the Java importer through the narrow document-import
    wrapper. It manages its own importer/async lifecycle, so you should not wrap it in
    `with db.transaction():`.
- **`db.graph_batch()`**: Creates the engine-backed bulk graph-ingest helper. It manages
    its own flush/commit lifecycle, so you should not wrap it in `with db.transaction():`.

### Best Practice Pattern

```python
# ✅ CORRECT: Queries outside transaction
results = db.query("sql", "SELECT * FROM Person")
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

If a transaction is already active, `begin()` starts a nested transaction (see
[Nested Transactions](#nested-transactions)).

**Raises:**

- `ArcadeDBError`: If the transaction cannot begin (for example, the database is closed)

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

### `Database.run_in_transaction(fn, retries=12, backoff_s=0.005)`

Run a zero-argument callable inside a transaction and return its result. Any exception
rolls the transaction back. On `ConcurrentModificationException` or
`NeedRetryException` the callable is run again, up to `retries` times, sleeping
`backoff_s * attempt` between attempts. A `with db.transaction():` block cannot be
re-entered, so use this for contended writes from several threads.

**Example:**

```python
def add_view():
    db.command("sql", "UPDATE Counter SET value = value + 1 WHERE name = ?", "page_views")

db.run_in_transaction(add_view)
```

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

Roll back the current transaction and discard all changes. With no active
transaction it does nothing and returns `None`.

**Raises:**

- `ArcadeDBError`: If the rollback fails

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

```python
with db.transaction():
    # db.begin() is called on entry

    ...  # your code

    # On normal exit: db.commit() is called
    # On an exception: db.rollback() is called and the exception propagates
```

---

## Nested Transactions

**Important:** `begin()` inside an active transaction starts a **new, independent** transaction on the same thread. The inner transaction commits or rolls back on its own, and the outer one continues after it:

```python
try:
    with db.transaction():
        db.command("sql", "INSERT INTO Outer SET layer = ?", "outer")

        # This DOES create a new transaction
        with db.transaction():
            db.command("sql", "INSERT INTO Inner SET layer = ?", "inner")
        # The inner insert is committed here

        raise RuntimeError("rolls back the outer transaction only")
except RuntimeError:
    pass

# The "inner" record survives; the "outer" record is rolled back
```

**Recommendation:** Avoid nesting `db.transaction()` unless you want the inner block to commit independently of the outer one.

---

## Best Practices

1. **Use Context Managers**: Prefer `with db.transaction()` over manual `begin()`/`commit()`
2. **Keep Transactions Short**: Long-running transactions can block other operations
3. **Batch Related Operations**: Group related writes in one transaction
4. **Handle Exceptions**: Always handle exceptions to ensure rollback
5. **Avoid Nested Contexts**: A nested `db.transaction()` commits independently of the outer one
6. **Don't Hold Transactions**: Don't keep transactions open during I/O or network calls
7. **Commit Regularly for Large Batches**: Commit in chunks for large loads, or use `db.insert_many(...)`

---

## See Also

- [Transactions guide](../guide/core/transactions.md) - Patterns, writes from several threads, and durability
- [Database API](database.md) - Database operations
- [Quick Start](../getting-started/quickstart.md) - Basic transaction examples
- [Graph Operations Guide](../guide/graphs.md) - Transactions with graphs
- [Import Workflow Reference](importer.md) - Bulk import with transactions
