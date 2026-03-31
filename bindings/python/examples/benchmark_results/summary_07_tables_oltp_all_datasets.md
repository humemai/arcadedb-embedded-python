# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-31T09:34:16Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 9
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c386f75daa139e46622b3ab6e7a77baf6ca7e33131cae81936fbe1de4d50d43a
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 402.791 | 796.62 | 503.71 | 496.317 | 43.81 | 6,227.039 | 8,756.41 |
| arcadedb_sql | sweep07_t04_r02_arcadedb_sql_s00004_mem8g | 4 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 387.991 | 674.749 | 482.491 | 518.145 | 42.566 | 6,462.602 | 8,756.398 |
| arcadedb_sql | sweep07_t04_r03_arcadedb_sql_s00008_mem8g | 8 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 385.613 | 665.596 | 410.95 | 608.347 | 38.253 | 6,034.375 | 8,756.391 |
| postgresql | sweep07_t04_r01_postgresql_s00001_mem8g | 1 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 607.728 | 12.71 | 536.617 | 465.882 | 30.058 | 4,915.688 | 15,866.969 |
| postgresql | sweep07_t04_r02_postgresql_s00005_mem8g | 5 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 590.201 | 13.927 | 458.556 | 545.19 | 31.433 | 4,957.273 | 15,866.598 |
| postgresql | sweep07_t04_r03_postgresql_s00009_mem8g | 9 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 583.482 | 16.171 | 455.156 | 549.263 | 31.392 | 4,897.469 | 15,866.848 |
| sqlite | sweep07_t04_r01_sqlite_s00002_mem8g | 2 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 874.556 | 18.226 | 323.745 | 772.212 | 25.859 | 956.742 | 8,547.156 |
| sqlite | sweep07_t04_r02_sqlite_s00006_mem8g | 6 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 865.492 | 17.629 | 327.359 | 763.686 | 26.131 | 958.195 | 8,547.207 |
| sqlite | sweep07_t04_r03_sqlite_s00010_mem8g | 10 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 873.801 | 28.613 | 350.483 | 713.302 | 27.654 | 956.758 | 8,547.234 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 298.112 | 0.13 | 13.779 | 41.024 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 98.573 | 0.343 | 54.553 | 128.715 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 49.656 | 0.553 | 107.956 | 230.576 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 49.977 | 12.162 | 122.135 | 231.857 |
| arcadedb_sql | sweep07_t04_r02_arcadedb_sql_s00004_mem8g | read | 149,937 | 310.756 | 0.114 | 13.263 | 41.031 |
| arcadedb_sql | sweep07_t04_r02_arcadedb_sql_s00004_mem8g | update | 49,800 | 103.214 | 0.327 | 51.038 | 115.865 |
| arcadedb_sql | sweep07_t04_r02_arcadedb_sql_s00004_mem8g | insert | 25,091 | 52.003 | 0.511 | 107.81 | 222.65 |
| arcadedb_sql | sweep07_t04_r02_arcadedb_sql_s00004_mem8g | delete | 25,172 | 52.171 | 11.546 | 119.256 | 210.158 |
| arcadedb_sql | sweep07_t04_r03_arcadedb_sql_s00008_mem8g | read | 150,432 | 366.059 | 0.118 | 11.695 | 39.925 |
| arcadedb_sql | sweep07_t04_r03_arcadedb_sql_s00008_mem8g | update | 49,778 | 121.129 | 0.404 | 39.167 | 77.585 |
| arcadedb_sql | sweep07_t04_r03_arcadedb_sql_s00008_mem8g | insert | 24,882 | 60.548 | 1.139 | 58.612 | 137.85 |
| arcadedb_sql | sweep07_t04_r03_arcadedb_sql_s00008_mem8g | delete | 24,908 | 60.611 | 15.044 | 72.234 | 139.077 |
| postgresql | sweep07_t04_r01_postgresql_s00001_mem8g | read | 150,040 | 279.604 | 0.202 | 9.666 | 29.467 |
| postgresql | sweep07_t04_r01_postgresql_s00001_mem8g | update | 49,633 | 92.492 | 6.995 | 40.109 | 165.477 |
| postgresql | sweep07_t04_r01_postgresql_s00001_mem8g | insert | 25,160 | 46.886 | 5.76 | 36.654 | 127.281 |
| postgresql | sweep07_t04_r01_postgresql_s00001_mem8g | delete | 25,167 | 46.899 | 13.237 | 51.84 | 155.388 |
| postgresql | sweep07_t04_r02_postgresql_s00005_mem8g | read | 150,224 | 327.602 | 0.201 | 8.682 | 27.31 |
| postgresql | sweep07_t04_r02_postgresql_s00005_mem8g | update | 50,023 | 109.088 | 8.488 | 38.678 | 65.817 |
| postgresql | sweep07_t04_r02_postgresql_s00005_mem8g | insert | 24,820 | 54.126 | 7.039 | 37.172 | 63.476 |
| postgresql | sweep07_t04_r02_postgresql_s00005_mem8g | delete | 24,933 | 54.373 | 15.666 | 49.923 | 78.073 |
| postgresql | sweep07_t04_r03_postgresql_s00009_mem8g | read | 150,185 | 329.964 | 0.209 | 9.225 | 29.242 |
| postgresql | sweep07_t04_r03_postgresql_s00009_mem8g | update | 50,006 | 109.866 | 8.474 | 38.401 | 66.82 |
| postgresql | sweep07_t04_r03_postgresql_s00009_mem8g | insert | 24,866 | 54.632 | 7.052 | 36.082 | 62.416 |
| postgresql | sweep07_t04_r03_postgresql_s00009_mem8g | delete | 24,943 | 54.801 | 15.437 | 50.085 | 79.065 |
| sqlite | sweep07_t04_r01_sqlite_s00002_mem8g | read | 150,097 | 463.627 | 0.025 | 2.234 | 25.592 |
| sqlite | sweep07_t04_r01_sqlite_s00002_mem8g | update | 50,336 | 155.48 | 0.039 | 39.69 | 128.722 |
| sqlite | sweep07_t04_r01_sqlite_s00002_mem8g | insert | 24,785 | 76.557 | 0.071 | 31.522 | 109.614 |
| sqlite | sweep07_t04_r01_sqlite_s00002_mem8g | delete | 24,782 | 76.548 | 9.694 | 61.681 | 140.07 |
| sqlite | sweep07_t04_r02_sqlite_s00006_mem8g | read | 149,692 | 457.271 | 0.025 | 2.191 | 26.131 |
| sqlite | sweep07_t04_r02_sqlite_s00006_mem8g | update | 50,258 | 153.525 | 0.038 | 39.428 | 124.538 |
| sqlite | sweep07_t04_r02_sqlite_s00006_mem8g | insert | 24,866 | 75.959 | 0.07 | 34.027 | 103.705 |
| sqlite | sweep07_t04_r02_sqlite_s00006_mem8g | delete | 25,184 | 76.931 | 9.807 | 59.11 | 130.872 |
| sqlite | sweep07_t04_r03_sqlite_s00010_mem8g | read | 150,159 | 428.435 | 0.024 | 2.583 | 27.131 |
| sqlite | sweep07_t04_r03_sqlite_s00010_mem8g | update | 49,866 | 142.278 | 0.038 | 43.434 | 128.761 |
| sqlite | sweep07_t04_r03_sqlite_s00010_mem8g | insert | 24,929 | 71.128 | 0.071 | 33.496 | 107.963 |
| sqlite | sweep07_t04_r03_sqlite_s00010_mem8g | delete | 25,046 | 71.461 | 10.197 | 59.36 | 140.728 |
