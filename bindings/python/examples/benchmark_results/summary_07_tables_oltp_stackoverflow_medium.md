# 07 Tables OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:09Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep07
- Total runs: 18

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 5000 |
| dataset | stackoverflow-medium |
| db | arcadedb, duckdb, postgresql, sqlite |
| docker_image | python:3.12-slim |
| duckdb_version | 1.4.4 |
| heap_size | 3276m, 4g |
| mem_limit | 4g |
| run_label | sweep07_t01_r01_arcadedb_s00000, sweep07_t01_r01_duckdb_s00002, sweep07_t01_r01_postgresql_s00003, sweep07_t01_r01_sqlite_s00001, sweep07_t01_r02_arcadedb_s00004, sweep07_t01_r02_duckdb_s00006, sweep07_t01_r02_postgresql_s00007, sweep07_t01_r02_sqlite_s00005, sweep07_t01_r03_arcadedb_s00008, sweep07_t01_r03_duckdb_s00010, sweep07_t01_r03_postgresql_s00011, sweep07_t01_r03_sqlite_s00009, sweep07_t08_r01_arcadedb_s00000, sweep07_t08_r01_sqlite_s00001, sweep07_t08_r02_arcadedb_s00002, sweep07_t08_r02_sqlite_s00003, sweep07_t08_r03_arcadedb_s00004, sweep07_t08_r03_sqlite_s00005 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |
| threads | 1, 8 |
| transactions | 100000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.00229319 |  | 0.000167842 | 0.00206065 | 0.0024507 |
| disk_after_oltp_bytes | 3 | 3.17573e+09 | 3.0GiB | 8.86968e+07 | 3071159167 | 3288009873 |
| disk_after_preload_bytes | 3 | 3191046101 | 3.0GiB | 9.79309e+07 | 3064340573 | 3302823785 |
| disk_usage.du_bytes | 3 | 2793754624 | 2.6GiB | 3344.37 | 2793750528 | 2793758720 |
| final_counts.Badge | 3 | 612228 |  | 70.0619 | 612129 | 612281 |
| final_counts.Comment | 3 | 819629 |  | 19.3964 | 819613 | 819656 |
| final_counts.Post | 3 | 425748 |  | 23.6831 | 425719 | 425777 |
| final_counts.PostHistory | 3 | 1.52567e+06 |  | 18.3727 | 1525646 | 1525689 |
| final_counts.PostLink | 3 | 86997.7 |  | 27.6325 | 86969 | 87035 |
| final_counts.Tag | 3 | 1658.33 |  | 23.6126 | 1627 | 1684 |
| final_counts.User | 3 | 345774 |  | 55.5218 | 345706 | 345842 |
| final_counts.Vote | 3 | 1.74717e+06 |  | 15.6276 | 1747157 | 1747194 |
| latency_summary.ops.delete.count | 3 | 10015.3 |  | 48.7465 | 9953 | 10072 |
| latency_summary.ops.delete.p50_ms | 3 | 4.11829 |  | 0.207353 | 3.83098 | 4.31278 |
| latency_summary.ops.delete.p95_ms | 3 | 30.5926 |  | 0.672975 | 30.0973 | 31.5441 |
| latency_summary.ops.delete.p99_ms | 3 | 74.4655 |  | 3.5582 | 70.2817 | 78.9788 |
| latency_summary.ops.insert.count | 3 | 10029.7 |  | 50.6908 | 9958 | 10067 |
| latency_summary.ops.insert.p50_ms | 3 | 0.347241 |  | 0.0147826 | 0.327831 | 0.363671 |
| latency_summary.ops.insert.p95_ms | 3 | 19.0196 |  | 0.0572504 | 18.9421 | 19.0785 |
| latency_summary.ops.insert.p99_ms | 3 | 24.6485 |  | 0.369074 | 24.2847 | 25.1545 |
| latency_summary.ops.read.count | 3 | 60138.3 |  | 118.114 | 60037 | 60304 |
| latency_summary.ops.read.p50_ms | 3 | 0.07609 |  | 0.00476021 | 0.07027 | 0.08193 |
| latency_summary.ops.read.p95_ms | 3 | 1.94145 |  | 1.09537 | 1.15615 | 3.49048 |
| latency_summary.ops.read.p99_ms | 3 | 7.93047 |  | 0.801495 | 6.82839 | 8.71099 |
| latency_summary.ops.update.count | 3 | 19816.7 |  | 22.8376 | 19785 | 19838 |
| latency_summary.ops.update.p50_ms | 3 | 0.1676 |  | 0.0170467 | 0.14632 | 0.188051 |
| latency_summary.ops.update.p95_ms | 3 | 3.63725 |  | 0.698251 | 3.10044 | 4.62343 |
| latency_summary.ops.update.p99_ms | 3 | 9.36212 |  | 0.624969 | 8.52263 | 10.0213 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 0.155423 |  | 0.0204724 | 0.13119 | 0.18126 |
| latency_summary.overall.p95_ms | 3 | 8.98813 |  | 0.24517 | 8.65165 | 9.22883 |
| latency_summary.overall.p99_ms | 3 | 24.9046 |  | 0.128544 | 24.7884 | 25.0838 |
| load_counts_time_s | 3 | 0.194079 |  | 0.0583565 | 0.132027 | 0.272226 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 275.954 |  | 10.2682 | 266.051 | 290.104 |
| rss_client_peak_kb | 3 | 3.17435e+06 | 3.0GiB | 349923 | 2919456 | 3669140 |
| rss_peak_kb | 3 | 3.17435e+06 | 3.0GiB | 349923 | 2919456 | 3669140 |
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
| throughput_ops_s | 3 | 578.492 |  | 21.7855 | 557.271 | 608.446 |
| total_time_s | 3 | 173.104 |  | 6.39266 | 164.353 | 179.446 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.00798035 |  | 0.00903443 | 0.00158858 | 0.020757 |
| disk_after_oltp_bytes | 3 | 3.46616e+09 | 3.2GiB | 4.73161e+07 | 3411185383 | 3526686657 |
| disk_after_preload_bytes | 3 | 3.19643e+09 | 3.0GiB | 4.77829e+07 | 3157546427 | 3263731464 |
| disk_usage.du_bytes | 3 | 2.79374e+09 | 2.6GiB | 3861.75 | 2793738240 | 2793746432 |
| final_counts.Badge | 3 | 612300 |  | 36.3349 | 612255 | 612344 |
| final_counts.Comment | 3 | 819609 |  | 49.484 | 819558 | 819676 |
| final_counts.Post | 3 | 425774 |  | 12.2565 | 425759 | 425789 |
| final_counts.PostHistory | 3 | 1.52574e+06 |  | 10.873 | 1525723 | 1525747 |
| final_counts.PostLink | 3 | 86952.3 |  | 34.4996 | 86913 | 86997 |
| final_counts.Tag | 3 | 1544 |  | 41.8569 | 1490 | 1592 |
| final_counts.User | 3 | 345692 |  | 14.2906 | 345675 | 345710 |
| final_counts.Vote | 3 | 1.74723e+06 |  | 38.4737 | 1747177 | 1747261 |
| latency_summary.ops.delete.count | 3 | 10039.3 |  | 23.1565 | 10021 | 10072 |
| latency_summary.ops.delete.p50_ms | 3 | 8.58084 |  | 0.480642 | 8.03356 | 9.20361 |
| latency_summary.ops.delete.p95_ms | 3 | 79.5614 |  | 23.4675 | 47.3628 | 102.626 |
| latency_summary.ops.delete.p99_ms | 3 | 159.467 |  | 53.8666 | 86.2878 | 214.387 |
| latency_summary.ops.insert.count | 3 | 10015.7 |  | 70.4856 | 9916 | 10067 |
| latency_summary.ops.insert.p50_ms | 3 | 3.60155 |  | 0.170708 | 3.43674 | 3.83673 |
| latency_summary.ops.insert.p95_ms | 3 | 77.9638 |  | 20.4805 | 49.2502 | 95.6101 |
| latency_summary.ops.insert.p99_ms | 3 | 182.05 |  | 53.7883 | 106.304 | 225.98 |
| latency_summary.ops.read.count | 3 | 59990 |  | 93.8545 | 59859 | 60074 |
| latency_summary.ops.read.p50_ms | 3 | 0.318091 |  | 0.032932 | 0.273891 | 0.352901 |
| latency_summary.ops.read.p95_ms | 3 | 12.7226 |  | 0.714148 | 11.7164 | 13.301 |
| latency_summary.ops.read.p99_ms | 3 | 25.0907 |  | 3.9195 | 19.5956 | 28.4684 |
| latency_summary.ops.update.count | 3 | 19955 |  | 173.299 | 19827 | 20200 |
| latency_summary.ops.update.p50_ms | 3 | 1.49032 |  | 0.161098 | 1.28391 | 1.67705 |
| latency_summary.ops.update.p95_ms | 3 | 41.2754 |  | 10.2149 | 27.6387 | 52.2226 |
| latency_summary.ops.update.p99_ms | 3 | 100.792 |  | 27.9965 | 61.6142 | 125.335 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 0.661518 |  | 0.0999397 | 0.520391 | 0.738732 |
| latency_summary.overall.p95_ms | 3 | 29.6087 |  | 3.93372 | 24.1707 | 33.3437 |
| latency_summary.overall.p99_ms | 3 | 95.4866 |  | 27.124 | 57.7018 | 120.106 |
| load_counts_time_s | 3 | 0.0656292 |  | 0.0104507 | 0.0531764 | 0.0787492 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 222.705 |  | 8.9681 | 211.847 | 233.81 |
| rss_client_peak_kb | 3 | 2.45079e+06 | 2.3GiB | 85272.2 | 2332520 | 2530312 |
| rss_peak_kb | 3 | 2.45079e+06 | 2.3GiB | 85272.2 | 2332520 | 2530312 |
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
| throughput_ops_s | 3 | 1159.44 |  | 201.976 | 1008.54 | 1444.92 |
| total_time_s | 3 | 88.6455 |  | 13.7594 | 69.208 | 99.1528 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: duckdb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 36.5912 |  | 3.16555 | 33.5792 | 40.9655 |
| disk_after_oltp_bytes | 3 | 6511977750 | 6.1GiB | 1.23623e+07 | 6501684150 | 6529362631 |
| disk_after_preload_bytes | 3 | 5.51848e+09 | 5.1GiB | 7.11286e+06 | 5513062424 | 5528528920 |
| disk_usage.du_bytes | 3 | 5898477568 | 5.5GiB | 7.04093e+06 | 5893496832 | 5908434944 |
| final_counts.Badge | 3 | 612271 |  | 15.3261 | 612251 | 612288 |
| final_counts.Comment | 3 | 819653 |  | 5.79272 | 819645 | 819659 |
| final_counts.Post | 3 | 425677 |  | 32.5679 | 425631 | 425702 |
| final_counts.PostHistory | 3 | 1525654 |  | 54.7053 | 1525577 | 1525699 |
| final_counts.PostLink | 3 | 86922.7 |  | 64.4584 | 86859 | 87011 |
| final_counts.Tag | 3 | 1592 |  | 21.4009 | 1570 | 1621 |
| final_counts.User | 3 | 345750 |  | 52.5547 | 345707 | 345824 |
| final_counts.Vote | 3 | 1.74722e+06 |  | 22.6912 | 1747204 | 1747256 |
| latency_summary.ops.delete.count | 3 | 10067.3 |  | 80.4833 | 9997 | 10180 |
| latency_summary.ops.delete.p50_ms | 3 | 14.1742 |  | 0.167846 | 14.0554 | 14.4116 |
| latency_summary.ops.delete.p95_ms | 3 | 34.9282 |  | 3.31528 | 32.1392 | 39.5866 |
| latency_summary.ops.delete.p99_ms | 3 | 70.793 |  | 7.75393 | 63.9846 | 81.6417 |
| latency_summary.ops.insert.count | 3 | 9947.33 |  | 45.021 | 9915 | 10011 |
| latency_summary.ops.insert.p50_ms | 3 | 12.9907 |  | 0.243823 | 12.651 | 13.2119 |
| latency_summary.ops.insert.p95_ms | 3 | 32.4793 |  | 3.39764 | 29.4897 | 37.2318 |
| latency_summary.ops.insert.p99_ms | 3 | 108.52 |  | 1.77396 | 106.837 | 110.973 |
| latency_summary.ops.read.count | 3 | 59970.7 |  | 150.905 | 59859 | 60184 |
| latency_summary.ops.read.p50_ms | 3 | 0.724929 |  | 0.0368639 | 0.673302 | 0.757022 |
| latency_summary.ops.read.p95_ms | 3 | 6.11565 |  | 0.721204 | 5.43955 | 7.11504 |
| latency_summary.ops.read.p99_ms | 3 | 26.6206 |  | 1.26188 | 24.9993 | 28.077 |
| latency_summary.ops.update.count | 3 | 20014.7 |  | 160.743 | 19808 | 20200 |
| latency_summary.ops.update.p50_ms | 3 | 11.9793 |  | 0.250478 | 11.6424 | 12.2425 |
| latency_summary.ops.update.p95_ms | 3 | 31.2939 |  | 3.19196 | 28.7593 | 35.7961 |
| latency_summary.ops.update.p99_ms | 3 | 100.552 |  | 4.74708 | 95.0547 | 106.638 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 1.94475 |  | 0.150683 | 1.82956 | 2.15761 |
| latency_summary.overall.p95_ms | 3 | 22.2933 |  | 1.98884 | 20.4531 | 25.0556 |
| latency_summary.overall.p99_ms | 3 | 60.2297 |  | 3.22761 | 57.8937 | 64.7938 |
| load_counts_time_s | 3 | 0.00654117 |  | 0.00424645 | 0.00284934 | 0.0124891 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 128.594 |  | 3.07052 | 125.555 | 132.8 |
| rss_client_peak_kb | 3 | 3.72375e+06 | 3.6GiB | 104868 | 3591832 | 3848396 |
| rss_peak_kb | 3 | 3.72375e+06 | 3.6GiB | 104868 | 3591832 | 3848396 |
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
| throughput_ops_s | 3 | 117.659 |  | 1.01178 | 116.301 | 118.729 |
| total_time_s | 3 | 849.975 |  | 7.33486 | 842.254 | 859.834 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: postgresql, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 3.23471 |  | 1.18387 | 1.57736 | 4.26888 |
| disk_after_oltp_bytes | 3 | 3515734523 | 3.3GiB | 43861 | 3515677179 | 3515783675 |
| disk_after_preload_bytes | 3 | 3.63618e+09 | 3.4GiB | 1.18099e+08 | 3507550715 | 3792755195 |
| disk_usage.du_bytes | 3 | 3.51625e+09 | 3.3GiB | 69618.6 | 3516157952 | 3516321792 |
| final_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| final_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| final_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| final_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| final_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| final_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| final_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| final_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| latency_summary.ops.delete.count | 3 | 9896 |  | 105.113 | 9763 | 10020 |
| latency_summary.ops.delete.p50_ms | 3 | 2.35986 |  | 0.0786907 | 2.28657 | 2.46903 |
| latency_summary.ops.delete.p95_ms | 3 | 15.3532 |  | 1.5146 | 14.0856 | 17.4823 |
| latency_summary.ops.delete.p99_ms | 3 | 41.5814 |  | 2.25279 | 39.7787 | 44.7577 |
| latency_summary.ops.insert.count | 3 | 10009 |  | 95.9618 | 9893 | 10128 |
| latency_summary.ops.insert.p50_ms | 3 | 0.180827 |  | 0.00723528 | 0.173121 | 0.19051 |
| latency_summary.ops.insert.p95_ms | 3 | 0.540951 |  | 0.0424014 | 0.495821 | 0.597711 |
| latency_summary.ops.insert.p99_ms | 3 | 1.88661 |  | 0.364338 | 1.62279 | 2.40182 |
| latency_summary.ops.read.count | 3 | 60171.3 |  | 36.5726 | 60134 | 60221 |
| latency_summary.ops.read.p50_ms | 3 | 0.0601867 |  | 0.00166358 | 0.05862 | 0.06249 |
| latency_summary.ops.read.p95_ms | 3 | 0.569985 |  | 0.0566647 | 0.505911 | 0.643702 |
| latency_summary.ops.read.p99_ms | 3 | 7.29282 |  | 0.477391 | 6.81999 | 7.94658 |
| latency_summary.ops.update.count | 3 | 19923.7 |  | 44.7238 | 19866 | 19975 |
| latency_summary.ops.update.p50_ms | 3 | 0.144027 |  | 0.00439842 | 0.139791 | 0.15009 |
| latency_summary.ops.update.p95_ms | 3 | 3.38516 |  | 0.181358 | 3.13354 | 3.55401 |
| latency_summary.ops.update.p99_ms | 3 | 11.8669 |  | 1.18118 | 10.3162 | 13.18 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 0.0976003 |  | 0.00340635 | 0.09469 | 0.10238 |
| latency_summary.overall.p95_ms | 3 | 4.52729 |  | 0.18277 | 4.34635 | 4.77761 |
| latency_summary.overall.p99_ms | 3 | 13.0909 |  | 0.929527 | 11.9408 | 14.2173 |
| load_counts_time_s | 3 | 18.0803 |  | 2.69818 | 14.3129 | 20.4888 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 221.22 |  | 14.0999 | 201.721 | 234.581 |
| rss_client_peak_kb | 3 | 279452 | 272.9MiB | 795.192 | 278568 | 280496 |
| rss_peak_kb | 3 | 1.56027e+06 | 1.5GiB | 34325.2 | 1522576 | 1605608 |
| rss_server_peak_kb | 3 | 1280908 | 1.2GiB | 33644.6 | 1244008 | 1325372 |
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
| throughput_ops_s | 3 | 1169.09 |  | 59.7506 | 1086.23 | 1224.85 |
| total_time_s | 3 | 85.7675 |  | 4.52175 | 81.6425 | 92.0618 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.0564168 |  | 0.0455556 | 0.0230112 | 0.120827 |
| disk_after_oltp_bytes | 3 | 2.83461e+09 | 2.6GiB | 13516.1 | 2834595536 | 2834628304 |
| disk_after_preload_bytes | 3 | 2834325200 | 2.6GiB | 0 | 2834325200 | 2834325200 |
| disk_usage.du_bytes | 3 | 2.83043e+09 | 2.6GiB | 13516.1 | 2830413824 | 2830446592 |
| final_counts.Badge | 3 | 612205 |  | 25.4209 | 612172 | 612234 |
| final_counts.Comment | 3 | 819631 |  | 33.0757 | 819590 | 819671 |
| final_counts.Post | 3 | 425703 |  | 11.1156 | 425692 | 425718 |
| final_counts.PostHistory | 3 | 1.5257e+06 |  | 21.914 | 1525666 | 1525717 |
| final_counts.PostLink | 3 | 86878 |  | 89.0431 | 86767 | 86985 |
| final_counts.Tag | 3 | 1659 |  | 56.5155 | 1609 | 1738 |
| final_counts.User | 3 | 345719 |  | 3.85861 | 345714 | 345723 |
| final_counts.Vote | 3 | 1.74723e+06 |  | 55.4276 | 1747148 | 1747268 |
| latency_summary.ops.delete.count | 3 | 10061.3 |  | 65.6878 | 9993 | 10150 |
| latency_summary.ops.delete.p50_ms | 3 | 2.7653 |  | 0.116282 | 2.6169 | 2.90086 |
| latency_summary.ops.delete.p95_ms | 3 | 15.8324 |  | 0.216834 | 15.6458 | 16.1364 |
| latency_summary.ops.delete.p99_ms | 3 | 40.221 |  | 2.57195 | 36.8328 | 43.0608 |
| latency_summary.ops.insert.count | 3 | 9914.67 |  | 73.2317 | 9857 | 10018 |
| latency_summary.ops.insert.p50_ms | 3 | 0.05001 |  | 0.00485087 | 0.04654 | 0.05687 |
| latency_summary.ops.insert.p95_ms | 3 | 0.152517 |  | 0.00548336 | 0.14816 | 0.160251 |
| latency_summary.ops.insert.p99_ms | 3 | 0.375887 |  | 0.0243035 | 0.341629 | 0.395421 |
| latency_summary.ops.read.count | 3 | 60181.3 |  | 58.4028 | 60111 | 60254 |
| latency_summary.ops.read.p50_ms | 3 | 0.0137834 |  | 0.00131471 | 0.01277 | 0.01564 |
| latency_summary.ops.read.p95_ms | 3 | 0.227474 |  | 0.246193 | 0.05274 | 0.575642 |
| latency_summary.ops.read.p99_ms | 3 | 2.29292 |  | 3.08037 | 0.112771 | 6.64923 |
| latency_summary.ops.update.count | 3 | 19842.7 |  | 141.049 | 19653 | 19991 |
| latency_summary.ops.update.p50_ms | 3 | 0.0211767 |  | 0.00207522 | 0.01963 | 0.02411 |
| latency_summary.ops.update.p95_ms | 3 | 0.270407 |  | 0.278243 | 0.07322 | 0.663902 |
| latency_summary.ops.update.p99_ms | 3 | 2.50506 |  | 3.31299 | 0.161449 | 7.19033 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 0.0188167 |  | 0.00239968 | 0.01708 | 0.02221 |
| latency_summary.overall.p95_ms | 3 | 3.40296 |  | 0.880938 | 2.72163 | 4.6469 |
| latency_summary.overall.p99_ms | 3 | 12.6058 |  | 0.0771069 | 12.4981 | 12.6744 |
| load_counts_time_s | 3 | 0.22341 |  | 0.275133 | 0.026813 | 0.612501 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 762.308 |  | 32.8028 | 719.929 | 799.838 |
| rss_client_peak_kb | 3 | 267355 | 261.1MiB | 725.346 | 266344 | 268012 |
| rss_peak_kb | 3 | 267355 | 261.1MiB | 725.346 | 266344 | 268012 |
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
| throughput_ops_s | 3 | 1600.94 |  | 257.618 | 1238.38 | 1813.24 |
| total_time_s | 3 | 64.3346 |  | 11.6352 | 55.15 | 80.7506 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: sqlite, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.308103 |  | 0.403417 | 0.0207043 | 0.878615 |
| disk_after_oltp_bytes | 3 | 3.09471e+09 | 2.9GiB | 2.47029e+06 | 3091416664 | 3097362064 |
| disk_after_preload_bytes | 3 | 2834325200 | 2.6GiB | 0 | 2834325200 | 2834325200 |
| disk_usage.du_bytes | 3 | 2830442496 | 2.6GiB | 17696.7 | 2830426112 | 2830467072 |
| final_counts.Badge | 3 | 612239 |  | 68.7475 | 612142 | 612296 |
| final_counts.Comment | 3 | 819644 |  | 51.545 | 819579 | 819705 |
| final_counts.Post | 3 | 425758 |  | 64.768 | 425706 | 425849 |
| final_counts.PostHistory | 3 | 1.52577e+06 |  | 26.386 | 1525733 | 1525794 |
| final_counts.PostLink | 3 | 86935.3 |  | 23.6972 | 86902 | 86955 |
| final_counts.Tag | 3 | 1608.33 |  | 20.854 | 1582 | 1633 |
| final_counts.User | 3 | 345729 |  | 51.8738 | 345664 | 345791 |
| final_counts.Vote | 3 | 1.7472e+06 |  | 79.4411 | 1747140 | 1747310 |
| latency_summary.ops.delete.count | 3 | 9984.67 |  | 162.936 | 9763 | 10150 |
| latency_summary.ops.delete.p50_ms | 3 | 3.42306 |  | 0.781878 | 2.6714 | 4.50121 |
| latency_summary.ops.delete.p95_ms | 3 | 33.0908 |  | 8.85024 | 21.4856 | 42.953 |
| latency_summary.ops.delete.p99_ms | 3 | 153.173 |  | 31.0046 | 111.694 | 186.222 |
| latency_summary.ops.insert.count | 3 | 10001 |  | 111.286 | 9857 | 10128 |
| latency_summary.ops.insert.p50_ms | 3 | 0.0744033 |  | 0.0149313 | 0.05921 | 0.0947 |
| latency_summary.ops.insert.p95_ms | 3 | 20.0798 |  | 5.18872 | 13.9132 | 26.6075 |
| latency_summary.ops.insert.p99_ms | 3 | 103.801 |  | 20.4934 | 78.5555 | 128.751 |
| latency_summary.ops.read.count | 3 | 60141.3 |  | 28.241 | 60111 | 60179 |
| latency_summary.ops.read.p50_ms | 3 | 0.01754 |  | 0.00423614 | 0.01369 | 0.02344 |
| latency_summary.ops.read.p95_ms | 3 | 0.846809 |  | 1.09115 | 0.06007 | 2.38983 |
| latency_summary.ops.read.p99_ms | 3 | 5.08277 |  | 4.84731 | 1.29534 | 11.9248 |
| latency_summary.ops.update.count | 3 | 19873 |  | 155.701 | 19653 | 19991 |
| latency_summary.ops.update.p50_ms | 3 | 0.03289 |  | 0.0115187 | 0.02331 | 0.04909 |
| latency_summary.ops.update.p95_ms | 3 | 25.9287 |  | 6.24048 | 18.1744 | 33.4553 |
| latency_summary.ops.update.p99_ms | 3 | 124.328 |  | 26.4784 | 89.4162 | 153.512 |
| latency_summary.overall.count | 3 | 100000 |  | 0 | 100000 | 100000 |
| latency_summary.overall.p50_ms | 3 | 0.02713 |  | 0.00902025 | 0.0193201 | 0.03977 |
| latency_summary.overall.p95_ms | 3 | 10.5696 |  | 4.08231 | 6.86508 | 16.2566 |
| latency_summary.overall.p99_ms | 3 | 49.7042 |  | 15.801 | 30.2197 | 68.9214 |
| load_counts_time_s | 3 | 0.154906 |  | 0.185216 | 0.022351 | 0.416836 |
| preload_counts.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| preload_counts.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| preload_counts.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| preload_counts.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| preload_counts.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| preload_counts.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| preload_counts.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| preload_counts.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| preload_time_s | 3 | 625.099 |  | 132.262 | 521.059 | 811.736 |
| rss_client_peak_kb | 3 | 273987 | 267.6MiB | 488.986 | 273564 | 274672 |
| rss_peak_kb | 3 | 273987 | 267.6MiB | 488.986 | 273564 | 274672 |
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
| throughput_ops_s | 3 | 2260.3 |  | 524.642 | 1699.61 | 2961.47 |
| total_time_s | 3 | 46.5926 |  | 10.243 | 33.767 | 58.837 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
