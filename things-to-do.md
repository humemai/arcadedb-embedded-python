## Things to do for python bindings

- [ ] Currently: vector examples use a temporary hybrid flow. We create the
      LSM_VECTOR / HNSW index in SQL, then fetch it via the Python object API and
      call `build_graph_now()` to build the HNSW graph immediately. This is a bit
      dirty, but cleaner than `REBUILD INDEX` for now. Luca is working on making
      this fully doable from SQL in one clean step. when done, update the tests,
      examples, and the documents
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
