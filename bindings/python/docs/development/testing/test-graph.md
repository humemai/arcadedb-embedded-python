# Graph API Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph.py)

There are 3 tests.

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
