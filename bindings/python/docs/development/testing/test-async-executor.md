# AsyncExecutor Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_async_executor.py){ .md-button }

The file covers asynchronous SQL command/query execution and executor configuration. There are 13 tests.

## Overview

AsyncExecutor tests cover:

- ✅ **Async SQL commands** – `async_exec.command("sql", ...)` with positional and named args
- ✅ **Record loss above parallel level 1** – exact submitted-versus-stored counts, including the regression test for the parallel-level-4 loss fixed in 26.10.1
- ✅ **Async SQL queries** – `async_exec.query("sql", ...)` with a per-row callback
- ✅ **Auto-commit cadence** – `set_commit_every()` batching
- ✅ **Parallel execution** – `set_parallel_level()` worker threads
- ✅ **Configuration getters** – `get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `get_transaction_sync()`, `get_thread_count()`
- ✅ **Status checks** – `is_pending()` / `is_processing()` and `is_closed()`
- ✅ **Callbacks** – per-operation `error_callback` plus global `on_ok()` / `on_error()`
- ✅ **Lifecycle** – idempotent `close()` and owned-executor shutdown on `db.close()`

!!! warning "Async SQL commands silently lost records above parallel level 1 before 26.10.1"

    `async_exec.command(...)` discarded records once the parallel level was above 1,
    before 26.10.1 (`ArcadeData/arcadedb#7615`, fixed in #7625: a failed periodic commit
    is now retried and otherwise reported through the error callback).
    Observed on arcadedb-engine 26.9.1 and 26.6.1, measured 2026-09-15. How much was lost
    varied by run and by workload shape: 9,742 single-record `INSERT` commands submitted
    at parallel level 4 stored 2,436, 5,742, and 7,742 rows across runs. No error
    reached the per-command callback, nothing was logged, and `wait_completion()`
    returned normally. Only the
    executor-wide `on_error` handler saw anything, one `ConcurrentModificationException`
    per rolled-back batch. At parallel level 1 nothing was lost. Filed upstream as
    `ArcadeData/arcadedb#7615`.

    The count tests below therefore assert an exact stored count at parallel level 1,
    and one of them at level 4, the level that lost records. The lifecycle and callback
    tests (`test_database_close_closes_owned_async_executor`,
    `test_async_executor_command_error_callback`, and
    `test_async_executor_global_callbacks`) write at the default level (available
    cores minus 1) and do not count rows. For bulk writes use `Database.insert_many`
    or `Database.graph_batch`, both covered in
    [Bulk Insert Tests](test-bulk-insert.md).

## Test Coverage

### Command and Query Tests

#### test_async_executor_sql_command_insert_is_exact_at_parallel_one

Configures `set_parallel_level(1).set_commit_every(1)`, issues 200 async `INSERT INTO Item` commands (positional `args`, a no-op `callback`), then `wait_completion()` and asserts the stored count is exactly 200.

Until 2026-09-15 this test ran at parallel level 4 and asserted `count > 0`. That is the assertion shape that let #7615 through: at level 4 the executor stored a fraction of what it was given, and `count > 0` still passed.

#### test_async_executor_bulk_command_is_exact_at_parallel_one

Submits `LOSS_REPRO_ROWS` (9,742) single-record `INSERT INTO Bulk` commands at `set_parallel_level(1).set_commit_every(1_000)` with an `on_error` collector attached, then asserts the stored count equals 9,742 and that the error list is empty. 9,742 is the size from the original report, the run in which only 2,436 of them survived at parallel level 4.

#### test_async_executor_bulk_command_is_exact_at_parallel_four

