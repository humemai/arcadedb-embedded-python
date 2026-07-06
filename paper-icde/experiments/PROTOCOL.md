# Benchmark protocol (decided 2026-07-06)

## Resource envelope — parent-cgroup equality

Every cell runs under ONE parent cgroup (`docker run --cgroup-parent=<slice>`)
carrying the cell's TOTAL budget: cpuset = P-core threads only (0-11 on the
i9-12900HK bench host), `--memory` + `--memory-swap` caps, same JVM-heap policy
per scale tier.

- Embedded topology: 1 container under the parent (engine + workload in-process).
- Client-server topology: server container + client container under the SAME
  parent — they compete for the same total; no manual client/server split
  (removes the split-ratio tunable as a bias vector; mirrors a real single-host
  deployment). One sensitivity cell per family uses an explicit 80/20 split to
  show conclusions don't depend on arbitration.
- HA topology (E3): 3 server containers + client under one parent with a bigger,
  stated budget (the co-running IS the experiment).

## Accounting — always sum both sides

- Memory: parent cgroup `memory.peak` (= client + server summed, comparable to
  embedded's single-process number, which inherently includes client-side work).
  Per-container peaks also recorded for breakdown figures.
- CPU: parent cgroup usage (user+sys), plus per-container.
- Cross-check parent numbers against `docker stats` samples (the RSS-confound
  lesson from the cypherglot harness).

## Measurement rules

- Metrics per cell: latency p50/p95/p99 + mean, sustained QPS, bulk-load /
  index-build time, recall@10 vs exact ground truth, peak + post-load RSS,
  on-disk size, cold-start where relevant.
- N=5 repeats -> mean±std; warmups discarded and counted.
- Two-tier parallelism: shuffled parallel sweep (2-3 workers, disjoint cpusets)
  for exploration only; EVERY number reported in the paper comes from serial
  re-runs (one cell at a time, full budget). Manifests record the tier.
- Images pinned by digest on first run; engine versions in every manifest.

## Experiment matrix (revised 2026-07-06 — eval must mirror the multi-model thesis)

Per-model lanes (compact: 1 figure/table each, 1-2 specialist baselines):
- L1 tabular OLTP+OLAP vs PostgreSQL, DuckDB (10-100M rows)
- L2 graph OLTP+OLAP vs Neo4j (LDBC-SNB-style, ~10M nodes / ~80M edges;
  cypherglot harness reused, FRESH runs + engine-focused queries — no result
  overlap with the CypherGlot paper)
- L3 vector: sparse headline (Qdrant, Milvus, Elasticsearch) at 100k/1M/10M
  x 30k-dim + E1b scale-ceiling (grow past 10M until each system fails the
  fixed 61GiB node — "max corpus per node" figure); real-SPLADE 1M subset for
  external validity; dense sanity vs pgvector
- L4 time-series (small): ingest + range/downsample vs InfluxDB, one table

Unification experiments (the depth):
- U1 hybrid cross-model ACID txn (vector hit -> graph traversal -> doc update,
  ONE transaction) vs composed Postgres+Neo4j+Qdrant stack: latency + atomicity
  demonstration (induced mid-write failure)
- U2 deployment axis: same workload embedded (wheel) vs server
- U3 durability: kill -9 during ingest -> WAL recovery; 3-node Raft failover
- Headline summary figure: "one engine vs N specialists" — ArcadeDB within X
  of the best specialist per lane, only system present in every row

Datasets: synthetic SPLADE-shape (seeded generator), MS MARCO SPLADE 1M,
Stack Exchange multi-model corpus (reused, U1/U2), LDBC-SNB-style graph
(cypherglot generator), TPC-H-style or Stack Exchange tables (L1), synthetic
metrics stream (L4).

Disjointness: SciPy paper = embedded-from-Python, small scale, SQLite/Chroma/
Ladybug; this paper = engine-level, 10-100x scale, Postgres/Neo4j/ES/Qdrant/
Milvus/InfluxDB. CypherGlot = workload-shape claims; harness reuse only.
