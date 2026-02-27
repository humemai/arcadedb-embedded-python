# 12 Vector Search Matrix Summary

- Generated (UTC): 2026-02-27T12:38:14Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep12
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant
- Sweep samples: 12

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| cpus | 8 |
| dataset | stackoverflow-medium |
| dataset_label | all |
| dim | 384 |
| docker_image | pgvector/pgvector:pg16, python:3.12-slim |
| heap | 6553m |
| k | 50 |
| mem_limit | 8g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| query_count | 1000 |
| query_limit | 1000 |
| query_order | shuffled |
| query_runs | 1 |
| rows | 1242391 |
| run_label | sweep12_r01_arcadedb_s00000, sweep12_r01_milvus_s00003, sweep12_r01_pgvector_s00001, sweep12_r01_qdrant_s00002, sweep12_r02_arcadedb_s00004, sweep12_r02_milvus_s00007, sweep12_r02_pgvector_s00005, sweep12_r02_qdrant_s00006, sweep12_r03_arcadedb_s00008, sweep12_r03_milvus_s00011, sweep12_r03_pgvector_s00009, sweep12_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| threads | 8 |

## Aggregated Run Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| disk_usage_search.du_bytes | 3 | 2.91606e+09 | 2.7GiB | 29975.2 | 2916020224 | 2916085760 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 6679.09 | 6.5GiB | 165.665 | 6457.39 | 6855.56 |
| run.total_time_s | 3 | 104.025 |  | 46.7263 | 41.6607 | 154.129 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| telemetry.db_close_time_s | 3 | 0.0579923 |  | 0.0388019 | 0.0185697 | 0.110761 |
| telemetry.db_open_time_s | 3 | 3.24746 |  | 0.787206 | 2.68621 | 4.36073 |
| telemetry.query_cold_time_s | 3 | 0.100101 |  | 0.0473993 | 0.0367565 | 0.150764 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
| telemetry.query_result_hash_stable | 3 | 3 | 0 | 1 |
| telemetry.query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: milvus (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 3 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| disk_usage_search.du_bytes | 3 | 5.88305e+09 | 5.5GiB | 1.69786e+08 | 5653331968 | 6058430464 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 4345.74 | 4.2GiB | 110.285 | 4189.88 | 4428.8 |
| run.total_time_s | 3 | 57.5518 |  | 4.78674 | 52.9609 | 64.1556 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| telemetry.db_close_time_s | 3 | 0.432192 |  | 0.0524827 | 0.364416 | 0.492281 |
| telemetry.db_open_time_s | 3 | 0.247633 |  | 0.0156546 | 0.228937 | 0.26725 |
| telemetry.query_cold_time_s | 3 | 0.0180666 |  | 0.00185349 | 0.0154647 | 0.0196426 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
| telemetry.query_result_hash_stable | 3 | 3 | 0 | 1 |
| telemetry.query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: pgvector (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| disk_usage_search.du_bytes | 3 | 5697105920 | 5.3GiB | 7.86652e+06 | 5685981184 | 5702725632 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 2312.19 | 2.3GiB | 7.87127 | 2301.05 | 2317.8 |
| run.total_time_s | 3 | 23.3962 |  | 12.859 | 5.21095 | 32.5538 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| telemetry.db_close_time_s | 3 | 0.00182044 |  | 9.85176e-05 | 0.00172007 | 0.00195431 |
| telemetry.db_open_time_s | 3 | 0.0103263 |  | 0.000662489 | 0.00954205 | 0.0111623 |
| telemetry.query_cold_time_s | 3 | 0.0226725 |  | 0.0128591 | 0.00448709 | 0.0318308 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
| telemetry.query_result_hash_stable | 3 | 3 | 0 | 1 |
| telemetry.query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: qdrant (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 0.2 |  | 0 | 0.2 | 0.2 |
| budget.split.server_fraction | 3 | 0.8 |  | 0 | 0.8 | 0.8 |
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| disk_usage_search.du_bytes | 3 | 2.1442e+09 | 2.0GiB | 1.79116e+06 | 2142027776 | 2146414592 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 2535.11 | 2.5GiB | 7.18361 | 2525.1 | 2541.62 |
| run.total_time_s | 3 | 60.8915 |  | 0.881879 | 59.6987 | 61.8034 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| telemetry.db_close_time_s | 3 | 0.0426923 |  | 0.0023161 | 0.0397212 | 0.0453719 |
| telemetry.db_open_time_s | 3 | 0.179121 |  | 0.00927743 | 0.170083 | 0.191876 |
| telemetry.query_cold_time_s | 3 | 0.0516428 |  | 0.000789854 | 0.0505662 | 0.052439 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
| telemetry.query_result_hash_stable | 3 | 3 | 0 | 1 |
| telemetry.query_row_count_stable | 3 | 3 | 0 | 1 |

## Aggregated Sweep Metrics

### Backend: arcadedb | Overquery: 4.0 (samples=3)

- Effective ef_search values:
- Effective overquery values: 4

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| latency_ms_mean | 3 | 100.101 |  | 47.3993 | 36.7565 | 150.764 |
| latency_ms_mean_max | 3 | 100.101 |  | 47.3993 | 36.7565 | 150.764 |
| latency_ms_mean_min | 3 | 100.101 |  | 47.3993 | 36.7565 | 150.764 |
| latency_ms_p95 | 3 | 207.655 |  | 87.6632 | 85.5152 | 287.128 |
| latency_ms_p95_max | 3 | 207.655 |  | 87.6632 | 85.5152 | 287.128 |
| latency_ms_p95_min | 3 | 207.655 |  | 87.6632 | 85.5152 | 287.128 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.100101 |  | 0.0473993 | 0.0367565 | 0.150764 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.950213 |  | 0.000877319 | 0.9492 | 0.95134 |
| recall_mean_max | 3 | 0.950213 |  | 0.000877319 | 0.9492 | 0.95134 |
| recall_mean_min | 3 | 0.950213 |  | 0.000877319 | 0.9492 | 0.95134 |
| rss_after_mb | 3 | 6676.07 | 6.5GiB | 167.736 | 6452.01 | 6855.56 |
| rss_before_mb | 3 | 3422.45 | 3.3GiB | 291.856 | 3020.05 | 3703.2 |
| rss_delta_mb | 3 | 3253.62 | 3.2GiB | 446.978 | 2748.81 | 3835.51 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| time_sec | 3 | 100.609 |  | 47.4568 | 37.1674 | 151.293 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: milvus | Overquery: 4.0 (samples=3)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 3 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 3 | 18.0666 |  | 1.85349 | 15.4647 | 19.6426 |
| latency_ms_mean_max | 3 | 18.0666 |  | 1.85349 | 15.4647 | 19.6426 |
| latency_ms_mean_min | 3 | 18.0666 |  | 1.85349 | 15.4647 | 19.6426 |
| latency_ms_p95 | 3 | 32.1581 |  | 0.374819 | 31.778 | 32.6681 |
| latency_ms_p95_max | 3 | 32.1581 |  | 0.374819 | 31.778 | 32.6681 |
| latency_ms_p95_min | 3 | 32.1581 |  | 0.374819 | 31.778 | 32.6681 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0180666 |  | 0.00185349 | 0.0154647 | 0.0196426 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.972413 |  | 0.000488899 | 0.972 | 0.9731 |
| recall_mean_max | 3 | 0.972413 |  | 0.000488899 | 0.972 | 0.9731 |
| recall_mean_min | 3 | 0.972413 |  | 0.000488899 | 0.972 | 0.9731 |
| rss_after_mb | 3 | 4345.57 | 4.2GiB | 110.25 | 4189.77 | 4428.62 |
| rss_before_mb | 3 | 4451.67 | 4.3GiB | 118.245 | 4316.78 | 4604.71 |
| rss_delta_mb | 3 | -106.104 | -106.1MiB | 75.5518 | -186.391 | -4.90625 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| time_sec | 3 | 18.527 |  | 1.85855 | 15.9149 | 20.0863 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: pgvector | Overquery: 4.0 (samples=3)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 3 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 3 | 22.6725 |  | 12.8591 | 4.48709 | 31.8308 |
| latency_ms_mean_max | 3 | 22.6725 |  | 12.8591 | 4.48709 | 31.8308 |
| latency_ms_mean_min | 3 | 22.6725 |  | 12.8591 | 4.48709 | 31.8308 |
| latency_ms_p95 | 3 | 103.323 |  | 65.895 | 10.2935 | 154.571 |
| latency_ms_p95_max | 3 | 103.323 |  | 65.895 | 10.2935 | 154.571 |
| latency_ms_p95_min | 3 | 103.323 |  | 65.895 | 10.2935 | 154.571 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0226725 |  | 0.0128591 | 0.00448709 | 0.0318308 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.967493 |  | 0.000450284 | 0.96692 | 0.96802 |
| recall_mean_max | 3 | 0.967493 |  | 0.000450284 | 0.96692 | 0.96802 |
| recall_mean_min | 3 | 0.967493 |  | 0.000450284 | 0.96692 | 0.96802 |
| rss_after_mb | 3 | 2309.41 | 2.3GiB | 7.29152 | 2299.11 | 2314.97 |
| rss_before_mb | 3 | 191.716 | 191.7MiB | 0.635622 | 190.855 | 192.371 |
| rss_delta_mb | 3 | 2117.69 | 2.1GiB | 7.7475 | 2106.74 | 2123.29 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| time_sec | 3 | 22.7238 |  | 12.8625 | 4.53358 | 31.882 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### Backend: qdrant | Overquery: 4.0 (samples=3)

- Effective ef_search values: 100
- Effective overquery values:

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| effective_ef_search | 3 | 100 |  | 0 | 100 | 100 |
| latency_ms_mean | 3 | 51.6428 |  | 0.789854 | 50.5662 | 52.439 |
| latency_ms_mean_max | 3 | 51.6428 |  | 0.789854 | 50.5662 | 52.439 |
| latency_ms_mean_min | 3 | 51.6428 |  | 0.789854 | 50.5662 | 52.439 |
| latency_ms_p95 | 3 | 55.3298 |  | 0.902744 | 54.0531 | 55.9723 |
| latency_ms_p95_max | 3 | 55.3298 |  | 0.902744 | 54.0531 | 55.9723 |
| latency_ms_p95_min | 3 | 55.3298 |  | 0.902744 | 54.0531 | 55.9723 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0516428 |  | 0.000789854 | 0.0505662 | 0.052439 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.988787 |  | 0.000466 | 0.9882 | 0.98934 |
| recall_mean_max | 3 | 0.988787 |  | 0.000466 | 0.9882 | 0.98934 |
| recall_mean_min | 3 | 0.988787 |  | 0.000466 | 0.9882 | 0.98934 |
| rss_after_mb | 3 | 2531.7 | 2.5GiB | 11.9658 | 2514.87 | 2541.62 |
| rss_before_mb | 3 | 2532.3 | 2.5GiB | 5.23643 | 2525.1 | 2537.41 |
| rss_delta_mb | 3 | -0.595052 | -609.3KiB | 6.81605 | -10.2344 | 4.24609 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| time_sec | 3 | 51.7596 |  | 0.793378 | 50.6797 | 52.5633 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |
