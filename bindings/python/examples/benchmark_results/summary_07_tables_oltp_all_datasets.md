# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 4
- Note: `preload_time_s` is data ingest only, `index_time_s` is post-ingest index build, and `oltp_crud_time_s` / `throughput_s` measure OLTP CRUD only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.

## Dataset: stackoverflow-small

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | 0 | 1 | 50,000 | 2,500 | 2g | 1,406,035 | 77.47 | 14.124 | 46.128 | 1,083.932 | 2.414 | 1,249.992 | 573.566 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | 2 | 1 | 50,000 | 2,500 | 2g | 1,406,035 | 56.953 | 0.24 | 155.806 | 320.911 | 6.525 | 1,804.234 | 1,134.789 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | 3 | 1 | 50,000 | 2,500 | 2g | 1,406,035 | 53.314 | 0.715 | 30.82 | 1,622.341 | 2.031 | 934.418 | 1,458.719 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | 1 | 1 | 50,000 | 2,500 | 2g | 1,406,035 | 53.467 | 0.722 | 7.582 | 6,594.942 | 0.91 | 96.633 | 573.918 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | read | 30,147 | 653.546 | 0.07 | 0.365 | 0.58 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | update | 9,884 | 214.272 | 0.149 | 2.4 | 4.741 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | insert | 4,984 | 108.046 | 0.392 | 18.483 | 25.087 |
| arcadedb | sweep07_t01_r01_arcadedb_s00000 | delete | 4,985 | 108.068 | 1.49 | 22.148 | 50.088 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | read | 30,021 | 192.682 | 0.542 | 2.86 | 16.549 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | update | 10,023 | 64.33 | 3.627 | 8.493 | 23.681 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | insert | 4,979 | 31.956 | 4.518 | 8.155 | 20.932 |
| duckdb | sweep07_t01_r01_duckdb_s00002 | delete | 4,977 | 31.944 | 4.102 | 7.109 | 8.94 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | read | 29,913 | 970.582 | 0.099 | 0.175 | 0.967 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | update | 9,942 | 322.586 | 0.931 | 2.94 | 4.879 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | insert | 5,120 | 166.128 | 1.021 | 2.849 | 4.108 |
| postgresql | sweep07_t01_r01_postgresql_s00003 | delete | 5,025 | 163.045 | 1.444 | 3.873 | 5.941 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | read | 30,101 | 3,970.287 | 0.017 | 0.032 | 0.057 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | update | 9,731 | 1,283.508 | 0.026 | 0.05 | 0.093 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | insert | 5,060 | 667.408 | 0.048 | 0.111 | 0.175 |
| sqlite | sweep07_t01_r01_sqlite_s00001 | delete | 5,108 | 673.739 | 0.879 | 3.815 | 5.692 |
