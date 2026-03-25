# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-21T09:58:09Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 4
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:6f1f08f5d05cb615d15ba346b4845cae7b42f0199b8c41bf26bcad2d44d1e8e1
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
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 857.024 | 961.97 | 633.084 | 394.892 | 15.669 | 7,594.062 | 8,756.41 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 463.906 | 866.117 | 469.48 | 532.504 | 42.117 | 7,197.27 | 8,756.41 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 237.191 | 0.182 | 3.572 | 8.738 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 78.429 | 0.311 | 4.678 | 9.995 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 39.508 | 0.357 | 18.035 | 23.057 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 39.764 | 10.277 | 48.358 | 68.225 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 319.847 | 0.162 | 18.723 | 46.925 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 105.759 | 0.393 | 46.991 | 98.161 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 53.276 | 0.568 | 73.882 | 167.212 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 53.621 | 12.19 | 90.243 | 178.535 |

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 179.581 | 147.305 | 118.098 | 846.754 | 5.926 | 3,454.5 | 2,682.223 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 5,564,864 | 87.907 | 134.82 | 67.723 | 1,476.614 | 14.2 | 2,834.664 | 2,682.227 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | read | 60,074 | 508.679 | 0.068 | 2.854 | 7.539 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | update | 19,838 | 167.979 | 0.154 | 3.87 | 8.145 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | insert | 10,067 | 85.243 | 0.317 | 15.937 | 20.927 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | delete | 10,021 | 84.853 | 2.421 | 20.23 | 33.324 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | read | 60,074 | 887.061 | 0.117 | 6.938 | 12.533 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | update | 19,838 | 292.931 | 0.306 | 16.991 | 30.473 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | insert | 10,067 | 148.651 | 0.589 | 31.207 | 54.267 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | delete | 10,021 | 147.971 | 4.311 | 32.998 | 47.855 |
