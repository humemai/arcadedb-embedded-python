# 12 Vector Search Matrix Summary

- Generated (UTC): 2026-02-27T12:38:14Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep12
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant
- Sweep samples: 12

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| cpus | 2 |
| dataset | stackoverflow-tiny |
| dataset_label | all |
| dim | 384 |
| docker_image | pgvector/pgvector:pg16, python:3.12-slim |
| heap | 1638m |
| k | 50 |
| mem_limit | 2g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| query_count | 1000 |
| query_limit | 1000 |
| query_order | shuffled |
| query_runs | 1 |
| rows | 19591 |
| run_label | sweep12_r01_arcadedb_s00000, sweep12_r01_milvus_s00003, sweep12_r01_pgvector_s00001, sweep12_r01_qdrant_s00002, sweep12_r02_arcadedb_s00004, sweep12_r02_milvus_s00007, sweep12_r02_pgvector_s00005, sweep12_r02_qdrant_s00006, sweep12_r03_arcadedb_s00008, sweep12_r03_milvus_s00011, sweep12_r03_pgvector_s00009, sweep12_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| threads | 2 |

## Aggregated Run Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| disk_usage_search.du_bytes | 3 | 4.65196e+07 | 44.4MiB | 1930.87 | 46518272 | 46522368 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 366.107 | 366.1MiB | 5.60863 | 359.984 | 373.535 |
| run.total_time_s | 3 | 10.368 |  | 0.755038 | 9.82587 | 11.4358 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| telemetry.db_close_time_s | 3 | 0.00803181 |  | 0.000802019 | 0.00703406 | 0.00899783 |
| telemetry.db_open_time_s | 3 | 0.724825 |  | 0.113984 | 0.633004 | 0.885476 |
| telemetry.query_cold_time_s | 3 | 0.00888508 |  | 0.000502123 | 0.00849223 | 0.00959379 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| disk_usage_search.du_bytes | 3 | 2.42902e+08 | 231.6MiB | 29975.2 | 242860032 | 242925568 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 878.503 | 878.5MiB | 6.63125 | 869.145 | 883.711 |
| run.total_time_s | 3 | 35.4523 |  | 0.915385 | 34.7602 | 36.7458 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| telemetry.db_close_time_s | 3 | 0.913591 |  | 0.155425 | 0.734784 | 1.1137 |
| telemetry.db_open_time_s | 3 | 0.638741 |  | 0.0266438 | 0.615597 | 0.676064 |
| telemetry.query_cold_time_s | 3 | 0.00928912 |  | 0.000440262 | 0.00885852 | 0.00989388 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| disk_usage_search.du_bytes | 3 | 187957248 | 179.2MiB | 17696.7 | 187932672 | 187973632 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 245.691 | 245.7MiB | 0.904435 | 244.508 | 246.703 |
| run.total_time_s | 3 | 3.18733 |  | 0.516449 | 2.47965 | 3.69759 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| telemetry.db_close_time_s | 3 | 0.00189082 |  | 0.000169339 | 0.00165973 | 0.00206077 |
| telemetry.db_open_time_s | 3 | 0.0264666 |  | 0.0159185 | 0.0126544 | 0.048768 |
| telemetry.query_cold_time_s | 3 | 0.00246935 |  | 0.000486542 | 0.0018434 | 0.00302977 |

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
| budget.total.threads_input | 3 | 2 |  | 0 | 2 | 2 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 19591 |  | 0 | 19591 | 19591 |
| disk_usage_search.du_bytes | 3 | 74178560 | 70.7MiB | 2.96003e+06 | 69992448 | 76271616 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 2 |  | 0 | 2 | 2 |
| peak_rss_mb | 3 | 299.513 | 299.5MiB | 3.48799 | 295.207 | 303.75 |
| run.total_time_s | 3 | 50.0121 |  | 0.333121 | 49.6078 | 50.4236 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| telemetry.db_close_time_s | 3 | 0.102522 |  | 0.00238943 | 0.0996332 | 0.105485 |
| telemetry.db_open_time_s | 3 | 0.364438 |  | 0.0214411 | 0.346304 | 0.394552 |
| telemetry.query_cold_time_s | 3 | 0.0450197 |  | 0.000262692 | 0.0447028 | 0.045346 |

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
| latency_ms_mean | 3 | 8.88508 |  | 0.502123 | 8.49223 | 9.59379 |
| latency_ms_mean_max | 3 | 8.88508 |  | 0.502123 | 8.49223 | 9.59379 |
| latency_ms_mean_min | 3 | 8.88508 |  | 0.502123 | 8.49223 | 9.59379 |
| latency_ms_p95 | 3 | 14.3746 |  | 1.81685 | 12.777 | 16.9161 |
| latency_ms_p95_max | 3 | 14.3746 |  | 1.81685 | 12.777 | 16.9161 |
| latency_ms_p95_min | 3 | 14.3746 |  | 1.81685 | 12.777 | 16.9161 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.00888508 |  | 0.000502123 | 0.00849223 | 0.00959379 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.99166 |  | 0 | 0.99166 | 0.99166 |
| recall_mean_max | 3 | 0.99166 |  | 0 | 0.99166 | 0.99166 |
| recall_mean_min | 3 | 0.99166 |  | 0 | 0.99166 | 0.99166 |
| rss_after_mb | 3 | 366.096 | 366.1MiB | 5.59484 | 359.984 | 373.504 |
| rss_before_mb | 3 | 205.587 | 205.6MiB | 0.155019 | 205.391 | 205.77 |
| rss_delta_mb | 3 | 160.509 | 160.5MiB | 5.74912 | 154.215 | 168.113 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| time_sec | 3 | 9.33805 |  | 0.504315 | 8.91519 | 10.0469 |

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
| latency_ms_mean | 3 | 9.28912 |  | 0.440262 | 8.85852 | 9.89388 |
| latency_ms_mean_max | 3 | 9.28912 |  | 0.440262 | 8.85852 | 9.89388 |
| latency_ms_mean_min | 3 | 9.28912 |  | 0.440262 | 8.85852 | 9.89388 |
| latency_ms_p95 | 3 | 2.34816 |  | 0.184665 | 2.13736 | 2.58707 |
| latency_ms_p95_max | 3 | 2.34816 |  | 0.184665 | 2.13736 | 2.58707 |
| latency_ms_p95_min | 3 | 2.34816 |  | 0.184665 | 2.13736 | 2.58707 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.00928912 |  | 0.000440262 | 0.00885852 | 0.00989388 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.987773 |  | 0.000895669 | 0.98714 | 0.98904 |
| recall_mean_max | 3 | 0.987773 |  | 0.000895669 | 0.98714 | 0.98904 |
| recall_mean_min | 3 | 0.987773 |  | 0.000895669 | 0.98714 | 0.98904 |
| rss_after_mb | 3 | 859.309 | 859.3MiB | 23.8245 | 826.531 | 882.453 |
| rss_before_mb | 3 | 634.102 | 634.1MiB | 3.20662 | 630.43 | 638.242 |
| rss_delta_mb | 3 | 225.207 | 225.2MiB | 22.9638 | 192.898 | 244.211 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| time_sec | 3 | 10.0691 |  | 0.582806 | 9.59704 | 10.8903 |

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
| latency_ms_mean | 3 | 2.46935 |  | 0.486542 | 1.8434 | 3.02977 |
| latency_ms_mean_max | 3 | 2.46935 |  | 0.486542 | 1.8434 | 3.02977 |
| latency_ms_mean_min | 3 | 2.46935 |  | 0.486542 | 1.8434 | 3.02977 |
| latency_ms_p95 | 3 | 6.14022 |  | 2.21617 | 3.65749 | 9.03814 |
| latency_ms_p95_max | 3 | 6.14022 |  | 2.21617 | 3.65749 | 9.03814 |
| latency_ms_p95_min | 3 | 6.14022 |  | 2.21617 | 3.65749 | 9.03814 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.00246935 |  | 0.000486542 | 0.0018434 | 0.00302977 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.99336 |  | 2.82843e-05 | 0.99332 | 0.99338 |
| recall_mean_max | 3 | 0.99336 |  | 2.82843e-05 | 0.99332 | 0.99338 |
| recall_mean_min | 3 | 0.99336 |  | 2.82843e-05 | 0.99332 | 0.99338 |
| rss_after_mb | 3 | 243.417 | 243.4MiB | 0.788858 | 242.594 | 244.48 |
| rss_before_mb | 3 | 158.076 | 158.1MiB | 1.07527 | 157.043 | 159.559 |
| rss_delta_mb | 3 | 85.3411 | 85.3MiB | 0.296469 | 84.9219 | 85.5508 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| time_sec | 3 | 2.7976 |  | 0.507108 | 2.10065 | 3.29247 |

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
| latency_ms_mean | 3 | 45.0197 |  | 0.262692 | 44.7028 | 45.346 |
| latency_ms_mean_max | 3 | 45.0197 |  | 0.262692 | 44.7028 | 45.346 |
| latency_ms_mean_min | 3 | 45.0197 |  | 0.262692 | 44.7028 | 45.346 |
| latency_ms_p95 | 3 | 46.496 |  | 0.336592 | 46.0213 | 46.7632 |
| latency_ms_p95_max | 3 | 46.496 |  | 0.336592 | 46.0213 | 46.7632 |
| latency_ms_p95_min | 3 | 46.496 |  | 0.336592 | 46.0213 | 46.7632 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0450197 |  | 0.000262692 | 0.0447028 | 0.045346 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 1 |  | 0 | 1 | 1 |
| recall_mean_max | 3 | 1 |  | 0 | 1 | 1 |
| recall_mean_min | 3 | 1 |  | 0 | 1 | 1 |
| rss_after_mb | 3 | 294.268 | 294.3MiB | 8.15217 | 283.848 | 303.75 |
| rss_before_mb | 3 | 296.754 | 296.8MiB | 4.2308 | 290.773 | 299.902 |
| rss_delta_mb | 3 | -2.48568 | -2.5MiB | 9.37406 | -15.7383 | 4.43359 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| time_sec | 3 | 45.2034 |  | 0.256644 | 44.8891 | 45.5177 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |
