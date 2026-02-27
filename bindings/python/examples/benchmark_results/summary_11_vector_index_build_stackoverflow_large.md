# 11 Vector Index Build Matrix Summary

- Generated (UTC): 2026-02-27T12:38:13Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep11
- Total runs: 8
- Backends: arcadedb, milvus, pgvector, qdrant

## Parameters Used

| Parameter | Values |
|---|---|
| add_hierarchy | True |
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| batch_size | 10000 |
| beam_width | 100 |
| count | 5461227 |
| cpus | 16 |
| dataset | stackoverflow-large |
| dataset_label | all |
| dim | 384 |
| docker_image | python:3.12-slim |
| heap | 26214m |
| max_connections | 16 |
| mem_limit | 32g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| rows | 5461227 |
| run_label | sweep11_r01_arcadedb_s00000, sweep11_r01_milvus_s00003, sweep11_r01_pgvector_s00001, sweep11_r01_qdrant_s00002, sweep11_r02_arcadedb_s00004, sweep11_r02_milvus_s00007, sweep11_r02_pgvector_s00005, sweep11_r02_qdrant_s00006 |
| seed | 0, 1, 2, 3, 4, 5, 6, 7 |
| server_fraction | 0.0, 0.8 |
| store_vectors_in_graph | False |
| threads | 16 |

## Aggregated Metrics by Backend

### Backend: arcadedb (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 2 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| config.batch_size | 2 | 10000 |  | 0 | 10000 | 10000 |
| config.beam_width | 2 | 100 |  | 0 | 100 | 100 |
| config.count | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| config.max_connections | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 2 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 2 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.seed | 2 | 2 |  | 2 | 0 | 4 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| db_size_mb | 2 | 12229.8 | 11.9GiB | 0.000380039 | 12229.8 | 12229.8 |
| disk_usage.du_bytes | 2 | 12823873536 | 11.9GiB | 2048 | 12823871488 | 12823875584 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 25412.3 | 24.8GiB | 847.18 | 24565.1 | 26259.5 |
| phases.close_db.rss_after_mb | 2 | 25412.3 | 24.8GiB | 847.18 | 24565.1 | 26259.5 |
| phases.close_db.rss_before_mb | 2 | 25411 | 24.8GiB | 847.006 | 24564 | 26258 |
| phases.close_db.rss_delta_mb | 2 | 1.31055 | 1.3MiB | 0.173828 | 1.13672 | 1.48438 |
| phases.close_db.time_sec | 2 | 0.176192 |  | 0.116818 | 0.0593742 | 0.29301 |
| phases.create_db.rss_after_mb | 2 | 199.434 | 199.4MiB | 1.03516 | 198.398 | 200.469 |
| phases.create_db.rss_before_mb | 2 | 50.2617 | 50.3MiB | 0.015625 | 50.2461 | 50.2773 |
| phases.create_db.rss_delta_mb | 2 | 149.172 | 149.2MiB | 1.05078 | 148.121 | 150.223 |
| phases.create_db.time_sec | 2 | 0.411159 |  | 0.0105452 | 0.400614 | 0.421705 |
| phases.create_index.rss_after_mb | 2 | 25411 | 24.8GiB | 846.988 | 24564 | 26258 |
| phases.create_index.rss_before_mb | 2 | 12715.2 | 12.4GiB | 112.701 | 12602.5 | 12827.9 |
| phases.create_index.rss_delta_mb | 2 | 12695.8 | 12.4GiB | 959.689 | 11736.1 | 13655.5 |
| phases.create_index.time_sec | 2 | 72227.2 |  | 2147.75 | 70079.4 | 74374.9 |
| phases.ingest.ingested | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| phases.ingest.rss_after_mb | 2 | 12715.2 | 12.4GiB | 112.701 | 12602.5 | 12827.9 |
| phases.ingest.rss_before_mb | 2 | 199.434 | 199.4MiB | 1.03516 | 198.398 | 200.469 |
| phases.ingest.rss_delta_mb | 2 | 12515.8 | 12.2GiB | 113.736 | 12402.1 | 12629.5 |
| phases.ingest.time_sec | 2 | 258.256 |  | 59.6653 | 198.591 | 317.922 |
| run.total_time_s | 2 | 72486.5 |  | 2088.58 | 70397.9 | 74575 |
| telemetry.db_close_time_s | 2 | 0.176192 |  | 0.116818 | 0.0593742 | 0.29301 |
| telemetry.db_create_time_s | 2 | 0.411159 |  | 0.0105452 | 0.400614 | 0.421705 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 2 | 2 | 0 | 1 |
| config.store_vectors_in_graph | 2 | 0 | 2 | 0 |
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |

