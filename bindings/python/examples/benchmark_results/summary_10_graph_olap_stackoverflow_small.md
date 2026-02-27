# 10 Graph OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:12Z
- Dataset: stackoverflow-small
- Dataset size profile: small
- Label prefix: sweep10
- Total runs: 6
- Query samples: 60
- Cross-DB parity: True

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep10_r01_arcadedb_s00000, sweep10_r01_ladybug_s00001, sweep10_r02_arcadedb_s00002, sweep10_r02_ladybug_s00003, sweep10_r03_arcadedb_s00004, sweep10_r03_ladybug_s00005 |
| seed | 0, 1, 2, 3, 4, 5 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 6.85795 |  | 0.0768031 | 6.78474 | 6.96404 |
| disk_after_index_bytes | 3 | 3.32237e+08 | 316.8MiB | 4.20838e+06 | 329261716 | 338189039 |
| disk_after_load_bytes | 3 | 3.32237e+08 | 316.8MiB | 4.20838e+06 | 329261716 | 338189039 |
| disk_after_queries_bytes | 3 | 3.32237e+08 | 316.8MiB | 4.20838e+06 | 329261716 | 338189039 |
| disk_usage.du_bytes | 3 | 3.29385e+08 | 314.1MiB | 1930.87 | 329383936 | 329388032 |
| edge_count | 3 | 694317 |  | 0 | 694317 | 694317 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21869 |  | 0 | 21869 | 21869 |
| edge_counts_by_type.ANSWERED | 3 | 54937 |  | 0 | 54937 | 54937 |
| edge_counts_by_type.ASKED | 3 | 47121 |  | 0 | 47121 | 47121 |
| edge_counts_by_type.COMMENTED_ON | 3 | 110805 |  | 0 | 110805 | 110805 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84944 |  | 0 | 84944 | 84944 |
| edge_counts_by_type.EARNED | 3 | 182975 |  | 0 | 182975 | 182975 |
| edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 0 | 56255 | 56255 |
| edge_counts_by_type.LINKED_TO | 3 | 10775 |  | 0 | 10775 | 10775 |
| edge_counts_by_type.TAGGED_WITH | 3 | 124636 |  | 0 | 124636 | 124636 |
| index_time_s | 3 | 2.90539 |  | 0.528957 | 2.15872 | 3.31816 |
| load_counts_time_s | 3 | 7.08894 |  | 0.152768 | 6.87437 | 7.21807 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 10.2134 |  | 1.28532 | 8.52716 | 11.6443 |
| load_stats.edges.ANSWERED | 3 | 27.1366 |  | 2.54836 | 24.4476 | 30.5591 |
| load_stats.edges.ASKED | 3 | 25.2662 |  | 2.39815 | 22.0583 | 27.8234 |
| load_stats.edges.COMMENTED_ON | 3 | 91.0726 |  | 5.09464 | 86.2715 | 98.1256 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 91.0726 |  | 5.09464 | 86.2715 | 98.1256 |
| load_stats.edges.EARNED | 3 | 92.4437 |  | 4.82929 | 85.6222 | 96.1433 |
| load_stats.edges.HAS_ANSWER | 3 | 22.2842 |  | 4.55187 | 17.4626 | 28.3887 |
| load_stats.edges.LINKED_TO | 3 | 5.27813 |  | 1.20832 | 4.2504 | 6.97432 |
| load_stats.edges.TAGGED_WITH | 3 | 42.9009 |  | 3.48147 | 39.3099 | 47.6135 |
| load_stats.nodes.Badge | 3 | 42.5475 |  | 1.22109 | 41.0625 | 44.0533 |
| load_stats.nodes.Comment | 3 | 51.4066 |  | 2.91588 | 48.7223 | 55.4597 |
| load_stats.nodes.Post | 3 | 39.6897 |  | 1.30395 | 38.5329 | 41.5118 |
| load_stats.nodes.Tag | 3 | 0.435199 |  | 0.0198492 | 0.413732 | 0.461597 |
| load_stats.nodes.User | 3 | 42.4074 |  | 5.12495 | 36.864 | 49.2227 |
| load_time_including_index_s | 3 | 495.993 |  | 16.4263 | 483.953 | 519.218 |
| load_time_s | 3 | 493.087 |  | 16.1501 | 480.714 | 515.9 |
| node_count | 3 | 622796 |  | 0 | 622796 | 622796 |
| node_counts_by_type.Answer | 3 | 56255 |  | 0 | 56255 | 56255 |
| node_counts_by_type.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| node_counts_by_type.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| node_counts_by_type.Question | 3 | 48390 |  | 0 | 48390 | 48390 |
| node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| node_counts_by_type.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| query_cold_time_s | 3 | 0.386295 |  | 0.0266192 | 0.349149 | 0.410162 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 34.6135 |  | 0.950752 | 33.2695 | 35.3191 |
| query_warm_mean_s | 3 | 0.341452 |  | 0.00764023 | 0.33065 | 0.347065 |
| rss_peak_kb | 3 | 1390504 | 1.3GiB | 38906.2 | 1335504 | 1419340 |
| schema_time_s | 3 | 0.0994814 |  | 0.0174618 | 0.0818024 | 0.123253 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| total_time_s | 3 | 545.211 |  | 17.0705 | 531.645 | 569.288 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: ladybug (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 2500 |  | 0 | 2500 | 2500 |
| counts_time_s | 3 | 0.0620099 |  | 0.0028629 | 0.0581753 | 0.0650525 |
| disk_after_index_bytes | 3 | 4.48801e+08 | 428.0MiB | 28443.5 | 448765638 | 448835270 |
| disk_after_load_bytes | 3 | 4.48801e+08 | 428.0MiB | 28443.5 | 448765638 | 448835270 |
| disk_after_queries_bytes | 3 | 4.48801e+08 | 428.0MiB | 28443.5 | 448765638 | 448835270 |
| disk_usage.du_bytes | 3 | 4.489e+08 | 428.1MiB | 19016.9 | 448880640 | 448925696 |
| edge_count | 3 | 694317 |  | 0 | 694317 | 694317 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 21869 |  | 0 | 21869 | 21869 |
| edge_counts_by_type.ANSWERED | 3 | 54937 |  | 0 | 54937 | 54937 |
| edge_counts_by_type.ASKED | 3 | 47121 |  | 0 | 47121 | 47121 |
| edge_counts_by_type.COMMENTED_ON | 3 | 110805 |  | 0 | 110805 | 110805 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 84944 |  | 0 | 84944 | 84944 |
| edge_counts_by_type.EARNED | 3 | 182975 |  | 0 | 182975 | 182975 |
| edge_counts_by_type.HAS_ANSWER | 3 | 56255 |  | 0 | 56255 | 56255 |
| edge_counts_by_type.LINKED_TO | 3 | 10775 |  | 0 | 10775 | 10775 |
| edge_counts_by_type.TAGGED_WITH | 3 | 124636 |  | 0 | 124636 | 124636 |
| index_time_s | 3 | 0 |  | 0 | 0 | 0 |
| load_counts_time_s | 3 | 0.0719767 |  | 0.00753951 | 0.066483 | 0.0826375 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.06595 |  | 0.0174457 | 0.0413024 | 0.0792241 |
| load_stats.edges.ANSWERED | 3 | 0.0935254 |  | 0.00414256 | 0.0905757 | 0.0993838 |
| load_stats.edges.ASKED | 3 | 0.078914 |  | 0.00970314 | 0.0674217 | 0.0911541 |
| load_stats.edges.COMMENTED_ON | 3 | 0.102959 |  | 0.00691095 | 0.0931957 | 0.108225 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.0878038 |  | 0.0136403 | 0.0687945 | 0.100149 |
| load_stats.edges.EARNED | 3 | 0.121842 |  | 0.00589472 | 0.113574 | 0.126896 |
| load_stats.edges.HAS_ANSWER | 3 | 0.0712837 |  | 0.0192273 | 0.0442541 | 0.0873642 |
| load_stats.edges.LINKED_TO | 3 | 0.0699306 |  | 0.0197855 | 0.0424221 | 0.0881183 |
| load_stats.edges.TAGGED_WITH | 3 | 0.078894 |  | 0.0162146 | 0.0561361 | 0.0927083 |
| load_stats.nodes.Answer | 3 | 2.00148 |  | 0.909145 | 1.25202 | 3.28095 |
| load_stats.nodes.Badge | 3 | 0.212974 |  | 0.12985 | 0.10809 | 0.395957 |
| load_stats.nodes.Comment | 3 | 1.39933 |  | 0.952364 | 0.697384 | 2.74577 |
| load_stats.nodes.Post | 3 | 3.00307 |  | 0.869592 | 2.34402 | 4.23177 |
| load_stats.nodes.Question | 3 | 1.00159 |  | 0.131091 | 0.872551 | 1.18139 |
| load_stats.nodes.Tag | 3 | 0.154783 |  | 0.0826821 | 0.0809815 | 0.27023 |
| load_stats.nodes.User | 3 | 0.247096 |  | 0.00532256 | 0.241681 | 0.254332 |
| load_time_including_index_s | 3 | 31.213 |  | 7.26616 | 25.3372 | 41.4518 |
| load_time_s | 3 | 31.213 |  | 7.26616 | 25.3372 | 41.4518 |
| node_count | 3 | 622796 |  | 0 | 622796 | 622796 |
| node_counts_by_type.Answer | 3 | 56255 |  | 0 | 56255 | 56255 |
| node_counts_by_type.Badge | 3 | 182975 |  | 0 | 182975 | 182975 |
| node_counts_by_type.Comment | 3 | 195781 |  | 0 | 195781 | 195781 |
| node_counts_by_type.Question | 3 | 48390 |  | 0 | 48390 | 48390 |
| node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| node_counts_by_type.User | 3 | 138727 |  | 0 | 138727 | 138727 |
| query_cold_time_s | 3 | 0.0308869 |  | 0.00180422 | 0.0287805 | 0.0331872 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 2.9205 |  | 0.151361 | 2.70712 | 3.04188 |
| query_warm_mean_s | 3 | 0.0287528 |  | 0.00186137 | 0.0261381 | 0.0303236 |
| rss_peak_kb | 3 | 1.54171e+06 | 1.5GiB | 27501.2 | 1505632 | 1572332 |
| schema_time_s | 3 | 0.200314 |  | 0.10061 | 0.0679328 | 0.311671 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| total_time_s | 3 | 34.7857 |  | 7.09124 | 28.9644 | 44.7683 |

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
| elapsed_max_s | 3 | 0.301795 |  | 0.019457 | 0.278382 | 0.326021 |
| elapsed_mean_s | 3 | 0.254463 |  | 0.00701479 | 0.245305 | 0.262345 |
| elapsed_min_s | 3 | 0.225127 |  | 0.00592254 | 0.218152 | 0.23263 |
| elapsed_s | 3 | 0.252751 |  | 0.00926876 | 0.245499 | 0.265833 |
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
| elapsed_max_s | 3 | 0.252861 |  | 0.0370343 | 0.209126 | 0.299684 |
| elapsed_mean_s | 3 | 0.201075 |  | 0.0119083 | 0.18462 | 0.212407 |
| elapsed_min_s | 3 | 0.169503 |  | 0.00399058 | 0.164078 | 0.173561 |
| elapsed_s | 3 | 0.19897 |  | 0.013071 | 0.183636 | 0.215578 |
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
| elapsed_max_s | 3 | 1.26143 |  | 0.0530949 | 1.18789 | 1.31133 |
| elapsed_mean_s | 3 | 1.18003 |  | 0.0323472 | 1.1355 | 1.21138 |
| elapsed_min_s | 3 | 1.10894 |  | 0.031663 | 1.06845 | 1.14574 |
| elapsed_s | 3 | 1.18975 |  | 0.0288623 | 1.16129 | 1.22932 |
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
| elapsed_max_s | 3 | 0.409919 |  | 0.0680546 | 0.356491 | 0.50596 |
| elapsed_mean_s | 3 | 0.342985 |  | 0.0124388 | 0.326694 | 0.356878 |
| elapsed_min_s | 3 | 0.305974 |  | 0.00779547 | 0.294956 | 0.311803 |
| elapsed_s | 3 | 0.340899 |  | 0.00763664 | 0.33091 | 0.34945 |
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
| elapsed_max_s | 3 | 0.261789 |  | 0.0123903 | 0.250139 | 0.278949 |
| elapsed_mean_s | 3 | 0.23872 |  | 0.00582429 | 0.230794 | 0.244625 |
| elapsed_min_s | 3 | 0.224109 |  | 0.00504074 | 0.217168 | 0.228988 |
| elapsed_s | 3 | 0.237456 |  | 0.00660825 | 0.229222 | 0.245401 |
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
| elapsed_max_s | 3 | 0.292665 |  | 0.0179891 | 0.269558 | 0.313436 |
| elapsed_mean_s | 3 | 0.253198 |  | 0.00412549 | 0.247417 | 0.25677 |
| elapsed_min_s | 3 | 0.223015 |  | 0.00476251 | 0.218533 | 0.22961 |
| elapsed_s | 3 | 0.251031 |  | 0.00217751 | 0.247962 | 0.252791 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: arcadedb | Query: top_badges (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.506835 |  | 0.0130365 | 0.492914 | 0.524264 |
| elapsed_mean_s | 3 | 0.451601 |  | 0.0107632 | 0.439633 | 0.46573 |
| elapsed_min_s | 3 | 0.404591 |  | 0.00667174 | 0.397268 | 0.413405 |
| elapsed_s | 3 | 0.45231 |  | 0.0147042 | 0.439135 | 0.472831 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.101347 |  | 0.0269958 | 0.0662503 | 0.131908 |
| elapsed_mean_s | 3 | 0.0572764 |  | 0.00389823 | 0.0518784 | 0.0609452 |
| elapsed_min_s | 3 | 0.0459099 |  | 0.00158036 | 0.0446081 | 0.0481341 |
| elapsed_s | 3 | 0.0532148 |  | 0.000291538 | 0.0528035 | 0.0534456 |
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
| elapsed_max_s | 3 | 0.323259 |  | 0.069802 | 0.24996 | 0.417171 |
| elapsed_mean_s | 3 | 0.218235 |  | 0.00779943 | 0.210192 | 0.228793 |
| elapsed_min_s | 3 | 0.191785 |  | 0.00317105 | 0.187301 | 0.194105 |
| elapsed_s | 3 | 0.206526 |  | 0.00380936 | 0.201401 | 0.210527 |
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
| elapsed_max_s | 3 | 0.289762 |  | 0.0106539 | 0.281489 | 0.304803 |
| elapsed_mean_s | 3 | 0.261782 |  | 0.00814193 | 0.252961 | 0.272602 |
| elapsed_min_s | 3 | 0.243807 |  | 0.00861269 | 0.233164 | 0.254258 |
| elapsed_s | 3 | 0.257239 |  | 0.00775014 | 0.25103 | 0.268165 |
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
| elapsed_max_s | 3 | 0.00457788 |  | 0.000465605 | 0.00403404 | 0.0051713 |
| elapsed_mean_s | 3 | 0.00376313 |  | 0.000240027 | 0.00342922 | 0.003983 |
| elapsed_min_s | 3 | 0.0029819 |  | 0.000345009 | 0.00260043 | 0.00343609 |
| elapsed_s | 3 | 0.00373276 |  | 0.000193156 | 0.0034802 | 0.00394917 |
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
| elapsed_max_s | 3 | 0.0159488 |  | 0.00177282 | 0.0143054 | 0.0184102 |
| elapsed_mean_s | 3 | 0.0123735 |  | 0.000373974 | 0.0120251 | 0.0128923 |
| elapsed_min_s | 3 | 0.0105426 |  | 0.000355546 | 0.0101871 | 0.0110283 |
| elapsed_s | 3 | 0.0122362 |  | 0.000656026 | 0.0114076 | 0.0130119 |
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
| elapsed_max_s | 3 | 0.0640353 |  | 0.0100854 | 0.0565391 | 0.0782919 |
| elapsed_mean_s | 3 | 0.0531303 |  | 0.00238377 | 0.0512308 | 0.0564919 |
| elapsed_min_s | 3 | 0.0488801 |  | 0.000360313 | 0.0483727 | 0.0491748 |
| elapsed_s | 3 | 0.0522867 |  | 0.00123732 | 0.051023 | 0.0539668 |
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
| elapsed_max_s | 3 | 0.0461388 |  | 0.0203279 | 0.0280666 | 0.0745368 |
| elapsed_mean_s | 3 | 0.0254736 |  | 0.0019943 | 0.0236274 | 0.0282431 |
| elapsed_min_s | 3 | 0.0200444 |  | 0.00188046 | 0.0176537 | 0.0222485 |
| elapsed_s | 3 | 0.0235778 |  | 0.000745504 | 0.0225275 | 0.0241816 |
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
| elapsed_max_s | 3 | 0.042781 |  | 0.00463424 | 0.036505 | 0.047554 |
| elapsed_mean_s | 3 | 0.034542 |  | 0.00323884 | 0.0299694 | 0.037059 |
| elapsed_min_s | 3 | 0.0254824 |  | 0.00142026 | 0.0241983 | 0.027462 |
| elapsed_s | 3 | 0.0361363 |  | 0.00329272 | 0.0314839 | 0.0386336 |
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
| elapsed_max_s | 3 | 0.0489456 |  | 0.00425419 | 0.0450408 | 0.0548618 |
| elapsed_mean_s | 3 | 0.0387336 |  | 0.00333645 | 0.0340305 | 0.0414144 |
| elapsed_min_s | 3 | 0.0327258 |  | 0.00352615 | 0.0278759 | 0.0361555 |
| elapsed_s | 3 | 0.0385035 |  | 0.0032516 | 0.0339251 | 0.0411639 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| consistent_across_runs | 3 | 3 | 0 | 1 |

### DB: ladybug | Query: top_badges (samples=3)

- Row counts: 10
- Hash stable: True

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| elapsed_max_s | 3 | 0.0666439 |  | 0.00371992 | 0.0639536 | 0.0719042 |
| elapsed_mean_s | 3 | 0.0547041 |  | 0.00270315 | 0.0511439 | 0.05769 |
| elapsed_min_s | 3 | 0.0479773 |  | 0.00302947 | 0.043833 | 0.0509903 |
| elapsed_s | 3 | 0.0541445 |  | 0.00306478 | 0.0499306 | 0.0571299 |
| row_count | 3 | 10 |  | 0 | 10 | 10 |

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
| elapsed_max_s | 3 | 0.00229613 |  | 0.000300716 | 0.0019412 | 0.00267649 |
| elapsed_mean_s | 3 | 0.00187859 |  | 8.81941e-05 | 0.00179107 | 0.00199931 |
| elapsed_min_s | 3 | 0.0013562 |  | 9.27865e-05 | 0.00122762 | 0.00144315 |
| elapsed_s | 3 | 0.0018785 |  | 5.43096e-05 | 0.00183463 | 0.00195503 |
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
| elapsed_max_s | 3 | 0.0572503 |  | 0.00677234 | 0.0512524 | 0.0667157 |
| elapsed_mean_s | 3 | 0.0475338 |  | 0.00340946 | 0.0438008 | 0.0520432 |
| elapsed_min_s | 3 | 0.0400917 |  | 0.00032516 | 0.0396318 | 0.0403249 |
| elapsed_s | 3 | 0.0484413 |  | 0.00340684 | 0.0444591 | 0.0527811 |
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
| elapsed_max_s | 3 | 0.0201855 |  | 0.00028686 | 0.0199051 | 0.0205796 |
| elapsed_mean_s | 3 | 0.0175297 |  | 0.000440995 | 0.0169956 | 0.0180757 |
| elapsed_min_s | 3 | 0.0155725 |  | 0.000724544 | 0.0148637 | 0.0165677 |
| elapsed_s | 3 | 0.0177046 |  | 0.000311373 | 0.017324 | 0.0180867 |
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
| arcadedb | 9689fb3e5b5dc76745b05b9bdf99315e5c693a51942be96a2b7854d55e547386 | 10 | True | True |
| ladybug | 9689fb3e5b5dc76745b05b9bdf99315e5c693a51942be96a2b7854d55e547386 | 10 | True | True |

### tag_cooccurrence

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | de321f4e22e0e7b3dc072a81cdf64e384cb765ef326c062d8184245ca10b733f | 10 | True | True |
| ladybug | de321f4e22e0e7b3dc072a81cdf64e384cb765ef326c062d8184245ca10b733f | 10 | True | True |

### top_accepted_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | a8c3cc366ec2c29de3cd72e9b986a6083b4a976b5a76b3544f8d023924205d10 | 10 | True | True |
| ladybug | a8c3cc366ec2c29de3cd72e9b986a6083b4a976b5a76b3544f8d023924205d10 | 10 | True | True |

### top_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 5d17f68bb37cfc841995e9cf514c0b6cb3a6d5cbb4dfa610e94986d9a48a1494 | 10 | True | True |
| ladybug | 5d17f68bb37cfc841995e9cf514c0b6cb3a6d5cbb4dfa610e94986d9a48a1494 | 10 | True | True |

### top_askers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 7d538af67ce222a3de73a1f3a2ab427d890275289ef08bb95674c539cab876b2 | 10 | True | True |
| ladybug | 7d538af67ce222a3de73a1f3a2ab427d890275289ef08bb95674c539cab876b2 | 10 | True | True |

### top_badges

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 05b80e0599745e16cb7cc6fc49481b70ad9dc1c3d3fdb6a841495d236f18078e | 10 | True | True |
| ladybug | 05b80e0599745e16cb7cc6fc49481b70ad9dc1c3d3fdb6a841495d236f18078e | 10 | True | True |

### top_questions_by_score

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 5a9cc16cff5f13ebde36a93c643d897c919b067b519e95cb60cca54a8149a7b9 | 10 | True | True |
| ladybug | 5a9cc16cff5f13ebde36a93c643d897c919b067b519e95cb60cca54a8149a7b9 | 10 | True | True |

### top_questions_by_total_comments

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 7cbb71b1a5e555c85058dc74060e649a30a728249fcdaeb6a4a515bd06ddb9d8 | 10 | True | True |
| ladybug | 7cbb71b1a5e555c85058dc74060e649a30a728249fcdaeb6a4a515bd06ddb9d8 | 10 | True | True |

### top_tags_by_questions

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | e197cbb9d184024d28373f8546a7e3fd744632d4612c025b03ffeda45ba6ad13 | 10 | True | True |
| ladybug | e197cbb9d184024d28373f8546a7e3fd744632d4612c025b03ffeda45ba6ad13 | 10 | True | True |
