# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T16:54:27Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 8
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:3f359ca6b9a9b4fde4cfda499cd6951e802a6aae6e930134f1aaf3f664184696
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - duckdb: 1.4.4
  - duckdb_runtime_version: 1.4.4
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | 0 | 1 | 100,000 | 5,000 | 8g | 5,564,864 | 243.322 | 88.883 | 145.945 | 685.19 | 5.387 | 5,139.777 | 2,658.891 |
| arcadedb | sweep07_t04_r01_arcadedb_s00000 | 0 | 4 | 100,000 | 5,000 | 8g | 5,564,864 | 228.446 | 69.659 | 101.456 | 985.652 | 17.904 | 4,044.57 | 2,658.836 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | 2 | 1 | 100,000 | 5,000 | 8g | 5,564,864 | 120.877 | 0.92 | 262.523 | 380.92 | 8.232 | 2,716.586 | 5,264.734 |
| duckdb | sweep07_t04_r01_duckdb_s00002 | 2 | 4 | 100,000 | 5,000 | 8g | 5,564,864 | 114.28 | 0.537 | 179.474 | 557.183 | 20.127 | 2,699.172 | 5,265.48 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | 3 | 1 | 100,000 | 5,000 | 8g | 5,564,864 | 145.793 | 2.925 | 164.296 | 608.657 | 5.464 | 1,655.98 | 5,447.738 |
| postgresql | sweep07_t04_r01_postgresql_s00003 | 3 | 4 | 100,000 | 5,000 | 8g | 5,564,864 | 131.958 | 3.322 | 73.67 | 1,357.407 | 10.254 | 2,613.215 | 5,447.059 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | 1 | 1 | 100,000 | 5,000 | 8g | 5,564,864 | 246.37 | 3.608 | 50.011 | 1,999.564 | 2.989 | 266.113 | 2,691.812 |
| sqlite | sweep07_t04_r01_sqlite_s00001 | 1 | 4 | 100,000 | 5,000 | 8g | 5,564,864 | 240.575 | 3.313 | 51.855 | 1,928.471 | 10.22 | 270.07 | 2,691.766 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | read | 60,074 | 411.621 | 0.067 | 0.376 | 0.607 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | update | 19,838 | 135.928 | 0.139 | 0.745 | 11.963 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | insert | 10,067 | 68.978 | 0.379 | 0.894 | 84.002 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | delete | 10,021 | 68.663 | 3.725 | 33.406 | 91.506 |
| arcadedb | sweep07_t04_r01_arcadedb_s00000 | read | 60,074 | 592.121 | 0.141 | 6.103 | 17.048 |
| arcadedb | sweep07_t04_r01_arcadedb_s00000 | update | 19,838 | 195.534 | 0.319 | 21.258 | 67.434 |
| arcadedb | sweep07_t04_r01_arcadedb_s00000 | insert | 10,067 | 99.226 | 0.894 | 59.337 | 125.352 |
| arcadedb | sweep07_t04_r01_arcadedb_s00000 | delete | 10,021 | 98.772 | 6.748 | 59.062 | 122.439 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | read | 59,859 | 228.015 | 0.478 | 1.228 | 2.28 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | update | 20,200 | 76.946 | 3.628 | 7.624 | 10.345 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | insert | 9,916 | 37.772 | 4.825 | 8.657 | 10.005 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | delete | 10,025 | 38.187 | 6.759 | 17.309 | 21.578 |
| duckdb | sweep07_t04_r01_duckdb_s00002 | read | 59,859 | 333.524 | 2.961 | 9.86 | 17.194 |
| duckdb | sweep07_t04_r01_duckdb_s00002 | update | 20,200 | 112.551 | 9.617 | 23.401 | 29.645 |
| duckdb | sweep07_t04_r01_duckdb_s00002 | insert | 9,916 | 55.25 | 11.113 | 24.806 | 31.615 |
| duckdb | sweep07_t04_r01_duckdb_s00002 | delete | 10,025 | 55.858 | 12.356 | 26.877 | 34.254 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | read | 60,134 | 366.01 | 0.118 | 0.301 | 0.474 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | update | 19,975 | 121.579 | 2.755 | 5.328 | 8.896 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | insert | 10,128 | 61.645 | 2.834 | 5.229 | 8.196 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | delete | 9,763 | 59.423 | 4.635 | 11.359 | 14.214 |
| postgresql | sweep07_t04_r01_postgresql_s00003 | read | 60,134 | 816.263 | 0.164 | 1.552 | 6.532 |
| postgresql | sweep07_t04_r01_postgresql_s00003 | update | 19,975 | 271.142 | 5.132 | 12.209 | 18.179 |
| postgresql | sweep07_t04_r01_postgresql_s00003 | insert | 10,128 | 137.478 | 5.141 | 12.113 | 17.575 |
| postgresql | sweep07_t04_r01_postgresql_s00003 | delete | 9,763 | 132.524 | 7.183 | 15.665 | 21.849 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | read | 60,179 | 1,203.318 | 0.02 | 0.064 | 0.13 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | update | 19,653 | 392.974 | 0.031 | 0.091 | 0.171 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | insert | 10,018 | 200.316 | 0.06 | 0.164 | 0.242 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | delete | 10,150 | 202.956 | 2.889 | 15.383 | 20.144 |
| sqlite | sweep07_t04_r01_sqlite_s00001 | read | 60,179 | 1,160.535 | 0.028 | 0.138 | 5.479 |
| sqlite | sweep07_t04_r01_sqlite_s00001 | update | 19,653 | 379.002 | 0.041 | 16.174 | 42.924 |
| sqlite | sweep07_t04_r01_sqlite_s00001 | insert | 10,018 | 193.194 | 0.089 | 13.979 | 41.259 |
| sqlite | sweep07_t04_r01_sqlite_s00001 | delete | 10,150 | 195.74 | 4.132 | 22.213 | 48.176 |
