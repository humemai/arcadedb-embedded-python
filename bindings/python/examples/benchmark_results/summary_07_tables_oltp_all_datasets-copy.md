# 07 Tables OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T16:19:52Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep07
- Total runs: 24
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:08c19266ac0fee12e891534141ccc1e9ae6a493d3b69479feaad1261218395c4, arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585, ... (+1 more)
  - arcadedb_docker_tag: 26.3.1, 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - duckdb: auto
  - duckdb_runtime_version: 1.5.0
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
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 796.361 | 1,569.766 | 678.86 | 368.265 | 17.334 | 7,638.836 | 8,718.844 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 802.131 | 1,269.759 | 541.62 | 461.578 | 47.908 | 5,122.672 | 8,718.848 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_mem8g | 0 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 782.192 | 1,220.134 | 531.053 | 470.763 | 81.202 | 4,749.086 | 8,718.906 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem16g | 0 | 1 | 250,000 | 10,000 | 16g | 22,649,754 | 366.548 | 0 | 2,460.172 | 101.619 | 25.998 | 11,140.641 | 17,542.738 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem16g | 0 | 4 | 250,000 | 10,000 | 16g | 22,649,754 | 327.309 | 0 | 867.823 | 288.077 | 41.742 | 10,199.543 | 17,550.246 |
| duckdb | sweep07_t08_r01_duckdb_s00000_mem16g | 0 | 8 | 250,000 | 10,000 | 16g | 22,649,754 | 370.773 | 0 | 1,024.621 | 243.993 | 86.57 | 9,613.008 | 17,550.512 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem8g | 3 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 481.035 | 20.464 | 892.934 | 279.976 | 13.532 | 4,480.379 | 15,866.668 |
| postgresql | sweep07_t04_r01_postgresql_s00003_mem8g | 3 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 692.841 | 21.379 | 538.551 | 464.209 | 31.753 | 4,834.102 | 15,866.727 |
| postgresql | sweep07_t08_r01_postgresql_s00003_mem8g | 3 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 631.205 | 26.091 | 439.911 | 568.296 | 46.323 | 5,426.539 | 15,866.953 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem8g | 1 | 1 | 250,000 | 10,000 | 8g | 22,649,754 | 1,056.041 | 23.305 | 296.355 | 843.583 | 6.363 | 954.805 | 8,547.223 |
| sqlite | sweep07_t04_r01_sqlite_s00001_mem8g | 1 | 4 | 250,000 | 10,000 | 8g | 22,649,754 | 1,111.745 | 31.095 | 352.575 | 709.069 | 29.073 | 957.941 | 8,547.137 |
| sqlite | sweep07_t08_r01_sqlite_s00001_mem8g | 1 | 8 | 250,000 | 10,000 | 8g | 22,649,754 | 1,101.288 | 39.955 | 352.077 | 710.073 | 38.31 | 1,014.34 | 8,547.211 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 221.197 | 0.103 | 2.8 | 5.606 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 73.14 | 0.26 | 4.03 | 7.626 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 36.844 | 0.301 | 20.378 | 25.148 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 37.083 | 11.395 | 50.745 | 69.856 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 277.246 | 0.132 | 16.285 | 45.389 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 91.673 | 0.354 | 54.338 | 125.135 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 46.18 | 0.637 | 101.942 | 219.951 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 46.479 | 15.879 | 117.818 | 238.849 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_mem8g | read | 150,162 | 282.763 | 0.331 | 35.161 | 57.242 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_mem8g | update | 49,652 | 93.497 | 4.63 | 95.556 | 221.047 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_mem8g | insert | 25,012 | 47.099 | 14.612 | 172.384 | 323.663 |
| arcadedb_sql | sweep07_t08_r01_arcadedb_sql_s00000_mem8g | delete | 25,174 | 47.404 | 27.361 | 171.326 | 296.249 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem16g | read | 150,162 | 61.037 | 2.895 | 14.541 | 22.915 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem16g | update | 49,652 | 20.182 | 14.307 | 25.947 | 36.196 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem16g | insert | 25,012 | 10.167 | 12.302 | 16.6 | 19.86 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem16g | delete | 25,174 | 10.233 | 19.992 | 63.973 | 86.94 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem16g | read | 150,162 | 173.033 | 6.227 | 20.42 | 46.573 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem16g | update | 49,652 | 57.214 | 19.277 | 46.687 | 66.577 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem16g | insert | 25,012 | 28.822 | 17.584 | 44.7 | 66.553 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem16g | delete | 25,174 | 29.008 | 25.484 | 65.834 | 85.743 |
| duckdb | sweep07_t08_r01_duckdb_s00000_mem16g | read | 150,162 | 146.554 | 11.669 | 41.097 | 67.928 |
| duckdb | sweep07_t08_r01_duckdb_s00000_mem16g | update | 49,652 | 48.459 | 54.832 | 96.433 | 123.027 |
| duckdb | sweep07_t08_r01_duckdb_s00000_mem16g | insert | 25,012 | 24.411 | 53.975 | 96.126 | 123.144 |
| duckdb | sweep07_t08_r01_duckdb_s00000_mem16g | delete | 25,174 | 24.569 | 62.895 | 113.781 | 142.188 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem8g | read | 149,761 | 167.718 | 0.179 | 3.419 | 7.02 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem8g | update | 50,062 | 56.065 | 4.073 | 14.45 | 33.957 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem8g | insert | 25,102 | 28.112 | 3.975 | 11.53 | 27.964 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem8g | delete | 25,075 | 28.082 | 9.578 | 35.867 | 54.729 |
| postgresql | sweep07_t04_r01_postgresql_s00003_mem8g | read | 149,761 | 278.081 | 0.273 | 10.319 | 27.57 |
| postgresql | sweep07_t04_r01_postgresql_s00003_mem8g | update | 50,062 | 92.957 | 10.041 | 40.752 | 94.886 |
| postgresql | sweep07_t04_r01_postgresql_s00003_mem8g | insert | 25,102 | 46.61 | 8.35 | 36.964 | 91.461 |
| postgresql | sweep07_t04_r01_postgresql_s00003_mem8g | delete | 25,075 | 46.56 | 16.355 | 51.44 | 100.811 |
| postgresql | sweep07_t08_r01_postgresql_s00003_mem8g | read | 149,761 | 340.434 | 0.664 | 20.427 | 38.239 |
| postgresql | sweep07_t08_r01_postgresql_s00003_mem8g | update | 50,062 | 113.8 | 17.046 | 60.175 | 191.645 |
| postgresql | sweep07_t08_r01_postgresql_s00003_mem8g | insert | 25,102 | 57.061 | 14.395 | 56.948 | 189.309 |
| postgresql | sweep07_t08_r01_postgresql_s00003_mem8g | delete | 25,075 | 57 | 24.599 | 73.69 | 198.454 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem8g | read | 150,040 | 506.285 | 0.017 | 0.136 | 0.206 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem8g | update | 49,633 | 167.478 | 0.024 | 0.147 | 0.238 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem8g | insert | 25,160 | 84.898 | 0.042 | 0.104 | 0.146 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem8g | delete | 25,167 | 84.922 | 5.965 | 43.017 | 51.574 |
| sqlite | sweep07_t04_r01_sqlite_s00001_mem8g | read | 150,040 | 425.555 | 0.026 | 3.924 | 30.302 |
| sqlite | sweep07_t04_r01_sqlite_s00001_mem8g | update | 49,633 | 140.773 | 0.042 | 45.225 | 128.663 |
| sqlite | sweep07_t04_r01_sqlite_s00001_mem8g | insert | 25,160 | 71.361 | 0.076 | 35.065 | 105.163 |
| sqlite | sweep07_t04_r01_sqlite_s00001_mem8g | delete | 25,167 | 71.381 | 10.414 | 58.392 | 137.712 |
| sqlite | sweep07_t08_r01_sqlite_s00001_mem8g | read | 150,040 | 426.157 | 0.027 | 6.018 | 36.945 |
| sqlite | sweep07_t08_r01_sqlite_s00001_mem8g | update | 49,633 | 140.972 | 0.047 | 64.231 | 544.04 |
| sqlite | sweep07_t08_r01_sqlite_s00001_mem8g | insert | 25,160 | 71.462 | 0.08 | 53.89 | 343.456 |
| sqlite | sweep07_t08_r01_sqlite_s00001_mem8g | delete | 25,167 | 71.482 | 11.819 | 83.696 | 564.834 |

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 191.453 | 76.561 | 100.717 | 992.886 | 4.108 | 2,804.426 | 2,658.895 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 5,564,864 | 178.934 | 74.496 | 94.371 | 1,059.644 | 19.087 | 2,251.84 | 2,658.906 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 5,564,864 | 127.323 | 0 | 779.855 | 128.229 | 23.512 | 3,977.531 | 5,137.238 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem8g | 0 | 4 | 100,000 | 5,000 | 8g | 5,564,864 | 122.766 | 0 | 494.969 | 202.033 | 51.373 | 3,614.258 | 5,137.484 |
| postgresql | sweep07_t01_r01_postgresql_s00000_mem4g | 0 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 189.095 | 6.889 | 249.835 | 400.263 | 9.175 | 2,537.426 | 5,447.93 |
| postgresql | sweep07_t04_r01_postgresql_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 5,564,864 | 173.783 | 7.312 | 199.35 | 501.629 | 25.933 | 3,129.203 | 5,447.785 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem4g | 1 | 1 | 100,000 | 5,000 | 4g | 5,564,864 | 195.975 | 6.164 | 34.204 | 2,923.641 | 2.124 | 266.543 | 2,691.812 |
| sqlite | sweep07_t04_r01_sqlite_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 5,564,864 | 292.576 | 3.124 | 53.728 | 1,861.229 | 8.542 | 271.988 | 2,691.754 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | read | 60,074 | 596.466 | 0.053 | 0.325 | 0.517 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | update | 19,838 | 196.969 | 0.115 | 2.182 | 3.861 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | insert | 10,067 | 99.954 | 0.256 | 17.955 | 23.683 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem4g | delete | 10,021 | 99.497 | 2.751 | 22.063 | 32.26 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | read | 60,074 | 636.571 | 0.12 | 8 | 16.076 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | update | 19,838 | 210.212 | 0.385 | 21.668 | 37.695 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | insert | 10,067 | 106.674 | 0.64 | 37.965 | 68.587 |
| arcadedb_sql | sweep07_t04_r01_arcadedb_sql_s00000_mem4g | delete | 10,021 | 106.187 | 6.595 | 41.802 | 63.149 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem8g | read | 60,074 | 77.032 | 1.051 | 3.341 | 4.538 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem8g | update | 19,838 | 25.438 | 11.573 | 48.923 | 108.332 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem8g | insert | 10,067 | 12.909 | 11.481 | 47.708 | 100.073 |
| duckdb | sweep07_t01_r01_duckdb_s00000_mem8g | delete | 10,021 | 12.85 | 13.862 | 51.9 | 106.914 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem8g | read | 60,074 | 121.369 | 10.082 | 22.307 | 53.849 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem8g | update | 19,838 | 40.079 | 32.04 | 63.524 | 173.682 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem8g | insert | 10,067 | 20.339 | 32.895 | 66.389 | 171.672 |
| duckdb | sweep07_t04_r01_duckdb_s00000_mem8g | delete | 10,021 | 20.246 | 31.606 | 64.4 | 174.018 |
| postgresql | sweep07_t01_r01_postgresql_s00000_mem4g | read | 60,074 | 240.454 | 0.105 | 0.611 | 2.858 |
| postgresql | sweep07_t01_r01_postgresql_s00000_mem4g | update | 19,838 | 79.404 | 2.664 | 11.337 | 26.487 |
| postgresql | sweep07_t01_r01_postgresql_s00000_mem4g | insert | 10,067 | 40.295 | 2.674 | 10.112 | 18.382 |
| postgresql | sweep07_t01_r01_postgresql_s00000_mem4g | delete | 10,021 | 40.11 | 4.962 | 14.448 | 27.313 |
| postgresql | sweep07_t04_r01_postgresql_s00000_mem4g | read | 60,074 | 301.349 | 0.172 | 6.467 | 11.838 |
| postgresql | sweep07_t04_r01_postgresql_s00000_mem4g | update | 19,838 | 99.513 | 15.441 | 33.623 | 73.715 |
| postgresql | sweep07_t04_r01_postgresql_s00000_mem4g | insert | 10,067 | 50.499 | 14.603 | 31.159 | 75.773 |
| postgresql | sweep07_t04_r01_postgresql_s00000_mem4g | delete | 10,021 | 50.268 | 17.201 | 36.413 | 76.859 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem4g | read | 60,179 | 1,759.418 | 0.014 | 0.038 | 0.138 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem4g | update | 19,653 | 574.583 | 0.021 | 0.057 | 0.159 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem4g | insert | 10,018 | 292.89 | 0.037 | 0.095 | 0.143 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem4g | delete | 10,150 | 296.75 | 2.003 | 10.643 | 13.04 |
| sqlite | sweep07_t04_r01_sqlite_s00000_mem4g | read | 60,074 | 1,118.115 | 0.023 | 0.1 | 2.728 |
| sqlite | sweep07_t04_r01_sqlite_s00000_mem4g | update | 19,838 | 369.231 | 0.037 | 20.475 | 42.963 |
| sqlite | sweep07_t04_r01_sqlite_s00000_mem4g | insert | 10,067 | 187.37 | 0.076 | 18.819 | 40.765 |
| sqlite | sweep07_t04_r01_sqlite_s00000_mem4g | delete | 10,021 | 186.514 | 3.537 | 24.416 | 50.209 |

