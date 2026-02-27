# 12 Vector Search Matrix Summary

- Generated (UTC): 2026-02-27T12:38:14Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep12
- Total runs: 8
- Backends: arcadedb, milvus, pgvector, qdrant
- Sweep samples: 8

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| cpus | 16 |
| dataset | stackoverflow-large |
| dataset_label | all |
| dim | 384 |
| docker_image | pgvector/pgvector:pg16, python:3.12-slim |
| heap | 13107m |
| k | 50 |
| mem_limit | 16g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| query_count | 1000 |
| query_limit | 1000 |
| query_order | shuffled |
| query_runs | 1 |
| rows | 5461227 |
| run_label | sweep12_r01_arcadedb_s00000, sweep12_r01_milvus_s00003, sweep12_r01_pgvector_s00001, sweep12_r01_qdrant_s00002, sweep12_r02_arcadedb_s00004, sweep12_r02_milvus_s00007, sweep12_r02_pgvector_s00005, sweep12_r02_qdrant_s00006 |
| seed | 0, 1, 2, 3, 4, 5, 6, 7 |
| server_fraction | 0.0, 0.8 |
| threads | 16 |

## Aggregated Run Metrics by Backend

### Backend: arcadedb (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 2 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| disk_usage_search.du_bytes | 2 | 12823894016 | 11.9GiB | 6144 | 12823887872 | 12823900160 |
| environment.hnsw_ef_normalization | 2 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 13488.7 | 13.2GiB | 71.6934 | 13417 | 13560.4 |
| run.total_time_s | 2 | 359.371 |  | 0.968533 | 358.403 | 360.34 |
| search.k | 2 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 2 | 1 |  | 0 | 1 | 1 |
| search.seed | 2 | 2 |  | 2 | 0 | 4 |
| telemetry.db_close_time_s | 2 | 0.0349775 |  | 0.000672744 | 0.0343047 | 0.0356502 |
| telemetry.db_open_time_s | 2 | 10.1185 |  | 0.078228 | 10.0403 | 10.1968 |
| telemetry.query_cold_time_s | 2 | 0.348647 |  | 0.000881986 | 0.347765 | 0.349529 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |
| telemetry.query_result_hash_stable | 2 | 2 | 0 | 1 |
| telemetry.query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: milvus (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 2 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| disk_usage_search.du_bytes | 2 | 39918182400 | 37.2GiB | 9.97663e+07 | 39818416128 | 40017948672 |
| environment.hnsw_ef_normalization | 2 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 10807.3 | 10.6GiB | 345.424 | 10461.8 | 11152.7 |
| run.total_time_s | 2 | 110.732 |  | 20.4291 | 90.3033 | 131.162 |
| search.k | 2 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 2 | 1 |  | 0 | 1 | 1 |
| search.seed | 2 | 5 |  | 2 | 3 | 7 |
| telemetry.db_close_time_s | 2 | 0.344657 |  | 0.0946275 | 0.25003 | 0.439285 |
| telemetry.db_open_time_s | 2 | 0.25605 |  | 0.00592272 | 0.250127 | 0.261972 |
| telemetry.query_cold_time_s | 2 | 0.0359448 |  | 0.00276575 | 0.0331791 | 0.0387106 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |
| telemetry.query_result_hash_stable | 2 | 2 | 0 | 1 |
| telemetry.query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: pgvector (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 2 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| disk_usage_search.du_bytes | 2 | 21326968832 | 19.9GiB | 8.35789e+06 | 21318610944 | 21335326720 |
| environment.hnsw_ef_normalization | 2 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 4459.42 | 4.4GiB | 10.8906 | 4448.53 | 4470.31 |
| run.total_time_s | 2 | 101.026 |  | 1.65506 | 99.3707 | 102.681 |
| search.k | 2 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 2 | 1 |  | 0 | 1 | 1 |
| search.seed | 2 | 3 |  | 2 | 1 | 5 |
| telemetry.db_close_time_s | 2 | 0.00199562 |  | 0.000304181 | 0.00169144 | 0.0022998 |
| telemetry.db_open_time_s | 2 | 0.0113241 |  | 0.000933865 | 0.0103902 | 0.012258 |
| telemetry.query_cold_time_s | 2 | 0.0998676 |  | 0.00166387 | 0.0982038 | 0.101531 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |
| telemetry.query_result_hash_stable | 2 | 2 | 0 | 1 |
| telemetry.query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: qdrant (runs=2)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 2 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 2 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 2 | 16 |  | 0 | 16 | 16 |
| dataset.dim | 2 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 2 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 2 | 5461227 |  | 0 | 5461227 | 5461227 |
| disk_usage_search.du_bytes | 2 | 9282170880 | 8.6GiB | 131072 | 9282039808 | 9282301952 |
| environment.hnsw_ef_normalization | 2 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 2 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 2 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 2 | 16 |  | 0 | 16 | 16 |
| peak_rss_mb | 2 | 9505.01 | 9.3GiB | 1.75 | 9503.26 | 9506.76 |
| run.total_time_s | 2 | 96.0324 |  | 0.0124399 | 96.0199 | 96.0448 |
| search.k | 2 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 2 | 1 |  | 0 | 1 | 1 |
| search.seed | 2 | 4 |  | 2 | 2 | 6 |
| telemetry.db_close_time_s | 2 | 0.0410083 |  | 0.00122941 | 0.0397789 | 0.0422377 |
| telemetry.db_open_time_s | 2 | 0.173597 |  | 0.00163551 | 0.171961 | 0.175232 |
| telemetry.query_cold_time_s | 2 | 0.0734162 |  | 0.000746428 | 0.0726698 | 0.0741626 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 2 | 2 | 0 | 1 |
| telemetry.query_result_hash_stable | 2 | 2 | 0 | 1 |
| telemetry.query_row_count_stable | 2 | 2 | 0 | 1 |

## Aggregated Sweep Metrics

### Backend: arcadedb | Overquery: 4.0 (samples=2)

- Effective ef_search values:
- Effective overquery values: 4

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_overquery_factor | 2 | 4 |  | 0 | 4 | 4 |
| latency_ms_mean | 2 | 348.647 |  | 0.881986 | 347.765 | 349.529 |
| latency_ms_mean_max | 2 | 348.647 |  | 0.881986 | 347.765 | 349.529 |
| latency_ms_mean_min | 2 | 348.647 |  | 0.881986 | 347.765 | 349.529 |
| latency_ms_p95 | 2 | 425.484 |  | 2.61161 | 422.872 | 428.095 |
| latency_ms_p95_max | 2 | 425.484 |  | 2.61161 | 422.872 | 428.095 |
| latency_ms_p95_min | 2 | 425.484 |  | 2.61161 | 422.872 | 428.095 |
| overquery_factor | 2 | 4 |  | 0 | 4 | 4 |
| queries | 2 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 2 | 0.348647 |  | 0.000881986 | 0.347765 | 0.349529 |
| query_runs | 2 | 1 |  | 0 | 1 | 1 |
| recall_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 2 | 0.94371 |  | 0.00085 | 0.94286 | 0.94456 |
| recall_mean_max | 2 | 0.94371 |  | 0.00085 | 0.94286 | 0.94456 |
| recall_mean_min | 2 | 0.94371 |  | 0.00085 | 0.94286 | 0.94456 |
| rss_after_mb | 2 | 13488.7 | 13.2GiB | 71.6934 | 13417 | 13560.4 |
| rss_before_mb | 2 | 8781.3 | 8.6GiB | 257.828 | 8523.48 | 9039.13 |
| rss_delta_mb | 2 | 4707.4 | 4.6GiB | 186.135 | 4521.27 | 4893.54 |
| seed | 2 | 2 |  | 2 | 0 | 4 |
| time_sec | 2 | 349.104 |  | 0.886239 | 348.218 | 349.99 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 2 | 2 | 0 | 1 |
| query_result_hash_stable | 2 | 2 | 0 | 1 |
| query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: milvus | Overquery: 4.0 (samples=2)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 2 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 2 | 35.9448 |  | 2.76575 | 33.1791 | 38.7106 |
| latency_ms_mean_max | 2 | 35.9448 |  | 2.76575 | 33.1791 | 38.7106 |
| latency_ms_mean_min | 2 | 35.9448 |  | 2.76575 | 33.1791 | 38.7106 |
| latency_ms_p95 | 2 | 67.1581 |  | 1.7267 | 65.4314 | 68.8848 |
| latency_ms_p95_max | 2 | 67.1581 |  | 1.7267 | 65.4314 | 68.8848 |
| latency_ms_p95_min | 2 | 67.1581 |  | 1.7267 | 65.4314 | 68.8848 |
| overquery_factor | 2 | 4 |  | 0 | 4 | 4 |
| queries | 2 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 2 | 0.0359448 |  | 0.00276575 | 0.0331791 | 0.0387106 |
| query_runs | 2 | 1 |  | 0 | 1 | 1 |
| recall_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 2 | 0.98032 |  | 0.0015 | 0.97882 | 0.98182 |
| recall_mean_max | 2 | 0.98032 |  | 0.0015 | 0.97882 | 0.98182 |
| recall_mean_min | 2 | 0.98032 |  | 0.0015 | 0.97882 | 0.98182 |
| rss_after_mb | 2 | 10806.7 | 10.6GiB | 345.969 | 10460.8 | 11152.7 |
| rss_before_mb | 2 | 10785.9 | 10.5GiB | 376.723 | 10409.2 | 11162.6 |
| rss_delta_mb | 2 | 20.7969 | 20.8MiB | 30.7539 | -9.95703 | 51.5508 |
| seed | 2 | 5 |  | 2 | 3 | 7 |
| time_sec | 2 | 36.4815 |  | 2.73037 | 33.7511 | 39.2119 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 2 | 2 | 0 | 1 |
| query_result_hash_stable | 2 | 2 | 0 | 1 |
| query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: pgvector | Overquery: 4.0 (samples=2)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 2 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 2 | 99.8676 |  | 1.66387 | 98.2038 | 101.531 |
| latency_ms_mean_max | 2 | 99.8676 |  | 1.66387 | 98.2038 | 101.531 |
| latency_ms_mean_min | 2 | 99.8676 |  | 1.66387 | 98.2038 | 101.531 |
| latency_ms_p95 | 2 | 215.693 |  | 2.37546 | 213.317 | 218.068 |
| latency_ms_p95_max | 2 | 215.693 |  | 2.37546 | 213.317 | 218.068 |
| latency_ms_p95_min | 2 | 215.693 |  | 2.37546 | 213.317 | 218.068 |
| overquery_factor | 2 | 4 |  | 0 | 4 | 4 |
| queries | 2 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 2 | 0.0998676 |  | 0.00166387 | 0.0982038 | 0.101531 |
| query_runs | 2 | 1 |  | 0 | 1 | 1 |
| recall_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 2 | 0.96519 |  | 0.00063 | 0.96456 | 0.96582 |
| recall_mean_max | 2 | 0.96519 |  | 0.00063 | 0.96456 | 0.96582 |
| recall_mean_min | 2 | 0.96519 |  | 0.00063 | 0.96456 | 0.96582 |
| rss_after_mb | 2 | 4457.82 | 4.4GiB | 9.28906 | 4448.53 | 4467.11 |
| rss_before_mb | 2 | 231.73 | 231.7MiB | 0.789062 | 230.941 | 232.52 |
| rss_delta_mb | 2 | 4226.09 | 4.1GiB | 10.0781 | 4216.01 | 4236.17 |
| seed | 2 | 3 |  | 2 | 1 | 5 |
| time_sec | 2 | 99.9226 |  | 1.65831 | 98.2643 | 101.581 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 2 | 2 | 0 | 1 |
| query_result_hash_stable | 2 | 2 | 0 | 1 |
| query_row_count_stable | 2 | 2 | 0 | 1 |

### Backend: qdrant | Overquery: 4.0 (samples=2)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 2 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 2 | 73.4162 |  | 0.746428 | 72.6698 | 74.1626 |
| latency_ms_mean_max | 2 | 73.4162 |  | 0.746428 | 72.6698 | 74.1626 |
| latency_ms_mean_min | 2 | 73.4162 |  | 0.746428 | 72.6698 | 74.1626 |
| latency_ms_p95 | 2 | 80.4542 |  | 1.49086 | 78.9633 | 81.945 |
| latency_ms_p95_max | 2 | 80.4542 |  | 1.49086 | 78.9633 | 81.945 |
| latency_ms_p95_min | 2 | 80.4542 |  | 1.49086 | 78.9633 | 81.945 |
| overquery_factor | 2 | 4 |  | 0 | 4 | 4 |
| queries | 2 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 2 | 0.0734162 |  | 0.000746428 | 0.0726698 | 0.0741626 |
| query_runs | 2 | 1 |  | 0 | 1 | 1 |
| recall_count | 2 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 2 | 0.98474 |  | 0.00058 | 0.98416 | 0.98532 |
| recall_mean_max | 2 | 0.98474 |  | 0.00058 | 0.98416 | 0.98532 |
| recall_mean_min | 2 | 0.98474 |  | 0.00058 | 0.98416 | 0.98532 |
| rss_after_mb | 2 | 9500.37 | 9.3GiB | 2.88672 | 9497.48 | 9503.26 |
| rss_before_mb | 2 | 9481.5 | 9.3GiB | 25.2578 | 9456.24 | 9506.76 |
| rss_delta_mb | 2 | 18.8711 | 18.9MiB | 28.1445 | -9.27344 | 47.0156 |
| seed | 2 | 4 |  | 2 | 2 | 6 |
| time_sec | 2 | 73.5412 |  | 0.739977 | 72.8012 | 74.2811 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 2 | 2 | 0 | 1 |
| query_result_hash_stable | 2 | 2 | 0 | 1 |
| query_row_count_stable | 2 | 2 | 0 | 1 |
