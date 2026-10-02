# Logging Helper Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_logging_helper.py)

Tests for the internal _logging helper.

## Test Cases

### test_get_logger_returns_namespaced_logger

`get_logger("arcadedb_embedded.foo")` returns a `logging.Logger` with that name.

### test_log_swallowed_exception_emits_debug

Inside an `except` block, `log_swallowed_exception(logger, "during shutdown")` emits
exactly one DEBUG record on that logger; its message contains the text and it carries
`exc_info`.

## Running

```bash
uv run pytest bindings/python/tests/test_logging_helper.py -v
```
