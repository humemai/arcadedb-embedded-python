# 07 Tables OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:09Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep07
- Total runs: 13

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 10000 |
| dataset | stackoverflow-large |
| db | arcadedb, duckdb, postgresql, sqlite |
| docker_image | python:3.12-slim |
| duckdb_version | 1.4.4 |
| heap_size | 6553m, 8g |
| mem_limit | 8g |
| run_label | sweep07_t01_r01_arcadedb_s00000, sweep07_t01_r01_duckdb_s00002, sweep07_t01_r01_postgresql_s00003, sweep07_t01_r01_sqlite_s00001, sweep07_t01_r02_arcadedb_s00004, sweep07_t01_r02_duckdb_s00006, sweep07_t01_r02_postgresql_s00007, sweep07_t01_r02_sqlite_s00005, sweep07_t01_r03_arcadedb_s00008, sweep07_t01_r03_duckdb_s00010, sweep07_t01_r03_postgresql_s00011, sweep07_t01_r03_sqlite_s00009, sweep07_t08_r01_arcadedb_s00000 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| threads | 1, 8 |
| transactions | 250000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 0.00515159 |  | 0.00443809 | 0.00155306 | 0.0114043 |
| disk_after_oltp_bytes | 3 | 1.0484e+10 | 9.8GiB | 3.96196e+08 | 10048368528 | 11006995301 |
| disk_after_preload_bytes | 3 | 10453003876 | 9.7GiB | 3.87265e+08 | 9995926251 | 10942830839 |
| disk_usage.du_bytes | 3 | 9.1969e+09 | 8.6GiB | 59950.4 | 9196818432 | 9196949504 |
| final_counts.Badge | 3 | 1657078 |  | 20.7043 | 1657060 | 1657107 |
| final_counts.Comment | 3 | 2723789 |  | 60.3379 | 2723740 | 2723874 |
| final_counts.Post | 3 | 2.73835e+06 |  | 125.996 | 2738205 | 2738513 |
| final_counts.PostHistory | 3 | 6970823 |  | 22.5536 | 6970797 | 6970852 |
| final_counts.PostLink | 3 | 204691 |  | 84.555 | 204599 | 204803 |
| final_counts.Tag | 3 | 1908 |  | 12.0277 | 1891 | 1917 |
| final_counts.User | 3 | 661600 |  | 43.6883 | 661539 | 661639 |
| final_counts.Vote | 3 | 7.69142e+06 |  | 110.774 | 7691273 | 7691538 |
| latency_summary.ops.delete.count | 3 | 25084.7 |  | 124.925 | 24908 | 25174 |
| latency_summary.ops.delete.p50_ms | 3 | 14.9126 |  | 2.46559 | 11.4333 | 16.8516 |
| latency_summary.ops.delete.p95_ms | 3 | 94.5483 |  | 10.4659 | 82.1303 | 107.732 |
| latency_summary.ops.delete.p99_ms | 3 | 223.732 |  | 8.67001 | 213.666 | 234.828 |
| latency_summary.ops.insert.count | 3 | 24995 |  | 86.1665 | 24882 | 25091 |
| latency_summary.ops.insert.p50_ms | 3 | 0.430665 |  | 0.0333094 | 0.385602 | 0.465082 |
| latency_summary.ops.insert.p95_ms | 3 | 21.9846 |  | 0.759991 | 21.0613 | 22.9227 |
| latency_summary.ops.insert.p99_ms | 3 | 67.0223 |  | 51.0794 | 26.2642 | 139.052 |
| latency_summary.ops.read.count | 3 | 150177 |  | 202.361 | 149937 | 150432 |
| latency_summary.ops.read.p50_ms | 3 | 0.250647 |  | 0.00554818 | 0.246121 | 0.258461 |
| latency_summary.ops.read.p95_ms | 3 | 2.51866 |  | 2.18799 | 0.937632 | 5.61269 |
| latency_summary.ops.read.p99_ms | 3 | 6.46779 |  | 4.51191 | 1.91631 | 12.6164 |
| latency_summary.ops.update.count | 3 | 49743.3 |  | 65.204 | 49652 | 49800 |
| latency_summary.ops.update.p50_ms | 3 | 0.433385 |  | 0.0757845 | 0.349762 | 0.533251 |
| latency_summary.ops.update.p95_ms | 3 | 4.84521 |  | 1.57253 | 3.2115 | 6.96879 |
| latency_summary.ops.update.p99_ms | 3 | 12.8779 |  | 5.74109 | 5.19537 | 18.9938 |
| latency_summary.overall.count | 3 | 250000 |  | 0 | 250000 | 250000 |
| latency_summary.overall.p50_ms | 3 | 0.369131 |  | 0.0271748 | 0.339111 | 0.404921 |
| latency_summary.overall.p95_ms | 3 | 20.1385 |  | 1.94863 | 17.4969 | 22.1392 |
| latency_summary.overall.p99_ms | 3 | 70.6591 |  | 8.61596 | 61.4426 | 82.1698 |
| load_counts_time_s | 3 | 0.247739 |  | 0.146589 | 0.131663 | 0.454529 |
| preload_counts.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| preload_counts.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| preload_counts.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| preload_counts.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| preload_counts.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| preload_counts.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| preload_counts.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| preload_counts.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| preload_time_s | 3 | 1522.66 |  | 78.7715 | 1412.48 | 1591.96 |
| rss_client_peak_kb | 3 | 7.73213e+06 | 7.4GiB | 54982.2 | 7680728 | 7808360 |
| rss_peak_kb | 3 | 7.73213e+06 | 7.4GiB | 54982.2 | 7680728 | 7808360 |
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
| throughput_ops_s | 3 | 248.572 |  | 19.1648 | 226.052 | 272.893 |
| total_time_s | 3 | 1011.71 |  | 77.5027 | 916.111 | 1105.94 |
| transactions | 3 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=1)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 1 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 1 | 0.00237846 |  | 0 | 0.00237846 | 0.00237846 |
| disk_after_oltp_bytes | 1 | 10814462827 | 10.1GiB | 0 | 10814462827 | 10814462827 |
| disk_after_preload_bytes | 1 | 10655433458 | 9.9GiB | 0 | 10655433458 | 10655433458 |
| disk_usage.du_bytes | 1 | 9196896256 | 8.6GiB | 0 | 9196896256 | 9196896256 |
| final_counts.Badge | 1 | 1657254 |  | 0 | 1657254 | 1657254 |
| final_counts.Comment | 1 | 2723739 |  | 0 | 2723739 | 2723739 |
| final_counts.Post | 1 | 2738352 |  | 0 | 2738352 | 2738352 |
| final_counts.PostHistory | 1 | 6970814 |  | 0 | 6970814 | 6970814 |
| final_counts.PostLink | 1 | 204494 |  | 0 | 204494 | 204494 |
| final_counts.Tag | 1 | 1792 |  | 0 | 1792 | 1792 |
| final_counts.User | 1 | 661680 |  | 0 | 661680 | 661680 |
| final_counts.Vote | 1 | 7691467 |  | 0 | 7691467 | 7691467 |
| latency_summary.ops.delete.count | 1 | 25174 |  | 0 | 25174 | 25174 |
| latency_summary.ops.delete.p50_ms | 1 | 32.1126 |  | 0 | 32.1126 | 32.1126 |
| latency_summary.ops.delete.p95_ms | 1 | 144.661 |  | 0 | 144.661 | 144.661 |
| latency_summary.ops.delete.p99_ms | 1 | 264.458 |  | 0 | 264.458 | 264.458 |
| latency_summary.ops.insert.count | 1 | 25012 |  | 0 | 25012 | 25012 |
| latency_summary.ops.insert.p50_ms | 1 | 5.53687 |  | 0 | 5.53687 | 5.53687 |
| latency_summary.ops.insert.p95_ms | 1 | 124.543 |  | 0 | 124.543 | 124.543 |
| latency_summary.ops.insert.p99_ms | 1 | 273.286 |  | 0 | 273.286 | 273.286 |
| latency_summary.ops.read.count | 1 | 150162 |  | 0 | 150162 | 150162 |
| latency_summary.ops.read.p50_ms | 1 | 0.606123 |  | 0 | 0.606123 | 0.606123 |
| latency_summary.ops.read.p95_ms | 1 | 54.1005 |  | 0 | 54.1005 | 54.1005 |
| latency_summary.ops.read.p99_ms | 1 | 88.1282 |  | 0 | 88.1282 | 88.1282 |
| latency_summary.ops.update.count | 1 | 49652 |  | 0 | 49652 | 49652 |
| latency_summary.ops.update.p50_ms | 1 | 5.12185 |  | 0 | 5.12185 | 5.12185 |
| latency_summary.ops.update.p95_ms | 1 | 80.2001 |  | 0 | 80.2001 | 80.2001 |
| latency_summary.ops.update.p99_ms | 1 | 154.269 |  | 0 | 154.269 | 154.269 |
| latency_summary.overall.count | 1 | 250000 |  | 0 | 250000 | 250000 |
| latency_summary.overall.p50_ms | 1 | 2.87669 |  | 0 | 2.87669 | 2.87669 |
| latency_summary.overall.p95_ms | 1 | 79.0722 |  | 0 | 79.0722 | 79.0722 |
| latency_summary.overall.p99_ms | 1 | 155.854 |  | 0 | 155.854 | 155.854 |
| load_counts_time_s | 1 | 0.0797958 |  | 0 | 0.0797958 | 0.0797958 |
| preload_counts.Badge | 1 | 1657162 |  | 0 | 1657162 | 1657162 |
| preload_counts.Comment | 1 | 2723828 |  | 0 | 2723828 | 2723828 |
| preload_counts.Post | 1 | 2738307 |  | 0 | 2738307 | 2738307 |
| preload_counts.PostHistory | 1 | 6970840 |  | 0 | 6970840 | 6970840 |
| preload_counts.PostLink | 1 | 204690 |  | 0 | 204690 | 204690 |
| preload_counts.Tag | 1 | 1925 |  | 0 | 1925 | 1925 |
| preload_counts.User | 1 | 661594 |  | 0 | 661594 | 661594 |
| preload_counts.Vote | 1 | 7691408 |  | 0 | 7691408 | 7691408 |
| preload_time_s | 1 | 1261.5 |  | 0 | 1261.5 | 1261.5 |
| rss_client_peak_kb | 1 | 5542680 | 5.3GiB | 0 | 5542680 | 5542680 |
| rss_peak_kb | 1 | 5542680 | 5.3GiB | 0 | 5542680 | 5542680 |
| rss_server_peak_kb | 1 | 0 | 0.0B | 0 | 0 | 0 |
| seed | 1 | 0 |  | 0 | 0 | 0 |
| table_schema.Badge.column_count | 1 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 1 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 1 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 1 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 1 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 1 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 1 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 1 | 6 |  | 0 | 6 | 6 |
| threads | 1 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 1 | 437.735 |  | 0 | 437.735 | 437.735 |
| total_time_s | 1 | 571.121 |  | 0 | 571.121 | 571.121 |
| transactions | 1 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: duckdb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 111.011 |  | 4.86119 | 106.081 | 117.626 |
| disk_after_oltp_bytes | 3 | 2.61531e+10 | 24.4GiB | 2.14112e+08 | 25850289053 | 26306555736 |
| disk_after_preload_bytes | 3 | 19086367312 | 17.8GiB | 1.6717e+06 | 19084008016 | 19087678032 |
| disk_usage.du_bytes | 3 | 19955433472 | 18.6GiB | 2.26709e+06 | 19952283648 | 19957526528 |
| final_counts.Badge | 3 | 1.65713e+06 |  | 94.8308 | 1657010 | 1657242 |
| final_counts.Comment | 3 | 2.72377e+06 |  | 28.1109 | 2723732 | 2723798 |
| final_counts.Post | 3 | 2738276 |  | 51.4393 | 2738204 | 2738321 |
| final_counts.PostHistory | 3 | 6.97078e+06 |  | 23.6972 | 6970751 | 6970809 |
| final_counts.PostLink | 3 | 204724 |  | 47.8911 | 204656 | 204760 |
| final_counts.Tag | 3 | 1976.67 |  | 95.9074 | 1850 | 2082 |
| final_counts.User | 3 | 661530 |  | 39.1947 | 661482 | 661578 |
| final_counts.Vote | 3 | 7691424 |  | 35.8143 | 7691386 | 7691472 |
| latency_summary.ops.delete.count | 3 | 25004 |  | 166.781 | 24782 | 25184 |
| latency_summary.ops.delete.p50_ms | 3 | 17.133 |  | 1.84555 | 14.5452 | 18.7213 |
| latency_summary.ops.delete.p95_ms | 3 | 112.783 |  | 50.8833 | 51.6628 | 176.235 |
| latency_summary.ops.delete.p99_ms | 3 | 402.202 |  | 215.633 | 97.3171 | 560.123 |
| latency_summary.ops.insert.count | 3 | 24860 |  | 58.9406 | 24785 | 24929 |
| latency_summary.ops.insert.p50_ms | 3 | 10.923 |  | 0.85011 | 9.76728 | 11.7876 |
| latency_summary.ops.insert.p95_ms | 3 | 93.4798 |  | 73.6019 | 19.3897 | 193.84 |
| latency_summary.ops.insert.p99_ms | 3 | 460.789 |  | 259.81 | 94.1151 | 664.479 |
| latency_summary.ops.read.count | 3 | 149983 |  | 207.085 | 149692 | 150159 |
| latency_summary.ops.read.p50_ms | 3 | 0.888146 |  | 0.143209 | 0.727561 | 1.07531 |
| latency_summary.ops.read.p95_ms | 3 | 48.7216 |  | 36.9159 | 7.91586 | 97.3262 |
| latency_summary.ops.read.p99_ms | 3 | 233.874 |  | 138.489 | 38.2252 | 339.443 |
| latency_summary.ops.update.count | 3 | 50153.3 |  | 205.656 | 49866 | 50336 |
| latency_summary.ops.update.p50_ms | 3 | 10.3339 |  | 0.789432 | 9.27216 | 11.1636 |
| latency_summary.ops.update.p95_ms | 3 | 106.649 |  | 75.2497 | 21.6459 | 204.6 |
| latency_summary.ops.update.p99_ms | 3 | 521.969 |  | 293.227 | 110.762 | 773.988 |
| latency_summary.overall.count | 3 | 250000 |  | 0 | 250000 | 250000 |
| latency_summary.overall.p50_ms | 3 | 4.43725 |  | 1.2153 | 2.74641 | 5.54954 |
| latency_summary.overall.p95_ms | 3 | 71.4044 |  | 42.5292 | 22.4041 | 126.109 |
| latency_summary.overall.p99_ms | 3 | 333.495 |  | 185.788 | 70.9827 | 474.302 |
| load_counts_time_s | 3 | 0.0137303 |  | 0.0006549 | 0.0131001 | 0.0146332 |
| preload_counts.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| preload_counts.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| preload_counts.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| preload_counts.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| preload_counts.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| preload_counts.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| preload_counts.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| preload_counts.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| preload_time_s | 3 | 525.637 |  | 36.1205 | 476.973 | 563.419 |
| rss_client_peak_kb | 3 | 8194216 | 7.8GiB | 122883 | 8034688 | 8333676 |
| rss_peak_kb | 3 | 8194216 | 7.8GiB | 122883 | 8034688 | 8333676 |
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
| throughput_ops_s | 3 | 59.744 |  | 35.2131 | 34.2715 | 109.538 |
| total_time_s | 3 | 5544.92 |  | 2309.04 | 2282.3 | 7294.68 |
| transactions | 3 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: postgresql, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 9.89165 |  | 1.94642 | 7.15165 | 11.49 |
| disk_after_oltp_bytes | 3 | 9.8742e+09 | 9.2GiB | 16833 | 9874184697 | 9874225657 |
| disk_after_preload_bytes | 3 | 10040449529 | 9.4GiB | 8.55474e+07 | 9923009017 | 10124335609 |
| disk_usage.du_bytes | 3 | 9.87454e+09 | 9.2GiB | 28834.1 | 9874497536 | 9874567168 |
| final_counts.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| final_counts.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| final_counts.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| final_counts.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| final_counts.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| final_counts.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| final_counts.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| final_counts.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| latency_summary.ops.delete.count | 3 | 24998.7 |  | 55.6317 | 24944 | 25075 |
| latency_summary.ops.delete.p50_ms | 3 | 7.77548 |  | 1.58073 | 5.89974 | 9.76655 |
| latency_summary.ops.delete.p95_ms | 3 | 55.9846 |  | 15.6093 | 38.114 | 76.143 |
| latency_summary.ops.delete.p99_ms | 3 | 126.381 |  | 58.6709 | 46.1903 | 184.929 |
| latency_summary.ops.insert.count | 3 | 25073.3 |  | 75.4424 | 24970 | 25148 |
| latency_summary.ops.insert.p50_ms | 3 | 0.213997 |  | 0.0188706 | 0.19013 | 0.236271 |
| latency_summary.ops.insert.p95_ms | 3 | 0.634021 |  | 0.0955922 | 0.511671 | 0.744992 |
| latency_summary.ops.insert.p99_ms | 3 | 1.2511 |  | 0.364301 | 0.737022 | 1.5376 |
| latency_summary.ops.read.count | 3 | 150013 |  | 178.191 | 149761 | 150139 |
| latency_summary.ops.read.p50_ms | 3 | 0.11282 |  | 0.0336001 | 0.07692 | 0.15773 |
| latency_summary.ops.read.p95_ms | 3 | 0.714839 |  | 0.15994 | 0.518572 | 0.910342 |
| latency_summary.ops.read.p99_ms | 3 | 8.08752 |  | 2.04891 | 6.56354 | 10.9838 |
| latency_summary.ops.update.count | 3 | 49915 |  | 134.999 | 49736 | 50062 |
| latency_summary.ops.update.p50_ms | 3 | 0.341914 |  | 0.0642941 | 0.253621 | 0.404871 |
| latency_summary.ops.update.p95_ms | 3 | 2.40941 |  | 1.11497 | 1.47727 | 3.97687 |
| latency_summary.ops.update.p99_ms | 3 | 13.9245 |  | 2.2205 | 11.8684 | 17.0081 |
| latency_summary.overall.count | 3 | 250000 |  | 0 | 250000 | 250000 |
| latency_summary.overall.p50_ms | 3 | 0.204211 |  | 0.0314079 | 0.16009 | 0.230711 |
| latency_summary.overall.p95_ms | 3 | 10.4738 |  | 0.9385 | 9.63614 | 11.7842 |
| latency_summary.overall.p99_ms | 3 | 42.1266 |  | 9.07927 | 30.7815 | 53.0065 |
| load_counts_time_s | 3 | 64.4339 |  | 3.4957 | 61.4387 | 69.3376 |
| preload_counts.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| preload_counts.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| preload_counts.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| preload_counts.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| preload_counts.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| preload_counts.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| preload_counts.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| preload_counts.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| preload_time_s | 3 | 947.542 |  | 81.921 | 854.962 | 1054.15 |
| rss_client_peak_kb | 3 | 956943 | 934.5MiB | 1263.08 | 955428 | 958520 |
| rss_peak_kb | 3 | 2.43394e+06 | 2.3GiB | 3480.06 | 2429652 | 2438176 |
| rss_server_peak_kb | 3 | 1.48074e+06 | 1.4GiB | 2789.28 | 1478224 | 1484628 |
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
| throughput_ops_s | 3 | 494.859 |  | 110.628 | 381.886 | 645.077 |
| total_time_s | 3 | 529.503 |  | 109.687 | 387.551 | 654.645 |
| transactions | 3 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 0.242445 |  | 0.0648788 | 0.17845 | 0.331384 |
| disk_after_oltp_bytes | 3 | 9.14791e+09 | 8.5GiB | 64878.5 | 9147854616 | 9147997976 |
| disk_after_preload_bytes | 3 | 9145151256 | 8.5GiB | 0 | 9145151256 | 9145151256 |
| disk_usage.du_bytes | 3 | 9.14372e+09 | 8.5GiB | 67663.3 | 9143668736 | 9143816192 |
| final_counts.Badge | 3 | 1657114 |  | 75.6086 | 1657019 | 1657204 |
| final_counts.Comment | 3 | 2.72384e+06 |  | 43.4844 | 2723782 | 2723885 |
| final_counts.Post | 3 | 2.73829e+06 |  | 9.46338 | 2738275 | 2738298 |
| final_counts.PostHistory | 3 | 6.97082e+06 |  | 78.9698 | 6970711 | 6970897 |
| final_counts.PostLink | 3 | 204672 |  | 55.8092 | 204600 | 204736 |
| final_counts.Tag | 3 | 1961.67 |  | 56.6294 | 1883 | 2014 |
| final_counts.User | 3 | 661576 |  | 47.5908 | 661509 | 661617 |
| final_counts.Vote | 3 | 7691417 |  | 49.1799 | 7691365 | 7691483 |
| latency_summary.ops.delete.count | 3 | 25014.3 |  | 108.029 | 24933 | 25167 |
| latency_summary.ops.delete.p50_ms | 3 | 9.34833 |  | 1.16307 | 8.15994 | 10.9274 |
| latency_summary.ops.delete.p95_ms | 3 | 68.9482 |  | 8.58592 | 59.6727 | 80.372 |
| latency_summary.ops.delete.p99_ms | 3 | 165.455 |  | 20.1926 | 138.85 | 187.744 |
| latency_summary.ops.insert.count | 3 | 24948.7 |  | 150.611 | 24820 | 25160 |
| latency_summary.ops.insert.p50_ms | 3 | 0.06591 |  | 0.0069514 | 0.0595 | 0.07557 |
| latency_summary.ops.insert.p95_ms | 3 | 0.204137 |  | 0.0128041 | 0.18626 | 0.215571 |
| latency_summary.ops.insert.p99_ms | 3 | 0.416738 |  | 0.0388355 | 0.366712 | 0.461381 |
| latency_summary.ops.read.count | 3 | 150150 |  | 79.1637 | 150040 | 150224 |
| latency_summary.ops.read.p50_ms | 3 | 0.022597 |  | 0.00240603 | 0.02069 | 0.025991 |
| latency_summary.ops.read.p95_ms | 3 | 1.43698 |  | 1.53746 | 0.270801 | 3.60932 |
| latency_summary.ops.read.p99_ms | 3 | 3.78956 |  | 4.65365 | 0.408301 | 10.37 |
| latency_summary.ops.update.count | 3 | 49887.3 |  | 179.975 | 49633 | 50023 |
| latency_summary.ops.update.p50_ms | 3 | 0.0382136 |  | 0.00482873 | 0.03242 | 0.044241 |
| latency_summary.ops.update.p95_ms | 3 | 1.57267 |  | 1.69216 | 0.29476 | 3.96385 |
| latency_summary.ops.update.p99_ms | 3 | 4.10569 |  | 5.00283 | 0.474941 | 11.1799 |
| latency_summary.overall.count | 3 | 250000 |  | 0 | 250000 | 250000 |
| latency_summary.overall.p50_ms | 3 | 0.0459803 |  | 0.00589185 | 0.03816 | 0.052381 |
| latency_summary.overall.p95_ms | 3 | 10.059 |  | 1.98567 | 8.28802 | 12.8319 |
| latency_summary.overall.p99_ms | 3 | 52.8007 |  | 5.29449 | 47.1064 | 59.8584 |
| load_counts_time_s | 3 | 5.78269 |  | 1.55379 | 4.5983 | 7.97779 |
| preload_counts.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| preload_counts.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| preload_counts.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| preload_counts.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| preload_counts.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| preload_counts.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| preload_counts.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| preload_counts.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| preload_time_s | 3 | 3032.31 |  | 406.932 | 2657.59 | 3597.93 |
| rss_client_peak_kb | 3 | 943204 | 921.1MiB | 744.408 | 942524 | 944240 |
| rss_peak_kb | 3 | 943204 | 921.1MiB | 744.408 | 942524 | 944240 |
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
| throughput_ops_s | 3 | 457.675 |  | 77.0608 | 354.218 | 539.068 |
| total_time_s | 3 | 563.553 |  | 103.26 | 463.764 | 705.781 |
| transactions | 3 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
