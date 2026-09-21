# Comparators: what runs against ArcadeDB, pinned

One row per engine. The digest is the amd64 manifest digest (`docker manifest inspect -v <tag>`), which is what `runner.BACKENDS` pins and what every row records under `server_image`; the tag beside it is for humans. Two pins were NOT that, until 2026-09-19: Qdrant and mongot carried the multi-arch INDEX digest instead. Both forms resolve and both are exact, so no row ever ran the wrong image, but the file said one thing and held another; both are normalised to the amd64 manifest digest now. Client-side packages are pinned in `build_images.sh` (`PKGS[client]`). The version a row publishes is what the engine reported at connect time, never the tag.

Which arms are on the October page, with their rows and columns, is PAGE-SPEC.md section 2; the September queue chain is CAMPAIGN.md section 6. This file says only what each engine is pinned to and why it runs the way it does.


ArcadeDB's document analytics rows were withdrawn from the page on 2026-09-14 (BUGS F42 and F43), so the `docs_olap` comparisons on the live page are between comparators only until October re-measures them. The engine defect behind half of it, a bare decimal literal compared at single precision, was filed upstream as #7609 on 2026-09-15 and is the reason this repository's ArcadeDB SQL never compares a numeric column against a bare decimal literal and uses `BETWEEN` or a bound parameter instead. The other half was ours: `Q1_ARCADE` computed four of the five aggregates every comparator computed, so the cell timed a smaller question than the row beside it (BUGS F43).

Two more filings came out of the same answer checking on 2026-09-15. #7610 is the served engine printing a time bucket as a date, which collapses every bucket inside one calendar day, so the served native time-series grouping is withheld from the page and named as a known disagreement. #7611 is an indexed lower bound skipping part of a run of equal entries, which is why the revenue query disagreed only at the size where the loss landed on a qualifying row (BUGS F44 and F46).

## In the harness

