# Testing Best Practices

Usage patterns the test suite exercises, and how to write a test for it.

## Database Lifecycle

### ✅ Use Context Managers

```python
# Good: Automatic cleanup
with arcadedb.create_database("./mydb") as db:
    db.query("sql", "SELECT ...")
# Database automatically closed
```

```python
# Also good for servers
with arcadedb.create_server("./databases", root_password="change-me") as server:
    # The context manager starts the server; do not call start() again
    # "mydb" will be created at ./databases/databases/mydb
    db = server.create_database("mydb")
    # ... work ...
# Server automatically stopped
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

### ✅ Use Server Mode for Multi-Process

```python
# Good: Server mode for multiple processes
server = arcadedb.create_server(root_path="./databases", root_password="change-me")
server.start()

# Python process: embedded access
db = server.get_database("mydb")

# Other processes: HTTP API
# http://localhost:2480/api/v1/query/mydb
```

### ❌ Don't Try Concurrent Process Access

```python
# Bad: Two processes, same database
# process1.py
db1 = arcadedb.create_database("./mydb")  # Locks

# process2.py (simultaneously)
db2 = arcadedb.open_database("./mydb")    # ❌ ArcadeDBError: ... is locked by another process
```

## Server Patterns

### ✅ Prefer Pattern 2 (Server First)

```python
# Recommended: Start server first
server = arcadedb.create_server("./databases", root_password="change-me")
server.start()
# "mydb" will be created at ./databases/databases/mydb
db = server.create_database("mydb")

# Use embedded access (fast!)
# HTTP also available for other processes
```

### ⚠️ Pattern 1 Requires close()

```python
# If using Pattern 1, MUST close
db = arcadedb.create_database("./mydb")
# ... populate ...
db.close()  # ⚠️ Critical!

# Then start server
server = arcadedb.create_server(...)
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

# For the largest Python benchmark ingest paths, prefer insert_many() for documents
# and GraphBatch for graphs.
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

## Writing a Test for This Suite

1. **Use the shared fixtures** in `tests/conftest.py`: `temp_db_path` (a fresh database
   path), `temp_db` (an open database, closed and deleted afterwards), `temp_server_root`,
   and `temp_dir_factory`, or pytest's own `tmp_path`. Server tests use `TEST_PASSWORD` as
   the root password.
2. **A teardown warns; it never swallows.** A teardown that hides its own failure hides the
   bug with it. `temp_db` shows the pattern: it closes the database if it is still open and
   turns a failed close into a warning.
3. **Do not skip on what the wheel ships.** A test for the server stack, OpenCypher, or any
   other bundled feature runs and fails when the feature is missing: a guard that skips
   cannot notice the feature going missing (the server JARs left the wheel in 26.7.2 and
   the guarded tests skipped into a green suite). Skip only for an optional Python package,
   through `pytest.importorskip` without a custom reason, or for a platform that cannot run
   the test; CI fails every other skip (`scripts/check_test_skips.py`). A server test carries
   `@pytest.mark.server`.
4. **One JVM serves the whole session.** A `start_jvm()` call with a different configuration
   raises "already started", and engine-wide settings carry from one test to the next, so
   run the full suite after adding a test. Anything that needs its own JVM, a crash, a lock
   held by another process, or an isolated `sys.path` runs in a subprocess.
5. **An optional dependency** goes through `pytest.importorskip("module")` with its default
   reason, so that CI fails when the module is missing. Add the module to the `test` extra
   in `bindings/python/pyproject.toml`, to the install step in
   `.github/workflows/test-python-bindings.yml`, and to the repo-root `pyproject.toml`.
6. **Hang diagnostics are built in.** A test still running after
   `ARCADEDB_TEST_JAVA_DUMP_AFTER_S` seconds (540 by default) prints every Java thread's
   stack, and `faulthandler_timeout` dumps the Python threads at 600 s. On Windows, run with
   `--capture=sys`. `ARCADEDB_PYTEST_FORCE_EXIT=1` ends the session with `os._exit(0)`
   instead of a JVM shutdown, for debugging a hang at exit.
7. **Bandit scans `tests/`** at low severity and low confidence. Put `# nosec B608` on the
   flagged line of an f-string SQL statement, as the existing tests do.

```python
import pytest

import arcadedb_embedded as arcadedb
from tests.conftest import TEST_PASSWORD


def test_insert_is_visible(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE Note")
    with temp_db.transaction():
        temp_db.command("sql", "INSERT INTO Note SET k = 1")
    assert temp_db.query("sql", "SELECT k FROM Note").to_list() == [{"k": 1}]


@pytest.mark.server
def test_server_starts(temp_server_root):
    with arcadedb.create_server(temp_server_root, root_password=TEST_PASSWORD) as server:
        assert server.is_started()
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

### ✅ Server-Managed Embedded = Fast

```python
# Fast: No HTTP overhead, direct JVM call
server = arcadedb.create_server("./databases", root_password="change-me")
server.start()
# "mydb" will be created at ./databases/databases/mydb
db = server.create_database("mydb")

# A direct JVM call, like standalone embedded access (not HTTP)
result = db.query("sql", "SELECT FROM Data")
```

## Summary Checklist

- [ ] Use context managers for automatic cleanup
- [ ] Wrap writes in transactions
- [ ] Use threads (not processes) for parallelism
- [ ] Use server mode for multi-process access
- [ ] Prefer Pattern 2 (server first) for new projects
- [ ] Pre-create schema for better import performance
- [ ] Batch operations in transactions
- [ ] Clean up test databases
- [ ] Catch ArcadeDBError exceptions
- [ ] Close databases to release locks

## Related Documentation

- [Core Tests](test-core.md)
- [Concurrency Tests](test-concurrency.md)
- [Server Patterns](test-server-patterns.md)
- [Import Tests](test-importer.md)
- [User Guide](../../guide/core/database.md)
