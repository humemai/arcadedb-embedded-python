# Logging Helper Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_logging_helper.py)

Tests for the internal _logging helper.

There are 2 tests.

## Test Cases

### 1) get logger returns namespaced logger

See the source for the exact assertions.

### 2) log swallowed exception emits debug

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_logging_helper.py -v
```
