# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-05-11T05:33:32Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 3
- Versions/digest observed:
  - arcadedb: 26.5.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:976b0cf48f8feff118f69ed61ab9b8360b20c381634796970750168559d638f7
  - arcadedb_docker_tag: 26.5.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - bruteforce: builtin
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.5.1.dev0-cp312-cp312-manylinux_2_34_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.5.1.dev0
- Run status files: total=3, success=3, failed=0
- Note: `quantization` and `encoding` reflect the Example 11 build configuration used for that row.
- Note: LanceDB prefers pure `HNSW` when supported by the installed version; otherwise it falls back to single-partition `IVF_HNSW_SQ`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-medium

| backend | run_label | quantization | encoding | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g | INT8 | NONE |  |  | 0 | 8g | 4 | 5,000 | 1,242,391 | 1,242,391 | 778.707 | 0.339 | 739.641 | 38.6 | 0.055 | 6,863.488 | 3,250.941 | 3,251 | success | 0 |
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g | NONE | INT8 |  |  | 0 | 8g | 4 | 5,000 | 1,242,391 | 1,242,391 | 795.565 | 0.325 | 719.702 | 75.463 | 0.01 | 6,872.727 | 683.505 | 683.555 | success | 0 |
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g | NONE | NONE |  |  | 0 | 8g | 4 | 5,000 | 1,242,391 | 1,242,391 | 802.589 | 0.301 | 757.279 | 44.876 | 0.071 | 6,832.219 | 2,781.441 | 2,781.496 | success | 0 |
