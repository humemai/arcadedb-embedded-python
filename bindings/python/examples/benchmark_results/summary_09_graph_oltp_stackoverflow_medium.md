# 09 Graph OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:11Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep09
- Total runs: 7

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 5000 |
| dataset | stackoverflow-medium |
| db | arcadedb, ladybug |
| docker_image | python:3.12-slim |
| heap_size | 3276m, 4g |
| ladybug_version | 0.14.1 |
| mem_limit | 4g |
| run_label | sweep09_t01_r01_arcadedb_s00000, sweep09_t01_r01_ladybug_s00001, sweep09_t01_r02_arcadedb_s00002, sweep09_t01_r02_ladybug_s00003, sweep09_t01_r03_arcadedb_s00004, sweep09_t01_r03_ladybug_s00005, sweep09_t08_r01_arcadedb_s00000 |
| seed | 0, 1, 2, 3, 4, 5 |
| threads | 1, 8 |
| transactions | 10000, 100000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 25.1693 |  | 6.04334 | 17.2708 | 31.9457 |
| disk_after_load_bytes | 3 | 1465545310 | 1.4GiB | 4.18446e+07 | 1425361911 | 1523259174 |
| disk_after_oltp_bytes | 3 | 1.45938e+09 | 1.4GiB | 4.08016e+07 | 1415237713 | 1513633079 |
| disk_usage.du_bytes | 3 | 1405333504 | 1.3GiB | 150608 | 1405227008 | 1405546496 |
| edge_count | 3 | 2.60822e+06 |  | 15694.2 | 2586028 | 2619693 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 72300.7 |  | 71.0602 | 72203 | 72370 |
| edge_counts_by_type.ANSWERED | 3 | 206838 |  | 114.788 | 206676 | 206920 |
| edge_counts_by_type.ASKED | 3 | 210234 |  | 110.243 | 210078 | 210319 |
| edge_counts_by_type.COMMENTED_ON | 3 | 474124 |  | 23.1132 | 474107 | 474157 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 342949 |  | 38.5775 | 342914 | 343003 |
| edge_counts_by_type.EARNED | 3 | 610677 |  | 105.152 | 610562 | 610816 |
| edge_counts_by_type.HAS_ANSWER | 3 | 208482 |  | 29.7097 | 208440 | 208504 |
| edge_counts_by_type.LINKED_TO | 3 | 86221 |  | 81.2034 | 86140 | 86332 |
| edge_counts_by_type.TAGGED_WITH | 3 | 396393 |  | 15565 | 374381 | 407528 |
| latency_summary.ops.delete.50 | 3 | 0.00182208 |  | 0.000315627 | 0.00150818 | 0.00225386 |
| latency_summary.ops.delete.95 | 3 | 0.0382469 |  | 0.00345629 | 0.0338997 | 0.0423557 |
| latency_summary.ops.delete.99 | 3 | 0.137421 |  | 0.0151147 | 0.116053 | 0.148591 |
| latency_summary.ops.insert.50 | 3 | 0.000906643 |  | 6.88266e-05 | 0.000815353 | 0.000981533 |
| latency_summary.ops.insert.95 | 3 | 0.0216379 |  | 0.000476363 | 0.0209764 | 0.0220791 |
| latency_summary.ops.insert.99 | 3 | 0.0305795 |  | 0.00141136 | 0.0287486 | 0.0321832 |
| latency_summary.ops.read.50 | 3 | 0.000571998 |  | 4.40881e-05 | 0.000509661 | 0.000604272 |
| latency_summary.ops.read.95 | 3 | 0.002728 |  | 0.000625696 | 0.00205307 | 0.00356104 |
| latency_summary.ops.read.99 | 3 | 0.00672787 |  | 0.00185121 | 0.00508898 | 0.00931537 |
| latency_summary.ops.update.50 | 3 | 0.000255587 |  | 1.78871e-05 | 0.00023562 | 0.000279021 |
| latency_summary.ops.update.95 | 3 | 0.00329537 |  | 0.000154692 | 0.00310173 | 0.00348035 |
| latency_summary.ops.update.99 | 3 | 0.00637718 |  | 0.000812357 | 0.00571203 | 0.00752097 |
| latency_summary.overall.50 | 3 | 0.000597089 |  | 4.91276e-05 | 0.000528512 | 0.000641032 |
| latency_summary.overall.95 | 3 | 0.00774627 |  | 0.00119317 | 0.00637917 | 0.00928642 |
| latency_summary.overall.99 | 3 | 0.0300266 |  | 0.00225844 | 0.0272786 | 0.0328103 |
| load_counts_time_s | 3 | 33.5528 |  | 10.2615 | 25.3024 | 48.017 |
| load_edge_count | 3 | 2877037 |  | 0 | 2877037 | 2877037 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 71547 |  | 0 | 71547 | 71547 |
| load_edge_counts_by_type.ANSWERED | 3 | 206435 |  | 0 | 206435 | 206435 |
| load_edge_counts_by_type.ASKED | 3 | 210226 |  | 0 | 210226 | 210226 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 475470 |  | 0 | 475470 | 475470 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 344052 |  | 0 | 344052 | 344052 |
| load_edge_counts_by_type.EARNED | 3 | 612258 |  | 0 | 612258 | 612258 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 208986 |  | 0 | 208986 | 208986 |
| load_edge_counts_by_type.LINKED_TO | 3 | 85669 |  | 0 | 85669 | 85669 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 662394 |  | 0 | 662394 | 662394 |
| load_node_count | 3 | 2202019 |  | 0 | 2202019 | 2202019 |
| load_node_counts_by_type.Answer | 3 | 208986 |  | 0 | 208986 | 208986 |
| load_node_counts_by_type.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| load_node_counts_by_type.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| load_node_counts_by_type.Question | 3 | 213761 |  | 0 | 213761 | 213761 |
| load_node_counts_by_type.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| load_node_counts_by_type.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 52.0383 |  | 5.2613 | 44.9848 | 57.6163 |
| load_stats.edges.ANSWERED | 3 | 168.287 |  | 5.68247 | 163.195 | 176.217 |
| load_stats.edges.ASKED | 3 | 180.302 |  | 13.3387 | 168.828 | 199.006 |
| load_stats.edges.COMMENTED_ON | 3 | 628.128 |  | 13.1893 | 610.937 | 642.991 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 628.128 |  | 13.1893 | 610.937 | 642.991 |
| load_stats.edges.EARNED | 3 | 436.153 |  | 26.6247 | 398.69 | 458.158 |
| load_stats.edges.HAS_ANSWER | 3 | 152.149 |  | 11.0542 | 138.04 | 165.034 |
| load_stats.edges.LINKED_TO | 3 | 67.7709 |  | 7.86669 | 61.9544 | 78.8921 |
| load_stats.edges.TAGGED_WITH | 3 | 447.163 |  | 14.597 | 435.547 | 467.75 |
| load_stats.nodes.Badge | 3 | 352.611 |  | 14.1447 | 333.721 | 367.756 |
| load_stats.nodes.Comment | 3 | 503.951 |  | 7.37364 | 498.171 | 514.358 |
| load_stats.nodes.Post | 3 | 519.606 |  | 45.4624 | 456.639 | 562.341 |
| load_stats.nodes.Tag | 3 | 8.6953 |  | 5.60715 | 2.32457 | 15.9697 |
| load_stats.nodes.User | 3 | 315.518 |  | 21.6957 | 297.327 | 346.012 |
| load_time_s | 3 | 3832.45 |  | 64.7167 | 3746.34 | 3902.36 |
| node_count | 3 | 2.20521e+06 |  | 34.3058 | 2205168 | 2205252 |
| node_counts_by_type.Answer | 3 | 209751 |  | 30.0925 | 209723 | 209793 |
| node_counts_by_type.Badge | 3 | 612988 |  | 36.4265 | 612945 | 613034 |
| node_counts_by_type.Comment | 3 | 820428 |  | 23.2809 | 820400 | 820457 |
| node_counts_by_type.Question | 3 | 214558 |  | 19.3964 | 214531 | 214574 |
| node_counts_by_type.Tag | 3 | 950.333 |  | 12.3918 | 934 | 964 |
| node_counts_by_type.User | 3 | 346534 |  | 34.8839 | 346509 | 346583 |
| op_counts.delete | 3 | 10039.3 |  | 23.1565 | 10021 | 10072 |
| op_counts.insert | 3 | 10015.7 |  | 70.4856 | 9916 | 10067 |
| op_counts.read | 3 | 59990 |  | 93.8545 | 59859 | 60074 |
| op_counts.update | 3 | 19955 |  | 173.299 | 19827 | 20200 |
| rss_peak_kb | 3 | 3.81479e+06 | 3.6GiB | 53909.7 | 3738624 | 3855716 |
| schema_time_s | 3 | 0.398174 |  | 0.280486 | 0.187364 | 0.794573 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 416.337 |  | 39.7912 | 366.873 | 464.307 |
| total_time_s | 3 | 242.426 |  | 23.4537 | 215.375 | 272.574 |
| transactions | 3 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=1)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 1 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 1 | 10.5801 |  | 0 | 10.5801 | 10.5801 |
| disk_after_load_bytes | 1 | 1566793494 | 1.5GiB | 0 | 1566793494 | 1566793494 |
| disk_after_oltp_bytes | 1 | 1625965424 | 1.5GiB | 0 | 1625965424 | 1625965424 |
| disk_usage.du_bytes | 1 | 1405227008 | 1.3GiB | 0 | 1405227008 | 1405227008 |
| edge_count | 1 | 2619882 |  | 0 | 2619882 | 2619882 |
| edge_counts_by_type.ACCEPTED_ANSWER | 1 | 72292 |  | 0 | 72292 | 72292 |
| edge_counts_by_type.ANSWERED | 1 | 206133 |  | 0 | 206133 | 206133 |
| edge_counts_by_type.ASKED | 1 | 210248 |  | 0 | 210248 | 210248 |
| edge_counts_by_type.COMMENTED_ON | 1 | 474190 |  | 0 | 474190 | 474190 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 1 | 342969 |  | 0 | 342969 | 342969 |
| edge_counts_by_type.EARNED | 1 | 610415 |  | 0 | 610415 | 610415 |
| edge_counts_by_type.HAS_ANSWER | 1 | 208459 |  | 0 | 208459 | 208459 |
| edge_counts_by_type.LINKED_TO | 1 | 86447 |  | 0 | 86447 | 86447 |
| edge_counts_by_type.TAGGED_WITH | 1 | 408729 |  | 0 | 408729 | 408729 |
| latency_summary.ops.delete.50 | 1 | 0.00282435 |  | 0 | 0.00282435 | 0.00282435 |
| latency_summary.ops.delete.95 | 1 | 0.0953474 |  | 0 | 0.0953474 | 0.0953474 |
| latency_summary.ops.delete.99 | 1 | 0.465904 |  | 0 | 0.465904 | 0.465904 |
| latency_summary.ops.insert.50 | 1 | 0.00114407 |  | 0 | 0.00114407 | 0.00114407 |
| latency_summary.ops.insert.95 | 1 | 0.0923384 |  | 0 | 0.0923384 | 0.0923384 |
| latency_summary.ops.insert.99 | 1 | 0.23348 |  | 0 | 0.23348 | 0.23348 |
| latency_summary.ops.read.50 | 1 | 0.000627532 |  | 0 | 0.000627532 | 0.000627532 |
| latency_summary.ops.read.95 | 1 | 0.007051 |  | 0 | 0.007051 | 0.007051 |
| latency_summary.ops.read.99 | 1 | 0.0231351 |  | 0 | 0.0231351 | 0.0231351 |
| latency_summary.ops.update.50 | 1 | 0.000287211 |  | 0 | 0.000287211 | 0.000287211 |
| latency_summary.ops.update.95 | 1 | 0.0263835 |  | 0 | 0.0263835 | 0.0263835 |
| latency_summary.ops.update.99 | 1 | 0.0779682 |  | 0 | 0.0779682 | 0.0779682 |
| latency_summary.overall.50 | 1 | 0.000632922 |  | 0 | 0.000632922 | 0.000632922 |
| latency_summary.overall.95 | 1 | 0.0264596 |  | 0 | 0.0264596 | 0.0264596 |
| latency_summary.overall.99 | 1 | 0.103693 |  | 0 | 0.103693 | 0.103693 |
| load_counts_time_s | 1 | 27.3308 |  | 0 | 27.3308 | 27.3308 |
| load_edge_count | 1 | 2877037 |  | 0 | 2877037 | 2877037 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 1 | 71547 |  | 0 | 71547 | 71547 |
| load_edge_counts_by_type.ANSWERED | 1 | 206435 |  | 0 | 206435 | 206435 |
| load_edge_counts_by_type.ASKED | 1 | 210226 |  | 0 | 210226 | 210226 |
| load_edge_counts_by_type.COMMENTED_ON | 1 | 475470 |  | 0 | 475470 | 475470 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 1 | 344052 |  | 0 | 344052 | 344052 |
| load_edge_counts_by_type.EARNED | 1 | 612258 |  | 0 | 612258 | 612258 |
| load_edge_counts_by_type.HAS_ANSWER | 1 | 208986 |  | 0 | 208986 | 208986 |
| load_edge_counts_by_type.LINKED_TO | 1 | 85669 |  | 0 | 85669 | 85669 |
| load_edge_counts_by_type.TAGGED_WITH | 1 | 662394 |  | 0 | 662394 | 662394 |
| load_node_count | 1 | 2202019 |  | 0 | 2202019 | 2202019 |
| load_node_counts_by_type.Answer | 1 | 208986 |  | 0 | 208986 | 208986 |
| load_node_counts_by_type.Badge | 1 | 612258 |  | 0 | 612258 | 612258 |
| load_node_counts_by_type.Comment | 1 | 819648 |  | 0 | 819648 | 819648 |
| load_node_counts_by_type.Question | 1 | 213761 |  | 0 | 213761 | 213761 |
| load_node_counts_by_type.Tag | 1 | 1612 |  | 0 | 1612 | 1612 |
| load_node_counts_by_type.User | 1 | 345754 |  | 0 | 345754 | 345754 |
| load_stats.edges.ACCEPTED_ANSWER | 1 | 40.6382 |  | 0 | 40.6382 | 40.6382 |
| load_stats.edges.ANSWERED | 1 | 131.109 |  | 0 | 131.109 | 131.109 |
| load_stats.edges.ASKED | 1 | 142.286 |  | 0 | 142.286 | 142.286 |
| load_stats.edges.COMMENTED_ON | 1 | 408.439 |  | 0 | 408.439 | 408.439 |
| load_stats.edges.COMMENTED_ON_ANSWER | 1 | 408.439 |  | 0 | 408.439 | 408.439 |
| load_stats.edges.EARNED | 1 | 314.775 |  | 0 | 314.775 | 314.775 |
| load_stats.edges.HAS_ANSWER | 1 | 119.986 |  | 0 | 119.986 | 119.986 |
| load_stats.edges.LINKED_TO | 1 | 50.4127 |  | 0 | 50.4127 | 50.4127 |
| load_stats.edges.TAGGED_WITH | 1 | 330.172 |  | 0 | 330.172 | 330.172 |
| load_stats.nodes.Badge | 1 | 322.405 |  | 0 | 322.405 | 322.405 |
| load_stats.nodes.Comment | 1 | 431.252 |  | 0 | 431.252 | 431.252 |
| load_stats.nodes.Post | 1 | 302.675 |  | 0 | 302.675 | 302.675 |
| load_stats.nodes.Tag | 1 | 14.1908 |  | 0 | 14.1908 | 14.1908 |
| load_stats.nodes.User | 1 | 170.608 |  | 0 | 170.608 | 170.608 |
| load_time_s | 1 | 2779.1 |  | 0 | 2779.1 | 2779.1 |
| node_count | 1 | 2205223 |  | 0 | 2205223 | 2205223 |
| node_counts_by_type.Answer | 1 | 209747 |  | 0 | 209747 | 209747 |
| node_counts_by_type.Badge | 1 | 612982 |  | 0 | 612982 | 612982 |
| node_counts_by_type.Comment | 1 | 820478 |  | 0 | 820478 | 820478 |
| node_counts_by_type.Question | 1 | 214561 |  | 0 | 214561 | 214561 |
| node_counts_by_type.Tag | 1 | 915 |  | 0 | 915 | 915 |
| node_counts_by_type.User | 1 | 346540 |  | 0 | 346540 | 346540 |
| op_counts.delete | 1 | 10021 |  | 0 | 10021 | 10021 |
| op_counts.insert | 1 | 10067 |  | 0 | 10067 | 10067 |
| op_counts.read | 1 | 60074 |  | 0 | 60074 | 60074 |
| op_counts.update | 1 | 19838 |  | 0 | 19838 | 19838 |
| rss_peak_kb | 1 | 3697380 | 3.5GiB | 0 | 3697380 | 3697380 |
| schema_time_s | 1 | 0.613273 |  | 0 | 0.613273 | 0.613273 |
| seed | 1 | 0 |  | 0 | 0 | 0 |
| threads | 1 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 1 | 720.793 |  | 0 | 720.793 | 720.793 |
| total_time_s | 1 | 138.736 |  | 0 | 138.736 | 138.736 |
| transactions | 1 | 100000 |  | 0 | 100000 | 100000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: ladybug, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.358508 |  | 0.0629419 | 0.269605 | 0.406788 |
| disk_after_load_bytes | 3 | 1906743850 | 1.8GiB | 31903.3 | 1906698794 | 1906768426 |
| disk_after_oltp_bytes | 3 | 1.90743e+09 | 1.8GiB | 22881.5 | 1907395233 | 1907446000 |
| disk_usage.du_bytes | 3 | 1.97185e+09 | 1.8GiB | 2.49208e+07 | 1936621568 | 1990352896 |
| edge_count | 3 | 2.84664e+06 |  | 4838.07 | 2840455 | 2852265 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 71636.3 |  | 8.37987 | 71625 | 71645 |
| edge_counts_by_type.ANSWERED | 3 | 206510 |  | 7.4087 | 206500 | 206518 |
| edge_counts_by_type.ASKED | 3 | 210279 |  | 20.2704 | 210251 | 210299 |
| edge_counts_by_type.COMMENTED_ON | 3 | 475366 |  | 51.0969 | 475295 | 475412 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 343965 |  | 46.5069 | 343904 | 344017 |
| edge_counts_by_type.EARNED | 3 | 612246 |  | 3.39935 | 612243 | 612251 |
| edge_counts_by_type.HAS_ANSWER | 3 | 209002 |  | 13.8884 | 208989 | 209021 |
| edge_counts_by_type.LINKED_TO | 3 | 85771 |  | 6.16441 | 85763 | 85778 |
| edge_counts_by_type.TAGGED_WITH | 3 | 631869 |  | 4741.81 | 625768 | 637330 |
| latency_summary.ops.delete.50 | 3 | 0.0258955 |  | 0.00601622 | 0.0186884 | 0.0334151 |
| latency_summary.ops.delete.95 | 3 | 0.0781687 |  | 0.00968761 | 0.0647106 | 0.0871191 |
| latency_summary.ops.delete.99 | 3 | 0.118013 |  | 0.0258648 | 0.0928028 | 0.153571 |
| latency_summary.ops.insert.50 | 3 | 0.0228854 |  | 0.00524774 | 0.0169668 | 0.0297223 |
| latency_summary.ops.insert.95 | 3 | 0.0375113 |  | 0.0137679 | 0.0239904 | 0.0564052 |
| latency_summary.ops.insert.99 | 3 | 0.10445 |  | 0.0401867 | 0.0649587 | 0.15959 |
| latency_summary.ops.read.50 | 3 | 0.00394658 |  | 0.000648287 | 0.00316526 | 0.00475265 |
| latency_summary.ops.read.95 | 3 | 0.0748911 |  | 0.00179729 | 0.0726607 | 0.077062 |
| latency_summary.ops.read.99 | 3 | 0.0907313 |  | 0.00072297 | 0.0897191 | 0.0913627 |
| latency_summary.ops.update.50 | 3 | 0.0225733 |  | 0.00539527 | 0.0166134 | 0.0296791 |
| latency_summary.ops.update.95 | 3 | 0.0377121 |  | 0.0164159 | 0.0217888 | 0.0603046 |
| latency_summary.ops.update.99 | 3 | 0.100915 |  | 0.0328853 | 0.0701054 | 0.14649 |
| latency_summary.overall.50 | 3 | 0.0150135 |  | 0.000690255 | 0.0144775 | 0.0159881 |
| latency_summary.overall.95 | 3 | 0.071148 |  | 0.00252545 | 0.0676686 | 0.0735856 |
| latency_summary.overall.99 | 3 | 0.0928462 |  | 0.00368064 | 0.0888482 | 0.0977318 |
| load_counts_time_s | 3 | 0.299964 |  | 0.0441366 | 0.254578 | 0.359767 |
| load_edge_count | 3 | 2877037 |  | 0 | 2877037 | 2877037 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 71547 |  | 0 | 71547 | 71547 |
| load_edge_counts_by_type.ANSWERED | 3 | 206435 |  | 0 | 206435 | 206435 |
| load_edge_counts_by_type.ASKED | 3 | 210226 |  | 0 | 210226 | 210226 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 475470 |  | 0 | 475470 | 475470 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 344052 |  | 0 | 344052 | 344052 |
| load_edge_counts_by_type.EARNED | 3 | 612258 |  | 0 | 612258 | 612258 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 208986 |  | 0 | 208986 | 208986 |
| load_edge_counts_by_type.LINKED_TO | 3 | 85669 |  | 0 | 85669 | 85669 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 662394 |  | 0 | 662394 | 662394 |
| load_node_count | 3 | 2202019 |  | 0 | 2202019 | 2202019 |
| load_node_counts_by_type.Answer | 3 | 208986 |  | 0 | 208986 | 208986 |
| load_node_counts_by_type.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| load_node_counts_by_type.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| load_node_counts_by_type.Question | 3 | 213761 |  | 0 | 213761 | 213761 |
| load_node_counts_by_type.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| load_node_counts_by_type.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.209502 |  | 0.0173355 | 0.193935 | 0.233688 |
| load_stats.edges.ANSWERED | 3 | 0.390385 |  | 0.0223584 | 0.362509 | 0.417248 |
| load_stats.edges.ASKED | 3 | 0.377592 |  | 0.0314759 | 0.346805 | 0.420829 |
| load_stats.edges.COMMENTED_ON | 3 | 0.954201 |  | 0.0549005 | 0.90758 | 1.03128 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.764667 |  | 0.053139 | 0.690141 | 0.810302 |
| load_stats.edges.EARNED | 3 | 1.22946 |  | 0.0416998 | 1.1793 | 1.2814 |
| load_stats.edges.HAS_ANSWER | 3 | 0.350424 |  | 0.0325488 | 0.311572 | 0.391228 |
| load_stats.edges.LINKED_TO | 3 | 0.276613 |  | 0.0615305 | 0.191632 | 0.335312 |
| load_stats.edges.TAGGED_WITH | 3 | 0.666564 |  | 0.0403572 | 0.614183 | 0.712382 |
| load_stats.nodes.Answer | 3 | 10.8054 |  | 0.457685 | 10.1617 | 11.1863 |
| load_stats.nodes.Badge | 3 | 0.621501 |  | 0.092886 | 0.519459 | 0.744162 |
| load_stats.nodes.Comment | 3 | 8.09285 |  | 1.37712 | 6.94255 | 10.029 |
| load_stats.nodes.Post | 3 | 19.1172 |  | 0.230544 | 18.7981 | 19.3347 |
| load_stats.nodes.Question | 3 | 8.31183 |  | 0.24858 | 8.03254 | 8.63637 |
| load_stats.nodes.Tag | 3 | 0.401167 |  | 0.070322 | 0.302481 | 0.461169 |
| load_stats.nodes.User | 3 | 1.20601 |  | 0.0989902 | 1.08243 | 1.32476 |
| load_time_s | 3 | 134.207 |  | 8.27036 | 124.356 | 144.593 |
| node_count | 3 | 2202346 |  | 55.1543 | 2202307 | 2202424 |
| node_counts_by_type.Answer | 3 | 209070 |  | 14.3372 | 209053 | 209088 |
| node_counts_by_type.Badge | 3 | 612326 |  | 7.54247 | 612315 | 612331 |
| node_counts_by_type.Comment | 3 | 819727 |  | 17.282 | 819711 | 819751 |
| node_counts_by_type.Question | 3 | 213839 |  | 14.8847 | 213819 | 213855 |
| node_counts_by_type.Tag | 3 | 1543 |  | 7.25718 | 1536 | 1553 |
| node_counts_by_type.User | 3 | 345842 |  | 15.7692 | 345825 | 345863 |
| op_counts.delete | 3 | 1027.67 |  | 6.84755 | 1018 | 1033 |
| op_counts.insert | 3 | 994 |  | 31.0161 | 960 | 1035 |
| op_counts.read | 3 | 6011.67 |  | 28.5346 | 5973 | 6041 |
| op_counts.update | 3 | 1966.67 |  | 52.9423 | 1906 | 2035 |
| rss_peak_kb | 3 | 2.75377e+06 | 2.6GiB | 103691 | 2647552 | 2894432 |
| schema_time_s | 3 | 0.200337 |  | 0.0579425 | 0.158012 | 0.282265 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 51.0985 |  | 6.73659 | 44.4977 | 60.3482 |
| total_time_s | 3 | 198.945 |  | 24.667 | 165.705 | 224.731 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
