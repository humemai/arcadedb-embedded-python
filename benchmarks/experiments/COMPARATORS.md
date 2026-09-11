# Comparators: what runs against ArcadeDB, pinned

One row per engine. The digest is the amd64 manifest digest (`docker manifest
inspect -v <tag>`), which is what `runner.BACKENDS` pins and what every row
records under `server_image`; the tag beside it is for humans. Client-side
packages are pinned in `build_images.sh` (`PKGS[client]`). The version a row
publishes is what the engine reports at connect time, never the tag.

## In the harness (2026-09-11)

| Engine | Pin | Version | Lanes | Deployment | Ingest path |
|---|---|---|---|---|---|
| ArcadeDB | wheel + `arcadedb-c25:<commit>` built from one commit | `26.9.1-dev · 8d6af9475` | all | embedded and served | Python package / Java API; sqlscript over HTTP when served |
| PostgreSQL | `postgres@sha256:de1e13ca…` | 17.10 | documents (synthetic, TPC) | served | COPY FROM STDIN |
| DuckDB | `dbbench:duckdb` (duckdb==1.5.5) | 1.5.5 | documents, time series, dense (VSS) | embedded | DataFrame / Arrow INSERT SELECT |
| SQLite | `dbbench:client` stdlib sqlite3 | 3.50.x (image's Python) | documents, TPC, time series | embedded | executemany per transaction |
| Neo4j | `neo4j@sha256:4bae36af…` | 5-community | graph, composed cross-model | served | UNWIND batches over bolt |
| LadybugDB | `ladybug==0.19.1` | 0.19.1 | graph | embedded | COPY from CSV |
| Qdrant | `qdrant/qdrant@sha256:75eab8c4…` | v1.18.2 | dense, sparse, composed cross-model | served | upsert batches, gRPC |
| Milvus | `milvusdb/milvus@sha256:0ea40276…` (embedded etcd) | v2.6.13 | dense, sparse | served | insert batches, flush, load |
| Elasticsearch | pinned in runner | 9.4.1 | sparse | served | bulk index, refresh, force-merge |
| Chroma, LanceDB, sqlite-vec | `dbbench:dense` (chromadb==1.5.9, lancedb==0.37.1, sqlite-vec==0.1.9) | as pinned | dense | embedded | add() / Arrow / executemany |
| QuestDB | `questdb/questdb@sha256:e62916bd…` | 9.1.1 | time series | served | InfluxDB line protocol over TCP |
| SurrealDB | `surrealdb==2.0.0` (Python SDK, in-process; the SDK embeds engine 2.0.0) | 2.0.0 | cross-model, documents (TPC), graph, dense | embedded, SurrealKV on disk (`mem://` until 2026-09-11) | SDK `insert()` batches, `RELATE` statements for edges |

## Mode: server or embedded (Python)

Every comparator is one of two things, and the page's Mode column says which: a
server in its own container, reached from the client container over the cell
network; or an engine embedded in the Python client process. An engine that
genuinely offers both gets both rows, as ArcadeDB does; SurrealDB is that case
(Python SDK on RocksDB, and the v3.2.4 server). Qdrant's "local mode" is a
pure-Python reimplementation rather than the engine and is not run. Servers:
PostgreSQL, pgvector, TimescaleDB, MongoDB, Neo4j, Qdrant, Milvus,
Elasticsearch, QuestDB, SurrealDB (served). Embedded: DuckDB, SQLite, LadybugDB,
Chroma, LanceDB, sqlite-vec, SurrealDB (SDK).

## Being added (2026-09-11, user review: "what else did we miss")

Latest self-hosted releases as of 2026-09-11, looked up and pinned on that day.

| Engine | Pin | Version | Lanes | Notes |
|---|---|---|---|---|
| MongoDB | `mongo@sha256:41afd6e1183f57e4e4d03ab733070671fca8553da2b36f15d6e3fc9760494d17` (`mongo:8.2.12`) | 8.2.12 | documents (TPC-C/TPC-H, synthetic), time series (native time-series collection) | 8.0 refuses to start on Linux >= 6.19 (SERVER-121912); 8.2 runs. Single-node replica set, because multi-document transactions (TPC-C new-order) need one. Vector search in Community 8.2 needs the separate `mongot` process (`mongodb/mongodb-community-search`), a second container per cell: deferred until the runner can start a two-container server. Graph via `$graphLookup` is not a model MongoDB claims; not measured. Client: `pymongo==4.18.1`. |
| pgvector | `pgvector/pgvector@sha256:dca0d688bbb31d3f851502ffcb9c7791387b4fcc544ae434dab41761e5ece317` (`0.8.6-pg17`) | PostgreSQL 17 + pgvector 0.8.6 | dense (`vector`, HNSW m=16, ef_construction=100, ef_search=100), sparse (`sparsevec`, HNSW, inner product; indexing needs <= 1,000 non-zeros per vector, SPLADE has ~127) | Same PostgreSQL major as the document comparator. `maintenance_work_mem` sized to the cell's cap for the build (resource fitting, disclosed). |
| TimescaleDB | `timescale/timescaledb@sha256:189fd4822991918322c1f0d17e5adcf42853bf022a3d0dbdb56da61c5f811286` (`2.28.3-pg17`) | 2.28.3 on PostgreSQL 17 | time series (hypertable, `time_bucket`) | One of TSBS's home engines. COPY ingest, index on (host, ts). Smoke on the laptop: 206k points/s, 12h aggregate 118 ms. |
| Neo4j | `neo4j@sha256:1ee8f6fa220f9a4f194d07caa82e12120ee501c06cb38eb245e530737cbdb15b` (`2026.07.1-community`) | 2026.07.1 | graph (re-run), dense (its vector index, HNSW), cross-model (vector index + graph + property update in one transaction) | Replaces the 5-community pin so one Neo4j version appears everywhere. Calendar versioning since 2025. Dense queries use the Cypher 25 `SEARCH` clause (the procedure is deprecated since 2026.04); it has no candidate-count option and `LIMIT k` alone gave recall 0.50 at micro scale, so the adapter asks for `ef_search` (100) candidates and keeps the best k, the operating point every other engine runs at; recall 0.999 on the smoke. |
| PostgreSQL + pgvector + Apache AGE | built image `dbbench:pg-age` (Dockerfile.pgage) FROM `pgvector/pgvector@sha256:dca0d688…` + `postgresql-17-age` from the PGDG apt repo, which ships AGE 1.7.0 as of 2026-09-11; both extension versions recorded on the row at connect | PostgreSQL 17.11 + pgvector 0.8.6 + AGE 1.7.0 | cross-model (pgvector hit, Cypher hop through AGE, row update, one transaction) | The strongest "one engine" rival to the page's central claim. |
| SurrealDB (served) | `surrealdb/surrealdb@sha256:6a5002363ff5b000b72a55f985203e951e3175e578002954b0e38f113e48a698` (`v3.2.4`) | 3.2.4, RocksDB storage | documents (TPC-C/TPC-H), graph (RELATE edges), dense (HNSW), cross-model (re-run, replacing the in-memory row) | Disk-backed and served like the other comparators; `mem://` stays only as history. No time-series type: not measured there. The embedded twin (SDK, engine 2.0.0 on SurrealKV) runs the same three single-model lanes; the two versions differ because no newer SDK exists, and both are recorded per row. SurrealQL details: records carry `RecordID`s (a string id becomes a string key, BUGS F31); the two grouped graph OLAP queries use a subquery because the 2.0.0 engine sorted by the group key after GROUP BY; Q1/Q6 with `math::sum`/`math::mean`/`GROUP ALL`; new-order as one `BEGIN ... COMMIT`; dense through `DEFINE INDEX ... HNSW DIMENSION n DIST EUCLIDEAN TYPE F32 EFC 100 M 16` and the `<\|k,ef\|>` operator. Queue qDO, after qDN. |

## Not added, and why

- OrientDB: ArcadeDB is its successor; not a live comparison.
- Cloud-only engines (Atlas-only features, Cosmos DB): cannot run in the envelope.
- Repurposing a relational engine as a graph store, or the reverse, outside the cross-model transaction: out of scope by decision (DECISIONS #67).

## Smoke tests before queueing (laptop, 2026-09-11)

Every new adapter ran once on the laptop against its pinned image before its
queue script was written: MongoDB (documents tiny, time series full corpus),
SQLite (documents tiny, time series full corpus), pgvector dense (micro, recall
1.0) and sparse (micro), Neo4j vector index (micro, recall 0.999), TimescaleDB
(full corpus). The TPC adapters have no laptop corpus and are exercised by their
queue script's first cell.

SurrealDB single-model adapters (2026-09-11, engine 2.0.0 embedded through the
SDK and 3.2.4 served, a 0.01-scale TPC-H corpus generated with DuckDB, LDBC
micro, SIFT 5k): documents new-order 2,598 ops/s embedded and 112 ops/s served
(one round trip per statement), Q1 3.1 s embedded and 0.54 s served at 1/100
of SF1; graph builds 7.7 s embedded and 5.9 s served, point/hop1/hop2 0.15 /
8.1 / 128 ms embedded and 1.1 / 1.5 / 3.1 ms served, OLAP 1.8 s embedded and
0.1 to 0.43 s served; dense recall@10 0.9996 embedded and 0.9979 served.
Found and fixed on the way: string ids become string keys (F31), ORDER BY
after GROUP BY on 2.0.0, and RELATE statements 60x slower than the SDK's
bulk relation insert.
