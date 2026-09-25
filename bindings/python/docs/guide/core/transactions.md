# Transactions

Prefer SQL/OpenCypher for schema and CRUD. When you see `temp_db_path`, substitute your own path if you are not in
the test harness.

> **Embedded note:** For bulk table/document ingest in embedded mode, the repository
> recommendation is `db.insert_many(...)`, which batches rows across the FFI boundary.
> Use explicit chunked transactions when you need tight manual control, but do not
> treat them as the default bulk-ingest recommendation here. The async executor's SQL
> command path (`db.async_executor().command(...)`) is not a bulk-ingest path: before
> 26.10.1, above parallel level 1 it silently discarded records, with no error on the
> per-command callback and a normal return from `wait_completion()`. See
> `ArcadeData/arcadedb#7615`, fixed in #7625: a failed periodic commit is now retried
> and otherwise reported through the error callback.

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
    db.command("sql", "CREATE EDGE TYPE Knows")

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

## Durability: what a commit survives

A commit is written to the write-ahead log (WAL) before it returns, so it survives the Python process or the JVM
crashing. Whether it also survives a power cut or an OS crash depends on whether the WAL is flushed to disk at
commit, which ArcadeDB does **not** do by default:

| `arcadedb.txWalFlush` | at each commit | a process crash | a power cut or OS crash |
|---|---|---|---|
| `0` (default) | no flush | survives | the last commits can be lost |
| `1` | `fdatasync` (the data) | survives | survives |
| `2` | `fsync` (data and metadata) | survives | survives |

PostgreSQL, MySQL/InnoDB, and SQLite all flush at every commit by default. `1` is the same kind of sync that
SQLite's `synchronous=FULL` and PostgreSQL's default use on Linux, and it is what ArcadeDB's own production server
mode picks.

**For data you cannot recreate, set `1` when the JVM starts**, so that it covers every thread and every database:

```python
db = arcadedb.create_database(path, jvm_kwargs={"jvm_args": "-Darcadedb.txWalFlush=1"})
```

A server started with `config={"mode": "production"}` sets it to 1 by itself, along with ArcadeDB's other
production defaults, and for the whole process: every database opened in that Python process afterwards, embedded
ones included, inherits it. See [Server Mode](../server.md).

**`db.set_wal_flush()` changes only the calling thread.** It sets the flush for the transactions that thread commits
and leaves every other thread at the JVM's setting. Measured on 26.10.1-SNAPSHOT: the thread that called
`set_wal_flush("yes_nometadata")` synced every commit (7.5 ms each), and a second thread synced none (0.8 ms each).
Use it for a deliberate per-thread choice, not as a database setting (`ArcadeData/arcadedb#8352`).

**The cost is one disk sync per commit**, about 7 ms on a laptop NVMe drive, so commit in batches: one transaction
per chunk of writes, not one per row (`insert_many`, or the chunked pattern above).

**Bulk imports are the exception:** `db.graph_batch()` and the server's `/api/v1/batch` turn the WAL off by default
for speed. Pass `use_wal=True` (served: `wal=true`) unless you would rather delete the database and re-run the import
after a crash; see [GraphBatch](../../api/graph_batch.md).
