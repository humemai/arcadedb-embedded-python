# 07 Tables OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:09Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep07
- Total runs: 18

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 2500 |
| dataset | stackoverflow-small |
| db | arcadedb, duckdb, postgresql, sqlite |
| docker_image | python:3.12-slim |
| duckdb_version | 1.4.4 |
| heap_size | 1638m, 2g |
| mem_limit | 2g |
| run_label | sweep07_t01_r01_arcadedb_s00000, sweep07_t01_r01_duckdb_s00002, sweep07_t01_r01_postgresql_s00003, sweep07_t01_r01_sqlite_s00001, sweep07_t01_r02_arcadedb_s00004, sweep07_t01_r02_duckdb_s00006, sweep07_t01_r02_postgresql_s00007, sweep07_t01_r02_sqlite_s00005, sweep07_t01_r03_arcadedb_s00008, sweep07_t01_r03_duckdb_s00010, sweep07_t01_r03_postgresql_s00011, sweep07_t01_r03_sqlite_s00009, sweep07_t08_r01_arcadedb_s00000, sweep07_t08_r01_sqlite_s00001, sweep07_t08_r02_arcadedb_s00002, sweep07_t08_r02_sqlite_s00003, sweep07_t08_r03_arcadedb_s00004, sweep07_t08_r03_sqlite_s00005 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| threads | 1, 8 |
| transactions | 50000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.00762836 |  | 0.00423802 | 0.00166655 | 0.011142 |
| disk_after_oltp_bytes | 3 | 6.76482e+08 | 645.1MiB | 2.96117e+07 | 635987763 | 705972715 |
| disk_after_preload_bytes | 3 | 673587887 | 642.4MiB | 6.02252e+07 | 600778646 | 748264221 |
| disk_usage.du_bytes | 3 | 601686016 | 573.8MiB | 3344.37 | 601681920 | 601690112 |
| final_counts.Badge | 3 | 183004 |  | 11.0454 | 182990 | 183017 |
| final_counts.Comment | 3 | 195788 |  | 19.6469 | 195765 | 195813 |
| final_counts.Post | 3 | 105363 |  | 7.31817 | 105357 | 105373 |
| final_counts.PostHistory | 3 | 360343 |  | 33.6683 | 360310 | 360389 |
| final_counts.PostLink | 3 | 11011 |  | 19.3046 | 10986 | 11033 |
| final_counts.Tag | 3 | 673 |  | 27.9404 | 648 | 712 |
| final_counts.User | 3 | 138744 |  | 29.937 | 138717 | 138786 |
| final_counts.Vote | 3 | 411148 |  | 29.17 | 411122 | 411189 |
| latency_summary.ops.delete.count | 3 | 4989.33 |  | 45.419 | 4936 | 5047 |
| latency_summary.ops.delete.p50_ms | 3 | 1.1052 |  | 0.116276 | 0.961513 | 1.24629 |
| latency_summary.ops.delete.p95_ms | 3 | 19.7065 |  | 3.30933 | 15.0326 | 22.2527 |
| latency_summary.ops.delete.p99_ms | 3 | 42.8077 |  | 9.31809 | 30.3905 | 52.8372 |
| latency_summary.ops.insert.count | 3 | 5028.33 |  | 42.1453 | 4984 | 5085 |
| latency_summary.ops.insert.p50_ms | 3 | 0.303284 |  | 0.0406835 | 0.263591 | 0.359201 |
| latency_summary.ops.insert.p95_ms | 3 | 13.7626 |  | 6.13144 | 5.11788 | 18.6711 |
| latency_summary.ops.insert.p99_ms | 3 | 26.0436 |  | 1.63233 | 23.7355 | 27.2311 |
| latency_summary.ops.read.count | 3 | 30127 |  | 39.37 | 30072 | 30162 |
| latency_summary.ops.read.p50_ms | 3 | 0.05091 |  | 0.00748147 | 0.04484 | 0.06145 |
| latency_summary.ops.read.p95_ms | 3 | 1.89503 |  | 2.21255 | 0.313171 | 5.02399 |
| latency_summary.ops.read.p99_ms | 3 | 5.09497 |  | 3.73305 | 1.33412 | 10.1841 |
| latency_summary.ops.update.count | 3 | 9855.33 |  | 41.9629 | 9796 | 9886 |
| latency_summary.ops.update.p50_ms | 3 | 0.113401 |  | 0.0241641 | 0.093771 | 0.147441 |
| latency_summary.ops.update.p95_ms | 3 | 3.33223 |  | 1.50674 | 2.0861 | 5.45221 |
| latency_summary.ops.update.p99_ms | 3 | 7.44384 |  | 2.84127 | 4.90828 | 11.4111 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 0.088097 |  | 0.0218833 | 0.070801 | 0.11897 |
| latency_summary.overall.p95_ms | 3 | 3.25243 |  | 1.71568 | 1.97995 | 5.67779 |
| latency_summary.overall.p99_ms | 3 | 19.3562 |  | 1.78792 | 16.8658 | 20.9799 |
| load_counts_time_s | 3 | 0.127504 |  | 0.0900852 | 0.041841 | 0.252002 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 74.0592 |  | 1.31744 | 72.4735 | 75.6992 |
| rss_client_peak_kb | 3 | 1733136 | 1.7GiB | 127872 | 1629284 | 1913272 |
| rss_peak_kb | 3 | 1733136 | 1.7GiB | 127872 | 1629284 | 1913272 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 1114.79 |  | 178.446 | 874.286 | 1301.25 |
| total_time_s | 3 | 46.1306 |  | 8.01922 | 38.4247 | 57.1895 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.00490689 |  | 0.00428604 | 0.0018518 | 0.0109682 |
| disk_after_oltp_bytes | 3 | 7.71986e+08 | 736.2MiB | 6.73287e+07 | 720242860 | 867080046 |
| disk_after_preload_bytes | 3 | 660645528 | 630.0MiB | 1.54397e+07 | 641301703 | 679088938 |
| disk_usage.du_bytes | 3 | 6.01685e+08 | 573.8MiB | 1930.87 | 601681920 | 601686016 |
| final_counts.Badge | 3 | 182964 |  | 45.7991 | 182900 | 183003 |
| final_counts.Comment | 3 | 195778 |  | 21.1397 | 195758 | 195807 |
| final_counts.Post | 3 | 105341 |  | 4.98888 | 105336 | 105348 |
| final_counts.PostHistory | 3 | 360366 |  | 28.5463 | 360326 | 360388 |
| final_counts.PostLink | 3 | 11007 |  | 9.89949 | 11000 | 11021 |
| final_counts.Tag | 3 | 669.333 |  | 20.1384 | 641 | 686 |
| final_counts.User | 3 | 138742 |  | 27.6446 | 138703 | 138766 |
| final_counts.Vote | 3 | 411181 |  | 54.3016 | 411115 | 411248 |
| latency_summary.ops.delete.count | 3 | 5003 |  | 31.2836 | 4977 | 5047 |
| latency_summary.ops.delete.p50_ms | 3 | 2.36615 |  | 0.320151 | 2.11962 | 2.8183 |
| latency_summary.ops.delete.p95_ms | 3 | 36.4996 |  | 5.68598 | 28.5606 | 41.5756 |
| latency_summary.ops.delete.p99_ms | 3 | 74.4018 |  | 14.2476 | 55.817 | 90.4355 |
| latency_summary.ops.insert.count | 3 | 5016 |  | 48.833 | 4979 | 5085 |
| latency_summary.ops.insert.p50_ms | 3 | 1.04631 |  | 0.250926 | 0.847053 | 1.40023 |
| latency_summary.ops.insert.p95_ms | 3 | 40.2369 |  | 3.27073 | 35.714 | 43.3375 |
| latency_summary.ops.insert.p99_ms | 3 | 94.816 |  | 17.3109 | 75.6866 | 117.611 |
| latency_summary.ops.read.count | 3 | 30080 |  | 51.7494 | 30021 | 30147 |
| latency_summary.ops.read.p50_ms | 3 | 0.152477 |  | 0.0205442 | 0.13335 | 0.18098 |
| latency_summary.ops.read.p95_ms | 3 | 4.36184 |  | 0.616271 | 3.49055 | 4.81567 |
| latency_summary.ops.read.p99_ms | 3 | 12.1496 |  | 3.09386 | 8.10734 | 15.6209 |
| latency_summary.ops.update.count | 3 | 9901 |  | 93.4487 | 9796 | 10023 |
| latency_summary.ops.update.p50_ms | 3 | 0.395571 |  | 0.0713529 | 0.332861 | 0.495391 |
| latency_summary.ops.update.p95_ms | 3 | 20.8539 |  | 2.37342 | 17.5502 | 23.0197 |
| latency_summary.ops.update.p99_ms | 3 | 50.5002 |  | 8.19799 | 40.7552 | 60.812 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 0.276717 |  | 0.042578 | 0.23659 | 0.335661 |
| latency_summary.overall.p95_ms | 3 | 14.2803 |  | 2.49663 | 11.0226 | 17.0882 |
| latency_summary.overall.p99_ms | 3 | 46.6842 |  | 6.65285 | 38.4002 | 54.6891 |
| load_counts_time_s | 3 | 0.0491334 |  | 0.0136858 | 0.038363 | 0.0684452 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 60.3851 |  | 0.905248 | 59.3244 | 61.5363 |
| rss_client_peak_kb | 3 | 1401980 | 1.3GiB | 107717 | 1321924 | 1554248 |
| rss_peak_kb | 3 | 1401980 | 1.3GiB | 107717 | 1321924 | 1554248 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 3 | 2492.18 |  | 333.044 | 2066.41 | 2879.46 |
| total_time_s | 3 | 20.4395 |  | 2.83063 | 17.3643 | 24.1966 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: duckdb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 14.0615 |  | 4.96901 | 9.46855 | 20.964 |
| disk_after_oltp_bytes | 3 | 1.68988e+09 | 1.6GiB | 2.18156e+07 | 1672022183 | 1720599957 |
| disk_after_preload_bytes | 3 | 1.20266e+09 | 1.1GiB | 326951 | 1202307387 | 1203093819 |
| disk_usage.du_bytes | 3 | 1.58819e+09 | 1.5GiB | 2.92442e+06 | 1585745920 | 1592303616 |
| final_counts.Badge | 3 | 182963 |  | 46.6214 | 182899 | 183008 |
| final_counts.Comment | 3 | 195772 |  | 9.46338 | 195764 | 195785 |
| final_counts.Post | 3 | 105381 |  | 9.4163 | 105368 | 105390 |
| final_counts.PostHistory | 3 | 360326 |  | 6.79869 | 360319 | 360335 |
| final_counts.PostLink | 3 | 10994.7 |  | 59.0273 | 10917 | 11060 |
| final_counts.Tag | 3 | 653.333 |  | 12.2837 | 636 | 663 |
| final_counts.User | 3 | 138730 |  | 41.2499 | 138673 | 138770 |
| final_counts.Vote | 3 | 411197 |  | 17.7826 | 411173 | 411215 |
| latency_summary.ops.delete.count | 3 | 5002.67 |  | 38.439 | 4974 | 5057 |
| latency_summary.ops.delete.p50_ms | 3 | 13.4916 |  | 1.3727 | 11.9633 | 15.2924 |
| latency_summary.ops.delete.p95_ms | 3 | 36.707 |  | 4.80392 | 30.974 | 42.7304 |
| latency_summary.ops.delete.p99_ms | 3 | 71.7772 |  | 13.4649 | 54.9854 | 87.9501 |
| latency_summary.ops.insert.count | 3 | 4984.33 |  | 36.9354 | 4942 | 5032 |
| latency_summary.ops.insert.p50_ms | 3 | 14.3547 |  | 1.30459 | 12.8449 | 16.028 |
| latency_summary.ops.insert.p95_ms | 3 | 44.0368 |  | 5.89904 | 36.7855 | 51.2348 |
| latency_summary.ops.insert.p99_ms | 3 | 114.702 |  | 18.02 | 91.8719 | 135.924 |
| latency_summary.ops.read.count | 3 | 30053.3 |  | 100.214 | 29950 | 30189 |
| latency_summary.ops.read.p50_ms | 3 | 0.694945 |  | 0.0173543 | 0.672832 | 0.715222 |
| latency_summary.ops.read.p95_ms | 3 | 5.66958 |  | 0.738468 | 5.00482 | 6.69951 |
| latency_summary.ops.read.p99_ms | 3 | 29.4466 |  | 7.36635 | 23.0341 | 39.763 |
| latency_summary.ops.update.count | 3 | 9959.67 |  | 52.2643 | 9895 | 10023 |
| latency_summary.ops.update.p50_ms | 3 | 13.2516 |  | 1.45542 | 11.6785 | 15.1877 |
| latency_summary.ops.update.p95_ms | 3 | 41.5643 |  | 6.00271 | 33.7934 | 48.4092 |
| latency_summary.ops.update.p99_ms | 3 | 108.377 |  | 26.5733 | 73.2238 | 137.46 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 1.52118 |  | 0.0598929 | 1.47507 | 1.60577 |
| latency_summary.overall.p95_ms | 3 | 28.3759 |  | 2.80202 | 24.423 | 30.5927 |
| latency_summary.overall.p99_ms | 3 | 73.6019 |  | 16.6401 | 52.4291 | 93.0835 |
| load_counts_time_s | 3 | 0.00192118 |  | 0.000138159 | 0.00172639 | 0.0020318 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 37.9078 |  | 7.89803 | 26.8382 | 44.7335 |
| rss_client_peak_kb | 3 | 1.89521e+06 | 1.8GiB | 45785.4 | 1861776 | 1959948 |
| rss_peak_kb | 3 | 1.89521e+06 | 1.8GiB | 45785.4 | 1861776 | 1959948 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 109.129 |  | 13.5092 | 93.3581 | 126.353 |
| total_time_s | 3 | 465.216 |  | 57.0988 | 395.717 | 535.572 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: postgresql, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.343717 |  | 0.137075 | 0.236166 | 0.537167 |
| disk_after_oltp_bytes | 3 | 1.65255e+09 | 1.5GiB | 21501.3 | 1652516169 | 1652565321 |
| disk_after_preload_bytes | 3 | 1598424393 | 1.5GiB | 0 | 1598424393 | 1598424393 |
| disk_usage.du_bytes | 3 | 1.65309e+09 | 1.5GiB | 10217.2 | 1653080064 | 1653104640 |
| final_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| final_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| final_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| final_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| final_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| final_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| final_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| final_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| latency_summary.ops.delete.count | 3 | 5006.33 |  | 25.6948 | 4970 | 5025 |
| latency_summary.ops.delete.p50_ms | 3 | 0.670912 |  | 0.0312837 | 0.635952 | 0.711873 |
| latency_summary.ops.delete.p95_ms | 3 | 3.31413 |  | 0.394336 | 2.78392 | 3.72893 |
| latency_summary.ops.delete.p99_ms | 3 | 10.1045 |  | 2.00613 | 7.59891 | 12.5098 |
| latency_summary.ops.insert.count | 3 | 5020.67 |  | 71.2991 | 4956 | 5120 |
| latency_summary.ops.insert.p50_ms | 3 | 0.148667 |  | 0.00612802 | 0.14323 | 0.15723 |
| latency_summary.ops.insert.p95_ms | 3 | 0.342488 |  | 0.0337428 | 0.296221 | 0.375741 |
| latency_summary.ops.insert.p99_ms | 3 | 1.12457 |  | 0.218048 | 0.818042 | 1.30697 |
| latency_summary.ops.read.count | 3 | 30058 |  | 102.57 | 29913 | 30134 |
| latency_summary.ops.read.p50_ms | 3 | 0.0488134 |  | 0.0018305 | 0.047 | 0.05132 |
| latency_summary.ops.read.p95_ms | 3 | 0.135654 |  | 0.0139054 | 0.11667 | 0.14959 |
| latency_summary.ops.read.p99_ms | 3 | 3.34277 |  | 0.731147 | 2.72744 | 4.37008 |
| latency_summary.ops.update.count | 3 | 9915 |  | 20.3142 | 9893 | 9942 |
| latency_summary.ops.update.p50_ms | 3 | 0.115917 |  | 0.00383854 | 0.11256 | 0.12129 |
| latency_summary.ops.update.p95_ms | 3 | 0.323948 |  | 0.043179 | 0.264791 | 0.366641 |
| latency_summary.ops.update.p99_ms | 3 | 5.72974 |  | 1.90647 | 3.92506 | 8.36682 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 0.073467 |  | 0.00342187 | 0.07056 | 0.078271 |
| latency_summary.overall.p95_ms | 3 | 0.974163 |  | 0.0680071 | 0.880363 | 1.03946 |
| latency_summary.overall.p99_ms | 3 | 4.44982 |  | 0.774091 | 3.88274 | 5.54431 |
| load_counts_time_s | 3 | 5.20524 |  | 1.4175 | 4.15334 | 7.20906 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 60.3064 |  | 8.50657 | 54.2821 | 72.3366 |
| rss_client_peak_kb | 3 | 110055 | 107.5MiB | 385.806 | 109704 | 110592 |
| rss_peak_kb | 3 | 832675 | 813.2MiB | 3660.65 | 828984 | 837664 |
| rss_server_peak_kb | 3 | 722620 | 705.7MiB | 3276.81 | 719280 | 727072 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 3593.86 |  | 323.586 | 3212.73 | 4003.78 |
| total_time_s | 3 | 14.0254 |  | 1.25532 | 12.4882 | 15.5631 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.00686741 |  | 0.000576869 | 0.00627923 | 0.00765109 |
| disk_after_oltp_bytes | 3 | 607862456 | 579.7MiB | 58022.7 | 607784632 | 607923896 |
| disk_after_preload_bytes | 3 | 607698616 | 579.5MiB | 0 | 607698616 | 607698616 |
| disk_usage.du_bytes | 3 | 603688960 | 575.7MiB | 58022.7 | 603611136 | 603750400 |
| final_counts.Badge | 3 | 182948 |  | 50.7302 | 182896 | 183017 |
| final_counts.Comment | 3 | 195759 |  | 4.49691 | 195754 | 195765 |
| final_counts.Post | 3 | 105349 |  | 37.7448 | 105296 | 105381 |
| final_counts.PostHistory | 3 | 360367 |  | 19.7034 | 360347 | 360394 |
| final_counts.PostLink | 3 | 11004 |  | 50.7017 | 10944 | 11068 |
| final_counts.Tag | 3 | 689.333 |  | 31.6895 | 648 | 725 |
| final_counts.User | 3 | 138709 |  | 15.9234 | 138695 | 138731 |
| final_counts.Vote | 3 | 411145 |  | 51.4738 | 411083 | 411209 |
| latency_summary.ops.delete.count | 3 | 5048 |  | 78.5748 | 4937 | 5108 |
| latency_summary.ops.delete.p50_ms | 3 | 0.750876 |  | 0.0572694 | 0.686032 | 0.825323 |
| latency_summary.ops.delete.p95_ms | 3 | 4.27721 |  | 1.0949 | 3.30578 | 5.80717 |
| latency_summary.ops.delete.p99_ms | 3 | 13.4685 |  | 3.05735 | 11.2441 | 17.7917 |
| latency_summary.ops.insert.count | 3 | 4983.67 |  | 54.5303 | 4936 | 5060 |
| latency_summary.ops.insert.p50_ms | 3 | 0.03583 |  | 0.00254025 | 0.03224 | 0.03774 |
| latency_summary.ops.insert.p95_ms | 3 | 0.10059 |  | 0.0157113 | 0.084031 | 0.1217 |
| latency_summary.ops.insert.p99_ms | 3 | 0.325718 |  | 0.0462555 | 0.274781 | 0.386731 |
| latency_summary.ops.read.count | 3 | 30010.3 |  | 95.0836 | 29879 | 30101 |
| latency_summary.ops.read.p50_ms | 3 | 0.0103833 |  | 0.000534735 | 0.00965002 | 0.01091 |
| latency_summary.ops.read.p95_ms | 3 | 0.0264934 |  | 0.00399668 | 0.02234 | 0.0318901 |
| latency_summary.ops.read.p99_ms | 3 | 0.0665637 |  | 0.0124957 | 0.05509 | 0.08394 |
| latency_summary.ops.update.count | 3 | 9958 |  | 160.949 | 9731 | 10086 |
| latency_summary.ops.update.p50_ms | 3 | 0.01719 |  | 0.000797035 | 0.01614 | 0.01807 |
| latency_summary.ops.update.p95_ms | 3 | 0.0408233 |  | 0.00517499 | 0.03482 | 0.04745 |
| latency_summary.ops.update.p99_ms | 3 | 0.104753 |  | 0.0254024 | 0.08248 | 0.1403 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 0.0139867 |  | 0.000889094 | 0.0128 | 0.01494 |
| latency_summary.overall.p95_ms | 3 | 0.783346 |  | 0.0720266 | 0.694642 | 0.871062 |
| latency_summary.overall.p99_ms | 3 | 3.05254 |  | 0.42967 | 2.64731 | 3.64728 |
| load_counts_time_s | 3 | 0.00843501 |  | 0.00106818 | 0.00692582 | 0.00924683 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 216.979 |  | 59.3965 | 150.7 | 294.809 |
| rss_client_peak_kb | 3 | 95218.7 | 93.0MiB | 231.455 | 94980 | 95532 |
| rss_peak_kb | 3 | 95218.7 | 93.0MiB | 231.455 | 94980 | 95532 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 5306.07 |  | 1053.15 | 4319.26 | 6765.58 |
| total_time_s | 3 | 9.77038 |  | 1.7564 | 7.39035 | 11.5761 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.0100138 |  | 0.00169649 | 0.00789547 | 0.0120485 |
| disk_after_oltp_bytes | 3 | 7.32369e+08 | 698.4MiB | 1.4878e+06 | 730962976 | 734427488 |
| disk_after_preload_bytes | 3 | 607698616 | 579.5MiB | 0 | 607698616 | 607698616 |
| disk_usage.du_bytes | 3 | 6.03703e+08 | 575.7MiB | 66998.8 | 603623424 | 603787264 |
| final_counts.Badge | 3 | 182983 |  | 40.6147 | 182936 | 183035 |
| final_counts.Comment | 3 | 195759 |  | 5.24934 | 195752 | 195764 |
| final_counts.Post | 3 | 105381 |  | 24.7835 | 105348 | 105408 |
| final_counts.PostHistory | 3 | 360330 |  | 19.9388 | 360303 | 360350 |
| final_counts.PostLink | 3 | 11026.7 |  | 29.2385 | 11005 | 11068 |
| final_counts.Tag | 3 | 664.333 |  | 48.5066 | 617 | 731 |
| final_counts.User | 3 | 138717 |  | 24.5674 | 138698 | 138752 |
| final_counts.Vote | 3 | 411135 |  | 67.1863 | 411041 | 411194 |
| latency_summary.ops.delete.count | 3 | 5077.33 |  | 37.1872 | 5025 | 5108 |
| latency_summary.ops.delete.p50_ms | 3 | 0.93866 |  | 0.109911 | 0.798643 | 1.06712 |
| latency_summary.ops.delete.p95_ms | 3 | 8.29927 |  | 2.1038 | 5.77127 | 10.9219 |
| latency_summary.ops.delete.p99_ms | 3 | 50.1133 |  | 5.67288 | 42.108 | 54.5734 |
| latency_summary.ops.insert.count | 3 | 5038.67 |  | 76.6174 | 4936 | 5120 |
| latency_summary.ops.insert.p50_ms | 3 | 0.0544637 |  | 0.00375503 | 0.0494 | 0.058381 |
| latency_summary.ops.insert.p95_ms | 3 | 4.8982 |  | 0.455478 | 4.30044 | 5.40494 |
| latency_summary.ops.insert.p99_ms | 3 | 47.5749 |  | 8.5426 | 35.4949 | 53.7476 |
| latency_summary.ops.read.count | 3 | 29964.3 |  | 97.6297 | 29879 | 30101 |
| latency_summary.ops.read.p50_ms | 3 | 0.01311 |  | 0.000783884 | 0.01208 | 0.01398 |
| latency_summary.ops.read.p95_ms | 3 | 0.04681 |  | 0.0083713 | 0.03702 | 0.05747 |
| latency_summary.ops.read.p99_ms | 3 | 0.279637 |  | 0.0791923 | 0.21793 | 0.391431 |
| latency_summary.ops.update.count | 3 | 9919.67 |  | 145.786 | 9731 | 10086 |
| latency_summary.ops.update.p50_ms | 3 | 0.022397 |  | 0.00117731 | 0.020821 | 0.02365 |
| latency_summary.ops.update.p95_ms | 3 | 5.59883 |  | 0.66998 | 4.71633 | 6.33876 |
| latency_summary.ops.update.p99_ms | 3 | 51.4159 |  | 2.5212 | 47.8611 | 53.4328 |
| latency_summary.overall.count | 3 | 50000 |  | 0 | 50000 | 50000 |
| latency_summary.overall.p50_ms | 3 | 0.01868 |  | 0.00124296 | 0.01703 | 0.02003 |
| latency_summary.overall.p95_ms | 3 | 2.44712 |  | 0.275365 | 2.09323 | 2.76481 |
| latency_summary.overall.p99_ms | 3 | 20.5293 |  | 1.83365 | 18.5214 | 22.9544 |
| load_counts_time_s | 3 | 0.00775552 |  | 0.00149819 | 0.00618839 | 0.00977397 |
| preload_counts.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| preload_counts.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| preload_counts.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| preload_counts.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| preload_counts.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| preload_counts.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| preload_time_s | 3 | 264.722 |  | 28.766 | 234.417 | 303.378 |
| rss_client_peak_kb | 3 | 103407 | 101.0MiB | 388.451 | 103128 | 103956 |
| rss_peak_kb | 3 | 103407 | 101.0MiB | 388.451 | 103128 | 103956 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| threads | 3 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 3 | 6564.92 |  | 1429.42 | 5177.61 | 8531.92 |
| total_time_s | 3 | 7.95707 |  | 1.57516 | 5.86035 | 9.65696 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
