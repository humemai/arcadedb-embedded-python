## Things to do for python bindings

- [x] Vector examples, tests, and docs now use the SQL-only flow for eager
      LSM_VECTOR / HNSW graph creation by default. Keep `build_graph_now()` for
      explicit maintenance cases after large vector mutations.
- [ ] add example 17: time series end-to-end (create type, insert tagged points, range query, bucket aggregation)
- [ ] add example 18: geo predicates (within/intersects with WKT points/polygons)
- [ ] add example 19: hash index exact-match lookup workflow
- [ ] add example 20: materialized view lifecycle (create, alter refresh mode, refresh, inspect metadata, drop)
- [ ] add example 21: graph algorithms (shortestPath, dijkstra, astar)
- [ ] add example 22: better support for client-server in python? We are positioning
      this repo as arcadedb-embedded-python, but it would be nice to have some level of
      support for client-server as well. Let's see how much can work out of the box. Let's
      not over-engineer it.
- [ ] GAV: add a small management API in Python
  - [ ] I think this is still being updated. Maybe i'll visit later.
