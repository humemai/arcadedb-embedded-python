# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-14T20:32:34Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 4
- Versions/digest observed:
  - arcadedb_embedded: auto
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: auto
  - lancedb: 0.29.2
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant: 1.16.3
  - qdrant_image: qdrant/qdrant:v1.11.3
- Search run status files: total=4, success=3, failed=1
- Note: `search_run_label` is the Example 12 sweep label; `build_run_label` is the Example 11 build label for the reused DB directory.
- Note: LanceDB search uses HNSW-style `ef_search` tuning when available; for the single-partition IVF fallback it also pins `nprobes=1`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-tiny

| backend | search_run_label | build_run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| faiss | sweep12_r01_faiss_s00002_mem4g | sweep11_r01_faiss_s00002_mem4g |  |  | 2 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.838 | 19.933 | 72.969 | 20.203 | 0.016 | 20.026 | 0 | 118.395 | 31.594 | success |
| lancedb | sweep12_r01_lancedb_s00000_mem4g | sweep11_r01_lancedb_s00000_mem4g |  |  | 0 | 4g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.981 | 7.092 | 9.744 | 8.747 | 0.002 | 7.734 | 0 | 219.16 | 40.121 | success |
| pgvector | sweep12_r01_pgvector_s00000_mem4g | sweep11_r01_pgvector_s00000_mem2g |  |  | 0 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.993 | 1.128 | 1.763 | 1.532 | 0.009 | 1.167 | 0.002 | 305.051 | 180.004 | success |
| qdrant | sweep12_r01_qdrant_s00001_mem4g | sweep11_r01_qdrant_s00001_mem4g |  |  | 1 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 1 | 43.6 | 44.925 | 46.787 | 0.177 | 43.706 | 0.043 | 364.043 | 66.031 | failed |
