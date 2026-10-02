# Example 11 Degree-Matching Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_example11_degree_matching.py)

Example 11 compares ArcadeDB against hnswlib-derived vector backends. ArcadeDB applies
`maxConnections` to every graph layer, while hnswlib-derived indexes allocate `2*M`
links at the base layer, so the example converts one to the other. These tests check
that conversion, `hnsw_m_from_max_connections()`, loaded from
`examples/11_vector_index_build.py`. The module skips when that file is absent.

## Test Cases

### test_hnsw_m_is_half_the_vamana_degree

32 gives 16 and 64 gives 32.

### test_hnsw_m_never_drops_below_one

1 gives 1 and 0 gives 1.

### test_hnsw_m_accepts_string_input

The string `"32"` gives 16.

## Running

```bash
uv run pytest bindings/python/tests/test_example11_degree_matching.py -v
```
