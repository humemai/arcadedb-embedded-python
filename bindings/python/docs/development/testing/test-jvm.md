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

## Running

```bash
uv run pytest bindings/python/tests/test_jvm.py -v
```
