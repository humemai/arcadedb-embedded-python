# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-17T09:30:30Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 12
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:e381eb8b71e375e976e6e0380d5f503540d42aca89bc310399526b8498ff7db1
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: auto
  - lancedb: 0.29.2, 0.30.0
  - milvus: 2.6.10
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Search run status files: total=12, success=12, failed=0
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the Example 11 build label for the reused DB directory.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-large

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bruteforce | sweep12_r01_bruteforce_s00003_mem16g | sweep11_r01_bruteforce_s00003_mem16g |  |  | 3 | 16g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 1 | 630.619 | 704.747 | 692.107 | 61.348 | 630.694 | 0 | 8,100.863 | 0.02 | success |
| faiss | sweep12_r01_faiss_s00002_mem16g | sweep11_r01_faiss_s00002_mem16g |  |  | 2 | 16g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.756 | 14.154 | 78.142 | 20.401 | 5.718 | 14.305 | 0 | 9,084.387 | 8,792.977 | success |
| lancedb | sweep12_r01_lancedb_s00000_mem16g | sweep11_r01_lancedb_s00000_mem16g |  |  | 0 | 16g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.944 | 23.602 | 10.801 | 24.701 | 0.003 | 23.66 | 0 | 7,709.438 | 11,086.387 | success |
| qdrant | sweep12_r01_qdrant_s00001_mem16g | sweep11_r01_qdrant_s00001_mem16g |  |  | 1 | 16g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.985 | 55.218 | 58.914 | 79.45 | 0.166 | 55.326 | 0.046 | 9,519.699 | 8,888.848 | success |

## Dataset: stackoverflow-medium

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00005_mem4g | sweep11_r01_arcadedb_sql_s00005_mem4g |  |  | 5 | 4g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.85 | 213.313 | 243.102 | 216.633 | 3.109 | 213.422 | 0.01 | 3,531.156 | 2,780.754 | success |
| bruteforce | sweep12_r01_bruteforce_s00006_mem4g | sweep11_r01_bruteforce_s00006_mem4g |  |  | 6 | 4g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.999 | 156.242 | 191.561 | 176.02 | 19.102 | 156.856 | 0 | 1,870.488 | 0.02 | success |
| faiss | sweep12_r01_faiss_s00002_mem4g | sweep11_r01_faiss_s00002_mem4g |  |  | 2 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.758 | 20.275 | 73.998 | 21.805 | 1.293 | 20.358 | 0 | 2,128.383 | 2,000.371 | success |
| lancedb | sweep12_r01_lancedb_s00000_mem4g | sweep11_r01_lancedb_s00000_mem4g |  |  | 0 | 4g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.946 | 10.23 | 8.616 | 11.688 | 0.002 | 10.272 | 0 | 2,125.859 | 2,536.266 | success |
| milvus | sweep12_r01_milvus_s00004_mem8g | sweep11_r01_milvus_s00004_mem4g |  |  | 4 | 8g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.973 | 9.755 | 13.775 | 52.679 | 0.265 | 10.152 | 0.24 | 4,013.266 | 8,136.637 | success |
| pgvector | sweep12_r01_pgvector_s00003_mem4g | sweep11_r01_pgvector_s00003_mem4g |  |  | 3 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.967 | 9.738 | 15.146 | 11.91 | 0.008 | 11.437 | 0.002 | 1,273.738 | 5,438.957 | success |
| qdrant | sweep12_r01_qdrant_s00001_mem4g | sweep11_r01_qdrant_s00001_mem4g |  |  | 1 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.989 | 52.171 | 54.944 | 59.368 | 0.162 | 52.276 | 0.038 | 2,578.172 | 2,037.113 | success |

## Dataset: stackoverflow-xlarge

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lancedb | sweep12_r01_lancedb_s00000_mem64g | sweep11_r01_lancedb_s00000_mem64g |  |  | 0 | 64g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.914 | 89.059 | 13.534 | 90.643 | 0.006 | 89.133 | 0 | 34,070.949 | 52,342.379 | success |
