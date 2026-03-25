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

**stackoverflow-medium**

- User: 345,754
- Post: 425,735
- Comment: 819,648
- Badge: 612,258
- Vote: 1,747,225
- PostLink: 86,919
- Tag: 1,612
- PostHistory: 1,525,713
- Total: 5,564,864
- Dataset size (except vectors) on disk: ~2.9 GB
- Vector size on disk: 2.0 GB
- Num vectors: 1,242,391

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

## 07_stackoverflow_tables_oltp

- Generated (UTC): 2026-03-13T16:19:52Z
- Environment: ArcadeDB tags `26.3.1` and `26.4.1-SNAPSHOT`; local wheel versions
  `26.3.1` and `26.4.1.dev0`; DuckDB `1.5.0`; PostgreSQL `18.3`; SQLite `3.46.1`.
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

### stackoverflow-medium

| db           | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib    |
| ------------ | ------- | ------------ | ---------- | --------- | ------------------ | -------------- | ------------ | ---------------- | ------------ | ------ | ------------ | --------- |
| arcadedb_sql | 1       | 100,000      | 5,000      | 4g        | 5,564,864          | 191.453        | 76.561       | 100.717          | 992.886      | 4.108  | 2,804.426    | 2,658.895 |
| arcadedb_sql | 4       | 100,000      | 5,000      | 4g        | 5,564,864          | 178.934        | 74.496       | 94.371           | 1,059.644    | 19.087 | 2,251.84     | 2,658.906 |
| duckdb       | 1       | 100,000      | 5,000      | 8g        | 5,564,864          | 127.323        | 0            | 779.855          | 128.229      | 23.512 | 3,977.531    | 5,137.238 |
| duckdb       | 4       | 100,000      | 5,000      | 8g        | 5,564,864          | 122.766        | 0            | 494.969          | 202.033      | 51.373 | 3,614.258    | 5,137.484 |
| postgresql   | 1       | 100,000      | 5,000      | 4g        | 5,564,864          | 189.095        | 6.889        | 249.835          | 400.263      | 9.175  | 2,537.426    | 5,447.93  |
| postgresql   | 4       | 100,000      | 5,000      | 4g        | 5,564,864          | 173.783        | 7.312        | 199.35           | 501.629      | 25.933 | 3,129.203    | 5,447.785 |
| sqlite       | 1       | 100,000      | 5,000      | 4g        | 5,564,864          | 195.975        | 6.164        | 34.204           | 2,923.641    | 2.124  | 266.543      | 2,691.812 |
| sqlite       | 4       | 100,000      | 5,000      | 4g        | 5,564,864          | 292.576        | 3.124        | 53.728           | 1,861.229    | 8.542  | 271.988      | 2,691.754 |

### Dataset: stackoverflow-large

| db           | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib     |
| ------------ | ------- | ------------ | ---------- | --------- | ------------------ | -------------- | ------------ | ---------------- | ------------ | ------ | ------------ | ---------- |
| arcadedb_sql | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 796.361        | 1,569.766    | 678.86           | 368.265      | 17.334 | 7,638.836    | 8,718.844  |
| arcadedb_sql | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 802.131        | 1,269.759    | 541.62           | 461.578      | 47.908 | 5,122.672    | 8,718.848  |
| arcadedb_sql | 8       | 250,000      | 10,000     | 8g        | 22,649,754         | 782.192        | 1,220.134    | 531.053          | 470.763      | 81.202 | 4,749.086    | 8,718.906  |
| duckdb       | 1       | 250,000      | 10,000     | 16g       | 22,649,754         | 366.548        | 0            | 2,460.172        | 101.619      | 25.998 | 11,140.641   | 17,542.738 |
| duckdb       | 4       | 250,000      | 10,000     | 16g       | 22,649,754         | 327.309        | 0            | 867.823          | 288.077      | 41.742 | 10,199.543   | 17,550.246 |
| duckdb       | 8       | 250,000      | 10,000     | 16g       | 22,649,754         | 370.773        | 0            | 1,024.621        | 243.993      | 86.57  | 9,613.008    | 17,550.512 |
| postgresql   | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 481.035        | 20.464       | 892.934          | 279.976      | 13.532 | 4,480.379    | 15,866.668 |
| postgresql   | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 692.841        | 21.379       | 538.551          | 464.209      | 31.753 | 4,834.102    | 15,866.727 |
| postgresql   | 8       | 250,000      | 10,000     | 8g        | 22,649,754         | 631.205        | 26.091       | 439.911          | 568.296      | 46.323 | 5,426.539    | 15,866.953 |
| sqlite       | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 1,056.041      | 23.305       | 296.355          | 843.583      | 6.363  | 954.805      | 8,547.223  |
| sqlite       | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 1,111.745      | 31.095       | 352.575          | 709.069      | 29.073 | 957.941      | 8,547.137  |
| sqlite       | 8       | 250,000      | 10,000     | 8g        | 22,649,754         | 1,101.288      | 39.955       | 352.077          | 710.073      | 38.31  | 1,014.34     | 8,547.211  |

