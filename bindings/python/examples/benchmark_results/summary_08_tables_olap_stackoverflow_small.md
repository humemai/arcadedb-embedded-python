# 08 Tables OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:10Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep08
- Total runs: 12

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep08_r01_arcadedb_s00000, sweep08_r01_duckdb_s00002, sweep08_r01_postgresql_s00003, sweep08_r01_sqlite_s00001, sweep08_r02_arcadedb_s00004, sweep08_r02_duckdb_s00006, sweep08_r02_postgresql_s00007, sweep08_r02_sqlite_s00005, sweep08_r03_arcadedb_s00008, sweep08_r03_duckdb_s00010, sweep08_r03_postgresql_s00011, sweep08_r03_sqlite_s00009 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| disk_after_index_bytes | 3 | 6.69876e+08 | 638.8MiB | 1.40636e+07 | 655411884 | 688930180 |
| disk_after_load_bytes | 3 | 6.05337e+08 | 577.3MiB | 2.38522e+07 | 577773521 | 635958595 |
| disk_after_queries_bytes | 3 | 646401211 | 616.5MiB | 2.01317e+07 | 618507105 | 665284644 |
| disk_usage.du_bytes | 3 | 6.11667e+08 | 583.3MiB | 1930.87 | 611663872 | 611667968 |
| index.total_s | 3 | 9.59454 |  | 1.09753 | 8.58269 | 11.1198 |
| load.total_s | 3 | 45.9561 |  | 1.97999 | 43.3429 | 48.1339 |
| queries.total_s | 3 | 32.3942 |  | 3.40749 | 28.1836 | 36.5292 |
| query_cold_time_s | 3 | 0.266174 |  | 0.0100681 | 0.257833 | 0.280338 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.330192 |  | 0.0387868 | 0.281815 | 0.376772 |
| rss_client_peak_kb | 3 | 1.62561e+06 | 1.6GiB | 45556.9 | 1582376 | 1688592 |
| rss_peak_kb | 3 | 1.62561e+06 | 1.6GiB | 45556.9 | 1582376 | 1688592 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.407505 |  | 0.228013 | 0.0854065 | 0.581764 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| table_counts.after_load.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_load.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_load.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_load.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_load.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_load.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.after_queries.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_queries.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_queries.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_queries.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_queries.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_queries.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.counts_time_s | 3 | 0.000635147 |  | 9.55344e-05 | 0.000549316 | 0.000768423 |
| table_counts.load_counts_time_s | 3 | 0.0422223 |  | 0.00274164 | 0.0384409 | 0.0448551 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 88.9723 |  | 1.44608 | 86.9811 | 90.3718 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: duckdb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| disk_after_index_bytes | 3 | 1214498456 | 1.1GiB | 249168 | 1214319360 | 1214850816 |
| disk_after_load_bytes | 3 | 1.16925e+09 | 1.1GiB | 247152 | 1169077988 | 1169602276 |
| disk_after_queries_bytes | 3 | 1214498456 | 1.1GiB | 249168 | 1214319360 | 1214850816 |
| disk_usage.du_bytes | 3 | 1215455232 | 1.1GiB | 249083 | 1215279104 | 1215807488 |
| index.total_s | 3 | 0.758441 |  | 0.0905369 | 0.631092 | 0.833611 |
| load.total_s | 3 | 36.7062 |  | 5.50003 | 29.0228 | 41.5964 |
| queries.total_s | 3 | 0.173154 |  | 0.00865761 | 0.161685 | 0.182601 |
| query_cold_time_s | 3 | 0.00315977 |  | 0.00131194 | 0.0020972 | 0.00500824 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.00151493 |  | 8.54762e-05 | 0.00141104 | 0.00162039 |
| rss_client_peak_kb | 3 | 939141 | 917.1MiB | 13105.1 | 926196 | 957100 |
| rss_peak_kb | 3 | 939141 | 917.1MiB | 13105.1 | 926196 | 957100 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.0866419 |  | 0.00414896 | 0.0828965 | 0.0924261 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| table_counts.after_load.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_load.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_load.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_load.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_load.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_load.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.after_queries.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_queries.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_queries.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_queries.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_queries.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_queries.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.counts_time_s | 3 | 0.00145388 |  | 5.07882e-05 | 0.0013845 | 0.00150466 |
| table_counts.load_counts_time_s | 3 | 0.00711036 |  | 0.0013507 | 0.00573659 | 0.00894666 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 37.9659 |  | 5.63985 | 30.0715 | 42.8982 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: postgresql (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| disk_after_index_bytes | 3 | 1095206209 | 1.0GiB | 0 | 1095206209 | 1095206209 |
| disk_after_load_bytes | 3 | 1014048065 | 967.1MiB | 0 | 1014048065 | 1014048065 |
| disk_after_queries_bytes | 3 | 1095206209 | 1.0GiB | 0 | 1095206209 | 1095206209 |
| disk_usage.du_bytes | 3 | 1095622656 | 1.0GiB | 15325.8 | 1095602176 | 1095639040 |
| index.total_s | 3 | 1.50369 |  | 1.0164 | 0.776686 | 2.94106 |
| load.total_s | 3 | 39.9899 |  | 1.62892 | 38.0564 | 42.0412 |
| queries.total_s | 3 | 2.09383 |  | 0.740339 | 1.179 | 2.99223 |
| query_cold_time_s | 3 | 0.012292 |  | 0.00106796 | 0.0108992 | 0.0134943 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.0218311 |  | 0.00829794 | 0.0116453 | 0.0319709 |
| rss_client_peak_kb | 3 | 56773.3 | 55.4MiB | 131.142 | 56632 | 56948 |
| rss_peak_kb | 3 | 652837 | 637.5MiB | 16132.5 | 633032 | 672548 |
| rss_server_peak_kb | 3 | 596929 | 582.9MiB | 16018.3 | 577380 | 616616 |
| schema.total_s | 3 | 0.0191851 |  | 0.0136137 | 0.00799942 | 0.0383484 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| table_counts.after_load.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_load.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_load.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_load.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_load.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_load.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.after_queries.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_queries.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_queries.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_queries.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_queries.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_queries.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.counts_time_s | 3 | 0.333781 |  | 0.367572 | 0.0682406 | 0.853565 |
| table_counts.load_counts_time_s | 3 | 0.284611 |  | 0.0522331 | 0.220949 | 0.348889 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 50.4901 |  | 2.20516 | 48.3848 | 53.5352 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: sqlite (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| disk_after_index_bytes | 3 | 623407104 | 594.5MiB | 0 | 623407104 | 623407104 |
| disk_after_load_bytes | 3 | 585060352 | 558.0MiB | 0 | 585060352 | 585060352 |
| disk_after_queries_bytes | 3 | 623407104 | 594.5MiB | 0 | 623407104 | 623407104 |
| disk_usage.du_bytes | 3 | 623439872 | 594.6MiB | 0 | 623439872 | 623439872 |
| index.total_s | 3 | 1.83836 |  | 0.0523866 | 1.79726 | 1.91229 |
| load.total_s | 3 | 35.8282 |  | 4.65562 | 31.374 | 42.2543 |
| queries.total_s | 3 | 1.33739 |  | 0.0336923 | 1.30951 | 1.3848 |
| query_cold_time_s | 3 | 0.0131164 |  | 0.000609788 | 0.0123426 | 0.013833 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.0133265 |  | 0.000312707 | 0.0131029 | 0.0137688 |
| rss_client_peak_kb | 3 | 42992 | 42.0MiB | 113.137 | 42832 | 43072 |
| rss_peak_kb | 3 | 42992 | 42.0MiB | 113.137 | 42832 | 43072 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.338843 |  | 0.0666423 | 0.244675 | 0.389252 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| table_counts.after_load.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_load.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_load.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_load.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_load.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_load.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_load.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_load.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.after_queries.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| table_counts.after_queries.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| table_counts.after_queries.Post | 3 | 105373 |  | 0 | 105373 | 105373 |
| table_counts.after_queries.PostHistory | 3 | 360340 |  | 0 | 360340 | 360340 |
| table_counts.after_queries.PostLink | 3 | 11005 |  | 0 | 11005 | 11005 |
| table_counts.after_queries.Tag | 3 | 668 |  | 0 | 668 | 668 |
| table_counts.after_queries.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| table_counts.after_queries.Vote | 3 | 411166 |  | 0 | 411166 | 411166 |
| table_counts.counts_time_s | 3 | 0.00393414 |  | 0.000408339 | 0.00364041 | 0.00451159 |
| table_counts.load_counts_time_s | 3 | 0.150393 |  | 0.00874225 | 0.138529 | 0.159338 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 39.4984 |  | 4.56532 | 35.0382 | 45.7712 |

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
| elapsed_max_s | 3 | 0.737309 |  | 0.0396617 | 0.693934 | 0.789795 |
| elapsed_mean_s | 3 | 0.310802 |  | 0.0263683 | 0.288754 | 0.347871 |
| elapsed_min_s | 3 | 0.195706 |  | 0.0084646 | 0.184254 | 0.20445 |
| elapsed_s | 3 | 0.238528 |  | 0.0225462 | 0.208218 | 0.262254 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 6

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.369869 |  | 0.0468472 | 0.303803 | 0.407197 |
| elapsed_mean_s | 3 | 0.23421 |  | 0.00745904 | 0.224272 | 0.242242 |
| elapsed_min_s | 3 | 0.178629 |  | 0.00260418 | 0.175187 | 0.181484 |
| elapsed_s | 3 | 0.221426 |  | 0.00796758 | 0.211174 | 0.230602 |
| row_count | 3 | 6 |  | 0 | 6 | 6 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 30

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 2.44685 |  | 1.47659 | 1.04528 | 4.48823 |
| elapsed_mean_s | 3 | 0.980005 |  | 0.169839 | 0.791474 | 1.20315 |
| elapsed_min_s | 3 | 0.690708 |  | 0.033008 | 0.654237 | 0.734176 |
| elapsed_s | 3 | 0.786913 |  | 0.0474236 | 0.736888 | 0.850612 |
| row_count | 3 | 30 |  | 0 | 30 | 30 |

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
| elapsed_max_s | 3 | 0.0480768 |  | 0.0253989 | 0.0245702 | 0.0833511 |
| elapsed_mean_s | 3 | 0.017464 |  | 0.00253383 | 0.014766 | 0.0208553 |
| elapsed_min_s | 3 | 0.0116727 |  | 9.23072e-05 | 0.0115447 | 0.011759 |
| elapsed_s | 3 | 0.0143157 |  | 0.00124293 | 0.0131891 | 0.0160475 |
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
| elapsed_max_s | 3 | 2.08364 |  | 1.45394 | 0.609889 | 4.06227 |
| elapsed_mean_s | 3 | 0.385368 |  | 0.14274 | 0.263804 | 0.585716 |
| elapsed_min_s | 3 | 0.0974114 |  | 0.00428037 | 0.0919254 | 0.10237 |
| elapsed_s | 3 | 0.162362 |  | 0.0426443 | 0.124227 | 0.221891 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: top_badges (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.258988 |  | 0.0847381 | 0.14537 | 0.348797 |
| elapsed_mean_s | 3 | 0.13768 |  | 0.0127805 | 0.12008 | 0.150044 |
| elapsed_min_s | 3 | 0.110965 |  | 0.00228597 | 0.108818 | 0.114132 |
| elapsed_s | 3 | 0.124349 |  | 0.00462353 | 0.117908 | 0.128546 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 1.68285 |  | 1.23888 | 0.681611 | 3.42862 |
| elapsed_mean_s | 3 | 0.308497 |  | 0.165356 | 0.16095 | 0.53939 |
| elapsed_min_s | 3 | 0.0807951 |  | 0.004257 | 0.075325 | 0.0857077 |
| elapsed_s | 3 | 0.105033 |  | 0.00629153 | 0.0965471 | 0.111593 |
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
| elapsed_max_s | 3 | 0.0117997 |  | 0.00862103 | 0.00550485 | 0.0239894 |
| elapsed_mean_s | 3 | 0.00325435 |  | 0.00197923 | 0.00178044 | 0.00605206 |
| elapsed_min_s | 3 | 0.00102695 |  | 6.97122e-05 | 0.000932693 | 0.00109911 |
| elapsed_s | 3 | 0.00164509 |  | 0.000315557 | 0.00127411 | 0.00204539 |
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
| elapsed_max_s | 3 | 0.332465 |  | 0.0196099 | 0.306026 | 0.352934 |
| elapsed_mean_s | 3 | 0.192704 |  | 0.00524737 | 0.185484 | 0.197799 |
| elapsed_min_s | 3 | 0.136986 |  | 0.00320028 | 0.132867 | 0.14067 |
| elapsed_s | 3 | 0.177006 |  | 0.0235482 | 0.153751 | 0.209278 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 14

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 1.25244 |  | 0.57704 | 0.81897 | 2.06796 |
| elapsed_mean_s | 3 | 0.667917 |  | 0.0553635 | 0.626461 | 0.746167 |
| elapsed_min_s | 3 | 0.542566 |  | 0.00244759 | 0.539105 | 0.544349 |
| elapsed_s | 3 | 0.594264 |  | 0.00952174 | 0.582681 | 0.606003 |
| row_count | 3 | 14 |  | 0 | 14 | 14 |

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
| elapsed_max_s | 3 | 0.00886989 |  | 0.00297681 | 0.00582361 | 0.0129094 |
| elapsed_mean_s | 3 | 0.00453452 |  | 0.000432952 | 0.00399373 | 0.00505357 |
| elapsed_min_s | 3 | 0.00330003 |  | 0.000113792 | 0.00316572 | 0.00344396 |
| elapsed_s | 3 | 0.00402228 |  | 3.10923e-05 | 0.00397849 | 0.00404763 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 6

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00169905 |  | 0.000501157 | 0.00101399 | 0.00219893 |
| elapsed_mean_s | 3 | 0.000828091 |  | 3.86216e-05 | 0.000776887 | 0.000870156 |
| elapsed_min_s | 3 | 0.000640631 |  | 3.06298e-05 | 0.000598431 | 0.000670195 |
| elapsed_s | 3 | 0.00074776 |  | 4.10493e-05 | 0.000690222 | 0.000783205 |
| row_count | 3 | 6 |  | 0 | 6 | 6 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 30

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00560474 |  | 0.00333972 | 0.000881672 | 0.00796819 |
| elapsed_mean_s | 3 | 0.00149005 |  | 0.000537137 | 0.000772238 | 0.0020642 |
| elapsed_min_s | 3 | 0.000625451 |  | 4.45259e-05 | 0.000566721 | 0.000674486 |
| elapsed_s | 3 | 0.000852346 |  | 0.000112505 | 0.000768423 | 0.00101137 |
| row_count | 3 | 30 |  | 0 | 30 | 30 |

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
| elapsed_max_s | 3 | 0.00193159 |  | 0.0011111 | 0.000976562 | 0.00348973 |
| elapsed_mean_s | 3 | 0.000640543 |  | 0.000120959 | 0.000538278 | 0.000810432 |
| elapsed_min_s | 3 | 0.000365893 |  | 2.3142e-05 | 0.000339746 | 0.000396013 |
| elapsed_s | 3 | 0.00047946 |  | 3.2516e-06 | 0.000475883 | 0.000483751 |
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
| elapsed_max_s | 3 | 0.0048267 |  | 0.00158277 | 0.00290203 | 0.00677872 |
| elapsed_mean_s | 3 | 0.00195876 |  | 0.000160173 | 0.00176666 | 0.00215876 |
| elapsed_min_s | 3 | 0.00119988 |  | 6.6462e-05 | 0.00110888 | 0.00126576 |
| elapsed_s | 3 | 0.00154583 |  | 0.00010437 | 0.00141454 | 0.00166988 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: top_badges (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00225727 |  | 0.00129867 | 0.00110984 | 0.0040729 |
| elapsed_mean_s | 3 | 0.000991384 |  | 0.000130348 | 0.00088079 | 0.0011744 |
| elapsed_min_s | 3 | 0.000686169 |  | 2.73056e-05 | 0.000651598 | 0.000718355 |
| elapsed_s | 3 | 0.000860294 |  | 5.0928e-05 | 0.000802994 | 0.000926733 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.00625714 |  | 0.0032972 | 0.00305653 | 0.0107942 |
| elapsed_mean_s | 3 | 0.00206132 |  | 0.000267256 | 0.0017509 | 0.00240326 |
| elapsed_min_s | 3 | 0.00119193 |  | 6.58951e-05 | 0.00113916 | 0.00128484 |
| elapsed_s | 3 | 0.00146866 |  | 0.000105428 | 0.00135851 | 0.00161076 |
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
| elapsed_max_s | 3 | 0.000680129 |  | 0.000260528 | 0.000494003 | 0.00104856 |
| elapsed_mean_s | 3 | 0.0004107 |  | 5.27415e-05 | 0.000351977 | 0.000479889 |
| elapsed_min_s | 3 | 0.000282923 |  | 1.1988e-05 | 0.000268698 | 0.000298023 |
| elapsed_s | 3 | 0.000365496 |  | 3.43141e-05 | 0.000325918 | 0.000409603 |
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
| elapsed_max_s | 3 | 0.00828155 |  | 0.00366382 | 0.00318241 | 0.0116277 |
| elapsed_mean_s | 3 | 0.00244445 |  | 0.000422275 | 0.00185394 | 0.00281684 |
| elapsed_min_s | 3 | 0.00139427 |  | 4.85816e-05 | 0.00133014 | 0.00144768 |
| elapsed_s | 3 | 0.00170461 |  | 0.000117325 | 0.00153995 | 0.00180459 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 14

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00630784 |  | 0.00336846 | 0.0036025 | 0.0110562 |
| elapsed_mean_s | 3 | 0.00143433 |  | 0.000390402 | 0.00105865 | 0.00197256 |
| elapsed_min_s | 3 | 0.0007116 |  | 4.44015e-05 | 0.000679255 | 0.000774384 |
| elapsed_s | 3 | 0.000835578 |  | 3.12224e-05 | 0.000794411 | 0.000869989 |
| row_count | 3 | 14 |  | 0 | 14 | 14 |

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
| elapsed_max_s | 3 | 0.234255 |  | 0.274091 | 0.0391595 | 0.621875 |
| elapsed_mean_s | 3 | 0.0513822 |  | 0.0264388 | 0.0321115 | 0.0887663 |
| elapsed_min_s | 3 | 0.0276512 |  | 0.000830045 | 0.0266469 | 0.0286796 |
| elapsed_s | 3 | 0.0319703 |  | 0.00135219 | 0.0300844 | 0.0331872 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 6

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.127456 |  | 0.145292 | 0.0232713 | 0.332923 |
| elapsed_mean_s | 3 | 0.0387081 |  | 0.0270132 | 0.0187262 | 0.0768968 |
| elapsed_min_s | 3 | 0.0147928 |  | 0.00100748 | 0.0136354 | 0.0160911 |
| elapsed_s | 3 | 0.0188125 |  | 0.000812909 | 0.0180056 | 0.0199251 |
| row_count | 3 | 6 |  | 0 | 6 | 6 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 30

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.577894 |  | 0.392366 | 0.0317006 | 0.935734 |
| elapsed_mean_s | 3 | 0.0817704 |  | 0.0392312 | 0.0276624 | 0.119449 |
| elapsed_min_s | 3 | 0.0233499 |  | 0.000860354 | 0.0221603 | 0.0241659 |
| elapsed_s | 3 | 0.0274591 |  | 0.00227318 | 0.0245368 | 0.0300806 |
| row_count | 3 | 30 |  | 0 | 30 | 30 |

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
| elapsed_max_s | 3 | 0.00204293 |  | 0.000559604 | 0.00158811 | 0.00283122 |
| elapsed_mean_s | 3 | 0.00135519 |  | 3.56105e-05 | 0.00132871 | 0.00140553 |
| elapsed_min_s | 3 | 0.00099508 |  | 7.38216e-05 | 0.000917435 | 0.00109434 |
| elapsed_s | 3 | 0.00129986 |  | 0.000119883 | 0.00114083 | 0.00143027 |
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
| elapsed_max_s | 3 | 0.000613928 |  | 0.000218323 | 0.000444889 | 0.000922203 |
| elapsed_mean_s | 3 | 0.000325139 |  | 2.84489e-05 | 0.000285816 | 0.000352168 |
| elapsed_min_s | 3 | 0.000161886 |  | 3.30712e-05 | 0.000128508 | 0.000206947 |
| elapsed_s | 3 | 0.000348647 |  | 2.91315e-05 | 0.00031209 | 0.000383377 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: top_badges (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0148908 |  | 0.00133491 | 0.0131433 | 0.0163832 |
| elapsed_mean_s | 3 | 0.0127061 |  | 0.000619815 | 0.0118616 | 0.0133318 |
| elapsed_min_s | 3 | 0.0112605 |  | 0.00034089 | 0.0107803 | 0.0115378 |
| elapsed_s | 3 | 0.0128489 |  | 0.000576472 | 0.0120409 | 0.0133464 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.000924269 |  | 0.000628499 | 0.000394344 | 0.00180721 |
| elapsed_mean_s | 3 | 0.000342472 |  | 5.4293e-05 | 0.000292325 | 0.0004179 |
| elapsed_min_s | 3 | 0.000118574 |  | 2.92218e-06 | 0.000114441 | 0.00012064 |
| elapsed_s | 3 | 0.000328461 |  | 2.48088e-05 | 0.000306368 | 0.000363111 |
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
| elapsed_max_s | 3 | 0.000553528 |  | 3.23409e-05 | 0.000527859 | 0.000599146 |
| elapsed_mean_s | 3 | 0.000312153 |  | 2.68559e-06 | 0.000309658 | 0.000315881 |
| elapsed_min_s | 3 | 0.000171105 |  | 1.17856e-05 | 0.000155687 | 0.000184298 |
| elapsed_s | 3 | 0.000286659 |  | 4.03678e-05 | 0.00024724 | 0.000342131 |
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
| elapsed_max_s | 3 | 0.000820478 |  | 0.000370406 | 0.00041151 | 0.00130844 |
| elapsed_mean_s | 3 | 0.000332793 |  | 4.4991e-05 | 0.000272894 | 0.000381327 |
| elapsed_min_s | 3 | 0.000157833 |  | 2.42508e-05 | 0.000123739 | 0.000178099 |
| elapsed_s | 3 | 0.000295957 |  | 1.48438e-05 | 0.000279427 | 0.000315428 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 14

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0245862 |  | 0.00239963 | 0.0217507 | 0.0276186 |
| elapsed_mean_s | 3 | 0.0215373 |  | 0.000846643 | 0.0203566 | 0.0222997 |
| elapsed_min_s | 3 | 0.0196408 |  | 0.00059282 | 0.0190525 | 0.0204523 |
| elapsed_s | 3 | 0.0213462 |  | 0.000788797 | 0.020262 | 0.0221157 |
| row_count | 3 | 14 |  | 0 | 14 | 14 |

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
| elapsed_max_s | 3 | 0.0129863 |  | 0.00163508 | 0.011116 | 0.015099 |
| elapsed_mean_s | 3 | 0.0110469 |  | 0.000357097 | 0.0107315 | 0.0115462 |
| elapsed_min_s | 3 | 0.0103001 |  | 0.000141534 | 0.0101001 | 0.0104079 |
| elapsed_s | 3 | 0.0107234 |  | 9.55725e-06 | 0.01071 | 0.0107315 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 6

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0047067 |  | 0.000828017 | 0.00357008 | 0.00551891 |
| elapsed_mean_s | 3 | 0.00319004 |  | 0.000155853 | 0.00297139 | 0.00332341 |
| elapsed_min_s | 3 | 0.00278997 |  | 6.84061e-05 | 0.00271487 | 0.00288033 |
| elapsed_s | 3 | 0.00299088 |  | 3.48256e-05 | 0.00295091 | 0.00303578 |
| row_count | 3 | 6 |  | 0 | 6 | 6 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: posthistory_by_type (samples=3)

- Hash stable: True
- Row counts: 30

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0108912 |  | 0.000239968 | 0.0105624 | 0.0111284 |
| elapsed_mean_s | 3 | 0.0102316 |  | 0.0002054 | 0.0100621 | 0.0105206 |
| elapsed_min_s | 3 | 0.00951592 |  | 0.000366824 | 0.00907469 | 0.00997281 |
| elapsed_s | 3 | 0.0102754 |  | 0.000101434 | 0.0101917 | 0.0104182 |
| row_count | 3 | 30 |  | 0 | 30 | 30 |

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
| elapsed_max_s | 3 | 0.000713428 |  | 0.00026299 | 0.000415564 | 0.00105524 |
| elapsed_mean_s | 3 | 0.000393438 |  | 6.03497e-05 | 0.000335789 | 0.000476766 |
| elapsed_min_s | 3 | 0.000311136 |  | 9.4429e-06 | 0.000304222 | 0.000324488 |
| elapsed_s | 3 | 0.000347058 |  | 2.43765e-05 | 0.000328064 | 0.00038147 |
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
| elapsed_max_s | 3 | 0.0492948 |  | 0.00178164 | 0.0475149 | 0.0517292 |
| elapsed_mean_s | 3 | 0.0466825 |  | 0.00113212 | 0.0456029 | 0.0482462 |
| elapsed_min_s | 3 | 0.0439789 |  | 0.000211179 | 0.0436807 | 0.0441413 |
| elapsed_s | 3 | 0.0470307 |  | 0.00131429 | 0.0457773 | 0.048846 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: top_badges (samples=3)

- Hash stable: True
- Row counts: 10

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00817951 |  | 0.000803637 | 0.00708008 | 0.00897861 |
| elapsed_mean_s | 3 | 0.00665236 |  | 0.000427681 | 0.00630019 | 0.00725429 |
| elapsed_min_s | 3 | 0.00601157 |  | 8.02269e-05 | 0.0059011 | 0.00608921 |
| elapsed_s | 3 | 0.0066371 |  | 0.000595106 | 0.00611949 | 0.00747061 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.0493917 |  | 0.00285769 | 0.0472658 | 0.0534313 |
| elapsed_mean_s | 3 | 0.0427183 |  | 0.000934234 | 0.0416675 | 0.0439373 |
| elapsed_min_s | 3 | 0.0387774 |  | 0.000898055 | 0.0378511 | 0.039993 |
| elapsed_s | 3 | 0.0424473 |  | 0.000327068 | 0.042064 | 0.0428631 |
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
| elapsed_max_s | 3 | 0.000137409 |  | 2.73606e-05 | 0.000104427 | 0.000171423 |
| elapsed_mean_s | 3 | 8.94547e-05 |  | 4.03019e-06 | 8.42094e-05 | 9.40084e-05 |
| elapsed_min_s | 3 | 6.2863e-05 |  | 3.44036e-06 | 6.00815e-05 | 6.77109e-05 |
| elapsed_s | 3 | 9.02017e-05 |  | 2.23939e-06 | 8.74996e-05 | 9.29832e-05 |
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
| elapsed_max_s | 3 | 0.000161091 |  | 4.94523e-06 | 0.000157595 | 0.000168085 |
| elapsed_mean_s | 3 | 8.79288e-05 |  | 4.50554e-06 | 8.39233e-05 | 9.4223e-05 |
| elapsed_min_s | 3 | 5.34852e-05 |  | 1.51945e-05 | 3.24249e-05 | 6.77109e-05 |
| elapsed_s | 3 | 8.49565e-05 |  | 1.4868e-06 | 8.29697e-05 | 8.65459e-05 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: votes_by_type (samples=3)

- Hash stable: True
- Row counts: 14

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0136185 |  | 0.00101836 | 0.0128624 | 0.015058 |
| elapsed_mean_s | 3 | 0.0119628 |  | 0.000214946 | 0.0117703 | 0.0122628 |
| elapsed_min_s | 3 | 0.0111351 |  | 0.000216711 | 0.0109749 | 0.0114415 |
| elapsed_s | 3 | 0.0118713 |  | 1.72194e-05 | 0.011847 | 0.0118854 |
| row_count | 3 | 14 |  | 0 | 14 | 14 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

## Cross-DB Query Result Hash Checks

| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | All Hashes |
|---|---:|---|---|---|---|
| most_commented_posts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b |
| post_type_counts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b |
| posthistory_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b |
| postlinks_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 |
| top_answers_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad |
| top_badges | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d |
| top_questions_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 |
| top_tags_by_count | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 |
| top_users_by_reputation | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 |
| votes_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 |

### most_commented_posts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b | True |
| duckdb | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b | True |
| postgresql | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b | True |
| sqlite | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b | True |

### post_type_counts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b | True |
| duckdb | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b | True |
| postgresql | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b | True |
| sqlite | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b | True |

### posthistory_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b | True |
| duckdb | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b | True |
| postgresql | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b | True |
| sqlite | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b | True |

### postlinks_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 | True |
| duckdb | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 | True |
| postgresql | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 | True |
| sqlite | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 | True |

### top_answers_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad | True |
| duckdb | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad | True |
| postgresql | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad | True |
| sqlite | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad | True |

### top_badges

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d | True |
| duckdb | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d | True |
| postgresql | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d | True |
| sqlite | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d | True |

### top_questions_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 | True |
| duckdb | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 | True |
| postgresql | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 | True |
| sqlite | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 | True |

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
| arcadedb | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 | True |
| duckdb | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 | True |
| postgresql | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 | True |
| sqlite | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 | True |

### votes_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 | True |
| duckdb | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 | True |
| postgresql | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 | True |
| sqlite | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 | True |
