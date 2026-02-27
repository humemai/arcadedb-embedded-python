# 11 Vector Index Build Matrix Summary

- Generated (UTC): 2026-02-27T12:38:13Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep11
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant

## Parameters Used

| Parameter | Values |
|---|---|
| add_hierarchy | True |
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| batch_size | 1000 |
| beam_width | 100 |
| count | 19591 |
| cpus | 2 |
| dataset | stackoverflow-tiny |
| dataset_label | all |
| dim | 384 |
| docker_image | python:3.12-slim |
| heap | 1638m |
| max_connections | 16 |
| mem_limit | 2g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| rows | 19591 |
| run_label | sweep11_r01_arcadedb_s00000, sweep11_r01_milvus_s00003, sweep11_r01_pgvector_s00001, sweep11_r01_qdrant_s00002, sweep11_r02_arcadedb_s00004, sweep11_r02_milvus_s00007, sweep11_r02_pgvector_s00005, sweep11_r02_qdrant_s00006, sweep11_r03_arcadedb_s00008, sweep11_r03_milvus_s00011, sweep11_r03_pgvector_s00009, sweep11_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| store_vectors_in_graph | False |
| threads | 2 |

## Aggregated Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| config.batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 19591 |  | 0 | 19591 | 19591 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| db_size_mb | 3 | 44.3161 | 44.3MiB | 0 | 44.3161 | 44.3161 |
| disk_usage.du_bytes | 3 | 4.65196e+07 | 44.4MiB | 1930.87 | 46518272 | 46522368 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 469.941 | 469.9MiB | 70.3866 | 406.156 | 568.016 |
| phases.close_db.rss_after_mb | 3 | 469.931 | 469.9MiB | 70.3961 | 406.125 | 568.016 |
| phases.close_db.rss_before_mb | 3 | 469.935 | 469.9MiB | 70.38 | 406.156 | 568 |
| phases.close_db.rss_delta_mb | 3 | -0.00390625 | -4096.0B | 0.019918 | -0.03125 | 0.015625 |
| phases.close_db.time_sec | 3 | 0.0518806 |  | 0.0216186 | 0.0213743 | 0.0688844 |
| phases.create_db.rss_after_mb | 3 | 143.146 | 143.1MiB | 0.536152 | 142.391 | 143.582 |
| phases.create_db.rss_before_mb | 3 | 50.5221 | 50.5MiB | 0.0602908 | 50.4648 | 50.6055 |
| phases.create_db.rss_delta_mb | 3 | 92.6237 | 92.6MiB | 0.526232 | 91.8945 | 93.1172 |
| phases.create_db.time_sec | 3 | 0.423825 |  | 0.0133656 | 0.410021 | 0.44191 |
| phases.create_index.rss_after_mb | 3 | 469.935 | 469.9MiB | 70.38 | 406.156 | 568 |
| phases.create_index.rss_before_mb | 3 | 245.555 | 245.6MiB | 11.5721 | 232.246 | 260.457 |
| phases.create_index.rss_delta_mb | 3 | 224.38 | 224.4MiB | 59.2511 | 173.91 | 307.543 |
| phases.create_index.time_sec | 3 | 7.10869 |  | 0.262377 | 6.74505 | 7.35443 |
| phases.ingest.ingested | 3 | 19591 |  | 0 | 19591 | 19591 |
| phases.ingest.rss_after_mb | 3 | 245.555 | 245.6MiB | 11.5721 | 232.246 | 260.457 |
| phases.ingest.rss_before_mb | 3 | 143.146 | 143.1MiB | 0.536152 | 142.391 | 143.582 |
| phases.ingest.rss_delta_mb | 3 | 102.409 | 102.4MiB | 11.4845 | 88.7812 | 116.875 |
| phases.ingest.time_sec | 3 | 0.913188 |  | 0.0387455 | 0.860404 | 0.952315 |
| run.total_time_s | 3 | 8.53503 |  | 0.245474 | 8.18856 | 8.72708 |
| telemetry.db_close_time_s | 3 | 0.0518806 |  | 0.0216186 | 0.0213743 | 0.0688844 |
| telemetry.db_create_time_s | 3 | 0.423825 |  | 0.0133656 | 0.410021 | 0.44191 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| config.batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 19591 |  | 0 | 19591 | 19591 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| db_size_mb | 3 | 160.208 | 160.2MiB | 0.000348406 | 160.208 | 160.208 |
| disk_usage.du_bytes | 3 | 242413568 | 231.2MiB | 675306 | 241459200 | 242921472 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 853.69 | 853.7MiB | 9.84232 | 839.848 | 861.875 |
| phases.close_db.rss_after_mb | 3 | 853.69 | 853.7MiB | 9.84232 | 839.848 | 861.875 |
| phases.close_db.rss_before_mb | 3 | 853.622 | 853.6MiB | 9.93755 | 839.645 | 861.875 |
| phases.close_db.rss_delta_mb | 3 | 0.0677083 | 69.3KiB | 0.095754 | 0 | 0.203125 |
| phases.close_db.time_sec | 3 | 0.437064 |  | 0.0329643 | 0.390794 | 0.465123 |
| phases.create_db.rss_after_mb | 3 | 524.303 | 524.3MiB | 3.18271 | 520.105 | 527.809 |
| phases.create_db.rss_before_mb | 3 | 523.901 | 523.9MiB | 3.19563 | 519.691 | 527.43 |
| phases.create_db.rss_delta_mb | 3 | 0.402344 | 412.0KiB | 0.0165728 | 0.378906 | 0.414062 |
| phases.create_db.time_sec | 3 | 0.459576 |  | 0.0182806 | 0.43704 | 0.481815 |
| phases.create_index.rss_after_mb | 3 | 568.719 | 568.7MiB | 1.85211 | 566.859 | 571.246 |
| phases.create_index.rss_before_mb | 3 | 568.271 | 568.3MiB | 1.70122 | 566.664 | 570.625 |
| phases.create_index.rss_delta_mb | 3 | 0.447917 | 458.7KiB | 0.182673 | 0.195312 | 0.621094 |
| phases.create_index.time_sec | 3 | 1.22564 |  | 0.152327 | 1.10765 | 1.44072 |
| phases.ingest.ingested | 3 | 19591 |  | 0 | 19591 | 19591 |
| phases.ingest.rss_after_mb | 3 | 853.118 | 853.1MiB | 10.441 | 838.438 | 861.828 |
| phases.ingest.rss_before_mb | 3 | 568.724 | 568.7MiB | 1.85024 | 566.859 | 571.246 |
| phases.ingest.rss_delta_mb | 3 | 284.395 | 284.4MiB | 10.3339 | 270.371 | 294.969 |
| phases.ingest.time_sec | 3 | 6.37053 |  | 0.040401 | 6.31571 | 6.41188 |
| run.total_time_s | 3 | 23.9101 |  | 0.593041 | 23.0715 | 24.3356 |
| telemetry.db_close_time_s | 3 | 0.437064 |  | 0.0329643 | 0.390794 | 0.465123 |
| telemetry.db_create_time_s | 3 | 0.459576 |  | 0.0182806 | 0.43704 | 0.481815 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| config.batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 19591 |  | 0 | 19591 | 19591 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| db_size_mb | 3 | 179.165 | 179.2MiB | 0 | 179.165 | 179.165 |
| disk_usage.du_bytes | 3 | 187957248 | 179.2MiB | 17696.7 | 187932672 | 187973632 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 282.492 | 282.5MiB | 0.0977343 | 282.406 | 282.629 |
| phases.close_db.rss_after_mb | 3 | 165.158 | 165.2MiB | 0.0267482 | 165.137 | 165.195 |
| phases.close_db.rss_before_mb | 3 | 282.492 | 282.5MiB | 0.0977343 | 282.406 | 282.629 |
| phases.close_db.rss_delta_mb | 3 | -117.335 | -123034282.7B | 0.0717683 | -117.434 | -117.266 |
| phases.close_db.time_sec | 3 | 0.00185486 |  | 0.0001847 | 0.00169591 | 0.00211384 |
| phases.create_db.rss_after_mb | 3 | 155.363 | 155.4MiB | 0.124388 | 155.188 | 155.457 |
| phases.create_db.rss_before_mb | 3 | 140.299 | 140.3MiB | 0.041626 | 140.246 | 140.348 |
| phases.create_db.rss_delta_mb | 3 | 15.0638 | 15.1MiB | 0.0874822 | 14.9414 | 15.1406 |
| phases.create_db.time_sec | 3 | 0.00631172 |  | 0.000430293 | 0.00595367 | 0.00691686 |
| phases.create_index.rss_after_mb | 3 | 282.492 | 282.5MiB | 0.0977343 | 282.406 | 282.629 |
| phases.create_index.rss_before_mb | 3 | 240.428 | 240.4MiB | 0.0186884 | 240.402 | 240.445 |
| phases.create_index.rss_delta_mb | 3 | 42.0638 | 42.1MiB | 0.0847055 | 42.0039 | 42.1836 |
| phases.create_index.time_sec | 3 | 3.36458 |  | 0.811572 | 2.72642 | 4.50982 |
| phases.ingest.ingested | 3 | 19591 |  | 0 | 19591 | 19591 |
| phases.ingest.rss_after_mb | 3 | 240.424 | 240.4MiB | 0.0186884 | 240.398 | 240.441 |
| phases.ingest.rss_before_mb | 3 | 169.182 | 169.2MiB | 0.0831908 | 169.066 | 169.258 |
| phases.ingest.rss_delta_mb | 3 | 71.2422 | 71.2MiB | 0.0884459 | 71.1758 | 71.3672 |
| phases.ingest.time_sec | 3 | 1.6502 |  | 0.0112141 | 1.63907 | 1.66555 |
| run.total_time_s | 3 | 8.82767 |  | 0.741106 | 8.2304 | 9.87216 |
| telemetry.db_close_time_s | 3 | 0.00185486 |  | 0.0001847 | 0.00169591 | 0.00211384 |
| telemetry.db_create_time_s | 3 | 0.00631172 |  | 0.000430293 | 0.00595367 | 0.00691686 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| config.batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 19591 |  | 0 | 19591 | 19591 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| db_size_mb | 3 | 126.706 | 126.7MiB | 0.818249 | 126.127 | 127.863 |
| disk_usage.du_bytes | 3 | 74178560 | 70.7MiB | 2.96003e+06 | 69992448 | 76271616 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 336.655 | 336.7MiB | 12.5421 | 322.363 | 352.898 |
| phases.close_db.rss_after_mb | 3 | 336.655 | 336.7MiB | 12.5421 | 322.363 | 352.898 |
| phases.close_db.rss_before_mb | 3 | 336.655 | 336.7MiB | 12.5421 | 322.363 | 352.898 |
| phases.close_db.rss_delta_mb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| phases.close_db.time_sec | 3 | 0.056663 |  | 0.0253295 | 0.0377467 | 0.0924652 |
| phases.create_db.rss_after_mb | 3 | 150.991 | 151.0MiB | 0.0512631 | 150.945 | 151.062 |
| phases.create_db.rss_before_mb | 3 | 147.095 | 147.1MiB | 0.0602064 | 147.031 | 147.176 |
| phases.create_db.rss_delta_mb | 3 | 3.89583 | 3.9MiB | 0.01289 | 3.88672 | 3.91406 |
| phases.create_db.time_sec | 3 | 0.322379 |  | 0.0135269 | 0.303523 | 0.3346 |
| phases.create_index.rss_after_mb | 3 | 158.901 | 158.9MiB | 0.170697 | 158.695 | 159.113 |
| phases.create_index.rss_before_mb | 3 | 150.995 | 151.0MiB | 0.0479831 | 150.957 | 151.062 |
| phases.create_index.rss_delta_mb | 3 | 7.90625 | 7.9MiB | 0.12865 | 7.73828 | 8.05078 |
| phases.create_index.time_sec | 3 | 0.599108 |  | 0.0168921 | 0.58326 | 0.622512 |
| phases.ingest.ingested | 3 | 19591 |  | 0 | 19591 | 19591 |
| phases.ingest.rss_after_mb | 3 | 336.539 | 336.5MiB | 12.5506 | 322.301 | 352.836 |
| phases.ingest.rss_before_mb | 3 | 158.905 | 158.9MiB | 0.170697 | 158.699 | 159.117 |
| phases.ingest.rss_delta_mb | 3 | 177.634 | 177.6MiB | 12.6496 | 163.402 | 194.137 |
| phases.ingest.time_sec | 3 | 7.15311 |  | 0.0705071 | 7.05342 | 7.20443 |
| run.total_time_s | 3 | 12.8196 |  | 0.236831 | 12.4862 | 13.0145 |
| telemetry.db_close_time_s | 3 | 0.056663 |  | 0.0253295 | 0.0377467 | 0.0924652 |
| telemetry.db_create_time_s | 3 | 0.322379 |  | 0.0135269 | 0.303523 | 0.3346 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
