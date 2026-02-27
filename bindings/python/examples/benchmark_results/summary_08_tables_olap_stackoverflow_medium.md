# 08 Tables OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:10Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep08
- Total runs: 12

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep08_r01_arcadedb_s00000, sweep08_r01_duckdb_s00002, sweep08_r01_postgresql_s00003, sweep08_r01_sqlite_s00001, sweep08_r02_arcadedb_s00004, sweep08_r02_duckdb_s00006, sweep08_r02_postgresql_s00007, sweep08_r02_sqlite_s00005, sweep08_r03_arcadedb_s00008, sweep08_r03_duckdb_s00010, sweep08_r03_postgresql_s00011, sweep08_r03_sqlite_s00009 |
| seed | 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| disk_after_index_bytes | 3 | 2.86406e+09 | 2.7GiB | 1.47257e+07 | 2851081924 | 2884656706 |
| disk_after_load_bytes | 3 | 2.75496e+09 | 2.6GiB | 1.13723e+07 | 2739680214 | 2766951640 |
| disk_after_queries_bytes | 3 | 2.86406e+09 | 2.7GiB | 1.47257e+07 | 2851081924 | 2884656706 |
| disk_usage.du_bytes | 3 | 2832695296 | 2.6GiB | 3344.37 | 2832691200 | 2832699392 |
| index.total_s | 3 | 77.0114 |  | 2.21592 | 73.8802 | 78.6861 |
| load.total_s | 3 | 177.424 |  | 13.0551 | 159.182 | 189.008 |
| queries.total_s | 3 | 433.376 |  | 139.223 | 295.557 | 624.059 |
| query_cold_time_s | 3 | 7.72205 |  | 5.44778 | 3.27796 | 15.3943 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 3.95692 |  | 0.954435 | 2.91943 | 5.22341 |
| rss_client_peak_kb | 3 | 3.47735e+06 | 3.3GiB | 143174 | 3360488 | 3678980 |
| rss_peak_kb | 3 | 3.47735e+06 | 3.3GiB | 143174 | 3360488 | 3678980 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.124908 |  | 0.0504568 | 0.0858035 | 0.196151 |
| seed | 3 | 4 |  | 3.26599 | 0 | 8 |
| table_counts.after_load.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_load.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_load.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_load.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_load.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_load.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_load.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_load.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.after_queries.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_queries.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_queries.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_queries.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_queries.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_queries.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_queries.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_queries.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.counts_time_s | 3 | 0.000902017 |  | 0.000172741 | 0.000662804 | 0.00106454 |
| table_counts.load_counts_time_s | 3 | 0.058796 |  | 0.0081587 | 0.0491662 | 0.0691152 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 688.605 |  | 125.139 | 558.852 | 857.706 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: duckdb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| disk_after_index_bytes | 3 | 5.56372e+09 | 5.2GiB | 328742 | 5563281685 | 5564072005 |
| disk_after_load_bytes | 3 | 5.38506e+09 | 5.0GiB | 445559 | 5384447296 | 5385495872 |
| disk_after_queries_bytes | 3 | 5.56372e+09 | 5.2GiB | 328742 | 5563281685 | 5564072005 |
| disk_usage.du_bytes | 3 | 5.564e+09 | 5.2GiB | 329150 | 5563559936 | 5564350464 |
| index.total_s | 3 | 2.69653 |  | 0.711603 | 2.00982 | 3.67698 |
| load.total_s | 3 | 137.644 |  | 3.76894 | 133.33 | 142.512 |
| queries.total_s | 3 | 0.22085 |  | 0.032722 | 0.177315 | 0.256204 |
| query_cold_time_s | 3 | 0.0039487 |  | 0.000746096 | 0.00289452 | 0.00451467 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.00195731 |  | 0.000284099 | 0.001603 | 0.00229852 |
| rss_client_peak_kb | 3 | 3.14238e+06 | 3.0GiB | 121885 | 3053636 | 3314728 |
| rss_peak_kb | 3 | 3.14238e+06 | 3.0GiB | 121885 | 3053636 | 3314728 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.0925238 |  | 0.00397507 | 0.0873618 | 0.0970328 |
| seed | 3 | 6 |  | 3.26599 | 2 | 10 |
| table_counts.after_load.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_load.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_load.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_load.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_load.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_load.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_load.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_load.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.after_queries.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_queries.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_queries.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_queries.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_queries.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_queries.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_queries.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_queries.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.counts_time_s | 3 | 0.0017186 |  | 0.000101123 | 0.00162888 | 0.0018599 |
| table_counts.load_counts_time_s | 3 | 0.0060509 |  | 0.00371267 | 0.00243664 | 0.0111563 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 140.928 |  | 4.43923 | 135.935 | 146.72 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: postgresql (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| disk_after_index_bytes | 3 | 3372983619 | 3.1GiB | 34755.7 | 3372959043 | 3373032771 |
| disk_after_load_bytes | 3 | 3.20799e+09 | 3.0GiB | 3.16702e+07 | 3185591619 | 3252774211 |
| disk_after_queries_bytes | 3 | 3.40095e+09 | 3.2GiB | 3.9579e+07 | 3372967235 | 3456927043 |
| disk_usage.du_bytes | 3 | 3.37343e+09 | 3.1GiB | 42610.7 | 3373391872 | 3373486080 |
| index.total_s | 3 | 12.3155 |  | 0.544742 | 11.733 | 13.0434 |
| load.total_s | 3 | 147.415 |  | 4.18374 | 142.066 | 152.279 |
| queries.total_s | 3 | 6.72364 |  | 1.26602 | 5.07483 | 8.15242 |
| query_cold_time_s | 3 | 0.0436037 |  | 0.00763548 | 0.0370066 | 0.0543056 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.0697878 |  | 0.0133267 | 0.0522088 | 0.0844625 |
| rss_client_peak_kb | 3 | 66657.3 | 65.1MiB | 146.436 | 66456 | 66800 |
| rss_peak_kb | 3 | 1.29082e+06 | 1.2GiB | 28325 | 1270368 | 1330872 |
| rss_server_peak_kb | 3 | 1226396 | 1.2GiB | 29909.5 | 1204856 | 1268692 |
| schema.total_s | 3 | 0.0149102 |  | 0.00787762 | 0.00898552 | 0.0260432 |
| seed | 3 | 7 |  | 3.26599 | 3 | 11 |
| table_counts.after_load.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_load.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_load.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_load.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_load.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_load.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_load.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_load.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.after_queries.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_queries.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_queries.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_queries.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_queries.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_queries.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_queries.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_queries.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.counts_time_s | 3 | 0.218448 |  | 0.0392134 | 0.189852 | 0.273895 |
| table_counts.load_counts_time_s | 3 | 8.27388 |  | 0.284915 | 7.88348 | 8.55543 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 177.706 |  | 5.72928 | 172.064 | 185.563 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: sqlite (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| disk_after_index_bytes | 3 | 2908622848 | 2.7GiB | 0 | 2908622848 | 2908622848 |
| disk_after_load_bytes | 3 | 2755674112 | 2.6GiB | 0 | 2755674112 | 2755674112 |
| disk_after_queries_bytes | 3 | 2908622848 | 2.7GiB | 0 | 2908622848 | 2908622848 |
| disk_usage.du_bytes | 3 | 2908651520 | 2.7GiB | 0 | 2908651520 | 2908651520 |
| index.total_s | 3 | 6.40118 |  | 0.935423 | 5.07924 | 7.10558 |
| load.total_s | 3 | 80.5031 |  | 5.86337 | 76.2857 | 88.7947 |
| queries.total_s | 3 | 4.9064 |  | 0.205714 | 4.61636 | 5.07108 |
| query_cold_time_s | 3 | 0.0485219 |  | 0.00175322 | 0.0460425 | 0.0497706 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_warm_mean_s | 3 | 0.0490538 |  | 0.00209285 | 0.0461047 | 0.0507452 |
| rss_client_peak_kb | 3 | 50705.3 | 49.5MiB | 297.659 | 50304 | 51016 |
| rss_peak_kb | 3 | 50705.3 | 49.5MiB | 297.659 | 50304 | 51016 |
| rss_server_peak_kb | 3 | 0 | 0.0B | 0 | 0 | 0 |
| schema.total_s | 3 | 0.235074 |  | 0.00182542 | 0.232628 | 0.237012 |
| seed | 3 | 5 |  | 3.26599 | 1 | 9 |
| table_counts.after_load.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_load.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_load.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_load.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_load.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_load.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_load.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_load.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.after_queries.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| table_counts.after_queries.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| table_counts.after_queries.Post | 3 | 425735 |  | 0 | 425735 | 425735 |
| table_counts.after_queries.PostHistory | 3 | 1525713 |  | 0 | 1525713 | 1525713 |
| table_counts.after_queries.PostLink | 3 | 86919 |  | 0 | 86919 | 86919 |
| table_counts.after_queries.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| table_counts.after_queries.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| table_counts.after_queries.Vote | 3 | 1747225 |  | 0 | 1747225 | 1747225 |
| table_counts.counts_time_s | 3 | 0.0137777 |  | 0.00126399 | 0.0120108 | 0.0148957 |
| table_counts.load_counts_time_s | 3 | 1.02 |  | 0.6108 | 0.580258 | 1.88375 |
| table_schema.Badge.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Comment.column_count | 3 | 6 |  | 0 | 6 | 6 |
| table_schema.Post.column_count | 3 | 20 |  | 0 | 20 | 20 |
| table_schema.PostHistory.column_count | 3 | 10 |  | 0 | 10 | 10 |
| table_schema.PostLink.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.Tag.column_count | 3 | 5 |  | 0 | 5 | 5 |
| table_schema.User.column_count | 3 | 12 |  | 0 | 12 | 12 |
| table_schema.Vote.column_count | 3 | 6 |  | 0 | 6 | 6 |
| total_time_s | 3 | 93.0808 |  | 6.7639 | 87.2622 | 102.565 |

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
| elapsed_max_s | 3 | 2.92079 |  | 0.393095 | 2.4324 | 3.39497 |
| elapsed_mean_s | 3 | 1.54683 |  | 0.299321 | 1.3221 | 1.96986 |
| elapsed_min_s | 3 | 1.05865 |  | 0.259133 | 0.802051 | 1.41354 |
| elapsed_s | 3 | 1.39763 |  | 0.351335 | 1.14497 | 1.89447 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### arcadedb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 7

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 2.08318 |  | 0.624346 | 1.27189 | 2.7906 |
| elapsed_mean_s | 3 | 1.26341 |  | 0.225077 | 0.946242 | 1.44527 |
| elapsed_min_s | 3 | 0.882705 |  | 0.0993974 | 0.776772 | 1.01569 |
| elapsed_s | 3 | 1.25563 |  | 0.221424 | 0.960538 | 1.49391 |
| row_count | 3 | 7 |  | 0 | 7 | 7 |

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
| elapsed_max_s | 3 | 72.8374 |  | 47.9122 | 35.3605 | 140.463 |
| elapsed_mean_s | 3 | 32.8623 |  | 15.2724 | 20.9116 | 54.4183 |
| elapsed_min_s | 3 | 15.1979 |  | 6.59245 | 7.84589 | 23.8389 |
| elapsed_s | 3 | 28.088 |  | 8.40783 | 20.1355 | 39.7197 |
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
| elapsed_max_s | 3 | 0.36274 |  | 0.120205 | 0.197852 | 0.480999 |
| elapsed_mean_s | 3 | 0.156248 |  | 0.0314641 | 0.118799 | 0.195785 |
| elapsed_min_s | 3 | 0.0985154 |  | 0.0111068 | 0.0871174 | 0.113574 |
| elapsed_s | 3 | 0.122819 |  | 0.0173081 | 0.107597 | 0.14703 |
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
| elapsed_max_s | 3 | 4.06539 |  | 2.28478 | 1.60176 | 7.10779 |
| elapsed_mean_s | 3 | 1.91178 |  | 1.25018 | 0.841408 | 3.66564 |
| elapsed_min_s | 3 | 0.382881 |  | 0.0367402 | 0.343106 | 0.43172 |
| elapsed_s | 3 | 1.97626 |  | 1.80705 | 0.581009 | 4.5281 |
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
| elapsed_max_s | 3 | 1.18538 |  | 0.461349 | 0.556871 | 1.65129 |
| elapsed_mean_s | 3 | 0.598675 |  | 0.105778 | 0.460091 | 0.716746 |
| elapsed_min_s | 3 | 0.395431 |  | 0.0223771 | 0.36529 | 0.418854 |
| elapsed_s | 3 | 0.503568 |  | 0.0575323 | 0.456086 | 0.584528 |
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
| elapsed_max_s | 3 | 4.75432 |  | 3.89912 | 0.78017 | 10.0519 |
| elapsed_mean_s | 3 | 1.83928 |  | 1.20753 | 0.625064 | 3.48632 |
| elapsed_min_s | 3 | 0.394427 |  | 0.0309099 | 0.365338 | 0.437229 |
| elapsed_s | 3 | 2.06277 |  | 1.54651 | 0.678957 | 4.22142 |
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
| elapsed_max_s | 3 | 0.0129368 |  | 0.00619898 | 0.00508928 | 0.0202448 |
| elapsed_mean_s | 3 | 0.00420454 |  | 0.00144157 | 0.0025692 | 0.00607646 |
| elapsed_min_s | 3 | 0.0019474 |  | 0.000118032 | 0.00179076 | 0.00207567 |
| elapsed_s | 3 | 0.00244776 |  | 0.000350875 | 0.00215697 | 0.00294137 |
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
| elapsed_max_s | 3 | 1.09088 |  | 0.450482 | 0.526328 | 1.62882 |
| elapsed_mean_s | 3 | 0.547308 |  | 0.0812449 | 0.442506 | 0.640496 |
| elapsed_min_s | 3 | 0.400393 |  | 0.0374811 | 0.372484 | 0.453374 |
| elapsed_s | 3 | 0.472508 |  | 0.0251239 | 0.452054 | 0.507895 |
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
| elapsed_max_s | 3 | 3.8506 |  | 1.22248 | 2.19175 | 5.10174 |
| elapsed_mean_s | 3 | 2.60424 |  | 0.405225 | 2.03324 | 2.93191 |
| elapsed_min_s | 3 | 2.051 |  | 0.208577 | 1.80437 | 2.31445 |
| elapsed_s | 3 | 2.44988 |  | 0.323442 | 2.09486 | 2.87717 |
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
| elapsed_max_s | 3 | 0.0137231 |  | 0.00404512 | 0.00800443 | 0.0167143 |
| elapsed_mean_s | 3 | 0.00745473 |  | 0.00103113 | 0.00599651 | 0.00819137 |
| elapsed_min_s | 3 | 0.0053134 |  | 0.000581851 | 0.00455856 | 0.00597453 |
| elapsed_s | 3 | 0.00617965 |  | 0.000301038 | 0.00584149 | 0.00657272 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### duckdb :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 7

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00128452 |  | 9.34447e-05 | 0.00115585 | 0.00137496 |
| elapsed_mean_s | 3 | 0.000885224 |  | 4.46679e-05 | 0.000826049 | 0.000933957 |
| elapsed_min_s | 3 | 0.000742118 |  | 3.67306e-05 | 0.000691414 | 0.000777245 |
| elapsed_s | 3 | 0.000848373 |  | 5.57666e-05 | 0.00078702 | 0.000921965 |
| row_count | 3 | 7 |  | 0 | 7 | 7 |

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
| elapsed_max_s | 3 | 0.00136932 |  | 0.000194466 | 0.00112534 | 0.00160122 |
| elapsed_mean_s | 3 | 0.00104415 |  | 7.99828e-05 | 0.000943017 | 0.00113859 |
| elapsed_min_s | 3 | 0.000888189 |  | 8.14088e-05 | 0.000786781 | 0.000986099 |
| elapsed_s | 3 | 0.00102576 |  | 8.68719e-05 | 0.00090766 | 0.00111413 |
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
| elapsed_max_s | 3 | 0.00106239 |  | 0.000299024 | 0.000642538 | 0.00131607 |
| elapsed_mean_s | 3 | 0.000744605 |  | 0.000125894 | 0.000603962 | 0.000909472 |
| elapsed_min_s | 3 | 0.000574668 |  | 4.149e-05 | 0.000533819 | 0.000631571 |
| elapsed_s | 3 | 0.000699997 |  | 8.54752e-05 | 0.000619173 | 0.000818253 |
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
| elapsed_max_s | 3 | 0.00359162 |  | 0.000625979 | 0.00270653 | 0.00404954 |
| elapsed_mean_s | 3 | 0.00177797 |  | 0.000212998 | 0.0014884 | 0.00199461 |
| elapsed_min_s | 3 | 0.00129382 |  | 8.49291e-05 | 0.0011754 | 0.00137043 |
| elapsed_s | 3 | 0.00154916 |  | 0.000108157 | 0.00141215 | 0.00167656 |
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
| elapsed_max_s | 3 | 0.0116838 |  | 0.00587936 | 0.00549769 | 0.0195882 |
| elapsed_mean_s | 3 | 0.00331465 |  | 0.00174822 | 0.00157483 | 0.00570581 |
| elapsed_min_s | 3 | 0.000893354 |  | 7.48743e-05 | 0.00079298 | 0.000972748 |
| elapsed_s | 3 | 0.00113511 |  | 0.000109553 | 0.00100517 | 0.00127316 |
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
| elapsed_max_s | 3 | 0.00289385 |  | 0.000743721 | 0.00193405 | 0.00374627 |
| elapsed_mean_s | 3 | 0.00165496 |  | 0.000111708 | 0.00154111 | 0.00180674 |
| elapsed_min_s | 3 | 0.00128794 |  | 8.48603e-05 | 0.0011909 | 0.00139761 |
| elapsed_s | 3 | 0.00156109 |  | 7.83611e-05 | 0.0014503 | 0.00161886 |
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
| elapsed_max_s | 3 | 0.000551701 |  | 0.000124784 | 0.000376225 | 0.000655651 |
| elapsed_mean_s | 3 | 0.000413386 |  | 5.65897e-05 | 0.000347233 | 0.000485468 |
| elapsed_min_s | 3 | 0.000333389 |  | 2.03438e-05 | 0.000318766 | 0.000362158 |
| elapsed_s | 3 | 0.000412305 |  | 7.55395e-05 | 0.000339508 | 0.000516415 |
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
| elapsed_max_s | 3 | 0.0066874 |  | 0.00380659 | 0.00361013 | 0.0120513 |
| elapsed_mean_s | 3 | 0.00228634 |  | 0.000456752 | 0.00188663 | 0.00292563 |
| elapsed_min_s | 3 | 0.00149806 |  | 3.95738e-05 | 0.0014689 | 0.00155401 |
| elapsed_s | 3 | 0.0017786 |  | 0.000131175 | 0.0016458 | 0.00195718 |
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
| elapsed_max_s | 3 | 0.0083669 |  | 0.00355967 | 0.0033524 | 0.0112588 |
| elapsed_mean_s | 3 | 0.00198851 |  | 0.000365308 | 0.00149183 | 0.00235996 |
| elapsed_min_s | 3 | 0.00112065 |  | 7.1185e-05 | 0.00102019 | 0.0011766 |
| elapsed_s | 3 | 0.00128031 |  | 8.5819e-05 | 0.00116372 | 0.00136781 |
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
| elapsed_max_s | 3 | 1.68896 |  | 0.372119 | 1.33297 | 2.20261 |
| elapsed_mean_s | 3 | 0.417831 |  | 0.119626 | 0.270555 | 0.563566 |
| elapsed_min_s | 3 | 0.148021 |  | 0.00084474 | 0.1469 | 0.148939 |
| elapsed_s | 3 | 0.171867 |  | 0.0209768 | 0.155334 | 0.201465 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### postgresql :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 7

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0312331 |  | 0.00546925 | 0.0237384 | 0.0366361 |
| elapsed_mean_s | 3 | 0.0262978 |  | 0.00311642 | 0.0223416 | 0.029958 |
| elapsed_min_s | 3 | 0.0226223 |  | 0.00243751 | 0.0206709 | 0.0260589 |
| elapsed_s | 3 | 0.025608 |  | 0.00347315 | 0.0222549 | 0.0303929 |
| row_count | 3 | 7 |  | 0 | 7 | 7 |

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
| elapsed_max_s | 3 | 0.130895 |  | 0.0206405 | 0.106735 | 0.157162 |
| elapsed_mean_s | 3 | 0.102972 |  | 0.0078289 | 0.0965999 | 0.113999 |
| elapsed_min_s | 3 | 0.0880527 |  | 0.00355058 | 0.083169 | 0.0915055 |
| elapsed_s | 3 | 0.102507 |  | 0.00715717 | 0.0970287 | 0.112617 |
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
| elapsed_max_s | 3 | 0.00896621 |  | 0.00174066 | 0.00735283 | 0.0113831 |
| elapsed_mean_s | 3 | 0.00705496 |  | 0.000422865 | 0.0067251 | 0.00765188 |
| elapsed_min_s | 3 | 0.00601776 |  | 6.49626e-05 | 0.00593042 | 0.00608611 |
| elapsed_s | 3 | 0.00695984 |  | 7.08124e-05 | 0.00690484 | 0.00705981 |
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
| elapsed_max_s | 3 | 0.00196973 |  | 0.00206802 | 0.000370979 | 0.00488997 |
| elapsed_mean_s | 3 | 0.000519252 |  | 0.000309876 | 0.00027597 | 0.000956559 |
| elapsed_min_s | 3 | 0.000172933 |  | 7.41295e-05 | 0.000104189 | 0.00027585 |
| elapsed_s | 3 | 0.000381311 |  | 8.03979e-05 | 0.0002985 | 0.000490189 |
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
| elapsed_max_s | 3 | 0.112258 |  | 0.100075 | 0.0375564 | 0.25371 |
| elapsed_mean_s | 3 | 0.0407332 |  | 0.00876137 | 0.0333025 | 0.0530353 |
| elapsed_min_s | 3 | 0.0301167 |  | 0.000439284 | 0.0295544 | 0.0306265 |
| elapsed_s | 3 | 0.0325786 |  | 0.00106174 | 0.0310838 | 0.0334489 |
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
| elapsed_max_s | 3 | 0.00340366 |  | 0.00365353 | 0.000437975 | 0.00855064 |
| elapsed_mean_s | 3 | 0.000649651 |  | 0.000385454 | 0.000298142 | 0.00118623 |
| elapsed_min_s | 3 | 0.000132243 |  | 1.94106e-05 | 0.000104904 | 0.000148058 |
| elapsed_s | 3 | 0.000361363 |  | 2.49269e-05 | 0.000326157 | 0.000380516 |
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
| elapsed_max_s | 3 | 0.000843445 |  | 0.000151404 | 0.000650406 | 0.00102019 |
| elapsed_mean_s | 3 | 0.000444269 |  | 2.43955e-05 | 0.000409913 | 0.000464177 |
| elapsed_min_s | 3 | 0.000250181 |  | 8.71089e-06 | 0.000243902 | 0.000262499 |
| elapsed_s | 3 | 0.000434558 |  | 1.31027e-05 | 0.00041604 | 0.000444412 |
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
| elapsed_max_s | 3 | 0.00242019 |  | 0.00235029 | 0.000408888 | 0.00571752 |
| elapsed_mean_s | 3 | 0.000527589 |  | 0.000235629 | 0.000300241 | 0.000852251 |
| elapsed_min_s | 3 | 0.000199477 |  | 1.87855e-05 | 0.000183105 | 0.000225782 |
| elapsed_s | 3 | 0.00032417 |  | 3.60137e-05 | 0.00029254 | 0.000374556 |
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
| elapsed_max_s | 3 | 0.220159 |  | 0.214658 | 0.0575221 | 0.523466 |
| elapsed_mean_s | 3 | 0.0746646 |  | 0.0212316 | 0.0562472 | 0.10441 |
| elapsed_min_s | 3 | 0.0549515 |  | 0.000373145 | 0.0546403 | 0.0554762 |
| elapsed_s | 3 | 0.0584084 |  | 0.00167638 | 0.0563061 | 0.0604086 |
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
| elapsed_max_s | 3 | 0.0438776 |  | 0.000376014 | 0.043381 | 0.0442905 |
| elapsed_mean_s | 3 | 0.0419097 |  | 0.000537717 | 0.04135 | 0.0426354 |
| elapsed_min_s | 3 | 0.0405794 |  | 0.000569198 | 0.0401182 | 0.0413814 |
| elapsed_s | 3 | 0.0416723 |  | 0.000752223 | 0.0410638 | 0.0427322 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### sqlite :: post_type_counts (samples=3)

- Hash stable: True
- Row counts: 7

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0120622 |  | 0.000384423 | 0.0117521 | 0.012604 |
| elapsed_mean_s | 3 | 0.0114837 |  | 0.000201236 | 0.0112483 | 0.0117399 |
| elapsed_min_s | 3 | 0.01085 |  | 0.0003085 | 0.0106134 | 0.0112858 |
| elapsed_s | 3 | 0.0115724 |  | 0.000131408 | 0.0114005 | 0.0117195 |
| row_count | 3 | 7 |  | 0 | 7 | 7 |

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
| elapsed_max_s | 3 | 0.0427533 |  | 0.00139646 | 0.0413754 | 0.0446675 |
| elapsed_mean_s | 3 | 0.0402072 |  | 0.000958473 | 0.0391054 | 0.0414419 |
| elapsed_min_s | 3 | 0.0377058 |  | 0.000954871 | 0.0367689 | 0.0390165 |
| elapsed_s | 3 | 0.0406641 |  | 0.00044548 | 0.0401714 | 0.0412505 |
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
| elapsed_max_s | 3 | 0.00247955 |  | 3.59198e-05 | 0.00243592 | 0.0025239 |
| elapsed_mean_s | 3 | 0.00236266 |  | 3.66385e-05 | 0.00232728 | 0.00241313 |
| elapsed_min_s | 3 | 0.00219957 |  | 6.31146e-05 | 0.0021441 | 0.00228786 |
| elapsed_s | 3 | 0.002376 |  | 1.72743e-05 | 0.00236273 | 0.0024004 |
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
| elapsed_max_s | 3 | 0.170438 |  | 0.00967131 | 0.156874 | 0.17874 |
| elapsed_mean_s | 3 | 0.162046 |  | 0.0111387 | 0.146303 | 0.170396 |
| elapsed_min_s | 3 | 0.156689 |  | 0.0116313 | 0.140249 | 0.165384 |
| elapsed_s | 3 | 0.162159 |  | 0.0112965 | 0.146186 | 0.170392 |
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
| elapsed_max_s | 3 | 0.0215893 |  | 0.000564699 | 0.020823 | 0.0221672 |
| elapsed_mean_s | 3 | 0.0205041 |  | 0.000567952 | 0.0200003 | 0.0212977 |
| elapsed_min_s | 3 | 0.0198472 |  | 0.000874197 | 0.018832 | 0.0209658 |
| elapsed_s | 3 | 0.0203684 |  | 0.000611567 | 0.0197771 | 0.0212107 |
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
| elapsed_max_s | 3 | 0.173709 |  | 0.0115494 | 0.15829 | 0.186085 |
| elapsed_mean_s | 3 | 0.164512 |  | 0.0112939 | 0.148658 | 0.174117 |
| elapsed_min_s | 3 | 0.158449 |  | 0.0114217 | 0.142296 | 0.166528 |
| elapsed_s | 3 | 0.164912 |  | 0.0102719 | 0.150465 | 0.173455 |
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
| elapsed_max_s | 3 | 0.0002412 |  | 7.75671e-05 | 0.00018096 | 0.000350714 |
| elapsed_mean_s | 3 | 0.000149139 |  | 1.14536e-05 | 0.000138068 | 0.000164914 |
| elapsed_min_s | 3 | 0.000112851 |  | 2.2813e-06 | 0.000109673 | 0.000114918 |
| elapsed_s | 3 | 0.000145515 |  | 8.27358e-06 | 0.000135422 | 0.000155687 |
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
| elapsed_max_s | 3 | 0.000134786 |  | 1.70079e-06 | 0.000133038 | 0.000137091 |
| elapsed_mean_s | 3 | 9.26336e-05 |  | 1.77675e-06 | 9.0313e-05 | 9.46283e-05 |
| elapsed_min_s | 3 | 6.99361e-05 |  | 1.65563e-06 | 6.79493e-05 | 7.20024e-05 |
| elapsed_s | 3 | 8.83738e-05 |  | 3.04289e-06 | 8.44002e-05 | 9.17912e-05 |
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
| elapsed_max_s | 3 | 0.0488073 |  | 0.000805317 | 0.0477524 | 0.0497065 |
| elapsed_mean_s | 3 | 0.0467397 |  | 0.000652829 | 0.0458323 | 0.0473406 |
| elapsed_min_s | 3 | 0.04424 |  | 0.000863288 | 0.0430434 | 0.045048 |
| elapsed_s | 3 | 0.0468725 |  | 0.000622704 | 0.0460176 | 0.0474832 |
| row_count | 3 | 14 |  | 0 | 14 | 14 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

## Cross-DB Query Result Hash Checks

| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | All Hashes |
|---|---:|---|---|---|---|
| most_commented_posts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 |
| post_type_counts | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b |
| posthistory_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b |
| postlinks_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 |
| top_answers_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 |
| top_badges | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 |
| top_questions_by_score | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce |
| top_tags_by_count | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf |
| top_users_by_reputation | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 |
| votes_by_type | 12 | arcadedb, duckdb, postgresql, sqlite |  | True | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c |

### most_commented_posts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 | True |
| duckdb | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 | True |
| postgresql | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 | True |
| sqlite | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 | True |

### post_type_counts

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b | True |
| duckdb | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b | True |
| postgresql | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b | True |
| sqlite | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b | True |

### posthistory_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b | True |
| duckdb | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b | True |
| postgresql | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b | True |
| sqlite | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b | True |

### postlinks_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 | True |
| duckdb | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 | True |
| postgresql | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 | True |
| sqlite | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 | True |

### top_answers_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 | True |
| duckdb | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 | True |
| postgresql | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 | True |
| sqlite | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 | True |

### top_badges

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 | True |
| duckdb | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 | True |
| postgresql | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 | True |
| sqlite | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 | True |

### top_questions_by_score

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce | True |
| duckdb | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce | True |
| postgresql | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce | True |
| sqlite | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce | True |

### top_tags_by_count

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf | True |
| duckdb | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf | True |
| postgresql | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf | True |
| sqlite | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf | True |

### top_users_by_reputation

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 | True |
| duckdb | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 | True |
| postgresql | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 | True |
| sqlite | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 | True |

### votes_by_type

| DB | Hashes | Stable Within DB |
|---|---|---|
| arcadedb | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c | True |
| duckdb | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c | True |
| postgresql | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c | True |
| sqlite | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c | True |
