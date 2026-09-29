# GraphBatch Bulk Path Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph.py)

Despite the file name, these tests cover the `GraphBatch` bulk paths (`new_edges` and `create_vertices`), not the graph wrapper API; that is in [Graph API Tests](test-graph-api.md).

There are 3 tests.

## Test Cases

### 1) graph batch new edges bulk

`new_edges` creates 99 property-less edges between 100 vertices in one call; the test asserts `SELECT count(*)` on the edge type is 99.

### 2) graph batch create vertices json bulk correctness

`create_vertices` on JSON-safe rows (the bulk JSON path) returns two `#` RIDs, and the stored `name`, `score`, and `ok` values read back as given. A row holding a `datetime` takes the property-matrix fallback: the test asserts it returns one RID and that the stored `ts` is not null (it does not check the type, and it does not compare the two paths).

### 3) graph batch new edges bulk with properties

`new_edges` with a `properties` list stores each edge's `w` and `label`; the test asserts both edges read back as `(1.5, "x")` and `(2.5, "y")`.

## Running

```bash
uv run pytest bindings/python/tests/test_graph.py -v
```