## 08_stackoverflow_tables_olap

- Generated (UTC): 2026-03-13T16:19:52Z
- Environment: ArcadeDB tag `26.4.1-SNAPSHOT`; local wheel version `26.4.1.dev0`;
  DuckDB `1.5.0`; PostgreSQL `18.3`; SQLite `3.46.1`.
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.
- 10 OLAP queries are asked 100 times each; resulting in 1,000 queries in total.

### Dataset: stackoverflow-medium

| db           | batch_size | mem_limit | threads | query_runs | ingest_mode       |  load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| ------------ | ---------: | --------- | ------: | ---------: | ----------------- | ------: | ------: | --------: | -----------: | --------: |
| arcadedb_sql |      5,000 | 4g        |       1 |        100 | bulk_tuned_insert | 172.945 |  86.463 | 4,528.169 |    3,455.598 | 2,694.016 |
| arcadedb_sql |      5,000 | 4g        |       4 |        100 | bulk_tuned_insert | 161.579 |  74.509 | 2,762.007 |     3,341.48 | 2,694.008 |
| arcadedb_sql |      5,000 | 8g        |       4 |        100 | bulk_tuned_insert | 167.464 |  73.148 |   924.121 |    6,241.055 | 2,694.016 |
| duckdb       |      5,000 | 4g        |       1 |        100 | copy_csv          | 139.812 |       0 |     3.237 |    2,372.527 | 5,133.613 |
| duckdb       |      5,000 | 4g        |       4 |        100 | copy_csv          | 130.349 |       0 |     2.125 |    2,765.754 | 5,137.113 |
| duckdb       |      5,000 | 8g        |       1 |        100 | copy_csv          | 123.204 |       0 |     3.262 |    2,373.992 | 5,132.867 |
| postgresql   |      5,000 | 4g        |       1 |        100 | copy_from_stdin   | 170.231 |  18.198 |   188.183 |    2,395.047 | 5,494.469 |
| postgresql   |      5,000 | 4g        |       4 |        100 | copy_from_stdin   | 172.095 |  11.786 |     36.58 |    2,306.328 | 5,494.352 |
| sqlite       |      5,000 | 4g        |       1 |        100 | executemany       |  54.596 |   6.475 |    56.463 |      574.754 |  2,759.66 |
| sqlite       |      5,000 | 4g        |       4 |        100 | executemany       |  61.087 |   7.616 |    60.118 |      574.055 | 2,759.723 |
| sqlite       |      5,000 | 8g        |       1 |        100 | executemany       |  69.526 |    6.73 |    56.324 |      574.578 | 2,759.664 |

### Dataset: stackoverflow-large