## Dataset: stackoverflow-tiny

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem1g | 0 | 1 | 10,000 | 1,000 | 1g | 70,668 | 4.656 | 1.001 | 8.597 | 1,163.156 | 0.797 | 435.43 | 30.684 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem1g | 3 | 1 | 10,000 | 1,000 | 1g | 70,668 | 3.891 | 0.048 | 6.628 | 1,508.653 | 3.101 | 250.281 | 131.656 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem1g | 1 | 1 | 10,000 | 1,000 | 1g | 70,668 | 1.956 | 0.021 | 0.24 | 41,606.188 | 0.057 | 38.039 | 29.613 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem1g | read | 5,977 | 695.218 | 0.078 | 0.287 | 0.691 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem1g | update | 2,017 | 234.608 | 0.155 | 2.564 | 6.554 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem1g | insert | 1,049 | 122.015 | 0.284 | 19.074 | 53.479 |
| arcadedb_sql | sweep07_t01_r01_arcadedb_sql_s00000_mem1g | delete | 957 | 111.314 | 0.379 | 19.626 | 28.874 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem1g | read | 6,041 | 911.377 | 0.065 | 0.166 | 0.33 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem1g | update | 1,906 | 287.549 | 0.898 | 3.763 | 4.906 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem1g | insert | 1,035 | 156.146 | 0.963 | 3.777 | 4.418 |
| postgresql | sweep07_t01_r01_postgresql_s00003_mem1g | delete | 1,018 | 153.581 | 0.912 | 3.725 | 4.842 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem1g | read | 6,021 | 25,051.086 | 0.008 | 0.015 | 0.022 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem1g | update | 1,959 | 8,150.652 | 0.014 | 0.025 | 0.036 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem1g | insert | 987 | 4,106.531 | 0.025 | 0.05 | 0.072 |
| sqlite | sweep07_t01_r01_sqlite_s00001_mem1g | delete | 1,033 | 4,297.919 | 0.053 | 0.111 | 0.148 |

## Dataset: stackoverflow-xlarge

| db | run_label | seed | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sqlite | sweep07_t08_r01_sqlite_s00000_mem8g | 0 | 8 | 1,000,000 | 25,000 | 8g | 108,201,302 | 4,836.762 | 139.31 | 6,504.316 | 153.744 | 173.193 | 4,329.582 | 43,023.73 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| sqlite | sweep07_t08_r01_sqlite_s00000_mem8g | read | 600,445 | 92.315 | 0.133 | 30.417 | 186.733 |
| sqlite | sweep07_t08_r01_sqlite_s00000_mem8g | update | 199,781 | 30.715 | 0.238 | 305.994 | 2,831.108 |
| sqlite | sweep07_t08_r01_sqlite_s00000_mem8g | insert | 99,846 | 15.351 | 0.098 | 245.874 | 2,530.157 |
| sqlite | sweep07_t08_r01_sqlite_s00000_mem8g | delete | 99,928 | 15.363 | 51.455 | 409.438 | 2,879 |
