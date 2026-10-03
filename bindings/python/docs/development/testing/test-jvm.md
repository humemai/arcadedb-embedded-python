# JVM Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm.py)

Tests for start_jvm() re-entry behavior once the JVM is running, plus reopening a
database in the same process and interpreter exit with a database left open. An
autouse fixture starts the JVM before each test.

## Test Cases

### test_bare_start_jvm_joins_running_jvm

With a stored `-Xmx6g -Xms6g` config, a bare `start_jvm()` does not raise.

### test_identical_config_is_idempotent

With the stored config built from `heap_size="6g"` and `jvm_args="-Xms6g"`, calling
`start_jvm()` with the same arguments does not raise.

### test_conflicting_override_raises

With `-Xmx4g` stored, `start_jvm(heap_size="99g")` raises `ArcadeDBError` matching
"already started".

### test_create_close_reopen_same_process

Create a database, insert `k = 1`, close it, and reopen it in the same process: the
query returns `[{"k": 1}]`.

### test_interpreter_exits_with_unclosed_database

A leaked (unclosed) Database must not hang interpreter exit. A child process creates a
database without closing it; the test asserts it prints `OK` and exits 0 within 120 s.

## Ctrl-C (`test_sigint.py`)

Each case starts a child process, sends it SIGINT after the JVM is up, and reads what it printed (humemai/arcadedb-embedded-python#118). JPype's default in a script is `interrupt=True`: the JVM ends the whole process with status 130 and no `KeyboardInterrupt`, `finally`, or `atexit` runs. `start_jvm()` now passes `interrupt=False`.

- **a Python loop and a blocked Java call (`Thread.sleep`)**: inside `with db.transaction():` that inserted a row, Ctrl-C raises `KeyboardInterrupt`, the transaction is rolled back (the count is 0), `finally` and `atexit` run, and the exit status is 0.
- **`interrupt=True` keeps the old behavior**: exit status 130 and no `KeyboardInterrupt`.

A CPU-bound Java call that never checks for interruption (a slow query) is not interrupted: the `KeyboardInterrupt` arrives when it returns. That was measured (a 10 s query, Ctrl-C after 1.5 s, the `KeyboardInterrupt` at 10.3 s), not tested.

## Running

```bash
uv run pytest bindings/python/tests/test_jvm.py -v
uv run pytest bindings/python/tests/test_sigint.py -v
```
