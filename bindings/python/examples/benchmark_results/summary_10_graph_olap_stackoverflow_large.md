# 10 Graph OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:12Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep10
- Total runs: 6
- Query samples: 60
- Cross-DB parity: True

## Parameters Used

| Parameter | Values |
|---|---|
| arcadedb_version | 26.2.1 |
| batch_size | 10000 |
| dataset | stackoverflow-large |
| db | arcadedb, ladybug |
| docker_image | python:3.12-slim |
| heap_size | 6553m, 8g |
| ladybug_version | 0.14.1 |
| mem_limit | 8g |
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep10_r01_arcadedb_s00000, sweep10_r01_ladybug_s00001, sweep10_r02_arcadedb_s00002, sweep10_r02_ladybug_s00003, sweep10_r03_arcadedb_s00004, sweep10_r03_ladybug_s00005 |
| seed | 0, 1, 2, 3, 4, 5 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 1081.85 |  | 107.565 | 942.632 | 1204.55 |
| disk_after_index_bytes | 3 | 4539070481 | 4.2GiB | 3.73501e+06 | 4535542064 | 4544238821 |
| disk_after_load_bytes | 3 | 4539070481 | 4.2GiB | 3.73501e+06 | 4535542064 | 4544238821 |
| disk_after_queries_bytes | 3 | 4539070481 | 4.2GiB | 3.73501e+06 | 4535542064 | 4544238821 |
| disk_usage.du_bytes | 3 | 4533735424 | 4.2GiB | 6688.74 | 4533727232 | 4533743616 |
| edge_count | 3 | 9770001 |  | 0 | 9770001 | 9770001 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 547717 |  | 0 | 547717 | 547717 |
| edge_counts_by_type.ANSWERED | 3 | 1857047 |  | 0 | 1857047 | 1857047 |
| edge_counts_by_type.ASKED | 3 | 703823 |  | 0 | 703823 | 703823 |
| edge_counts_by_type.COMMENTED_ON | 3 | 658618 |  | 0 | 658618 | 658618 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2065210 |  | 0 | 2065210 | 2065210 |
| edge_counts_by_type.EARNED | 3 | 397914 |  | 0 | 397914 | 397914 |
| edge_counts_by_type.HAS_ANSWER | 3 | 1957474 |  | 0 | 1957474 | 1957474 |
| edge_counts_by_type.LINKED_TO | 3 | 3974 |  | 0 | 3974 | 3974 |
| edge_counts_by_type.TAGGED_WITH | 3 | 1578224 |  | 0 | 1578224 | 1578224 |
| index_time_s | 3 | 170.2 |  | 28.0614 | 149.549 | 209.874 |
| load_counts_time_s | 3 | 1218.63 |  | 572.476 | 787.527 | 2027.65 |
| load_edge_count | 3 | 9770001 |  | 0 | 9770001 | 9770001 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 547717 |  | 0 | 547717 | 547717 |
| load_edge_counts_by_type.ANSWERED | 3 | 1857047 |  | 0 | 1857047 | 1857047 |
| load_edge_counts_by_type.ASKED | 3 | 703823 |  | 0 | 703823 | 703823 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 658618 |  | 0 | 658618 | 658618 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2065210 |  | 0 | 2065210 | 2065210 |
| load_edge_counts_by_type.EARNED | 3 | 397914 |  | 0 | 397914 | 397914 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 1957474 |  | 0 | 1957474 | 1957474 |
| load_edge_counts_by_type.LINKED_TO | 3 | 3974 |  | 0 | 3974 | 3974 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 1578224 |  | 0 | 1578224 | 1578224 |
| load_node_count | 3 | 7782816 |  | 0 | 7782816 | 7782816 |
| load_node_counts_by_type.Answer | 3 | 1960629 |  | 0 | 1960629 | 1960629 |
| load_node_counts_by_type.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| load_node_counts_by_type.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| load_node_counts_by_type.Question | 3 | 777678 |  | 0 | 777678 | 777678 |
| load_node_counts_by_type.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| load_node_counts_by_type.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 478.189 |  | 106.808 | 338.454 | 597.73 |
| load_stats.edges.ANSWERED | 3 | 1566.24 |  | 43.4226 | 1509.19 | 1614.43 |
| load_stats.edges.ASKED | 3 | 708.888 |  | 61.5374 | 652.982 | 794.601 |
| load_stats.edges.COMMENTED_ON | 3 | 1678.74 |  | 342.949 | 1195.75 | 1958.51 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 1678.74 |  | 342.949 | 1195.75 | 1958.51 |
| load_stats.edges.EARNED | 3 | 561.02 |  | 115.52 | 398.373 | 655.634 |
| load_stats.edges.HAS_ANSWER | 3 | 1522.98 |  | 189.899 | 1257.62 | 1691.45 |
| load_stats.edges.LINKED_TO | 3 | 9.02735 |  | 3.15035 | 5.95689 | 13.3583 |
| load_stats.edges.TAGGED_WITH | 3 | 1084.19 |  | 195.39 | 808.326 | 1235.98 |
| load_stats.nodes.Badge | 3 | 390.783 |  | 34.0426 | 363.741 | 438.799 |
| load_stats.nodes.Comment | 3 | 990.8 |  | 230.882 | 803.583 | 1316.08 |
| load_stats.nodes.Post | 3 | 1538.1 |  | 108.717 | 1390.57 | 1649.36 |
| load_stats.nodes.Tag | 3 | 14.621 |  | 0.703279 | 13.6543 | 15.307 |
| load_stats.nodes.User | 3 | 185.603 |  | 11.2659 | 172.704 | 200.152 |
| load_time_including_index_s | 3 | 10899.6 |  | 695.04 | 9917.66 | 11428.5 |
| load_time_s | 3 | 10729.4 |  | 723.095 | 9707.78 | 11279 |
| node_count | 3 | 7782816 |  | 0 | 7782816 | 7782816 |
| node_counts_by_type.Answer | 3 | 1960629 |  | 0 | 1960629 | 1960629 |
| node_counts_by_type.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| node_counts_by_type.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| node_counts_by_type.Question | 3 | 777678 |  | 0 | 777678 | 777678 |
| node_counts_by_type.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| node_counts_by_type.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| query_cold_time_s | 3 | 64.0472 |  | 19.4847 | 40.5118 | 88.2264 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 6773.46 |  | 1054.19 | 5631.68 | 8174.54 |
| query_warm_mean_s | 3 | 68.1437 |  | 10.4102 | 55.529 | 81.0246 |
| rss_peak_kb | 3 | 7864956 | 7.5GiB | 163286 | 7662644 | 8062528 |
| schema_time_s | 3 | 0.329912 |  | 0.177313 | 0.123252 | 0.55624 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| total_time_s | 3 | 19974.6 |  | 2098.4 | 17435.9 | 22574.8 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: ladybug (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 0.155919 |  | 0.00634949 | 0.147685 | 0.163138 |
| disk_after_index_bytes | 3 | 6112106124 | 5.7GiB | 122104 | 6111958668 | 6112257676 |
| disk_after_load_bytes | 3 | 6112106124 | 5.7GiB | 122104 | 6111958668 | 6112257676 |
| disk_after_queries_bytes | 3 | 6112106124 | 5.7GiB | 122104 | 6111958668 | 6112257676 |
| disk_usage.du_bytes | 3 | 6.11227e+09 | 5.7GiB | 158614 | 6112112640 | 6112489472 |
| edge_count | 3 | 9770001 |  | 0 | 9770001 | 9770001 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 547717 |  | 0 | 547717 | 547717 |
| edge_counts_by_type.ANSWERED | 3 | 1857047 |  | 0 | 1857047 | 1857047 |
| edge_counts_by_type.ASKED | 3 | 703823 |  | 0 | 703823 | 703823 |
| edge_counts_by_type.COMMENTED_ON | 3 | 658618 |  | 0 | 658618 | 658618 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2065210 |  | 0 | 2065210 | 2065210 |
| edge_counts_by_type.EARNED | 3 | 397914 |  | 0 | 397914 | 397914 |
| edge_counts_by_type.HAS_ANSWER | 3 | 1957474 |  | 0 | 1957474 | 1957474 |
| edge_counts_by_type.LINKED_TO | 3 | 3974 |  | 0 | 3974 | 3974 |
| edge_counts_by_type.TAGGED_WITH | 3 | 1578224 |  | 0 | 1578224 | 1578224 |
| index_time_s | 3 | 0 |  | 0 | 0 | 0 |
| load_counts_time_s | 3 | 0.243238 |  | 0.0832773 | 0.181235 | 0.360954 |
| load_edge_count | 3 | 9770001 |  | 0 | 9770001 | 9770001 |
| load_edge_counts_by_type.ACCEPTED_ANSWER | 3 | 547717 |  | 0 | 547717 | 547717 |
| load_edge_counts_by_type.ANSWERED | 3 | 1857047 |  | 0 | 1857047 | 1857047 |
| load_edge_counts_by_type.ASKED | 3 | 703823 |  | 0 | 703823 | 703823 |
| load_edge_counts_by_type.COMMENTED_ON | 3 | 658618 |  | 0 | 658618 | 658618 |
| load_edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2065210 |  | 0 | 2065210 | 2065210 |
| load_edge_counts_by_type.EARNED | 3 | 397914 |  | 0 | 397914 | 397914 |
| load_edge_counts_by_type.HAS_ANSWER | 3 | 1957474 |  | 0 | 1957474 | 1957474 |
| load_edge_counts_by_type.LINKED_TO | 3 | 3974 |  | 0 | 3974 | 3974 |
| load_edge_counts_by_type.TAGGED_WITH | 3 | 1578224 |  | 0 | 1578224 | 1578224 |
| load_node_count | 3 | 7782816 |  | 0 | 7782816 | 7782816 |
| load_node_counts_by_type.Answer | 3 | 1960629 |  | 0 | 1960629 | 1960629 |
| load_node_counts_by_type.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| load_node_counts_by_type.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| load_node_counts_by_type.Question | 3 | 777678 |  | 0 | 777678 | 777678 |
| load_node_counts_by_type.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| load_node_counts_by_type.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.242071 |  | 0.0852614 | 0.170192 | 0.361852 |
| load_stats.edges.ANSWERED | 3 | 0.666436 |  | 0.135766 | 0.566459 | 0.858383 |
| load_stats.edges.ASKED | 3 | 0.244021 |  | 0.0129809 | 0.225934 | 0.255783 |
| load_stats.edges.COMMENTED_ON | 3 | 0.316447 |  | 0.060316 | 0.267264 | 0.401394 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.918032 |  | 0.446664 | 0.555936 | 1.54733 |
| load_stats.edges.EARNED | 3 | 0.322831 |  | 0.14268 | 0.195766 | 0.522111 |
| load_stats.edges.HAS_ANSWER | 3 | 0.68879 |  | 0.263185 | 0.455052 | 1.05651 |
| load_stats.edges.LINKED_TO | 3 | 0.122062 |  | 0.0250926 | 0.103014 | 0.157515 |
| load_stats.edges.TAGGED_WITH | 3 | 0.574858 |  | 0.118189 | 0.443368 | 0.729965 |
| load_stats.nodes.Answer | 3 | 20.4024 |  | 4.12924 | 14.5632 | 23.379 |
| load_stats.nodes.Badge | 3 | 0.702481 |  | 0.125379 | 0.579448 | 0.874573 |
| load_stats.nodes.Comment | 3 | 8.00279 |  | 0.658123 | 7.11868 | 8.69674 |
| load_stats.nodes.Post | 3 | 32.1089 |  | 7.21552 | 22.6135 | 40.0928 |
| load_stats.nodes.Question | 3 | 11.7065 |  | 3.6636 | 8.05028 | 16.7138 |
| load_stats.nodes.Tag | 3 | 0.138098 |  | 0.0314188 | 0.111103 | 0.182159 |
| load_stats.nodes.User | 3 | 0.934959 |  | 0.401093 | 0.588872 | 1.49721 |
| load_time_including_index_s | 3 | 449.193 |  | 26.2118 | 414.208 | 477.298 |
| load_time_s | 3 | 449.193 |  | 26.2118 | 414.208 | 477.298 |
| node_count | 3 | 7782816 |  | 0 | 7782816 | 7782816 |
| node_counts_by_type.Answer | 3 | 1960629 |  | 0 | 1960629 | 1960629 |
| node_counts_by_type.Badge | 3 | 1657162 |  | 0 | 1657162 | 1657162 |
| node_counts_by_type.Comment | 3 | 2723828 |  | 0 | 2723828 | 2723828 |
| node_counts_by_type.Question | 3 | 777678 |  | 0 | 777678 | 777678 |
| node_counts_by_type.Tag | 3 | 1925 |  | 0 | 1925 | 1925 |
| node_counts_by_type.User | 3 | 661594 |  | 0 | 661594 | 661594 |
| query_cold_time_s | 3 | 0.114065 |  | 0.0126725 | 0.103333 | 0.131861 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 9.9409 |  | 0.365941 | 9.67605 | 10.4584 |
| query_warm_mean_s | 3 | 0.0974494 |  | 0.00265251 | 0.0954168 | 0.101196 |
| rss_peak_kb | 3 | 5492424 | 5.2GiB | 123431 | 5332528 | 5633016 |
| schema_time_s | 3 | 0.359161 |  | 0.0570733 | 0.278626 | 0.404078 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| total_time_s | 3 | 460.404 |  | 26.3177 | 425.118 | 488.3 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

## Aggregated Query Metrics

### DB: arcadedb | Query: asker_answerer_pairs (samples=3)

- Row counts: 0
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 14.3661 |  | 4.6648 | 10.6342 | 20.9432 |
| elapsed_mean_s | 3 | 6.90297 |  | 0.129369 | 6.79941 | 7.08537 |
| elapsed_min_s | 3 | 4.0786 |  | 0.577133 | 3.26252 | 4.49837 |
| elapsed_s | 3 | 5.65956 |  | 0.452157 | 5.08975 | 6.19578 |
| row_count | 3 | 0 |  | 0 | 0 | 0 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: questions_with_most_answers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 39.5407 |  | 5.46706 | 32.1831 | 45.2768 |
| elapsed_mean_s | 3 | 23.4505 |  | 0.393596 | 23.1225 | 24.0039 |
| elapsed_min_s | 3 | 16.3906 |  | 2.22471 | 13.8051 | 19.2359 |
| elapsed_s | 3 | 21.9135 |  | 1.61175 | 20.2233 | 24.083 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: tag_cooccurrence (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 23.9532 |  | 0.709688 | 23.2771 | 24.9336 |
| elapsed_mean_s | 3 | 19.1671 |  | 1.28398 | 17.9028 | 20.928 |
| elapsed_min_s | 3 | 15.1225 |  | 1.87505 | 12.8723 | 17.4626 |
| elapsed_s | 3 | 19.7386 |  | 1.45107 | 17.9588 | 21.5131 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_accepted_answerers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 853.465 |  | 308.76 | 484.336 | 1240.04 |
| elapsed_mean_s | 3 | 532.926 |  | 105.641 | 413.281 | 670.233 |
| elapsed_min_s | 3 | 330.398 |  | 26.4742 | 308.41 | 367.635 |
| elapsed_s | 3 | 544.92 |  | 147.096 | 412.972 | 750.171 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_answerers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 94.4967 |  | 22.822 | 71.9307 | 125.763 |
| elapsed_mean_s | 3 | 52.0743 |  | 4.10929 | 48.1194 | 57.7393 |
| elapsed_min_s | 3 | 36.2443 |  | 8.08409 | 27.3577 | 46.9166 |
| elapsed_s | 3 | 47.3544 |  | 7.50437 | 41.1641 | 57.915 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_askers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 13.7973 |  | 1.62299 | 11.5677 | 15.3841 |
| elapsed_mean_s | 3 | 7.47734 |  | 0.271912 | 7.11642 | 7.77272 |
| elapsed_min_s | 3 | 3.0038 |  | 0.184275 | 2.83884 | 3.261 |
| elapsed_s | 3 | 8.3145 |  | 0.299694 | 8.09545 | 8.73825 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_badges (samples=3)

- Row counts: 2
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 6.02497 |  | 1.36933 | 4.51945 | 7.83256 |
| elapsed_mean_s | 3 | 3.79743 |  | 0.41424 | 3.36306 | 4.35503 |
| elapsed_min_s | 3 | 2.23716 |  | 0.366266 | 1.91313 | 2.74914 |
| elapsed_s | 3 | 3.81091 |  | 0.244844 | 3.51184 | 4.11158 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_questions_by_score (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 7.90474 |  | 3.56237 | 4.73391 | 12.8806 |
| elapsed_mean_s | 3 | 3.22422 |  | 0.706071 | 2.68257 | 4.22152 |
| elapsed_min_s | 3 | 0.891906 |  | 0.0854124 | 0.818905 | 1.01175 |
| elapsed_s | 3 | 2.92709 |  | 0.423071 | 2.45079 | 3.47882 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_questions_by_total_comments (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 35.8012 |  | 7.28799 | 26.2611 | 43.9494 |
| elapsed_mean_s | 3 | 21.5387 |  | 1.54041 | 19.8862 | 23.5943 |
| elapsed_min_s | 3 | 14.0562 |  | 2.31553 | 11.4527 | 17.0781 |
| elapsed_s | 3 | 20.2625 |  | 1.45206 | 18.2294 | 21.5292 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_tags_by_questions (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 13.1297 |  | 3.9851 | 7.70081 | 17.1544 |
| elapsed_mean_s | 3 | 6.78197 |  | 1.23251 | 5.80448 | 8.52051 |
| elapsed_min_s | 3 | 4.17511 |  | 0.436656 | 3.68881 | 4.74786 |
| elapsed_s | 3 | 5.80698 |  | 0.850593 | 4.80702 | 6.88603 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: asker_answerer_pairs (samples=3)

- Row counts: 0
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0090886 |  | 0.00337279 | 0.00569034 | 0.0136864 |
| elapsed_mean_s | 3 | 0.00471402 |  | 0.00032994 | 0.0043613 | 0.00515492 |
| elapsed_min_s | 3 | 0.0033474 |  | 0.000558673 | 0.002635 | 0.00399947 |
| elapsed_s | 3 | 0.00440137 |  | 6.46445e-05 | 0.00432849 | 0.00448561 |
| row_count | 3 | 0 |  | 0 | 0 | 0 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: questions_with_most_answers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.06613 |  | 0.00686922 | 0.0612118 | 0.0758443 |
| elapsed_mean_s | 3 | 0.0486081 |  | 0.00217567 | 0.0465417 | 0.0516156 |
| elapsed_min_s | 3 | 0.0380503 |  | 0.00589399 | 0.0314622 | 0.0457666 |
| elapsed_s | 3 | 0.047192 |  | 0.00287013 | 0.0448911 | 0.0512383 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: tag_cooccurrence (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.201978 |  | 0.0663342 | 0.152896 | 0.295754 |
| elapsed_mean_s | 3 | 0.137426 |  | 0.00793319 | 0.128735 | 0.147916 |
| elapsed_min_s | 3 | 0.108336 |  | 0.00397344 | 0.104347 | 0.113758 |
| elapsed_s | 3 | 0.130789 |  | 0.00524682 | 0.125217 | 0.137819 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_accepted_answerers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.249475 |  | 0.0558388 | 0.196455 | 0.326666 |
| elapsed_mean_s | 3 | 0.189904 |  | 0.0138107 | 0.179045 | 0.209393 |
| elapsed_min_s | 3 | 0.148966 |  | 0.00403672 | 0.145689 | 0.154653 |
| elapsed_s | 3 | 0.184562 |  | 0.00668286 | 0.179202 | 0.193984 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_answerers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0723953 |  | 0.0286762 | 0.0395961 | 0.10945 |
| elapsed_mean_s | 3 | 0.0294784 |  | 0.00303572 | 0.0254887 | 0.0328462 |
| elapsed_min_s | 3 | 0.0211598 |  | 0.00132335 | 0.0196514 | 0.0228734 |
| elapsed_s | 3 | 0.0257457 |  | 0.00132478 | 0.0243566 | 0.027529 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_askers (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.18892 |  | 0.054032 | 0.148907 | 0.265304 |
| elapsed_mean_s | 3 | 0.130192 |  | 0.00935204 | 0.122454 | 0.14335 |
| elapsed_min_s | 3 | 0.102585 |  | 0.00960179 | 0.0893335 | 0.111778 |
| elapsed_s | 3 | 0.124746 |  | 0.00265911 | 0.122434 | 0.128471 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_badges (samples=3)

- Row counts: 2
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0174177 |  | 0.00155898 | 0.0159671 | 0.0195808 |
| elapsed_mean_s | 3 | 0.0149251 |  | 0.000633939 | 0.0144481 | 0.015821 |
| elapsed_min_s | 3 | 0.0129847 |  | 0.00028482 | 0.012584 | 0.0132205 |
| elapsed_s | 3 | 0.0147488 |  | 0.000418918 | 0.0143211 | 0.0153177 |
| row_count | 3 | 2 |  | 0 | 2 | 2 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_questions_by_score (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.00950734 |  | 0.00555086 | 0.00490427 | 0.0173159 |
| elapsed_mean_s | 3 | 0.00349408 |  | 0.000472915 | 0.00306182 | 0.00415218 |
| elapsed_min_s | 3 | 0.00196481 |  | 0.000327515 | 0.0015223 | 0.00230455 |
| elapsed_s | 3 | 0.00303237 |  | 0.000101246 | 0.00289345 | 0.00313187 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_questions_by_total_comments (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.49088 |  | 0.0604892 | 0.417069 | 0.565234 |
| elapsed_mean_s | 3 | 0.388629 |  | 0.0203634 | 0.372219 | 0.417328 |
| elapsed_min_s | 3 | 0.309732 |  | 0.024109 | 0.291147 | 0.34378 |
| elapsed_s | 3 | 0.385958 |  | 0.0363549 | 0.35208 | 0.436389 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_tags_by_questions (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0756857 |  | 0.0296803 | 0.0479646 | 0.116842 |
| elapsed_mean_s | 3 | 0.0437399 |  | 0.00220712 | 0.0406312 | 0.0455367 |
| elapsed_min_s | 3 | 0.0360709 |  | 0.0032093 | 0.0332048 | 0.0405517 |
| elapsed_s | 3 | 0.0403586 |  | 0.00391534 | 0.0366991 | 0.0457871 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

## Cross-DB Query Result Checks

| Query | Samples | DBs Present | DBs Missing | Hash Equal Across DBs | Row Counts Equal Across DBs | All Values Equal Across DBs |
|---|---:|---|---|---|---|---|
| asker_answerer_pairs | 6 | arcadedb, ladybug |  | True | True | True |
| questions_with_most_answers | 6 | arcadedb, ladybug |  | True | True | True |
| tag_cooccurrence | 6 | arcadedb, ladybug |  | True | True | True |
| top_accepted_answerers | 6 | arcadedb, ladybug |  | True | True | True |
| top_answerers | 6 | arcadedb, ladybug |  | True | True | True |
| top_askers | 6 | arcadedb, ladybug |  | True | True | True |
| top_badges | 6 | arcadedb, ladybug |  | True | True | True |
| top_questions_by_score | 6 | arcadedb, ladybug |  | True | True | True |
| top_questions_by_total_comments | 6 | arcadedb, ladybug |  | True | True | True |
| top_tags_by_questions | 6 | arcadedb, ladybug |  | True | True | True |

### asker_answerer_pairs

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 | 0 | True | True |
| ladybug | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 | 0 | True | True |

### questions_with_most_answers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 0c1ff04cbc6bc48ff24d226233cdb2e1e8197e770a49274909256c0d93f04414 | 10 | True | True |
| ladybug | 0c1ff04cbc6bc48ff24d226233cdb2e1e8197e770a49274909256c0d93f04414 | 10 | True | True |

### tag_cooccurrence

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 9fdd63bd0adb836216fca1d373776363ce2a95ebd52c966e9aaae003d3f48bce | 10 | True | True |
| ladybug | 9fdd63bd0adb836216fca1d373776363ce2a95ebd52c966e9aaae003d3f48bce | 10 | True | True |

### top_accepted_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 9a51a5e270a7ae70da5b173ef6964648bc493363f1790890ac6618e687113124 | 10 | True | True |
| ladybug | 9a51a5e270a7ae70da5b173ef6964648bc493363f1790890ac6618e687113124 | 10 | True | True |

### top_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | d121248386775d50eda887a708d2699f0e3bf1ffc8694dae1b1ab0a0fc75f114 | 10 | True | True |
| ladybug | d121248386775d50eda887a708d2699f0e3bf1ffc8694dae1b1ab0a0fc75f114 | 10 | True | True |

### top_askers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 0644552cf9d3d088990e1a2cbd4d2148bcc948b619caa12b0180658e1e6032a5 | 10 | True | True |
| ladybug | 0644552cf9d3d088990e1a2cbd4d2148bcc948b619caa12b0180658e1e6032a5 | 10 | True | True |

### top_badges

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | e26bf9c71f40ff798afc00f3fd447e8d78b11a0143ed34c22b1d4b7f0469bf2e | 2 | True | True |
| ladybug | e26bf9c71f40ff798afc00f3fd447e8d78b11a0143ed34c22b1d4b7f0469bf2e | 2 | True | True |

### top_questions_by_score

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 66761801286712cb11dfac2f0f015c5afda3975e52d05caa3e34906faa0ab66a | 10 | True | True |
| ladybug | 66761801286712cb11dfac2f0f015c5afda3975e52d05caa3e34906faa0ab66a | 10 | True | True |

### top_questions_by_total_comments

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | a30c1e9e125ba2c065d9059e1fce6822878ede0dd750028b3201c8006e2eb053 | 10 | True | True |
| ladybug | a30c1e9e125ba2c065d9059e1fce6822878ede0dd750028b3201c8006e2eb053 | 10 | True | True |

### top_tags_by_questions

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 280ede11e63d45fb1ea02aa6c1b9871330fe2a4fd610c6a2fec9cef7b07e080e | 10 | True | True |
| ladybug | 280ede11e63d45fb1ea02aa6c1b9871330fe2a4fd610c6a2fec9cef7b07e080e | 10 | True | True |
