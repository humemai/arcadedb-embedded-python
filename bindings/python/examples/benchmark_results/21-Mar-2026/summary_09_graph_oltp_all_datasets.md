# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-21T09:58:09Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 6
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:6f1f08f5d05cb615d15ba346b4845cae7b42f0199b8c41bf26bcad2d44d1e8e1
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - python_memory: builtin
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=15, success=6, failed=9
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 1 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.306 | 149.889 | 6,914.567 | 0.001 | 666.779 | 374.937 | 6.213 | 17,154.641 | 3,972.059 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | 0 | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.162 | 136.237 | 6,746.082 | 0.002 | 393.07 | 636.019 | 23.378 | 12,561.438 | 12,753.059 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 4 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.197 | 135.821 | 6,789.425 | 0.002 | 356.979 | 700.321 | 19.377 | 20,666.551 | 12,753.051 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 37.755 | 0.169 | 19.88 | 45.522 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 37.512 | 0.472 | 1.141 | 47.666 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 225.205 | 0.297 | 6.056 | 10.928 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 74.465 | 0.144 | 0.456 | 6.654 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | delete | 25,174 | 64.045 | 0.735 | 33.975 | 74.553 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | insert | 25,012 | 63.632 | 0.781 | 23.762 | 99.786 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | read | 150,162 | 382.024 | 0.831 | 23.302 | 77.399 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | update | 49,652 | 126.319 | 0.246 | 7.419 | 49.413 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 70.519 | 0.677 | 28.199 | 50.816 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 70.066 | 0.823 | 13.662 | 31.106 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 420.646 | 0.779 | 21.182 | 60.007 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 139.089 | 0.239 | 1.438 | 17.433 |

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.588 | 41.368 | 627.801 | 0.004 | 175.262 | 570.576 | 3.913 | 7,983.469 | 1,237.621 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | 0 | 4 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.224 | 36.992 | 676.864 | 0.004 | 124.119 | 805.676 | 16.874 | 7,464.438 | 4,011.113 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00001_mem8g | 1 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.289 | 40.745 | 642.462 | 0.002 | 86.377 | 1,157.715 | 3.206 | 7,782.949 | 1,237.43 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | delete | 10,021 | 57.177 | 0.187 | 16.431 | 29.276 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | insert | 10,067 | 57.44 | 0.523 | 19.056 | 27.03 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | read | 60,074 | 342.768 | 0.312 | 2.5 | 16.598 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | update | 19,838 | 113.191 | 0.162 | 2.727 | 4.702 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | delete | 10,021 | 80.737 | 0.895 | 25.071 | 51.059 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | insert | 10,067 | 81.107 | 1.017 | 41.393 | 104.361 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | read | 60,074 | 484.002 | 0.843 | 10.034 | 74.501 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | update | 19,838 | 159.83 | 0.255 | 20.046 | 39.749 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00001_mem8g | delete | 10,150 | 117.508 | 2.461 | 21.784 | 40.934 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00001_mem8g | insert | 10,018 | 115.98 | 0.358 | 15.469 | 23.698 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00001_mem8g | read | 60,179 | 696.701 | 0.052 | 0.294 | 0.511 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00001_mem8g | update | 19,653 | 227.526 | 0.071 | 2.091 | 4.78 |
