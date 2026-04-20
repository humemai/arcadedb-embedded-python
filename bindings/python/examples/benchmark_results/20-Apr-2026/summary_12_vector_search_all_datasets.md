# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-04-20T16:41:48Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 2
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
- Search run status files: total=2, success=2, failed=0
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the Example 11 build label for the reused DB directory.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one ef_search sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-large

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | ef_search | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem16g | sweep11_r01_arcadedb_sql_s00000_mem32g |  |  | 0 | 16g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.914 | 151.734 | 205.095 | 162.489 | 10.481 | 151.869 | 0.024 | 13,577.004 | 12,230.332 | success |

## Dataset: stackoverflow-medium

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | ef_search | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem4g | sweep11_r01_arcadedb_sql_s00000_mem8g |  |  | 0 | 4g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.914 | 224.264 | 277.887 | 227.512 | 2.976 | 224.411 | 0.013 | 3,397.293 | 2,781.516 | success |
