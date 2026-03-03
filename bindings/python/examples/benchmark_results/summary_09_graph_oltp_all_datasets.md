# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 6
- Run status files: total=6, success=6, failed=0
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-small

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | 1 | 1 | 50,000 | 2,500 | 2g | 622,796 | 694,317 | 1.016 | 6.371 | 132.804 | 0.009 | 66.07 | 756.777 | 2.532 | 2,027.023 | 290.703 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | 0 | 1 | 50,000 | 2,500 | 2g | 622,796 | 694,317 | 0.493 | 6.003 | 133.246 | 0.005 | 40.382 | 1,238.175 | 2.104 | 2,026.953 | 290.711 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | 2 | 1 | 5,000 | 2,500 | 2g | 622,796 | 694,317 | 0.081 |  | 45.942 | 0.036 | 26.198 | 190.853 | 9.425 | 1,563.094 | 487.363 |
| python_memory | sweep09_t01_r01_python_memory_s00000 | 0 | 1 | 50,000 | 2,500 | 2g | 622,796 | 694,317 | 0 | 0 | 10.009 | 0.123 | 303.104 | 164.96 | 21.104 | 733.367 | 211.781 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | 4 | 1 | 50,000 | 2,500 | 2g | 622,796 | 694,317 | 0 | 0 | 16.559 | 0.167 | 302.277 | 165.411 | 20.951 | 733.242 | 211.848 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | 3 | 1 | 50,000 | 2,500 | 2g | 622,796 | 694,317 | 0.006 | 0.001 | 18.069 | 0.081 | 6.682 | 7,482.656 | 0.049 | 102.883 | 240.957 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | delete | 5,108 | 77.312 | 0.457 | 17.65 | 36.107 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | insert | 5,060 | 76.586 | 0.718 | 18.542 | 28.947 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | read | 30,101 | 455.595 | 0.395 | 1.974 | 4.145 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | update | 9,731 | 147.284 | 0.229 | 2.657 | 4.706 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | delete | 4,985 | 123.446 | 1.339 | 20.784 | 47.896 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | insert | 4,984 | 123.421 | 0.514 | 14.231 | 26.533 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | read | 30,147 | 746.545 | 0.085 | 0.386 | 0.597 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | update | 9,884 | 244.762 | 0.114 | 1.94 | 4.028 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | delete | 497 | 18.971 | 7.921 | 11.671 | 30.036 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | insert | 493 | 18.818 | 7.124 | 10.101 | 23.846 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | read | 2,990 | 114.13 | 2.407 | 5.107 | 33.201 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | update | 1,020 | 38.934 | 6.867 | 9.122 | 30.524 |
| python_memory | sweep09_t01_r01_python_memory_s00000 | delete | 4,985 | 16.446 | 0.029 | 61.297 | 76.737 |
| python_memory | sweep09_t01_r01_python_memory_s00000 | insert | 4,984 | 16.443 | 0.024 | 0.043 | 0.053 |
| python_memory | sweep09_t01_r01_python_memory_s00000 | read | 30,147 | 99.461 | 7.423 | 19.854 | 28.483 |
| python_memory | sweep09_t01_r01_python_memory_s00000 | update | 9,884 | 32.609 | 0.013 | 0.03 | 0.037 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | delete | 5,047 | 16.697 | 0.029 | 60.223 | 76.172 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | insert | 5,085 | 16.822 | 0.024 | 0.044 | 0.053 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | read | 30,072 | 99.485 | 7.528 | 19.617 | 28.044 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | update | 9,796 | 32.407 | 0.013 | 0.03 | 0.037 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | delete | 5,025 | 752.007 | 0.011 | 1.934 | 3.05 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | insert | 5,120 | 766.224 | 0.02 | 0.051 | 0.073 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | read | 29,913 | 4,476.574 | 0.009 | 0.032 | 0.048 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | update | 9,942 | 1,487.851 | 0.008 | 0.016 | 0.025 |