| Engine | Pin | Version | Lanes | Deployment | Ingest path |
|---|---|---|---|---|---|
| ArcadeDB | wheel + `arcadedb-c25:<commit>` built from one commit | `26.9.1-dev · 8d6af9475` is September's pin; October re-pins to the matched pair built from the 26.10.1 release when it ships (DECISIONS #74), and the laptop skeleton runs the stock published image `arcadedata/arcadedb:26.8.1@sha256:49036720b167…`, which its rows name. That stock digest is also the `server_image` BACKENDS carries for every served ArcadeDB arm, and it is what runs if `ARCADEDB_SERVER_IMAGE` is not exported -- which `runner._require_local_server_image()` refuses when a local pin is claimed, after 21 rows were once stamped with a commit they had not run (2026-08-27). Stated here because the code pins it and a pin no document names is a pin nobody checks | all | embedded and served | Python package / Java API; sqlscript over HTTP when served |
| PostgreSQL | `postgres@sha256:7341002d…` | 18.6 | documents (TPC) | served | COPY FROM STDIN. A second arm, `postgres_tuned`, derives shared_buffers and friends from the container cap and leaves durability alone; it is an ablation of one image's defaults, so it runs on the lane and is kept off the document tables and the durability table, where it would read as a second engine (DECISIONS #76). |
| DuckDB | `dbbench:duckdb` (duckdb==1.5.4, moved down from 1.5.5 on 2026-09-17: 1.5.4 is the newest DuckDB the community-extensions registry has a DuckPGQ build for, a campaign pins each engine to the latest version at which it can be measured across every table it belongs on, and one engine wears one version per page, so every DuckDB arm moved together; DECISIONS #103d, and #103e for September) | 1.5.4 | documents, time series, dense (VSS), graph (DuckPGQ) | embedded | DataFrame / Arrow INSERT SELECT |
| DuckPGQ | `dbbench:duckdb` (duckdb==1.5.4) + `INSTALL duckpgq FROM community` at connect (extension version recorded on the row; `f386a6c` on 2026-09-17) | duckdb 1.5.4 + duckpgq | graph | embedded | Arrow INSERT SELECT into the persons and knows tables; a `CREATE PROPERTY GRAPH` over them answers every read in SQL/PGQ (`GRAPH_TABLE ... MATCH`), writes are plain SQL in one transaction (DECISIONS #103d, #92). The community DuckPGQ build exists for 1.5.4 and 404s for 1.5.5 and 1.6.0, which is why every DuckDB arm pins to 1.5.4. All twenty-one graph questions, the seven interactive and the fourteen analytics with LSQB's nine, are expressible in SQL/PGQ and agree with the other engines on the slice (DECISIONS #104b); the constructs are in `.notes/bench/COMPARATOR-DIALECTS.md`. |
| SQLite | `dbbench:client` stdlib sqlite3 | 3.46.1 (the client image's Python) | documents, TPC, time series | embedded | executemany per transaction. Not at its defaults, by DECISIONS #70: `PRAGMA foreign_keys=ON; journal_mode=WAL; synchronous=NORMAL`, the common production setting. Disclosed in the page's durability note. |
| LadybugDB | `ladybug==0.20.4` | 0.20.4 | graph | embedded | COPY from CSV. Re-pinned 2026-09-19 across five releases (0.20.0-0.20.4). 0.20.x added a physical-plan cache keyed on query text, and the lane re-executes each query text many times, so the jump was smoked and answer-checked rather than assumed; see the risky-jump note below. |
| Qdrant | `qdrant/qdrant@sha256:0699e773…` | v1.19.1 | dense, sparse, composed cross-model | served (the composed stack's vector half runs in-process, in memory, until its own re-run) | upsert batches, gRPC |
| Milvus | `milvusdb/milvus@sha256:2b2fc2cf…` (embedded etcd) | v3.0.1 | dense, sparse | served | insert batches, flush, load. Re-pinned 2026-09-19 across a MAJOR (2.6.13 -> 3.0.1). 3.0 is pinned at .1 and not at .2: v3.0.2 has a git tag and pushed images but no GitHub release and no release-notes entry, so it is a tag rather than an announced release. 3.0 replaces the message queue with Woodpecker, which in the Docker standalone deployment defaults to a local-filesystem WAL, so the single container with embedded etcd and local storage that the runner starts is still a supported deployment. 3.0 rebuilt sparse retrieval around SINDI, but SINDI sits behind a version gate: it is selected only at vector index version 10 or higher, and 3.0.1 ships `targetVecIndexVersion: 8` against a knowhere whose own current version is 8, so a stock 3.0.1 runs DAAT_MAXSCORE with fp32 posting values and NOT SINDI. Milvus's own notes say new index versions are opt-in. The harness sets no `targetVecIndexVersion`, no `inverted_index_algo` and no `quant_type`, so every Milvus arm lands on version 8; this matters because the opt-in would silently quantize sparse weights to fp16 and falsify the page's precision column. Dense and sparse were smoked separately. |
| Elasticsearch | pinned in runner (`…@sha256:33178ff4…`) | server 9.5.4, client 9.5.1 | sparse | served | bulk index, refresh, force-merge. The client line lags the server line: 9.5.1 is the newest `elasticsearch` release on PyPI while the server is at 9.5.4, so the two numbers differ by design and both are the latest of their own artifact. |
| Chroma, LanceDB, sqlite-vec | `dbbench:dense` (chromadb==1.5.9, lancedb==0.39.0, sqlite-vec==0.1.9) | as pinned | dense | embedded | add() / Arrow / executemany |
| QuestDB | `questdb/questdb@sha256:931af415…` | 10.0.1 | time series | served | InfluxDB line protocol over TCP on 9009. Re-pinned 2026-09-19 across a MAJOR. QuestDB 10 adds QWP, a binary columnar protocol over WebSocket on the HTTP port, beside the line protocol; `line.tcp.enabled` still defaults to true on 0.0.0.0:9009 in 10.x and only the UDP receiver is deprecated, so this lane keeps the path it has always measured. Moving to QWP would be a new measurement, not a version bump. |
| SurrealDB (embedded) | `surrealdb==2.0.0` (Python SDK, in-process) | core 2.3.10, SDK 2.0.0 | cross-model, documents (TPC), graph, dense, time series (plain table), lifecycle (2026-09-16, DECISIONS #95b: its own SurrealKV store on disk, every situation in SurrealQL, the HNSW index for the vector situation; sparse vectors and the analytical view declared with the parse error captured verbatim, and no JVM start on its rows) | embedded, SurrealKV on disk | SDK `insert()` batches, bulk relation insert for edges. Time series (2026-09-15): no time-series type, so a SCHEMALESS table with a datetime `ts` and `DEFINE INDEX p_host_ts ON p FIELDS host, ts` defined before the load, SQLite's footing; buckets by `time::floor(ts, 1m)` / `time::floor(ts, 1h)`; the grouped-ordered-limited query is a subquery because core 2.3.10 sorts by the group key ascending after `GROUP BY` (BUGS F31). |
| SurrealDB (served) | `surrealdb/surrealdb@sha256:6a500236…` (`v3.2.4`) | 3.2.4, RocksDB storage | documents (TPC), graph, dense, cross-model, time series (plain table) | served | SDK `insert()` and bulk relation insert over ws. Time series (2026-09-15): the same table, index and SurrealQL as the embedded arm, over ws through the reconnecting client (DECISIONS #91). |
| MongoDB | `mongo@sha256:41afd6e1…` (`mongo:8.2.12`) | 8.2.12 | documents (TPC), time series (native time-series collection), graph | served | insert_many batches; single-node replica set, because TPC-C new-order needs a multi-document transaction. Client `pymongo==4.18.1` (unmoved, already the latest). Did NOT move in the October re-pin: 8.3.11 cannot boot on the bench kernel (SERVER-121912), so 8.2.12 is the latest measurable MongoDB; see the Unmoved list. The graph arm runs the SAME digest: chained `$lookup` for the fixed-depth hops, `$graphLookup` measured beside it, both core mongod; all twenty-one graph questions, LSQB's nine included, are expressed as aggregation pipelines and agree on the slice (DECISIONS #104b). |
| MongoDB + MongoDB Search | built image `dbbench:mongo-search` (Dockerfile.mongosearch) FROM `mongo@sha256:41afd6e1…` + `mongodb/mongodb-community-search@sha256:24c0cd30…`; both digests pinned in the Dockerfile | mongod 8.2.12 + mongot-community 1.70.4 | dense vectors, cross-model | served, one container holding both processes | `$vectorSearch` over a `vectorSearch` index at `hnswOptions.maxEdges`=16, `numEdgeCandidates`=100, stage `numCandidates`=100, i.e. the lane's matched point. mongod runs WITH access control, because mongot authenticates to its sync source with SCRAM and mongod authorizes it through the `searchCoordinator` role; the document arm above does not. Not `mongodb/mongodb-atlas-local`: MongoDB documents that image as "For evaluation only" and "not suitable for production use", and its vector-capable variant is a `:preview` tag. |
| pgvector | `pgvector/pgvector@sha256:1d50c689…` (`0.8.6-pg18`) | PostgreSQL 18 + pgvector 0.8.6 | dense (`vector`, HNSW m=16, ef_construction=100, ef_search=100), sparse (`sparsevec`, HNSW, inner product) | served | COPY, then HNSW build. `maintenance_work_mem` sized to the cell's cap for the build (resource fitting, disclosed). |
| TimescaleDB | `timescale/timescaledb@sha256:f7036933…` (`2.30.1-pg18`) | 2.30.1 on PostgreSQL 18 | time series (hypertable, `time_bucket`) | served | COPY into a hypertable, index on (host, ts). One of TSBS's home engines. Pinned at 2.30.1 and never 2.30.0: 2.30.0 introduced the `DeferredChunkAppend` planner node and 2.30.1 fixes that node producing DUPLICATE ROWS, which is an answer bug on this lane's own query shapes. |
| Neo4j | `neo4j@sha256:e702d6b5…` (`2026.08.1-community`) | 2026.08.1 | graph, dense (its vector index, HNSW), cross-model | served | UNWIND batches over bolt. Dense queries use the Cypher 25 `SEARCH` clause; it has no candidate-count option and `LIMIT k` alone gave recall 0.50 at micro scale, so the adapter asks for `ef_search` (100) candidates and keeps the best k, the operating point every other engine runs at. |
| PostgreSQL + pgvector + Apache AGE | built image `dbbench:pg-age` (Dockerfile.pgage) FROM `pgvector/pgvector@sha256:1d50c689…` + `postgresql-18-age` from PGDG; both extension versions recorded on the row at connect | PostgreSQL 18 + pgvector 0.8.6 + AGE 1.8.0 | cross-model | served | COPY plus Cypher CREATE through AGE. The strongest "one engine" rival to the page's central claim. |
| ArangoDB | `arangodb@sha256:563cb2c0…` (`arangodb:3.12.11`; the image reports "enterprise", which since 3.12 is the one self-managed build). License BSL 1.1 per the repository's LICENSE at tag v3.12.11, so not open source; the page's license table says so | 3.12.11, RocksDB storage | documents (TPC), graph, dense, cross-model, time series (plain table) | served only: python-arango 8.3.5 is an HTTP client and the engine has no in-process mode | bulk import API in batches; the server runs `arangod --vector-index true`. Its vector index is FAISS IVF, matched by effect rather than by knob, and the seven `ivf_*` fields on the row make the operating point auditable (FAIRNESS.md F7). Time series (2026-09-15): no time-series type, so one collection with `ts` as epoch milliseconds and a persistent index over `["host", "ts"]`, SQLite's footing; buckets by `DATE_TRUNC(d.ts, 'minute')` / `DATE_TRUNC(d.ts, 'hour')`, which return ISO strings the digest reads as instants. |
| Memgraph | `memgraph/memgraph@sha256:4710bee1…` (`memgraph:3.13.1`, the latest self-hosted stable on 2026-09-17; `latest` resolves to the same digest). License BSL 1.1 for the engine (`memgraph/memgraph` LICENSE), with Memgraph's own Enterprise features gated by a license key that the arm never has; not open source | 3.13.1, IN_MEMORY_TRANSACTIONAL (the documented default: the graph in RAM, WAL and periodic snapshots on disk) | graph | served, Bolt through the same `neo4j==6.3.1` driver the Neo4j arm uses (2026-09-17; moved from 6.2.0 in the October re-pin below, and this row moves with it because the two arms share one driver) | UNWIND batches over bolt, the Neo4j arm's statements verbatim; every query on the lane runs unchanged and every digest matched Neo4j's at micro. Four host-sized or unbounded defaults are set from the cell and read back onto the row: Bolt workers and snapshot threads from the cpuset (FAIRNESS F6), `--memory-limit` at 90% of the container cap (its own rule, which it otherwise applies to the host's physical memory), `--query-execution-timeout-sec=0` in place of the 600 s default so the lane's budget is the only censor, telemetry off. Durability from `SHOW CONFIG`: WAL fsynced every 100,000 transactions by default; the strict class sets 1 (both straced). Memory at SF10: about 1.1 KiB per stored object measured at 10k persons / 207k edges, so 2.3 GiB for the graph inside the tier's 24g. |
| FalkorDB | `falkordb/falkordb@sha256:0a9fe4d1…` (`falkordb:v4.20.6`, the latest release on 2026-09-17; `latest` resolves to the same digest). License SSPL 1.0 (`FalkorDB/FalkorDB` LICENSE.txt) on Redis 8.6.3 (RSALv2 / SSPLv1 / AGPLv3); not open source under the page's tests | 4.20.6 on Redis 8.6.3 | graph | served, the Redis protocol through `falkordb==1.7.1` (`redis==8.1.0`) (2026-09-17) | UNWIND batches as `GRAPH.QUERY` calls, the Neo4j arm's statements verbatim (the client carries `$rows` as a CYPHER parameter prefix); every query on the lane runs unchanged and every digest matched Neo4j's at micro. The image's own `FALKORDB_ARGS` ("MAX_QUEUED_QUERIES 25 TIMEOUT 1000 RESULTSET_SIZE 10000") is replaced: the 1 s timeout would abort the triangle count at micro (1.2 s) and the 10,000-row cap is the ArcadeDB HTTP trap in another engine; `THREAD_COUNT` is passed from the cpuset because the module sizes it from the host (16 threads under a 12-CPU cpuset, FAIRNESS F6); `BROWSER=0` stops the image's Next.js process. Durability from `CONFIG GET`: RDB snapshots only by default (nothing synced at commit); the strict class runs AOF with `appendfsync always` through `REDIS_ARGS` (both straced). |

The composed cross-model stack (Qdrant + Neo4j) is not a pinned engine of its own: it is two of the rows above wired together. On the September page it carries the retired Neo4j 5-community pin until qDT re-runs it; the October skeleton payload records it at `qdrant-local:1.19.1+neo4j:2026.08.1`, with its Qdrant half still in memory and disclosed on the table.

**September carries two DuckDB versions, and that is a known defect of the stopped extension.** #103d and #103e say one engine wears one version per page, and the re-measure that would have made that true (stage qEE) was cancelled. DuckPGQ landed on the graph table at DuckDB 1.5.4 while the documents, time-series and dense-VSS rows still read 1.5.5, so the live page shows both until October re-measures every DuckDB arm at one version. Do not quote a DuckDB comparison across those tables without naming the version each row ran.

From 2026-10 every engine above that has a durability setting runs the relaxed commit class, read out of the engine and recorded on the row; FAIRNESS.md F10 holds the mapping and names the engines that cannot be relaxed.

**The two SurrealDB rows are two engines.** The embedded arm used one core on every lane measured, at about 1.0 to 1.3 processor seconds per elapsed second against 6.5 to 14.9 for its own server and 13.5 for ArcadeDB embedded, so its latencies are a single-threaded engine's and the page says so rather than reading them as the product's ceiling. Its core is a year older than the server's (core 2.3.10 against server 3.2.4, BUGS F39) and sits on a different store, so the two rows differ by version, store, and threading as well as by transport (DECISIONS #95). They also run different text for the triangle count, each the form that is fast on its own version (DECISIONS #93, FAIRNESS.md F4).

## The October re-pin (2026-09-19)

Every comparator was re-surveyed on 2026-09-19 against its registry and its project's own release
feed, under DECISIONS #87 (latest self-hosted stable release at campaign time, pinned by amd64
manifest digest) and #103d (pin each engine to the latest version at which it can be MEASURED
across the tables it belongs on, which is not always the highest number, and record where the two
differ).

**Moved.**

| Engine | From | To | amd64 manifest digest |
|---|---|---|---|
| PostgreSQL (and `postgres_tuned`) | 17.10 | 18.6 | `sha256:7341002d2b8c…` |
| pgvector | 0.8.6-pg17 | 0.8.6-pg18 | `sha256:1d50c689b0a6…` |
| PostgreSQL + pgvector + AGE | PG17 + AGE 1.7.0~rc0 | PG18 + AGE 1.8.0~rc0 | built image, base as pgvector |
| TimescaleDB | 2.28.3-pg17 | 2.30.1-pg18 | `sha256:f7036933154c…` |
| MongoDB Search (mongot) | 1.70.4 (index digest) | 1.70.4 (amd64 digest) | `sha256:24c0cd30baf0…` |
| Neo4j | 2026.07.1-community | 2026.08.1-community | `sha256:e702d6b535d9…` |
| Qdrant | v1.18.2 (index digest) | v1.19.1 | `sha256:0699e7733a6f…` |
| Milvus | v2.6.13 | v3.0.1 | `sha256:2b2fc2cf499a…` |
| Elasticsearch | 9.4.1 | 9.5.4 | `sha256:33178ff49e06…` |
| QuestDB | 9.1.1 | 10.0.1 | `sha256:931af4156771…` |
| LadybugDB | `ladybug==0.19.1` | `ladybug==0.20.4` | client package |
| LanceDB | `lancedb==0.37.1` | `lancedb==0.39.0` | client package |
| Qdrant client | `qdrant-client==1.19.0` | `1.19.1` | client package |
| Elasticsearch client | `elasticsearch==9.5.0` | `9.5.1` | client package |
| Neo4j driver (Neo4j AND Memgraph arms) | `neo4j==6.2.0` | `6.3.1` | client package |

**Unmoved, and why.** Each of these was checked against the registry or the project's release feed
on the same day and is already at its latest stable release, unless a reason is given.

- **MongoDB stays at 8.2.12 while 8.3.11 exists, and this is the one engine where #103d
  overrode #87.** 8.3.11 refuses to start on the bench kernel: `MongoDB cannot start: Linux
  kernel versions 6.19 and newer has a known incompatibility with this version of MongoDB`
  (SERVER-121912) -- the same guard that moved this project off 8.0 in the first place,
  reappearing on the 8.3 line. Found by the re-pin smoke, not by reading: the 8.3.11 pin was
  applied, the first `l1tpc` MongoDB cell died `server_not_ready` after 124 s, and the captured
  serverlog carried that one fatal line. On the same laptop and the same kernel
  (7.0.0-29-generic) 8.2.12 reaches "Waiting for connections" and reports 8.2.12. 8.2.12 is also
  the newest release on the 8.2 line, so it is the latest MongoDB that can be MEASURED, which is
  exactly what #103d asks for. Intermediate 8.3.x releases were deliberately not hunted for one
  predating the guard: the guard is MongoDB declaring this kernel incompatible with the 8.3 line,
  and running an older 8.3 that merely lacks the warning would be running a configuration its own
  vendor now calls unsafe. Every MongoDB arm -- documents, TPC, time series, graph, and the
  mongod half of the MongoDB Search image -- holds at 8.2.12 together.
- **DuckDB and DuckPGQ stay at 1.5.4** while 1.5.5 exists. This is the standing exception of
  DECISIONS #103d/#103e, not an oversight: the community-extensions registry still has no DuckPGQ
  build for 1.5.5 or 1.6.0, the graph arm cannot be measured on a version whose graph extension
  404s, and one engine wears one version per page, so every DuckDB arm holds together at 1.5.4.
- **SurrealDB server stays at v3.2.4** and **the SurrealDB Python SDK at 2.0.0**. v3.2.4 is still
  the newest release on the 3.2 line; v3.1.6 is a backport on the older line, and the only higher
  numbers are `v3.3.0-beta.1` through `-beta.4`, which are pre-releases. The SDK's only higher
  number is `3.0.0b8`, likewise a pre-release.
- **ArangoDB stays at 3.12.11.** It is the latest release. The `3.12.11` tag was REBUILT on
  2026-09-18, so the tag's amd64 digest moved to `sha256:460b77c5349f…` while the pin holds
  `sha256:563cb2c07af0…`. The pin is deliberately not chased: the release did not change, and
  moving a digest under an unchanged version would force every ArangoDB row to be re-measured to
  record a rebuilt base layer.
- **Memgraph stays at 3.13.1** and **FalkorDB at v4.20.6**; both are the latest releases and both
  tags still resolve to the pinned digests, unchanged since the September survey.
- **Chroma stays at 1.5.9** and **sqlite-vec at 0.1.9**; both are the newest stable releases
  (sqlite-vec's only higher number, `0.1.10a4`, is a pre-release).
- **pymongo 4.18.1, python-arango 8.3.5, falkordb 1.7.1, redis 8.1.0** are all already at the
  latest release.
- **pymilvus stays at 3.0.1**, which is what Milvus's own compatibility table names for a 3.0.1
  server. It did not move, but its meaning did: until this commit a 3.x client was pinned against
  a 2.6 server, a major apart. The Milvus move closes that, rather than opening it.
- **SQLite stays at 3.46.1**, which is not a pin of ours at all: it is whatever stdlib `sqlite3`
  the `python:3.12-slim` base carries, read back at connect. Verified by running after the
  rebuild, not assumed.
- **ArcadeDB is not a comparator** and is untouched here: it is pinned to our own wheel and the
  matching `arcadedata/arcadedb:26.10.1-SNAPSHOT` image at commit 417314c18d (DECISIONS #74).

**The jumps that needed their own smoke, and why.**

- **QuestDB 9 -> 10, a major that adds an ingest protocol.** 10.0 introduced QWP, a binary
  columnar protocol over WebSocket on the HTTP port, beside the InfluxDB line protocol this lane
  ingests over. QuestDB's own configuration docs still show `line.tcp.enabled` defaulting to true
  on 0.0.0.0:9009 in 10.x, with only the UDP receiver deprecated, so the measured path is
  unchanged. What the release notes do not cover is the startup banner, and the runner gates
  readiness on a regex over it, so that was smoked rather than assumed. The 10.0.x answer-changing
  changes (UNION over SYMBOL, LEFT JOIN LATERAL count compensation, SHOW PARTITIONS columns,
  EXPLAIN no longer HTML-encoded) all land on constructs this lane does not use.
- **Milvus 2.6 -> 3.0, a major that rewrites the deployment.** 3.0 replaces the message queue with
  Woodpecker; in the Docker standalone deployment Woodpecker defaults to a local-filesystem WAL, so
  the one container with embedded etcd and local storage that the runner starts is still a
  supported deployment and needs no MinIO and no external MQ. The `dataCoord.segment.*` keys the
  dense arm overrides are not renamed in 3.0.
- **Milvus 3.0's sparse rewrite does NOT reach a stock deployment, and the page's precision column
  depends on that.** 3.0 rebuilt sparse retrieval around SINDI, whose posting values are hard
  quantized to fp16 for inner product. SINDI is not a new index type -- `SPARSE_INVERTED_INDEX` is
  still the only one -- it is an algorithm behind a version gate, selected only at vector index
  version 10 or above, and rejected outright below it. 3.0.1 ships `targetVecIndexVersion: 8`
  against a knowhere whose current version is also 8, and Milvus's own release notes say new index
  versions are opt-in. So a stock 3.0.1 runs DAAT_MAXSCORE at fp32, the sparse precision column
  still reads fp32, and it reads fp32 BECAUSE of a config key rather than because of the version.
  Raising `dataCoord.targetVecIndexVersion` to 10 would falsify that column silently. Checked: the
  harness sets none of `targetVecIndexVersion`, `inverted_index_algo` or `quant_type`, the sparse
  arm mounts no `milvus.yaml` at all, and AUTOINDEX's sparse default carries none of them either.
- **The segment-seal override was a 2.6 config file and had to be regenerated.**
  `docker-conf/milvus-dense.yaml` is a verbatim copy of the stock `milvus.yaml` with exactly one
  line changed (`dataCoord.segment.sealProportion`, 0.12 -> 0.5). Mounted over a 3.0 container it
  would have pinned EVERY key to 2.6's defaults, silently running the new engine on the old
  engine's configuration -- the same shape of defect as the ArcadeDB build-cache note in
  `runner.py`. It is regenerated from 3.0.1's own stock config with the same one line changed.
- **The PostgreSQL set moves as one.** postgres, pgvector, TimescaleDB and AGE all wear one
  PostgreSQL major per page (#103d), so 18 could only be taken if all four had a PG18 build. AGE
  gated it, being the only one packaged per major; PGDG carries `postgresql-18-age` (1.8.0~rc0),
  so the set moved together. PostgreSQL 18 turns data checksums on by default and makes
  `EXPLAIN ANALYZE` report BUFFERS automatically; the first is a write-path cost the page pins to
  because it is PostgreSQL's own default, and the second is harmless here because no lane parses
  PostgreSQL's EXPLAIN output.
- **Neo4j's dense operating point had to be re-measured.** The dense arm's recall rests on a
  hand-built operating point, because the Cypher `SEARCH` clause has no candidate-count option and
  `LIMIT k` alone gave recall 0.50 at micro; the adapter asks for `ef_search` (100) candidates and
  keeps the best k. 2026.08 does not add a query-time knob, and the HNSW defaults (m=16,
  ef_construction=100) are unchanged, but a new index provider `vector-2026.08` is auto-selected
  for newly created indexes, so the operating point is a measurement and not an inheritance.
  (2026.08 also makes `null / 0` return null instead of raising, and the pin is at .1 rather than
  .0 because 2026.08.0 could fail queries through its internal resource monitoring.)
- **LadybugDB crosses five pre-1.0 releases that touch the paths this lane times.** 0.20.x added a
  physical-plan cache for repeated queries, and 0.20.0/0.20.1/0.20.2 are each partly a fix for a
  defect in it: state reuse on the cached fast path, silent row loss when LOAD FROM/UNWIND feeds a
  MATCH primary-key predicate, and stale rows from re-executed parameterized queries. One is still
  open: ladybug#985, where re-executing a prepared query with different SKIP/LIMIT PARAMETER values
  returns the first execution's page. This lane cannot reach #985's mechanism -- `LadybugGraph`
  calls `conn.execute(text)` with no parameters at all and every LIMIT is a literal -- but it does
  re-execute the same query text many times, which is exactly what the new cache keys on, so the
  jump was answer-checked rather than reasoned about. Probed directly on 0.20.4 in the rebuilt
  client image (2026-09-19, laptop): COPY FROM CSV loads the expected cardinality and preserves a
  comma inside a quoted name; the lane's four analytics shapes (top-degree, group-by-city, a
  two-hop count, and a grouped average) are byte-identical across 25 consecutive executions of the
  same text on one connection; and #985 does NOT reproduce -- a prepared query re-executed at
  SKIP 0, 4 and 8 returned the correct three pages, not the first one three times. So the cache
  does not move an answer on the shapes this lane times, by measurement rather than by argument.
  The storage format also moved and the lane rebuilds from CSV on every cell, so nothing is carried
  across the bump. One deprecation noted for later: 0.20.x warns that separate `prepare` +
  `execute` is deprecated in favour of a single `execute` call; this lane already uses the latter.

## Dialect facts that decide a comparison

Things an engine does that are not wrong and are not a performance property, but that change what comes back and therefore what the #88 answer check sees. Each was found by a disagreement, and each is written down here so the next lane does not have to find it again.

- **ArangoDB returns an integral `SUM` as an integer.** AQL's `SUM` over a column whose values VelocyPack stored as integers returns an integer, where every SQL engine, MongoDB's `$sum` and SurrealQL's `math::sum` return a double. Found 2026-09-14 on TPC-H Q1 at SF1: `sum_qty` came back `37734107` against every other engine's `37734107.0`, the same number, and the canonical form printed the first exactly and the second as `3.77341e+07`. Seven engines to one, on an answer nobody got wrong. It is invisible below a million, which is why SF0.01 passed. The fix is in the lane's column declaration — a summed measure is declared `num` — not in the engine and not in the hash.
- **The ArcadeDB SQL parser narrows a decimal literal that needs more than single precision.** `INSERT INTO T SET v=0.33333333` into a `DOUBLE` property stores 0.33333334; a bound parameter with the same value stores the double exactly. TPC-H money is unaffected (two decimals below 131072 round-trip through float32 and the served arm's corpus is bit-identical to the embedded arm's, measured at SF1), but any lane that loads through SQL text with more than about seven significant digits is exposed. BUGS F43 recorded the comparison half of this; the insert half is the same parser.
- **The ArcadeDB HTTP API truncates a result at 20,000 rows** unless the request says otherwise, and `/command` takes no `limit` field. Lanes that send scans over HTTP carry an explicit `LIMIT` in the SQL instead.
- **A two-sided indexed range on a STRING column loses rows at its `>=` lower bound.** Found 2026-09-14 at TPC-H SF0.1, where both ArcadeDB arms returned a Q6 revenue of 11,801,684.4174 against every other engine's 11,803,420.2534. The deficit is 1,735.836, which is exactly one line item of the qualifying set (shipdate 1994-01-01, quantity 17, extendedprice 28930.6, discount 0.06). Isolated through the lane's own adapter, with a `NOTUNIQUE` index on `l_shipdate`:

  | predicate over the same window | rows, SF0.1 | rows, SF1 |
  |---|---|---|
  | `l_shipdate >= '1994-01-01' AND l_shipdate < '1995-01-01'` | 92,037 | 908,652 |
  | `l_shipdate > '1993-12-31' AND l_shipdate < '1995-01-01'` | 92,040 | 909,455 |
  | `l_shipdate.substring(0, 4) = '1994'` (no index can serve it) | 92,040 | 909,455 |

  Deterministic: ten repeats inside one build and two independent builds all returned 92,037. The two rewrites, which denote the same set, both return the truth, so it is the `>=` bound on the index scan and not the data. It is NOT registered as a known disagreement: at SF1 the extra Q6 predicates happen to exclude every lost row and the answer is right to 1e-14, so registering it would suppress a gate that is correctly failing at the size where the loss lands on a qualifying row. `arcadedb_literal_precision_probe.py` is the sibling finding on the insert path; this one wants a Java repro against the engine's index range scan before it goes upstream.


## Retired pins

| Engine | Pin | Replaced by |
|---|---|---|
| Neo4j 5-community (5.26.28) | `neo4j@sha256:4bae36af…` | 2026.07.1 on every arm. The composed cross-model row on the September page is the last one still on it; the October payload records 2026.07.1 for it. |
| SurrealDB in memory (`mem://`) | `surrealdb==2.0.0` | the SDK's SurrealKV disk store |

Each row carries the digest it actually ran on, so a table can hold a mix while a re-run is queued (BUGS.md F32).

## Mode: server or embedded (Python)

Every comparator is one of two things, and the page's Mode column says which: a server in its own container, reached from the client container over the cell network; or an engine embedded in the Python client process. An engine that genuinely offers both gets both rows, as ArcadeDB does; SurrealDB is the one comparator that does.

Servers: PostgreSQL, pgvector, PG+AGE, TimescaleDB, MongoDB, MongoDB + MongoDB Search, Neo4j, Memgraph, FalkorDB, Qdrant, Milvus, Elasticsearch, QuestDB, SurrealDB (served), and ArangoDB. Embedded: DuckDB (its VSS and DuckPGQ arms included), SQLite, LadybugDB, Chroma, LanceDB, sqlite-vec, and SurrealDB (SDK).

## Not added, and why

- OrientDB: ArcadeDB is its successor, so it is the ancestor and not a live comparison (DECISIONS #68, #103).
- Kuzu: LadybugDB, its continuation, is already the embedded graph comparator (DECISIONS #103).
- HugeGraph, Dgraph, and TigerGraph: a sixth dialect for a comparator few readers care about, a different model, and not freely self-hostable, respectively (DECISIONS #103).
- LDBC Graphalytics: not run. It is an algorithm suite that needs each engine's own analytics library, which most of the comparators lack; upstream already publishes it against the graph specialists and the page links there for that question (DECISIONS #103, #104). LSQB's nine queries are run instead, on the analytics table.
- Cloud-only engines (Atlas-only features, Cosmos DB): cannot run in the envelope.
- ~~MongoDB vector search~~ and ~~MongoDB graph~~: **both joined on 2026-09-15** and their rows are in the table above. The vector exclusion was "needs the separate `mongot` process, a second container per cell, and the runner starts one server per cell"; the pair runs in one container now, which is the deployment MongoDB's own default mongot config is written for, and MongoDB Search reached general availability for Community Edition on 2026-06-30. The graph exclusion was "`$graphLookup` is not a model MongoDB claims", which DECISIONS #92 does not accept as a reason: an engine competes in its own dialect if it can express the query. All twenty-one graph questions are expressible, LSQB's nine included (DECISIONS #104b); the constructs and the ones that needed care are in `.notes/bench/COMPARATOR-DIALECTS.md`.
- Repurposing a relational engine as a graph store, or the reverse, outside the cross-model transaction: out of scope (DECISIONS #68).

DuckDB with DuckPGQ was on this list until 2026-09-17, stopped by the community extension having no build for the then-pinned duckdb==1.5.5; it joined when every DuckDB arm moved to 1.5.4 (DECISIONS #103d), and its row in the table above carries the reason.

## Smoke before queueing

Every new adapter runs once on the laptop through the runner, against its pinned image, at a micro or sweep scale with one rep, before its queue script is written. The smoke proves the image, the adapter, the recorded schema, and the version string; nothing it produces is a page number, and every published row is re-measured on mini. The TPC adapters have no laptop corpus and are exercised by their queue script's first cell instead.

Laptop fixtures live in `~/bench-data`: `dense` is a 20k cut of SIFT1M, `dense1m` the full million with ground truth (`BENCH_DENSE_DATA=/data/dense1m` selects it). Mini holds its own copies.

**What durability costs, measured on the laptop skeleton.** Placeholders from a busy development machine, labelled as such: nothing here reaches the page, and the campaign's own rows replace them (DECISIONS #90).

Document insert, strict against relaxed: SQLite 69x (0.021 ms to 1.45 ms), ArcadeDB embedded 33.7x (0.217 to 7.31), PostgreSQL 16.3x (0.155 to 2.53), SurrealDB embedded 12.3x (0.584 to 7.18), MongoDB 4.1x (0.686 to 2.81), ArangoDB 4.0x (2.18 to 8.70), and ArcadeDB served 3.7x (2.47 to 9.19). Graph insert: SurrealDB embedded 10.5x, ArangoDB 3.6x, ArcadeDB embedded 3.5x, and ArcadeDB served 2.1x. Cross-model transaction: ArangoDB 1.4x, ArcadeDB served 1.2x, PostgreSQL with pgvector and AGE 1.2x, and ArcadeDB embedded 1.2x.

The pattern is the finding rather than any one number: the strict document inserts span 1.45 to 9.19 ms where the relaxed ones span 0.021 to 2.47, so waiting for the disk costs every engine about the same and the multiple is largest exactly where the relaxed path is fastest. PROTOCOL.md section 3 carries what follows from it for the write rows the page prints.

Smoke findings that changed an adapter are recorded in `.notes/bench/BUGS.md`, not here.
