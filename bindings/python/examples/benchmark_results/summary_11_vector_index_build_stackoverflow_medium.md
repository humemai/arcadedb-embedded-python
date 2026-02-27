# 11 Vector Index Build Matrix Summary

- Generated (UTC): 2026-02-27T12:38:13Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep11
- Total runs: 12
- Backends: arcadedb, milvus, pgvector, qdrant

## Parameters Used

| Parameter | Values |
|---|---|
| add_hierarchy | True |
| arcadedb_version | 26.2.1 |
| backend | arcadedb, milvus, pgvector, qdrant |
| batch_size | 5000 |
| beam_width | 100 |
| count | 1242391 |
| cpus | 8 |
| dataset | stackoverflow-medium |
| dataset_label | all |
| dim | 384 |
| docker_image | python:3.12-slim |
| heap | 13107m |
| max_connections | 16 |
| mem_limit | 16g |
| milvus_version | 2.6.10 |
| postgres_version | 16.11 (Debian 16.11-1.pgdg12+1) |
| qdrant_version | 1.11.3 |
| quantization | NONE |
| rows | 1242391 |
| run_label | sweep11_r01_arcadedb_s00000, sweep11_r01_milvus_s00003, sweep11_r01_pgvector_s00001, sweep11_r01_qdrant_s00002, sweep11_r02_arcadedb_s00004, sweep11_r02_milvus_s00007, sweep11_r02_pgvector_s00005, sweep11_r02_qdrant_s00006, sweep11_r03_arcadedb_s00008, sweep11_r03_milvus_s00011, sweep11_r03_pgvector_s00009, sweep11_r03_qdrant_s00010 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| server_fraction | 0.0, 0.8 |
| store_vectors_in_graph | False |
| threads | 8 |

## Aggregated Metrics by Backend