| db           | batch_size | mem_limit | threads | query_runs | ingest_mode       |  load_s |   index_s |    query_s | rss_peak_mib |     du_mib |
| ------------ | ---------: | --------- | ------: | ---------: | ----------------- | ------: | --------: | ---------: | -----------: | ---------: |
| arcadedb_sql |     10,000 | 8g        |       1 |        100 | bulk_tuned_insert | 713.583 | 1,531.178 | 15,768.988 |    6,771.938 |  8,863.953 |
| arcadedb_sql |     10,000 | 8g        |       4 |        100 | bulk_tuned_insert |  766.93 | 1,560.059 | 16,645.468 |    6,438.742 |  8,863.945 |
| arcadedb_sql |     10,000 | 8g        |       8 |        100 | bulk_tuned_insert | 815.177 | 1,580.613 | 15,710.747 |    6,938.078 |  8,863.945 |
| duckdb       |     10,000 | 8g        |       1 |        100 | copy_csv          | 507.563 |         0 |      17.46 |    6,414.094 | 17,541.422 |
| duckdb       |     10,000 | 8g        |       4 |        100 | copy_csv          | 494.861 |         0 |      5.628 |    8,016.219 | 17,538.676 |
| duckdb       |     10,000 | 8g        |       8 |        100 | copy_csv          | 496.671 |         0 |      4.037 |    7,747.883 | 17,537.418 |
| postgresql   |     10,000 | 8g        |       1 |        100 | copy_from_stdin   | 584.426 |    46.119 |    376.271 |    3,494.324 | 16,071.297 |
| postgresql   |     10,000 | 8g        |       4 |        100 | copy_from_stdin   | 496.397 |    30.609 |    114.205 |    2,634.801 | 16,071.211 |
| postgresql   |     10,000 | 8g        |       8 |        100 | copy_from_stdin   | 504.869 |     38.45 |    115.498 |    2,742.203 | 16,071.254 |
| sqlite       |     10,000 | 8g        |       1 |        100 | executemany       | 237.635 |    40.862 |    270.244 |      848.434 |  8,829.914 |
| sqlite       |     10,000 | 8g        |       4 |        100 | executemany       | 267.511 |    43.902 |    302.047 |      845.719 |  8,829.918 |
| sqlite       |     10,000 | 8g        |       8 |        100 | executemany       | 274.191 |    48.518 |    319.653 |      847.277 |  8,829.918 |

## 09_stackoverflow_graph_oltp

- Generated (UTC): 2026-03-13T16:19:53Z
- Environment: ArcadeDB tags `26.3.1` and `26.4.1-SNAPSHOT`; local wheel versions
  `26.3.1` and `26.4.1.dev0`; Ladybug `0.15.1`; DuckDB `1.5.0`; SQLite `3.46.1`.
- Run status files: total=56, success=28, failed=28
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

### Dataset: stackoverflow-medium

| db              | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms  | rss_peak_mib | du_mib    |
| --------------- | ------- | ------------ | ---------- | --------- | --------------- | --------------- | ------------ | ----------- | ------------- | ---------------- | ------------ | ------- | ------------ | --------- |
| arcadedb_cypher | 1       | 100,000      | 5,000      | 8g        | 2,202,019       | 2,877,037       | 19.887       | 660.884     | 0.001         | 201.595          | 496.045      | 4.622   | 7,339.707    | 1,247.484 |
| arcadedb_cypher | 4       | 100,000      | 5,000      | 8g        | 2,202,019       | 2,877,037       | 11.554       | 850.308     | 0.001         | 157.169          | 636.258      | 12.932  | 6,143.281    | 1,247.477 |
| arcadedb_sql    | 1       | 100,000      | 5,000      | 8g        | 2,202,019       | 2,877,037       | 22.426       | 699.452     | 0.003         | 81.893           | 1,221.101    | 3.138   | 7,861.051    | 1,247.598 |
| duckdb          | 1       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0            | 94.573      | 0.072         | 791.608          | 126.325      | 36.144  | 3,498.746    | 1,966.168 |
| duckdb          | 1       | 100,000      | 5,000      | 8g        | 2,202,019       | 2,877,037       | 0            | 79.227      | 0.088         | 793.931          | 125.956      | 36.089  | 3,491.52     | 1,965.922 |
| duckdb          | 4       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0            | 102.99      | 0.09          | 490.868          | 203.721      | 70.884  | 3,219.801    | 1,966.426 |
| ladybug         | 1       | 100,000      | 5,000      | 8g        | 2,202,019       | 2,877,037       |              | 121.483     | 0.168         | 1,920.342        | 52.074       | 71.822  | 5,228.199    | 1,959.586 |
| python_memory   | 1       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0            | 34.221      | 0.499         | 1,804.339        | 55.422       | 65.018  | 2,733.129    | 935.566   |
| python_memory   | 4       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0            | 42.666      | 0.48          | 2,387.573        | 41.884       | 322.502 | 2,732.168    | 936.562   |
| sqlite          | 1       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0.001        | 75.524      | 0.218         | 21.35            | 4,683.876    | 0.055   | 257.527      | 1,079.727 |
| sqlite          | 4       | 100,000      | 5,000      | 4g        | 2,202,019       | 2,877,037       | 0.001        | 84.285      | 0.235         | 38.45            | 2,600.794    | 0.097   | 265.406      | 1,079.719 |

