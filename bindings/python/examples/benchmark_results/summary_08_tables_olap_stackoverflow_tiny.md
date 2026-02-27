# 08 Tables OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:10Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep08
- Total runs: 12

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep08_r01_arcadedb_s00000, sweep08_r01_duckdb_s00002, sweep08_r01_postgresql_s00003, sweep08_r01_sqlite_s00001, sweep08_r02_arcadedb_s00004, sweep08_r02_duckdb_s00006, sweep08_r02_postgresql_s00007, sweep08_r02_sqlite_s00005, sweep08_r03_arcadedb_s00008, sweep08_r03_duckdb_s00010, sweep08_r03_postgresql_s00011, sweep08_r03_sqlite_s00009 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| disk_after_index_bytes | 3 | 81791573 | 78.0MiB | 0 | 81791573 | 81791573 |
| disk_after_load_bytes | 3 | 67876805 | 64.7MiB | 0 | 67876805 | 67876805 |
| disk_after_queries_bytes | 3 | 81791573 | 78.0MiB | 0 | 81791573 | 81791573 |
| disk_usage.du_bytes | 3 | 3.50071e+07 | 33.4MiB | 1930.87 | 35004416 | 35008512 |
| index.total_s | 3 | 1.49752 |  | 0.0137473 | 1.47831 | 1.50973 |
| load.total_s | 3 | 3.73355 |  | 0.0476281 | 3.66903 | 3.78257 |
| queries.total_s | 3 | 1.61116 |  | 0.136568 | 1.41842 | 1.71817 |
| query_cold_time_s | 3 | 0.0397992 |  | 0.00322872 | 0.0353159 | 0.0427905 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.0133969 |  | 0.00117352 | 0.0117546 | 0.014425 |
| rss_client_peak_kb | 3 | 243103 | 237.4MiB | 8615.76 | 234112 | 254720 |
| rss_peak_kb | 3 | 243103 | 237.4MiB | 8615.76 | 234112 | 254720 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.192754 |  | 0.166854 | 0.0739446 | 0.428718 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| table_counts.after_load.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.counts_time_s | 3 | 0.000588179 |  | 2.813e-05 | 0.000551224 | 0.000619411 |
| table_counts.load_counts_time_s | 3 | 0.0386937 |  | 0.00281354 | 0.034883 | 0.0415905 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 7.54388 |  | 0.071465 | 7.44313 | 7.60117 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: duckdb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| disk_after_index_bytes | 3 | 61774129 | 58.9MiB | 370728 | 61249841 | 62036273 |
| disk_after_load_bytes | 3 | 58762824 | 56.0MiB | 370728 | 58238536 | 59024968 |
| disk_after_queries_bytes | 3 | 61774129 | 58.9MiB | 370728 | 61249841 | 62036273 |
| disk_usage.du_bytes | 3 | 6.95146e+07 | 66.3MiB | 371727 | 68988928 | 69783552 |
| index.total_s | 3 | 0.328296 |  | 0.241138 | 0.100508 | 0.661975 |
| load.total_s | 3 | 12.4102 |  | 3.6944 | 7.57737 | 16.5458 |
| queries.total_s | 3 | 0.0544631 |  | 0.00406572 | 0.050112 | 0.0598938 |
| query_cold_time_s | 3 | 0.00068783 |  | 0.000160811 | 0.000535154 | 0.000910139 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.000491953 |  | 2.61357e-05 | 0.000462474 | 0.000526002 |
| rss_client_peak_kb | 3 | 163205 | 159.4MiB | 2044.5 | 160572 | 165556 |
| rss_peak_kb | 3 | 163205 | 159.4MiB | 2044.5 | 160572 | 165556 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.0646468 |  | 0.0297296 | 0.0226293 | 0.086947 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| table_counts.after_load.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.counts_time_s | 3 | 0.00118995 |  | 5.86697e-05 | 0.00110698 | 0.00123191 |
| table_counts.load_counts_time_s | 3 | 0.00196671 |  | 0.000259057 | 0.00165772 | 0.00229168 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 13.4211 |  | 2.93771 | 9.71596 | 16.9013 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: postgresql (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| disk_after_index_bytes | 3 | 109569343 | 104.5MiB | 0 | 109569343 | 109569343 |
| disk_after_load_bytes | 3 | 106579263 | 101.6MiB | 0 | 106579263 | 106579263 |
| disk_after_queries_bytes | 3 | 109569343 | 104.5MiB | 0 | 109569343 | 109569343 |
| disk_usage.du_bytes | 3 | 1.09968e+08 | 104.9MiB | 16833 | 109948928 | 109989888 |
| index.total_s | 3 | 0.685827 |  | 0.451415 | 0.0487695 | 1.04014 |
| load.total_s | 3 | 2.47766 |  | 0.707337 | 1.5618 | 3.284 |
| queries.total_s | 3 | 0.11115 |  | 0.00159322 | 0.109317 | 0.113201 |
| query_cold_time_s | 3 | 0.00142072 |  | 0.000100443 | 0.00129838 | 0.0015444 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.00104467 |  | 2.32041e-05 | 0.00101249 | 0.00106634 |
| rss_client_peak_kb | 3 | 50957.3 | 49.8MiB | 45.2941 | 50896 | 51004 |
| rss_peak_kb | 3 | 208563 | 203.7MiB | 6549.35 | 202460 | 217648 |
| rss_server_peak_kb | 3 | 157605 | 153.9MiB | 6589.39 | 151488 | 166752 |
| schema.total_s | 3 | 0.00953046 |  | 0.00215388 | 0.00765729 | 0.0125473 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| table_counts.after_load.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.counts_time_s | 3 | 0.00495768 |  | 0.000470671 | 0.00459504 | 0.00562239 |
| table_counts.load_counts_time_s | 3 | 0.00663837 |  | 0.000484088 | 0.00603008 | 0.00721455 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 7.51824 |  | 1.44285 | 5.68841 | 9.21515 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: sqlite (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| disk_after_index_bytes | 3 | 32288768 | 30.8MiB | 0 | 32288768 | 32288768 |
| disk_after_load_bytes | 3 | 30228480 | 28.8MiB | 0 | 30228480 | 30228480 |
| disk_after_queries_bytes | 3 | 32288768 | 30.8MiB | 0 | 32288768 | 32288768 |
| disk_usage.du_bytes | 3 | 32321536 | 30.8MiB | 0 | 32321536 | 32321536 |
| index.total_s | 3 | 1.05311 |  | 0.905993 | 0.244191 | 2.31808 |
| load.total_s | 3 | 5.21289 |  | 4.67188 | 1.32744 | 11.7835 |
| queries.total_s | 3 | 0.0949097 |  | 0.00316866 | 0.0904286 | 0.0971508 |
| query_cold_time_s | 3 | 0.000996407 |  | 3.61591e-05 | 0.000947905 | 0.00103469 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.000915794 |  | 2.94929e-05 | 0.000874085 | 0.000936752 |
| rss_client_peak_kb | 3 | 36906.7 | 36.0MiB | 234.181 | 36576 | 37088 |
| rss_peak_kb | 3 | 36906.7 | 36.0MiB | 234.181 | 36576 | 37088 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.18731 |  | 0.0825039 | 0.0713522 | 0.256502 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| table_counts.after_load.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_load.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Post | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostHistory | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.PostLink | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.after_queries.Vote | 3 | 10000 |  | 0 | 10000 | 10000 |
| table_counts.counts_time_s | 3 | 0.000305971 |  | 4.97198e-06 | 0.000299692 | 0.000311852 |
| table_counts.load_counts_time_s | 3 | 0.00811855 |  | 0.000582233 | 0.00730467 | 0.00863361 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 6.55771 |  | 5.6354 | 1.7433 | 14.4652 |

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
| elapsed_max_s | 3 | 0.0431979 |  | 0.00307796 | 0.0404508 | 0.0474956 |
| elapsed_mean_s | 3 | 0.0163147 |  | 0.00102983 | 0.0153063 | 0.0177289 |
| elapsed_min_s | 3 | 0.00880162 |  | 0.000597992 | 0.00832844 | 0.00964522 |
| elapsed_s | 3 | 0.013119 |  | 0.00190258 | 0.0107319 | 0.0153878 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 5

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0505064 |  | 0.0114355 | 0.0390298 | 0.0661125 |
| elapsed_mean_s | 3 | 0.0245686 |  | 0.0024896 | 0.0217713 | 0.0278189 |
| elapsed_min_s | 3 | 0.015957 |  | 0.000900289 | 0.0147827 | 0.0169702 |
| elapsed_s | 3 | 0.0190689 |  | 0.0016972 | 0.0169511 | 0.021106 |
| row_count | 3 | 5 |  | 0 | 5 | 5 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 22

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0781328 |  | 0.00311336 | 0.0738151 | 0.0810385 |
| elapsed_mean_s | 3 | 0.0252646 |  | 0.00169085 | 0.0232049 | 0.0273464 |
| elapsed_min_s | 3 | 0.0138902 |  | 0.000586402 | 0.0134585 | 0.0147192 |
| elapsed_s | 3 | 0.0169714 |  | 0.000308637 | 0.0167167 | 0.0174057 |
| row_count | 3 | 22 |  | 0 | 22 | 22 |

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
| elapsed_max_s | 3 | 0.0491945 |  | 0.0171952 | 0.0322049 | 0.0727568 |
| elapsed_mean_s | 3 | 0.0183762 |  | 0.00276583 | 0.0144648 | 0.0203566 |
| elapsed_min_s | 3 | 0.0105831 |  | 6.5172e-05 | 0.0104942 | 0.0106487 |
| elapsed_s | 3 | 0.0131737 |  | 0.00100771 | 0.0124021 | 0.0145972 |
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
| elapsed_max_s | 3 | 0.0323915 |  | 0.0151369 | 0.0173652 | 0.0531087 |
| elapsed_mean_s | 3 | 0.0155385 |  | 0.0029008 | 0.0122854 | 0.0193295 |
| elapsed_min_s | 3 | 0.00953213 |  | 0.000524058 | 0.00891161 | 0.0101933 |
| elapsed_s | 3 | 0.0132673 |  | 0.000921644 | 0.0120053 | 0.0141807 |
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
| elapsed_max_s | 3 | 0.0252474 |  | 0.00429415 | 0.0198183 | 0.0303185 |
| elapsed_mean_s | 3 | 0.0105177 |  | 0.00063731 | 0.00962985 | 0.0110959 |
| elapsed_min_s | 3 | 0.00611933 |  | 0.000187128 | 0.00591826 | 0.00636888 |
| elapsed_s | 3 | 0.00828989 |  | 0.000780375 | 0.00723863 | 0.0091064 |
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
| elapsed_max_s | 3 | 0.0399176 |  | 0.0166627 | 0.0170925 | 0.0564022 |
| elapsed_mean_s | 3 | 0.0127191 |  | 0.00163423 | 0.0105344 | 0.0144645 |
| elapsed_min_s | 3 | 0.00640623 |  | 0.000257487 | 0.00604439 | 0.00662255 |
| elapsed_s | 3 | 0.0096391 |  | 0.000708393 | 0.00877976 | 0.0105147 |
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
| elapsed_max_s | 3 | 0.00800975 |  | 0.0036542 | 0.00500488 | 0.0131533 |
| elapsed_mean_s | 3 | 0.00253083 |  | 0.0011096 | 0.00165961 | 0.00409672 |
| elapsed_min_s | 3 | 0.000979582 |  | 4.76349e-05 | 0.000918865 | 0.00103521 |
| elapsed_s | 3 | 0.001285 |  | 0.000134645 | 0.00111175 | 0.00144005 |
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
| elapsed_max_s | 3 | 0.0390106 |  | 0.00852644 | 0.0269592 | 0.0453866 |
| elapsed_mean_s | 3 | 0.0169009 |  | 0.00177387 | 0.0145767 | 0.0188806 |
| elapsed_min_s | 3 | 0.0107025 |  | 0.000223256 | 0.0103881 | 0.0108855 |
| elapsed_s | 3 | 0.014741 |  | 0.0012859 | 0.0134826 | 0.0165071 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0434743 |  | 0.011012 | 0.0297234 | 0.0566807 |
| elapsed_mean_s | 3 | 0.0176405 |  | 0.00237122 | 0.0150502 | 0.02078 |
| elapsed_min_s | 3 | 0.010282 |  | 0.000391869 | 0.00984645 | 0.0107965 |
| elapsed_s | 3 | 0.0150923 |  | 0.00187067 | 0.0132816 | 0.017668 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.000968456 |  | 0.000246853 | 0.000638962 | 0.0012331 |
| elapsed_mean_s | 3 | 0.000645828 |  | 8.92382e-05 | 0.000534463 | 0.000752926 |
| elapsed_min_s | 3 | 0.000486612 |  | 1.58376e-05 | 0.000472784 | 0.000508785 |
| elapsed_s | 3 | 0.000617822 |  | 9.55323e-05 | 0.000505924 | 0.000739336 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 5

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000392516 |  | 1.43175e-05 | 0.000377417 | 0.000411749 |
| elapsed_mean_s | 3 | 0.00033346 |  | 1.50001e-05 | 0.00032196 | 0.000354648 |
| elapsed_min_s | 3 | 0.000301361 |  | 2.08731e-05 | 0.000276804 | 0.000327826 |
| elapsed_s | 3 | 0.000327269 |  | 1.76862e-05 | 0.000312567 | 0.000352144 |
| row_count | 3 | 5 |  | 0 | 5 | 5 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 22

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000419219 |  | 2.75937e-05 | 0.000383139 | 0.000450134 |
| elapsed_mean_s | 3 | 0.00033625 |  | 1.48512e-05 | 0.000324225 | 0.000357175 |
| elapsed_min_s | 3 | 0.000301758 |  | 1.66009e-05 | 0.000288963 | 0.000325203 |
| elapsed_s | 3 | 0.000326792 |  | 1.49481e-05 | 0.000312328 | 0.000347376 |
| row_count | 3 | 22 |  | 0 | 22 | 22 |

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
| elapsed_max_s | 3 | 0.000710249 |  | 0.000323493 | 0.000418663 | 0.00116134 |
| elapsed_mean_s | 3 | 0.000355776 |  | 3.55911e-05 | 0.000309873 | 0.000396609 |
| elapsed_min_s | 3 | 0.000284672 |  | 1.31901e-05 | 0.000270605 | 0.000302315 |
| elapsed_s | 3 | 0.000311693 |  | 1.83859e-05 | 0.000296831 | 0.000337601 |
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
| elapsed_max_s | 3 | 0.000853936 |  | 6.48327e-05 | 0.000783682 | 0.000940084 |
| elapsed_mean_s | 3 | 0.000704018 |  | 4.75616e-05 | 0.000662422 | 0.000770593 |
| elapsed_min_s | 3 | 0.000621478 |  | 4.94167e-05 | 0.000580072 | 0.000690937 |
| elapsed_s | 3 | 0.000689109 |  | 4.21856e-05 | 0.000641584 | 0.000744104 |
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
| elapsed_max_s | 3 | 0.000728051 |  | 7.5148e-05 | 0.000621796 | 0.000782967 |
| elapsed_mean_s | 3 | 0.000495021 |  | 2.30504e-05 | 0.000469089 | 0.000525093 |
| elapsed_min_s | 3 | 0.000403802 |  | 2.06443e-05 | 0.000375271 | 0.000423431 |
| elapsed_s | 3 | 0.000471512 |  | 3.47439e-05 | 0.000424385 | 0.000507116 |
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
| elapsed_max_s | 3 | 0.00137575 |  | 0.000604786 | 0.000780106 | 0.00220513 |
| elapsed_mean_s | 3 | 0.000759466 |  | 8.4785e-05 | 0.000688291 | 0.00087862 |
| elapsed_min_s | 3 | 0.000624975 |  | 3.20998e-05 | 0.000598907 | 0.000670195 |
| elapsed_s | 3 | 0.000689268 |  | 3.73783e-05 | 0.000654936 | 0.000741243 |
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
| elapsed_max_s | 3 | 0.000319163 |  | 1.93353e-05 | 0.000298023 | 0.000344753 |
| elapsed_mean_s | 3 | 0.000266663 |  | 2.37066e-06 | 0.000263548 | 0.000269294 |
| elapsed_min_s | 3 | 0.000240088 |  | 5.24882e-06 | 0.000235796 | 0.000247478 |
| elapsed_s | 3 | 0.000257969 |  | 8.59189e-06 | 0.000247955 | 0.000268936 |
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
| elapsed_max_s | 3 | 0.0010287 |  | 0.000194688 | 0.000811577 | 0.00128388 |
| elapsed_mean_s | 3 | 0.00084819 |  | 8.49513e-05 | 0.000763702 | 0.000964403 |
| elapsed_min_s | 3 | 0.000777324 |  | 4.63057e-05 | 0.000744343 | 0.00084281 |
| elapsed_s | 3 | 0.000809193 |  | 7.0515e-05 | 0.000756264 | 0.000908852 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000833352 |  | 0.000222148 | 0.000635862 | 0.00114369 |
| elapsed_mean_s | 3 | 0.000370733 |  | 3.10377e-05 | 0.000334835 | 0.000410557 |
| elapsed_min_s | 3 | 0.000296354 |  | 6.91825e-06 | 0.000291109 | 0.000306129 |
| elapsed_s | 3 | 0.000321309 |  | 1.39093e-05 | 0.000302076 | 0.000334501 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.00214108 |  | 0.000232747 | 0.00189734 | 0.00245452 |
| elapsed_mean_s | 3 | 0.00173816 |  | 0.000101615 | 0.00161896 | 0.00186727 |
| elapsed_min_s | 3 | 0.00145308 |  | 0.000154039 | 0.00123644 | 0.00158119 |
| elapsed_s | 3 | 0.00175969 |  | 8.63098e-05 | 0.00166416 | 0.00187325 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 5

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00198118 |  | 0.000350169 | 0.00150442 | 0.00233555 |
| elapsed_mean_s | 3 | 0.00142851 |  | 0.00017397 | 0.00119708 | 0.00161653 |
| elapsed_min_s | 3 | 0.00101916 |  | 9.72686e-05 | 0.000881672 | 0.00109172 |
| elapsed_s | 3 | 0.0014317 |  | 0.000197817 | 0.00117326 | 0.00165367 |
| row_count | 3 | 5 |  | 0 | 5 | 5 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 22

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0024821 |  | 0.00048927 | 0.00211501 | 0.00317359 |
| elapsed_mean_s | 3 | 0.00164216 |  | 3.11128e-05 | 0.00160513 | 0.00168126 |
| elapsed_min_s | 3 | 0.0011154 |  | 5.78633e-05 | 0.00104856 | 0.00118971 |
| elapsed_s | 3 | 0.00157698 |  | 9.87725e-05 | 0.00146151 | 0.00170279 |
| row_count | 3 | 22 |  | 0 | 22 | 22 |

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
| elapsed_max_s | 3 | 0.00129708 |  | 0.000369298 | 0.000978947 | 0.00181484 |
| elapsed_mean_s | 3 | 0.00102397 |  | 0.000181665 | 0.000875306 | 0.00127976 |
| elapsed_min_s | 3 | 0.000785112 |  | 3.63216e-05 | 0.000746012 | 0.000833511 |
| elapsed_s | 3 | 0.00116309 |  | 0.000372773 | 0.000870943 | 0.0016892 |
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
| elapsed_max_s | 3 | 0.00209792 |  | 0.000365156 | 0.00163341 | 0.00252557 |
| elapsed_mean_s | 3 | 0.00137168 |  | 7.97963e-05 | 0.00129907 | 0.0014828 |
| elapsed_min_s | 3 | 0.000912666 |  | 5.29364e-05 | 0.000837803 | 0.000950098 |
| elapsed_s | 3 | 0.00132608 |  | 0.000192468 | 0.00106263 | 0.00151706 |
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
| elapsed_max_s | 3 | 0.00124717 |  | 4.37587e-05 | 0.00120902 | 0.00130844 |
| elapsed_mean_s | 3 | 0.00100327 |  | 8.0783e-06 | 0.000994897 | 0.00101418 |
| elapsed_min_s | 3 | 0.000898123 |  | 2.25487e-05 | 0.000868797 | 0.000923634 |
| elapsed_s | 3 | 0.0009799 |  | 2.72194e-05 | 0.00094533 | 0.00101185 |
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
| elapsed_max_s | 3 | 0.00187755 |  | 0.000459213 | 0.00151658 | 0.00252557 |
| elapsed_mean_s | 3 | 0.00115469 |  | 0.000142663 | 0.000982046 | 0.00133142 |
| elapsed_min_s | 3 | 0.000855525 |  | 0.00011478 | 0.00070858 | 0.000988722 |
| elapsed_s | 3 | 0.0011162 |  | 0.000115558 | 0.000953913 | 0.00121403 |
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
| elapsed_max_s | 3 | 0.00029556 |  | 1.02572e-05 | 0.000281096 | 0.000303745 |
| elapsed_mean_s | 3 | 0.000193524 |  | 1.22955e-05 | 0.000181198 | 0.000210309 |
| elapsed_min_s | 3 | 0.000145833 |  | 1.11358e-05 | 0.00013113 | 0.000158072 |
| elapsed_s | 3 | 0.000187635 |  | 1.46868e-05 | 0.000172853 | 0.000207663 |
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
| elapsed_max_s | 3 | 0.000695149 |  | 0.000464061 | 0.000303745 | 0.00134706 |
| elapsed_mean_s | 3 | 0.000223096 |  | 5.17242e-05 | 0.000184608 | 0.000296211 |
| elapsed_min_s | 3 | 0.000121752 |  | 1.78738e-05 | 0.000103235 | 0.000145912 |
| elapsed_s | 3 | 0.000178814 |  | 8.69711e-06 | 0.000170231 | 0.000190735 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0015351 |  | 0.000402349 | 0.00123477 | 0.00210381 |
| elapsed_mean_s | 3 | 0.00104373 |  | 0.00019167 | 0.000892019 | 0.00131412 |
| elapsed_min_s | 3 | 0.000786622 |  | 2.65751e-05 | 0.000762939 | 0.000823736 |
| elapsed_s | 3 | 0.00114322 |  | 0.000394167 | 0.000861168 | 0.00170064 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.000552893 |  | 7.75502e-06 | 0.000547409 | 0.00056386 |
| elapsed_mean_s | 3 | 0.000520651 |  | 5.52093e-07 | 0.000519872 | 0.000521088 |
| elapsed_min_s | 3 | 0.000490268 |  | 1.43584e-05 | 0.000471115 | 0.000505686 |
| elapsed_s | 3 | 0.000520229 |  | 7.78672e-07 | 0.000519276 | 0.000521183 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 5

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000362714 |  | 4.47136e-05 | 0.000315428 | 0.000422716 |
| elapsed_mean_s | 3 | 0.000296728 |  | 1.5497e-06 | 0.000294614 | 0.000298285 |
| elapsed_min_s | 3 | 0.000275294 |  | 4.0942e-06 | 0.000270128 | 0.000280142 |
| elapsed_s | 3 | 0.000289679 |  | 4.60257e-06 | 0.000284433 | 0.000295639 |
| row_count | 3 | 5 |  | 0 | 5 | 5 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 22

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000394424 |  | 5.57357e-05 | 0.000317097 | 0.00044632 |
| elapsed_mean_s | 3 | 0.000305502 |  | 7.7034e-06 | 0.000294638 | 0.000311637 |
| elapsed_min_s | 3 | 0.000260671 |  | 4.04766e-06 | 0.000257015 | 0.000266314 |
| elapsed_s | 3 | 0.000300805 |  | 6.2577e-07 | 0.000299931 | 0.000301361 |
| row_count | 3 | 22 |  | 0 | 22 | 22 |

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
| elapsed_max_s | 3 | 0.000354449 |  | 4.42502e-05 | 0.000321388 | 0.000416994 |
| elapsed_mean_s | 3 | 0.000295782 |  | 1.01869e-05 | 0.000286317 | 0.00030992 |
| elapsed_min_s | 3 | 0.000270367 |  | 3.88849e-06 | 0.000264883 | 0.000273466 |
| elapsed_s | 3 | 0.000289043 |  | 2.41838e-06 | 0.000285625 | 0.000290871 |
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
| elapsed_max_s | 3 | 0.00447734 |  | 7.66642e-05 | 0.00436926 | 0.00453877 |
| elapsed_mean_s | 3 | 0.00399221 |  | 0.000164383 | 0.00376575 | 0.00415094 |
| elapsed_min_s | 3 | 0.00359853 |  | 0.000330274 | 0.00313163 | 0.00384307 |
| elapsed_s | 3 | 0.00398946 |  | 0.000117214 | 0.0038259 | 0.0040946 |
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
| elapsed_max_s | 3 | 0.000445604 |  | 7.79059e-05 | 0.000368118 | 0.000552177 |
| elapsed_mean_s | 3 | 0.000347018 |  | 7.09946e-06 | 0.000341797 | 0.000357056 |
| elapsed_min_s | 3 | 0.00031511 |  | 1.42312e-05 | 0.000295639 | 0.000329256 |
| elapsed_s | 3 | 0.000330289 |  | 4.59158e-06 | 0.000324965 | 0.00033617 |
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
| elapsed_max_s | 3 | 0.0034941 |  | 0.000252695 | 0.00313687 | 0.00368118 |
| elapsed_mean_s | 3 | 0.00306569 |  | 0.000157916 | 0.00284328 | 0.00319445 |
| elapsed_min_s | 3 | 0.00279363 |  | 0.000330488 | 0.00232625 | 0.00302744 |
| elapsed_s | 3 | 0.00306932 |  | 0.000104037 | 0.00292253 | 0.00315142 |
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
| elapsed_max_s | 3 | 0.000118574 |  | 6.14785e-05 | 7.48634e-05 | 0.000205517 |
| elapsed_mean_s | 3 | 6.64393e-05 |  | 5.88639e-06 | 6.09398e-05 | 7.46012e-05 |
| elapsed_min_s | 3 | 5.07037e-05 |  | 3.44036e-06 | 4.79221e-05 | 5.55515e-05 |
| elapsed_s | 3 | 6.07173e-05 |  | 3.12885e-06 | 5.79357e-05 | 6.50883e-05 |
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
| elapsed_max_s | 3 | 8.09828e-05 |  | 1.5508e-05 | 6.58035e-05 | 0.000102282 |
| elapsed_mean_s | 3 | 5.41925e-05 |  | 4.57776e-06 | 4.79221e-05 | 5.87225e-05 |
| elapsed_min_s | 3 | 3.91801e-05 |  | 1.15304e-05 | 2.28882e-05 | 4.79221e-05 |
| elapsed_s | 3 | 5.2611e-05 |  | 2.82324e-06 | 4.91142e-05 | 5.60284e-05 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.000357707 |  | 4.35927e-05 | 0.000319242 | 0.000418663 |
| elapsed_mean_s | 3 | 0.000294344 |  | 4.21969e-06 | 0.000290918 | 0.000300288 |
| elapsed_min_s | 3 | 0.000256856 |  | 9.79807e-07 | 0.000255585 | 0.000257969 |
| elapsed_s | 3 | 0.000294447 |  | 1.91726e-06 | 0.00029254 | 0.00029707 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

## Cross-DB Query Result Hash Checks

| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | All Hashes |
|---|---:|---|---|---|---|
| most_commented_posts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 1f31efc2ffdf18a35bc728191464347f52a4ff5d7273427c7ea1595e6c12ec28 |
| post_type_counts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 5197185908bb61e8b36679ffa296bd9cb2ad1b60463fb2f31da078c406b49c36 |
| posthistory_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | ead380b3805f89f4725e904f8382d8c5b54ab8acaa8dc3aff099b4a8adbf551c |
| postlinks_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | bf2cc559992e5b14a7a44a2ddb484cc69a123fe6f0a4dc0f189e920d0e13d4a7 |
| top_answers_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | b1f424cdd67a017d973078f2ac7e259dc9b60da8b0fefb60cced29c4edb0002c |
| top_badges | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | d45eba9b94c67b2cd37e9c58712c5aac9490f6c1ace927d6f19a2544cddfd421 |
| top_questions_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 5cf45e02296e343567ce9ee943ed7c48e879090af05954a6ab8cc2719bb6d89f |
| top_tags_by_count | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 |
| top_users_by_reputation | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | eea3eaa10ee67607c73e22808ecba38364b000fdb6c125b5c8c46174bc885f26 |
| votes_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | a680e3e9d76bce7e4e0083ae56d75ff2735692dd8193deb46e1867606ed165c7 |

### most_commented_posts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 1f31efc2ffdf18a35bc728191464347f52a4ff5d7273427c7ea1595e6c12ec28 | True |
| duckdb | 1f31efc2ffdf18a35bc728191464347f52a4ff5d7273427c7ea1595e6c12ec28 | True |
| postgresql | 1f31efc2ffdf18a35bc728191464347f52a4ff5d7273427c7ea1595e6c12ec28 | True |
| sqlite | 1f31efc2ffdf18a35bc728191464347f52a4ff5d7273427c7ea1595e6c12ec28 | True |

### post_type_counts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 5197185908bb61e8b36679ffa296bd9cb2ad1b60463fb2f31da078c406b49c36 | True |
| duckdb | 5197185908bb61e8b36679ffa296bd9cb2ad1b60463fb2f31da078c406b49c36 | True |
| postgresql | 5197185908bb61e8b36679ffa296bd9cb2ad1b60463fb2f31da078c406b49c36 | True |
| sqlite | 5197185908bb61e8b36679ffa296bd9cb2ad1b60463fb2f31da078c406b49c36 | True |

### posthistory_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | ead380b3805f89f4725e904f8382d8c5b54ab8acaa8dc3aff099b4a8adbf551c | True |
| duckdb | ead380b3805f89f4725e904f8382d8c5b54ab8acaa8dc3aff099b4a8adbf551c | True |
| postgresql | ead380b3805f89f4725e904f8382d8c5b54ab8acaa8dc3aff099b4a8adbf551c | True |
| sqlite | ead380b3805f89f4725e904f8382d8c5b54ab8acaa8dc3aff099b4a8adbf551c | True |

### postlinks_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | bf2cc559992e5b14a7a44a2ddb484cc69a123fe6f0a4dc0f189e920d0e13d4a7 | True |
| duckdb | bf2cc559992e5b14a7a44a2ddb484cc69a123fe6f0a4dc0f189e920d0e13d4a7 | True |
| postgresql | bf2cc559992e5b14a7a44a2ddb484cc69a123fe6f0a4dc0f189e920d0e13d4a7 | True |
| sqlite | bf2cc559992e5b14a7a44a2ddb484cc69a123fe6f0a4dc0f189e920d0e13d4a7 | True |

### top_answers_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | b1f424cdd67a017d973078f2ac7e259dc9b60da8b0fefb60cced29c4edb0002c | True |
| duckdb | b1f424cdd67a017d973078f2ac7e259dc9b60da8b0fefb60cced29c4edb0002c | True |
| postgresql | b1f424cdd67a017d973078f2ac7e259dc9b60da8b0fefb60cced29c4edb0002c | True |
| sqlite | b1f424cdd67a017d973078f2ac7e259dc9b60da8b0fefb60cced29c4edb0002c | True |

### top_badges

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | d45eba9b94c67b2cd37e9c58712c5aac9490f6c1ace927d6f19a2544cddfd421 | True |
| duckdb | d45eba9b94c67b2cd37e9c58712c5aac9490f6c1ace927d6f19a2544cddfd421 | True |
| postgresql | d45eba9b94c67b2cd37e9c58712c5aac9490f6c1ace927d6f19a2544cddfd421 | True |
| sqlite | d45eba9b94c67b2cd37e9c58712c5aac9490f6c1ace927d6f19a2544cddfd421 | True |

### top_questions_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 5cf45e02296e343567ce9ee943ed7c48e879090af05954a6ab8cc2719bb6d89f | True |
| duckdb | 5cf45e02296e343567ce9ee943ed7c48e879090af05954a6ab8cc2719bb6d89f | True |
| postgresql | 5cf45e02296e343567ce9ee943ed7c48e879090af05954a6ab8cc2719bb6d89f | True |
| sqlite | 5cf45e02296e343567ce9ee943ed7c48e879090af05954a6ab8cc2719bb6d89f | True |

### top_tags_by_count

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 | True |
| duckdb | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 | True |
| postgresql | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 | True |
| sqlite | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 | True |

### top_users_by_reputation

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | eea3eaa10ee67607c73e22808ecba38364b000fdb6c125b5c8c46174bc885f26 | True |
| duckdb | eea3eaa10ee67607c73e22808ecba38364b000fdb6c125b5c8c46174bc885f26 | True |
| postgresql | eea3eaa10ee67607c73e22808ecba38364b000fdb6c125b5c8c46174bc885f26 | True |
| sqlite | eea3eaa10ee67607c73e22808ecba38364b000fdb6c125b5c8c46174bc885f26 | True |

### votes_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | a680e3e9d76bce7e4e0083ae56d75ff2735692dd8193deb46e1867606ed165c7 | True |
| duckdb | a680e3e9d76bce7e4e0083ae56d75ff2735692dd8193deb46e1867606ed165c7 | True |
| postgresql | a680e3e9d76bce7e4e0083ae56d75ff2735692dd8193deb46e1867606ed165c7 | True |
| sqlite | a680e3e9d76bce7e4e0083ae56d75ff2735692dd8193deb46e1867606ed165c7 | True |
