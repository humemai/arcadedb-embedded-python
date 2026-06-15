# AsyncExecutor Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_async_executor.py){ .md-button }

The file contains **8 tests** covering asynchronous SQL command/query execution and executor configuration.

## Overview

AsyncExecutor tests cover:

- ✅ **Async SQL commands** – `async_exec.command("sql", ...)` with positional and named args
- ✅ **Async SQL queries** – `async_exec.query("sql", ...)` with a per-row callback
- ✅ **Auto-commit cadence** – `set_commit_every()` batching
- ✅ **Parallel execution** – `set_parallel_level()` worker threads
- ✅ **Configuration getters** – `get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `get_transaction_sync()`, `get_thread_count()`
- ✅ **Status checks** – `is_pending()` / `is_processing()` and `is_closed()`
- ✅ **Callbacks** – per-operation `error_callback` plus global `on_ok()` / `on_error()`
- ✅ **Lifecycle** – idempotent `close()` and owned-executor shutdown on `db.close()`

## Test Coverage

### Command and Query Tests

#### test_async_executor_sql_command_insert

Configures `set_parallel_level(4).set_commit_every(1)`, issues 200 async `INSERT INTO Item` commands (positional `args`, a no-op `callback`), then `wait_completion()` and asserts the inserted count is greater than zero.

#### test_async_executor_query_callback_collects_rows

Inserts 20 `Person` rows synchronously, then runs an async `SELECT id FROM Person ORDER BY id` via `async_exec.query(...)` with a per-row callback that appends each `id`; asserts the collected ids equal `range(20)`.

### Lifecycle Tests

#### test_database_close_closes_owned_async_executor

Runs one async command, then closes the owning database and asserts the executor's `is_closed()` returns `True` (the database shuts down its owned executor).

#### test_async_executor_close_is_idempotent

Calls `close()` twice and asserts `is_closed()` is `True` with no error.

### Status Tracking Tests

#### test_async_executor_pending_and_processing_flags

Uses `set_commit_every(100)`, asserts `is_pending()` is initially `False`, queues 1000 commands, observes `is_processing()` during the in-flight phase, then after `wait_completion()` asserts `is_pending()` is `False`.

#### test_async_executor_getters_and_sync_modes

Sets `set_parallel_level(3)`, `set_commit_every(123)`, `set_back_pressure(40)`, `set_transaction_use_wal(False)`, `set_transaction_sync("yes_nometadata")`, then asserts the corresponding getters (`get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `is_transaction_use_wal()`, `get_transaction_sync()`, `get_thread_count()`).

### Callback Tests

#### test_async_executor_command_error_callback

Issues an async command against a missing type with a per-operation `error_callback`; asserts the error callback was invoked.

#### test_async_executor_global_callbacks

Registers global `on_ok(...)` and `on_error(...)` handlers, issues 5 successful inserts, and asserts the success callback fired at least once.

## Test Pattern (mirrors `test_async_executor_sql_command_insert`)

```python
db = arcadedb.create_database(str(db_path))
db.command("sql", "CREATE DOCUMENT TYPE Item")

async_exec = db.async_executor().set_parallel_level(4).set_commit_every(1)
for i in range(200):
    async_exec.command(
        "sql",
        "INSERT INTO Item SET id = ?, name = ?",
        callback=lambda _r: None,
        args=(i, f"Item{i}"),
    )

async_exec.wait_completion()
async_exec.close()
assert db.query("sql", "SELECT count(*) as c FROM Item").first().get("c") > 0
```

## Key Takeaways

1. Call `wait_completion()` before `close()` to flush worker threads.
2. Tune `set_commit_every()` and `set_parallel_level()` per workload (tests use commit-every 1/100 and 2–4 workers).
3. Use per-operation `error_callback` or global `on_ok()` / `on_error()` handlers to observe outcomes.
4. `is_pending()` / `is_processing()` track queue state; `is_pending()` is `False` after completion.
5. Closing the owning database also closes its owned async executor; `close()` is idempotent.

## See Also

- **[AsyncExecutor API](../../api/async_executor.md)**
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)**
- **[Testing Overview](overview.md)**