### Dataset: stackoverflow-large

| db              | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms  | rss_peak_mib | du_mib    |
| --------------- | ------- | ------------ | ---------- | --------- | --------------- | --------------- | ------------ | ----------- | ------------- | ---------------- | ------------ | ------- | ------------ | --------- |
| arcadedb_cypher | 1       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 168.972      | 6,434.854   | 0.001         | 483.19           | 517.395      | 3.098   | 18,639.383   | 4,057.113 |
| arcadedb_cypher | 4       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 131.732      | 5,707.357   | 0.002         | 455.198          | 549.212      | 22.64   | 15,344.52    | 4,057.117 |
| arcadedb_cypher | 8       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 136.272      | 6,441.466   | 0.001         | 392.245          | 637.357      | 34.938  | 13,287.195   | 4,057.117 |
| duckdb          | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 0            | 318.645     | 0.185         | 1,632.358        | 153.153      | 27.432  | 7,547.707    | 6,959.012 |
| duckdb          | 1       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0            | 349.088     | 0.186         | 1,627.595        | 153.601      | 27.273  | 7,613.152    | 6,960.762 |
| duckdb          | 4       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0            | 355.896     | 0.183         | 1,049.554        | 238.196      | 55.926  | 7,122.297    | 6,970.262 |
| duckdb          | 8       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0            | 368.718     | 0.172         | 1,025.813        | 243.709      | 114.924 | 7,194.75     | 6,969.773 |
| ladybug         | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       |              | 350.137     | 1.09          | 5,028.21         | 49.719       | 84.881  | 11,859.805   | 6,104.633 |
| python_memory   | 1       | 250,000      | 10,000     | 16g       | 7,782,816       | 9,770,001       | 0            | 158.887     | 1.419         | 13,752.43        | 18.179       | 181.45  | 9,033.387    | 3,002.098 |
| sqlite          | 1       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0.001        | 324.433     | 4.797         | 176.24           | 1,418.523    | 0.117   | 730.355      | 3,465.57  |
| sqlite          | 4       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0.001        | 272.435     | 0.951         | 141.632          | 1,765.143    | 1.112   | 739.402      | 3,465.59  |
| sqlite          | 8       | 250,000      | 10,000     | 8g        | 7,782,816       | 9,770,001       | 0.001        | 248.3       | 0.791         | 127.271          | 1,964.32     | 3.2     | 748.355      | 3,465.574 |

## 10_stackoverflow_graph_olap

- Generated (UTC): 2026-03-13T16:19:53Z
- Label prefix: sweep10
- Total result files: 26
- Environment: ArcadeDB tag `26.4.1-SNAPSHOT`; local wheel version `26.4.1.dev0`;
  Ladybug `0.15.1`; DuckDB `1.5.0`; SQLite `3.46.1`.
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.
- 10 OLAP queries are asked 100 times each; resulting in 1,000 queries in total.

