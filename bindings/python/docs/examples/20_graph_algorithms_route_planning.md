# 20 - Graph Algorithms Route Planning

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/20_graph_algorithms_route_planning.py){ .md-button }

This example demonstrates a more realistic SQL-first graph algorithm workflow in the
Python bindings. It builds a small directed multi-modal transport network and compares
several pathfinding strategies over the same graph:

- `shortestPath(...)` for minimum-hop routing
- `dijkstra(...)` for optimizing different edge properties
- `astar(...)` for weighted routing with an options map

The workflow covers:

- creating a route graph with `City` vertices and `Road`, `Rail`, and `Ferry` edges
- comparing minimum-hop routing against weighted routing over `distance`, `duration`,
  and `risk`
- showing that `shortestPath(...)` ignores the edge weight property
- showing that `dijkstra(...)` picks different paths when the business objective changes
- cross-checking `astar(...)` against `dijkstra(...)` for multiple weighted objectives
- using `direction` to constrain shortest-path traversal
- using `sqlscript` variables with both vertex values and `@rid` inputs
- printing segment-level route summaries instead of just raw RID lists
- verifying disconnected destinations do not produce a valid route
- reopening the database and rerunning weighted and constrained queries

## Run

From `bindings/python/examples`:

```bash
python3 20_graph_algorithms_route_planning.py
```

With a custom database path:

```bash
python3 20_graph_algorithms_route_planning.py --db-path ./my_test_databases/graph_algo_demo
```

## Notes

- The example stays SQL-first on purpose. It does not introduce a Python-native graph
  algorithms wrapper.
- `shortestPath(...)` is unweighted. It minimizes hops, not `distance`, `duration`, or
  `risk`.
- `dijkstra(...)` and `astar(...)` are the right fit when edge weights matter.
- The example uses an `astar(...)` options map to show the SQL shape for heuristics,
  direction, and tie-breaking.
- The same graph is reused for several routing questions so you can see how objective
  selection changes the chosen route and how `astar(...)` compares with `dijkstra(...)`.
- If the packaged runtime does not include the graph algorithm SQL functions, the script
  prints a short explanation and exits.

## Why This Example Exists

The Python bindings already expose the graph algorithm SQL functions, and the bindings
test suite already covers them. This example turns that low-level coverage into a richer
route planning lab so the examples set includes a dedicated pathfinding example that
goes beyond a single shortest-path query and demonstrates realistic routing tradeoffs.
