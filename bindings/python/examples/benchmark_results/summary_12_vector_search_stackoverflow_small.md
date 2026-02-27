# 12 Vector Search Matrix Summary

- Generated (UTC): 2026-02-27T12:38:14Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep12
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant
- Sweep samples: 12

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| cpus | 4 |
| dataset | stackoverflow-small |
| dataset_label | all |
| dim | 384 |
| docker_image | pgvector/pgvector:pg16, python:3.12-slim |
| heap | 3276m |
| k | 50 |
| mem_limit | 4g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| query_count | 1000 |
| query_limit | 1000 |
| query_order | shuffled |
| query_runs | 1 |
| rows | 300424 |
| run_label | sweep12_r01_arcadedb_s00000, sweep12_r01_milvus_s00003, sweep12_r01_pgvector_s00001, sweep12_r01_qdrant_s00002, sweep12_r02_arcadedb_s00004, sweep12_r02_milvus_s00007, sweep12_r02_pgvector_s00005, sweep12_r02_qdrant_s00006, sweep12_r03_arcadedb_s00008, sweep12_r03_milvus_s00011, sweep12_r03_pgvector_s00009, sweep12_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| threads | 4 |

## Aggregated Run Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| disk_usage_search.du_bytes | 3 | 705552384 | 672.9MiB | 0 | 705552384 | 705552384 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 1580.96 | 1.5GiB | 117.107 | 1444.55 | 1730.5 |
| run.total_time_s | 3 | 15.8736 |  | 2.50523 | 12.5332 | 18.5663 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| telemetry.db_close_time_s | 3 | 0.0125751 |  | 0.00134327 | 0.0114502 | 0.0144633 |
| telemetry.db_open_time_s | 3 | 1.74277 |  | 0.354093 | 1.44257 | 2.23998 |
| telemetry.query_cold_time_s | 3 | 0.0132978 |  | 0.00241291 | 0.0099356 | 0.0154837 |

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
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| disk_usage_search.du_bytes | 3 | 2862755840 | 2.7GiB | 1.88739e+08 | 2622930944 | 3084140544 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 2319.87 | 2.3GiB | 108.464 | 2166.49 | 2398.17 |
| run.total_time_s | 3 | 38.5324 |  | 1.8492 | 36.4443 | 40.94 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| telemetry.db_close_time_s | 3 | 0.433661 |  | 0.0606531 | 0.34851 | 0.485193 |
| telemetry.db_open_time_s | 3 | 0.399571 |  | 0.0633328 | 0.327053 | 0.481354 |
| telemetry.query_cold_time_s | 3 | 0.0117203 |  | 0.00144744 | 0.0103613 | 0.0137255 |

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
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| disk_usage_search.du_bytes | 3 | 2.21505e+09 | 2.1GiB | 31609.8 | 2215022592 | 2215096320 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 1047.37 | 1.0GiB | 0.523003 | 1046.69 | 1047.96 |
| run.total_time_s | 3 | 27.5999 |  | 4.19711 | 24.4956 | 33.5334 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| telemetry.db_close_time_s | 3 | 0.00203598 |  | 0.00012571 | 0.00189896 | 0.00220259 |
| telemetry.db_open_time_s | 3 | 0.0409438 |  | 0.0319386 | 0.0169692 | 0.0860826 |
| telemetry.query_cold_time_s | 3 | 0.0263958 |  | 0.00463406 | 0.0223512 | 0.0328838 |

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
| budget.total.threads_input | 3 | 4 |  | 0 | 4 | 4 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.query_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.query_limit | 3 | 1000 |  | 0 | 1000 | 1000 |
| dataset.rows | 3 | 300424 |  | 0 | 300424 | 300424 |
| disk_usage_search.du_bytes | 3 | 579735552 | 552.9MiB | 2.76309e+06 | 577445888 | 583622656 |
| environment.hnsw_ef_normalization | 3 | 0.5 |  | 0 | 0.5 | 0.5 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 4 |  | 0 | 4 | 4 |
| peak_rss_mb | 3 | 916.279 | 916.3MiB | 4.4602 | 910.246 | 920.891 |
| run.total_time_s | 3 | 57.6307 |  | 1.4013 | 56.3839 | 59.5881 |
| search.k | 3 | 50 |  | 0 | 50 | 50 |
| search.query_runs | 3 | 1 |  | 0 | 1 | 1 |
| search.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| telemetry.db_close_time_s | 3 | 0.057921 |  | 0.0121476 | 0.0429903 | 0.0727451 |
| telemetry.db_open_time_s | 3 | 0.232814 |  | 0.0159908 | 0.218206 | 0.255069 |
| telemetry.query_cold_time_s | 3 | 0.0494998 |  | 0.000718773 | 0.048775 | 0.0504794 |

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
| latency_ms_mean | 3 | 13.2978 |  | 2.41291 | 9.9356 | 15.4837 |
| latency_ms_mean_max | 3 | 13.2978 |  | 2.41291 | 9.9356 | 15.4837 |
| latency_ms_mean_min | 3 | 13.2978 |  | 2.41291 | 9.9356 | 15.4837 |
| latency_ms_p95 | 3 | 18.1437 |  | 3.45447 | 13.6058 | 21.9797 |
| latency_ms_p95_max | 3 | 18.1437 |  | 3.45447 | 13.6058 | 21.9797 |
| latency_ms_p95_min | 3 | 18.1437 |  | 3.45447 | 13.6058 | 21.9797 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0132978 |  | 0.00241291 | 0.0099356 | 0.0154837 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.963907 |  | 0.000703768 | 0.96324 | 0.96488 |
| recall_mean_max | 3 | 0.963907 |  | 0.000703768 | 0.96324 | 0.96488 |
| recall_mean_min | 3 | 0.963907 |  | 0.000703768 | 0.96324 | 0.96488 |
| rss_after_mb | 3 | 1580.96 | 1.5GiB | 117.107 | 1444.55 | 1730.5 |
| rss_before_mb | 3 | 1073.29 | 1.0GiB | 33.4959 | 1033.55 | 1115.48 |
| rss_delta_mb | 3 | 507.676 | 507.7MiB | 100.291 | 373.719 | 615.016 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| time_sec | 3 | 13.7199 |  | 2.42896 | 10.3364 | 15.9249 |

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
| latency_ms_mean | 3 | 11.7203 |  | 1.44744 | 10.3613 | 13.7255 |
| latency_ms_mean_max | 3 | 11.7203 |  | 1.44744 | 10.3613 | 13.7255 |
| latency_ms_mean_min | 3 | 11.7203 |  | 1.44744 | 10.3613 | 13.7255 |
| latency_ms_p95 | 3 | 9.15478 |  | 3.36287 | 4.40966 | 11.8034 |
| latency_ms_p95_max | 3 | 9.15478 |  | 3.36287 | 4.40966 | 11.8034 |
| latency_ms_p95_min | 3 | 9.15478 |  | 3.36287 | 4.40966 | 11.8034 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0117203 |  | 0.00144744 | 0.0103613 | 0.0137255 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.982767 |  | 0.003619 | 0.97768 | 0.9858 |
| recall_mean_max | 3 | 0.982767 |  | 0.003619 | 0.97768 | 0.9858 |
| recall_mean_min | 3 | 0.982767 |  | 0.003619 | 0.97768 | 0.9858 |
| rss_after_mb | 3 | 2319.18 | 2.3GiB | 108.501 | 2165.74 | 2396.86 |
| rss_before_mb | 3 | 1596.74 | 1.6GiB | 161.641 | 1371.39 | 1742.63 |
| rss_delta_mb | 3 | 722.441 | 722.4MiB | 58.001 | 652.316 | 794.355 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| time_sec | 3 | 12.1319 |  | 1.46125 | 10.7562 | 14.1552 |

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
| latency_ms_mean | 3 | 26.3958 |  | 4.63406 | 22.3512 | 32.8838 |
| latency_ms_mean_max | 3 | 26.3958 |  | 4.63406 | 22.3512 | 32.8838 |
| latency_ms_mean_min | 3 | 26.3958 |  | 4.63406 | 22.3512 | 32.8838 |
| latency_ms_p95 | 3 | 116.001 |  | 32.9088 | 75.0775 | 155.657 |
| latency_ms_p95_max | 3 | 116.001 |  | 32.9088 | 75.0775 | 155.657 |
| latency_ms_p95_min | 3 | 116.001 |  | 32.9088 | 75.0775 | 155.657 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0263958 |  | 0.00463406 | 0.0223512 | 0.0328838 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.978213 |  | 9.84322e-05 | 0.9781 | 0.97834 |
| recall_mean_max | 3 | 0.978213 |  | 9.84322e-05 | 0.9781 | 0.97834 |
| recall_mean_min | 3 | 0.978213 |  | 9.84322e-05 | 0.9781 | 0.97834 |
| rss_after_mb | 3 | 1047.13 | 1.0GiB | 0.319348 | 1046.69 | 1047.45 |
| rss_before_mb | 3 | 169.125 | 169.1MiB | 0.390716 | 168.648 | 169.605 |
| rss_delta_mb | 3 | 878.001 | 878.0MiB | 0.115453 | 877.844 | 878.117 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| time_sec | 3 | 26.4461 |  | 4.63287 | 22.4069 | 32.9332 |

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
| latency_ms_mean | 3 | 49.4998 |  | 0.718773 | 48.775 | 50.4794 |
| latency_ms_mean_max | 3 | 49.4998 |  | 0.718773 | 48.775 | 50.4794 |
| latency_ms_mean_min | 3 | 49.4998 |  | 0.718773 | 48.775 | 50.4794 |
| latency_ms_p95 | 3 | 52.9323 |  | 0.937763 | 51.8453 | 54.1338 |
| latency_ms_p95_max | 3 | 52.9323 |  | 0.937763 | 51.8453 | 54.1338 |
| latency_ms_p95_min | 3 | 52.9323 |  | 0.937763 | 51.8453 | 54.1338 |
| overquery_factor | 3 | 4 |  | 0 | 4 | 4 |
| queries | 3 | 1000 |  | 0 | 1000 | 1000 |
| query_cold_time_s | 3 | 0.0494998 |  | 0.000718773 | 0.048775 | 0.0504794 |
| query_runs | 3 | 1 |  | 0 | 1 | 1 |
| recall_count | 3 | 1000 |  | 0 | 1000 | 1000 |
| recall_mean | 3 | 0.990293 |  | 0.000955033 | 0.98922 | 0.99154 |
| recall_mean_max | 3 | 0.990293 |  | 0.000955033 | 0.98922 | 0.99154 |
| recall_mean_min | 3 | 0.990293 |  | 0.000955033 | 0.98922 | 0.99154 |
| rss_after_mb | 3 | 916.279 | 916.3MiB | 4.4602 | 910.246 | 920.891 |
| rss_before_mb | 3 | 907.487 | 907.5MiB | 1.78992 | 905.262 | 909.645 |
| rss_delta_mb | 3 | 8.79167 | 8.8MiB | 4.34087 | 2.69141 | 12.4375 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| time_sec | 3 | 49.6518 |  | 0.722782 | 48.9106 | 50.632 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |
