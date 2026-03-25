# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-25T10:29:17Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 2
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
- Search run status files: total=2, success=2, failed=0
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the Example 11 build label for the reused DB directory.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one ef_search sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-large

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | ef_search | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem16g | sweep11_r01_arcadedb_sql_s00000_mem32g |  |  | 0 | 16g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.913 | 248.323 | 285.659 | 256.732 | 7.981 | 248.425 | 0.021 | 13,561.09 | 12,229.613 | success |

## Dataset: stackoverflow-medium

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | ef_search | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem4g | sweep11_r01_arcadedb_sql_s00000_mem8g |  |  | 0 | 4g | 50 | 1 | shuffled | 100 | 100 |  | 1,000 | 0.91 | 225.69 | 277.485 | 228.453 | 2.317 | 225.812 | 0.011 | 3,542.203 | 2,780.754 | success |
