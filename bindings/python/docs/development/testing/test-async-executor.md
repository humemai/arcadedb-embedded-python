# AsyncExecutor Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_async_executor.py){ .md-button }

The file contains **11 tests** (one of them skipped) covering asynchronous SQL command/query execution and executor configuration.

## Overview

AsyncExecutor tests cover:

- ✅ **Async SQL commands** – `async_exec.command("sql", ...)` with positional and named args
- ✅ **Record loss above parallel level 1** – exact submitted-versus-stored counts, including a skipped test that starts passing when the engine is fixed
- ✅ **Async SQL queries** – `async_exec.query("sql", ...)` with a per-row callback
- ✅ **Auto-commit cadence** – `set_commit_every()` batching
- ✅ **Parallel execution** – `set_parallel_level()` worker threads
- ✅ **Configuration getters** – `get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `get_transaction_sync()`, `get_thread_count()`
- ✅ **Status checks** – `is_pending()` / `is_processing()` and `is_closed()`
- ✅ **Callbacks** – per-operation `error_callback` plus global `on_ok()` / `on_error()`
- ✅ **Lifecycle** – idempotent `close()` and owned-executor shutdown on `db.close()`

!!! warning "Async SQL commands silently lose records above parallel level 1"

    `async_exec.command(...)` discards records once the parallel level is above 1.
    Observed on arcadedb-engine 26.9.1 and 26.6.1, measured 2026-09-15. How much is lost
    varies by run and by workload shape: 9,742 single-record `INSERT` commands submitted
    at parallel level 4 stored 2,436, 5,742, and 7,742 rows across runs. No error
    reaches the per-command callback, nothing is logged, and `wait_completion()`
    returns normally. Only the
    executor-wide `on_error` handler sees anything, one `ConcurrentModificationException`
    per rolled-back batch. At parallel level 1 nothing is lost. Filed upstream as
    `ArcadeData/arcadedb#7615`.

    Every write test in this file therefore runs at parallel level 1, apart from the one
    test whose subject is the loss itself. For bulk writes use `Database.insert_many`
    or `Database.graph_batch`, both covered in
    [Bulk Insert Tests](test-bulk-insert.md).

## Test Coverage

### Command and Query Tests

#### test_async_executor_sql_command_insert_is_exact_at_parallel_one

Configures `set_parallel_level(1).set_commit_every(1)`, issues 200 async `INSERT INTO Item` commands (positional `args`, a no-op `callback`), then `wait_completion()` and asserts the stored count is exactly 200.

Until 2026-09-15 this test ran at parallel level 4 and asserted `count > 0`. That is the assertion shape that let #7615 through: at level 4 the executor stores a fraction of what it is given, and `count > 0` still passes.

#### test_async_executor_bulk_command_is_exact_at_parallel_one

Submits `LOSS_REPRO_ROWS` (9,742) single-record `INSERT INTO Bulk` commands at `set_parallel_level(1).set_commit_every(1_000)` with an `on_error` collector attached, then asserts the stored count equals 9,742 and that the error list is empty. 9,742 is the size from the original report, the run in which only 2,436 of them survived at parallel level 4.

#### test_async_executor_bulk_command_is_exact_at_parallel_four

The same 9,742-row load at `set_parallel_level(4)`, asserting the same exact count. Marked `@pytest.mark.skip` with the issue number, so it is a statement of the behavior the engine should have rather than an assertion of the behavior it has, and it starts passing when upstream fixes #7615.

#### test_async_executor_query_callback_collects_rows

Inserts 20 `Person` rows synchronously, then runs an async `SELECT id FROM Person ORDER BY id` via `async_exec.query(...)` with a per-row callback that appends each `id`; asserts the collected ids equal `range(20)`.

### Lifecycle Tests

#### test_database_close_closes_owned_async_executor

Runs one async command, then closes the owning database and asserts the executor's `is_closed()` returns `True` (the database shuts down its owned executor).

#### test_async_executor_close_is_idempotent

Calls `close()` twice and asserts `is_closed()` is `True` with no error.

### Status Tracking Tests

#### test_async_executor_pending_and_processing_flags

Uses `set_parallel_level(1).set_commit_every(100)`, asserts `is_pending()` is initially `False`, queues 1000 commands, observes `is_processing()` during the in-flight phase, then after `wait_completion()` asserts `is_pending()` is `False`. The parallel level is pinned to 1 so the queue-state assertions are not mixed with discarded submissions.

#### test_async_executor_is_pending_true_while_queued

Queues work and asserts `is_pending()` answers `True` while it is still queued, without blocking (#7107). It used to call `waitCompletion(0)`, which the engine clamps to an infinite wait, so it blocked until the queue drained and then answered `False` - never `True`, no matter how much work was outstanding.

#### test_async_executor_getters_and_sync_modes

Sets `set_parallel_level(3)`, `set_commit_every(123)`, `set_back_pressure(40)`, `set_transaction_use_wal(False)`, `set_transaction_sync("yes_nometadata")`, then asserts the corresponding getters (`get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `is_transaction_use_wal()`, `get_transaction_sync()`, `get_thread_count()`).

### Callback Tests

#### test_async_executor_command_error_callback

Issues an async command against a missing type with a per-operation `error_callback`; asserts the error callback was invoked.

#### test_async_executor_global_callbacks

Registers global `on_ok(...)` and `on_error(...)` handlers, issues 5 successful inserts, and asserts the success callback fired at least once.

## Test Pattern (mirrors `test_async_executor_sql_command_insert_is_exact_at_parallel_one`)

```python
db = arcadedb.create_database(str(db_path))
db.command("sql", "CREATE DOCUMENT TYPE Item")

async_exec = db.async_executor().set_parallel_level(1).set_commit_every(1)
for i in range(200):
    async_exec.command(
        "sql",
        "INSERT INTO Item SET id = ?, name = ?",
        callback=lambda _r: None,
        args=(i, f"Item{i}"),
    )

async_exec.wait_completion()
async_exec.close()
count = db.query("sql", "SELECT count(*) as c FROM Item").first().get("c")
assert int(count) == 200
```

Two things carry the test: the parallel level is 1, and the assertion is an equality against the number of commands submitted.

## Key Takeaways

1. Call `wait_completion()` before `close()` to flush worker threads.
2. Keep `set_parallel_level()` at 1 whenever the executor runs SQL commands that write; above 1 the submissions are partly discarded (#7615). Levels above 1 are safe for `create_record`, `append_samples`, `Database.insert_many`, and `Database.graph_batch`.
3. Assert an exact count against what was submitted. A `count > 0` assertion passes on a load that lost three quarters of its rows.
4. Use per-operation `error_callback` or global `on_ok()` / `on_error()` handlers to observe outcomes. The per-command callback reports no error when records are discarded; only the executor-wide `on_error` handler does.
5. `is_pending()` / `is_processing()` track queue state; `is_pending()` is `False` after completion. Both are non-blocking polls of the engine's `isProcessing()`: `waitCompletion(0)` is not a poll, the engine reads a zero timeout as "wait forever" (#7107).
6. Closing the owning database also closes its owned async executor; `close()` is idempotent.

## See Also

- **[AsyncExecutor API](../../api/async_executor.md)**
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)**
- **[Testing Overview](overview.md)**
