# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T13:11:58Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 12
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585, arcadedata/arcadedb@sha256:c165ad4c2991c6a38f138b3e39b17131337e7f8b4667ec7435434e09ecdb828e
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
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=12, success=12, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-medium

| backend | run_label | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem8g | 0 | 8g | 4 | 5,000 | 1,242,391 | 1,242,391 | 17,211.696 | 0.417 | 17,162.236 | 48.914 | 0.026 | 6,851.895 | 2,780.941 | 2,780.98 | success | 0 |
| faiss | sweep11_r01_faiss_s00000_mem4g | 0 | 4g | 4 | 5,000 | 1,242,391 | 1,242,391 | 554.005 | 0 | 0 | 551.056 | 2.856 | 2,180.23 | 2,000.328 | 2,000.352 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00000_mem4g | 0 | 4g | 4 | 5,000 | 1,242,391 | 1,242,391 | 76.974 | 0.001 | 41.561 | 34.387 | 0 | 1,081.945 | 2,507.927 | 2,509.617 | success | 0 |
| milvus | sweep11_r01_milvus_s00000_mem4g | 0 | 4g | 4 | 5,000 | 1,242,391 | 1,242,391 | 209.35 | 0.376 | 1.05 | 191.839 | 0.776 | 1,999.742 | 7,415.073 | 7,431.336 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00000_mem4g | 0 | 4g | 4 | 5,000 | 1,242,391 | 1,242,391 | 3,160.773 | 0.008 | 2,978.681 | 179.946 | 0.003 | 3,901.082 | 5,439.175 | 5,439.422 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00000_mem4g | 0 | 4g | 4 | 5,000 | 1,242,391 | 1,242,391 | 451.194 | 0.604 | 0.271 | 447.109 | 0.067 | 3,473.543 | 2,865.578 | 2,804.648 | success | 0 |

## Dataset: stackoverflow-tiny

| backend | run_label | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000_mem2g | 0 | 2g | 1 | 1,000 | 19,591 | 19,591 | 14.114 | 0.801 | 10.515 | 2.759 | 0.006 | 369.98 | 44.316 | 44.355 | success | 0 |
| faiss | sweep11_r01_faiss_s00001_mem2g | 1 | 2g | 1 | 1,000 | 19,591 | 19,591 | 9.372 | 0 | 0 | 9.158 | 0.102 | 113.992 | 31.542 | 31.562 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00002_mem2g | 2 | 2g | 1 | 1,000 | 19,591 | 19,591 | 5.593 | 0.001 | 3.252 | 0.885 | 0 | 352.215 | 38.529 | 38.785 | success | 0 |
| milvus | sweep11_r01_milvus_s00005_mem2g | 5 | 2g | 1 | 1,000 | 19,591 | 19,591 | 23.66 | 0.509 | 1.129 | 6.6 | 0.71 | 826.957 | 160.205 | 145.586 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003_mem2g | 3 | 2g | 1 | 1,000 | 19,591 | 19,591 | 10.325 | 0.008 | 7.029 | 2.403 | 0.002 | 316.531 | 179.912 | 180.109 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00004_mem2g | 4 | 2g | 1 | 1,000 | 19,591 | 19,591 | 13.207 | 0.406 | 0.34 | 8.075 | 0.172 | 366.395 | 126.147 | 66.844 | success | 0 |
