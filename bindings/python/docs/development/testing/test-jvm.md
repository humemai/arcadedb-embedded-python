# JVM Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm.py)

Tests for start_jvm() re-entry behavior once the JVM is running.

There are 5 tests.

## Test Cases

### 1) bare start jvm joins running jvm

See the source for the exact assertions.

### 2) identical config is idempotent

See the source for the exact assertions.

### 3) conflicting override raises

See the source for the exact assertions.

### 4) create close reopen same process

See the source for the exact assertions.

### 5) interpreter exits with unclosed database

A leaked (unclosed) Database must not hang interpreter exit.

## Running

```bash
uv run pytest bindings/python/tests/test_jvm.py -v
```
