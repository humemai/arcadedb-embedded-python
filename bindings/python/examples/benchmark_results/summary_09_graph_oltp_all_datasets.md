# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T13:11:58Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 28
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:1b7ae0a2be5b648cf85f874c82225827658c5130153615b39b83471b4715f2b0, arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585, ... (+2 more)
  - arcadedb_docker_tag: 26.3.1, 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - duckdb: auto
  - graphqlite: auto
  - python_memory: builtin
  - real_ladybug: auto
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl, arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1, 26.4.1.dev0
- Run status files: total=56, success=28, failed=28
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 1 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.294 | 168.972 | 6,434.854 | 0.001 | 483.19 | 517.395 | 3.098 | 18,639.383 | 4,057.113 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | 0 | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.482 | 131.732 | 5,707.357 | 0.002 | 455.198 | 549.212 | 22.64 | 15,344.52 | 4,057.117 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_mem16g | 0 | 8 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.187 | 136.272 | 6,441.466 | 0.001 | 392.245 | 637.357 | 34.938 | 13,287.195 | 4,057.117 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem16g | 0 | 1 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.041 | 0 | 318.645 | 0.185 | 1,632.358 | 153.153 | 27.432 | 7,547.707 | 6,959.012 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | 0 | 1 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.041 | 0 | 349.088 | 0.186 | 1,627.595 | 153.601 | 27.273 | 7,613.152 | 6,960.762 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem8g | 0 | 4 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.075 | 0 | 355.896 | 0.183 | 1,049.554 | 238.196 | 55.926 | 7,122.297 | 6,970.262 |
| duckdb | sweep09_t08_r01_duckdb_s00000_mem8g | 0 | 8 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.054 | 0 | 368.718 | 0.172 | 1,025.813 | 243.709 | 114.924 | 7,194.75 | 6,969.773 |
| ladybug | sweep09_t01_r01_ladybug_s00002_mem16g | 2 | 1 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.082 |  | 350.137 | 1.09 | 5,028.21 | 49.719 | 84.881 | 11,859.805 | 6,104.633 |
| python_memory | sweep09_t01_r01_python_memory_s00003_mem16g | 3 | 1 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0 | 0 | 158.887 | 1.419 | 13,752.43 | 18.179 | 181.45 | 9,033.387 | 3,002.098 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem8g | 3 | 1 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.006 | 0.001 | 324.433 | 4.797 | 176.24 | 1,418.523 | 0.117 | 730.355 | 3,465.57 |
| sqlite | sweep09_t04_r01_sqlite_s00003_mem8g | 3 | 4 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.979 | 0.001 | 272.435 | 0.951 | 141.632 | 1,765.143 | 1.112 | 739.402 | 3,465.59 |
| sqlite | sweep09_t08_r01_sqlite_s00003_mem8g | 3 | 8 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.013 | 0.001 | 248.3 | 0.791 | 127.271 | 1,964.32 | 3.2 | 748.355 | 3,465.574 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 52.1 | 0.124 | 15.927 | 21.602 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 51.764 | 0.422 | 0.89 | 1.768 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 310.772 | 0.241 | 2.912 | 6.36 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 102.759 | 0.137 | 0.324 | 0.556 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | delete | 25,174 | 55.303 | 0.44 | 30.509 | 132.861 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | insert | 25,012 | 54.948 | 0.726 | 93.671 | 250.872 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | read | 150,162 | 329.883 | 0.623 | 17.394 | 82.675 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | update | 49,652 | 109.078 | 0.23 | 34.626 | 132.652 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_mem16g | delete | 25,174 | 64.179 | 0.635 | 37.516 | 126.021 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_mem16g | insert | 25,012 | 63.766 | 0.998 | 91.404 | 365.813 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_mem16g | read | 150,162 | 382.827 | 1.199 | 31.783 | 207.669 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_mem16g | update | 49,652 | 126.584 | 0.358 | 49.794 | 168.925 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem16g | delete | 25,174 | 15.422 | 1.441 | 64.366 | 83.715 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem16g | insert | 25,012 | 15.323 | 17.953 | 33.965 | 47.474 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem16g | read | 150,162 | 91.991 | 1.899 | 10.813 | 13.04 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem16g | update | 49,652 | 30.417 | 1.855 | 15.005 | 23.756 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | delete | 25,174 | 15.467 | 1.436 | 64.387 | 82.52 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | insert | 25,012 | 15.367 | 18.018 | 34.021 | 46.043 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | read | 150,162 | 92.26 | 1.899 | 10.734 | 12.943 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | update | 49,652 | 30.506 | 1.838 | 14.919 | 23.427 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem8g | delete | 25,174 | 23.985 | 19.198 | 133.989 | 185.227 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem8g | insert | 25,012 | 23.831 | 32.665 | 88.818 | 110.943 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem8g | read | 150,162 | 143.072 | 8.702 | 26.969 | 38.903 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem8g | update | 49,652 | 47.308 | 11.803 | 36.922 | 48.501 |
| duckdb | sweep09_t08_r01_duckdb_s00000_mem8g | delete | 25,174 | 24.541 | 25.36 | 262.185 | 350.621 |
| duckdb | sweep09_t08_r01_duckdb_s00000_mem8g | insert | 25,012 | 24.383 | 70.729 | 177.878 | 213.898 |
| duckdb | sweep09_t08_r01_duckdb_s00000_mem8g | read | 150,162 | 146.383 | 15.057 | 38.39 | 51.538 |
| duckdb | sweep09_t08_r01_duckdb_s00000_mem8g | update | 49,652 | 48.403 | 24.395 | 67.434 | 84.709 |
| ladybug | sweep09_t01_r01_ladybug_s00002_mem16g | delete | 24,782 | 4.929 | 10.951 | 87.728 | 95.493 |
| ladybug | sweep09_t01_r01_ladybug_s00002_mem16g | insert | 24,785 | 4.929 | 6.797 | 12.976 | 83.296 |
| ladybug | sweep09_t01_r01_ladybug_s00002_mem16g | read | 150,097 | 29.851 | 3.101 | 85.439 | 92.555 |
| ladybug | sweep09_t01_r01_ladybug_s00002_mem16g | update | 50,336 | 10.011 | 8.056 | 84.624 | 93.324 |
| python_memory | sweep09_t01_r01_python_memory_s00003_mem16g | delete | 25,075 | 1.823 | 0.015 | 689.173 | 797.246 |
| python_memory | sweep09_t01_r01_python_memory_s00003_mem16g | insert | 25,102 | 1.825 | 0.015 | 0.025 | 0.03 |
| python_memory | sweep09_t01_r01_python_memory_s00003_mem16g | read | 149,761 | 10.89 | 42.695 | 171.426 | 203.898 |
| python_memory | sweep09_t01_r01_python_memory_s00003_mem16g | update | 50,062 | 3.64 | 0.008 | 0.016 | 0.02 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem8g | delete | 25,075 | 142.278 | 0.014 | 17.148 | 24.015 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem8g | insert | 25,102 | 142.431 | 0.03 | 0.101 | 0.163 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem8g | read | 149,761 | 849.758 | 0.011 | 0.055 | 0.115 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem8g | update | 50,062 | 284.056 | 0.01 | 0.026 | 0.096 |
| sqlite | sweep09_t04_r01_sqlite_s00003_mem8g | delete | 25,075 | 177.044 | 0.018 | 23.349 | 40.331 |
| sqlite | sweep09_t04_r01_sqlite_s00003_mem8g | insert | 25,102 | 177.234 | 0.02 | 0.159 | 13.099 |
| sqlite | sweep09_t04_r01_sqlite_s00003_mem8g | read | 149,761 | 1,057.398 | 0.013 | 0.073 | 7.885 |
| sqlite | sweep09_t04_r01_sqlite_s00003_mem8g | update | 50,062 | 353.466 | 0.008 | 0.043 | 0.141 |
| sqlite | sweep09_t08_r01_sqlite_s00003_mem8g | delete | 25,075 | 197.021 | 0.018 | 19.096 | 31.176 |
| sqlite | sweep09_t08_r01_sqlite_s00003_mem8g | insert | 25,102 | 197.233 | 0.022 | 0.146 | 12.888 |
| sqlite | sweep09_t08_r01_sqlite_s00003_mem8g | read | 149,761 | 1,176.714 | 0.015 | 0.099 | 13.004 |
| sqlite | sweep09_t08_r01_sqlite_s00003_mem8g | update | 50,062 | 393.351 | 0.008 | 0.045 | 1.575 |

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.727 | 19.887 | 660.884 | 0.001 | 201.595 | 496.045 | 4.622 | 7,339.707 | 1,247.484 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | 0 | 4 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.209 | 11.554 | 850.308 | 0.001 | 157.169 | 636.258 | 12.932 | 6,143.281 | 1,247.477 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.683 | 22.426 | 699.452 | 0.003 | 81.893 | 1,221.101 | 3.138 | 7,861.051 | 1,247.598 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem4g | 0 | 1 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0.215 | 0 | 94.573 | 0.072 | 791.608 | 126.325 | 36.144 | 3,498.746 | 1,966.168 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.174 | 0 | 79.227 | 0.088 | 793.931 | 125.956 | 36.089 | 3,491.52 | 1,965.922 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0.042 | 0 | 102.99 | 0.09 | 490.868 | 203.721 | 70.884 | 3,219.801 | 1,966.426 |
| ladybug | sweep09_t01_r01_ladybug_s00000_mem8g | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.186 |  | 121.483 | 0.168 | 1,920.342 | 52.074 | 71.822 | 5,228.199 | 1,959.586 |
| python_memory | sweep09_t01_r01_python_memory_s00005_mem4g | 5 | 1 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0 | 0 | 34.221 | 0.499 | 1,804.339 | 55.422 | 65.018 | 2,733.129 | 935.566 |
| python_memory | sweep09_t04_r01_python_memory_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0 | 0 | 42.666 | 0.48 | 2,387.573 | 41.884 | 322.502 | 2,732.168 | 936.562 |
| sqlite | sweep09_t01_r01_sqlite_s00004_mem4g | 4 | 1 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0.004 | 0.001 | 75.524 | 0.218 | 21.35 | 4,683.876 | 0.055 | 257.527 | 1,079.727 |
| sqlite | sweep09_t04_r01_sqlite_s00000_mem4g | 0 | 4 | 100,000 | 5,000 | 4g | 2,202,019 | 2,877,037 | 0.012 | 0.001 | 84.285 | 0.235 | 38.45 | 2,600.794 | 0.097 | 265.406 | 1,079.719 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | delete | 10,021 | 49.709 | 0.187 | 18.482 | 28.552 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | insert | 10,067 | 49.937 | 0.52 | 19.321 | 26.684 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | read | 60,074 | 297.994 | 0.337 | 3.647 | 24.793 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem8g | update | 19,838 | 98.405 | 0.162 | 2.783 | 4.411 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | delete | 10,021 | 63.759 | 0.281 | 19.265 | 75.679 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | insert | 10,067 | 64.052 | 0.771 | 53.127 | 254.222 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | read | 60,074 | 382.225 | 0.527 | 8.988 | 140.998 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem8g | update | 19,838 | 126.221 | 0.249 | 21.799 | 110.985 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem8g | delete | 10,021 | 122.367 | 2.453 | 22.09 | 33.31 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem8g | insert | 10,067 | 122.928 | 0.372 | 14.042 | 23.591 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem8g | read | 60,074 | 733.564 | 0.055 | 0.293 | 0.482 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem8g | update | 19,838 | 242.242 | 0.078 | 1.961 | 4.041 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem4g | delete | 10,021 | 12.659 | 1.365 | 80.138 | 183.883 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem4g | insert | 10,067 | 12.717 | 22.922 | 84.108 | 182.048 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem4g | read | 60,074 | 75.889 | 1.278 | 4.452 | 5.555 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem4g | update | 19,838 | 25.06 | 2.324 | 26.208 | 73.958 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | delete | 10,021 | 12.622 | 1.366 | 82.397 | 175.835 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | insert | 10,067 | 12.68 | 23.049 | 86.583 | 187.416 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | read | 60,074 | 75.667 | 1.276 | 4.418 | 5.463 |
| duckdb | sweep09_t01_r01_duckdb_s00000_mem8g | update | 19,838 | 24.987 | 2.327 | 25.619 | 70.527 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem4g | delete | 10,021 | 20.415 | 21.955 | 159.944 | 281.991 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem4g | insert | 10,067 | 20.509 | 37.804 | 115.943 | 236.314 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem4g | read | 60,074 | 122.383 | 9.485 | 24.488 | 58.087 |
| duckdb | sweep09_t04_r01_duckdb_s00000_mem4g | update | 19,838 | 40.414 | 17.51 | 45.539 | 120.899 |
| ladybug | sweep09_t01_r01_ladybug_s00000_mem8g | delete | 10,021 | 5.218 | 20.377 | 81.555 | 138.177 |
| ladybug | sweep09_t01_r01_ladybug_s00000_mem8g | insert | 10,067 | 5.242 | 16.775 | 57.912 | 124.164 |
| ladybug | sweep09_t01_r01_ladybug_s00000_mem8g | read | 60,074 | 31.283 | 4.063 | 71.058 | 88.273 |
| ladybug | sweep09_t01_r01_ladybug_s00000_mem8g | update | 19,838 | 10.33 | 19.316 | 74.72 | 130.654 |
| python_memory | sweep09_t01_r01_python_memory_s00005_mem4g | delete | 10,041 | 5.565 | 0.019 | 205.076 | 219.311 |
| python_memory | sweep09_t01_r01_python_memory_s00005_mem4g | insert | 9,857 | 5.463 | 0.018 | 0.029 | 0.034 |
| python_memory | sweep09_t01_r01_python_memory_s00005_mem4g | read | 60,111 | 33.315 | 20.605 | 58.292 | 82.247 |
| python_memory | sweep09_t01_r01_python_memory_s00005_mem4g | update | 19,991 | 11.079 | 0.01 | 0.02 | 0.023 |
| python_memory | sweep09_t04_r01_python_memory_s00000_mem4g | delete | 10,021 | 4.197 | 88.92 | 379.754 | 578.183 |
| python_memory | sweep09_t04_r01_python_memory_s00000_mem4g | insert | 10,067 | 4.216 | 94.499 | 354.702 | 549.178 |
| python_memory | sweep09_t04_r01_python_memory_s00000_mem4g | read | 60,074 | 25.161 | 57.522 | 313.755 | 502.769 |
| python_memory | sweep09_t04_r01_python_memory_s00000_mem4g | update | 19,838 | 8.309 | 0.065 | 280.254 | 468.762 |
| sqlite | sweep09_t01_r01_sqlite_s00004_mem4g | delete | 10,072 | 471.76 | 0.011 | 4.79 | 7.284 |
| sqlite | sweep09_t01_r01_sqlite_s00004_mem4g | insert | 10,064 | 471.385 | 0.022 | 0.057 | 0.081 |
| sqlite | sweep09_t01_r01_sqlite_s00004_mem4g | read | 60,037 | 2,812.059 | 0.009 | 0.03 | 0.049 |
| sqlite | sweep09_t01_r01_sqlite_s00004_mem4g | update | 19,827 | 928.672 | 0.008 | 0.014 | 0.026 |
| sqlite | sweep09_t04_r01_sqlite_s00000_mem4g | delete | 10,021 | 260.626 | 0.018 | 8.82 | 16.981 |
| sqlite | sweep09_t04_r01_sqlite_s00000_mem4g | insert | 10,067 | 261.822 | 0.03 | 0.088 | 0.15 |
| sqlite | sweep09_t04_r01_sqlite_s00000_mem4g | read | 60,074 | 1,562.401 | 0.013 | 0.049 | 0.094 |
| sqlite | sweep09_t04_r01_sqlite_s00000_mem4g | update | 19,838 | 515.945 | 0.01 | 0.025 | 0.063 |

