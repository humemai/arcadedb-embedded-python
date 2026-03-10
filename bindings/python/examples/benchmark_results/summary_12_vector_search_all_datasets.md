# 12 Vector Search Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T14:58:09Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep12
- Total sweep rows: 7
- Versions/digest observed:
  - arcadedb: 26.3.1
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c1db044c71db11c553065dc9fcccfceae444df12210bf352b12bfc18bae68790
  - arcadedb_docker_tag: 26.3.1
  - arcadedb_embedded: auto
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: auto
  - lancedb: 0.29.2
  - milvus: 2.6.10
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1
- Search run status files: total=7, success=7, failed=0
- Note: one row = one backend run + one overquery sweep point.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du_search.json`.

## Dataset: stackoverflow-tiny

| backend | run_label | seed | mem_limit | k | query_runs | query_order | overquery_factor | effective_ef_search | effective_nprobes | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep12_r01_arcadedb_sql_s00005_m2g | 5 | 2g | 50 | 1 | shuffled | 4 |  |  | 100 | 0.943 | 153.569 | 205.292 | 16.496 | 0.874 | 15.39 | 0.006 | 288.871 | 44.375 | success |
| bruteforce | sweep12_r01_bruteforce_s00005_m2g | 5 | 2g | 50 | 1 | shuffled | 4 |  |  | 100 | 1 | 99.031 | 100.282 | 10.319 | 0.014 | 10.278 | 0 | 90.469 | 0.02 | success |
| faiss | sweep12_r01_faiss_s00000_m2g | 0 | 2g | 50 | 1 | shuffled | 4 | 100 |  | 100 | 0.839 | 184.551 | 203.626 | 18.737 | 0.014 | 18.588 | 0 | 116.242 | 31.586 | success |
| lancedb | sweep12_r01_lancedb_s00001_m2g | 1 | 2g | 50 | 1 | shuffled | 4 |  | 16 | 100 | 0.889 | 8.139 | 12.957 | 1.923 | 0.002 | 0.898 | 0 | 211.699 | 38.805 | success |
| milvus | sweep12_r01_milvus_s00004_m8g | 4 | 8g | 50 | 1 | shuffled | 4 | 100 |  | 1,000 | 0.915 | 4.28 | 15.695 | 32.148 | 0.526 | 4.668 | 0.699 | 853.898 | 231.285 | success |
| pgvector | sweep12_r01_pgvector_s00002_m2g | 2 | 2g | 50 | 1 | shuffled | 4 | 100 |  | 100 | 0.992 | 1.268 | 2.844 | 0.498 | 0.007 | 0.16 | 0.002 | 277.523 | 180.012 | success |
| qdrant | sweep12_r01_qdrant_s00003_m2g | 3 | 2g | 50 | 1 | shuffled | 4 | 100 |  | 100 | 1 | 43.529 | 45.125 | 10.28 | 0.27 | 4.504 | 0.092 | 329.137 | 84.355 | success |
