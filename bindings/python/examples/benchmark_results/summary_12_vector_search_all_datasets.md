# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T13:11:58Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 4
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - bruteforce: builtin
  - faiss_cpu: auto
  - lancedb: auto
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Search run status files: total=4, success=4, failed=0
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-medium

| backend | run_label | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem2g | 0 | 2g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.856 | 415.986 | 494.061 | 425.149 | 5.646 | 416.11 | 0.009 | 1,871.949 | 2,781 | success |
| bruteforce | sweep12_r01_bruteforce_s00000_mem4g | 0 | 4g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 1 | 316.72 | 390.295 | 332.834 | 15.843 | 316.935 | 0 | 1,885.148 | 0.02 | success |

## Dataset: stackoverflow-tiny

| backend | run_label | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00000_mem2g | 0 | 2g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 0.941 | 148.541 | 171.697 | 149.773 | 1.027 | 148.654 | 0.007 | 446.109 | 44.375 | success |
| bruteforce | sweep12_r01_bruteforce_s00000_mem2g | 0 | 2g | 50 | 1 | shuffled | 4 |  |  | 1,000 | 1 | 99.486 | 104.006 | 99.695 | 0.017 | 99.62 | 0 | 93.41 | 0.02 | success |