The same 9,742-row load at `set_parallel_level(4)` with an `on_error` collector attached, asserting the same exact count and no error. It was marked `@pytest.mark.skip` with the issue number until the fix (#7625, 26.10.1) landed, and it fails on 26.9.1 with 2,436 to 7,742 of 9,742 stored, so it is the regression test for #7615.

#### test_async_executor_query_callback_collects_rows

Inserts 20 `Person` rows synchronously, then runs an async `SELECT id FROM Person ORDER BY id` via `async_exec.query(...)` with a per-row callback that appends each `id`; asserts the collected ids equal `range(20)`.

### Lifecycle Tests

#### test_database_close_closes_owned_async_executor

Runs one async command, then closes the owning database and asserts the executor's `is_closed()` returns `True` (the database shuts down its owned executor).

#### test_async_executor_close_is_idempotent

Calls `close()` twice and asserts `is_closed()` is `True` with no error.

### Status Tracking Tests

#### test_async_executor_pending_and_processing_flags

Asserts `is_pending()` and `is_processing()` are `False` on a fresh executor, then submits one `INSERT` whose result callback holds the command until the test releases it: while it is held, both must be `True`. After release and `wait_completion()` both are `False` and the row is stored. Until 2026-09-29 this test polled with `waitCompletion(0)`, which the engine treats as an unbounded wait, and never asserted what it polled for.

#### test_async_executor_is_pending_true_while_queued

Queues work and asserts `is_pending()` answers `True` while it is still queued, without blocking (#7107). It used to call `waitCompletion(0)`, which the engine clamps to an infinite wait, so it blocked until the queue drained and then answered `False` - never `True`, no matter how much work was outstanding.

#### test_async_executor_getters_and_sync_modes

Sets `set_parallel_level(3)`, `set_commit_every(123)`, `set_back_pressure(40)`, `set_transaction_use_wal(False)`, `set_transaction_sync("yes_nometadata")`, then asserts the corresponding getters (`get_parallel_level()`, `get_commit_every()`, `get_back_pressure()`, `is_transaction_use_wal()`, `get_transaction_sync()`, `get_thread_count()`).

### Callback Tests

#### test_async_executor_parallel_level_has_no_upper_cap

`set_parallel_level(17)` is accepted and read back, and `set_parallel_level(0)` raises `ValueError`. The package refused anything above 16 until 2026-09-29, although the engine has no cap and its own default is the number of cores minus 1 (19 on a 20-thread host).

#### test_create_record_reports_a_rejected_record_to_its_error_callback

Three `Dup` documents with the same key under a UNIQUE index, submitted with `create_record(..., callback=..., error_callback=...)` at parallel level 1 and one record per commit: one is stored, `error_callback` receives two duplicate-key exceptions, and `callback` has fired for all three, since it runs when the writer creates a record, before its batch commits. `error_callback` is new in 26.10.1 (#14); before it, a rejected record reached only the executor-wide `on_error`.

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
2. On wheels before 26.10.1, keep `set_parallel_level()` at 1 whenever the executor runs SQL commands that write: above 1 the submissions were partly discarded (#7615, fixed in #7625). From 26.10.1, `test_async_executor_bulk_command_is_exact_at_parallel_four` asserts an exact count at level 4. Levels above 1 were already safe for `create_record`, `append_samples`, `Database.insert_many`, and `Database.graph_batch`.
3. Assert an exact count against what was submitted. A `count > 0` assertion passes on a load that lost three quarters of its rows.
4. Use per-operation `error_callback` or global `on_ok()` / `on_error()` handlers to observe outcomes. Before 26.10.1 the per-command callback reported no error when records were discarded; only the executor-wide `on_error` handler did (#7625 reports a failed batch through the command's error callback as well).
5. `is_pending()` / `is_processing()` track queue state; `is_pending()` is `False` after completion. Both are non-blocking polls of the engine's `isProcessing()`: `waitCompletion(0)` is not a poll, the engine reads a zero timeout as "wait forever" (#7107).
6. Closing the owning database also closes its owned async executor; `close()` is idempotent.

## See Also

- **[AsyncExecutor API](../../api/async_executor.md)**
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)**
- **[Testing Overview](overview.md)**
