# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 6
- Run status files: total=6, success=6, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-small

| backend | run_label | seed | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep11_r01_arcadedb_s00002 | 2 | 4 | 2,500 | 300,424 | 300,424 | 576.113 | 0.522 | 561.048 | 14.444 | 0.025 | 3,109.391 | 672.816 | 672.848 | success | 0 |
| faiss | sweep11_r01_faiss_s00000 | 0 | 4 | 2,500 | 300,424 | 300,424 | 81.946 | 0 | 0 | 79.516 | 2.254 | 601.352 | 483.704 | 483.727 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00001 | 1 | 4 | 2,500 | 300,424 | 300,424 | 27.549 | 0.001 | 13.535 | 10.802 | 0 | 584.328 | 602.665 | 603.707 | success | 0 |
| milvus | sweep11_r01_milvus_s00005 | 5 | 4 | 2,500 | 300,424 | 300,424 | 97.997 | 0.408 | 0.892 | 80.826 | 0.438 | 1,715.664 | 2,177.781 | 2,169.914 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003 | 3 | 4 | 2,500 | 300,424 | 300,424 | 297.777 | 0.047 | 248.143 | 37.89 | 0.003 | 2,302.898 | 2,112.317 | 2,112.645 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00004 | 4 | 4 | 2,500 | 300,424 | 300,424 | 123.797 | 0.325 | 0.304 | 118.303 | 0.062 | 1,227.391 | 736.96 | 703.348 | success | 0 |
