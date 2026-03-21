# Benchmarking DBs

## ArcadeDB: current problems and likely improvements

Based on the benchmark results in this document, the main ArcadeDB bottlenecks are:

- Vector indexing is currently the biggest problem. The build path is far slower than
  the other vector backends, and the large Stack Overflow run did not finish within the
  practical time budget. This is gonna be hard to improve, since its mainly due to the
  JVector library problem.
- Vector search is also not yet competitive enough: ArcadeDB currently trails the
  stronger ANN backends on both latency and recall in these runs.
- OLAP query execution is generally too slow, even after ingest and indexing have
  completed. This is understandable for an OLTP-oriented engine, but the gap is still
  larger than it should be relative to other OLTP or mixed-workload systems.
- Index creation in general is expensive, not just for vectors. Table and graph runs
  show that post-load indexing often consumes a disproportionate share of total runtime.
  some regress, which suggests shared contention or execution-path bottlenecks.

## Dataset overview

The Stack Overflow dataset is used in two different shapes across these benchmarks:

- Table benchmarks (Examples 07 and 08) load 8 XML tables: `Users`, `Posts`,
  `Comments`, `Badges`, `Votes`, `PostLinks`, `Tags`, and `PostHistory`.
- Graph benchmarks (Examples 09 and 10) derive a property graph from the XML sources
  with 6 vertex types and 9 edge types.
- This graph workload is still relatively simple: it is useful for ingestion,
  neighborhood traversal, and basic analytical queries, but it does not yet stress
  deeper multi-hop traversals or richer relationship patterns. Future benchmark work
  should add more complex graph datasets with longer paths, denser connectivity, and
  more heterogeneous relationship structures.

Graph schema used by Examples 09 and 10:

- Vertex types: `User`, `Question`, `Answer`, `Tag`, `Badge`, `Comment`
- Edge types: `ASKED`, `ANSWERED`, `HAS_ANSWER`, `ACCEPTED_ANSWER`,
  `TAGGED_WITH`, `COMMENTED_ON`, `COMMENTED_ON_ANSWER`, `EARNED`, `LINKED_TO`

Vector corpus used by Examples 11 and 12:

- Vectors are built from Stack Overflow questions, answers, and comments.
- Questions embed `Title + Body`; answers embed `Body`; comments embed `Text` after
  HTML stripping and whitespace normalization.
- The default embedding model is `all-MiniLM-L6-v2`, which yields normalized
  384-dimensional `float32` vectors; long texts are truncated to the model's max
  sequence length.
- Vectors are written as `.f32` shards with a default shard size of 100,000
  vectors, alongside per-corpus and combined ids/meta files.
- An exact ground-truth file is also built for the combined corpus from 1,000
  sampled queries with top-50 neighbors.

**stackoverflow-large**

- User: 661,594
- Post: 2,738,307
- Comment: 2,723,828
- Badge: 1,657,162
- Vote: 7,691,408
- PostLink: 204,690
- Tag: 1,925
- PostHistory: 6,970,840
- Total: 22,649,754
- Dataset size (except vectors) on disk: ~10 GB
- Vector size on disk: 8.8 GB
- Num vectors: 5,461,227

## Things to note

- Everything was run in Docker (AMD Ryzen 9 7950X 16-Core Processor, 128GB DDR5 RAM, 2TB
  NVMe SSD).
- Some rows have higher memory limit than the others, because they ran out of memory at
  lower limits.
- Some dbs are embedded, while some are client-server architecture, so we had to
  distribute the memory limit across client (20%) and server (80%) for the latter. The
  `rss_peak_mib` column includes combined client and server RSS for client-server
  backends.
- This README keeps only high-level environment/version notes; full digests, wheel
  filenames, and per-run provenance stay in the raw run artifacts and section summaries.
- This README now mixes benchmark snapshots on purpose: Examples 07-10 include ArcadeDB
  refreshes from 21-Mar-2026, while non-ArcadeDB rows in those sections remain from the
  earlier full-matrix runs on 13-Mar-2026 unless explicitly replaced below. Examples 11
  and 12 remain from 17-Mar-2026.

## 07_stackoverflow_tables_oltp