### Dataset: stackoverflow-medium

| db              | batch_size | mem_limit | threads | query_runs |    load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| --------------- | ---------: | --------- | ------: | ---------: | --------: | ------: | --------: | -----------: | --------: |
| arcadedb_cypher |      5,000 | 8g        |       1 |        100 | 1,368.763 |  17.519 | 1,481.209 |    8,048.605 |           |
| arcadedb_cypher |      5,000 | 8g        |       4 |        100 |  1,244.19 |  11.243 |  1,312.03 |    5,875.602 |           |
| duckdb          |      5,000 | 4g        |       1 |        100 |    95.507 |       0 |    31.761 |    1,317.355 | 1,961.957 |
| duckdb          |     10,000 | 8g        |       1 |        100 |     82.54 |       0 |    32.258 |    1,391.656 | 1,962.203 |
| duckdb          |      5,000 | 4g        |       4 |        100 |    86.968 |       0 |    18.851 |    1,445.141 | 1,962.699 |
| ladybug         |      5,000 | 4g        |       1 |        100 |   105.383 |       0 |    288.42 |    2,902.891 | 1,818.285 |
| ladybug         |      5,000 | 4g        |       4 |        100 |    90.657 |       0 |    98.664 |    2,888.902 | 1,818.309 |
| python_memory   |      5,000 | 4g        |       1 |        100 |    34.663 |       0 |   908.991 |    2,986.238 |   942.723 |
| python_memory   |      5,000 | 4g        |       4 |        100 |    36.313 |       0 |   901.499 |    2,985.785 |   942.723 |
| sqlite          |      5,000 | 4g        |       1 |        100 |    55.976 |   0.001 |   403.322 |      639.988 | 1,107.266 |
| sqlite          |      5,000 | 4g        |       4 |        100 |    58.716 |   0.001 |   406.361 |       639.77 | 1,107.266 |

### Dataset: stackoverflow-large

| db              | batch_size | mem_limit | threads | query_runs |    load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| --------------- | ---------: | --------- | ------: | ---------: | --------: | ------: | --------: | -----------: | --------: |
| arcadedb_cypher |     10,000 | 32g       |       1 |        100 | 6,787.391 | 175.501 | 3,976.375 |   30,332.566 | 4,039.594 |
| arcadedb_cypher |     10,000 | 32g       |       4 |        100 | 7,420.009 | 148.152 | 4,679.181 |   14,860.934 | 4,039.594 |
| arcadedb_cypher |     10,000 | 32g       |       8 |        100 | 6,149.502 | 128.021 | 4,003.029 |   14,603.973 | 4,039.586 |
| duckdb          |     10,000 | 8g        |       1 |        100 |   345.179 |       0 |   146.277 |    3,556.844 | 6,837.289 |
| duckdb          |     10,000 | 8g        |       4 |        100 |   341.622 |       0 |    54.812 |    4,303.328 | 6,833.793 |
| duckdb          |     10,000 | 8g        |       8 |        100 |   410.947 |       0 |    43.968 |    4,315.812 | 6,832.289 |
| ladybug         |     10,000 | 8g        |       1 |        100 |   477.448 |       0 |   919.989 |    5,561.555 | 5,828.738 |
| ladybug         |     10,000 | 8g        |       4 |        100 |   401.242 |       0 |   250.289 |    5,563.523 | 5,829.312 |
| ladybug         |     10,000 | 8g        |       8 |        100 |   422.852 |       0 |   139.157 |    5,428.852 | 5,828.918 |
| python_memory   |     10,000 | 16g       |       1 |        100 |   186.921 |       0 | 6,175.329 |   10,109.664 | 3,029.844 |
| sqlite          |     10,000 | 8g        |       1 |        100 |   246.934 |   0.001 | 1,185.689 |    1,240.238 | 3,465.602 |
| sqlite          |     10,000 | 8g        |       4 |        100 |    262.08 |   0.001 | 1,118.734 |    1,240.004 | 3,465.602 |
| sqlite          |     10,000 | 8g        |       8 |        100 |   257.276 |   0.001 | 1,174.008 |    1,240.457 | 3,465.605 |

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

