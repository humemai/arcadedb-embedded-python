# Comparators: what runs against ArcadeDB, pinned

One row per engine. The digest is the amd64 manifest digest (`docker manifest inspect -v <tag>`), which is what `runner.BACKENDS` pins and what every row records under `server_image`; the tag beside it is for humans. Client-side packages are pinned in `build_images.sh` (`PKGS[client]`). The version a row publishes is what the engine reported at connect time, never the tag.

Which arms are on the page and which are still queued is PAGE-SPEC.md section 2; the queue chain is CAMPAIGN.md section 6. This file says only what each engine is pinned to and why it runs the way it does.

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
| MongoDB | `mongo@sha256:41afd6e1…` (`mongo:8.2.12`) | 8.2.12 | documents (TPC), time series (native time-series collection), graph | served | insert_many batches; single-node replica set, because TPC-C new-order needs a multi-document transaction. Client `pymongo==4.18.1`. The graph arm runs the SAME digest: chained `$lookup` for the fixed-depth hops, `$graphLookup` measured beside it, both core mongod. |
| MongoDB + MongoDB Search | built image `dbbench:mongo-search` (Dockerfile.mongosearch) FROM `mongo@sha256:41afd6e1…` + `mongodb/mongodb-community-search@sha256:63ebc805…`; both digests pinned in the Dockerfile | mongod 8.2.12 + mongot-community 1.70.4 | dense vectors, cross-model | served, one container holding both processes | `$vectorSearch` over a `vectorSearch` index at `hnswOptions.maxEdges`=16, `numEdgeCandidates`=100, stage `numCandidates`=100, i.e. the lane's matched point. mongod runs WITH access control, because mongot authenticates to its sync source with SCRAM and mongod authorizes it through the `searchCoordinator` role; the document arm above does not. Not `mongodb/mongodb-atlas-local`: MongoDB documents that image as "For evaluation only" and "not suitable for production use", and its vector-capable variant is a `:preview` tag. |
| pgvector | `pgvector/pgvector@sha256:dca0d688…` (`0.8.6-pg17`) | PostgreSQL 17 + pgvector 0.8.6 | dense (`vector`, HNSW m=16, ef_construction=100, ef_search=100), sparse (`sparsevec`, HNSW, inner product) | served | COPY, then HNSW build. `maintenance_work_mem` sized to the cell's cap for the build (resource fitting, disclosed). |
| TimescaleDB | `timescale/timescaledb@sha256:189fd482…` (`2.28.3-pg17`) | 2.28.3 on PostgreSQL 17 | time series (hypertable, `time_bucket`) | served | COPY into a hypertable, index on (host, ts). One of TSBS's home engines. |
| Neo4j | `neo4j@sha256:1ee8f6fa…` (`2026.07.1-community`) | 2026.07.1 | graph, dense (its vector index, HNSW), cross-model | served | UNWIND batches over bolt. Dense queries use the Cypher 25 `SEARCH` clause; it has no candidate-count option and `LIMIT k` alone gave recall 0.50 at micro scale, so the adapter asks for `ef_search` (100) candidates and keeps the best k, the operating point every other engine runs at. |
| PostgreSQL + pgvector + Apache AGE | built image `dbbench:pg-age` (Dockerfile.pgage) FROM `pgvector/pgvector@sha256:dca0d688…` + `postgresql-17-age` from PGDG; both extension versions recorded on the row at connect | PostgreSQL 17.11 + pgvector 0.8.6 + AGE 1.7.0 | cross-model | served | COPY plus Cypher CREATE through AGE. The strongest "one engine" rival to the page's central claim. |
| ArangoDB | `arangodb@sha256:563cb2c0…` (`arangodb:3.12.11`; the image reports "enterprise", which since 3.12 is the one self-managed build). License BSL 1.1 per the repository's LICENSE at tag v3.12.11, so not open source; the page's license table says so | 3.12.11, RocksDB storage | documents (TPC), graph, dense, cross-model | served only: python-arango 8.3.5 is an HTTP client and the engine has no in-process mode | bulk import API in batches; the server runs `arangod --vector-index true`. Its vector index is FAISS IVF, matched by effect rather than by knob, and the seven `ivf_*` fields on the row make the operating point auditable (FAIRNESS.md F7). |

The composed cross-model stack (Qdrant + Neo4j) is not a pinned engine of its own: it is two of the rows above wired together, and it still carries the retired Neo4j 5-community pin until qDT re-runs it.

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
| Neo4j 5-community (5.26.28) | `neo4j@sha256:4bae36af…` | 2026.07.1 on every arm. The composed cross-model row is the last one still on it. |
| SurrealDB in memory (`mem://`) | `surrealdb==2.0.0` | the SDK's SurrealKV disk store |

Each row carries the digest it actually ran on, so a table can hold a mix while a re-run is queued (BUGS.md F32).

## Mode: server or embedded (Python)

Every comparator is one of two things, and the page's Mode column says which: a server in its own container, reached from the client container over the cell network; or an engine embedded in the Python client process. An engine that genuinely offers both gets both rows, as ArcadeDB does; SurrealDB is the one comparator that does.

Servers: PostgreSQL, pgvector, PG+AGE, TimescaleDB, MongoDB, MongoDB + MongoDB Search, Neo4j, Qdrant, Milvus, Elasticsearch, QuestDB, SurrealDB (served), and ArangoDB. Embedded: DuckDB, SQLite, LadybugDB, Chroma, LanceDB, sqlite-vec, and SurrealDB (SDK).

## Not added, and why

- OrientDB: ArcadeDB is its successor; not a live comparison.
- Cloud-only engines (Atlas-only features, Cosmos DB): cannot run in the envelope.
- ~~MongoDB vector search~~ and ~~MongoDB graph~~: **both joined on 2026-09-15** and their rows are in the table above. The vector exclusion was "needs the separate `mongot` process, a second container per cell, and the runner starts one server per cell" — the pair runs in one container now, which is the deployment MongoDB's own default mongot config is written for, and MongoDB Search reached general availability for Community Edition on 2026-06-30. The graph exclusion was "`$graphLookup` is not a model MongoDB claims", which DECISIONS #92 does not accept as a reason: an engine competes in its own dialect if it can express the query. All twelve graph questions are expressible; the constructs and the two that needed care are in `.notes/bench/COMPARATOR-DIALECTS.md`.
- Repurposing a relational engine as a graph store, or the reverse, outside the cross-model transaction: out of scope (DECISIONS #68).

## Smoke before queueing

Every new adapter runs once on the laptop through the runner, against its pinned image, at a micro or sweep scale with one rep, before its queue script is written. The smoke proves the image, the adapter, the recorded schema, and the version string; nothing it produces is a page number, and every published row is re-measured on mini. The TPC adapters have no laptop corpus and are exercised by their queue script's first cell instead.

Laptop fixtures live in `~/bench-data`: `dense` is a 20k cut of SIFT1M, `dense1m` the full million with ground truth (`BENCH_DENSE_DATA=/data/dense1m` selects it). Mini holds its own copies.

Smoke findings that changed an adapter are recorded in `.notes/bench/BUGS.md`, not here.