### Backend: milvus (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 2 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| config.batch_size | 2 | 10000 |  | 0 | 10000 | 10000 |
| config.beam_width | 2 | 100 |  | 0 | 100 | 100 |
| config.count | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| config.max_connections | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 2 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 2 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.seed | 2 | 5 |  | 2 | 3 | 7 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| db_size_mb | 2 | 34038.2 | 33.2GiB | 175.589 | 33862.6 | 34213.8 |
| disk_usage.du_bytes | 2 | 35769485312 | 33.3GiB | 1.81549e+08 | 35587936256 | 35951034368 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 2955.24 | 2.9GiB | 978.756 | 1976.48 | 3934 |
| phases.close_db.rss_after_mb | 2 | 2955.24 | 2.9GiB | 978.756 | 1976.48 | 3934 |
| phases.close_db.rss_before_mb | 2 | 2955.64 | 2.9GiB | 979.17 | 1976.47 | 3934.81 |
| phases.close_db.rss_delta_mb | 2 | -0.398438 | -417792.0B | 0.414062 | -0.8125 | 0.015625 |
| phases.close_db.time_sec | 2 | 0.306274 |  | 0.0112461 | 0.295028 | 0.31752 |
| phases.create_db.rss_after_mb | 2 | 527.764 | 527.8MiB | 2.56055 | 525.203 | 530.324 |
| phases.create_db.rss_before_mb | 2 | 527.383 | 527.4MiB | 2.65234 | 524.73 | 530.035 |
| phases.create_db.rss_delta_mb | 2 | 0.380859 | 390.0KiB | 0.0917969 | 0.289062 | 0.472656 |
| phases.create_db.time_sec | 2 | 0.222214 |  | 0.027657 | 0.194557 | 0.249871 |
| phases.create_index.rss_after_mb | 2 | 573.367 | 573.4MiB | 0.988281 | 572.379 | 574.355 |
| phases.create_index.rss_before_mb | 2 | 572.377 | 572.4MiB | 0.880859 | 571.496 | 573.258 |
| phases.create_index.rss_delta_mb | 2 | 0.990234 | 1014.0KiB | 0.107422 | 0.882812 | 1.09766 |
| phases.create_index.time_sec | 2 | 0.862239 |  | 0.0803098 | 0.781929 | 0.942549 |
| phases.ingest.ingested | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| phases.ingest.rss_after_mb | 2 | 2954.47 | 2.9GiB | 979.045 | 1975.43 | 3933.52 |
| phases.ingest.rss_before_mb | 2 | 573.395 | 573.4MiB | 1.01562 | 572.379 | 574.41 |
| phases.ingest.rss_delta_mb | 2 | 2381.08 | 2.3GiB | 980.061 | 1401.02 | 3361.14 |
| phases.ingest.time_sec | 2 | 585.79 |  | 76.6882 | 509.101 | 662.478 |
| run.total_time_s | 2 | 601.806 |  | 78.3704 | 523.436 | 680.177 |
| telemetry.db_close_time_s | 2 | 0.306274 |  | 0.0112461 | 0.295028 | 0.31752 |
| telemetry.db_create_time_s | 2 | 0.222214 |  | 0.027657 | 0.194557 | 0.249871 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 2 | 2 | 0 | 1 |
| config.store_vectors_in_graph | 2 | 0 | 2 | 0 |
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |

### Backend: pgvector (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 2 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| config.batch_size | 2 | 10000 |  | 0 | 10000 | 10000 |
| config.beam_width | 2 | 100 |  | 0 | 100 | 100 |
| config.count | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| config.max_connections | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 2 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 2 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.seed | 2 | 3 |  | 2 | 1 | 5 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| db_size_mb | 2 | 20346.6 | 19.9GiB | 0.00390625 | 20346.6 | 20346.6 |
| disk_usage.du_bytes | 2 | 21335300096 | 19.9GiB | 10240 | 21335289856 | 21335310336 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 25272.2 | 24.7GiB | 93.75 | 25178.5 | 25366 |
| phases.close_db.rss_after_mb | 2 | 16897.2 | 16.5GiB | 89.9805 | 16807.2 | 16987.2 |
| phases.close_db.rss_before_mb | 2 | 25272.5 | 24.7GiB | 93.541 | 25178.9 | 25366 |
| phases.close_db.rss_delta_mb | 2 | -8375.24 | -8782080000.0B | 3.56055 | -8378.8 | -8371.68 |
| phases.close_db.time_sec | 2 | 0.0297565 |  | 0.0279826 | 0.00177392 | 0.057739 |
| phases.create_db.rss_after_mb | 2 | 308.623 | 308.6MiB | 0.798828 | 307.824 | 309.422 |
| phases.create_db.rss_before_mb | 2 | 290.582 | 290.6MiB | 0.710938 | 289.871 | 291.293 |
| phases.create_db.rss_delta_mb | 2 | 18.041 | 18.0MiB | 0.0878906 | 17.9531 | 18.1289 |
| phases.create_db.time_sec | 2 | 0.00608469 |  | 0.000124215 | 0.00596048 | 0.00620891 |
| phases.create_index.rss_after_mb | 2 | 25272.2 | 24.7GiB | 93.75 | 25178.5 | 25366 |
| phases.create_index.rss_before_mb | 2 | 17707.8 | 17.3GiB | 603.453 | 17104.3 | 18311.2 |
| phases.create_index.rss_delta_mb | 2 | 7564.48 | 7.4GiB | 697.203 | 6867.28 | 8261.68 |
| phases.create_index.time_sec | 2 | 6502.99 |  | 460.44 | 6042.55 | 6963.43 |
| phases.ingest.ingested | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| phases.ingest.rss_after_mb | 2 | 17707.8 | 17.3GiB | 603.453 | 17104.3 | 18311.2 |
| phases.ingest.rss_before_mb | 2 | 330.9 | 330.9MiB | 0.833984 | 330.066 | 331.734 |
| phases.ingest.rss_delta_mb | 2 | 17376.9 | 17.0GiB | 604.287 | 16772.6 | 17981.2 |
| phases.ingest.time_sec | 2 | 574.351 |  | 37.6038 | 536.748 | 611.955 |
| run.total_time_s | 2 | 7086.9 |  | 428.517 | 6658.38 | 7515.42 |
| telemetry.db_close_time_s | 2 | 0.0297565 |  | 0.0279826 | 0.00177392 | 0.057739 |
| telemetry.db_create_time_s | 2 | 0.00608469 |  | 0.000124215 | 0.00596048 | 0.00620891 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 2 | 2 | 0 | 1 |
| config.store_vectors_in_graph | 2 | 0 | 2 | 0 |
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |

