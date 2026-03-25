# Benchmark Results

This directory stores benchmark result snapshots for the database comparison examples
in `bindings/python/examples`.

Scope:

- Examples 07-10 benchmark table and graph workloads.
- Examples 11-13 benchmark vector index build, vector search, and hybrid vector-query
  workflows.
- The benchmarks are used to compare ArcadeDB against other databases/backends across
  OLTP, OLAP, vector indexing, and vector search scenarios.

Organization:

- Each dated subdirectory (for example `17-Mar-2026`, `21-Mar-2026`, `24-Mar-2026`,
  `25-Mar-2026`) contains one benchmark snapshot.
- New dated folders can be added over time as benchmarks are rerun after code,
  configuration, or engine changes.

Use these snapshots to track how ArcadeDB and the comparison backends perform over
time under the example-driven benchmark suite.
