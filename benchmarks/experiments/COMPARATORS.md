# Comparators: what runs against ArcadeDB, pinned

One row per engine. The digest is the amd64 manifest digest (`docker manifest
inspect -v <tag>`), which is what `runner.BACKENDS` pins and what every row
records under `server_image`; the tag beside it is for humans. Client-side
packages are pinned in `build_images.sh` (`PKGS[client]`). The version a row
publishes is what the engine reports at connect time, never the tag.

## In the harness (2026-09-11; the pins every queued script runs at)

| Engine | Pin | Version | Lanes | Deployment | Ingest path |
|---|---|---|---|---|---|
| ArcadeDB | wheel + `arcadedb-c25:<commit>` built from one commit | `26.9.1-dev · 8d6af9475` | all | embedded and served | Python package / Java API; sqlscript over HTTP when served |
| PostgreSQL | `postgres@sha256:de1e13ca…` | 17.10 | documents (synthetic, TPC) | served | COPY FROM STDIN |
| DuckDB | `dbbench:duckdb` (duckdb==1.5.5) | 1.5.5 | documents, time series, dense (VSS) | embedded | DataFrame / Arrow INSERT SELECT |
| SQLite | `dbbench:client` stdlib sqlite3 | 3.46.1 (the client image's Python) | documents, TPC, time series | embedded | executemany per transaction. Not at its defaults, by decision (#70): `PRAGMA foreign_keys=ON; journal_mode=WAL; synchronous=NORMAL`, the common production setting; the default rollback journal with synchronous=FULL fsyncs twice per commit. Disclosed in the page's durability note. |
| LadybugDB | `ladybug==0.19.1` | 0.19.1 | graph | embedded | COPY from CSV |
| Qdrant | `qdrant/qdrant@sha256:75eab8c4…` | v1.18.2 | dense, sparse, composed cross-model (in-process local mode, in memory, until its own re-run) | served | upsert batches, gRPC |
| Milvus | `milvusdb/milvus@sha256:0ea40276…` (embedded etcd) | v2.6.13 | dense, sparse | served | insert batches, flush, load |
| Elasticsearch | pinned in runner | 9.4.1 | sparse | served | bulk index, refresh, force-merge |
| Chroma, LanceDB, sqlite-vec | `dbbench:dense` (chromadb==1.5.9, lancedb==0.37.1, sqlite-vec==0.1.9) | as pinned | dense | embedded | add() / Arrow / executemany |
| QuestDB | `questdb/questdb@sha256:e62916bd…` | 9.1.1 | time series | served | InfluxDB line protocol over TCP |
| SurrealDB | `surrealdb==2.0.0` (Python SDK, in-process; the SDK compiles in surrealdb-core 2.3.10, read from the extension by `surreal_common.core_version()`) | core 2.3.10 (SDK 2.0.0) | cross-model, documents (TPC), graph, dense | embedded, SurrealKV on disk (`mem://` until 2026-09-11) | SDK `insert()` batches, `RELATE` statements for edges |
| MongoDB | `mongo@sha256:41afd6e1183f57e4e4d03ab733070671fca8553da2b36f15d6e3fc9760494d17` (`mongo:8.2.12`) | 8.2.12 | documents (TPC-C/TPC-H, synthetic), time series (native time-series collection) | served | insert_many batches; single-node replica set. 8.0 refuses to start on Linux >= 6.19 (SERVER-121912); 8.2 runs. Single-node replica set, because multi-document transactions (TPC-C new-order) need one. Vector search in Community 8.2 needs the separate `mongot` process (`mongodb/mongodb-community-search`), a second container per cell: deferred until the runner can start a two-container server. Graph via `$graphLookup` is not a model MongoDB claims; not measured. Client: `pymongo==4.18.1`. |
| pgvector | `pgvector/pgvector@sha256:dca0d688bbb31d3f851502ffcb9c7791387b4fcc544ae434dab41761e5ece317` (`0.8.6-pg17`) | PostgreSQL 17 + pgvector 0.8.6 | dense (`vector`, HNSW m=16, ef_construction=100, ef_search=100), sparse (`sparsevec`, HNSW, inner product; indexing needs <= 1,000 non-zeros per vector, SPLADE has ~127) | served | COPY, then HNSW build. Same PostgreSQL major as the document comparator. `maintenance_work_mem` sized to the cell's cap for the build (resource fitting, disclosed). |
| TimescaleDB | `timescale/timescaledb@sha256:189fd4822991918322c1f0d17e5adcf42853bf022a3d0dbdb56da61c5f811286` (`2.28.3-pg17`) | 2.28.3 on PostgreSQL 17 | time series (hypertable, `time_bucket`) | served | COPY into a hypertable. One of TSBS's home engines. COPY ingest, index on (host, ts). Smoke on the laptop: 206k points/s, 12h aggregate 118 ms. |
| Neo4j | `neo4j@sha256:1ee8f6fa220f9a4f194d07caa82e12120ee501c06cb38eb245e530737cbdb15b` (`2026.07.1-community`) | 2026.07.1 | graph (re-run), dense (its vector index, HNSW), cross-model (vector index + graph + property update in one transaction) | served | UNWIND batches over bolt. Replaces the 5-community pin so one Neo4j version appears everywhere. Calendar versioning since 2025. Dense queries use the Cypher 25 `SEARCH` clause (the procedure is deprecated since 2026.04); it has no candidate-count option and `LIMIT k` alone gave recall 0.50 at micro scale, so the adapter asks for `ef_search` (100) candidates and keeps the best k, the operating point every other engine runs at; recall 0.999 on the smoke. |
| PostgreSQL + pgvector + Apache AGE | built image `dbbench:pg-age` (Dockerfile.pgage) FROM `pgvector/pgvector@sha256:dca0d688…` + `postgresql-17-age` from the PGDG apt repo, which ships AGE 1.7.0 as of 2026-09-11; both extension versions recorded on the row at connect | PostgreSQL 17.11 + pgvector 0.8.6 + AGE 1.7.0 | cross-model (pgvector hit, Cypher hop through AGE, row update, one transaction) | served | COPY plus Cypher CREATE through AGE. The strongest "one engine" rival to the page's central claim. |
| SurrealDB (served) | `surrealdb/surrealdb@sha256:6a5002363ff5b000b72a55f985203e951e3175e578002954b0e38f113e48a698` (`v3.2.4`) | 3.2.4, RocksDB storage | documents (TPC-C/TPC-H), graph (RELATE edges), dense (HNSW), cross-model (re-run, replacing the in-memory row) | served | SDK `insert()` and bulk relation insert over ws. Disk-backed and served like the other comparators; `mem://` stays only as history. No time-series type: not measured there. The embedded twin (SDK, engine 2.0.0 on SurrealKV) runs the same three single-model lanes; the two versions differ because no newer SDK exists, and both are recorded per row. SurrealQL details: records carry `RecordID`s (a string id becomes a string key, BUGS F31); the two grouped graph OLAP queries use a subquery because the 2.0.0 engine sorted by the group key after GROUP BY; Q1/Q6 with `math::sum`/`math::mean`/`GROUP ALL`; new-order as one `BEGIN ... COMMIT`; dense through `DEFINE INDEX ... HNSW DIMENSION n DIST EUCLIDEAN TYPE F32 EFC 100 M 16` and the `<\|k,ef\|>` operator. Queue qDO, after qDN. |
| ArangoDB | `arangodb@sha256:563cb2c07af0aead37fd688b58f51d6eb534a3da6163621e130e67d7a55176c4` (`arangodb:3.12.11`, 2026-08-31; the image reports "enterprise", which since 3.12 is the one self-managed build). License: BSL 1.1 per the repository's LICENSE at tag v3.12.11 (Licensed Work "ArangoDB Self Managed", Change License Apache-2.0 four years after each release), so not open source; the page's license table says so | 3.12.11, RocksDB storage | documents (TPC-C new-order as one stream transaction, TPC-H Q1/Q6 in AQL), graph (person collection keyed by id, KNOWS as an edge collection, LDBC reads and the three analytics as AQL traversals), dense (its vector index, which is FAISS IVF, not HNSW: nLists about the square root of the corpus, nProbe an eighth of them, both recorded on the row as `ivf_nlists`/`ivf_nprobe`; `degree_family` says `ivf_flat_no_degree` and F7 accepts that), cross-model (vector hit in AQL, one-hop traversal, document updates in one stream transaction that the crash trial aborts) | served only: python-arango 8.3.5 is an HTTP client and the engine has no in-process mode, so one row per table, like MongoDB | bulk import API in batches; the server runs `arangod --vector-index true`, the 3.12 opt-in for the vector index. Queued as qDV after qDU (2026-09-13, DECISIONS #78). |

## Retired pins

| Engine | Pin | Replaced by | Rows still on the page |
|---|---|---|---|
| Neo4j 5-community (5.26.28) | `neo4j@sha256:4bae36af…` | 2026.07.1 on every arm (qDK vector index and qDL graph landed 2026-09-12; qDN cross-model and the composed Qdrant + Neo4j arm in qDT still to run) | the composed cross-model row until qDT lands; each row carries the digest it ran on (BUGS F32) |
| SurrealDB in memory (`mem://`) | `surrealdb==2.0.0` | the SDK's SurrealKV disk store (qDN) | the cross-model row until qDN lands |

## Mode: server or embedded (Python)

Every comparator is one of two things, and the page's Mode column says which: a
server in its own container, reached from the client container over the cell
network; or an engine embedded in the Python client process. An engine that
genuinely offers both gets both rows, as ArcadeDB does; SurrealDB is that case
(Python SDK on SurrealKV, and the v3.2.4 server). Qdrant's local mode is not run as a
comparator on its own; the composed stack's vector half still runs it in memory
(PROTOCOL §7). Servers:
PostgreSQL, pgvector, TimescaleDB, MongoDB, Neo4j, Qdrant, Milvus,
Elasticsearch, QuestDB, SurrealDB (served), ArangoDB. Embedded: DuckDB, SQLite, LadybugDB,
Chroma, LanceDB, sqlite-vec, SurrealDB (SDK).

## Not added, and why

- OrientDB: ArcadeDB is its successor; not a live comparison.
- Cloud-only engines (Atlas-only features, Cosmos DB): cannot run in the envelope.
- Repurposing a relational engine as a graph store, or the reverse, outside the cross-model transaction: out of scope by decision (DECISIONS #68).

## Smoke tests before queueing (laptop, 2026-09-11)

Every new adapter ran once on the laptop against its pinned image before its
queue script was written: MongoDB (documents tiny, time series full corpus),
SQLite (documents tiny, time series full corpus), pgvector dense (micro, recall
1.0) and sparse (micro), Neo4j vector index (micro, recall 0.999), TimescaleDB
(full corpus). The TPC adapters have no laptop corpus and are exercised by their
queue script's first cell.

SurrealDB single-model adapters (2026-09-11, core 2.3.10 embedded through the 2.0.0
SDK and 3.2.4 served, a 0.01-scale TPC-H corpus generated with DuckDB, LDBC
micro, SIFT 5k): documents new-order 2,598 ops/s embedded and 112 ops/s served
(one round trip per statement), Q1 3.1 s embedded and 0.54 s served at 1/100
of SF1; graph builds 7.7 s embedded and 5.9 s served, point/hop1/hop2 0.15 /
8.1 / 128 ms embedded and 1.1 / 1.5 / 3.1 ms served, OLAP 1.8 s embedded and
0.1 to 0.43 s served; dense recall@10 0.9996 embedded and 0.9979 served.
Found and fixed on the way: string ids become string keys (F31), ORDER BY
after GROUP BY on core 2.3.10, and RELATE statements 60x slower than the SDK's
bulk relation insert.

### ArangoDB (laptop, 2026-09-13)

Every ArangoDB arm ran through the runner on the laptop (dbbench:client rebuilt
with python-arango 8.3.5, the pinned 3.12.11 image, `BENCH_HOST=laptop`, one rep,
sweep tier) before qDV was written; the lanes also ran directly against a
hand-started container first. Nothing here is a page number. Every row carried a
non-null latency, the server's own version (`arangodb:3.12.11`), and a server disk
reading (the image's declared volume, sized with `du` inside the container, so
the F38 gap does not repeat here).

| arm | scale | rc | headline | recall@10 | server disk MB |
|---|---|---|---|---|---|
| l1tpc oltp | tpch1 at SF 0.01 | 0 | new-order p50 10.3 ms | | 16.8 |
| l1tpc olap | tpch1 at SF 0.01 | 0 | Q1 194 ms, 4 rows | | 16.5 |
| l2 oltp | micro | 0 | point p50 2.4 ms | | 9.0 |
| l2 olap | micro | 0 | top degree p50 28 ms | | 9.0 |
| l3d search | micro (5k) | 0 | p50 2.8 ms, nLists 71, nProbe 9 | 0.953 | 9.3 |
| e2 hybrid | e2 | 0 | p50 16.2 ms | | 143.0 |
| e2 atomicity | e2 | 0 | 0 torn of 40, 40 raised | | 142.6 |

**Dense at 1M, matched by effect (laptop, 2026-09-13).** The IVF operating point
is calibrated, not typed (FAIRNESS F7 paragraph): nLists = round(4*sqrt(n)) =
4,000 at 1M, and nProbe is the smallest value whose recall@10 on the first 200
queries reaches the frozen ArcadeDB embedded fp32 median at the scale (0.9886 at
1M). The SIFT1M corpus (the same ann-benchmarks file mini's fixture was cut from)
in a separate laptop fixture dir; one build, then a calibration on the first 200
timed queries (the method before the held-out slice, kept for the curve), then
the full 1,000-query pass at half, at, and at twice the picked value. Not page
material.

| nProbe | recall@10 (1,000 queries) | p50 ms | p99 ms |
|---|---|---|---|
| 42 (picked / 2) | 0.9416 | 9.6 | 14.5 |
| 85 (picked) | 0.9827 | 13.9 | 23.3 |
| 170 (picked x 2) | 0.9950 | 25.4 | 36.6 |

Build (import + IVF training) 118.7 s on the laptop; the calibration itself took
104.8 s (12 binary-search steps of 200 queries). The curve is not flat: recall
and latency both move with nProbe, so the calibrated value is the answer and not
the cheapest one, unlike LanceDB's flat nprobes. The 200-query estimate (0.989)
sits 0.006 above the full pass (0.9827), inside the 0.01 tolerance
`fairness_check.py` allows.

The same corpus through the runner (`BENCH_ALLOW_DEV=1`, sweep tier, one rep,
`BENCH_DENSE_DATA=/data/dense1m`), calibrating on the held-out slice (fixture
queries 1000:1200, never the timed 1,000): rc 0; the row carries `ivf_nlists`
4000, `ivf_nprobe` 107, `ivf_recall_target` 0.9886 from
`runs_paper.csv arcadedb_dense_embedded fp32 small median of 5`,
`ivf_calibration_recall` 0.989, `ivf_calibration_queries` 200,
`ivf_calibration_slice` 1000:1200; full-pass recall@10 0.9886 (the target
itself), p50 18.02 ms, p99 24.4 ms, build 119.5 s, server disk 1,190.7 MB,
`degree_family` ivf_flat_no_degree. The sweep above calibrated on the first 200
timed queries and picked 85; the held-out slice picks a higher probe count and
lands the full pass on the target instead of 0.006 under it, which is the
difference between tuning on the exam and tuning beside it. Picked values also
move a little between builds because k-means training is not deterministic;
calibrating in the cell absorbs that.
