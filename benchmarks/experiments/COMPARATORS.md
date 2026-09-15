# Comparators: what runs against ArcadeDB, pinned

One row per engine. The digest is the amd64 manifest digest (`docker manifest inspect -v <tag>`), which is what `runner.BACKENDS` pins and what every row records under `server_image`; the tag beside it is for humans. Client-side packages are pinned in `build_images.sh` (`PKGS[client]`). The version a row publishes is what the engine reported at connect time, never the tag.

Which arms are on the page and which are still queued is PAGE-SPEC.md section 2; the queue chain is CAMPAIGN.md section 6. This file says only what each engine is pinned to and why it runs the way it does.


ArcadeDB's document analytics rows were withdrawn from the page on 2026-09-14 (BUGS F42 and F43), so the `docs_olap` comparisons on the live page are between comparators only until October re-measures them. The engine defect behind half of it, a bare decimal literal compared at single precision, was filed upstream as #7609 on 2026-09-15 and is the reason this repository's ArcadeDB SQL never compares a numeric column against a bare decimal literal and uses `BETWEEN` or a bound parameter instead. The other half was ours: `Q1_ARCADE` computed four of the five aggregates every comparator computed, so the cell timed a smaller question than the row beside it (BUGS F43).

Two more filings came out of the same answer checking on 2026-09-15. #7610 is the served engine printing a time bucket as a date, which collapses every bucket inside one calendar day, so the served native time-series grouping is withheld from the page and named as a known disagreement. #7611 is an indexed lower bound skipping part of a run of equal entries, which is why the revenue query disagreed only at the size where the loss landed on a qualifying row (BUGS F44 and F46).

## In the harness

