# 11 Vector Index Build Matrix Summary

- Generated (UTC): 2026-02-27T12:38:13Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep11
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant

## Parameters Used

| Parameter | Values |
|---|---|
| add_hierarchy | True |
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| batch_size | 2500 |
| beam_width | 100 |
| count | 300424 |
| cpus | 4 |
| dataset | stackoverflow-small |
| dataset_label | all |
| dim | 384 |
| docker_image | python:3.12-slim |
| heap | 3276m |
| max_connections | 16 |
| mem_limit | 4g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| rows | 300424 |
| run_label | sweep11_r01_arcadedb_s00000, sweep11_r01_milvus_s00003, sweep11_r01_pgvector_s00001, sweep11_r01_qdrant_s00002, sweep11_r02_arcadedb_s00004, sweep11_r02_milvus_s00007, sweep11_r02_pgvector_s00005, sweep11_r02_qdrant_s00006, sweep11_r03_arcadedb_s00008, sweep11_r03_milvus_s00011, sweep11_r03_pgvector_s00009, sweep11_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| store_vectors_in_graph | False |
| threads | 4 |

## Aggregated Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| config.batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 300424 |  | 0 | 300424 | 300424 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| db_size_mb | 3 | 672.816 | 672.8MiB | 0 | 672.816 | 672.816 |
| disk_usage.du_bytes | 3 | 705552384 | 672.9MiB | 0 | 705552384 | 705552384 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 3184.28 | 3.1GiB | 106.839 | 3107.29 | 3335.37 |
| phases.close_db.rss_after_mb | 3 | 3184.25 | 3.1GiB | 106.794 | 3107.29 | 3335.27 |
| phases.close_db.rss_before_mb | 3 | 3184.19 | 3.1GiB | 106.907 | 3107.07 | 3335.37 |
| phases.close_db.rss_delta_mb | 3 | 0.0651042 | 66.7KiB | 0.13078 | -0.09375 | 0.226562 |
| phases.close_db.time_sec | 3 | 0.0198324 |  | 0.00177756 | 0.0180662 | 0.0222647 |
| phases.create_db.rss_after_mb | 3 | 170.526 | 170.5MiB | 2.70919 | 168.07 | 174.301 |
| phases.create_db.rss_before_mb | 3 | 50.5664 | 50.6MiB | 0.0796722 | 50.457 | 50.6445 |
| phases.create_db.rss_delta_mb | 3 | 119.96 | 120.0MiB | 2.70169 | 117.426 | 123.703 |
| phases.create_db.time_sec | 3 | 0.433412 |  | 0.0380109 | 0.379937 | 0.464901 |
| phases.create_index.rss_after_mb | 3 | 3184.18 | 3.1GiB | 106.913 | 3107.04 | 3335.37 |
| phases.create_index.rss_before_mb | 3 | 1327.32 | 1.3GiB | 34.5112 | 1278.57 | 1353.68 |
| phases.create_index.rss_delta_mb | 3 | 1856.86 | 1.8GiB | 93.3264 | 1757.32 | 1981.69 |
| phases.create_index.time_sec | 3 | 398.982 |  | 3.3978 | 396.068 | 403.748 |
| phases.ingest.ingested | 3 | 300424 |  | 0 | 300424 | 300424 |
| phases.ingest.rss_after_mb | 3 | 1327.32 | 1.3GiB | 34.5112 | 1278.57 | 1353.68 |
| phases.ingest.rss_before_mb | 3 | 170.526 | 170.5MiB | 2.70919 | 168.07 | 174.301 |
| phases.ingest.rss_delta_mb | 3 | 1156.8 | 1.1GiB | 33.7977 | 1109.36 | 1185.61 |
| phases.ingest.time_sec | 3 | 9.63085 |  | 0.432255 | 9.23963 | 10.2332 |
| run.total_time_s | 3 | 409.101 |  | 3.8507 | 405.744 | 414.493 |
| telemetry.db_close_time_s | 3 | 0.0198324 |  | 0.00177756 | 0.0180662 | 0.0222647 |
| telemetry.db_create_time_s | 3 | 0.433412 |  | 0.0380109 | 0.379937 | 0.464901 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |

