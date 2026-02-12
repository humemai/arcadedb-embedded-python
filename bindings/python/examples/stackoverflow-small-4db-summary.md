# Vector Backend Benchmark Summary (stackoverflow-small)

## Workload at a glance

- Dataset: **stackoverflow-small**
- Vector count: **around 300k** (300,424 rows)
- Embedding model: **all-MiniLM-L6-v2**
- Vector dimension: **384**
- Query workload: 1,000 queries, `k=50`, overquery factor `4`
- Resource budget used in these runs: `4g` memory, `4` threads

## Execution setup

- All four experiments were run in Docker-isolated environments.
- ArcadeDB is the only truly embedded backend in this comparison; Milvus, Qdrant, and pgvector are client/server backends, and for those runs the memory and thread budgets were split server/client at `0.8/0.2`.

## Build / ingest results

| Backend  | Total build time (s) | DB disk size | Peak RSS (MB) |
| -------- | -------------------: | -----------: | ------------: |
| ArcadeDB |               726.99 |         673M |       3014.37 |
| pgvector |               311.06 |         2.1G |       2117.36 |
| Milvus   |                61.59 |         1.9G |       1245.32 |
| Qdrant   |               128.16 |         737M |       1286.73 |

## Search results (overquery factor = 4)

| Backend  | Search time for 1,000 queries (s) | Mean latency (ms) | P95 latency (ms) | Mean recall |
| -------- | --------------------------------: | ----------------: | ---------------: | ----------: |
| ArcadeDB |                             13.36 |             12.80 |            16.71 |     0.96406 |
| pgvector |                             13.42 |             13.35 |            23.84 |     0.98840 |
| Milvus   |                             15.81 |             14.94 |            35.01 |      0.9577 |
| Qdrant   |                             52.13 |             51.80 |            83.50 |     0.98548 |

## HNSW details

- For a simple apples-to-apples setup, focus on `M`, `efConstruction`, and `efSearch`; in this benchmark the other three backends used effective `efSearch=200`, while ArcadeDB used overquery factor `4` as the practical counterpart (with `M=16` and `efConstruction=100` on the HNSW-based backends).
- ArcadeDB vector indexing in this benchmark uses the Java **JVector** library with an **LSM**-based structure.

## Notes and quick interpretation

- **Fastest build** in this run: **Milvus**.
- **Smallest on-disk DB** in this run: **ArcadeDB** (673M), then **Qdrant** (737M).
- **Best recall** in this run: **pgvector** (0.9884), then **Qdrant** (0.98548).
- **Lowest mean query latency** in this run: **ArcadeDB** (12.80ms), very close to **pgvector** (13.35ms).
