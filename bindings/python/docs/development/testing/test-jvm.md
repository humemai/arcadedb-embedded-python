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

Each case starts a child process, sends it SIGINT after the JVM is up, and reads what it printed (humemai/arcadedb-embedded-python#118). Windows cannot deliver SIGINT to a child process, so `tests/conftest.py` leaves this file out of collection there (`collect_ignore`) rather than reporting skips. JPype's default in a script is `interrupt=True`: the JVM ends the whole process with status 130 and no `KeyboardInterrupt`, `finally`, or `atexit` runs. `start_jvm()` now passes `interrupt=False`.

- **a Python loop and a blocked Java call that Ctrl-C cannot wake (a socket `accept()` that times out after 4 s)**: inside `with db.transaction():` that inserted a row, Ctrl-C raises `KeyboardInterrupt` (in the Java case when the call returns), the transaction is rolled back (the count is 0), `finally` and `atexit` run, and the exit status is 0.
- **`interrupt=True` keeps the old behavior**: exit status 130 and no `KeyboardInterrupt`.

The Java case stands in for a CPU-bound Java call that never checks for interruption (a slow query), which is not interrupted: the `KeyboardInterrupt` arrives when it returns. That was also measured with a 10 s query (Ctrl-C after 1.5 s, the `KeyboardInterrupt` at 10.3 s).

The case does not block in `Thread.sleep()` on purpose (humemai/arcadedb-embedded-python#179). Ctrl-C wakes a call that waits in an interruptible way, and JPype 1.7.1 then fails at random: it raises `java.lang.InterruptedException` or `RuntimeError: Fatal error occurred` and delivers the `KeyboardInterrupt` late. That happened in 14 of 400 interrupts with two cores idle and in 26 of 200 with two busy cores, and a test that blocked in `Thread.sleep()` failed 4 of 40 runs with the busy cores. [Known Engine Issues](../../guide/known-issues.md) describes the race and the workaround.

## Running

```bash
uv run pytest bindings/python/tests/test_jvm.py -v
uv run pytest bindings/python/tests/test_sigint.py -v
```