### Backend: milvus (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 3 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| config.batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 300424 |  | 0 | 300424 | 300424 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| db_size_mb | 3 | 2232.47 | 2.2GiB | 58.8797 | 2149.23 | 2275.72 |
| disk_usage.du_bytes | 3 | 2.84644e+09 | 2.7GiB | 1.88555e+08 | 2622930944 | 3084140544 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 1636.85 | 1.6GiB | 84.3493 | 1546.96 | 1749.71 |
| phases.close_db.rss_after_mb | 3 | 1536.15 | 1.5GiB | 68.3067 | 1447.62 | 1613.88 |
| phases.close_db.rss_before_mb | 3 | 1456.79 | 1.4GiB | 74.9368 | 1372.32 | 1554.45 |
| phases.close_db.rss_delta_mb | 3 | 79.3633 | 79.4MiB | 18.1668 | 59.4297 | 103.367 |
| phases.close_db.time_sec | 3 | 0.288023 |  | 0.0083677 | 0.277075 | 0.297387 |
| phases.create_db.rss_after_mb | 3 | 527.495 | 527.5MiB | 0.843016 | 526.309 | 528.191 |
| phases.create_db.rss_before_mb | 3 | 526.96 | 527.0MiB | 0.831963 | 525.828 | 527.805 |
| phases.create_db.rss_delta_mb | 3 | 0.535156 | 548.0KiB | 0.148643 | 0.386719 | 0.738281 |
| phases.create_db.time_sec | 3 | 0.296868 |  | 0.041154 | 0.260032 | 0.354309 |
| phases.create_index.rss_after_mb | 3 | 569.016 | 569.0MiB | 2.98158 | 564.922 | 571.938 |
| phases.create_index.rss_before_mb | 3 | 568.29 | 568.3MiB | 2.95471 | 564.246 | 571.223 |
| phases.create_index.rss_delta_mb | 3 | 0.72526 | 742.7KiB | 0.0452556 | 0.675781 | 0.785156 |
| phases.create_index.time_sec | 3 | 1.01925 |  | 0.0795749 | 0.945818 | 1.12982 |
| phases.ingest.ingested | 3 | 300424 |  | 0 | 300424 | 300424 |
| phases.ingest.rss_after_mb | 3 | 1512.54 | 1.5GiB | 176.873 | 1325.11 | 1749.71 |
| phases.ingest.rss_before_mb | 3 | 569.283 | 569.3MiB | 3.09756 | 564.938 | 571.938 |
| phases.ingest.rss_delta_mb | 3 | 943.262 | 943.3MiB | 176.675 | 753.176 | 1178.74 |
| phases.ingest.time_sec | 3 | 79.6697 |  | 0.84768 | 78.4839 | 80.4151 |
| run.total_time_s | 3 | 95.7516 |  | 0.393438 | 95.2014 | 96.0982 |
| telemetry.db_close_time_s | 3 | 0.288023 |  | 0.0083677 | 0.277075 | 0.297387 |
| telemetry.db_create_time_s | 3 | 0.296868 |  | 0.041154 | 0.260032 | 0.354309 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |

### Backend: pgvector (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| config.batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 300424 |  | 0 | 300424 | 300424 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| db_size_mb | 3 | 2112.2 | 2.1GiB | 0.0168769 | 2112.18 | 2112.22 |
| disk_usage.du_bytes | 3 | 2.21505e+09 | 2.1GiB | 31609.8 | 2215022592 | 2215096320 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 2050.64 | 2.0GiB | 177.974 | 1886.32 | 2297.91 |
| phases.close_db.rss_after_mb | 3 | 973.25 | 973.2MiB | 177.048 | 811.199 | 1219.57 |
| phases.close_db.rss_before_mb | 3 | 2051.27 | 2.0GiB | 177.401 | 1888.2 | 2297.92 |
| phases.close_db.rss_delta_mb | 3 | -1078.02 | -1130384042.7B | 0.735436 | -1078.71 | -1077 |
| phases.close_db.time_sec | 3 | 0.00231886 |  | 0.000226296 | 0.00203236 | 0.00258561 |
| phases.create_db.rss_after_mb | 3 | 166.074 | 166.1MiB | 0.461346 | 165.426 | 166.461 |
| phases.create_db.rss_before_mb | 3 | 150.111 | 150.1MiB | 0.342465 | 149.629 | 150.395 |
| phases.create_db.rss_delta_mb | 3 | 15.9635 | 16.0MiB | 0.118925 | 15.7969 | 16.0664 |
| phases.create_db.time_sec | 3 | 0.00633961 |  | 0.000282051 | 0.00603685 | 0.00671589 |
| phases.create_index.rss_after_mb | 3 | 2050.64 | 2.0GiB | 177.974 | 1886.32 | 2297.91 |
| phases.create_index.rss_before_mb | 3 | 719.66 | 719.7MiB | 0.877113 | 718.59 | 720.738 |
| phases.create_index.rss_delta_mb | 3 | 1330.98 | 1.3GiB | 178.635 | 1166.66 | 1579.32 |
| phases.create_index.time_sec | 3 | 181.12 |  | 7.63153 | 170.333 | 186.813 |
| phases.ingest.ingested | 3 | 300424 |  | 0 | 300424 | 300424 |
| phases.ingest.rss_after_mb | 3 | 719.66 | 719.7MiB | 0.877113 | 718.59 | 720.738 |
| phases.ingest.rss_before_mb | 3 | 180.051 | 180.1MiB | 0.497563 | 179.352 | 180.469 |
| phases.ingest.rss_delta_mb | 3 | 539.609 | 539.6MiB | 0.563918 | 539.184 | 540.406 |
| phases.ingest.time_sec | 3 | 24.7093 |  | 0.233456 | 24.4123 | 24.9827 |
| run.total_time_s | 3 | 210.714 |  | 8.39621 | 198.965 | 218.08 |
| telemetry.db_close_time_s | 3 | 0.00231886 |  | 0.000226296 | 0.00203236 | 0.00258561 |
| telemetry.db_create_time_s | 3 | 0.00633961 |  | 0.000282051 | 0.00603685 | 0.00671589 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |

