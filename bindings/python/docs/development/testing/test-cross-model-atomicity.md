# Cross-Model Atomicity Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cross_model_atomicity.py)

The project page's cross-model story, at test size: search, hop and update in one transaction survive an interruption between the writes with nothing torn; the same writes without a transaction are torn every time.

There are 1 tests.

## Test Cases

### 1) one transaction is never torn and no transaction always is

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_cross_model_atomicity.py -v
```
