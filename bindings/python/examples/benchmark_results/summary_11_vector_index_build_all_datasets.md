# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T20:52:42Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 6
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
- Run status files: total=6, success=6, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-tiny

| backend | run_label | seed | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00005_m2g | 5 | 1 | 1,000 | 19,591 | 19,591 | 11.955 | 0.767 | 8.563 | 2.562 | 0.029 | 370.504 | 44.316 | 44.355 | success | 0 |
| faiss | sweep11_r01_faiss_s00000_m2g | 0 | 1 | 1,000 | 19,591 | 19,591 | 12.702 | 0 | 0 | 9.269 | 3.303 | 113.891 | 31.542 | 31.566 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00001_m2g | 1 | 1 | 1,000 | 19,591 | 19,591 | 5.929 | 0.001 | 4.2 | 0.65 | 0 | 348.941 | 38.526 | 38.785 | success | 0 |
| milvus | sweep11_r01_milvus_s00004_m2g | 4 | 1 | 1,000 | 19,591 | 19,591 | 25.012 | 0.578 | 1.108 | 6.482 | 0.582 | 850.578 | 160.204 | 145.562 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00002_m2g | 2 | 1 | 1,000 | 19,591 | 19,591 | 12.071 | 0.008 | 5.802 | 3.669 | 0.003 | 316.539 | 179.92 | 180.148 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00003_m2g | 3 | 1 | 1,000 | 19,591 | 19,591 | 14.125 | 0.333 | 0.289 | 9.388 | 0.042 | 337.141 | 127.881 | 68.582 | success | 0 |
