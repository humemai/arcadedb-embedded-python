# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T16:54:27Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 5
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:3f359ca6b9a9b4fde4cfda499cd6951e802a6aae6e930134f1aaf3f664184696
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - graphqlite: 0.3.7
  - python_memory: builtin
  - real_ladybug: 0.15.1
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Run status files: total=5, success=5, failed=0
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-medium

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | 1 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.341 | 22.32 | 750.541 | 0.01 | 152.776 | 654.551 | 2.906 | 6,997.781 | 1,247.473 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | 0 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.399 | 21.737 | 761.122 | 0.002 | 103.311 | 967.95 | 4.29 | 7,948.781 | 1,247.613 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | 2 | 1 | 10,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.107 |  | 111.3 | 0.284 | 91.343 | 109.477 | 51.768 | 2,926.293 | 1,930.914 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | 4 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0 | 0 | 44.642 | 0.532 | 2,338.849 | 42.756 | 87.7 | 2,733.41 | 936.898 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | 3 | 1 | 100,000 | 5,000 | 8g | 2,202,019 | 2,877,037 | 0.004 | 0.001 | 49.914 | 0.259 | 12.647 | 7,906.987 | 0.067 | 255.457 | 1,079.723 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | delete | 10,150 | 66.437 | 0.384 | 10.31 | 76.018 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | insert | 10,018 | 65.573 | 0.605 | 33.082 | 74.023 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | read | 60,179 | 393.902 | 0.35 | 2.064 | 3.785 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00001 | update | 19,653 | 128.639 | 0.213 | 5.966 | 10.028 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | delete | 10,021 | 96.998 | 3.298 | 26.124 | 47.502 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | insert | 10,067 | 97.444 | 0.474 | 17.625 | 38.044 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | read | 60,074 | 581.486 | 0.082 | 0.397 | 0.517 |
| arcadedb_sql | sweep09_t01_r01_arcadedb_sql_s00000 | update | 19,838 | 192.022 | 0.105 | 2.512 | 5.348 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | delete | 988 | 10.816 | 8.307 | 53.7 | 72.636 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | insert | 984 | 10.773 | 6.938 | 9.939 | 57.512 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | read | 6,047 | 66.201 | 2.745 | 56.073 | 70.916 |
| ladybug | sweep09_t01_r01_ladybug_s00002 | update | 1,981 | 21.687 | 6.658 | 10.035 | 55.442 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | delete | 10,072 | 4.306 | 0.029 | 241.067 | 301.776 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | insert | 10,064 | 4.303 | 0.025 | 0.042 | 0.047 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | read | 60,037 | 25.669 | 26.386 | 80.242 | 111.928 |
| python_memory | sweep09_t01_r01_python_memory_s00004 | update | 19,827 | 8.477 | 0.014 | 0.03 | 0.034 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | delete | 9,763 | 771.959 | 0.014 | 5.311 | 8.751 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | insert | 10,128 | 800.82 | 0.026 | 0.069 | 0.104 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | read | 60,134 | 4,754.788 | 0.011 | 0.036 | 0.063 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003 | update | 19,975 | 1,579.421 | 0.009 | 0.018 | 0.035 |