- ArcadeDB rows refreshed (UTC): 21-Mar-2026 09:58:09 UTC
- Non-ArcadeDB rows below remain from the full comparison run generated at
  13-Mar-2026 16:19:52 UTC.
- Environment: refreshed ArcadeDB rows use tag `26.4.1-SNAPSHOT` and local wheel version
  `26.4.1.dev0`; DuckDB `1.5.0`; PostgreSQL `18.3`; SQLite `3.46.1` rows shown below are
  unchanged from the earlier full-matrix run.
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

### Dataset: stackoverflow-large

| db           | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib     |
| ------------ | ------- | ------------ | ---------- | --------- | ------------------ | -------------- | ------------ | ---------------- | ------------ | ------ | ------------ | ---------- |
| arcadedb_sql | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 857.024        | 961.97       | 633.084          | 394.892      | 15.669 | 7,594.062    | 8,756.41   |
| arcadedb_sql | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 463.906        | 866.117      | 469.48           | 532.504      | 42.117 | 7,197.27     | 8,756.41   |
| duckdb       | 1       | 250,000      | 10,000     | 16g       | 22,649,754         | 366.548        | 0            | 2,460.172        | 101.619      | 25.998 | 11,140.641   | 17,542.738 |
| duckdb       | 4       | 250,000      | 10,000     | 16g       | 22,649,754         | 327.309        | 0            | 867.823          | 288.077      | 41.742 | 10,199.543   | 17,550.246 |
| postgresql   | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 481.035        | 20.464       | 892.934          | 279.976      | 13.532 | 4,480.379    | 15,866.668 |
| postgresql   | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 692.841        | 21.379       | 538.551          | 464.209      | 31.753 | 4,834.102    | 15,866.727 |
| sqlite       | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 1,056.041      | 23.305       | 296.355          | 843.583      | 6.363  | 954.805      | 8,547.223  |
| sqlite       | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 1,111.745      | 31.095       | 352.575          | 709.069      | 29.073 | 957.941      | 8,547.137  |

## 08_stackoverflow_tables_olap

- ArcadeDB rows refreshed (UTC): 21-Mar-2026 09:58:09 UTC
- Non-ArcadeDB rows below remain from the full comparison run generated at
  13-Mar-2026 16:19:52 UTC.
- Environment: refreshed ArcadeDB rows use tag `26.4.1-SNAPSHOT` and local wheel version
  `26.4.1.dev0`; DuckDB `1.5.0`; PostgreSQL `18.3`; SQLite `3.46.1` rows shown below are
  unchanged from the earlier full-matrix run.
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.
- 10 OLAP queries are asked 100 times each; resulting in 1,000 queries in total.

### Dataset: stackoverflow-large

| db           | batch_size | mem_limit | threads | query_runs | ingest_mode       |  load_s |  index_s |    query_s | rss_peak_mib |     du_mib |
| ------------ | ---------: | --------- | ------: | ---------: | ----------------- | ------: | -------: | ---------: | -----------: | ---------: |
| arcadedb_sql |     10,000 | 8g        |       1 |        100 | bulk_tuned_insert | 746.905 | 1,067.28 | 12,141.284 |    6,892.363 |  8,947.773 |
| arcadedb_sql |     10,000 | 8g        |       4 |        100 | bulk_tuned_insert | 430.836 |  873.472 | 13,620.748 |    7,052.184 |  8,947.773 |
| duckdb       |     10,000 | 8g        |       1 |        100 | copy_csv          | 507.563 |        0 |      17.46 |    6,414.094 | 17,541.422 |
| duckdb       |     10,000 | 8g        |       4 |        100 | copy_csv          | 494.861 |        0 |      5.628 |    8,016.219 | 17,538.676 |
| postgresql   |     10,000 | 8g        |       1 |        100 | copy_from_stdin   | 584.426 |   46.119 |    376.271 |    3,494.324 | 16,071.297 |
| postgresql   |     10,000 | 8g        |       4 |        100 | copy_from_stdin   | 496.397 |   30.609 |    114.205 |    2,634.801 | 16,071.211 |
| sqlite       |     10,000 | 8g        |       1 |        100 | executemany       | 237.635 |   40.862 |    270.244 |      848.434 |  8,829.914 |
| sqlite       |     10,000 | 8g        |       4 |        100 | executemany       | 267.511 |   43.902 |    302.047 |      845.719 |  8,829.918 |

