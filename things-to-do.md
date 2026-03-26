## Things to do for python bindings

- [ ] revisit: `/mnt/ssd2/repos/arcadedb-embedded-python/.github` the thing is that this
  repo is the fork of the original java-heavy repo, and my repo is about python
  bindings. so we can perhaps remove the java tests. This means that we also have to
  revisit `/mnt/ssd2/repos/arcadedb-embedded-python/sync-upstream.sh`, cuz we might have
  to add some stuff to `FORK_OWNED_PATHS`?
- [ ] add example 18: geo predicates (within/intersects with WKT points/polygons)
- [ ] add example 19: hash index exact-match lookup workflow
- [ ] add example 20: materialized view lifecycle (create, alter refresh mode, refresh, inspect metadata, drop)
- [ ] add example 21: graph algorithms (shortestPath, dijkstra, astar)
- [ ] add example 22: better support for client-server in python? We are positioning
      this repo as arcadedb-embedded-python, but it would be nice to have some level of
      support for client-server as well. Let's see how much can work out of the box. Let's
      not over-engineer it.
- [ ] GAV: add a small management API in Python
  - [ ] I think this is still under active development. Maybe i'll visit later.