### Backend: qdrant (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 2 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| config.batch_size | 2 | 10000 |  | 0 | 10000 | 10000 |
| config.beam_width | 2 | 100 |  | 0 | 100 | 100 |
| config.count | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| config.max_connections | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 2 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 2 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 2 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 2 | 16 |  | 0 | 16 | 16 |
| config.seed | 2 | 4 |  | 2 | 2 | 6 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| db_size_mb | 2 | 10346.5 | 10.1GiB | 67.0159 | 10279.4 | 10413.5 |
| disk_usage.du_bytes | 2 | 10791866368 | 10.1GiB | 7.0656e+07 | 10721210368 | 10862522368 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 12031.4 | 11.7GiB | 31.4277 | 12000 | 12062.8 |
| phases.close_db.rss_after_mb | 2 | 12029.3 | 11.7GiB | 29.9121 | 11999.4 | 12059.3 |
| phases.close_db.rss_before_mb | 2 | 12029.3 | 11.7GiB | 29.8984 | 11999.4 | 12059.2 |
| phases.close_db.rss_delta_mb | 2 | 0.0449219 | 46.0KiB | 0.0136719 | 0.03125 | 0.0585938 |
| phases.close_db.time_sec | 2 | 0.0644648 |  | 0.0122713 | 0.0521936 | 0.0767361 |
| phases.create_db.rss_after_mb | 2 | 195.498 | 195.5MiB | 0.181641 | 195.316 | 195.68 |
| phases.create_db.rss_before_mb | 2 | 191.619 | 191.6MiB | 0.181641 | 191.438 | 191.801 |
| phases.create_db.rss_delta_mb | 2 | 3.87891 | 3.9MiB | 0 | 3.87891 | 3.87891 |
| phases.create_db.time_sec | 2 | 0.165585 |  | 0.00809061 | 0.157494 | 0.173675 |
| phases.create_index.rss_after_mb | 2 | 210.605 | 210.6MiB | 0.0546875 | 210.551 | 210.66 |
| phases.create_index.rss_before_mb | 2 | 195.51 | 195.5MiB | 0.181641 | 195.328 | 195.691 |
| phases.create_index.rss_delta_mb | 2 | 15.0957 | 15.1MiB | 0.236328 | 14.8594 | 15.332 |
| phases.create_index.time_sec | 2 | 0.890484 |  | 0.389745 | 0.500739 | 1.28023 |
| phases.ingest.ingested | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| phases.ingest.rss_after_mb | 2 | 12031.4 | 11.7GiB | 31.4277 | 12000 | 12062.8 |
| phases.ingest.rss_before_mb | 2 | 210.605 | 210.6MiB | 0.0546875 | 210.551 | 210.66 |
| phases.ingest.rss_delta_mb | 2 | 11820.8 | 11.5GiB | 31.4824 | 11789.3 | 11852.3 |
| phases.ingest.time_sec | 2 | 1773.23 |  | 338.865 | 1434.37 | 2112.09 |
| run.total_time_s | 2 | 1778.56 |  | 339.861 | 1438.69 | 2118.42 |
| telemetry.db_close_time_s | 2 | 0.0644648 |  | 0.0122713 | 0.0521936 | 0.0767361 |
| telemetry.db_create_time_s | 2 | 0.165585 |  | 0.00809061 | 0.157494 | 0.173675 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 2 | 2 | 0 | 1 |
| config.store_vectors_in_graph | 2 | 0 | 2 | 0 |
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |
