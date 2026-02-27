# 08 Tables OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:10Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep08
- Total runs: 12

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep08_r01_arcadedb_s00000, sweep08_r01_duckdb_s00002, sweep08_r01_postgresql_s00003, sweep08_r01_sqlite_s00001, sweep08_r02_arcadedb_s00004, sweep08_r02_duckdb_s00006, sweep08_r02_postgresql_s00007, sweep08_r02_sqlite_s00005, sweep08_r03_arcadedb_s00008, sweep08_r03_duckdb_s00010, sweep08_r03_postgresql_s00011, sweep08_r03_sqlite_s00009 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| disk_after_index_bytes | 3 | 9.3652e+09 | 8.7GiB | 1.80277e+07 | 9344164990 | 9388194279 |
| disk_after_load_bytes | 3 | 8.8374e+09 | 8.2GiB | 1.00918e+07 | 8823125756 | 8844759008 |
| disk_after_queries_bytes | 3 | 9.3652e+09 | 8.7GiB | 1.80277e+07 | 9344164990 | 9388194279 |
| disk_usage.du_bytes | 3 | 9.34168e+09 | 8.7GiB | 5108.61 | 9341669376 | 9341681664 |
| index.total_s | 3 | 1607.9 |  | 46.8459 | 1547.45 | 1661.61 |
| load.total_s | 3 | 903.572 |  | 50.7786 | 843.548 | 967.724 |
| queries.total_s | 3 | 2297.01 |  | 294.839 | 1880.18 | 2514.43 |
| query_cold_time_s | 3 | 22.5072 |  | 2.40865 | 19.2983 | 25.1014 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 23.0211 |  | 3.0229 | 18.7461 | 25.1684 |
| rss_client_peak_kb | 3 | 6347424 | 6.1GiB | 155948 | 6159528 | 6541376 |
| rss_peak_kb | 3 | 6347424 | 6.1GiB | 155948 | 6159528 | 6541376 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.145371 |  | 0.119634 | 0.059746 | 0.314556 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| table_counts.after_load.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_load.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_load.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_load.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_load.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_load.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_load.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_load.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.after_queries.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_queries.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_queries.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_queries.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_queries.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_queries.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_queries.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_queries.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.counts_time_s | 3 | 0.00129223 |  | 0.000277053 | 0.000949621 | 0.00162816 |
| table_counts.load_counts_time_s | 3 | 0.0570525 |  | 0.0158845 | 0.0449862 | 0.0794954 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 4809.34 |  | 383.973 | 4271.82 | 5144.86 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: duckdb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| disk_after_index_bytes | 3 | 19236709578 | 17.9GiB | 1.40355e+06 | 19234874570 | 19238282442 |
| disk_after_load_bytes | 3 | 1.83781e+10 | 17.1GiB | 1.21708e+06 | 18376877258 | 18379760842 |
| disk_after_queries_bytes | 3 | 19236709578 | 17.9GiB | 1.40355e+06 | 19234874570 | 19238282442 |
| disk_usage.du_bytes | 3 | 1.92368e+10 | 17.9GiB | 1.40381e+06 | 19234947072 | 19238354944 |
| index.total_s | 3 | 9.7188 |  | 0.89962 | 8.65827 | 10.8577 |
| load.total_s | 3 | 495.211 |  | 10.392 | 480.679 | 504.378 |
| queries.total_s | 3 | 0.384078 |  | 0.0898301 | 0.304838 | 0.509692 |
| query_cold_time_s | 3 | 0.00549792 |  | 0.00059506 | 0.00492027 | 0.00631673 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.00356105 |  | 0.000893793 | 0.00274112 | 0.00480413 |
| rss_client_peak_kb | 3 | 7.64961e+06 | 7.3GiB | 70803 | 7582628 | 7747560 |
| rss_peak_kb | 3 | 7.64961e+06 | 7.3GiB | 70803 | 7582628 | 7747560 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.065767 |  | 0.0123191 | 0.0485227 | 0.0765376 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| table_counts.after_load.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_load.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_load.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_load.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_load.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_load.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_load.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_load.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.after_queries.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_queries.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_queries.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_queries.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_queries.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_queries.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_queries.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_queries.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.counts_time_s | 3 | 0.00206923 |  | 0.000200509 | 0.00178909 | 0.00224733 |
| table_counts.load_counts_time_s | 3 | 0.0108948 |  | 0.0035742 | 0.00584483 | 0.0136092 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 505.787 |  | 10.7104 | 491.09 | 516.307 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: postgresql (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| disk_after_index_bytes | 3 | 9.12882e+09 | 8.5GiB | 7.86461e+06 | 9123199473 | 9139943921 |
| disk_after_load_bytes | 3 | 8329730545 | 7.8GiB | 57926.2 | 8329689585 | 8329812465 |
| disk_after_queries_bytes | 3 | 9.12323e+09 | 8.5GiB | 66998.8 | 9123166705 | 9123322353 |
| disk_usage.du_bytes | 3 | 9.12377e+09 | 8.5GiB | 42347.3 | 9123717120 | 9123819520 |
| index.total_s | 3 | 34.4066 |  | 5.94888 | 29.8102 | 42.8071 |
| load.total_s | 3 | 629.294 |  | 3.43886 | 624.936 | 633.342 |
| queries.total_s | 3 | 15.5173 |  | 0.38939 | 15.0697 | 16.0189 |
| query_cold_time_s | 3 | 0.178081 |  | 0.0104342 | 0.168738 | 0.192644 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.152527 |  | 0.00322737 | 0.148581 | 0.156486 |
| rss_client_peak_kb | 3 | 65162.7 | 63.6MiB | 199.475 | 64940 | 65424 |
| rss_peak_kb | 3 | 1579424 | 1.5GiB | 29980.9 | 1538696 | 1609996 |
| rss_server_peak_kb | 3 | 1.51655e+06 | 1.4GiB | 29946.4 | 1475624 | 1546440 |
| schema.total_s | 3 | 0.0261006 |  | 0.0261865 | 0.00729203 | 0.0631323 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| table_counts.after_load.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_load.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_load.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_load.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_load.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_load.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_load.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_load.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.after_queries.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_queries.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_queries.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_queries.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_queries.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_queries.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_queries.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_queries.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.counts_time_s | 3 | 1.15914 |  | 0.062155 | 1.07552 | 1.22441 |
| table_counts.load_counts_time_s | 3 | 26.4022 |  | 4.25757 | 23.3523 | 32.4231 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 712.753 |  | 7.24111 | 702.591 | 718.929 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: sqlite (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| disk_after_index_bytes | 3 | 9355259904 | 8.7GiB | 0 | 9355259904 | 9355259904 |
| disk_after_load_bytes | 3 | 8678465536 | 8.1GiB | 0 | 8678465536 | 8678465536 |
| disk_after_queries_bytes | 3 | 9355259904 | 8.7GiB | 0 | 9355259904 | 9355259904 |
| disk_usage.du_bytes | 3 | 9.35529e+09 | 8.7GiB | 1930.87 | 9355288576 | 9355292672 |
| index.total_s | 3 | 57.5192 |  | 15.2259 | 36.0635 | 69.8229 |
| load.total_s | 3 | 303.35 |  | 21.3683 | 273.132 | 318.702 |
| queries.total_s | 3 | 24.9256 |  | 3.48384 | 20.454 | 28.9529 |
| query_cold_time_s | 3 | 0.447527 |  | 0.238482 | 0.207106 | 0.772576 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.227118 |  | 0.016393 | 0.20417 | 0.241445 |
| rss_client_peak_kb | 3 | 50474.7 | 49.3MiB | 731.802 | 49440 | 51012 |
| rss_peak_kb | 3 | 50474.7 | 49.3MiB | 731.802 | 49440 | 51012 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.300302 |  | 0.0361786 | 0.249348 | 0.329793 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| table_counts.after_load.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_load.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_load.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_load.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_load.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_load.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_load.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_load.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.after_queries.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| table_counts.after_queries.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| table_counts.after_queries.Post | 3 | 2738307 |  | 0 | 2738307 | 2738307 |
| table_counts.after_queries.PostHistory | 3 | 6970840 |  | 0 | 6970840 | 6970840 |
| table_counts.after_queries.PostLink | 3 | 204690 |  | 0 | 204690 | 204690 |
| table_counts.after_queries.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| table_counts.after_queries.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| table_counts.after_queries.Vote | 3 | 7691408 |  | 0 | 7691408 | 7691408 |
| table_counts.counts_time_s | 3 | 0.208016 |  | 0.105489 | 0.0629654 | 0.310744 |
| table_counts.load_counts_time_s | 3 | 31.4906 |  | 11.4378 | 15.3184 | 39.8624 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 417.797 |  | 51.2766 | 345.282 | 454.34 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

## Aggregated Query Metrics

### arcadedb :: most_commented_posts (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 11.7003 |  | 1.73163 | 9.79453 | 13.985 |
| elapsed_mean_s | 3 | 5.96883 |  | 0.280459 | 5.696 | 6.35456 |
| elapsed_min_s | 3 | 4.20644 |  | 0.0419218 | 4.16401 | 4.26352 |
| elapsed_s | 3 | 5.55726 |  | 0.112428 | 5.44286 | 5.71009 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 13.2342 |  | 4.71112 | 9.54795 | 19.8837 |
| elapsed_mean_s | 3 | 9.16289 |  | 1.84558 | 7.4175 | 11.7162 |
| elapsed_min_s | 3 | 6.81275 |  | 0.562629 | 6.08244 | 7.45143 |
| elapsed_s | 3 | 8.10106 |  | 0.466374 | 7.44157 | 8.43859 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 21

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 259.621 |  | 72.8009 | 172.635 | 350.811 |
| elapsed_mean_s | 3 | 187.732 |  | 24.4217 | 153.221 | 206.144 |
| elapsed_min_s | 3 | 148.118 |  | 15.513 | 127.347 | 164.619 |
| elapsed_s | 3 | 185.626 |  | 22.0325 | 155.507 | 207.598 |
| row_count | 3 | 21 |  | 0 | 21 | 21 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: postlinks_by_type (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.770572 |  | 0.0353814 | 0.743707 | 0.820563 |
| elapsed_mean_s | 3 | 0.371032 |  | 0.0168814 | 0.351179 | 0.392442 |
| elapsed_min_s | 3 | 0.265307 |  | 0.0122449 | 0.253018 | 0.282018 |
| elapsed_s | 3 | 0.317903 |  | 0.0138206 | 0.298361 | 0.32798 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_answers_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 18.0076 |  | 4.97724 | 11.3385 | 23.2919 |
| elapsed_mean_s | 3 | 8.07037 |  | 1.67589 | 5.7278 | 9.55342 |
| elapsed_min_s | 3 | 4.47094 |  | 0.478843 | 3.79376 | 4.81227 |
| elapsed_s | 3 | 6.09938 |  | 1.51496 | 4.40945 | 8.08484 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_badges (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 1.74084 |  | 0.283924 | 1.51304 | 2.1411 |
| elapsed_mean_s | 3 | 1.35669 |  | 0.0295542 | 1.31632 | 1.38625 |
| elapsed_min_s | 3 | 1.09281 |  | 0.111765 | 0.945622 | 1.2163 |
| elapsed_s | 3 | 1.33216 |  | 0.0301484 | 1.2899 | 1.3582 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_questions_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 19.9135 |  | 16.8187 | 6.52775 | 43.6334 |
| elapsed_mean_s | 3 | 5.69022 |  | 2.84602 | 2.96567 | 9.6181 |
| elapsed_min_s | 3 | 2.44042 |  | 0.284982 | 2.0408 | 2.68548 |
| elapsed_s | 3 | 4.29589 |  | 1.77113 | 2.32982 | 6.6229 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_tags_by_count (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0142069 |  | 0.00185552 | 0.0126839 | 0.016819 |
| elapsed_mean_s | 3 | 0.00517477 |  | 0.000293815 | 0.0048589 | 0.0055665 |
| elapsed_min_s | 3 | 0.00237687 |  | 0.000114991 | 0.00221491 | 0.00247049 |
| elapsed_s | 3 | 0.00421866 |  | 0.000592928 | 0.00367165 | 0.00504255 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_users_by_reputation (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 1.80384 |  | 0.8125 | 1.13302 | 2.94717 |
| elapsed_mean_s | 3 | 1.09983 |  | 0.0812772 | 1.01843 | 1.21081 |
| elapsed_min_s | 3 | 0.76294 |  | 0.0522862 | 0.689033 | 0.801929 |
| elapsed_s | 3 | 1.07789 |  | 0.0339297 | 1.0351 | 1.11809 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 18

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 12.3946 |  | 0.616489 | 11.6469 | 13.1568 |
| elapsed_mean_s | 3 | 10.2394 |  | 0.170653 | 10.0127 | 10.4245 |
| elapsed_min_s | 3 | 8.72042 |  | 0.314787 | 8.30951 | 9.0742 |
| elapsed_s | 3 | 10.3024 |  | 0.118209 | 10.1382 | 10.4117 |
| row_count | 3 | 18 |  | 0 | 18 | 18 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: most_commented_posts (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0226209 |  | 0.0110536 | 0.0144114 | 0.0382464 |
| elapsed_mean_s | 3 | 0.0155368 |  | 0.00404358 | 0.0122981 | 0.0212377 |
| elapsed_min_s | 3 | 0.0116473 |  | 0.000759116 | 0.0107958 | 0.0126393 |
| elapsed_s | 3 | 0.0146188 |  | 0.00292932 | 0.0118971 | 0.0186844 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00275644 |  | 0.000828368 | 0.00204492 | 0.00391817 |
| elapsed_mean_s | 3 | 0.00149867 |  | 0.000134173 | 0.00139637 | 0.00168822 |
| elapsed_min_s | 3 | 0.00103283 |  | 6.37558e-05 | 0.000948668 | 0.00110292 |
| elapsed_s | 3 | 0.00134134 |  | 0.000123215 | 0.00120497 | 0.00150347 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 21

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00433103 |  | 0.00265111 | 0.00208926 | 0.00805449 |
| elapsed_mean_s | 3 | 0.00232559 |  | 0.000419193 | 0.00189998 | 0.00289578 |
| elapsed_min_s | 3 | 0.00175301 |  | 6.56301e-05 | 0.00166845 | 0.00182843 |
| elapsed_s | 3 | 0.00211612 |  | 0.000197281 | 0.00192595 | 0.002388 |
| row_count | 3 | 21 |  | 0 | 21 | 21 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: postlinks_by_type (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00166225 |  | 0.000336035 | 0.00134897 | 0.00212836 |
| elapsed_mean_s | 3 | 0.00103424 |  | 0.000223999 | 0.000851178 | 0.00134966 |
| elapsed_min_s | 3 | 0.000684818 |  | 3.64348e-05 | 0.000646591 | 0.000733852 |
| elapsed_s | 3 | 0.000990709 |  | 0.000271472 | 0.000718117 | 0.00136113 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_answers_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00724339 |  | 0.00388801 | 0.00411391 | 0.0127234 |
| elapsed_mean_s | 3 | 0.00324824 |  | 0.000849035 | 0.00233824 | 0.00438163 |
| elapsed_min_s | 3 | 0.00206192 |  | 0.000242798 | 0.00174546 | 0.00233555 |
| elapsed_s | 3 | 0.00268022 |  | 0.000419335 | 0.0021162 | 0.0031209 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_badges (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00738843 |  | 0.00361715 | 0.00232267 | 0.0105371 |
| elapsed_mean_s | 3 | 0.00232654 |  | 0.000407348 | 0.00179641 | 0.00278685 |
| elapsed_min_s | 3 | 0.00112621 |  | 3.22288e-05 | 0.00108075 | 0.0011518 |
| elapsed_s | 3 | 0.00192475 |  | 0.000129626 | 0.00177431 | 0.00209069 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_questions_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0148553 |  | 0.00274639 | 0.0110223 | 0.0173151 |
| elapsed_mean_s | 3 | 0.00406441 |  | 0.00104868 | 0.00275037 | 0.0053169 |
| elapsed_min_s | 3 | 0.00171336 |  | 0.000137409 | 0.0015223 | 0.00183964 |
| elapsed_s | 3 | 0.00238363 |  | 0.000543057 | 0.00179958 | 0.00310755 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_tags_by_count (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00172909 |  | 0.00129299 | 0.000739574 | 0.00355554 |
| elapsed_mean_s | 3 | 0.00066487 |  | 0.000281724 | 0.000425577 | 0.00106039 |
| elapsed_min_s | 3 | 0.000347296 |  | 2.31658e-05 | 0.000323296 | 0.000378609 |
| elapsed_s | 3 | 0.00045387 |  | 5.8053e-05 | 0.000400305 | 0.000534534 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_users_by_reputation (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0057958 |  | 0.00417152 | 0.00258136 | 0.011687 |
| elapsed_mean_s | 3 | 0.0027181 |  | 0.000625528 | 0.00220468 | 0.00359869 |
| elapsed_min_s | 3 | 0.00188708 |  | 1.90297e-05 | 0.00186563 | 0.00191188 |
| elapsed_s | 3 | 0.00240588 |  | 0.000186087 | 0.00221777 | 0.00265932 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 18

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0139535 |  | 0.000396642 | 0.0134838 | 0.0144539 |
| elapsed_mean_s | 3 | 0.00412989 |  | 0.000802124 | 0.00336595 | 0.00523808 |
| elapsed_min_s | 3 | 0.0021112 |  | 4.83577e-05 | 0.00204301 | 0.00214982 |
| elapsed_s | 3 | 0.00256443 |  | 0.000451669 | 0.00215769 | 0.00319433 |
| row_count | 3 | 18 |  | 0 | 18 | 18 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: most_commented_posts (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.497298 |  | 0.209778 | 0.324773 | 0.792574 |
| elapsed_mean_s | 3 | 0.361235 |  | 0.132855 | 0.263569 | 0.549072 |
| elapsed_min_s | 3 | 0.292464 |  | 0.0830104 | 0.227082 | 0.409594 |
| elapsed_s | 3 | 0.352679 |  | 0.127364 | 0.261731 | 0.532796 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.515952 |  | 0.00693252 | 0.506327 | 0.52238 |
| elapsed_mean_s | 3 | 0.318816 |  | 0.0644461 | 0.228293 | 0.373248 |
| elapsed_min_s | 3 | 0.247532 |  | 0.052571 | 0.175536 | 0.299591 |
| elapsed_s | 3 | 0.314365 |  | 0.0917988 | 0.185247 | 0.390626 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 21

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.642945 |  | 0.0627518 | 0.556865 | 0.704677 |
| elapsed_mean_s | 3 | 0.526273 |  | 0.0254913 | 0.495774 | 0.558168 |
| elapsed_min_s | 3 | 0.437309 |  | 0.0195831 | 0.423393 | 0.465003 |
| elapsed_s | 3 | 0.526824 |  | 0.0129851 | 0.508908 | 0.53927 |
| row_count | 3 | 21 |  | 0 | 21 | 21 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: postlinks_by_type (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0360622 |  | 0.0114075 | 0.026355 | 0.0520749 |
| elapsed_mean_s | 3 | 0.026051 |  | 0.003071 | 0.0227007 | 0.0301196 |
| elapsed_min_s | 3 | 0.018436 |  | 0.000927789 | 0.0177553 | 0.0197477 |
| elapsed_s | 3 | 0.0257956 |  | 0.000933951 | 0.0244846 | 0.0265903 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_answers_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00205032 |  | 0.00131064 | 0.000591755 | 0.00377011 |
| elapsed_mean_s | 3 | 0.00056591 |  | 0.000162945 | 0.000372481 | 0.000771093 |
| elapsed_min_s | 3 | 0.00016133 |  | 2.61713e-05 | 0.000138044 | 0.000197887 |
| elapsed_s | 3 | 0.00042216 |  | 5.58277e-05 | 0.000346184 | 0.000478745 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_badges (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.123775 |  | 0.0309789 | 0.0807383 | 0.152394 |
| elapsed_mean_s | 3 | 0.079627 |  | 0.00937779 | 0.0670315 | 0.0895205 |
| elapsed_min_s | 3 | 0.0596034 |  | 0.00383332 | 0.0556431 | 0.0647895 |
| elapsed_s | 3 | 0.0714467 |  | 0.00536846 | 0.0642653 | 0.0771706 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_questions_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00614031 |  | 0.00482924 | 0.000846624 | 0.0125241 |
| elapsed_mean_s | 3 | 0.00106563 |  | 0.000510557 | 0.000501132 | 0.00173776 |
| elapsed_min_s | 3 | 0.000215133 |  | 4.61627e-06 | 0.000208855 | 0.000219822 |
| elapsed_s | 3 | 0.000546614 |  | 3.21587e-05 | 0.000514507 | 0.000590563 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_tags_by_count (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00196369 |  | 0.000936553 | 0.000869513 | 0.00315714 |
| elapsed_mean_s | 3 | 0.000706418 |  | 0.000103171 | 0.000596952 | 0.000844693 |
| elapsed_min_s | 3 | 0.000358184 |  | 1.08811e-05 | 0.000346899 | 0.000372887 |
| elapsed_s | 3 | 0.000579755 |  | 6.91949e-05 | 0.000482321 | 0.000636339 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_users_by_reputation (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00870244 |  | 0.00383935 | 0.00327706 | 0.0116019 |
| elapsed_mean_s | 3 | 0.00130345 |  | 0.00041644 | 0.000721955 | 0.00167501 |
| elapsed_min_s | 3 | 0.000243902 |  | 5.31169e-05 | 0.000170946 | 0.000295877 |
| elapsed_s | 3 | 0.000433286 |  | 2.76985e-05 | 0.000403404 | 0.000470161 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 18

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.289445 |  | 0.0244402 | 0.255541 | 0.312218 |
| elapsed_mean_s | 3 | 0.235178 |  | 0.00724814 | 0.226079 | 0.243815 |
| elapsed_min_s | 3 | 0.199051 |  | 0.00477298 | 0.19406 | 0.205482 |
| elapsed_s | 3 | 0.233028 |  | 0.00182968 | 0.231183 | 0.235521 |
| row_count | 3 | 18 |  | 0 | 18 | 18 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: most_commented_posts (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.214743 |  | 0.0294361 | 0.17315 | 0.237043 |
| elapsed_mean_s | 3 | 0.176312 |  | 0.00848198 | 0.166471 | 0.187173 |
| elapsed_min_s | 3 | 0.165118 |  | 0.00920176 | 0.156374 | 0.177837 |
| elapsed_s | 3 | 0.170992 |  | 0.00747381 | 0.164473 | 0.181456 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0988541 |  | 0.00928965 | 0.0885246 | 0.111049 |
| elapsed_mean_s | 3 | 0.0801132 |  | 0.00686359 | 0.0737429 | 0.0896409 |
| elapsed_min_s | 3 | 0.0725478 |  | 0.00541949 | 0.0678747 | 0.0801454 |
| elapsed_s | 3 | 0.0780172 |  | 0.00659612 | 0.0724413 | 0.0872817 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 21

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.231599 |  | 0.0385489 | 0.199199 | 0.285769 |
| elapsed_mean_s | 3 | 0.202307 |  | 0.0216052 | 0.186261 | 0.232848 |
| elapsed_min_s | 3 | 0.184893 |  | 0.0150909 | 0.17208 | 0.20608 |
| elapsed_s | 3 | 0.200321 |  | 0.016703 | 0.184399 | 0.223393 |
| row_count | 3 | 21 |  | 0 | 21 | 21 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: postlinks_by_type (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00898711 |  | 0.00132776 | 0.00746608 | 0.0107012 |
| elapsed_mean_s | 3 | 0.00641221 |  | 0.000625976 | 0.00590074 | 0.0072937 |
| elapsed_min_s | 3 | 0.00550286 |  | 0.000473799 | 0.00500464 | 0.00613999 |
| elapsed_s | 3 | 0.00618879 |  | 0.000855256 | 0.00547981 | 0.00739193 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_answers_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 1.61472 |  | 0.579462 | 0.79525 | 2.02771 |
| elapsed_mean_s | 3 | 0.954957 |  | 0.123575 | 0.781291 | 1.05871 |
| elapsed_min_s | 3 | 0.812982 |  | 0.0462958 | 0.767853 | 0.876625 |
| elapsed_s | 3 | 0.884314 |  | 0.0730969 | 0.780939 | 0.936135 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_badges (samples=3)

- Hash stable: True
- Row counts: 2

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0609404 |  | 0.00125866 | 0.0594053 | 0.0624883 |
| elapsed_mean_s | 3 | 0.0545989 |  | 0.00273173 | 0.0525868 | 0.058461 |
| elapsed_min_s | 3 | 0.0517317 |  | 0.00251748 | 0.0493832 | 0.0552232 |
| elapsed_s | 3 | 0.0539018 |  | 0.00360669 | 0.0513296 | 0.0590024 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_questions_by_score (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 2.11977 |  | 2.05247 | 0.580975 | 5.0206 |
| elapsed_mean_s | 3 | 0.791738 |  | 0.240599 | 0.569803 | 1.12607 |
| elapsed_min_s | 3 | 0.572829 |  | 0.0201028 | 0.556731 | 0.601171 |
| elapsed_s | 3 | 0.66022 |  | 0.065451 | 0.568986 | 0.719367 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_tags_by_count (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00140738 |  | 0.000920165 | 0.000323534 | 0.00257301 |
| elapsed_mean_s | 3 | 0.000313894 |  | 9.8253e-05 | 0.000186253 | 0.000425267 |
| elapsed_min_s | 3 | 0.000130335 |  | 5.12954e-06 | 0.00012517 | 0.000137329 |
| elapsed_s | 3 | 0.000179688 |  | 1.93127e-05 | 0.000157833 | 0.000204802 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_users_by_reputation (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00653505 |  | 0.00447378 | 0.00281906 | 0.0128276 |
| elapsed_mean_s | 3 | 0.000774407 |  | 0.000467054 | 0.000371313 | 0.0014291 |
| elapsed_min_s | 3 | 7.68503e-05 |  | 7.79969e-06 | 6.60419e-05 | 8.41618e-05 |
| elapsed_s | 3 | 0.000109275 |  | 5.64984e-06 | 0.000103235 | 0.000116825 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 18

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.255567 |  | 0.0326544 | 0.213459 | 0.293042 |
| elapsed_mean_s | 3 | 0.224064 |  | 0.021626 | 0.206311 | 0.254508 |
| elapsed_min_s | 3 | 0.205948 |  | 0.0206649 | 0.186397 | 0.234535 |
| elapsed_s | 3 | 0.223373 |  | 0.0211048 | 0.208012 | 0.253215 |
| row_count | 3 | 18 |  | 0 | 18 | 18 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

## Cross-DB Query Result Hash Checks

| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | All Hashes |
|---|---:|---|---|---|---|
| most_commented_posts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e |
| post_type_counts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 |
| posthistory_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b |
| postlinks_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 |
| top_answers_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd |
| top_badges | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd |
| top_questions_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 |
| top_tags_by_count | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec |
| top_users_by_reputation | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 |
| votes_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e |

### most_commented_posts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e | True |
| duckdb | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e | True |
| postgresql | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e | True |
| sqlite | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e | True |

### post_type_counts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 | True |
| duckdb | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 | True |
| postgresql | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 | True |
| sqlite | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 | True |

### posthistory_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b | True |
| duckdb | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b | True |
| postgresql | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b | True |
| sqlite | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b | True |

### postlinks_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 | True |
| duckdb | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 | True |
| postgresql | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 | True |
| sqlite | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 | True |

### top_answers_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd | True |
| duckdb | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd | True |
| postgresql | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd | True |
| sqlite | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd | True |

### top_badges

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd | True |
| duckdb | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd | True |
| postgresql | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd | True |
| sqlite | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd | True |

### top_questions_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 | True |
| duckdb | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 | True |
| postgresql | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 | True |
| sqlite | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 | True |

### top_tags_by_count

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec | True |
| duckdb | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec | True |
| postgresql | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec | True |
| sqlite | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec | True |

### top_users_by_reputation

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 | True |
| duckdb | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 | True |
| postgresql | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 | True |
| sqlite | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 | True |

### votes_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e | True |
| duckdb | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e | True |
| postgresql | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e | True |
| sqlite | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e | True |
