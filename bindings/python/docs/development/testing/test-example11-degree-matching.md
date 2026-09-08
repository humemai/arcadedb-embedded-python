# Example 11 Degree-Matching Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_example11_degree_matching.py)

Example 11 compares ArcadeDB against hnswlib-derived vector backends.

There are 3 tests.

## Test Cases

### 1) hnsw m is half the vamana degree

See the source for the exact assertions.

### 2) hnsw m never drops below one

See the source for the exact assertions.

### 3) hnsw m accepts string input

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_example11_degree_matching.py -v
```