### Dataset: stackoverflow-medium

| backend      | mem_limit | threads | batch_size | count     | rows      | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib    |
| ------------ | --------- | ------- | ---------- | --------- | --------- | ----------- | ----------- | -------------- | -------- | ---------- | ------------ | ----------- | --------- |
| arcadedb_sql | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 41,696.415  | 0.38        | 41,651.176     | 42.939   | 1.887      | 3,547.059    | 2,780.691   | 2,780.73  |
| faiss        | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 263.48      | 0           | 0              | 262.393  | 0.979      | 2,177.816    | 2,000.328   | 2,000.352 |
| lancedb      | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 95.525      | 0.001       | 61.577         | 32.621   | 0          | 1,622.492    | 2,534.549   | 2,536.246 |
| milvus       | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 190.58      | 0.209       | 0.792          | 175.046  | 0.254      | 1,927.609    | 8,575.717   | 8,592.477 |
| pgvector     | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 3,091.844   | 0.007       | 2,896.786      | 193.76   | 0.005      | 3,908.734    | 5,439.011   | 5,439.25  |
| qdrant       | 4g        | 8       | 5,000      | 1,242,391 | 1,242,391 | 368.162     | 0.173       | 0.244          | 364.39   | 0.04       | 3,432.996    | 2,514.004   | 2,446.309 |

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

### Dataset: stackoverflow-medium

| backend      | mem_limit | k   | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib    |
| ------------ | --------- | --- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ | --------- |
| arcadedb_sql | 4g        | 50  | 1,000   | 0.85        | 213.313         | 243.102        | 216.633     | 3.109     | 213.422  | 0.01       | 3,531.156    | 2,780.754 |
| bruteforce   | 4g        | 50  | 1,000   | 0.999       | 156.242         | 191.561        | 176.02      | 19.102    | 156.856  | 0          | 1,870.488    | 0.02      |
| faiss        | 4g        | 50  | 1,000   | 0.758       | 20.275          | 73.998         | 21.805      | 1.293     | 20.358   | 0          | 2,128.383    | 2,000.371 |
| lancedb      | 4g        | 50  | 1,000   | 0.946       | 10.23           | 8.616          | 11.688      | 0.002     | 10.272   | 0          | 2,125.859    | 2,536.266 |
| milvus       | 8g        | 50  | 1,000   | 0.973       | 9.755           | 13.775         | 52.679      | 0.265     | 10.152   | 0.24       | 4,013.266    | 8,136.637 |
| pgvector     | 4g        | 50  | 1,000   | 0.967       | 9.738           | 15.146         | 11.91       | 0.008     | 11.437   | 0.002      | 1,273.738    | 5,438.957 |
| qdrant       | 4g        | 50  | 1,000   | 0.989       | 52.171          | 54.944         | 59.368      | 0.162     | 52.276   | 0.038      | 2,578.172    | 2,037.113 |

### Dataset: stackoverflow-large

| backend    | mem_limit | k   | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib     |
| ---------- | --------- | --- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ | ---------- |
| bruteforce | 16g       | 50  | 1,000   | 1           | 630.619         | 704.747        | 692.107     | 61.348    | 630.694  | 0          | 8,100.863    | 0.02       |
| faiss      | 16g       | 50  | 1,000   | 0.756       | 14.154          | 78.142         | 20.401      | 5.718     | 14.305   | 0          | 9,084.387    | 8,792.977  |
| lancedb    | 16g       | 50  | 1,000   | 0.944       | 23.602          | 10.801         | 24.701      | 0.003     | 23.66    | 0          | 7,709.438    | 11,086.387 |
| qdrant     | 16g       | 50  | 1,000   | 0.985       | 55.218          | 58.914         | 79.45       | 0.166     | 55.326   | 0.046      | 9,519.699    | 8,888.848  |
