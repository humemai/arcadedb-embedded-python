# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-04-20T16:41:48Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 2
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:2b492d3879174bb56eb30f95cbbb0f5e433f5755869eda8929b782280dac4244
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - bruteforce: builtin
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=2, success=2, failed=0
- Note: LanceDB prefers pure `HNSW` when supported by the installed version; otherwise it falls back to single-partition `IVF_HNSW_SQ`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-large

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem32g |  |  | 0 | 32g | 8 | 10,000 | 5,461,227 | 5,461,227 | 2,018.532 | 0.295 | 1,842.518 | 175.607 | 0.063 | 27,010.812 | 12,230.254 | 12,230.305 | success | 0 |

## Dataset: stackoverflow-medium

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g |  |  | 0 | 8g | 8 | 5,000 | 1,242,391 | 1,242,391 | 412.938 | 0.269 | 373.061 | 39.523 | 0.038 | 6,931.047 | 2,781.441 | 2,781.484 | success | 0 |