### Backend: qdrant (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 3 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| config.batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 300424 |  | 0 | 300424 | 300424 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| db_size_mb | 3 | 766.713 | 766.7MiB | 30.2546 | 728.968 | 803.035 |
| disk_usage.du_bytes | 3 | 579735552 | 552.9MiB | 2.76309e+06 | 577445888 | 583622656 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 1271.46 | 1.2GiB | 33.3129 | 1228.57 | 1309.79 |
| phases.close_db.rss_after_mb | 3 | 1271.46 | 1.2GiB | 33.3129 | 1228.57 | 1309.79 |
| phases.close_db.rss_before_mb | 3 | 1271.45 | 1.2GiB | 33.3142 | 1228.56 | 1309.78 |
| phases.close_db.rss_delta_mb | 3 | 0.0117188 | 12.0KiB | 0.00318944 | 0.0078125 | 0.015625 |
| phases.close_db.time_sec | 3 | 0.0494588 |  | 0.00626862 | 0.0409968 | 0.0559788 |
| phases.create_db.rss_after_mb | 3 | 158.954 | 159.0MiB | 0.935166 | 157.637 | 159.711 |
| phases.create_db.rss_before_mb | 3 | 155.385 | 155.4MiB | 0.477579 | 154.719 | 155.812 |
| phases.create_db.rss_delta_mb | 3 | 3.56901 | 3.6MiB | 0.460367 | 2.91797 | 3.89844 |
| phases.create_db.time_sec | 3 | 0.198835 |  | 0.0278516 | 0.176856 | 0.238131 |
| phases.create_index.rss_after_mb | 3 | 169.012 | 169.0MiB | 0.643911 | 168.102 | 169.492 |
| phases.create_index.rss_before_mb | 3 | 158.957 | 159.0MiB | 0.931497 | 157.645 | 159.711 |
| phases.create_index.rss_delta_mb | 3 | 10.0547 | 10.1MiB | 0.290554 | 9.78125 | 10.457 |
| phases.create_index.time_sec | 3 | 0.583472 |  | 0.00827582 | 0.5718 | 0.590054 |
| phases.ingest.ingested | 3 | 300424 |  | 0 | 300424 | 300424 |
| phases.ingest.rss_after_mb | 3 | 1271.16 | 1.2GiB | 33.1996 | 1228.38 | 1309.3 |
| phases.ingest.rss_before_mb | 3 | 169.016 | 169.0MiB | 0.643911 | 168.105 | 169.496 |
| phases.ingest.rss_delta_mb | 3 | 1102.14 | 1.1GiB | 33.7127 | 1058.93 | 1141.2 |
| phases.ingest.time_sec | 3 | 77.4789 |  | 0.890006 | 76.7713 | 78.7342 |
| run.total_time_s | 3 | 81.3381 |  | 0.887211 | 80.4416 | 82.5466 |
| telemetry.db_close_time_s | 3 | 0.0494588 |  | 0.00626862 | 0.0409968 | 0.0559788 |
| telemetry.db_create_time_s | 3 | 0.198835 |  | 0.0278516 | 0.176856 | 0.238131 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
