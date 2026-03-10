# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T20:52:42Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 15
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:c1db044c71db11c553065dc9fcccfceae444df12210bf352b12bfc18bae68790
  - arcadedb_docker_tag: 26.3.1, 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - duckdb: auto
  - duckdb_runtime_version: 1.4.4, 1.5.0
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl, arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1, 26.4.1.dev0
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_m8g | 0 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 796.361 | 1,569.766 | 678.86 | 368.265 | 17.334 | 7,638.836 | 8,718.844 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_m8g | 0 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 802.131 | 1,269.759 | 541.62 | 461.578 | 47.908 | 5,122.672 | 8,718.848 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_m8g | 0 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 782.192 | 1,220.134 | 531.053 | 470.763 | 81.202 | 4,749.086 | 8,718.906 |
| duckdb | sweep07_t01_r01_duckdb_s00000_m16g | 0 | 1 | 250,000 | 10,000 | 16g | 22,649,754 | 442.287 | 3.683 | 1,303.984 | 191.72 | 15.914 | 8,552.176 | 18,224.988 |
| duckdb | sweep07_t04_r01_duckdb_s00000_m16g | 0 | 4 | 250,000 | 10,000 | 16g | 22,649,754 | 436.316 | 1.932 | 1,198.534 | 208.588 | 51.832 | 8,355.719 | 18,218.738 |
| postgresql | sweep07_t01_r01_postgresql_s00003_m8g | 3 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 481.035 | 20.464 | 892.934 | 279.976 | 13.532 | 4,480.379 | 15,866.668 |
| postgresql | sweep07_t04_r01_postgresql_s00003_m8g | 3 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 692.841 | 21.379 | 538.551 | 464.209 | 31.753 | 4,834.102 | 15,866.727 |
| postgresql | sweep07_t08_r01_postgresql_s00003_m8g | 3 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 631.205 | 26.091 | 439.911 | 568.296 | 46.323 | 5,426.539 | 15,866.953 |
| sqlite | sweep07_t01_r01_sqlite_s00001_m8g | 1 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 1,056.041 | 23.305 | 296.355 | 843.583 | 6.363 | 954.805 | 8,547.223 |
| sqlite | sweep07_t04_r01_sqlite_s00001_m8g | 1 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 1,111.745 | 31.095 | 352.575 | 709.069 | 29.073 | 957.941 | 8,547.137 |
| sqlite | sweep07_t08_r01_sqlite_s00001_m8g | 1 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 1,101.288 | 39.955 | 352.077 | 710.073 | 38.31 | 1,014.34 | 8,547.211 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_m8g | read | 150,162 | 221.197 | 0.103 | 2.8 | 5.606 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_m8g | update | 49,652 | 73.14 | 0.26 | 4.03 | 7.626 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_m8g | insert | 25,012 | 36.844 | 0.301 | 20.378 | 25.148 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_m8g | delete | 25,174 | 37.083 | 11.395 | 50.745 | 69.856 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_m8g | read | 150,162 | 277.246 | 0.132 | 16.285 | 45.389 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_m8g | update | 49,652 | 91.673 | 0.354 | 54.338 | 125.135 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_m8g | insert | 25,012 | 46.18 | 0.637 | 101.942 | 219.951 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_m8g | delete | 25,174 | 46.479 | 15.879 | 117.818 | 238.849 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_m8g | read | 150,162 | 282.763 | 0.331 | 35.161 | 57.242 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_m8g | update | 49,652 | 93.497 | 4.63 | 95.556 | 221.047 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_m8g | insert | 25,012 | 47.099 | 14.612 | 172.384 | 323.663 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_m8g | delete | 25,174 | 47.404 | 27.361 | 171.326 | 296.249 |
| duckdb | sweep07_t01_r01_duckdb_s00000_m16g | read | 150,162 | 115.156 | 0.357 | 1.118 | 2.639 |
| duckdb | sweep07_t01_r01_duckdb_s00000_m16g | update | 49,652 | 38.077 | 10.325 | 11.918 | 16.013 |
| duckdb | sweep07_t01_r01_duckdb_s00000_m16g | insert | 25,012 | 19.181 | 10.384 | 12.183 | 16.023 |
| duckdb | sweep07_t01_r01_duckdb_s00000_m16g | delete | 25,174 | 19.305 | 15.061 | 48.217 | 57.309 |
| duckdb | sweep07_t04_r01_duckdb_s00000_m16g | read | 150,162 | 125.288 | 10.362 | 24.505 | 49.177 |
| duckdb | sweep07_t04_r01_duckdb_s00000_m16g | update | 49,652 | 41.427 | 32.213 | 55.95 | 73.145 |
| duckdb | sweep07_t04_r01_duckdb_s00000_m16g | insert | 25,012 | 20.869 | 32.98 | 59.607 | 77.639 |
| duckdb | sweep07_t04_r01_duckdb_s00000_m16g | delete | 25,174 | 21.004 | 35.509 | 72.53 | 88.486 |
| postgresql | sweep07_t01_r01_postgresql_s00003_m8g | read | 149,761 | 167.718 | 0.179 | 3.419 | 7.02 |
| postgresql | sweep07_t01_r01_postgresql_s00003_m8g | update | 50,062 | 56.065 | 4.073 | 14.45 | 33.957 |
| postgresql | sweep07_t01_r01_postgresql_s00003_m8g | insert | 25,102 | 28.112 | 3.975 | 11.53 | 27.964 |
| postgresql | sweep07_t01_r01_postgresql_s00003_m8g | delete | 25,075 | 28.082 | 9.578 | 35.867 | 54.729 |
| postgresql | sweep07_t04_r01_postgresql_s00003_m8g | read | 149,761 | 278.081 | 0.273 | 10.319 | 27.57 |
| postgresql | sweep07_t04_r01_postgresql_s00003_m8g | update | 50,062 | 92.957 | 10.041 | 40.752 | 94.886 |
| postgresql | sweep07_t04_r01_postgresql_s00003_m8g | insert | 25,102 | 46.61 | 8.35 | 36.964 | 91.461 |
| postgresql | sweep07_t04_r01_postgresql_s00003_m8g | delete | 25,075 | 46.56 | 16.355 | 51.44 | 100.811 |
| postgresql | sweep07_t08_r01_postgresql_s00003_m8g | read | 149,761 | 340.434 | 0.664 | 20.427 | 38.239 |
| postgresql | sweep07_t08_r01_postgresql_s00003_m8g | update | 50,062 | 113.8 | 17.046 | 60.175 | 191.645 |
| postgresql | sweep07_t08_r01_postgresql_s00003_m8g | insert | 25,102 | 57.061 | 14.395 | 56.948 | 189.309 |
| postgresql | sweep07_t08_r01_postgresql_s00003_m8g | delete | 25,075 | 57 | 24.599 | 73.69 | 198.454 |
| sqlite | sweep07_t01_r01_sqlite_s00001_m8g | read | 150,040 | 506.285 | 0.017 | 0.136 | 0.206 |
| sqlite | sweep07_t01_r01_sqlite_s00001_m8g | update | 49,633 | 167.478 | 0.024 | 0.147 | 0.238 |
| sqlite | sweep07_t01_r01_sqlite_s00001_m8g | insert | 25,160 | 84.898 | 0.042 | 0.104 | 0.146 |
| sqlite | sweep07_t01_r01_sqlite_s00001_m8g | delete | 25,167 | 84.922 | 5.965 | 43.017 | 51.574 |
| sqlite | sweep07_t04_r01_sqlite_s00001_m8g | read | 150,040 | 425.555 | 0.026 | 3.924 | 30.302 |
| sqlite | sweep07_t04_r01_sqlite_s00001_m8g | update | 49,633 | 140.773 | 0.042 | 45.225 | 128.663 |
| sqlite | sweep07_t04_r01_sqlite_s00001_m8g | insert | 25,160 | 71.361 | 0.076 | 35.065 | 105.163 |
| sqlite | sweep07_t04_r01_sqlite_s00001_m8g | delete | 25,167 | 71.381 | 10.414 | 58.392 | 137.712 |
| sqlite | sweep07_t08_r01_sqlite_s00001_m8g | read | 150,040 | 426.157 | 0.027 | 6.018 | 36.945 |
| sqlite | sweep07_t08_r01_sqlite_s00001_m8g | update | 49,633 | 140.972 | 0.047 | 64.231 | 544.04 |
| sqlite | sweep07_t08_r01_sqlite_s00001_m8g | insert | 25,160 | 71.462 | 0.08 | 53.89 | 343.456 |
| sqlite | sweep07_t08_r01_sqlite_s00001_m8g | delete | 25,167 | 71.482 | 11.819 | 83.696 | 564.834 |