## 09_stackoverflow_graph_oltp

- ArcadeDB rows refreshed (UTC): 21-Mar-2026 09:58:09 UTC
- Non-ArcadeDB rows below remain from the full comparison run generated at
  13-Mar-2026 16:19:53 UTC.
- Environment: refreshed ArcadeDB rows use tag `26.4.1-SNAPSHOT` and local wheel version
  `26.4.1.dev0`; Ladybug `0.15.1`; DuckDB `1.5.0`; SQLite `3.46.1` rows shown below are
  unchanged from the earlier full-matrix run.
- Run status files for the 21-Mar-2026 ArcadeDB refresh: total=15, success=6, failed=9
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

### Dataset: stackoverflow-large

| db              | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib     |
| --------------- | ------- | ------------ | ---------- | --------- | --------------- | --------------- | ------------ | ----------- | ------------- | ---------------- | ------------ | ------ | ------------ | ---------- |
| arcadedb_cypher | 1       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 149.889      | 6,914.567   | 0.001         | 666.779          | 374.937      | 6.213  | 17,154.641   | 3,972.059  |
| arcadedb_cypher | 4       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 135.821      | 6,789.425   | 0.002         | 356.979          | 700.321      | 19.377 | 20,666.551   | 12,753.051 |
| duckdb          | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 0            | 318.645     | 0.185         | 1,632.358        | 153.153      | 27.432 | 7,547.707    | 6,959.012  |
| duckdb          | 1       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0            | 349.088     | 0.186         | 1,627.595        | 153.601      | 27.273 | 7,613.152    | 6,960.762  |
| duckdb          | 4       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0            | 355.896     | 0.183         | 1,049.554        | 238.196      | 55.926 | 7,122.297    | 6,970.262  |
| ladybug         | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       |              | 350.137     | 1.09          | 5,028.21         | 49.719       | 84.881 | 11,859.805   | 6,104.633  |
| python_memory   | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 0            | 158.887     | 1.419         | 13,752.43        | 18.179       | 181.45 | 9,033.387    | 3,002.098  |
| sqlite          | 1       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0.001        | 324.433     | 4.797         | 176.24           | 1,418.523    | 0.117  | 730.355      | 3,465.57   |
| sqlite          | 4       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0.001        | 272.435     | 0.951         | 141.632          | 1,765.143    | 1.112  | 739.402      | 3,465.59   |

## 10_stackoverflow_graph_olap

- ArcadeDB rows refreshed (UTC): 21-Mar-2026 09:58:09 UTC
- Label prefix: sweep10
- Total result files for the 21-Mar-2026 ArcadeDB refresh: 3
- Non-ArcadeDB rows below remain from the full comparison run generated at
  13-Mar-2026 16:19:53 UTC.
- Environment: refreshed ArcadeDB rows use tag `26.4.1-SNAPSHOT` and local wheel version
  `26.4.1.dev0`; Ladybug `0.15.1`; DuckDB `1.5.0`; SQLite `3.46.1` rows shown below are
  unchanged from the earlier full-matrix run.
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.
- 10 OLAP queries are asked 100 times each; resulting in 1,000 queries in total.

### Dataset: stackoverflow-large

