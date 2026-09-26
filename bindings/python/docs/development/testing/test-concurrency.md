# Concurrency Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_concurrency.py){ .md-button }

There are 5 tests covering file locking, thread safety, sequential access, the multi-process limitation, and a mixed OLTP-style workload.

## Key Insight

- ❌ Multiple **processes** cannot open the same database (the file lock prevents it)
- ✅ Multiple **threads** can share one `Database` (thread-safe within a process)
- ✅ For multi-process access, one process runs a server and the others use HTTP

## Test Cases

### 1) file lock mechanism

Opens a database and asserts `database.lck` exists while it is open. After `close()` it asserts the file is gone (a clean close deletes it) and opens the same path from a second Python process, asserting that succeeds, so the lock was released and not merely the handle closed.

### 2) thread safety

Creates 20 Person records and runs 4 threads that query disjoint id ranges (0-4, 5-9, 10-14, 15-19) through one shared `Database` at once, with bound parameters. Asserts each thread got exactly its own five ids.

### 3) sequential access

Create and insert, close, reopen and query, close, reopen and insert again. Asserts one message after the first reopen and both messages, by text, after the second.

### 4) concurrent access limitation

Holds the database open and tries to open it from a second Python process (its own JVM). Asserts the child is refused with the engine's reason, "is locked by another process". The parent closes its handle even if the check fails.

### 5) OLTP mixed workload (multi-thread)

Seeds 1,000 accounts, then 4 threads run 400 operations each, 90% point reads and 10% balance updates, retrying an update on `ConcurrentModificationException`. Prints throughput and latency. Asserts every operation completed and that the balances sum to the seed plus exactly the deltas that committed, so no committed update was lost.

## What the lock looks like from a second process

This is what test 4 does:

```python
import subprocess
import sys

import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./mydb")  # this process now holds the lock

child = """
import arcadedb_embedded as arcadedb
try:
    arcadedb.open_database("./mydb").close()
    print("OPENED")
except Exception as exc:
    print("LOCKED:", exc)
"""
out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
print(out.stdout)  # LOCKED: ... is locked by another process (path=...)

db.close()
```

The child sees an `ArcadeDBError`. From 26.10.1 its message ends with the engine's root cause, `(caused by com.arcadedb.utility.LockException: Database 'mydb' is locked by another process (path=...))`; earlier wheels printed only the outer "Error on creating new database instance".

## Threads: share one instance, retry conflicting writes

Share a single `Database` across threads rather than opening one per thread. Reads need no coordination. Two threads that update the same record can conflict: the losing commit raises `ArcadeDBError` with `ConcurrentModificationException` in the message, and the usual answer is to retry the transaction, as test 5 does:

```python
import time

from arcadedb_embedded.exceptions import ArcadeDBError

def add_to_balance(db, account_id, delta, retries=12):
    for attempt in range(retries):
        try:
            with db.transaction():
                db.command(
                    "sql",
                    "UPDATE Account SET balance = balance + ? WHERE account_id = ?",
                    delta,
                    account_id,
                )
            return
        except ArcadeDBError as exc:
            if "ConcurrentModificationException" not in str(exc):
                raise
            time.sleep(0.005 * (attempt + 1))
    raise RuntimeError("update kept conflicting")
```

## Summary Table

| Scenario | Supported? | Notes |
|----------|------------|-------|
| Multiple threads, same process | ✅ Yes | Share one database instance; retry conflicting writes |
| Sequential: open → close → reopen | ✅ Yes | Close to release the lock |
| Multiple processes, embedded mode | ❌ No | The file lock refuses the second process |
| Multiple processes via bundled `create_server()` | ✅ Yes | The owner keeps embedded access; others use HTTP |
| Multiple processes via standalone ArcadeDB server | ✅ Yes | All processes use its HTTP API |

## Running These Tests

```bash
uv run python -m pytest bindings/python/tests/test_concurrency.py -v

# One test, with its printed output
uv run python -m pytest bindings/python/tests/test_concurrency.py::test_thread_safety -v -s
```

## Troubleshooting

### "is locked by another process"

Another process has the database open. Close it there, or have that process run a server and reach the database over HTTP.

The lock is an operating-system lock on `database.lck` held by the process, so it goes away when the process exits, including after a crash. A clean close also deletes the file. A `database.lck` left on disk therefore means the last process did not close cleanly: it blocks nothing, and the next open sees it and replays the write-ahead log. Do not delete it by hand, because that skips the recovery.

## Related Documentation

- [Access Methods](../../api-access-methods.md) - Embedded vs standalone server
- [Database API](../../api/database.md) - Database class reference
