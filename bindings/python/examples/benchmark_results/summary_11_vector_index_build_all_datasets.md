# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-14T10:21:05Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 6
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:f4dfd7e19a88145e67d3fd0852d59504374247f59b9e91ab30b9d0d726f4e46f
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
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
- Note: LanceDB prefers pure `HNSW` when supported by the installed version; otherwise it falls back to single-partition `IVF_HNSW_SQ`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-medium

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00005_mem4g |  |  | 5 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 40,471.9 | 0.411 | 40,429.629 | 41.761 | 0.067 | 3,531.727 | 2,780.691 | 2,780.738 | success | 0 |
| faiss | sweep11_r01_faiss_s00002_mem4g |  |  | 2 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 272.291 | 0 | 0 | 268.91 | 3.288 | 2,183.59 | 2,000.328 | 2,000.352 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00000_mem4g | IVF_HNSW_SQ | 1 | 0 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 102.742 | 0.001 | 65.878 | 35.92 | 0 | 1,820.965 | 2,534.132 | 2,535.824 | success | 0 |
| milvus | sweep11_r01_milvus_s00004_mem4g |  |  | 4 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 177.853 | 0.21 | 0.783 | 164.208 | 0.297 | 1,875.211 | 9,370.606 | 9,387.688 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003_mem4g |  |  | 3 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 3,071.21 | 0.007 | 2,867.267 | 200.276 | 0.003 | 3,913.195 | 5,439.027 | 5,439.277 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00001_mem4g |  |  | 1 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 403.535 | 0.612 | 0.248 | 400.614 | 0.066 | 3,530.176 | 2,669.249 | 2,608.531 | success | 0 |
