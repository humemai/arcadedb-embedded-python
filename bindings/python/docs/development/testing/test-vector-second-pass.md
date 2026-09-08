# Vector Second-Pass Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_second_pass.py)

A repeated query set returns the same neighbours as its first pass: the warm second pass the project page reports is a cache effect, not a different answer.

There are 1 tests.

## Test Cases

### 1) second pass returns identical neighbours

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_vector_second_pass.py -v
```
