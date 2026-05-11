# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-05-11T05:33:32Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 3
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
- Search run status files: total=3, success=3, failed=0
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the Example 11 build label for the reused DB directory.
- Note: `build_quantization` and `build_encoding` come from the reused Example 11 build metadata.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one ef_search sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-medium

| backend | search_run_label | build_run_label | build_quantization | build_encoding | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | ef_search | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem4g | sweep11_r01_arcadedb_sql_s00000_mem8g | INT8 | NONE |  |  | 0 | 4g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.909 | 87.121 | 100.064 | 89.998 | 2.479 | 87.176 | 0.012 | 3,131.676 | 3,251.012 | success |
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem4g | sweep11_r01_arcadedb_sql_s00000_mem8g | NONE | INT8 |  |  | 0 | 4g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.903 | 78.346 | 85.818 | 79.486 | 0.972 | 78.39 | 0.011 | 2,190.344 | 683.57 | success |
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem4g | sweep11_r01_arcadedb_sql_s00000_mem8g | NONE | NONE |  |  | 0 | 4g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.913 | 226.04 | 268.102 | 228.753 | 2.269 | 226.094 | 0.012 | 3,292.16 | 2,781.508 | success |
