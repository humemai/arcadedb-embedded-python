# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T21:00:03Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 5
- Versions/digest observed:
  - arcadedb_embedded: 26.3.1.dev0
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: 1.13.2
  - lancedb: 0.29.2
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
- Search run status files: total=5, success=5, failed=0
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-medium

| backend | run_label | seed | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bruteforce | sweep12_r01_bruteforce_s00000 | 0 | 50 | 1 | shuffled | 4 |  |  | 1,000 | 1 | 803.893 | 893.463 | 812.53 | 8.525 | 803.945 | 0 | 1,884.992 | 0.02 | success |
| faiss | sweep12_r01_faiss_s00000 | 0 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.759 | 172.971 | 291.085 | 175.803 | 1.268 | 174.3 | 0 | 2,127.43 | 2,000.371 | success |
| lancedb | sweep12_r01_lancedb_s00001 | 1 | 50 | 1 | shuffled | 4 |  | 16 | 1,000 | 0.935 | 14.081 | 20.665 | 15.18 | 0.01 | 14.154 | 0 | 1,779.695 | 2,511.75 | success |
| pgvector | sweep12_r01_pgvector_s00003 | 3 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.967 | 29.083 | 139.756 | 30.118 | 0.011 | 29.129 | 0.002 | 2,341.695 | 5,439.258 | success |
| qdrant | sweep12_r01_qdrant_s00004 | 4 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.996 | 74.178 | 82.071 | 92.587 | 0.311 | 74.281 | 0.041 | 2,628.266 | 1,995.008 | success |
