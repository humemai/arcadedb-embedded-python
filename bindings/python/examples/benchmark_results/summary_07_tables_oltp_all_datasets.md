# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T20:52:17Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 4
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | 0 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 298.661 | 119.64 | 144.205 | 693.458 | 7.316 | 3,600.898 | 2,658.883 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | 2 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 185.474 | 0.933 | 358.315 | 279.084 | 10.794 | 3,901.762 | 5,265.73 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | 3 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 232.514 | 6.726 | 192.761 | 518.778 | 6.632 | 2,566.77 | 5,447.949 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | 1 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 255.25 | 3.682 | 51.601 | 1,937.945 | 3.122 | 267.707 | 2,691.809 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | read | 60,074 | 416.588 | 0.085 | 0.422 | 0.7 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | update | 19,838 | 137.568 | 0.219 | 2.71 | 4.378 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | insert | 10,067 | 69.81 | 0.399 | 19.13 | 24.001 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | delete | 10,021 | 69.491 | 4.352 | 26.12 | 41.768 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | read | 59,859 | 167.057 | 0.55 | 3.313 | 12.817 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | update | 20,200 | 56.375 | 3.592 | 12.834 | 33.396 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | insert | 9,916 | 27.674 | 4.755 | 11.081 | 26.138 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | delete | 10,025 | 27.978 | 6.943 | 17.905 | 22.334 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | read | 60,134 | 311.962 | 0.121 | 0.345 | 0.583 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | update | 19,975 | 103.626 | 2.724 | 9.924 | 23.95 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | insert | 10,128 | 52.542 | 2.773 | 8.001 | 17.933 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | delete | 9,763 | 50.648 | 4.583 | 13.254 | 25.926 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | read | 60,179 | 1,166.236 | 0.021 | 0.06 | 0.127 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | update | 19,653 | 380.864 | 0.031 | 0.088 | 0.166 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | insert | 10,018 | 194.143 | 0.061 | 0.16 | 0.237 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | delete | 10,150 | 196.701 | 2.998 | 16.174 | 20.708 |
