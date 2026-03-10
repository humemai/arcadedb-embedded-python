# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T21:52:44Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 6
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
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=6, success=6, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-tiny

| backend | run_label | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00000 | 0 | 2g | 1 | 1,000 | 19,591 | 19,591 | 14.114 | 0.801 | 10.515 | 2.759 | 0.006 | 369.98 | 44.316 | 44.355 | success | 0 |
| faiss | sweep11_r01_faiss_s00001 | 1 | 2g | 1 | 1,000 | 19,591 | 19,591 | 9.372 | 0 | 0 | 9.158 | 0.102 | 113.992 | 31.542 | 31.562 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00002 | 2 | 2g | 1 | 1,000 | 19,591 | 19,591 | 5.593 | 0.001 | 3.252 | 0.885 | 0 | 352.215 | 38.529 | 38.785 | success | 0 |
| milvus | sweep11_r01_milvus_s00005 | 5 | 2g | 1 | 1,000 | 19,591 | 19,591 | 23.66 | 0.509 | 1.129 | 6.6 | 0.71 | 826.957 | 160.205 | 145.586 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003 | 3 | 2g | 1 | 1,000 | 19,591 | 19,591 | 10.325 | 0.008 | 7.029 | 2.403 | 0.002 | 316.531 | 179.912 | 180.109 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00004 | 4 | 2g | 1 | 1,000 | 19,591 | 19,591 | 13.207 | 0.406 | 0.34 | 8.075 | 0.172 | 366.395 | 126.147 | 66.844 | success | 0 |
