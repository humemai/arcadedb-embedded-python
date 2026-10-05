# Transactions

Prefer SQL/OpenCypher for schema and CRUD. When you see `temp_db_path`, substitute your own path if you are not in
the test harness.

> **Embedded note:** For bulk table/document ingest in embedded mode, the repository
> recommendation is `db.insert_many(...)`, which batches rows across the FFI boundary.
> Use explicit chunked transactions when you need tight manual control, but do not
> treat them as the default bulk-ingest recommendation here. Before 26.10.1,
> `async_executor().command(...)` could silently drop records above parallel level 1
> (`ArcadeData/arcadedb#7615`, fixed in #7625); see
> [Bulk Ingest Recommendation](../import.md#bulk-ingest-recommendation).

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

## Writes from several threads

Threads that write at the same time can conflict: the transaction that loses raises
`ConcurrentModificationException` at commit, and a `with db.transaction():` block cannot
run again. `db.run_in_transaction(fn)` runs `fn` in a transaction and, on a
concurrent-modification conflict, rolls back and runs it again (12 retries with a linear
backoff by default). Any other error rolls back and propagates. See
[`run_in_transaction`](../../api/database.md#run_in_transaction).

```python
from threading import Thread


def worker(thread_id):
    for i in range(20):
        db.run_in_transaction(
            lambda: db.command("sql", "INSERT INTO Log SET thread = ?, i = ?", thread_id, i)
        )


threads = [Thread(target=worker, args=(t,)) for t in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

## Schema statements apply immediately

A schema statement (create or drop a type, property, or index) needs no transaction, and it is
not transactional: it takes effect at once, and a rollback does not undo it. To create many
types, put the statements in one transaction or one `sqlscript`: the schema is then written to
disk once, when the transaction ends, instead of once per statement, which on disk is the
difference between a few milliseconds per type and a durable write per statement
(ArcadeData/arcadedb#8635). A crash before such a transaction ends leaves the new files unnamed
in the schema; the database still opens, and the same statements can be run again.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database(temp_db_path) as db:
    # One schema statement: no transaction needed
    db.command("sql", "CREATE DOCUMENT TYPE TestDoc")

    # Many schema statements: one transaction, one schema write when it ends
    with db.transaction():
        for i in range(10):
            db.command("sql", f"CREATE DOCUMENT TYPE Part{i}")
            db.command("sql", f"CREATE PROPERTY Part{i}.id LONG")
            db.command("sql", f"CREATE INDEX ON Part{i} (id) UNIQUE_HASH")
    assert all(db.schema.exists_type(f"Part{i}") for i in range(10))

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

**`db.set_wal_flush()` sets it for one database, on every thread** (26.10.1 and later). Before that release it
changed only the calling thread: measured on an earlier 26.10.1-SNAPSHOT, the thread that called
`set_wal_flush("yes_nometadata")` synced every commit and a second thread synced none (`ArcadeData/arcadedb#8352`,
fixed in #8397; now both threads sync, about 9.8 ms per commit each). It still covers only the database it is called
on, so for a process-wide default the JVM flag above remains the simplest choice.

**The cost is one disk sync per commit**, 7 to 10 ms on a laptop NVMe drive, so commit in batches: one transaction
per chunk of writes, not one per row (`insert_many`, or the chunked pattern above).

**Bulk imports are the exception:** `db.graph_batch()` and the server's `/api/v1/batch` turn the WAL off by default
for speed. Pass `use_wal=True` (served: `wal=true`) unless you would rather delete the database and re-run the import
after a crash; see [GraphBatch](../../api/graph_batch.md).

**The async writers ignore `txWalFlush`.** `insert_many(..., parallel=True)`, and anything else that goes through
`db.async_executor()`, commits with the executor's own flush setting, which defaults to no flush whatever
`arcadedb.txWalFlush` or `set_wal_flush()` says (`ArcadeData/arcadedb#8478`). For a durable parallel load, set it on
the executor before the load:

```python
db.async_executor().set_transaction_sync("yes_nometadata")   # or "yes_full", to match txWalFlush=2
db.insert_many("Order", rows, parallel=True)
```
