# 09 Graph OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:11Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep09
- Total runs: 9

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 2500 |
| dataset | stackoverflow-small |
| db | arcadedb, ladybug |
| docker_image | python:3.12-slim |
| heap_size | 1638m, 2g |
| ladybug_version | 0.14.1 |
| mem_limit | 2g |
| run_label | sweep09_t01_r01_arcadedb_s00000, sweep09_t01_r01_ladybug_s00001, sweep09_t01_r02_arcadedb_s00002, sweep09_t01_r02_ladybug_s00003, sweep09_t01_r03_arcadedb_s00004, sweep09_t01_r03_ladybug_s00005, sweep09_t08_r01_arcadedb_s00000, sweep09_t08_r02_arcadedb_s00001, sweep09_t08_r03_arcadedb_s00002 |
| seed | 0, 1, 2, 3, 4, 5 |
| threads | 1, 8 |
| transactions | 5000, 50000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 2.09336 |  | 0.36997 | 1.57016 | 2.35878 |
| disk_after_load_bytes | 3 | 4.30968e+08 | 411.0MiB | 1.5108e+07 | 418687302 | 452250106 |
| disk_after_oltp_bytes | 3 | 3.96897e+08 | 378.5MiB | 2.76106e+07 | 369217134 | 434588063 |
| disk_usage.du_bytes | 3 | 330194944 | 314.9MiB | 28963.1 | 330153984 | 330215424 |
| edge_count | 3 | 634221 |  | 11331 | 624553 | 650122 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 22137.7 |  | 25.3815 | 22108 | 22170 |
| edge_counts_by_type.ANSWERED | 3 | 55259 |  | 41.8171 | 55200 | 55292 |
| edge_counts_by_type.ASKED | 3 | 47259 |  | 119.744 | 47093 | 47371 |
| edge_counts_by_type.COMMENTED_ON | 3 | 110085 |  | 95.9201 | 109989 | 110216 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84481.3 |  | 14.0554 | 84469 | 84501 |
| edge_counts_by_type.EARNED | 3 | 182453 |  | 91.9819 | 182384 | 182583 |
| edge_counts_by_type.HAS_ANSWER | 3 | 55859 |  | 25.1529 | 55831 | 55892 |
| edge_counts_by_type.LINKED_TO | 3 | 11278 |  | 46.7547 | 11213 | 11321 |
| edge_counts_by_type.TAGGED_WITH | 3 | 65408.7 |  | 11462.5 | 55671 | 81501 |
| latency_summary.ops.delete.50 | 3 | 0.000375998 |  | 5.75434e-05 | 0.000318071 | 0.000454461 |
| latency_summary.ops.delete.95 | 3 | 0.0218768 |  | 0.000673536 | 0.0213069 | 0.0228227 |
| latency_summary.ops.delete.99 | 3 | 0.0500305 |  | 0.00205367 | 0.0473255 | 0.0522988 |
| latency_summary.ops.insert.50 | 3 | 0.000483665 |  | 3.59704e-05 | 0.000456902 | 0.000534511 |
| latency_summary.ops.insert.95 | 3 | 0.0191315 |  | 0.000819833 | 0.0180826 | 0.0200838 |
| latency_summary.ops.insert.99 | 3 | 0.0296485 |  | 0.000857508 | 0.0290028 | 0.0308603 |
| latency_summary.ops.read.50 | 3 | 0.000237394 |  | 2.66187e-05 | 0.000205841 | 0.000270951 |
| latency_summary.ops.read.95 | 3 | 0.00130085 |  | 0.000137021 | 0.00114447 | 0.00147814 |
| latency_summary.ops.read.99 | 3 | 0.00339247 |  | 0.00108551 | 0.00192605 | 0.00451899 |
| latency_summary.ops.update.50 | 3 | 0.000141227 |  | 1.11157e-05 | 0.00012906 | 0.000155931 |
| latency_summary.ops.update.95 | 3 | 0.00270619 |  | 9.76187e-05 | 0.002579 | 0.00281627 |
| latency_summary.ops.update.99 | 3 | 0.00501746 |  | 5.92581e-05 | 0.00496556 | 0.0051004 |
| latency_summary.overall.50 | 3 | 0.00022418 |  | 2.69875e-05 | 0.00019766 | 0.00026121 |
| latency_summary.overall.95 | 3 | 0.00229287 |  | 0.00042935 | 0.00197051 | 0.00289967 |
| latency_summary.overall.99 | 3 | 0.022617 |  | 0.000749965 | 0.0216648 | 0.0234976 |
| load_counts_time_s | 3 | 4.56708 |  | 0.506562 | 3.90681 | 5.13791 |
| load_edge_count | 3 | 694317 |  | 0 | 694317 | 694317 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21869 |  | 0 | 21869 | 21869 |
| load_edge_counts_by_type.ANSWERED | 3 | 54937 |  | 0 | 54937 | 54937 |
| load_edge_counts_by_type.ASKED | 3 | 47121 |  | 0 | 47121 | 47121 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 110805 |  | 0 | 110805 | 110805 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84944 |  | 0 | 84944 | 84944 |
| load_edge_counts_by_type.EARNED | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_edge_counts_by_type.LINKED_TO | 3 | 10775 |  | 0 | 10775 | 10775 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 124636 |  | 0 | 124636 | 124636 |
| load_node_count | 3 | 622796 |  | 0 | 622796 | 622796 |
| load_node_counts_by_type.Answer | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_node_counts_by_type.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_node_counts_by_type.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| load_node_counts_by_type.Question | 3 | 48390 |  | 0 | 48390 | 48390 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 12.8052 |  | 1.84835 | 10.6245 | 15.1437 |
| load_stats.edges.ANSWERED | 3 | 35.5043 |  | 0.532516 | 34.7759 | 36.034 |
| load_stats.edges.ASKED | 3 | 40.0317 |  | 3.61892 | 34.9149 | 42.6831 |
| load_stats.edges.COMMENTED_ON | 3 | 130.761 |  | 9.69481 | 123.297 | 144.453 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 130.761 |  | 9.69481 | 123.297 | 144.453 |
| load_stats.edges.EARNED | 3 | 125.901 |  | 9.76696 | 114.929 | 138.653 |
| load_stats.edges.HAS_ANSWER | 3 | 30.7507 |  | 5.21875 | 26.4078 | 38.0901 |
| load_stats.edges.LINKED_TO | 3 | 7.18163 |  | 1.38896 | 5.22626 | 8.3212 |
| load_stats.edges.TAGGED_WITH | 3 | 72.9818 |  | 9.63466 | 65.6078 | 86.5914 |
| load_stats.nodes.Badge | 3 | 102.784 |  | 5.93547 | 96.2419 | 110.61 |
| load_stats.nodes.Comment | 3 | 125.389 |  | 11.8227 | 113.577 | 141.543 |
| load_stats.nodes.Post | 3 | 96.0508 |  | 11.9538 | 81.0913 | 110.35 |
| load_stats.nodes.Tag | 3 | 10.2002 |  | 4.65897 | 3.61483 | 13.6764 |
| load_stats.nodes.User | 3 | 156.975 |  | 16.2219 | 137.971 | 177.607 |
| load_time_s | 3 | 947.328 |  | 33.4837 | 917.583 | 994.11 |
| node_count | 3 | 624454 |  | 32.5611 | 624411 | 624490 |
| node_counts_by_type.Answer | 3 | 56640.3 |  | 46.9633 | 56582 | 56697 |
| node_counts_by_type.Badge | 3 | 183376 |  | 17.1075 | 183358 | 183399 |
| node_counts_by_type.Comment | 3 | 196187 |  | 34.5672 | 196138 | 196215 |
| node_counts_by_type.Question | 3 | 48778.7 |  | 16.4384 | 48760 | 48800 |
| node_counts_by_type.Tag | 3 | 360.667 |  | 6.84755 | 351 | 366 |
| node_counts_by_type.User | 3 | 139111 |  | 15.3261 | 139091 | 139128 |
| op_counts.delete | 3 | 5003 |  | 31.2836 | 4977 | 5047 |
| op_counts.insert | 3 | 5016 |  | 48.833 | 4979 | 5085 |
| op_counts.read | 3 | 30080 |  | 51.7494 | 30021 | 30147 |
| op_counts.update | 3 | 9901 |  | 93.4487 | 9796 | 10023 |
| rss_peak_kb | 3 | 1.90462e+06 | 1.8GiB | 8715.89 | 1895892 | 1916520 |
| schema_time_s | 3 | 0.586175 |  | 0.272266 | 0.201563 | 0.794229 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 878.235 |  | 76.4731 | 779.155 | 965.319 |
| total_time_s | 3 | 57.3779 |  | 5.12463 | 51.7964 | 64.1721 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 1.6538 |  | 0.156522 | 1.51727 | 1.87295 |
| disk_after_load_bytes | 3 | 3.91569e+08 | 373.4MiB | 2.88937e+07 | 350748461 | 413562913 |
| disk_after_oltp_bytes | 3 | 4.31004e+08 | 411.0MiB | 2.18635e+07 | 400210674 | 448821838 |
| disk_usage.du_bytes | 3 | 3.30221e+08 | 314.9MiB | 1930.87 | 330219520 | 330223616 |
| edge_count | 3 | 625611 |  | 5139.54 | 621069 | 632796 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 22151.7 |  | 12.2837 | 22142 | 22169 |
| edge_counts_by_type.ANSWERED | 3 | 55081.7 |  | 43.2538 | 55023 | 55126 |
| edge_counts_by_type.ASKED | 3 | 47260.7 |  | 79.7552 | 47182 | 47370 |
| edge_counts_by_type.COMMENTED_ON | 3 | 110105 |  | 22.2261 | 110080 | 110134 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84440.3 |  | 11.6714 | 84428 | 84456 |
| edge_counts_by_type.EARNED | 3 | 182453 |  | 126.839 | 182282 | 182585 |
| edge_counts_by_type.HAS_ANSWER | 3 | 55892 |  | 55.2509 | 55814 | 55935 |
| edge_counts_by_type.LINKED_TO | 3 | 11281.7 |  | 11.8977 | 11265 | 11292 |
| edge_counts_by_type.TAGGED_WITH | 3 | 56944.3 |  | 5392.14 | 52092 | 64465 |
| latency_summary.ops.delete.50 | 3 | 0.000583255 |  | 5.10024e-05 | 0.000543932 | 0.000655282 |
| latency_summary.ops.delete.95 | 3 | 0.0367016 |  | 0.00281868 | 0.0333596 | 0.0402543 |
| latency_summary.ops.delete.99 | 3 | 0.178915 |  | 0.0264562 | 0.143223 | 0.20648 |
| latency_summary.ops.insert.50 | 3 | 0.000653446 |  | 5.25883e-05 | 0.000585672 | 0.000713853 |
| latency_summary.ops.insert.95 | 3 | 0.0409104 |  | 0.00174526 | 0.0387881 | 0.0430627 |
| latency_summary.ops.insert.99 | 3 | 0.140011 |  | 0.0166486 | 0.126915 | 0.163504 |
| latency_summary.ops.read.50 | 3 | 0.000310508 |  | 2.08438e-05 | 0.000281691 | 0.000330291 |
| latency_summary.ops.read.95 | 3 | 0.00420459 |  | 0.000630206 | 0.00331335 | 0.00465224 |
| latency_summary.ops.read.99 | 3 | 0.0115953 |  | 0.00264934 | 0.00913731 | 0.0152732 |
| latency_summary.ops.update.50 | 3 | 0.000198368 |  | 1.36112e-05 | 0.000179301 | 0.000210191 |
| latency_summary.ops.update.95 | 3 | 0.00984329 |  | 0.00351365 | 0.00515194 | 0.0136074 |
| latency_summary.ops.update.99 | 3 | 0.049733 |  | 0.00515578 | 0.0459998 | 0.0570237 |
| latency_summary.overall.50 | 3 | 0.000311951 |  | 2.15364e-05 | 0.000282631 | 0.000333751 |
| latency_summary.overall.95 | 3 | 0.00855902 |  | 0.0011717 | 0.00691874 | 0.00958273 |
| latency_summary.overall.99 | 3 | 0.048981 |  | 0.00275301 | 0.0461756 | 0.0527216 |
| load_counts_time_s | 3 | 1.8324 |  | 0.0507804 | 1.76997 | 1.89435 |
| load_edge_count | 3 | 694317 |  | 0 | 694317 | 694317 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21869 |  | 0 | 21869 | 21869 |
| load_edge_counts_by_type.ANSWERED | 3 | 54937 |  | 0 | 54937 | 54937 |
| load_edge_counts_by_type.ASKED | 3 | 47121 |  | 0 | 47121 | 47121 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 110805 |  | 0 | 110805 | 110805 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84944 |  | 0 | 84944 | 84944 |
| load_edge_counts_by_type.EARNED | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_edge_counts_by_type.LINKED_TO | 3 | 10775 |  | 0 | 10775 | 10775 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 124636 |  | 0 | 124636 | 124636 |
| load_node_count | 3 | 622796 |  | 0 | 622796 | 622796 |
| load_node_counts_by_type.Answer | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_node_counts_by_type.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_node_counts_by_type.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| load_node_counts_by_type.Question | 3 | 48390 |  | 0 | 48390 | 48390 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 8.14517 |  | 0.405603 | 7.65086 | 8.64434 |
| load_stats.edges.ANSWERED | 3 | 32.9026 |  | 5.81636 | 25.6562 | 39.8966 |
| load_stats.edges.ASKED | 3 | 27.2361 |  | 3.4054 | 22.5203 | 30.4404 |
| load_stats.edges.COMMENTED_ON | 3 | 96.4187 |  | 5.59012 | 91.748 | 104.278 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 96.4187 |  | 5.59012 | 91.748 | 104.278 |
| load_stats.edges.EARNED | 3 | 99.9206 |  | 8.93523 | 90.4083 | 111.881 |
| load_stats.edges.HAS_ANSWER | 3 | 29.777 |  | 1.76331 | 27.6029 | 31.9218 |
| load_stats.edges.LINKED_TO | 3 | 6.13674 |  | 1.26859 | 4.34774 | 7.14782 |
| load_stats.edges.TAGGED_WITH | 3 | 51.2415 |  | 0.99562 | 50.4672 | 52.6471 |
| load_stats.nodes.Badge | 3 | 100.238 |  | 7.2763 | 91.9036 | 109.632 |
| load_stats.nodes.Comment | 3 | 113.933 |  | 4.87346 | 107.072 | 117.93 |
| load_stats.nodes.Post | 3 | 72.7393 |  | 9.01205 | 63.2804 | 84.8662 |
| load_stats.nodes.Tag | 3 | 0.715017 |  | 0.157093 | 0.51983 | 0.904501 |
| load_stats.nodes.User | 3 | 78.4596 |  | 3.59876 | 74.4111 | 83.1548 |
| load_time_s | 3 | 717.869 |  | 31.1011 | 678.139 | 754.076 |
| node_count | 3 | 624404 |  | 39.9694 | 624368 | 624460 |
| node_counts_by_type.Answer | 3 | 56635.7 |  | 29.8031 | 56599 | 56672 |
| node_counts_by_type.Badge | 3 | 183377 |  | 23.7954 | 183354 | 183410 |
| node_counts_by_type.Comment | 3 | 196166 |  | 20.8859 | 196139 | 196190 |
| node_counts_by_type.Question | 3 | 48777.3 |  | 11.8977 | 48767 | 48794 |
| node_counts_by_type.Tag | 3 | 338 |  | 4.08248 | 333 | 343 |
| node_counts_by_type.User | 3 | 139110 |  | 4.6428 | 139104 | 139115 |
| op_counts.delete | 3 | 5023.33 |  | 59.9574 | 4977 | 5108 |
| op_counts.insert | 3 | 5007.67 |  | 37.0615 | 4979 | 5060 |
| op_counts.read | 3 | 30089.7 |  | 52.0598 | 30021 | 30147 |
| op_counts.update | 3 | 9879.33 |  | 119.254 | 9731 | 10023 |
| rss_peak_kb | 3 | 1.65569e+06 | 1.6GiB | 18341.4 | 1629756 | 1668688 |
| schema_time_s | 3 | 0.148081 |  | 0.0253526 | 0.122107 | 0.182472 |
| seed | 3 | 1 |  | 0.816497 | 0 | 2 |
| threads | 3 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 3 | 1367.06 |  | 59.4654 | 1294.21 | 1439.87 |
| total_time_s | 3 | 36.6441 |  | 1.59633 | 34.7255 | 38.6337 |
| transactions | 3 | 50000 |  | 0 | 50000 | 50000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: ladybug, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.0444125 |  | 0.0239063 | 0.025666 | 0.0781515 |
| disk_after_load_bytes | 3 | 4.48808e+08 | 428.0MiB | 19308.7 | 448794310 | 448835270 |
| disk_after_oltp_bytes | 3 | 4.49153e+08 | 428.3MiB | 24234.2 | 449130716 | 449186694 |
| disk_usage.du_bytes | 3 | 5.12759e+08 | 489.0MiB | 1.55342e+06 | 511066112 | 514818048 |
| edge_count | 3 | 688707 |  | 2064.76 | 686589 | 691507 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21915 |  | 13.4412 | 21896 | 21925 |
| edge_counts_by_type.ANSWERED | 3 | 54979.7 |  | 16.2138 | 54958 | 54997 |
| edge_counts_by_type.ASKED | 3 | 47149.3 |  | 14.0554 | 47130 | 47163 |
| edge_counts_by_type.COMMENTED_ON | 3 | 110763 |  | 30.576 | 110722 | 110795 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84911.3 |  | 14.8847 | 84895 | 84931 |
| edge_counts_by_type.EARNED | 3 | 182978 |  | 16.7796 | 182957 | 182998 |
| edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 21.7715 | 56225 | 56276 |
| edge_counts_by_type.LINKED_TO | 3 | 10839 |  | 5.09902 | 10832 | 10844 |
| edge_counts_by_type.TAGGED_WITH | 3 | 118916 |  | 2009.08 | 116951 | 121676 |
| latency_summary.ops.delete.50 | 3 | 0.0278794 |  | 0.00717146 | 0.0208735 | 0.0377332 |
| latency_summary.ops.delete.95 | 3 | 0.0828412 |  | 0.0140721 | 0.0644817 | 0.0986716 |
| latency_summary.ops.delete.99 | 3 | 0.13251 |  | 0.0327585 | 0.0882224 | 0.166428 |
| latency_summary.ops.insert.50 | 3 | 0.0268119 |  | 0.00799099 | 0.0195779 | 0.0379479 |
| latency_summary.ops.insert.95 | 3 | 0.0659524 |  | 0.0303227 | 0.0274418 | 0.101545 |
| latency_summary.ops.insert.99 | 3 | 0.116566 |  | 0.041109 | 0.0584686 | 0.147478 |
| latency_summary.ops.read.50 | 3 | 0.00381824 |  | 0.000596106 | 0.00299554 | 0.00438892 |
| latency_summary.ops.read.95 | 3 | 0.0580746 |  | 0.0127491 | 0.0400953 | 0.0682337 |
| latency_summary.ops.read.99 | 3 | 0.0857175 |  | 0.00152086 | 0.0838755 | 0.0876002 |
| latency_summary.ops.update.50 | 3 | 0.0256729 |  | 0.00721515 | 0.0193807 | 0.0357756 |
| latency_summary.ops.update.95 | 3 | 0.0625782 |  | 0.0284171 | 0.0246844 | 0.0931159 |
| latency_summary.ops.update.99 | 3 | 0.115128 |  | 0.040801 | 0.0574281 | 0.144311 |
| latency_summary.overall.50 | 3 | 0.0113488 |  | 0.00420195 | 0.00540642 | 0.0143375 |
| latency_summary.overall.95 | 3 | 0.0708209 |  | 0.00875607 | 0.0615155 | 0.0825489 |
| latency_summary.overall.99 | 3 | 0.0992829 |  | 0.0134714 | 0.0848077 | 0.117248 |
| load_counts_time_s | 3 | 0.0507419 |  | 0.0183204 | 0.0290637 | 0.073869 |
| load_edge_count | 3 | 694317 |  | 0 | 694317 | 694317 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21869 |  | 0 | 21869 | 21869 |
| load_edge_counts_by_type.ANSWERED | 3 | 54937 |  | 0 | 54937 | 54937 |
| load_edge_counts_by_type.ASKED | 3 | 47121 |  | 0 | 47121 | 47121 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 110805 |  | 0 | 110805 | 110805 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84944 |  | 0 | 84944 | 84944 |
| load_edge_counts_by_type.EARNED | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_edge_counts_by_type.LINKED_TO | 3 | 10775 |  | 0 | 10775 | 10775 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 124636 |  | 0 | 124636 | 124636 |
| load_node_count | 3 | 622796 |  | 0 | 622796 | 622796 |
| load_node_counts_by_type.Answer | 3 | 56255 |  | 0 | 56255 | 56255 |
| load_node_counts_by_type.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| load_node_counts_by_type.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| load_node_counts_by_type.Question | 3 | 48390 |  | 0 | 48390 | 48390 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.101666 |  | 0.00353493 | 0.0978518 | 0.106372 |
| load_stats.edges.ANSWERED | 3 | 0.155295 |  | 0.033689 | 0.108232 | 0.185249 |
| load_stats.edges.ASKED | 3 | 0.250688 |  | 0.106399 | 0.115568 | 0.375589 |
| load_stats.edges.COMMENTED_ON | 3 | 0.35545 |  | 0.0492075 | 0.287475 | 0.402346 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.262066 |  | 0.0875426 | 0.196861 | 0.38581 |
| load_stats.edges.EARNED | 3 | 0.42844 |  | 0.129019 | 0.33212 | 0.610804 |
| load_stats.edges.HAS_ANSWER | 3 | 0.182484 |  | 0.0119107 | 0.166018 | 0.19379 |
| load_stats.edges.LINKED_TO | 3 | 0.196272 |  | 0.027704 | 0.157288 | 0.219147 |
| load_stats.edges.TAGGED_WITH | 3 | 0.14792 |  | 0.038007 | 0.120884 | 0.20167 |
| load_stats.nodes.Answer | 3 | 2.8794 |  | 0.956539 | 2.08197 | 4.22444 |
| load_stats.nodes.Badge | 3 | 0.376183 |  | 0.0722973 | 0.27977 | 0.453864 |
| load_stats.nodes.Comment | 3 | 1.50426 |  | 0.22192 | 1.20114 | 1.72627 |
| load_stats.nodes.Post | 3 | 4.79804 |  | 0.958148 | 3.88531 | 6.12174 |
| load_stats.nodes.Question | 3 | 1.91864 |  | 0.307206 | 1.55352 | 2.30511 |
| load_stats.nodes.Tag | 3 | 0.317514 |  | 0.0552554 | 0.275949 | 0.395603 |
| load_stats.nodes.User | 3 | 0.724418 |  | 0.0583198 | 0.665442 | 0.803838 |
| load_time_s | 3 | 32.0915 |  | 2.24167 | 29.2512 | 34.7311 |
| node_count | 3 | 622950 |  | 51.2705 | 622884 | 623009 |
| node_counts_by_type.Answer | 3 | 56299 |  | 16.8721 | 56276 | 56316 |
| node_counts_by_type.Badge | 3 | 183009 |  | 6.18241 | 183000 | 183014 |
| node_counts_by_type.Comment | 3 | 195819 |  | 9.46338 | 195806 | 195827 |
| node_counts_by_type.Question | 3 | 48425.7 |  | 12.6579 | 48408 | 48437 |
| node_counts_by_type.Tag | 3 | 630 |  | 0 | 630 | 630 |
| node_counts_by_type.User | 3 | 138767 |  | 14.6135 | 138752 | 138787 |
| op_counts.delete | 3 | 501 |  | 23.5089 | 468 | 521 |
| op_counts.insert | 3 | 507.667 |  | 42.0344 | 450 | 549 |
| op_counts.read | 3 | 3009.33 |  | 25.7725 | 2985 | 3045 |
| op_counts.update | 3 | 982 |  | 49.4031 | 938 | 1051 |
| rss_peak_kb | 3 | 1.5286e+06 | 1.5GiB | 53032.3 | 1453764 | 1570328 |
| schema_time_s | 3 | 0.337572 |  | 0.225351 | 0.157925 | 0.655365 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 50.7192 |  | 6.48638 | 42.5357 | 58.4001 |
| total_time_s | 3 | 100.26 |  | 13.1697 | 85.6163 | 117.548 |
| transactions | 3 | 5000 |  | 0 | 5000 | 5000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
