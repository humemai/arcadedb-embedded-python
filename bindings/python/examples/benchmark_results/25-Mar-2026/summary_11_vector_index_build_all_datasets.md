# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-25T10:29:17Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 2
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:185cfd16d3359d51a7e89c7b87fbd921e356c58dc4cec6ffc306371f938c637a
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
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem32g |  |  | 0 | 32g | 8 | 10,000 | 5,461,227 | 5,461,227 | 1,888.01 | 0.408 | 1,733.282 | 154.189 | 0.094 | 26,966.902 | 12,229.754 | 12,229.594 | success | 0 |

## Dataset: stackoverflow-medium

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g |  |  | 0 | 8g | 8 | 10,000 | 1,242,391 | 1,242,391 | 408.651 | 0.43 | 366.85 | 39.816 | 1.514 | 6,924.27 | 2,780.691 | 2,780.734 | success | 0 |
