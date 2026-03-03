# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 7
- Search run status files: total=7, success=7, failed=0
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-small

| backend | run_label | seed | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep12_r01_arcadedb_s00002 | 2 | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.896 | 11.797 | 12.502 | 15.145 | 2.673 | 12.055 | 0.02 | 2,617.062 | 672.875 | success |
| bruteforce | sweep12_r01_bruteforce_s00000 | 0 | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.999 | 92.357 | 167.969 | 95.467 | 2.466 | 92.713 | 0 | 494.191 | 0.016 | success |
| faiss | sweep12_r01_faiss_s00000 | 0 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.792 | 49.233 | 90.448 | 50.26 | 0.447 | 49.544 | 0 | 573.793 | 483.754 | success |
| lancedb | sweep12_r01_lancedb_s00001 | 1 | 50 | 1 | shuffled | 4 |  | 16 | 1,000 | 0.931 | 16.382 | 19.808 | 18.011 | 0.003 | 16.476 | 0 | 579.852 | 603.734 | success |
| milvus | sweep12_r01_milvus_s00005 | 5 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.985 | 11.982 | 12.342 | 39.08 | 0.413 | 12.498 | 0.805 | 2,345.113 | 3,006.406 | success |
| pgvector | sweep12_r01_pgvector_s00003 | 3 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.978 | 16.134 | 75.895 | 17.025 | 0.016 | 16.231 | 0.003 | 1,023.086 | 2,112.367 | success |
| qdrant | sweep12_r01_qdrant_s00004 | 4 | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.992 | 48.604 | 55.802 | 55.699 | 0.304 | 48.798 | 0.067 | 904.215 | 541.211 | success |
