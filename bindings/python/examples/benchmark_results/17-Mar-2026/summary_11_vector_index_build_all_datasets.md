# 11 Vector Index Build Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-17T09:30:29Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep11
- Total runs: 12
- Versions/digest observed:
  - arcadedb: 26.4.1.dev0
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:b51ab081326e84f9281e3a0d0b331ab06528787a55b3a9cfc23785276934ac92, arcadedata/arcadedb@sha256:e381eb8b71e375e976e6e0380d5f503540d42aca89bc310399526b8498ff7db1
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
- Note: LanceDB prefers pure `HNSW` when supported by the installed version; otherwise it falls back to single-partition `IVF_HNSW_SQ`.
- Note: heuristic HNSW similarity only, not a formal metric: Faiss `HNSWFlat` ~= 100%; pgvector/Qdrant/Milvus HNSW ~= 85-95%; LanceDB pure `HNSW` ~= 90-95%; LanceDB single-partition `IVF_HNSW_SQ` ~= 75%; bruteforce is exact search, not HNSW.
- Note: times are phase-level benchmark timings from each run result.
- Note: `du_mib` is measured filesystem usage from `disk_usage_du.json`.

## Dataset: stackoverflow-large

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| faiss | sweep11_r01_faiss_s00002_mem16g |  |  | 2 | 16g | 8 | 10,000 | 5,461,227 | 5,461,227 | 1,301.365 | 0 | 0 | 1,292.334 | 8.923 | 9,220.664 | 8,792.933 | 8,792.957 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00000_mem16g | IVF_HNSW_SQ | 1 | 0 | 16g | 8 | 10,000 | 5,461,227 | 5,461,227 | 458.75 | 0.002 | 295.195 | 162.586 | 0 | 5,189.641 | 11,082.237 | 11,086.367 | success | 0 |
| milvus | sweep11_r01_milvus_s00004_mem16g |  |  | 4 | 16g | 8 | 10,000 | 5,461,227 | 5,461,227 | 573.837 | 0.223 | 0.786 | 558.145 | 0.225 | 2,098.781 | 28,504.65 | 28,593.508 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003_mem16g |  |  | 3 | 16g | 8 | 10,000 | 5,461,227 | 5,461,227 | 10,678.269 | 0.006 | 9,936.255 | 738.916 | 0.003 | 14,499.773 | 20,347.128 | 20,347.441 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00001_mem16g |  |  | 1 | 16g | 8 | 10,000 | 5,461,227 | 5,461,227 | 1,513.433 | 0.168 | 0.276 | 1,509.315 | 0.044 | 10,659.523 | 9,341.247 | 9,286.531 | success | 0 |

## Dataset: stackoverflow-medium

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sql | sweep11_r01_arcadedb_sql_s00005_mem4g |  |  | 5 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 41,696.415 | 0.38 | 41,651.176 | 42.939 | 1.887 | 3,547.059 | 2,780.691 | 2,780.73 | success | 0 |
| faiss | sweep11_r01_faiss_s00002_mem4g |  |  | 2 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 263.48 | 0 | 0 | 262.393 | 0.979 | 2,177.816 | 2,000.328 | 2,000.352 | success | 0 |
| lancedb | sweep11_r01_lancedb_s00000_mem4g | IVF_HNSW_SQ | 1 | 0 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 95.525 | 0.001 | 61.577 | 32.621 | 0 | 1,622.492 | 2,534.549 | 2,536.246 | success | 0 |
| milvus | sweep11_r01_milvus_s00004_mem4g |  |  | 4 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 190.58 | 0.209 | 0.792 | 175.046 | 0.254 | 1,927.609 | 8,575.717 | 8,592.477 | success | 0 |
| pgvector | sweep11_r01_pgvector_s00003_mem4g |  |  | 3 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 3,091.844 | 0.007 | 2,896.786 | 193.76 | 0.005 | 3,908.734 | 5,439.011 | 5,439.25 | success | 0 |
| qdrant | sweep11_r01_qdrant_s00001_mem4g |  |  | 1 | 4g | 8 | 5,000 | 1,242,391 | 1,242,391 | 368.162 | 0.173 | 0.244 | 364.39 | 0.04 | 3,432.996 | 2,514.004 | 2,446.309 | success | 0 |

## Dataset: stackoverflow-xlarge

| backend | run_label | lancedb_index_type | lancedb_num_partitions | seed | mem_limit | threads | batch_size | count | rows | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib | status | exit_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lancedb | sweep11_r01_lancedb_s00000_mem64g | IVF_HNSW_SQ | 1 | 0 | 64g | 16 | 25,000 | 25,910,526 | 25,910,526 | 2,291.63 | 0.002 | 1,410.408 | 880.098 | 0 | 22,420.344 | 52,332.492 | 52,342.359 | success | 0 |