| db              | batch_size | mem_limit | threads | query_runs |    load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| --------------- | ---------: | --------- | ------: | ---------: | --------: | ------: | --------: | -----------: | --------: |
| arcadedb_cypher |     10,000 | 32g       |       1 |        100 | 5,275.918 | 124.897 | 3,579.275 |    19,691.93 | 3,968.625 |
| arcadedb_cypher |     10,000 | 32g       |       4 |        100 | 4,213.075 | 118.659 | 3,080.738 |   22,526.727 | 12,750.77 |
| duckdb          |     10,000 | 8g        |       1 |        100 |   345.179 |       0 |   146.277 |    3,556.844 | 6,837.289 |
| duckdb          |     10,000 | 8g        |       4 |        100 |   341.622 |       0 |    54.812 |    4,303.328 | 6,833.793 |
| ladybug         |     10,000 | 8g        |       1 |        100 |   477.448 |       0 |   919.989 |    5,561.555 | 5,828.738 |
| ladybug         |     10,000 | 8g        |       4 |        100 |   401.242 |       0 |   250.289 |    5,563.523 | 5,829.312 |
| python_memory   |     10,000 | 16g       |       1 |        100 |   186.921 |       0 | 6,175.329 |   10,109.664 | 3,029.844 |
| sqlite          |     10,000 | 8g        |       1 |        100 |   246.934 |   0.001 | 1,185.689 |    1,240.238 | 3,465.602 |
| sqlite          |     10,000 | 8g        |       4 |        100 |    262.08 |   0.001 | 1,118.734 |    1,240.004 | 3,465.602 |

## 11_vector_index_build

- Generated (UTC): 2026-03-17T09:30:29Z
- Environment: ArcadeDB `26.4.1.dev0` on tag `26.4.1-SNAPSHOT`; Faiss `1.13.2`;
  LanceDB `0.29.2`; Milvus `2.6.10`; Postgres `18.3`; Qdrant `1.11.3`.
- Run status files: total=12, success=12, failed=0
- Note: LanceDB prefers pure `HNSW` when supported by the installed version; otherwise
  it falls back to single-partition `IVF_HNSW_SQ`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%;
  pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB
  single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

### Dataset: stackoverflow-large

| backend  | mem_limit | threads | batch_size | count     | rows      | run_total_s | create_db_s | create_index_s | ingest_s  | close_db_s | peak_rss_mib | db_size_mib | du_mib     |
| -------- | --------- | ------- | ---------- | --------- | --------- | ----------- | ----------- | -------------- | --------- | ---------- | ------------ | ----------- | ---------- |
| faiss    | 16g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 1,301.365   | 0           | 0              | 1,292.334 | 8.923      | 9,220.664    | 8,792.933   | 8,792.957  |
| lancedb  | 16g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 458.75      | 0.002       | 295.195        | 162.586   | 0          | 5,189.641    | 11,082.237  | 11,086.367 |
| milvus   | 16g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 573.837     | 0.223       | 0.786          | 558.145   | 0.225      | 2,098.781    | 28,504.65   | 28,593.508 |
| pgvector | 16g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 10,678.269  | 0.006       | 9,936.255      | 738.916   | 0.003      | 14,499.773   | 20,347.128  | 20,347.441 |
| qdrant   | 16g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 1,513.433   | 0.168       | 0.276          | 1,509.315 | 0.044      | 10,659.523   | 9,341.247   | 9,286.531  |

## 12_vector_search

- Generated (UTC): 2026-03-17T09:30:30Z
- Environment: ArcadeDB `26.4.1.dev0` on tag `26.4.1-SNAPSHOT`; Faiss `1.13.2`;
  LanceDB `0.29.2` and `0.30.0`; Milvus `2.6.10`; Postgres `18.3`; Qdrant `1.11.3`.
- Search run status files: total=12, success=12, failed=0
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the
  Example 11 build label for the reused DB directory.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the
  single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%;
  pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB
  single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.
- topk=50
- Don't take recall too seriously here, the HNSW params are not all apples-to-apples here.

### Dataset: stackoverflow-large

| backend    | mem_limit | k   | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib     |
| ---------- | --------- | --- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ | ---------- |
| bruteforce | 16g       | 50  | 1,000   | 1           | 630.619         | 704.747        | 692.107     | 61.348    | 630.694  | 0          | 8,100.863    | 0.02       |
| faiss      | 16g       | 50  | 1,000   | 0.756       | 14.154          | 78.142         | 20.401      | 5.718     | 14.305   | 0          | 9,084.387    | 8,792.977  |
| lancedb    | 16g       | 50  | 1,000   | 0.944       | 23.602          | 10.801         | 24.701      | 0.003     | 23.66    | 0          | 7,709.438    | 11,086.387 |
| qdrant     | 16g       | 50  | 1,000   | 0.985       | 55.218          | 58.914         | 79.45       | 0.166     | 55.326   | 0.046      | 9,519.699    | 8,888.848  |