## Dataset: stackoverflow-tiny

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001_mem1g | 1 | 1 | 10,000 | 1,000 | 1g | 40,260 | 42,088 | 0.79 | 0.942 | 11.784 | 0.001 | 25.03 | 399.513 | 15.345 | 519.008 | 22.262 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem1g | 0 | 1 | 10,000 | 1,000 | 1g | 40,260 | 42,088 | 0.398 | 0.95 | 12.302 | 0.001 | 9.544 | 1,047.758 | 1.251 | 359.566 | 22.246 |
| python_memory | sweep09_t01_r01_python_memory_s00004_mem1g | 4 | 1 | 10,000 | 1,000 | 1g | 40,260 | 42,088 | 0 | 0 | 4.063 | 0.007 | 1.724 | 5,801.49 | 0.646 | 86.098 | 15.262 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem1g | 3 | 1 | 10,000 | 1,000 | 1g | 40,260 | 42,088 | 0.004 | 0.001 | 0.551 | 0.005 | 0.104 | 96,417.703 | 0.018 | 47.902 | 17.766 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001_mem1g | delete | 1,033 | 41.27 | 0.226 | 22.112 | 29.451 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001_mem1g | insert | 987 | 39.432 | 0.581 | 25.017 | 53.727 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001_mem1g | read | 6,021 | 240.547 | 0.414 | 3.48 | 51.423 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001_mem1g | update | 1,959 | 78.265 | 0.257 | 3.185 | 16.745 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem1g | delete | 957 | 100.27 | 0.404 | 23.046 | 54.462 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem1g | insert | 1,049 | 109.91 | 0.357 | 20.28 | 56.782 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem1g | read | 5,977 | 626.245 | 0.075 | 0.355 | 0.644 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000_mem1g | update | 2,017 | 211.333 | 0.111 | 2.583 | 4.967 |
| python_memory | sweep09_t01_r01_python_memory_s00004_mem1g | delete | 981 | 569.126 | 0.007 | 1.992 | 2.87 |
| python_memory | sweep09_t01_r01_python_memory_s00004_mem1g | insert | 1,059 | 614.378 | 0.006 | 0.013 | 0.016 |
| python_memory | sweep09_t01_r01_python_memory_s00004_mem1g | read | 6,027 | 3,496.558 | 0.172 | 0.612 | 0.915 |
| python_memory | sweep09_t01_r01_python_memory_s00004_mem1g | update | 1,933 | 1,121.428 | 0.003 | 0.007 | 0.009 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem1g | delete | 1,018 | 9,815.322 | 0.004 | 0.092 | 0.144 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem1g | insert | 1,035 | 9,979.232 | 0.006 | 0.017 | 0.033 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem1g | read | 6,041 | 58,245.935 | 0.002 | 0.011 | 0.019 |
| sqlite | sweep09_t01_r01_sqlite_s00003_mem1g | update | 1,906 | 18,377.214 | 0.003 | 0.01 | 0.017 |

## Dataset: stackoverflow-xlarge

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sqlite | sweep09_t08_r01_sqlite_s00000_mem8g | 0 | 8 | 1,000,000 | 25,000 | 8g | 37,829,568 | 49,990,847 | 0.318 | 0.011 | 3,013.252 | 229.017 | 1,756.719 | 569.243 | 79.49 | 3,287.816 | 17,767.434 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| sqlite | sweep09_t08_r01_sqlite_s00000_mem8g | delete | 99,928 | 56.883 | 0.147 | 130.236 | 227.868 |
| sqlite | sweep09_t08_r01_sqlite_s00000_mem8g | insert | 99,846 | 56.837 | 0.101 | 67.302 | 138.861 |
| sqlite | sweep09_t08_r01_sqlite_s00000_mem8g | read | 600,445 | 341.799 | 0.164 | 79.862 | 147.917 |
| sqlite | sweep09_t08_r01_sqlite_s00000_mem8g | update | 199,781 | 113.724 | 0.043 | 29.869 | 101.072 |
