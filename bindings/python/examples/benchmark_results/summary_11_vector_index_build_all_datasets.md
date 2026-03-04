# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T16:54:27Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 2
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:3f359ca6b9a9b4fde4cfda499cd6951e802a6aae6e930134f1aaf3f664184696
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - faiss: 1.13.2
  - faiss_cpu: 1.13.2
  - lancedb: 0.29.2
  - milvus_compose_version: v2.6.10
  - pgvector_image: pgvector/pgvector:pg18-trixie
  - qdrant_image: qdrant/qdrant:v1.11.3
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Run status files: total=2, success=2, failed=0
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-medium

| backend | run_label | seed | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| faiss | sweep11_r01_faiss_s00000 | 0 | 1 | 5,000 | 1,242,391 | 1,242,391 | 1,881.539 | 0 | 0 | 1,880.07 | 1.355 | 2,181.09 | 2,000.328 | 2,000.352 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00001 | 1 | 1 | 5,000 | 1,242,391 | 1,242,391 | 192.572 | 0.001 | 157.081 | 34.364 | 0 | 615.492 | 2,510.042 | 2,511.73 | success | 0 |