| Engine | Pin | Version | Lanes | Deployment | Ingest path |
|---|---|---|---|---|---|
| ArcadeDB | wheel + `arcadedb-c25:<commit>` built from one commit | `26.9.1-dev · 8d6af9475` | all | embedded and served | Python package / Java API; sqlscript over HTTP when served |
| PostgreSQL | `postgres@sha256:de1e13ca…` | 17.10 | documents (TPC) | served | COPY FROM STDIN. A second arm, `postgres_tuned`, derives shared_buffers and friends from the container cap and leaves durability alone. |
| DuckDB | `dbbench:duckdb` (duckdb==1.5.5) | 1.5.5 | documents, time series, dense (VSS) | embedded | DataFrame / Arrow INSERT SELECT |
| SQLite | `dbbench:client` stdlib sqlite3 | 3.46.1 (the client image's Python) | documents, TPC, time series | embedded | executemany per transaction. Not at its defaults, by DECISIONS #70: `PRAGMA foreign_keys=ON; journal_mode=WAL; synchronous=NORMAL`, the common production setting. Disclosed in the page's durability note. |
| LadybugDB | `ladybug==0.19.1` | 0.19.1 | graph | embedded | COPY from CSV |
| Qdrant | `qdrant/qdrant@sha256:75eab8c4…` | v1.18.2 | dense, sparse, composed cross-model | served (the composed stack's vector half runs in-process, in memory, until its own re-run) | upsert batches, gRPC |
| Milvus | `milvusdb/milvus@sha256:0ea40276…` (embedded etcd) | v2.6.13 | dense, sparse | served | insert batches, flush, load |
| Elasticsearch | pinned in runner | 9.4.1 | sparse | served | bulk index, refresh, force-merge |
| Chroma, LanceDB, sqlite-vec | `dbbench:dense` (chromadb==1.5.9, lancedb==0.37.1, sqlite-vec==0.1.9) | as pinned | dense | embedded | add() / Arrow / executemany |
| QuestDB | `questdb/questdb@sha256:e62916bd…` | 9.1.1 | time series | served | InfluxDB line protocol over TCP |
| SurrealDB (embedded) | `surrealdb==2.0.0` (Python SDK, in-process) | core 2.3.10, SDK 2.0.0 | cross-model, documents (TPC), graph, dense | embedded, SurrealKV on disk | SDK `insert()` batches, bulk relation insert for edges |
| SurrealDB (served) | `surrealdb/surrealdb@sha256:6a500236…` (`v3.2.4`) | 3.2.4, RocksDB storage | documents (TPC), graph, dense, cross-model | served | SDK `insert()` and bulk relation insert over ws. No time-series type: not measured there. |
| MongoDB | `mongo@sha256:41afd6e1…` (`mongo:8.2.12`) | 8.2.12 | documents (TPC), time series (native time-series collection) | served | insert_many batches; single-node replica set, because TPC-C new-order needs a multi-document transaction. Client `pymongo==4.18.1`. |
| pgvector | `pgvector/pgvector@sha256:dca0d688…` (`0.8.6-pg17`) | PostgreSQL 17 + pgvector 0.8.6 | dense (`vector`, HNSW m=16, ef_construction=100, ef_search=100), sparse (`sparsevec`, HNSW, inner product) | served | COPY, then HNSW build. `maintenance_work_mem` sized to the cell's cap for the build (resource fitting, disclosed). |
| TimescaleDB | `timescale/timescaledb@sha256:189fd482…` (`2.28.3-pg17`) | 2.28.3 on PostgreSQL 17 | time series (hypertable, `time_bucket`) | served | COPY into a hypertable, index on (host, ts). One of TSBS's home engines. |
| Neo4j | `neo4j@sha256:1ee8f6fa…` (`2026.07.1-community`) | 2026.07.1 | graph, dense (its vector index, HNSW), cross-model | served | UNWIND batches over bolt. Dense queries use the Cypher 25 `SEARCH` clause; it has no candidate-count option and `LIMIT k` alone gave recall 0.50 at micro scale, so the adapter asks for `ef_search` (100) candidates and keeps the best k, the operating point every other engine runs at. |
| PostgreSQL + pgvector + Apache AGE | built image `dbbench:pg-age` (Dockerfile.pgage) FROM `pgvector/pgvector@sha256:dca0d688…` + `postgresql-17-age` from PGDG; both extension versions recorded on the row at connect | PostgreSQL 17.11 + pgvector 0.8.6 + AGE 1.7.0 | cross-model | served | COPY plus Cypher CREATE through AGE. The strongest "one engine" rival to the page's central claim. |
| ArangoDB | `arangodb@sha256:563cb2c0…` (`arangodb:3.12.11`; the image reports "enterprise", which since 3.12 is the one self-managed build). License BSL 1.1 per the repository's LICENSE at tag v3.12.11, so not open source; the page's license table says so | 3.12.11, RocksDB storage | documents (TPC), graph, dense, cross-model | served only: python-arango 8.3.5 is an HTTP client and the engine has no in-process mode | bulk import API in batches; the server runs `arangod --vector-index true`. Its vector index is FAISS IVF, matched by effect rather than by knob, and the seven `ivf_*` fields on the row make the operating point auditable (FAIRNESS.md F7). |

The composed cross-model stack (Qdrant + Neo4j) is not a pinned engine of its own: it is two of the rows above wired together, and it still carries the retired Neo4j 5-community pin until qDT re-runs it.

From 2026-10 every engine above that has a durability setting runs the relaxed commit class, read out of the engine and recorded on the row; FAIRNESS.md F10 holds the mapping and names the engines that cannot be relaxed.

**The two SurrealDB rows are two engines.** The embedded arm used one core on every lane measured, at about 1.0 to 1.3 processor seconds per elapsed second against 6.5 to 14.9 for its own server and 13.5 for ArcadeDB embedded, so its latencies are a single-threaded engine's and the page says so rather than reading them as the product's ceiling. Its core is a year older than the server's (core 2.3.10 against server 3.2.4, BUGS F39) and sits on a different store, so the two rows differ by version, store, and threading as well as by transport (DECISIONS #95). They also run different text for the triangle count, each the form that is fast on its own version (DECISIONS #93, FAIRNESS.md F4).

## October re-pins (DECISIONS #87, surveyed 2026-09-14)

Every comparator was checked against its own release feed, stable only, amd64, digests taken with `docker manifest inspect` and no pulls. The rule is latest stable, so the default is to take all of them, including the two major jumps, rather than choosing the versions that suit us.

**Moved, and re-pinned in October.** PostgreSQL 17.10 to 18.6 (or 17.11 if the line is held), Qdrant v1.18.2 to v1.19.1, Milvus v2.6.13 to v3.0.1, Elasticsearch 9.4.1 to 9.5.3 with the client to 9.5.1, LadybugDB 0.19.1 to 0.20.4, LanceDB 0.37.1 to 0.38.0, QuestDB 9.1.1 to 10.0.1, MongoDB 8.2.12 to 8.3.9, TimescaleDB 2.28.3 to 2.30.0, and Neo4j 2026.07.1 to 2026.08.1 with the driver to 6.3.0.

**Unmoved.** DuckDB 1.5.5, Chroma 1.5.9, sqlite-vec 0.1.9, SurrealDB SDK 2.0.0 and server v3.2.4, pgvector 0.8.6, Apache AGE 1.7.0 on PostgreSQL 17, and ArangoDB 3.12.11.

**Five need their own smoke before the chain starts**, each for a stated reason. QuestDB 10 makes the ILP ingest we use a legacy path beside its new binary protocol, and the smoke measures both so the arm is not left on the slower one out of habit. Milvus 3.0 must still boot as a single standalone container with embedded etcd, keep the segment-seal override as the same knob, and leave the sparse index at its pre-SINDI default unless we opt in, with v2.6.23 as a recorded fallback only if it cannot. PostgreSQL 18 carries pgvector, TimescaleDB, and the AGE image with it, turns data checksums on by default, and takes AGE from 1.7.0 to 1.8.0, so it is smoked as a set of four or the line is held at 17.11 and that is recorded. Neo4j's dense recall is a hand-built operating point and is re-measured rather than assumed. LadybugDB crosses five pre-1.0 releases that touched the COPY and projection paths the graph lane times. TimescaleDB 2.30 changes last-point query scaling, which is a TSBS query we run, so that row is expected to move on its merit and the page says why.

**Two pinning defects, fixed at the re-pin and not before**, because the client image is rebuilt by the queue scripts still running. The SQLite arm has no version pin at all: it uses the standard library of an unpinned `python:3.12-slim`, so a rebuild silently takes whatever Debian ships, and the frozen rows record 3.46.1 against upstream's 3.53.4. And `Dockerfile.pgage` installs `postgresql-17-age` unpinned while its header claims AGE 1.6.0 when the build produces 1.7.0.

## Retired pins

| Engine | Pin | Replaced by |
|---|---|---|
| Neo4j 5-community (5.26.28) | `neo4j@sha256:4bae36af…` | 2026.07.1 on every arm. The composed cross-model row is the last one still on it. |
| SurrealDB in memory (`mem://`) | `surrealdb==2.0.0` | the SDK's SurrealKV disk store |

Each row carries the digest it actually ran on, so a table can hold a mix while a re-run is queued (BUGS.md F32).

## Mode: server or embedded (Python)

Every comparator is one of two things, and the page's Mode column says which: a server in its own container, reached from the client container over the cell network; or an engine embedded in the Python client process. An engine that genuinely offers both gets both rows, as ArcadeDB does; SurrealDB is the one comparator that does.

Servers: PostgreSQL, pgvector, PG+AGE, TimescaleDB, MongoDB, Neo4j, Qdrant, Milvus, Elasticsearch, QuestDB, SurrealDB (served), and ArangoDB. Embedded: DuckDB, SQLite, LadybugDB, Chroma, LanceDB, sqlite-vec, and SurrealDB (SDK).

## Not added, and why

- OrientDB: ArcadeDB is its successor; not a live comparison.
- Cloud-only engines (Atlas-only features, Cosmos DB): cannot run in the envelope.
- MongoDB vector search: Community 8.2 needs the separate `mongot` process, a second container per cell, and the runner starts one server per cell. Deferred.
- MongoDB graph: `$graphLookup` is not a model MongoDB claims. Not measured.
- Repurposing a relational engine as a graph store, or the reverse, outside the cross-model transaction: out of scope (DECISIONS #68).

## Smoke before queueing

Every new adapter runs once on the laptop through the runner, against its pinned image, at a micro or sweep scale with one rep, before its queue script is written. The smoke proves the image, the adapter, the recorded schema, and the version string; nothing it produces is a page number, and every published row is re-measured on mini. The TPC adapters have no laptop corpus and are exercised by their queue script's first cell instead.

Laptop fixtures live in `~/bench-data`: `dense` is a 20k cut of SIFT1M, `dense1m` the full million with ground truth (`BENCH_DENSE_DATA=/data/dense1m` selects it). Mini holds its own copies.

**What durability costs, measured on the laptop skeleton.** Placeholders from a busy development machine, labelled as such: nothing here reaches the page, and the campaign's own rows replace them (DECISIONS #90).

Document insert, strict against relaxed: SQLite 69x (0.021 ms to 1.45 ms), ArcadeDB embedded 33.7x (0.217 to 7.31), PostgreSQL 16.3x (0.155 to 2.53), SurrealDB embedded 12.3x (0.584 to 7.18), MongoDB 4.1x (0.686 to 2.81), ArangoDB 4.0x (2.18 to 8.70), and ArcadeDB served 3.7x (2.47 to 9.19). Graph insert: SurrealDB embedded 10.5x, ArangoDB 3.6x, ArcadeDB embedded 3.5x, and ArcadeDB served 2.1x. Cross-model transaction: ArangoDB 1.4x, ArcadeDB served 1.2x, PostgreSQL with pgvector and AGE 1.2x, and ArcadeDB embedded 1.2x.

The pattern is the finding rather than any one number: the strict document inserts span 1.45 to 9.19 ms where the relaxed ones span 0.021 to 2.47, so waiting for the disk costs every engine about the same and the multiple is largest exactly where the relaxed path is fastest. PROTOCOL.md section 3 carries what follows from it for the write rows the page prints.

Smoke findings that changed an adapter are recorded in `.notes/bench/BUGS.md`, not here.
