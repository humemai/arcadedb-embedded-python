# GraphBatch Bulk Path Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph.py)

Despite the file name, these tests cover the `GraphBatch` bulk paths (`new_edges` and `create_vertices`), not the graph wrapper API; that is in [Graph API Tests](test-graph-api.md).

## Test Cases

### 1) graph batch new edges bulk

new_edges buffers many property-less edges in one crossing.

### 2) graph batch create vertices json bulk correctness

The JSON bulk vertex path stores values identically to the matrix path (and datetimes fall back to the matrix path with types preserved).

### 3) graph batch new edges bulk with properties

new_edges with per-edge property dicts stores values correctly.

## Running

```bash
uv run pytest bindings/python/tests/test_graph.py -v
```