### Backend: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| budget.split.client_fraction | 3 | 1 |  | 0 | 1 | 1 |
| budget.split.server_fraction | 3 | 0 |  | 0 | 0 | 0 |
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| config.batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| db_size_mb | 3 | 2780.94 | 2.7GiB | 0 | 2780.94 | 2780.94 |
| disk_usage.du_bytes | 3 | 2.91605e+09 | 2.7GiB | 26824.5 | 2916020224 | 2916085760 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 8998.56 | 8.8GiB | 1084.61 | 7556.32 | 10171.9 |
| phases.close_db.rss_after_mb | 3 | 8998.5 | 8.8GiB | 1084.61 | 7556.25 | 10171.9 |
| phases.close_db.rss_before_mb | 3 | 8998.56 | 8.8GiB | 1084.61 | 7556.32 | 10171.9 |
| phases.close_db.rss_delta_mb | 3 | -0.0625 | -65536.0B | 0 | -0.0625 | -0.0625 |
| phases.close_db.time_sec | 3 | 0.0455387 |  | 0.0140466 | 0.0352362 | 0.0653989 |
| phases.create_db.rss_after_mb | 3 | 187.754 | 187.8MiB | 1.41954 | 185.805 | 189.145 |
| phases.create_db.rss_before_mb | 3 | 50.3112 | 50.3MiB | 0.0670794 | 50.2266 | 50.3906 |
| phases.create_db.rss_delta_mb | 3 | 137.443 | 137.4MiB | 1.46612 | 135.414 | 138.828 |
| phases.create_db.time_sec | 3 | 0.432712 |  | 0.0174205 | 0.415768 | 0.456672 |
| phases.create_index.rss_after_mb | 3 | 8998.56 | 8.8GiB | 1084.61 | 7556.32 | 10171.9 |
| phases.create_index.rss_before_mb | 3 | 4899.4 | 4.8GiB | 97.2306 | 4784.35 | 5022.14 |
| phases.create_index.rss_delta_mb | 3 | 4099.16 | 4.0GiB | 1153.47 | 2534.17 | 5280.21 |
| phases.create_index.time_sec | 3 | 2362.01 |  | 98.8098 | 2256.76 | 2494.24 |
| phases.ingest.ingested | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| phases.ingest.rss_after_mb | 3 | 4899.4 | 4.8GiB | 97.2306 | 4784.35 | 5022.14 |
| phases.ingest.rss_before_mb | 3 | 187.755 | 187.8MiB | 1.42082 | 185.805 | 189.148 |
| phases.ingest.rss_delta_mb | 3 | 4711.65 | 4.6GiB | 98.6161 | 4595.2 | 4836.34 |
| phases.ingest.time_sec | 3 | 44.2754 |  | 0.654796 | 43.5188 | 45.1161 |
| run.total_time_s | 3 | 2406.8 |  | 98.5504 | 2302.37 | 2538.94 |
| telemetry.db_close_time_s | 3 | 0.0455387 |  | 0.0140466 | 0.0352362 | 0.0653989 |
| telemetry.db_create_time_s | 3 | 0.432712 |  | 0.0174205 | 0.415768 | 0.456672 |

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
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| config.batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| db_size_mb | 3 | 8836.39 | 8.6GiB | 199.709 | 8554.48 | 8992.26 |
| disk_usage.du_bytes | 3 | 8.22972e+09 | 7.7GiB | 8.41098e+08 | 7570968576 | 9416826880 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 2993.28 | 2.9GiB | 237.483 | 2698.74 | 3280.3 |
| phases.close_db.rss_after_mb | 3 | 2979.63 | 2.9GiB | 237.835 | 2698.74 | 3280.3 |
| phases.close_db.rss_before_mb | 3 | 2982.88 | 2.9GiB | 236.021 | 2698.74 | 3276.63 |
| phases.close_db.rss_delta_mb | 3 | -3.2513 | -3409237.3B | 7.35198 | -13.4297 | 3.67578 |
| phases.close_db.time_sec | 3 | 0.274748 |  | 0.0132671 | 0.264134 | 0.293454 |
| phases.create_db.rss_after_mb | 3 | 532.171 | 532.2MiB | 7.15179 | 522.691 | 539.965 |
| phases.create_db.rss_before_mb | 3 | 531.901 | 531.9MiB | 7.18619 | 522.375 | 539.73 |
| phases.create_db.rss_delta_mb | 3 | 0.269531 | 276.0KiB | 0.0344991 | 0.234375 | 0.316406 |
| phases.create_db.time_sec | 3 | 0.210681 |  | 0.00247283 | 0.207533 | 0.213574 |
| phases.create_index.rss_after_mb | 3 | 576.826 | 576.8MiB | 9.12942 | 564.164 | 585.344 |
| phases.create_index.rss_before_mb | 3 | 575.626 | 575.6MiB | 9.31212 | 562.645 | 584.035 |
| phases.create_index.rss_delta_mb | 3 | 1.19922 | 1.2MiB | 0.315803 | 0.769531 | 1.51953 |
| phases.create_index.time_sec | 3 | 0.814486 |  | 0.076162 | 0.74353 | 0.920141 |
| phases.ingest.ingested | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| phases.ingest.rss_after_mb | 3 | 2991.2 | 2.9GiB | 235.004 | 2698.7 | 3274.09 |
| phases.ingest.rss_before_mb | 3 | 576.837 | 576.8MiB | 9.11921 | 564.191 | 585.352 |
| phases.ingest.rss_delta_mb | 3 | 2414.36 | 2.4GiB | 226.3 | 2134.5 | 2688.74 |
| phases.ingest.time_sec | 3 | 221.972 |  | 39.4091 | 166.245 | 250.503 |
| run.total_time_s | 3 | 240.067 |  | 40.187 | 183.258 | 269.903 |
| telemetry.db_close_time_s | 3 | 0.274748 |  | 0.0132671 | 0.264134 | 0.293454 |
| telemetry.db_create_time_s | 3 | 0.210681 |  | 0.00247283 | 0.207533 | 0.213574 |

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
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| config.batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| db_size_mb | 3 | 5438.43 | 5.3GiB | 0.00637888 | 5438.43 | 5438.44 |
| disk_usage.du_bytes | 3 | 5697310720 | 5.3GiB | 7.89829e+06 | 5686140928 | 5702930432 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 8908.87 | 8.7GiB | 100.139 | 8817.27 | 9048.21 |
| phases.close_db.rss_after_mb | 3 | 4706.23 | 4.6GiB | 99.8048 | 4615.23 | 4845.17 |
| phases.close_db.rss_before_mb | 3 | 8908.87 | 8.7GiB | 100.139 | 8817.27 | 9048.21 |
| phases.close_db.rss_delta_mb | 3 | -4202.64 | -4406792192.0B | 0.434642 | -4203.04 | -4202.04 |
| phases.close_db.time_sec | 3 | 0.00204709 |  | 0.000130406 | 0.00195461 | 0.00223151 |
| phases.create_db.rss_after_mb | 3 | 228.98 | 229.0MiB | 0.552022 | 228.316 | 229.668 |
| phases.create_db.rss_before_mb | 3 | 211.569 | 211.6MiB | 0.36234 | 211.137 | 212.023 |
| phases.create_db.rss_delta_mb | 3 | 17.4115 | 17.4MiB | 0.189774 | 17.1797 | 17.6445 |
| phases.create_db.time_sec | 3 | 0.00592294 |  | 0.000472596 | 0.00526507 | 0.00635398 |
| phases.create_index.rss_after_mb | 3 | 8908.87 | 8.7GiB | 100.139 | 8817.27 | 9048.21 |
| phases.create_index.rss_before_mb | 3 | 3886.42 | 3.8GiB | 20.4595 | 3858.69 | 3907.43 |
| phases.create_index.rss_delta_mb | 3 | 5022.45 | 4.9GiB | 89.5664 | 4924.13 | 5140.77 |
| phases.create_index.time_sec | 3 | 1139.09 |  | 82.5617 | 1022.37 | 1200.14 |
| phases.ingest.ingested | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| phases.ingest.rss_after_mb | 3 | 3886.42 | 3.8GiB | 20.4595 | 3858.69 | 3907.43 |
| phases.ingest.rss_before_mb | 3 | 247.242 | 247.2MiB | 0.13407 | 247.074 | 247.402 |
| phases.ingest.rss_delta_mb | 3 | 3639.18 | 3.6GiB | 20.5886 | 3611.29 | 3660.36 |
| phases.ingest.time_sec | 3 | 171.277 |  | 10.6508 | 157.225 | 183.001 |
| run.total_time_s | 3 | 1313.19 |  | 75.2045 | 1207.4 | 1375.56 |
| telemetry.db_close_time_s | 3 | 0.00204709 |  | 0.000130406 | 0.00195461 | 0.00223151 |
| telemetry.db_create_time_s | 3 | 0.00592294 |  | 0.000472596 | 0.00526507 | 0.00635398 |

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
| budget.total.threads_input | 3 | 8 |  | 0 | 8 | 8 |
| config.batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| config.beam_width | 3 | 100 |  | 0 | 100 | 100 |
| config.count | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| config.max_connections | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.milvus.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.milvus.port | 3 | 19530 |  | 0 | 19530 | 19530 |
| config.pg.port | 3 | 6543 |  | 0 | 6543 | 6543 |
| config.qdrant.hnsw_ef_construct | 3 | 100 |  | 0 | 100 | 100 |
| config.qdrant.hnsw_m | 3 | 16 |  | 0 | 16 | 16 |
| config.seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| dataset.dim | 3 | 384 |  | 0 | 384 | 384 |
| dataset.rows | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| db_size_mb | 3 | 2381.77 | 2.3GiB | 193.6 | 2108.3 | 2529.94 |
| disk_usage.du_bytes | 3 | 2.14452e+09 | 2.0GiB | 2.19715e+06 | 2142027776 | 2147373056 |
| environment.logical_cpu_count | 3 | 32 |  | 0 | 32 | 32 |
| environment.physical_cpu_count | 3 | 16 |  | 0 | 16 | 16 |
| environment.threads_limit | 3 | 8 |  | 0 | 8 | 8 |
| peak_rss_mb | 3 | 3361.47 | 3.3GiB | 176.919 | 3114.21 | 3518.25 |
| phases.close_db.rss_after_mb | 3 | 3357.68 | 3.3GiB | 181.529 | 3103.75 | 3517.35 |
| phases.close_db.rss_before_mb | 3 | 3361.15 | 3.3GiB | 176.599 | 3114.28 | 3517.3 |
| phases.close_db.rss_delta_mb | 3 | -3.47526 | -3644074.7B | 4.98658 | -10.5273 | 0.0546875 |
| phases.close_db.time_sec | 3 | 0.0498745 |  | 0.00803436 | 0.0388048 | 0.0576281 |
| phases.create_db.rss_after_mb | 3 | 172.849 | 172.8MiB | 1.1947 | 171.277 | 174.172 |
| phases.create_db.rss_before_mb | 3 | 168.949 | 168.9MiB | 1.19641 | 167.375 | 170.273 |
| phases.create_db.rss_delta_mb | 3 | 3.89974 | 3.9MiB | 0.00184142 | 3.89844 | 3.90234 |
| phases.create_db.time_sec | 3 | 0.175314 |  | 0.00429591 | 0.169712 | 0.180151 |
| phases.create_index.rss_after_mb | 3 | 186.374 | 186.4MiB | 0.932066 | 185.074 | 187.215 |
| phases.create_index.rss_before_mb | 3 | 172.849 | 172.8MiB | 1.1947 | 171.277 | 174.172 |
| phases.create_index.rss_delta_mb | 3 | 13.5247 | 13.5MiB | 0.341618 | 13.043 | 13.7969 |
| phases.create_index.time_sec | 3 | 0.636727 |  | 0.0906732 | 0.532095 | 0.753243 |
| phases.ingest.ingested | 3 | 1242391 |  | 0 | 1242391 | 1242391 |
| phases.ingest.rss_after_mb | 3 | 3361.41 | 3.3GiB | 176.887 | 3114.21 | 3518.25 |
| phases.ingest.rss_before_mb | 3 | 186.378 | 186.4MiB | 0.932066 | 185.078 | 187.219 |
| phases.ingest.rss_delta_mb | 3 | 3175.03 | 3.1GiB | 177.076 | 2927.38 | 3331.04 |
| phases.ingest.time_sec | 3 | 327.726 |  | 10.5675 | 314.977 | 340.854 |
| run.total_time_s | 3 | 331.754 |  | 10.9412 | 318.756 | 345.523 |
| telemetry.db_close_time_s | 3 | 0.0498745 |  | 0.00803436 | 0.0388048 | 0.0576281 |
| telemetry.db_create_time_s | 3 | 0.175314 |  | 0.00429591 | 0.169712 | 0.180151 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| config.add_hierarchy | 3 | 3 | 0 | 1 |
| config.store_vectors_in_graph | 3 | 0 | 3 | 0 |
| environment.is_running_in_docker | 3 | 3 | 0 | 1 |
