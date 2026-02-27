# 09 Graph OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:11Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep09
- Total runs: 9

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 1000 |
| dataset | stackoverflow-tiny |
| db | arcadedb, ladybug |
| docker_image | python:3.12-slim |
| heap_size | 1g, 819m |
| ladybug_version | 0.14.1 |
| mem_limit | 1g |
| run_label | sweep09_t01_r01_arcadedb_s00000, sweep09_t01_r01_ladybug_s00001, sweep09_t01_r02_arcadedb_s00002, sweep09_t01_r02_ladybug_s00003, sweep09_t01_r03_arcadedb_s00004, sweep09_t01_r03_ladybug_s00005, sweep09_t08_r01_arcadedb_s00000, sweep09_t08_r02_arcadedb_s00001, sweep09_t08_r03_arcadedb_s00002 |
| seed | 0, 1, 2, 3, 4, 5 |
| threads | 1, 8 |
| transactions | 1000, 10000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.168191 |  | 0.0249164 | 0.13738 | 0.198404 |
| disk_after_load_bytes | 3 | 2.66517e+08 | 254.2MiB | 1.50576e+07 | 250980140 | 286897137 |
| disk_after_oltp_bytes | 3 | 7.77391e+07 | 74.1MiB | 1.98554e+07 | 55852864 | 103917068 |
| disk_usage.du_bytes | 3 | 2.46934e+07 | 23.5MiB | 1930.87 | 24690688 | 24694784 |
| edge_count | 3 | 40572.7 |  | 376.918 | 40064 | 40965 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2193 |  | 14.5144 | 2173 | 2207 |
| edge_counts_by_type.ANSWERED | 3 | 5661 |  | 17.9629 | 5639 | 5683 |
| edge_counts_by_type.ASKED | 3 | 3577.67 |  | 13.0979 | 3561 | 3593 |
| edge_counts_by_type.COMMENTED_ON | 3 | 4794.33 |  | 6.01849 | 4786 | 4800 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5097 |  | 10.198 | 5087 | 5111 |
| edge_counts_by_type.EARNED | 3 | 3592 |  | 13.0639 | 3576 | 3608 |
| edge_counts_by_type.HAS_ANSWER | 3 | 5630.33 |  | 47.8632 | 5563 | 5670 |
| edge_counts_by_type.LINKED_TO | 3 | 893.667 |  | 2.62467 | 890 | 896 |
| edge_counts_by_type.TAGGED_WITH | 3 | 9133.67 |  | 419.794 | 8541 | 9460 |
| latency_summary.ops.delete.50 | 3 | 0.000398535 |  | 4.76336e-05 | 0.000351032 | 0.000463651 |
| latency_summary.ops.delete.95 | 3 | 0.0239866 |  | 0.00115587 | 0.0224237 | 0.0251828 |
| latency_summary.ops.delete.99 | 3 | 0.0559108 |  | 0.00436618 | 0.0511877 | 0.0617169 |
| latency_summary.ops.insert.50 | 3 | 0.000488931 |  | 4.20282e-05 | 0.000442081 | 0.000544032 |
| latency_summary.ops.insert.95 | 3 | 0.0231961 |  | 0.00066007 | 0.0225579 | 0.0241052 |
| latency_summary.ops.insert.99 | 3 | 0.0461539 |  | 0.0100012 | 0.0320107 | 0.0533413 |
| latency_summary.ops.read.50 | 3 | 0.000288124 |  | 7.47905e-06 | 0.000281971 | 0.000298651 |
| latency_summary.ops.read.95 | 3 | 0.0015585 |  | 0.0001275 | 0.00139173 | 0.00170126 |
| latency_summary.ops.read.99 | 3 | 0.0145495 |  | 0.00502991 | 0.00993353 | 0.0215446 |
| latency_summary.ops.update.50 | 3 | 0.000180197 |  | 1.50115e-05 | 0.00016725 | 0.000201241 |
| latency_summary.ops.update.95 | 3 | 0.00307595 |  | 0.000131057 | 0.00298169 | 0.00326128 |
| latency_summary.ops.update.99 | 3 | 0.00723155 |  | 0.00245038 | 0.00500847 | 0.0106453 |
| latency_summary.overall.50 | 3 | 0.000279811 |  | 1.56653e-05 | 0.000262751 | 0.000300581 |
| latency_summary.overall.95 | 3 | 0.00406777 |  | 0.000834274 | 0.00292741 | 0.00490007 |
| latency_summary.overall.99 | 3 | 0.0340711 |  | 0.00508933 | 0.029567 | 0.0411849 |
| load_counts_time_s | 3 | 0.760213 |  | 0.109998 | 0.610165 | 0.870784 |
| load_edge_count | 3 | 42088 |  | 0 | 42088 | 42088 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2142 |  | 0 | 2142 | 2142 |
| load_edge_counts_by_type.ANSWERED | 3 | 5618 |  | 0 | 5618 | 5618 |
| load_edge_counts_by_type.ASKED | 3 | 3563 |  | 0 | 3563 | 3563 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 4858 |  | 0 | 4858 | 4858 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5142 |  | 0 | 5142 | 5142 |
| load_edge_counts_by_type.EARNED | 3 | 3523 |  | 0 | 3523 | 3523 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_edge_counts_by_type.LINKED_TO | 3 | 786 |  | 0 | 786 | 786 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 10689 |  | 0 | 10689 | 10689 |
| load_node_count | 3 | 40260 |  | 0 | 40260 | 40260 |
| load_node_counts_by_type.Answer | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_node_counts_by_type.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Question | 3 | 3825 |  | 0 | 3825 | 3825 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 1.63655 |  | 0.957184 | 0.77884 | 2.97235 |
| load_stats.edges.ANSWERED | 3 | 9.23915 |  | 1.26301 | 8.19249 | 11.0159 |
| load_stats.edges.ASKED | 3 | 6.69261 |  | 1.60457 | 4.44007 | 8.05664 |
| load_stats.edges.COMMENTED_ON | 3 | 8.85059 |  | 0.525291 | 8.35475 | 9.57757 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 8.85059 |  | 0.525291 | 8.35475 | 9.57757 |
| load_stats.edges.EARNED | 3 | 2.89081 |  | 0.818013 | 2.17136 | 4.03508 |
| load_stats.edges.HAS_ANSWER | 3 | 4.99275 |  | 1.85893 | 2.87027 | 7.39739 |
| load_stats.edges.LINKED_TO | 3 | 0.326454 |  | 0.102651 | 0.245102 | 0.471256 |
| load_stats.edges.TAGGED_WITH | 3 | 6.79602 |  | 1.27586 | 5.08705 | 8.15181 |
| load_stats.nodes.Badge | 3 | 8.54404 |  | 2.25802 | 5.54803 | 10.9991 |
| load_stats.nodes.Comment | 3 | 10.6947 |  | 1.80521 | 8.27668 | 12.613 |
| load_stats.nodes.Post | 3 | 20.3468 |  | 2.59081 | 17.5863 | 23.8135 |
| load_stats.nodes.Tag | 3 | 2.39732 |  | 1.19727 | 1.53701 | 4.09045 |
| load_stats.nodes.User | 3 | 20.2155 |  | 1.59318 | 18.4071 | 22.2836 |
| load_time_s | 3 | 103.625 |  | 6.11019 | 96.1204 | 111.087 |
| node_count | 3 | 40593.7 |  | 21.0132 | 40564 | 40610 |
| node_counts_by_type.Answer | 3 | 5845.67 |  | 19.9053 | 5818 | 5864 |
| node_counts_by_type.Badge | 3 | 10070.3 |  | 7.31817 | 10060 | 10076 |
| node_counts_by_type.Comment | 3 | 10092.7 |  | 21.3125 | 10068 | 10120 |
| node_counts_by_type.Question | 3 | 3901.33 |  | 8.17856 | 3891 | 3911 |
| node_counts_by_type.Tag | 3 | 603.333 |  | 4.98888 | 598 | 610 |
| node_counts_by_type.User | 3 | 10080.3 |  | 10.873 | 10069 | 10095 |
| op_counts.delete | 3 | 975.333 |  | 13.2749 | 957 | 988 |
| op_counts.insert | 3 | 1030.67 |  | 33.2499 | 984 | 1059 |
| op_counts.read | 3 | 6017 |  | 29.4392 | 5977 | 6047 |
| op_counts.update | 3 | 1977 |  | 34.4093 | 1933 | 2017 |
| rss_peak_kb | 3 | 678647 | 662.7MiB | 201462 | 447612 | 938552 |
| schema_time_s | 3 | 0.584954 |  | 0.219264 | 0.292511 | 0.820467 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 639.34 |  | 63.4587 | 570.294 | 723.511 |
| total_time_s | 3 | 15.7922 |  | 1.52451 | 13.8215 | 17.5348 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: arcadedb, Threads: 8 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.18014 |  | 0.05948 | 0.134487 | 0.264152 |
| disk_after_load_bytes | 3 | 9.87226e+07 | 94.1MiB | 5.21687e+07 | 28651149 | 153754713 |
| disk_after_oltp_bytes | 3 | 135374532 | 129.1MiB | 3.33056e+07 | 89908548 | 168762485 |
| disk_usage.du_bytes | 3 | 24694784 | 23.6MiB | 0 | 24694784 | 24694784 |
| edge_count | 3 | 40924 |  | 352.637 | 40477 | 41339 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2183.67 |  | 16.4181 | 2167 | 2206 |
| edge_counts_by_type.ANSWERED | 3 | 5582.33 |  | 128.011 | 5406 | 5706 |
| edge_counts_by_type.ASKED | 3 | 3601.67 |  | 15.3261 | 3585 | 3622 |
| edge_counts_by_type.COMMENTED_ON | 3 | 4814.33 |  | 15.5849 | 4800 | 4836 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5063 |  | 30.7354 | 5020 | 5090 |
| edge_counts_by_type.EARNED | 3 | 3594.67 |  | 6.54896 | 3587 | 3603 |
| edge_counts_by_type.HAS_ANSWER | 3 | 5665 |  | 32.8938 | 5636 | 5711 |
| edge_counts_by_type.LINKED_TO | 3 | 887.667 |  | 6.12826 | 880 | 895 |
| edge_counts_by_type.TAGGED_WITH | 3 | 9531.67 |  | 140.158 | 9352 | 9694 |
| latency_summary.ops.delete.50 | 3 | 0.000592275 |  | 8.93039e-05 | 0.000512981 | 0.000717052 |
| latency_summary.ops.delete.95 | 3 | 0.0276833 |  | 0.00845719 | 0.0158127 | 0.0348849 |
| latency_summary.ops.delete.99 | 3 | 0.089384 |  | 0.00345193 | 0.0847002 | 0.0929178 |
| latency_summary.ops.insert.50 | 3 | 0.000846376 |  | 0.00011163 | 0.000751012 | 0.00100301 |
| latency_summary.ops.insert.95 | 3 | 0.0532515 |  | 0.0224627 | 0.0253451 | 0.0803493 |
| latency_summary.ops.insert.99 | 3 | 0.198337 |  | 0.0833163 | 0.080575 | 0.260605 |
| latency_summary.ops.read.50 | 3 | 0.000520998 |  | 8.68303e-05 | 0.000444221 | 0.000642382 |
| latency_summary.ops.read.95 | 3 | 0.0113023 |  | 0.00129317 | 0.00958106 | 0.0126982 |
| latency_summary.ops.read.99 | 3 | 0.0272571 |  | 0.0044985 | 0.0208995 | 0.0306366 |
| latency_summary.ops.update.50 | 3 | 0.000329688 |  | 3.45881e-05 | 0.000304971 | 0.000378602 |
| latency_summary.ops.update.95 | 3 | 0.0160511 |  | 0.00966752 | 0.00277354 | 0.0255133 |
| latency_summary.ops.update.99 | 3 | 0.0538619 |  | 0.0265509 | 0.0166003 | 0.0765054 |
| latency_summary.overall.50 | 3 | 0.000500912 |  | 7.39225e-05 | 0.000446412 | 0.000605422 |
| latency_summary.overall.95 | 3 | 0.0166085 |  | 0.00329711 | 0.0120906 | 0.0198664 |
| latency_summary.overall.99 | 3 | 0.0572369 |  | 0.0175898 | 0.0346762 | 0.0775927 |
| load_counts_time_s | 3 | 0.434722 |  | 0.08156 | 0.320655 | 0.506573 |
| load_edge_count | 3 | 42088 |  | 0 | 42088 | 42088 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2142 |  | 0 | 2142 | 2142 |
| load_edge_counts_by_type.ANSWERED | 3 | 5618 |  | 0 | 5618 | 5618 |
| load_edge_counts_by_type.ASKED | 3 | 3563 |  | 0 | 3563 | 3563 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 4858 |  | 0 | 4858 | 4858 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5142 |  | 0 | 5142 | 5142 |
| load_edge_counts_by_type.EARNED | 3 | 3523 |  | 0 | 3523 | 3523 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_edge_counts_by_type.LINKED_TO | 3 | 786 |  | 0 | 786 | 786 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 10689 |  | 0 | 10689 | 10689 |
| load_node_count | 3 | 40260 |  | 0 | 40260 | 40260 |
| load_node_counts_by_type.Answer | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_node_counts_by_type.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Question | 3 | 3825 |  | 0 | 3825 | 3825 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.661047 |  | 0.0395183 | 0.612341 | 0.709135 |
| load_stats.edges.ANSWERED | 3 | 3.37942 |  | 1.02951 | 1.92535 | 4.17046 |
| load_stats.edges.ASKED | 3 | 3.58036 |  | 0.91869 | 2.2822 | 4.27512 |
| load_stats.edges.COMMENTED_ON | 3 | 4.97031 |  | 1.39101 | 3.10278 | 6.43943 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 4.97031 |  | 1.39101 | 3.10278 | 6.43943 |
| load_stats.edges.EARNED | 3 | 3.25545 |  | 0.94235 | 1.94138 | 4.10471 |
| load_stats.edges.HAS_ANSWER | 3 | 3.77611 |  | 0.150982 | 3.65998 | 3.98935 |
| load_stats.edges.LINKED_TO | 3 | 0.251108 |  | 0.0352612 | 0.210287 | 0.296323 |
| load_stats.edges.TAGGED_WITH | 3 | 5.50624 |  | 0.958049 | 4.7443 | 6.85745 |
| load_stats.nodes.Badge | 3 | 9.66172 |  | 1.32372 | 8.10696 | 11.3421 |
| load_stats.nodes.Comment | 3 | 10.1638 |  | 1.57695 | 8.84352 | 12.3805 |
| load_stats.nodes.Post | 3 | 14.8813 |  | 3.24492 | 11.5345 | 19.2738 |
| load_stats.nodes.Tag | 3 | 1.6269 |  | 0.453433 | 1.12451 | 2.22321 |
| load_stats.nodes.User | 3 | 12.24 |  | 1.32622 | 11.1738 | 14.1094 |
| load_time_s | 3 | 73.9556 |  | 2.4003 | 71.9301 | 77.3274 |
| node_count | 3 | 40585 |  | 41.3038 | 40550 | 40643 |
| node_counts_by_type.Answer | 3 | 5847.67 |  | 18.2087 | 5831 | 5873 |
| node_counts_by_type.Badge | 3 | 10076 |  | 19.4422 | 10049 | 10094 |
| node_counts_by_type.Comment | 3 | 10070 |  | 4.32049 | 10064 | 10074 |
| node_counts_by_type.Question | 3 | 3906.33 |  | 10.5304 | 3892 | 3917 |
| node_counts_by_type.Tag | 3 | 600 |  | 0.816497 | 599 | 601 |
| node_counts_by_type.User | 3 | 10085 |  | 11.3431 | 10069 | 10094 |
| op_counts.delete | 3 | 992.667 |  | 31.2019 | 957 | 1033 |
| op_counts.insert | 3 | 1006.67 |  | 29.9592 | 984 | 1049 |
| op_counts.read | 3 | 6015 |  | 28.8906 | 5977 | 6047 |
| op_counts.update | 3 | 1985.67 |  | 23.9072 | 1959 | 2017 |
| rss_peak_kb | 3 | 597180 | 583.2MiB | 123120 | 463992 | 760900 |
| schema_time_s | 3 | 0.416136 |  | 0.216958 | 0.178151 | 0.702844 |
| seed | 3 | 1 |  | 0.816497 | 0 | 2 |
| threads | 3 | 8 |  | 0 | 8 | 8 |
| throughput_ops_s | 3 | 1906.57 |  | 329.294 | 1582.13 | 2358.11 |
| total_time_s | 3 | 5.39363 |  | 0.864025 | 4.24068 | 6.32058 |
| transactions | 3 | 10000 |  | 0 | 10000 | 10000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: ladybug, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.0154233 |  | 0.00729738 | 0.00519943 | 0.0217526 |
| disk_after_load_bytes | 3 | 48935102 | 46.7MiB | 0 | 48935102 | 48935102 |
| disk_after_oltp_bytes | 3 | 4.90033e+07 | 46.7MiB | 3997.18 | 48998348 | 49008139 |
| disk_usage.du_bytes | 3 | 5.44782e+07 | 52.0MiB | 15080.6 | 54460416 | 54497280 |
| edge_count | 3 | 41971 |  | 28.2489 | 41938 | 42007 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2153 |  | 9.4163 | 2140 | 2162 |
| edge_counts_by_type.ANSWERED | 3 | 5621 |  | 11.0454 | 5607 | 5634 |
| edge_counts_by_type.ASKED | 3 | 3567.33 |  | 3.85861 | 3562 | 3571 |
| edge_counts_by_type.COMMENTED_ON | 3 | 4854.33 |  | 10.3387 | 4840 | 4864 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5134.33 |  | 7.03957 | 5125 | 5142 |
| edge_counts_by_type.EARNED | 3 | 3538.33 |  | 2.49444 | 3535 | 3541 |
| edge_counts_by_type.HAS_ANSWER | 3 | 5766.67 |  | 8.37987 | 5758 | 5778 |
| edge_counts_by_type.LINKED_TO | 3 | 793.667 |  | 1.24722 | 792 | 795 |
| edge_counts_by_type.TAGGED_WITH | 3 | 10542.3 |  | 42.4604 | 10483 | 10580 |
| latency_summary.ops.delete.50 | 3 | 0.0280833 |  | 0.00225388 | 0.0254498 | 0.0309552 |
| latency_summary.ops.delete.95 | 3 | 0.0641834 |  | 0.0185174 | 0.0382106 | 0.0800682 |
| latency_summary.ops.delete.99 | 3 | 0.0942003 |  | 0.0329548 | 0.0477892 | 0.121085 |
| latency_summary.ops.insert.50 | 3 | 0.0271939 |  | 0.00270119 | 0.0239035 | 0.0305198 |
| latency_summary.ops.insert.95 | 3 | 0.0698853 |  | 0.0284436 | 0.0375484 | 0.106773 |
| latency_summary.ops.insert.99 | 3 | 0.322016 |  | 0.276295 | 0.0848441 | 0.709527 |
| latency_summary.ops.read.50 | 3 | 0.00332035 |  | 0.000667169 | 0.00270877 | 0.00424835 |
| latency_summary.ops.read.95 | 3 | 0.0530449 |  | 0.00600932 | 0.0454093 | 0.0600939 |
| latency_summary.ops.read.99 | 3 | 0.0844892 |  | 0.00335023 | 0.0798319 | 0.0875717 |
| latency_summary.ops.update.50 | 3 | 0.0267414 |  | 0.00311912 | 0.0233935 | 0.0309027 |
| latency_summary.ops.update.95 | 3 | 0.0529328 |  | 0.0117463 | 0.0379242 | 0.0666031 |
| latency_summary.ops.update.99 | 3 | 0.132638 |  | 0.0722662 | 0.067865 | 0.233486 |
| latency_summary.overall.50 | 3 | 0.0103345 |  | 0.00283007 | 0.0081628 | 0.0143319 |
| latency_summary.overall.95 | 3 | 0.0545352 |  | 0.0104025 | 0.0399685 | 0.0636005 |
| latency_summary.overall.99 | 3 | 0.0963402 |  | 0.00969626 | 0.0858837 | 0.109251 |
| load_counts_time_s | 3 | 0.0259903 |  | 0.0145884 | 0.0132201 | 0.0464084 |
| load_edge_count | 3 | 42088 |  | 0 | 42088 | 42088 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2142 |  | 0 | 2142 | 2142 |
| load_edge_counts_by_type.ANSWERED | 3 | 5618 |  | 0 | 5618 | 5618 |
| load_edge_counts_by_type.ASKED | 3 | 3563 |  | 0 | 3563 | 3563 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 4858 |  | 0 | 4858 | 4858 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5142 |  | 0 | 5142 | 5142 |
| load_edge_counts_by_type.EARNED | 3 | 3523 |  | 0 | 3523 | 3523 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_edge_counts_by_type.LINKED_TO | 3 | 786 |  | 0 | 786 | 786 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 10689 |  | 0 | 10689 | 10689 |
| load_node_count | 3 | 40260 |  | 0 | 40260 | 40260 |
| load_node_counts_by_type.Answer | 3 | 5767 |  | 0 | 5767 | 5767 |
| load_node_counts_by_type.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_node_counts_by_type.Question | 3 | 3825 |  | 0 | 3825 | 3825 |
| load_node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| load_node_counts_by_type.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.0971921 |  | 0.0136927 | 0.0778556 | 0.107759 |
| load_stats.edges.ANSWERED | 3 | 0.107278 |  | 0.0125857 | 0.0897789 | 0.118845 |
| load_stats.edges.ASKED | 3 | 0.115729 |  | 0.0668779 | 0.0504014 | 0.207623 |
| load_stats.edges.COMMENTED_ON | 3 | 0.129376 |  | 0.0339086 | 0.0819263 | 0.159108 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.146458 |  | 0.0545185 | 0.106191 | 0.223532 |
| load_stats.edges.EARNED | 3 | 0.331021 |  | 0.338631 | 0.0862021 | 0.809877 |
| load_stats.edges.HAS_ANSWER | 3 | 0.0944935 |  | 0.00934388 | 0.085031 | 0.107213 |
| load_stats.edges.LINKED_TO | 3 | 0.110537 |  | 0.0220282 | 0.0893655 | 0.140914 |
| load_stats.edges.TAGGED_WITH | 3 | 0.174471 |  | 0.0630797 | 0.085711 | 0.226586 |
| load_stats.nodes.Answer | 3 | 0.56488 |  | 0.0211403 | 0.535307 | 0.583467 |
| load_stats.nodes.Badge | 3 | 0.117152 |  | 0.0110261 | 0.102029 | 0.128006 |
| load_stats.nodes.Comment | 3 | 0.389984 |  | 0.0714159 | 0.297446 | 0.471294 |
| load_stats.nodes.Post | 3 | 1.2518 |  | 0.0665857 | 1.16013 | 1.31631 |
| load_stats.nodes.Question | 3 | 0.686916 |  | 0.0727172 | 0.584268 | 0.743643 |
| load_stats.nodes.Tag | 3 | 0.978851 |  | 0.852595 | 0.310119 | 2.18211 |
| load_stats.nodes.User | 3 | 0.37764 |  | 0.0720635 | 0.284894 | 0.460597 |
| load_time_s | 3 | 7.49894 |  | 2.28773 | 5.4202 | 10.6853 |
| node_count | 3 | 40289 |  | 10.7083 | 40275 | 40301 |
| node_counts_by_type.Answer | 3 | 5776 |  | 5.09902 | 5771 | 5783 |
| node_counts_by_type.Badge | 3 | 10014.3 |  | 1.69967 | 10012 | 10016 |
| node_counts_by_type.Comment | 3 | 10006.3 |  | 1.24722 | 10005 | 10008 |
| node_counts_by_type.Question | 3 | 3830 |  | 2.94392 | 3826 | 3833 |
| node_counts_by_type.Tag | 3 | 658.333 |  | 2.35702 | 655 | 660 |
| node_counts_by_type.User | 3 | 10004 |  | 4.24264 | 10001 | 10010 |
| op_counts.delete | 3 | 102.667 |  | 3.68179 | 98 | 107 |
| op_counts.insert | 3 | 101 |  | 14.5144 | 81 | 115 |
| op_counts.read | 3 | 600.667 |  | 9.74109 | 587 | 609 |
| op_counts.update | 3 | 195.667 |  | 5.73488 | 189 | 203 |
| rss_peak_kb | 3 | 819553 | 800.3MiB | 13669.3 | 803620 | 837000 |
| schema_time_s | 3 | 0.43797 |  | 0.23265 | 0.219699 | 0.760313 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 53.8293 |  | 4.14719 | 49.3527 | 59.3492 |
| total_time_s | 3 | 18.6854 |  | 1.40529 | 16.8494 | 20.2623 |
| transactions | 3 | 1000 |  | 0 | 1000 | 1000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
