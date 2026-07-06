# Benchmark protocol (decided 2026-07-06)

## Resource envelope — parent-cgroup equality

Every cell runs under ONE parent cgroup (`docker run --cgroup-parent=<slice>`)
carrying the cell's TOTAL budget: cpuset = P-core threads only (0-11 on the
i9-12900HK bench host), `--memory` + `--memory-swap` caps, same JVM-heap policy
per scale tier.

- Embedded topology: 1 container under the parent (engine + workload in-process).
- Client-server topology (implementation note 2026-07-06: docker slice limits
  need root, unavailable on the bench host — pragmatic equivalent adopted):
  server and client containers share the SAME cpuset (CPU is work-conserving,
  so competition is natural and unbiased — no split tunable), while MEMORY is
  split explicitly (default 75/25 server/client; memory does not arbitrate
  gracefully under contention — OOM). Sums must respect the cell total. One
  sensitivity cell per family uses 85/15 to show conclusions don't depend on
  the split.
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

Per-model lanes (compact: 1 figure/table each). DESIGN RULE: each lane pairs
one SERVER-grade specialist with one EMBEDDED specialist — the baseline set
itself restates the thesis (ArcadeDB is the only engine on both sides of every
lane):
- L1 tabular OLTP+OLAP: PostgreSQL (server) + DuckDB (embedded), 10-100M rows
- L2 graph OLTP+OLAP (Cypher engines): Neo4j (server) + LadybugDB (embedded),
  LDBC-SNB-style ~10M nodes / ~80M edges. Cypherglot harness reused with FRESH
  runs + a standard-workload query set — no result overlap with the CypherGlot
  paper (papers cross-cite; re-check disjointness when both drafts exist).
  Memgraph/AGE/FalkorDB cited, not run.
- L3 vector dense: Qdrant or pgvector (server) + LanceDB (embedded, columnar
  Lance format — no server mode, worth a sentence)
- L3 vector sparse (headline): Elasticsearch + Qdrant + Milvus (all server) at
  100k/1M/10M x 30k-dim + E1b scale-ceiling past 10M on the fixed 61GiB node
  ("max corpus per node" figure); real-SPLADE 1M subset for external validity.
  NOTE: no embedded learned-sparse engine exists to our knowledge — citable
  claim; ArcadeDB is the only embedded entry in this lane by definition.
- L4 time-series (small): InfluxDB (server), one table

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

## Workload design — OLTP and OLAP are separate suites (decided 2026-07-06)

- Every lane defines TWO fixed, versioned query suites: OLTP (point reads /
  inserts / updates / point traversals -> ops/s + latency percentiles) and OLAP
  (analytical aggregations / multi-hop traversals -> per-query ms, mean of K
  runs). Never blended into a single number; figures show them side by side.
- Every engine runs BOTH suites, with its IDIOMATIC configuration per workload
  (no strawmen): ArcadeDB graph OLAP = Graph Analytical View enabled (build
  polled to READY; build time reported as a separate one-time-cost column);
  specialists get their recommended indexes/settings per workload.
- Results are annotated with each engine's design orientation (DuckDB and
  LadybugDB are OLAP-oriented; Postgres/Neo4j OLTP-oriented; ArcadeDB
  OLTP-oriented with GAV as its OLAP answer) so wins/losses read as
  workload-shaped, not engine-shaped — the same honesty pattern protects
  ArcadeDB where specialists win.
- Index policy: indexed mode is the default reported configuration; an
  unindexed ablation only where it teaches something (cf. cypherglot's
  index-removal finding), not everywhere.
