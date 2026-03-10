# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T20:52:42Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 7
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c1db044c71db11c553065dc9fcccfceae444df12210bf352b12bfc18bae68790
  - arcadedb_docker_tag: 26.3.1
  - arcadedb_embedded: auto
  - graphqlite: auto
  - python_memory: builtin
  - real_ladybug: auto
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1
- Run status files: total=27, success=7, failed=20
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_m16g | 0 | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.482 | 131.732 | 5,707.357 | 0.002 | 455.198 | 549.212 | 22.64 | 15,344.52 | 4,057.117 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_m16g | 0 | 8 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.187 | 136.272 | 6,441.466 | 0.001 | 392.245 | 637.357 | 34.938 | 13,287.195 | 4,057.117 |
| ladybug | sweep09_t01_r01_ladybug_s00002_m16g | 2 | 1 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.082 |  | 350.137 | 1.09 | 5,028.21 | 49.719 | 84.881 | 11,859.805 | 6,104.633 |
| python_memory | sweep09_t01_r01_python_memory_s00003_m16g | 3 | 1 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0 | 0 | 158.887 | 1.419 | 13,752.43 | 18.179 | 181.45 | 9,033.387 | 3,002.098 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003_m8g | 3 | 1 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.006 | 0.001 | 324.433 | 4.797 | 176.24 | 1,418.523 | 0.117 | 730.355 | 3,465.57 |
| sqlite_native | sweep09_t04_r01_sqlite_native_s00003_m8g | 3 | 4 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.979 | 0.001 | 272.435 | 0.951 | 141.632 | 1,765.143 | 1.112 | 739.402 | 3,465.59 |
| sqlite_native | sweep09_t08_r01_sqlite_native_s00003_m8g | 3 | 8 | 250,000 | 10,000 | 8g | 7,782,816 | 9,770,001 | 0.013 | 0.001 | 248.3 | 0.791 | 127.271 | 1,964.32 | 3.2 | 748.355 | 3,465.574 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_m16g | delete | 25,174 | 55.303 | 0.44 | 30.509 | 132.861 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_m16g | insert | 25,012 | 54.948 | 0.726 | 93.671 | 250.872 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_m16g | read | 150,162 | 329.883 | 0.623 | 17.394 | 82.675 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_m16g | update | 49,652 | 109.078 | 0.23 | 34.626 | 132.652 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_m16g | delete | 25,174 | 64.179 | 0.635 | 37.516 | 126.021 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_m16g | insert | 25,012 | 63.766 | 0.998 | 91.404 | 365.813 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_m16g | read | 150,162 | 382.827 | 1.199 | 31.783 | 207.669 |
| arcadedb_cypher | sweep09_t08_r01_arcadedb_cypher_s00000_m16g | update | 49,652 | 126.584 | 0.358 | 49.794 | 168.925 |
| ladybug | sweep09_t01_r01_ladybug_s00002_m16g | delete | 24,782 | 4.929 | 10.951 | 87.728 | 95.493 |
| ladybug | sweep09_t01_r01_ladybug_s00002_m16g | insert | 24,785 | 4.929 | 6.797 | 12.976 | 83.296 |
| ladybug | sweep09_t01_r01_ladybug_s00002_m16g | read | 150,097 | 29.851 | 3.101 | 85.439 | 92.555 |
| ladybug | sweep09_t01_r01_ladybug_s00002_m16g | update | 50,336 | 10.011 | 8.056 | 84.624 | 93.324 |
| python_memory | sweep09_t01_r01_python_memory_s00003_m16g | delete | 25,075 | 1.823 | 0.015 | 689.173 | 797.246 |
| python_memory | sweep09_t01_r01_python_memory_s00003_m16g | insert | 25,102 | 1.825 | 0.015 | 0.025 | 0.03 |
| python_memory | sweep09_t01_r01_python_memory_s00003_m16g | read | 149,761 | 10.89 | 42.695 | 171.426 | 203.898 |
| python_memory | sweep09_t01_r01_python_memory_s00003_m16g | update | 50,062 | 3.64 | 0.008 | 0.016 | 0.02 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003_m8g | delete | 25,075 | 142.278 | 0.014 | 17.148 | 24.015 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003_m8g | insert | 25,102 | 142.431 | 0.03 | 0.101 | 0.163 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003_m8g | read | 149,761 | 849.758 | 0.011 | 0.055 | 0.115 |
| sqlite_native | sweep09_t01_r01_sqlite_native_s00003_m8g | update | 50,062 | 284.056 | 0.01 | 0.026 | 0.096 |
| sqlite_native | sweep09_t04_r01_sqlite_native_s00003_m8g | delete | 25,075 | 177.044 | 0.018 | 23.349 | 40.331 |
| sqlite_native | sweep09_t04_r01_sqlite_native_s00003_m8g | insert | 25,102 | 177.234 | 0.02 | 0.159 | 13.099 |
| sqlite_native | sweep09_t04_r01_sqlite_native_s00003_m8g | read | 149,761 | 1,057.398 | 0.013 | 0.073 | 7.885 |
| sqlite_native | sweep09_t04_r01_sqlite_native_s00003_m8g | update | 50,062 | 353.466 | 0.008 | 0.043 | 0.141 |
| sqlite_native | sweep09_t08_r01_sqlite_native_s00003_m8g | delete | 25,075 | 197.021 | 0.018 | 19.096 | 31.176 |
| sqlite_native | sweep09_t08_r01_sqlite_native_s00003_m8g | insert | 25,102 | 197.233 | 0.022 | 0.146 | 12.888 |
| sqlite_native | sweep09_t08_r01_sqlite_native_s00003_m8g | read | 149,761 | 1,176.714 | 0.015 | 0.099 | 13.004 |
| sqlite_native | sweep09_t08_r01_sqlite_native_s00003_m8g | update | 50,062 | 393.351 | 0.008 | 0.045 | 1.575 |
