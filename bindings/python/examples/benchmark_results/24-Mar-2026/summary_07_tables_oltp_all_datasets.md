# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-24T19:19:11Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 2
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:85144b5986b475530a67d95659a93457c9b804e26ac22065af540822670de953
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 783.969 | 1,179.189 | 550.472 | 454.156 | 15.048 | 7,614.371 | 8,756.41 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 412.823 | 943.983 | 465.265 | 537.328 | 40.147 | 6,040.414 | 8,756.473 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 272.788 | 0.132 | 0.552 | 2.441 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 90.199 | 0.287 | 2.981 | 5.273 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 45.437 | 0.323 | 17.463 | 21.039 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 45.732 | 9.868 | 46.108 | 61.734 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 322.745 | 0.157 | 17.562 | 43.141 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 106.718 | 0.429 | 44.019 | 97.727 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 53.759 | 0.614 | 73.406 | 160.079 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 54.107 | 12.221 | 90.542 | 175.711 |
