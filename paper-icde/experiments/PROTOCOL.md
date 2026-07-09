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

## Configuration policy — defaults first, fairness overrides (2026-07-07)

Every backend runs **as shipped, with default index/engine settings**, unless a
deviation is required to make the comparison fair. Legitimate deviations, each
recorded in the manifest and in the paper's configuration table with its
justification:

1. **Resource fitting** (always applied): heap/thread-pool/memory settings that
   adapt an engine to the cell's cpuset+memory envelope (JVM heap by scale,
   `SET threads` in DuckDB, ES `ES_JAVA_OPTS`). Not tuning — envelope equality.
2. **Vendor-documented settle steps** (bulk-load-then-query preparation, timed
   inside build): ES forcemerge, Milvus flush+load, Qdrant green-wait, ArcadeDB
   LSM compact. Each engine gets its own documented step; none gets skipped.
3. **Operating-point matching**: where defaults put systems at different points
   of a quality/latency tradeoff, raw latency comparison is misleading — match
   the points or sweep the curve. Dense ANN (L3d): same HNSW M/efConstruction
   everywhere, efSearch swept -> recall-latency curves; float32 everywhere, no
   PQ/SQ. Sparse: still no COMMON quantization axis (competitors' posting
   formats are internal and not user-selectable), so quality is surfaced via
   first-class recall@10 next to every latency number. As of 26.7.2, ArcadeDB
   DOES expose `weightQuantization` (engine #5143, filed off this benchmark),
   so we additionally report an INT8-vs-FP32 ablation on our own engine to
   price the default's recall cost (backend `arcadedb_sparse_embedded_fp32`).
4. **Escape hatch**: if a default is demonstrably pathological for a workload
   (e.g., a batch-size or refresh-interval default that cripples ingest), tune
   it to the vendor's own documented recommendation for that workload, apply
   the same care to every backend in the lane, and say so in the paper.

What we never do: per-system expert tuning beyond vendor-documented guidance,
or tuning ArcadeDB with insider knowledge not applied to competitors.

### ArcadeDB embedded vs server — parity matrix (2026-07-07)

The deployment axis (E4) is only meaningful if the two deployments of the
same engine differ ONLY in transport. Pinned:

| dimension | embedded | server | status |
|---|---|---|---|
| heap | -Xms{heap} -Xmx{heap} via jvm_kwargs | ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap} | MATCHED per scale tier |
| GC | bundled-JRE default (G1) | JAVA_OPTS override drops image ZGC -> G1 | MATCHED (G1 both) |
| JDK | wheel's jlink'd JRE 21 | image jdk-21 | same major; exact builds recorded in manifests |
| cpuset / mem-swap caps | 32g container | 24g srv + 8g client (75/25) | envelope equality: totals identical; split is inherent to the topology |
| DDL / index metadata | identical CREATE INDEX | identical | MATCHED |
| ingest path | native document API | SQL over HTTP | intentionally different — each surface's native bulk path |
| settle step | LSM compact() via Java API | none reachable over HTTP/SQL | documented product asymmetry (lessons material) |
| engine RAM-derived defaults | from 32g container | from 24g container | follows the envelope split; recorded, not tuned |

Every row's heap and mem cap now land in runs.jsonl (`heap`, `mem_cap`).
History: the 2GB-default heap starvation (user-caught 2026-07-07) cost the
server 15% p50 and 35% build time at 10M — parity is load-bearing.

## CPU allocation (explicit, 2026-07-06)

- Paper tier: 12 threads = full P-core set (cpuset 0-11; 6 physical P cores x
  2 SMT on the i9-12900HK), one cell at a time. E-core threads 12-19 stay
  OUTSIDE all containers (OS/dockerd/harness overhead never pollutes cells).
- Client-server: both containers share the same 12-thread cpuset (see topology
  note); sweep tier: 3 workers x 4 disjoint threads, never reported.
- ENGINE THREAD POOLS PINNED EXPLICITLY to the cpuset size — cpuset alone does
  not control pools sized from detected CPUs, and detection differs (JVM is
  cgroup-aware; DuckDB hardware_concurrency may see the host's 20):
  DuckDB `SET threads=12`; Postgres `max_parallel_workers=12` (+ per-gather);
  ArcadeDB JVM default (cgroup-aware) + ForkJoin parallelism stated;
  ES/Milvus/Qdrant per their config, documented per engine in the manifest.
  Every manifest records the engine's effective thread setting.

## Runtime budget & co-scheduling decision (2026-07-06)

1. BUILD ONCE, QUERY MANY: ingest/index-build happens once per (backend, scale)
   and is timed with its own N=3; the N=5 query repeats run against the
   persisted store with an engine restart between reps. This removes the
   dominant cost (multi-hour graph/sparse builds) from the repeat loop with
   zero fairness impact.
2. CALIBRATION STUDY decides paper-tier co-scheduling: ~6 representative cells
   run both solo (12 threads) and 2-at-once (disjoint 6-thread cpusets, no SMT
   sharing across jobs). If co-run deltas on means AND p95/p99 fall within the
   solo std, the paper tier runs 2-at-once and the paper states the measured
   perturbation bound; otherwise latency-bearing cells stay serial and only
   build/ingest cells co-run. (Permutation cancels between-config bias — fine
   for ratios — but cannot restore absolute levels/tails, and our headline
   claims are single-node absolutes.)
3. 10M-scale and scale-ceiling cells are serial regardless (RAM-bound) — they
   are also the longest, so co-scheduling only ever accelerates the cheap half
   of the matrix.

## Bench host (2026-07-06)

- tk@mini (i9-12900HK, 61 GiB, 1.8 TB NVMe) is EXCLUSIVE to this paper's runs;
  CypherGlot's campaigns run on Hetzner (standing arrangement, per maintainer).
  Paper-tier cells therefore run on an otherwise-idle host by default.
- Laptop is for harness development and smoke (plumbing validation) only —
  nothing measured on the laptop is ever reported.
- Before first mini runs: verify cpuset layout with lscpu (P-thread IDs 0-11
  assumed), stage images + datasets, re-run the tiny smoke there.

## One runner per bench host (enforced 2026-07-10)

`sweep_orphans()` force-removes every container labeled `icde-bench=1` at
runner startup. A second runner therefore DESTROYS a live campaign's in-flight
cells. This actually happened: a micro smoke launched while the L1 N=5 medium
tier was running wiped an in-flight cell (`can not get logs from container`)
and pushed another to the 6h watchdog (`timeout_after_21600s`). Those L1 rows
are contaminated and superseded by the definitive 26.7.2 campaign.

`runner.py` now takes an exclusive `flock` on `results/.runner.lock` before
sweeping. A second runner exits with an error instead of stomping the first.
Corollary rules: never rebuild a bench image while a campaign is live (running
containers keep the old image, new cells get the new one, so a campaign would
straddle two engine builds), and never co-run a smoke with a paper-tier run.
