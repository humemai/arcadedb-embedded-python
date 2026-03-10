# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T21:52:44Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 6
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: auto
  - lancedb: 0.29.2
  - milvus: 2.6.10
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Search run status files: total=6, success=6, failed=0
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-tiny

| backend | run_label | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000 | 0 | 2g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.941 | 148.541 | 171.697 | 149.773 | 1.027 | 148.654 | 0.007 | 446.109 | 44.375 | success |
| bruteforce | sweep12_r01_bruteforce_s00000 | 0 | 2g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 1 | 99.486 | 104.006 | 99.695 | 0.017 | 99.62 | 0 | 93.41 | 0.02 | success |
| faiss | sweep12_r01_faiss_s00001 | 1 | 2g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.839 | 179.729 | 296.631 | 180.233 | 0.016 | 180.051 | 0 | 116.477 | 31.59 | success |
| lancedb | sweep12_r01_lancedb_s00002 | 2 | 2g | 50 | 1 | shuffled | 4 |  | 16 | 1,000 | 0.904 | 9.222 | 13.128 | 10.421 | 0.003 | 9.286 | 0 | 213.66 | 38.812 | success |
| milvus | sweep12_r01_milvus_s00005 | 5 | 4g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.883 | 2.13 | 2.018 | 31.754 | 0.591 | 2.602 | 0.811 | 740.703 | 146.512 | success |
| pgvector | sweep12_r01_pgvector_s00003 | 3 | 2g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.992 | 1.28 | 2.02 | 1.712 | 0.009 | 1.328 | 0.003 | 287.223 | 179.973 | success |
