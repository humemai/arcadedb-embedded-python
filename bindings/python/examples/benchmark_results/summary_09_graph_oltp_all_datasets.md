# 09 Graph OLTP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-30T20:43:25Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep09
- Total runs: 3
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c386f75daa139e46622b3ab6e7a77baf6ca7e33131cae81936fbe1de4d50d43a
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - neo4j: 2026.02.3
  - python_memory: builtin
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=3, success=3, failed=0
- Note: `schema_time_s`/`index_time_s`/`load_time_s`/`counts_time_s` are setup phases; `oltp_crud_time_s` and latency metrics are OLTP workload only.
- Note: per-op `throughput_s` is computed as `op_count / oltp_crud_time_s`.
- Scope note: Scope: OLTP throughput/stability benchmark. ArcadeDB, Ladybug, GraphQLite, SQLite native, and Python in-memory use the same logical schema, ID indexing, ingestion dataset/relationships, and CRUD operation mix. Query language and execution path remain engine-native.

## Dataset: stackoverflow-large

| db | run_label | seed | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | schema_time_s | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | 0 | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0.164 | 130.28 | 6,104.965 | 0.002 | 290.312 | 861.142 | 15.061 | 13,197.523 | 12,753 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 4 | 250,000 | 10,000 | 32g | 7,782,816 | 9,770,001 | 0.151 | 131.424 | 5,667.299 | 0.001 | 200.169 | 1,248.944 | 13.346 | 18,692.27 | 12,753.133 |
| neo4j | sweep09_t04_r01_neo4j_s00000_mem16g | 0 | 4 | 250,000 | 10,000 | 16g | 7,782,816 | 9,770,001 | 0 | 0.243 | 840.012 | 0.04 | 305.951 | 817.125 | 24.95 | 11,868.905 | 7,367.043 |

### Per-operation OLTP details

| db | run_label | op | count | throughput_s | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|---|---|
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | delete | 25,174 | 86.714 | 0.546 | 21.731 | 104.81 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | insert | 25,012 | 86.156 | 0.64 | 64.135 | 183.087 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | read | 150,162 | 517.243 | 0.529 | 10.711 | 19.815 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem16g | update | 49,652 | 171.03 | 0.189 | 18.872 | 85.611 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | delete | 25,174 | 125.764 | 0.307 | 17.438 | 25.637 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | insert | 25,012 | 124.954 | 0.562 | 11.547 | 25.058 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | read | 150,162 | 750.175 | 0.428 | 14.365 | 37.009 |
| arcadedb_cypher | sweep09_t04_r01_arcadedb_cypher_s00000_mem32g | update | 49,652 | 248.05 | 0.186 | 2.236 | 14.637 |
| neo4j | sweep09_t04_r01_neo4j_s00000_mem16g | delete | 25,174 | 82.281 | 2.179 | 46.771 | 67.789 |
| neo4j | sweep09_t04_r01_neo4j_s00000_mem16g | insert | 25,012 | 81.752 | 3.347 | 31.566 | 54.776 |
| neo4j | sweep09_t04_r01_neo4j_s00000_mem16g | read | 150,162 | 490.804 | 1.446 | 14.484 | 41.039 |
| neo4j | sweep09_t04_r01_neo4j_s00000_mem16g | update | 49,652 | 162.288 | 2.002 | 22.942 | 47.471 |
