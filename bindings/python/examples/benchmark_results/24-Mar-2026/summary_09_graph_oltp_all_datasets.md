# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-24T19:19:11Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 3
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:85144b5986b475530a67d95659a93457c9b804e26ac22065af540822670de953
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - python_memory: builtin
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=5, success=2, failed=3
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 1 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.304 | 155.333 | 6,088.078 | 0.002 | 541.346 | 461.812 | 5.694 | 17,128.445 | 3,972.051 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g |  | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.164 | 134.037 | 6,696.966 | 0.003 | 439.757 | 568.496 | 26.509 | 13,355.812 |  |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 4 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.173 | 133.167 | 6,238.478 | 0.001 | 245.873 | 1,016.783 | 15.274 | 19,118.336 | 12,753.121 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 46.503 | 0.141 | 17.609 | 25.054 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 46.203 | 0.465 | 0.983 | 1.623 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 277.386 | 0.244 | 5.66 | 9.953 |
| arcadedb_cypher | sweep09_t01_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 91.719 | 0.142 | 0.358 | 0.577 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | delete | 25,174 | 57.245 | 0.755 | 36.945 | 140.229 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | insert | 25,012 | 56.877 | 0.813 | 85.947 | 244.087 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | read | 150,162 | 341.466 | 0.746 | 22.289 | 46.3 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | update | 49,652 | 112.908 | 0.237 | 31.398 | 119.424 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 102.386 | 0.276 | 19.462 | 72.06 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 101.727 | 0.576 | 19.499 | 131.043 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 610.729 | 0.415 | 14.245 | 38.034 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 201.941 | 0.179 | 8.637 | 64.979 |
