# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T21:00:03Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 6
- Versions/digest observed:
  - arcadedb: 26.3.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:4b9fa2efc7b4be4a89a39df86581b8aa2f93b4fd062d99556216e8b6cbc1a082
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - bruteforce: builtin
  - faiss: 1.13.2
  - faiss_cpu: 1.13.2
  - lancedb: 0.29.2
  - milvus: 2.6.10
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - postgres: 18.3 (Debian 18.3-1.pgdg13+1)
  - qdrant: 1.11.3
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Run status files: total=6, success=6, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-medium

| backend | run_label | seed | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb | sweep11_r01_arcadedb_s00002 | 2 | 1 | 5,000 | 1,242,391 | 1,242,391 | 6,210.621 | 0.809 | 6,158.422 | 51.28 | 0.065 | 10,927.176 | 2,780.941 | 2,780.98 | success | 0 |
| faiss | sweep11_r01_faiss_s00000 | 0 | 1 | 5,000 | 1,242,391 | 1,242,391 | 1,881.539 | 0 | 0 | 1,880.07 | 1.355 | 2,181.09 | 2,000.328 | 2,000.352 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00001 | 1 | 1 | 5,000 | 1,242,391 | 1,242,391 | 192.572 | 0.001 | 157.081 | 34.364 | 0 | 615.492 | 2,510.042 | 2,511.73 | success | 0 |
| milvus | sweep11_r01_milvus_s00005 | 5 | 1 | 5,000 | 1,242,391 | 1,242,391 | 232.9 | 0.428 | 1.089 | 214.306 | 0.676 | 1,568.898 | 6,172.792 | 6,186.59 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003 | 3 | 1 | 5,000 | 1,242,391 | 1,242,391 | 3,621.02 | 0.009 | 3,499.401 | 119.154 | 0.002 | 8,791.324 | 5,439.136 | 5,439.395 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00004 | 4 | 1 | 5,000 | 1,242,391 | 1,242,391 | 644.281 | 0.419 | 0.451 | 639.242 | 0.091 | 2,842.938 | 2,283.438 | 2,222.902 | success | 0 |
