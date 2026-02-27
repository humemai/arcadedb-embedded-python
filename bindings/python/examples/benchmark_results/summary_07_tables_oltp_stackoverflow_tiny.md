# 07 Tables OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:09Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep07
- Total runs: 18

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 1000 |
| dataset | stackoverflow-tiny |
| db | arcadedb, duckdb, postgresql, sqlite |
| docker_image | python:3.12-slim |
| duckdb_version | 1.4.4 |
| heap_size | 1g, 819m |
| mem_limit | 1g |
| run_label | sweep07_t01_r01_arcadedb_s00000, sweep07_t01_r01_duckdb_s00002, sweep07_t01_r01_postgresql_s00003, sweep07_t01_r01_sqlite_s00001, sweep07_t01_r02_arcadedb_s00004, sweep07_t01_r02_duckdb_s00006, sweep07_t01_r02_postgresql_s00007, sweep07_t01_r02_sqlite_s00005, sweep07_t01_r03_arcadedb_s00008, sweep07_t01_r03_duckdb_s00010, sweep07_t01_r03_postgresql_s00011, sweep07_t01_r03_sqlite_s00009, sweep07_t08_r01_arcadedb_s00000, sweep07_t08_r01_sqlite_s00001, sweep07_t08_r02_arcadedb_s00002, sweep07_t08_r02_sqlite_s00003, sweep07_t08_r03_arcadedb_s00004, sweep07_t08_r03_sqlite_s00005 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| threads | 1, 8 |
| transactions | 10000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.00156474 |  | 0.000263039 | 0.00131321 | 0.00192785 |
| disk_after_oltp_bytes | 3 | 8.67057e+07 | 82.7MiB | 6.00582e+07 | 32122774 | 170353234 |
| disk_after_preload_bytes | 3 | 88137079 | 84.1MiB | 0 | 88137079 | 88137079 |
| disk_usage.du_bytes | 3 | 3.21686e+07 | 30.7MiB | 1930.87 | 32165888 | 32169984 |
| final_counts.Badge | 3 | 10009.7 |  | 13.8884 | 9997 | 10029 |
| final_counts.Comment | 3 | 9985 |  | 12.9615 | 9973 | 10003 |
| final_counts.Post | 3 | 10021 |  | 7.11805 | 10015 | 10031 |
| final_counts.PostHistory | 3 | 9997.67 |  | 1.24722 | 9996 | 9999 |
| final_counts.PostLink | 3 | 10018.7 |  | 12.6579 | 10003 | 10034 |
| final_counts.Tag | 3 | 677.333 |  | 4.10961 | 672 | 682 |
| final_counts.User | 3 | 10003.3 |  | 13.1233 | 9985 | 10015 |
| final_counts.Vote | 3 | 10028.3 |  | 18.9268 | 10013 | 10055 |
| latency_summary.ops.delete.count | 3 | 974.667 |  | 12.6579 | 957 | 986 |
| latency_summary.ops.delete.p50_ms | 3 | 0.392325 |  | 0.0402296 | 0.351521 | 0.447062 |
| latency_summary.ops.delete.p95_ms | 3 | 24.4027 |  | 0.320775 | 23.955 | 24.6899 |
| latency_summary.ops.delete.p99_ms | 3 | 51.291 |  | 4.76812 | 44.945 | 56.4384 |
| latency_summary.ops.insert.count | 3 | 1047.67 |  | 9.84322 | 1035 | 1059 |
| latency_summary.ops.insert.p50_ms | 3 | 0.274578 |  | 0.0226682 | 0.250941 | 0.305151 |
| latency_summary.ops.insert.p95_ms | 3 | 22.5224 |  | 0.100209 | 22.4024 | 22.6477 |
| latency_summary.ops.insert.p99_ms | 3 | 44.2928 |  | 2.88961 | 41.7335 | 48.3315 |
| latency_summary.ops.read.count | 3 | 6023.67 |  | 36.8179 | 5977 | 6067 |
| latency_summary.ops.read.p50_ms | 3 | 0.0673403 |  | 0.0040314 | 0.06209 | 0.07189 |
| latency_summary.ops.read.p95_ms | 3 | 0.473082 |  | 0.0376403 | 0.433641 | 0.523762 |
| latency_summary.ops.read.p99_ms | 3 | 1.35113 |  | 0.178346 | 1.19302 | 1.60036 |
| latency_summary.ops.update.count | 3 | 1954 |  | 45.3652 | 1912 | 2017 |
| latency_summary.ops.update.p50_ms | 3 | 0.149724 |  | 0.0160161 | 0.13255 | 0.1711 |
| latency_summary.ops.update.p95_ms | 3 | 3.48408 |  | 0.159858 | 3.26995 | 3.65394 |
| latency_summary.ops.update.p99_ms | 3 | 8.18237 |  | 0.621998 | 7.44714 | 8.9682 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.10476 |  | 0.00908366 | 0.09392 | 0.11615 |
| latency_summary.overall.p95_ms | 3 | 4.12815 |  | 1.38435 | 2.8294 | 6.04621 |
| latency_summary.overall.p99_ms | 3 | 24.7089 |  | 0.0967111 | 24.6061 | 24.8385 |
| load_counts_time_s | 3 | 0.0928396 |  | 0.0395516 | 0.0421381 | 0.138648 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 6.56468 |  | 0.396284 | 6.0087 | 6.90372 |
| rss_client_peak_kb | 3 | 355395 | 347.1MiB | 36341.8 | 305320 | 390456 |
| rss_peak_kb | 3 | 355395 | 347.1MiB | 36341.8 | 305320 | 390456 |
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
| throughput_ops_s | 3 | 796 |  | 94.1453 | 665.606 | 884.502 |
| total_time_s | 3 | 12.7548 |  | 1.6249 | 11.3058 | 15.0239 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.00519753 |  | 0.00492036 | 0.00154114 | 0.0121529 |
| disk_after_oltp_bytes | 3 | 2.89915e+08 | 276.5MiB | 1.10366e+08 | 149530363 | 419183904 |
| disk_after_preload_bytes | 3 | 88137079 | 84.1MiB | 0 | 88137079 | 88137079 |
| disk_usage.du_bytes | 3 | 32190464 | 30.7MiB | 31903.3 | 32165888 | 32235520 |
| final_counts.Badge | 3 | 9978.33 |  | 8.73053 | 9966 | 9985 |
| final_counts.Comment | 3 | 10001.7 |  | 11.4407 | 9988 | 10016 |
| final_counts.Post | 3 | 10004.3 |  | 3.39935 | 10001 | 10009 |
| final_counts.PostHistory | 3 | 10006.7 |  | 21.1397 | 9987 | 10036 |
| final_counts.PostLink | 3 | 10004.3 |  | 8.21922 | 9995 | 10015 |
| final_counts.Tag | 3 | 697.333 |  | 13.8163 | 683 | 716 |
| final_counts.User | 3 | 10012 |  | 9.79796 | 10000 | 10024 |
| final_counts.Vote | 3 | 10018.7 |  | 11.3235 | 10007 | 10034 |
| latency_summary.ops.delete.count | 3 | 975.333 |  | 13.2749 | 957 | 988 |
| latency_summary.ops.delete.p50_ms | 3 | 13.0229 |  | 8.44041 | 1.10321 | 19.5317 |
| latency_summary.ops.delete.p95_ms | 3 | 75.1766 |  | 11.1265 | 64.1375 | 90.407 |
| latency_summary.ops.delete.p99_ms | 3 | 146.056 |  | 26.7658 | 114.325 | 179.795 |
| latency_summary.ops.insert.count | 3 | 1030.67 |  | 33.2499 | 984 | 1059 |
| latency_summary.ops.insert.p50_ms | 3 | 12.5316 |  | 7.9777 | 1.25107 | 18.3389 |
| latency_summary.ops.insert.p95_ms | 3 | 86.4156 |  | 15.4841 | 66.0734 | 103.607 |
| latency_summary.ops.insert.p99_ms | 3 | 170.062 |  | 36.6513 | 123.039 | 212.457 |
| latency_summary.ops.read.count | 3 | 6017 |  | 29.4392 | 5977 | 6047 |
| latency_summary.ops.read.p50_ms | 3 | 0.157774 |  | 0.0426373 | 0.10914 | 0.212961 |
| latency_summary.ops.read.p95_ms | 3 | 0.925646 |  | 0.30535 | 0.498712 | 1.19526 |
| latency_summary.ops.read.p99_ms | 3 | 7.30107 |  | 4.67189 | 2.76385 | 13.729 |
| latency_summary.ops.update.count | 3 | 1977 |  | 34.4093 | 1933 | 2017 |
| latency_summary.ops.update.p50_ms | 3 | 2.02502 |  | 1.0005 | 0.611052 | 2.77674 |
| latency_summary.ops.update.p95_ms | 3 | 50.7487 |  | 5.91734 | 44.8646 | 58.844 |
| latency_summary.ops.update.p99_ms | 3 | 127.492 |  | 29.6572 | 86.3145 | 154.982 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.280047 |  | 0.0598953 | 0.20087 | 0.345701 |
| latency_summary.overall.p95_ms | 3 | 42.6386 |  | 2.31672 | 39.8059 | 45.4807 |
| latency_summary.overall.p99_ms | 3 | 95.4437 |  | 15.2368 | 78.1624 | 115.232 |
| load_counts_time_s | 3 | 0.0454979 |  | 0.00290503 | 0.0432045 | 0.0495965 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 4.93609 |  | 0.253152 | 4.68597 | 5.28298 |
| rss_client_peak_kb | 3 | 595392 | 581.4MiB | 70143.2 | 523948 | 690712 |
| rss_peak_kb | 3 | 595392 | 581.4MiB | 70143.2 | 523948 | 690712 |
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
| throughput_ops_s | 3 | 1003.15 |  | 48.0381 | 943.517 | 1061.15 |
| total_time_s | 3 | 9.9916 |  | 0.480459 | 9.42372 | 10.5986 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: duckdb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.0238192 |  | 0.0136648 | 0.0130157 | 0.0430973 |
| disk_after_oltp_bytes | 3 | 6.17865e+07 | 58.9MiB | 447139 | 61172654 | 62224935 |
| disk_after_preload_bytes | 3 | 6.10822e+07 | 58.3MiB | 445559 | 60470572 | 61519148 |
| disk_usage.du_bytes | 3 | 9.47582e+07 | 90.4MiB | 758843 | 93880320 | 95731712 |
| final_counts.Badge | 3 | 9997.33 |  | 11.7284 | 9981 | 10008 |
| final_counts.Comment | 3 | 9994 |  | 4.32049 | 9990 | 10000 |
| final_counts.Post | 3 | 9986.67 |  | 9.84322 | 9974 | 9998 |
| final_counts.PostHistory | 3 | 10005.3 |  | 4.6428 | 9999 | 10010 |
| final_counts.PostLink | 3 | 10010.3 |  | 13.1233 | 9992 | 10022 |
| final_counts.Tag | 3 | 678 |  | 7.25718 | 668 | 685 |
| final_counts.User | 3 | 10001.7 |  | 8.17856 | 9992 | 10012 |
| final_counts.Vote | 3 | 10007.3 |  | 16.9771 | 9992 | 10031 |
| latency_summary.ops.delete.count | 3 | 981.667 |  | 18.1169 | 957 | 1000 |
| latency_summary.ops.delete.p50_ms | 3 | 10.2452 |  | 1.09727 | 9.32749 | 11.7877 |
| latency_summary.ops.delete.p95_ms | 3 | 28.2641 |  | 8.91858 | 17.6922 | 39.5072 |
| latency_summary.ops.delete.p99_ms | 3 | 49.1836 |  | 20.772 | 19.9498 | 66.301 |
| latency_summary.ops.insert.count | 3 | 994.333 |  | 13.2246 | 984 | 1013 |
| latency_summary.ops.insert.p50_ms | 3 | 11.367 |  | 1.09302 | 10.5009 | 12.9088 |
| latency_summary.ops.insert.p95_ms | 3 | 27.1721 |  | 7.26755 | 17.8881 | 35.6326 |
| latency_summary.ops.insert.p99_ms | 3 | 46.6284 |  | 17.7431 | 21.5656 | 60.2186 |
| latency_summary.ops.read.count | 3 | 6039 |  | 21.1818 | 6010 | 6060 |
| latency_summary.ops.read.p50_ms | 3 | 0.458065 |  | 0.0133322 | 0.445771 | 0.476592 |
| latency_summary.ops.read.p95_ms | 3 | 1.60187 |  | 0.158297 | 1.38442 | 1.75668 |
| latency_summary.ops.read.p99_ms | 3 | 4.01459 |  | 0.183284 | 3.79614 | 4.24464 |
| latency_summary.ops.update.count | 3 | 1985 |  | 8.64099 | 1977 | 1997 |
| latency_summary.ops.update.p50_ms | 3 | 10.2367 |  | 1.08558 | 9.29138 | 11.7569 |
| latency_summary.ops.update.p95_ms | 3 | 26.8563 |  | 6.54858 | 17.6076 | 31.8954 |
| latency_summary.ops.update.p99_ms | 3 | 54.9543 |  | 25.8871 | 19.2184 | 79.7086 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.859109 |  | 0.0770734 | 0.756892 | 0.942993 |
| latency_summary.overall.p95_ms | 3 | 18.0479 |  | 2.42051 | 15.7531 | 21.395 |
| latency_summary.overall.p99_ms | 3 | 35.5787 |  | 12.1001 | 18.5522 | 45.5722 |
| load_counts_time_s | 3 | 0.00159391 |  | 0.000180883 | 0.00139952 | 0.00183511 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 6.47289 |  | 5.93957 | 1.34875 | 14.7991 |
| rss_client_peak_kb | 3 | 473313 | 462.2MiB | 6417.53 | 464456 | 479456 |
| rss_peak_kb | 3 | 473313 | 462.2MiB | 6417.53 | 464456 | 479456 |
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
| throughput_ops_s | 3 | 182.52 |  | 24.5617 | 156.021 | 215.218 |
| total_time_s | 3 | 55.7578 |  | 7.22902 | 46.4644 | 64.0941 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: postgresql, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.0199019 |  | 0.0100067 | 0.00577855 | 0.0277367 |
| disk_after_oltp_bytes | 3 | 1.11555e+08 | 106.4MiB | 10217.2 | 111543623 | 111568199 |
| disk_after_preload_bytes | 3 | 110847303 | 105.7MiB | 0 | 110847303 | 110847303 |
| disk_usage.du_bytes | 3 | 1.11941e+08 | 106.8MiB | 22267.9 | 111923200 | 111972352 |
| final_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| final_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| final_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.ops.delete.count | 3 | 1016 |  | 15.5778 | 996 | 1034 |
| latency_summary.ops.delete.p50_ms | 3 | 0.155573 |  | 0.0355472 | 0.127 | 0.20568 |
| latency_summary.ops.delete.p95_ms | 3 | 0.610129 |  | 0.271555 | 0.297011 | 0.959253 |
| latency_summary.ops.delete.p99_ms | 3 | 1.39584 |  | 0.659054 | 0.464292 | 1.88782 |
| latency_summary.ops.insert.count | 3 | 997.333 |  | 41.8277 | 939 | 1035 |
| latency_summary.ops.insert.p50_ms | 3 | 0.137351 |  | 0.0189255 | 0.121271 | 0.16392 |
| latency_summary.ops.insert.p95_ms | 3 | 0.338974 |  | 0.115085 | 0.24042 | 0.500421 |
| latency_summary.ops.insert.p99_ms | 3 | 1.03243 |  | 0.0762551 | 0.928303 | 1.10879 |
| latency_summary.ops.read.count | 3 | 6052.67 |  | 15.107 | 6041 | 6074 |
| latency_summary.ops.read.p50_ms | 3 | 0.040947 |  | 0.00649907 | 0.035241 | 0.05004 |
| latency_summary.ops.read.p95_ms | 3 | 0.0972607 |  | 0.0263484 | 0.076661 | 0.134451 |
| latency_summary.ops.read.p99_ms | 3 | 0.228724 |  | 0.0565767 | 0.14878 | 0.271541 |
| latency_summary.ops.update.count | 3 | 1934 |  | 20.2155 | 1906 | 1953 |
| latency_summary.ops.update.p50_ms | 3 | 0.10193 |  | 0.0145964 | 0.08871 | 0.12227 |
| latency_summary.ops.update.p95_ms | 3 | 0.271408 |  | 0.0693165 | 0.198871 | 0.364781 |
| latency_summary.ops.update.p99_ms | 3 | 1.34165 |  | 1.02952 | 0.514311 | 2.79287 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.0589004 |  | 0.0127684 | 0.04808 | 0.07683 |
| latency_summary.overall.p95_ms | 3 | 0.250807 |  | 0.0900965 | 0.186481 | 0.378221 |
| latency_summary.overall.p99_ms | 3 | 0.640972 |  | 0.161924 | 0.497441 | 0.867263 |
| load_counts_time_s | 3 | 0.00793362 |  | 0.00068142 | 0.0071559 | 0.00881529 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 8.40331 |  | 8.53449 | 2.16534 | 20.4706 |
| rss_client_peak_kb | 3 | 52202.7 | 51.0MiB | 323.421 | 51868 | 52640 |
| rss_peak_kb | 3 | 258815 | 252.7MiB | 434.098 | 258244 | 259296 |
| rss_server_peak_kb | 3 | 206612 | 201.8MiB | 177.479 | 206376 | 206804 |
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
| throughput_ops_s | 3 | 9723.07 |  | 1478.44 | 7682.26 | 11137.1 |
| total_time_s | 3 | 1.05527 |  | 0.176473 | 0.897896 | 1.3017 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.000854095 |  | 0.000132566 | 0.000709057 | 0.00102949 |
| disk_after_oltp_bytes | 3 | 3.54491e+07 | 33.8MiB | 15080.6 | 35430000 | 35466864 |
| disk_after_preload_bytes | 3 | 35270256 | 33.6MiB | 0 | 35270256 | 35270256 |
| disk_usage.du_bytes | 3 | 3.12907e+07 | 29.8MiB | 18419.4 | 31268864 | 31313920 |
| final_counts.Badge | 3 | 9992.67 |  | 6.12826 | 9984 | 9997 |
| final_counts.Comment | 3 | 10005 |  | 3.74166 | 10000 | 10009 |
| final_counts.Post | 3 | 9987 |  | 9.62635 | 9974 | 9997 |
| final_counts.PostHistory | 3 | 9994.67 |  | 9.53357 | 9982 | 10005 |
| final_counts.PostLink | 3 | 9995.67 |  | 6.59966 | 9991 | 10005 |
| final_counts.Tag | 3 | 656 |  | 15.5134 | 637 | 675 |
| final_counts.User | 3 | 9982.67 |  | 18.3727 | 9960 | 10005 |
| final_counts.Vote | 3 | 10012.3 |  | 13.1993 | 9995 | 10027 |
| latency_summary.ops.delete.count | 3 | 1013 |  | 27.5802 | 974 | 1033 |
| latency_summary.ops.delete.p50_ms | 3 | 0.057627 |  | 0.00117306 | 0.056021 | 0.05879 |
| latency_summary.ops.delete.p95_ms | 3 | 0.282551 |  | 0.192869 | 0.142251 | 0.555272 |
| latency_summary.ops.delete.p99_ms | 3 | 0.872463 |  | 0.877336 | 0.23945 | 2.11312 |
| latency_summary.ops.insert.count | 3 | 971 |  | 11.5758 | 960 | 987 |
| latency_summary.ops.insert.p50_ms | 3 | 0.0250367 |  | 0.000464491 | 0.0246 | 0.02568 |
| latency_summary.ops.insert.p95_ms | 3 | 0.0789967 |  | 0.0432602 | 0.04721 | 0.14016 |
| latency_summary.ops.insert.p99_ms | 3 | 0.192388 |  | 0.162793 | 0.073161 | 0.422562 |
| latency_summary.ops.read.count | 3 | 6022.67 |  | 41.2499 | 5973 | 6074 |
| latency_summary.ops.read.p50_ms | 3 | 0.00720031 |  | 0.000184482 | 0.006961 | 0.00740995 |
| latency_summary.ops.read.p95_ms | 3 | 0.0183833 |  | 0.00774296 | 0.01267 | 0.02933 |
| latency_summary.ops.read.p99_ms | 3 | 0.0387 |  | 0.0264812 | 0.0199 | 0.07615 |
| latency_summary.ops.update.count | 3 | 1993.33 |  | 31.4572 | 1959 | 2035 |
| latency_summary.ops.update.p50_ms | 3 | 0.01321 |  | 0.000219233 | 0.01297 | 0.0135 |
| latency_summary.ops.update.p95_ms | 3 | 0.0346267 |  | 0.0185159 | 0.02125 | 0.06081 |
| latency_summary.ops.update.p99_ms | 3 | 0.0663233 |  | 0.0413197 | 0.03585 | 0.12474 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.00957667 |  | 0.000467782 | 0.00904 | 0.01018 |
| latency_summary.overall.p95_ms | 3 | 0.067664 |  | 0.00968972 | 0.05882 | 0.081151 |
| latency_summary.overall.p99_ms | 3 | 0.174258 |  | 0.0754151 | 0.115661 | 0.280731 |
| load_counts_time_s | 3 | 0.000559092 |  | 6.09466e-05 | 0.000481129 | 0.000629902 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 21.3873 |  | 1.91635 | 18.8944 | 23.5545 |
| rss_client_peak_kb | 3 | 37889.3 | 37.0MiB | 91.9323 | 37784 | 38008 |
| rss_peak_kb | 3 | 37889.3 | 37.0MiB | 91.9323 | 37784 | 38008 |
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
| throughput_ops_s | 3 | 21538.9 |  | 3595.78 | 16964.8 | 25750.1 |
| total_time_s | 3 | 0.478129 |  | 0.0835041 | 0.388348 | 0.589457 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.00239142 |  | 0.00250566 | 0.000616312 | 0.00593495 |
| disk_after_oltp_bytes | 3 | 58509808 | 55.8MiB | 473485 | 57912216 | 59070224 |
| disk_after_preload_bytes | 3 | 35270256 | 33.6MiB | 0 | 35270256 | 35270256 |
| disk_usage.du_bytes | 3 | 31309824 | 29.9MiB | 23170.5 | 31293440 | 31342592 |
| final_counts.Badge | 3 | 9996 |  | 9.4163 | 9985 | 10008 |
| final_counts.Comment | 3 | 9983 |  | 6.16441 | 9976 | 9991 |
| final_counts.Post | 3 | 9992 |  | 3.74166 | 9988 | 9997 |
| final_counts.PostHistory | 3 | 9988.33 |  | 17.2498 | 9966 | 10008 |
| final_counts.PostLink | 3 | 9994.33 |  | 5.18545 | 9987 | 9998 |
| final_counts.Tag | 3 | 674.667 |  | 6.12826 | 667 | 682 |
| final_counts.User | 3 | 9998 |  | 15.5134 | 9977 | 10014 |
| final_counts.Vote | 3 | 10008 |  | 11.5181 | 9993 | 10021 |
| latency_summary.ops.delete.count | 3 | 1027.67 |  | 6.84755 | 1018 | 1033 |
| latency_summary.ops.delete.p50_ms | 3 | 0.0734 |  | 0.00416314 | 0.06755 | 0.0769 |
| latency_summary.ops.delete.p95_ms | 3 | 0.891353 |  | 0.492879 | 0.195501 | 1.27445 |
| latency_summary.ops.delete.p99_ms | 3 | 8.32118 |  | 0.066535 | 8.25954 | 8.41357 |
| latency_summary.ops.insert.count | 3 | 994 |  | 31.0161 | 960 | 1035 |
| latency_summary.ops.insert.p50_ms | 3 | 0.0378637 |  | 0.0027209 | 0.034051 | 0.04022 |
| latency_summary.ops.insert.p95_ms | 3 | 0.813756 |  | 0.524427 | 0.07223 | 1.19636 |
| latency_summary.ops.insert.p99_ms | 3 | 9.99768 |  | 6.258 | 3.18048 | 18.2938 |
| latency_summary.ops.read.count | 3 | 6011.67 |  | 28.5346 | 5973 | 6041 |
| latency_summary.ops.read.p50_ms | 3 | 0.00934002 |  | 0.000197983 | 0.00912003 | 0.00960001 |
| latency_summary.ops.read.p95_ms | 3 | 0.0245333 |  | 0.00354834 | 0.01987 | 0.02847 |
| latency_summary.ops.read.p99_ms | 3 | 0.0609233 |  | 0.0122127 | 0.04504 | 0.07474 |
| latency_summary.ops.update.count | 3 | 1966.67 |  | 52.9423 | 1906 | 2035 |
| latency_summary.ops.update.p50_ms | 3 | 0.0174933 |  | 0.000496424 | 0.01707 | 0.01819 |
| latency_summary.ops.update.p95_ms | 3 | 0.756185 |  | 0.50217 | 0.04615 | 1.12341 |
| latency_summary.ops.update.p99_ms | 3 | 11.6021 |  | 4.72354 | 8.24003 | 18.2822 |
| latency_summary.overall.count | 3 | 10000 |  | 0 | 10000 | 10000 |
| latency_summary.overall.p50_ms | 3 | 0.0134433 |  | 0.000677072 | 0.01257 | 0.01422 |
| latency_summary.overall.p95_ms | 3 | 0.114664 |  | 0.0249153 | 0.08077 | 0.139951 |
| latency_summary.overall.p99_ms | 3 | 2.53105 |  | 0.960859 | 1.17221 | 3.21722 |
| load_counts_time_s | 3 | 0.000494162 |  | 5.14323e-05 | 0.000442505 | 0.000564337 |
| preload_counts.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Tag | 3 | 668 |  | 0 | 668 | 668 |
| preload_counts.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_counts.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| preload_time_s | 3 | 14.8007 |  | 1.6763 | 12.6631 | 16.7571 |
| rss_client_peak_kb | 3 | 45817.3 | 44.7MiB | 3179.11 | 43324 | 50304 |
| rss_peak_kb | 3 | 45817.3 | 44.7MiB | 3179.11 | 43324 | 50304 |
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
| throughput_ops_s | 3 | 27188.5 |  | 6738.74 | 18513.4 | 34942.6 |
| total_time_s | 3 | 0.394028 |  | 0.107155 | 0.286184 | 0.540149 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