## Dataset: stackoverflow-tiny

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000 | 0 | 1 | 10,000 | 1,000 | 1g | 70,668 | 5.126 | 1.127 | 13.264 | 753.932 | 5.437 | 335.082 | 30.691 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | 2 | 1 | 10,000 | 1,000 | 1g | 70,668 | 1.124 | 0.041 | 21.21 | 471.478 | 6.107 | 236.801 | 64.781 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | 3 | 1 | 10,000 | 1,000 | 1g | 70,668 | 1.01 | 0.047 | 5.449 | 1,835.107 | 2.767 | 253.004 | 131.66 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | 1 | 1 | 10,000 | 1,000 | 1g | 70,668 | 16.234 | 0.024 | 0.252 | 39,698.197 | 0.055 | 38.008 | 29.613 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000 | read | 5,977 | 450.625 | 0.068 | 0.399 | 0.814 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000 | update | 2,017 | 152.068 | 0.138 | 3.171 | 5.415 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000 | insert | 1,049 | 79.087 | 0.244 | 22.124 | 40.758 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000 | delete | 957 | 72.151 | 0.334 | 23.057 | 32.523 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | read | 6,047 | 285.103 | 0.376 | 0.744 | 0.964 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | update | 1,981 | 93.4 | 4.645 | 6.339 | 8.446 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | insert | 984 | 46.393 | 5.129 | 8.284 | 10.134 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | delete | 988 | 46.582 | 4.441 | 6.167 | 8.209 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | read | 6,041 | 1,108.588 | 0.053 | 0.104 | 0.153 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | update | 1,906 | 349.771 | 0.85 | 3.604 | 3.958 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | insert | 1,035 | 189.934 | 0.889 | 3.801 | 4.06 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | delete | 1,018 | 186.814 | 0.866 | 3.666 | 4.023 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | read | 6,021 | 23,902.285 | 0.008 | 0.014 | 0.02 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | update | 1,959 | 7,776.877 | 0.014 | 0.023 | 0.034 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | insert | 987 | 3,918.212 | 0.025 | 0.046 | 0.068 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | delete | 1,033 | 4,100.824 | 0.051 | 0.102 | 0.146 |
