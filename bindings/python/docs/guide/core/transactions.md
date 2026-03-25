# Transactions

Prefer SQL/OpenCypher for schema and CRUD. When you see `temp_db_path`, substitute your own path if you are not in
the test harness.

> **Embedded note:** For bulk table/document ingest in embedded mode, the repository
> recommendation is async SQL insert with a single async worker. Use explicit chunked
> transactions when you need tight manual control, but do not treat them as the default
> bulk-ingest recommendation here.

## Basic commit and rollback

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE DOCUMENT TYPE TransactionTest")

    # Commit on success
    with db.transaction():
        db.command("sql", "INSERT INTO TransactionTest SET id = 1")
        db.command("sql", "INSERT INTO TransactionTest SET id = 2")

    result = db.query("sql", "SELECT count(*) as count FROM TransactionTest")
    count = list(result)[0].get("count")
    assert count == 2

    # Rollback on exception
    try:
        with db.transaction():
            db.command("sql", "INSERT INTO TransactionTest SET id = 3")
            raise Exception("Intentional error")
    except Exception:
        pass

    result = db.query("sql", "SELECT count(*) as count FROM TransactionTest")
    count = list(result)[0].get("count")
    assert count == 2
```

## Schema is auto-transactional

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    # Schema changes do not need an explicit transaction
    db.command("sql", "CREATE DOCUMENT TYPE TestDoc")

    # Data writes do
    with db.transaction():
        db.command("sql", "INSERT INTO TestDoc SET name = 'test', value = 42")

    result = db.query("sql", "SELECT FROM TestDoc WHERE name = 'test'")
    record = list(result)[0]
    assert record.get("value") == 42
```

## SQL inserts in a transaction

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE DOCUMENT TYPE Task")

    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)
        db.command("sql", "INSERT INTO Task SET title = ?, priority = ?", "Test Task", 5)
```

## SQL edge creation with properties

```python
with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")

    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice'")
        db.command("sql", "INSERT INTO Person SET name = 'Bob'")
        db.command(
            "sql",
            """
            CREATE EDGE Knows
            FROM (SELECT FROM Person WHERE name = 'Alice')
            TO (SELECT FROM Person WHERE name = 'Bob')
            SET since = '2020', strength = 0.8
            """,
        )
```

## Update after querying (SQL-first)

```python
with arcadedb.create_database(temp_db_path) as db:
    db.command("sql", "CREATE VERTEX TYPE City")

    with db.transaction():
        db.command(
            "sql",
            "INSERT INTO City SET name = 'New York', population = 8000000",
        )

    with db.transaction():
        db.command(
            "sql",
            "UPDATE City SET country = 'USA' WHERE name = 'New York'",
        )

    updated = list(db.query("sql", "SELECT FROM City WHERE name = 'New York'"))[0]
    assert updated.get("country") == "USA"
```

## Chunked bulk inserts with manual commit/renew

```python
import arcadedb_embedded as arcadedb

BATCH_SIZE = 1000
with db.transaction():
    total_inserted = 0
    for i, doc in enumerate(documents):
        db.command(
            "sql",
            "INSERT INTO Article SET id = ?, title = ?, content = ?, category = ?, embedding = ?",
            doc["id"],
            doc["title"],
            doc["content"],
            doc["category"],
            arcadedb.to_java_float_array(doc["embedding"]),
        )

        total_inserted += 1
        if total_inserted % BATCH_SIZE == 0:
            db.commit()
            db.begin()
```

## SQL updates inside transactions

```python
with db.transaction():
    db.command(
        "sql",
        """UPDATE Task SET
           completed = true,
           cost = 127.50
           WHERE title = 'Buy groceries'""",
    )

with db.transaction():
    db.command(
        "sql",
        """UPDATE Task SET
           cost = NULL,
           estimated_hours = NULL
           WHERE title = 'Call dentist'""",
    )
```
