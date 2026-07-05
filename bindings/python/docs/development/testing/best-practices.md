# Testing Best Practices

Summary of best practices learned from the ArcadeDB Python test suite.

## Database Lifecycle

### ✅ Use Context Managers

```python
# Good: Automatic cleanup
with arcadedb.create_database("./mydb") as db:
    db.query("sql", "SELECT ...")
# Database automatically closed
```

### ✅ Close When Done

```python
# If not using context manager, explicit close
db = arcadedb.create_database("./mydb")
try:
    # ... work ...
finally:
    db.close()  # Always close to release lock
```

## Transactions

### ✅ Always Use Transactions for Writes

```python
# Good: Wrapped in transaction
with db.transaction():
    person = db.new_document("Person")
    person.set("name", "Alice").save()
    db.command("sql", "UPDATE Person SET age = 30 WHERE name = 'Alice'")
# Auto-commit on success, auto-rollback on exception
```

### ❌ Don't Write Without Transactions

```python
# Bad: No transaction
db.command("sql", "INSERT INTO Person SET name = 'Alice'")  # May fail
```

## Concurrency

### ✅ Use Threads for Parallelism

```python
# Good: Share database instance across threads
db = arcadedb.create_database("./mydb")

def worker():
    result = db.query("sql", "SELECT FROM Data")
    # Process...

threads = [Thread(target=worker) for _ in range(10)]
```

### ✅ Use the Standalone Server for Multi-Process

```bash
# Good: run the official ArcadeDB server for multiple processes
docker run -d -p 2480:2480 -p 2424:2424 \
  -e JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
  arcadedata/arcadedb:latest
# All processes connect over its HTTP API
```

### ❌ Don't Try Concurrent Process Access

```python
# Bad: Two processes, same database
# process1.py
db1 = arcadedb.create_database("./mydb")  # Locks

# process2.py (simultaneously)
db2 = arcadedb.open_database("./mydb")    # ❌ LockException!
```

## Data Import

### ✅ Use SQL Import Deliberately

```python
# SQL import is supported for file-driven loads, but do not default to it for the
# largest Python-side bulk ingest benchmarks in this repo.
db.command(
    "sql",
    "IMPORT DATABASE file:///data/sample.csv WITH documentType = 'Data', commitEvery = 10000",
)
```

### ✅ Define Schema Before Import

```python
# Good: Define schema first for better performance
db.command("sql", "CREATE DOCUMENT TYPE Person")
db.command("sql", "CREATE PROPERTY Person.age INTEGER")
db.command("sql", "CREATE PROPERTY Person.name STRING")
db.command("sql", "CREATE INDEX ON Person (name)")

# Then import if this workflow genuinely fits the use case
db.command(
    "sql",
    "IMPORT DATABASE file:///data/people.csv WITH documentType = 'Person'",
)

# For the largest Python benchmark ingest paths, prefer transactional or async SQL.
```

## Query Handling

### ✅ Iterate Results Efficiently

```python
# Good: Iterate directly
result = db.query("sql", "SELECT FROM Person")
for person in result:
    process(person.get("name"))
```

### ✅ Convert to List When Needed

```python
# Good when you need all results
result = db.query("sql", "SELECT FROM Person")
people = list(result)
print(f"Found {len(people)} people")
```

## Error Handling

### ✅ Catch ArcadeDBError

```python
from arcadedb_embedded.exceptions import ArcadeDBError

try:
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice").save()
except ArcadeDBError as e:
    print(f"Database error: {e}")
    # Handle error
```

### ✅ Transactions Auto-Rollback

```python
# Good: Exception triggers rollback
try:
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice").save()
        raise Exception("Something went wrong")
except Exception:
    pass

# Transaction was automatically rolled back
```

## Testing

### ✅ Clean Up Test Databases

```python
import tempfile
import shutil

# Good: Use temp directory
temp_dir = tempfile.mkdtemp()
try:
    db = arcadedb.create_database(f"{temp_dir}/test_db")
    # ... tests ...
    db.close()
finally:
    shutil.rmtree(temp_dir)
```

### ✅ Use Fixtures for Setup/Teardown

```python
import pytest

@pytest.fixture
def db():
    temp_dir = tempfile.mkdtemp()
    database = arcadedb.create_database(f"{temp_dir}/test_db")
    yield database
    database.close()
    shutil.rmtree(temp_dir)

def test_something(db):
    # db is ready to use
    db.command("sql", "CREATE DOCUMENT TYPE Test")
```

## Performance

### ✅ Batch Operations in Transactions

```python
# Good: One transaction for many operations
with db.transaction():
    for i in range(1000):
        rec = db.new_document("Data")
        rec.set("value", i).save()
```

### ❌ Don't Use Transaction Per Operation

```python
# Bad: 1000 separate transactions
for i in range(1000):
    with db.transaction():
        rec = db.new_document("Data")
        rec.set("value", i).save()
```

## Summary Checklist

- [ ] Use context managers for automatic cleanup
- [ ] Wrap writes in transactions
- [ ] Use threads (not processes) for parallelism
- [ ] Use the standalone ArcadeDB server for multi-process access
- [ ] Pre-create schema for better import performance
- [ ] Batch operations in transactions
- [ ] Clean up test databases
- [ ] Catch ArcadeDBError exceptions
- [ ] Close databases to release locks

## Related Documentation

- [Core Tests](test-core.md)
- [Concurrency Tests](test-concurrency.md)
- [Import Tests](test-importer.md)
- [User Guide](../../guide/core/database.md)
