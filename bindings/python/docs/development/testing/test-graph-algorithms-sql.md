# Graph Algorithms SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph_algorithms_sql.py){ .md-button }

These tests cover the SQL graph-algorithm functions exposed through the packaged runtime.

## Covered Behavior

### 1) `shortestPath(...)`

Validates the returned path shape for an unweighted minimum-hop query.

### 2) `dijkstra(...)`

Verifies weighted path selection using the configured `distance` edge property.

### 3) `astar(...)`

Checks that A* returns the same weighted path shape on the same graph.

### 4) RID variable inputs

Confirms that `dijkstra(...)` accepts RID-valued sqlscript variables, matching the documented example style.

### 5) disconnected paths

Ensures disconnected `shortestPath(...)` queries do not produce a misleading multi-hop path.

## Runtime Guard

If the packaged runtime does not include `shortestPath`, `dijkstra`, or `astar`, these tests skip instead of reporting a false regression.
