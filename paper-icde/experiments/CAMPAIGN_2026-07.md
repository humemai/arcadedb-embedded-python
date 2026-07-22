# ICDE 2027 experimental campaign — July 2026 (COMPLETE)

Status: **all seven lanes data-complete on mini** as of 2026-07-22.
Raw data: mini `~/repos/arcadedb-icde/paper-icde/experiments/results/`
(runs.jsonl + l4_tsbs.jsonl), archived on mini at
`~/archives/icde-campaign-2026-07-22-{results,queue-logs}.tar.gz`; laptop
working copies pulled into `results/` here (gitignored). Queue-runner
infrastructure torn down 2026-07-22 (campaign-scoped; reinstall for the
October freeze week).

## Canonical-row rule

Dedupe runs.jsonl by latest row per (lane, scale, workload, backend, rep).
Two cell groups carry a pre-2026-07-21 duplicate under the old (non
scale-qualified) run_id scheme — l2/sf10 (all backends) and
l3d/small/duckdb_vss_dense; both duplicates agree with the canonical
July-21 rows (e.g. DuckDB-VSS recall 0.975 in both sets). micro/tiny tiers
are smoke, not paper rows. All paper cells: N=5, rc=0, no gaps.

## Lane status and headline medians (median [min–max], N=5)

| Lane | Scale(s) | Backends | Headline |
|---|---|---|---|
| L1 tabular | small, medium | arcade emb+srv, duckdb, postgres | OLTP/OLAP split per workload |
| L1-TPC | TPC-H SF1 (Q1/Q6 + New-Order OLTP) | same 4 | arcade OLTP 2,165 tx/s; duck Q1 15.5 ms |
| L2 graph | LDBC SF1, SF10 | arcade emb+srv, neo4j, ladybug | arcade point-traversal p99 wins; strict-durability parity 539 vs 525 ops/s |
| L3s sparse | Big-ANN small (100k), medium (1M) | arcade emb(+fp32,+nocompact)+srv, qdrant, milvus, es | recall next to latency everywhere; ES 0.725 on real SPLADE |
| L3d dense | SIFT small, DEEP-10M | arcade emb+srv, qdrant, milvus, chroma, lancedb, sqlite-vec, duckdb-vss | arcade recall 0.873→0.948 at new default M=32 (#5352) |
| E2 hybrid-ACID | e2 | arcade, surrealdb, composed qdrant+neo4j | arcade 3.36 ms [3.20–3.49] atomic; composed 22.35 ms and TORN 5/5 (306≠299) |
| E3 durability/HA | kill-9 + 3-node Raft | arcade | recovery <1 s, zero tearing; failover 0.23–3.32 s, no_loss 5/5 (251/251) |
| L4 TSBS | cpu-only 2.59M pts | arcade, duckdb, questdb | see table below |

### L4 TSBS (2,592,000 points, N=5)

| Backend | Ingest pts/s | q_last ms | q_range ms | q_global ms |
|---|---|---|---|---|
| arcadedb | 31,276 [30,957–31,509] | **0.52** [0.49–0.58] | 4.80 [3.92–5.28] | 1,791.65 [1,761.71–1,810.96] |
| duckdb | 1,940,570 [1,910,007–1,946,089] | 1.40 [1.37–1.54] | 1.28 [1.24–1.28] | **4.57** [4.37–4.82] |
| questdb | 431,306 [428,659–436,302] | 0.85 [0.72–0.89] | **0.77** [0.72–1.05] | 2.22 [2.05–2.82] |

Row-count agreement across backends (1/60/12) validates query equivalence.
ArcadeDB wins the point lookup (composite (host,ts) index); loses global
aggregation (no time partitioning — full scan). Honest framing: ArcadeDB is
not a TS specialist; the lane shows the same substrate handles the shape.

## Version disclosure (October freeze re-measures on one pinned release)

Arcade engine versions vary by lane sub-campaign (26.8.1.dev0 → dev3 →
26.8.1-SNAPSHOT servers); recorded per-row in `engine_version`. All headline
tables get re-measured on the final pinned release during the October freeze
(~1 week mini time) — July data drives drafting and the upstream-issue trail
(7 filed → 7 fixed → 7 verified).
