# 10 Graph OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:12Z
- Dataset: stackoverflow-medium
- Dataset size profile: medium
- Label prefix: sweep10
- Total runs: 6
- Query samples: 60
- Cross-DB parity: True

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep10_r01_arcadedb_s00000, sweep10_r01_ladybug_s00001, sweep10_r02_arcadedb_s00002, sweep10_r02_ladybug_s00003, sweep10_r03_arcadedb_s00004, sweep10_r03_ladybug_s00005 |
| seed | 0, 1, 2, 3, 4, 5 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 80.874 |  | 14.1788 | 64.2675 | 98.9099 |
| disk_after_index_bytes | 3 | 1402479252 | 1.3GiB | 0 | 1402479252 | 1402479252 |
| disk_after_load_bytes | 3 | 1402479252 | 1.3GiB | 0 | 1402479252 | 1402479252 |
| disk_after_queries_bytes | 3 | 1402479252 | 1.3GiB | 0 | 1402479252 | 1402479252 |
| disk_usage.du_bytes | 3 | 1.40262e+09 | 1.3GiB | 1930.87 | 1402621952 | 1402626048 |
| edge_count | 3 | 2877037 |  | 0 | 2877037 | 2877037 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 71547 |  | 0 | 71547 | 71547 |
| edge_counts_by_type.ANSWERED | 3 | 206435 |  | 0 | 206435 | 206435 |
| edge_counts_by_type.ASKED | 3 | 210226 |  | 0 | 210226 | 210226 |
| edge_counts_by_type.COMMENTED_ON | 3 | 475470 |  | 0 | 475470 | 475470 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 344052 |  | 0 | 344052 | 344052 |
| edge_counts_by_type.EARNED | 3 | 612258 |  | 0 | 612258 | 612258 |
| edge_counts_by_type.HAS_ANSWER | 3 | 208986 |  | 0 | 208986 | 208986 |
| edge_counts_by_type.LINKED_TO | 3 | 85669 |  | 0 | 85669 | 85669 |
| edge_counts_by_type.TAGGED_WITH | 3 | 662394 |  | 0 | 662394 | 662394 |
| index_time_s | 3 | 16.7786 |  | 1.48777 | 14.9186 | 18.5604 |
| load_counts_time_s | 3 | 74.5149 |  | 21.0229 | 45.4425 | 94.4399 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 44.495 |  | 6.61231 | 35.3295 | 50.684 |
| load_stats.edges.ANSWERED | 3 | 137.618 |  | 12.9508 | 120.407 | 151.648 |
| load_stats.edges.ASKED | 3 | 142.751 |  | 15.5153 | 130.478 | 164.639 |
| load_stats.edges.COMMENTED_ON | 3 | 589.949 |  | 114.325 | 448.271 | 728.249 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 589.949 |  | 114.325 | 448.271 | 728.249 |
| load_stats.edges.EARNED | 3 | 405.761 |  | 74.8748 | 312.619 | 495.953 |
| load_stats.edges.HAS_ANSWER | 3 | 131.579 |  | 17.3873 | 108.846 | 151.062 |
| load_stats.edges.LINKED_TO | 3 | 56.4793 |  | 9.56071 | 44.9222 | 68.3354 |
| load_stats.edges.TAGGED_WITH | 3 | 356.666 |  | 55.045 | 279.46 | 403.897 |
| load_stats.nodes.Badge | 3 | 146.225 |  | 8.73002 | 139.452 | 158.551 |
| load_stats.nodes.Comment | 3 | 231.111 |  | 18.1549 | 214.815 | 256.441 |
| load_stats.nodes.Post | 3 | 197.805 |  | 27.9332 | 172.148 | 236.647 |
| load_stats.nodes.Tag | 3 | 6.07194 |  | 6.12756 | 0.689366 | 14.6447 |
| load_stats.nodes.User | 3 | 97.2988 |  | 3.84901 | 93.2256 | 102.463 |
| load_time_including_index_s | 3 | 2560.72 |  | 335.341 | 2147.66 | 2969.04 |
| load_time_s | 3 | 2543.94 |  | 334.54 | 2132.74 | 2952.18 |
| node_count | 3 | 2202019 |  | 0 | 2202019 | 2202019 |
| node_counts_by_type.Answer | 3 | 208986 |  | 0 | 208986 | 208986 |
| node_counts_by_type.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| node_counts_by_type.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| node_counts_by_type.Question | 3 | 213761 |  | 0 | 213761 | 213761 |
| node_counts_by_type.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| node_counts_by_type.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| query_cold_time_s | 3 | 3.26294 |  | 0.837971 | 2.34979 | 4.37367 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 302.93 |  | 56.2823 | 225.236 | 356.753 |
| query_warm_mean_s | 3 | 3.00294 |  | 0.544139 | 2.24105 | 3.47754 |
| rss_peak_kb | 3 | 3.78562e+06 | 3.6GiB | 76270.8 | 3680632 | 3859544 |
| schema_time_s | 3 | 0.136759 |  | 0.00285204 | 0.134159 | 0.140729 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| total_time_s | 3 | 3019.79 |  | 397.269 | 2518.1 | 3489.65 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: ladybug (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 5000 |  | 0 | 5000 | 5000 |
| counts_time_s | 3 | 0.129285 |  | 0.0148204 | 0.11233 | 0.148433 |
| disk_after_index_bytes | 3 | 1.90644e+09 | 1.8GiB | 10217.2 | 1906432554 | 1906457130 |
| disk_after_load_bytes | 3 | 1.90644e+09 | 1.8GiB | 10217.2 | 1906432554 | 1906457130 |
| disk_after_queries_bytes | 3 | 1.90644e+09 | 1.8GiB | 10217.2 | 1906432554 | 1906457130 |
| disk_usage.du_bytes | 3 | 1906532352 | 1.8GiB | 3344.37 | 1906528256 | 1906536448 |
| edge_count | 3 | 2877037 |  | 0 | 2877037 | 2877037 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 71547 |  | 0 | 71547 | 71547 |
| edge_counts_by_type.ANSWERED | 3 | 206435 |  | 0 | 206435 | 206435 |
| edge_counts_by_type.ASKED | 3 | 210226 |  | 0 | 210226 | 210226 |
| edge_counts_by_type.COMMENTED_ON | 3 | 475470 |  | 0 | 475470 | 475470 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 344052 |  | 0 | 344052 | 344052 |
| edge_counts_by_type.EARNED | 3 | 612258 |  | 0 | 612258 | 612258 |
| edge_counts_by_type.HAS_ANSWER | 3 | 208986 |  | 0 | 208986 | 208986 |
| edge_counts_by_type.LINKED_TO | 3 | 85669 |  | 0 | 85669 | 85669 |
| edge_counts_by_type.TAGGED_WITH | 3 | 662394 |  | 0 | 662394 | 662394 |
| index_time_s | 3 | 0 |  | 0 | 0 | 0 |
| load_counts_time_s | 3 | 0.163872 |  | 0.0491625 | 0.129019 | 0.233399 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.0833055 |  | 0.00815965 | 0.0717661 | 0.0891187 |
| load_stats.edges.ANSWERED | 3 | 0.134202 |  | 0.0229127 | 0.107563 | 0.163498 |
| load_stats.edges.ASKED | 3 | 0.163959 |  | 0.0571631 | 0.1076 | 0.24233 |
| load_stats.edges.COMMENTED_ON | 3 | 0.235833 |  | 0.0105851 | 0.220922 | 0.244435 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.174318 |  | 0.0135732 | 0.163 | 0.193404 |
| load_stats.edges.EARNED | 3 | 0.250364 |  | 0.0429548 | 0.193677 | 0.297617 |
| load_stats.edges.HAS_ANSWER | 3 | 0.111775 |  | 0.0117392 | 0.0987501 | 0.127203 |
| load_stats.edges.LINKED_TO | 3 | 0.140776 |  | 0.0593186 | 0.0870938 | 0.223444 |
| load_stats.edges.TAGGED_WITH | 3 | 0.185276 |  | 0.0269464 | 0.149376 | 0.214298 |
| load_stats.nodes.Answer | 3 | 6.1457 |  | 2.02943 | 4.45367 | 8.99937 |
| load_stats.nodes.Badge | 3 | 0.328358 |  | 0.0894691 | 0.239014 | 0.450621 |
| load_stats.nodes.Comment | 3 | 4.57801 |  | 0.570577 | 4.01463 | 5.35999 |
| load_stats.nodes.Post | 3 | 11.5985 |  | 2.80061 | 9.16519 | 15.5215 |
| load_stats.nodes.Question | 3 | 5.45283 |  | 0.966372 | 4.18113 | 6.52216 |
| load_stats.nodes.Tag | 3 | 0.147526 |  | 0.037612 | 0.0973959 | 0.187993 |
| load_stats.nodes.User | 3 | 0.540513 |  | 0.0156296 | 0.526038 | 0.562217 |
| load_time_including_index_s | 3 | 130.318 |  | 9.5783 | 119.752 | 142.941 |
| load_time_s | 3 | 130.318 |  | 9.5783 | 119.752 | 142.941 |
| node_count | 3 | 2202019 |  | 0 | 2202019 | 2202019 |
| node_counts_by_type.Answer | 3 | 208986 |  | 0 | 208986 | 208986 |
| node_counts_by_type.Badge | 3 | 612258 |  | 0 | 612258 | 612258 |
| node_counts_by_type.Comment | 3 | 819648 |  | 0 | 819648 | 819648 |
| node_counts_by_type.Question | 3 | 213761 |  | 0 | 213761 | 213761 |
| node_counts_by_type.Tag | 3 | 1612 |  | 0 | 1612 | 1612 |
| node_counts_by_type.User | 3 | 345754 |  | 0 | 345754 | 345754 |
| query_cold_time_s | 3 | 0.115923 |  | 0.0172707 | 0.0945869 | 0.136886 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 10.051 |  | 2.74892 | 7.95711 | 13.9346 |
| query_warm_mean_s | 3 | 0.0983495 |  | 0.0288198 | 0.0751641 | 0.138972 |
| rss_peak_kb | 3 | 3.10975e+06 | 3.0GiB | 7487.49 | 3099420 | 3116932 |
| schema_time_s | 3 | 0.165683 |  | 0.01462 | 0.153389 | 0.186227 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| total_time_s | 3 | 141.353 |  | 12.4379 | 128.456 | 158.16 |

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
| elapsed_max_s | 3 | 2.98023 |  | 0.761427 | 1.92218 | 3.68259 |
| elapsed_mean_s | 3 | 1.82051 |  | 0.374732 | 1.29362 | 2.13325 |
| elapsed_min_s | 3 | 1.32178 |  | 0.220819 | 1.02758 | 1.55957 |
| elapsed_s | 3 | 1.69228 |  | 0.292545 | 1.2833 | 1.95083 |
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
| elapsed_max_s | 3 | 4.50988 |  | 1.48408 | 2.76602 | 6.39323 |
| elapsed_mean_s | 3 | 2.14569 |  | 0.533125 | 1.39338 | 2.56493 |
| elapsed_min_s | 3 | 1.04479 |  | 0.18011 | 0.910611 | 1.29938 |
| elapsed_s | 3 | 1.73002 |  | 0.420409 | 1.20558 | 2.23481 |
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
| elapsed_max_s | 3 | 15.381 |  | 6.56004 | 9.83929 | 24.5953 |
| elapsed_mean_s | 3 | 10.4512 |  | 2.95671 | 7.09403 | 14.2885 |
| elapsed_min_s | 3 | 9.11578 |  | 2.46077 | 6.32742 | 12.3132 |
| elapsed_s | 3 | 10.0254 |  | 2.61851 | 6.69499 | 13.0928 |
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
| elapsed_max_s | 3 | 8.22321 |  | 1.97471 | 5.43232 | 9.70483 |
| elapsed_mean_s | 3 | 4.64287 |  | 0.853794 | 4.03684 | 5.85032 |
| elapsed_min_s | 3 | 1.76498 |  | 0.527022 | 1.17123 | 2.45201 |
| elapsed_s | 3 | 4.39588 |  | 1.18147 | 2.98657 | 5.87784 |
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
| elapsed_max_s | 3 | 4.14022 |  | 1.07562 | 2.85323 | 5.48598 |
| elapsed_mean_s | 3 | 2.02085 |  | 0.120101 | 1.87199 | 2.16611 |
| elapsed_min_s | 3 | 1.05257 |  | 0.26004 | 0.765172 | 1.39497 |
| elapsed_s | 3 | 1.84253 |  | 0.146857 | 1.69482 | 2.04282 |
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
| elapsed_max_s | 3 | 2.48696 |  | 0.740874 | 1.69978 | 3.47938 |
| elapsed_mean_s | 3 | 1.5848 |  | 0.368538 | 1.10182 | 1.99593 |
| elapsed_min_s | 3 | 1.26408 |  | 0.406473 | 0.852077 | 1.81724 |
| elapsed_s | 3 | 1.47396 |  | 0.401591 | 0.966722 | 1.94881 |
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
| elapsed_max_s | 3 | 3.29009 |  | 0.292119 | 2.87701 | 3.50137 |
| elapsed_mean_s | 3 | 2.67353 |  | 0.516226 | 1.95593 | 3.14858 |
| elapsed_min_s | 3 | 2.20787 |  | 0.474359 | 1.56296 | 2.69032 |
| elapsed_s | 3 | 2.65985 |  | 0.611306 | 1.82121 | 3.26096 |
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
| elapsed_max_s | 3 | 0.680978 |  | 0.113059 | 0.568724 | 0.83571 |
| elapsed_mean_s | 3 | 0.39213 |  | 0.0732848 | 0.303035 | 0.482531 |
| elapsed_min_s | 3 | 0.240387 |  | 0.0483741 | 0.196899 | 0.307866 |
| elapsed_s | 3 | 0.360337 |  | 0.0658604 | 0.267909 | 0.416512 |
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
| elapsed_max_s | 3 | 4.30309 |  | 0.6319 | 3.423 | 4.87742 |
| elapsed_mean_s | 3 | 2.52291 |  | 0.36601 | 2.01362 | 2.85762 |
| elapsed_min_s | 3 | 1.42656 |  | 0.33088 | 0.966638 | 1.73119 |
| elapsed_s | 3 | 2.73978 |  | 0.485756 | 2.06655 | 3.19475 |
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
| elapsed_max_s | 3 | 2.79071 |  | 0.668778 | 1.84742 | 3.32191 |
| elapsed_mean_s | 3 | 2.03495 |  | 0.41259 | 1.455 | 2.38051 |
| elapsed_min_s | 3 | 1.61323 |  | 0.359909 | 1.21547 | 2.08714 |
| elapsed_s | 3 | 1.95528 |  | 0.387157 | 1.40998 | 2.27067 |
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
| elapsed_max_s | 3 | 0.0131884 |  | 0.00725007 | 0.00517821 | 0.0227363 |
| elapsed_mean_s | 3 | 0.00551814 |  | 0.00121909 | 0.00393062 | 0.00689421 |
| elapsed_min_s | 3 | 0.00307997 |  | 0.000416285 | 0.00262475 | 0.00363088 |
| elapsed_s | 3 | 0.00475152 |  | 0.000823305 | 0.00412059 | 0.00591445 |
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
| elapsed_max_s | 3 | 0.183278 |  | 0.0358312 | 0.13588 | 0.222497 |
| elapsed_mean_s | 3 | 0.115491 |  | 0.0300597 | 0.091212 | 0.157851 |
| elapsed_min_s | 3 | 0.0862132 |  | 0.0214311 | 0.0710511 | 0.116521 |
| elapsed_s | 3 | 0.110617 |  | 0.0353238 | 0.0832469 | 0.160494 |
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
| elapsed_max_s | 3 | 0.31759 |  | 0.108614 | 0.199078 | 0.461474 |
| elapsed_mean_s | 3 | 0.229879 |  | 0.0533877 | 0.179975 | 0.303898 |
| elapsed_min_s | 3 | 0.169575 |  | 0.0168499 | 0.154132 | 0.193013 |
| elapsed_s | 3 | 0.22865 |  | 0.0586298 | 0.177799 | 0.310792 |
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
| elapsed_max_s | 3 | 0.0729793 |  | 0.0260003 | 0.0458829 | 0.108053 |
| elapsed_mean_s | 3 | 0.0527565 |  | 0.0183185 | 0.0394542 | 0.0786597 |
| elapsed_min_s | 3 | 0.0363479 |  | 0.0110211 | 0.0281079 | 0.0519254 |
| elapsed_s | 3 | 0.0507133 |  | 0.0147664 | 0.0391252 | 0.0715525 |
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
| elapsed_max_s | 3 | 0.158067 |  | 0.0629365 | 0.0783415 | 0.232199 |
| elapsed_mean_s | 3 | 0.100881 |  | 0.0384408 | 0.0700482 | 0.155073 |
| elapsed_min_s | 3 | 0.0661662 |  | 0.0157396 | 0.0517588 | 0.0880642 |
| elapsed_s | 3 | 0.103683 |  | 0.0481269 | 0.0661082 | 0.171618 |
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
| elapsed_max_s | 3 | 0.22176 |  | 0.0751301 | 0.117293 | 0.290781 |
| elapsed_mean_s | 3 | 0.11166 |  | 0.0309809 | 0.082929 | 0.154672 |
| elapsed_min_s | 3 | 0.072777 |  | 0.00825118 | 0.0643802 | 0.0839927 |
| elapsed_s | 3 | 0.100839 |  | 0.0279533 | 0.0791399 | 0.140306 |
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
| elapsed_max_s | 3 | 0.259434 |  | 0.100736 | 0.131197 | 0.377293 |
| elapsed_mean_s | 3 | 0.159812 |  | 0.0492904 | 0.113667 | 0.228131 |
| elapsed_min_s | 3 | 0.101396 |  | 0.0243404 | 0.0804009 | 0.135517 |
| elapsed_s | 3 | 0.142078 |  | 0.0385451 | 0.11408 | 0.196582 |
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
| elapsed_max_s | 3 | 0.0182772 |  | 0.0183736 | 0.00474906 | 0.0442538 |
| elapsed_mean_s | 3 | 0.0042239 |  | 0.00169155 | 0.0024236 | 0.0064883 |
| elapsed_min_s | 3 | 0.00192189 |  | 0.000241723 | 0.00159144 | 0.00216293 |
| elapsed_s | 3 | 0.00276351 |  | 0.00063184 | 0.00229263 | 0.00365663 |
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
| elapsed_max_s | 3 | 0.211323 |  | 0.06971 | 0.15781 | 0.309783 |
| elapsed_mean_s | 3 | 0.171602 |  | 0.0492294 | 0.134924 | 0.241189 |
| elapsed_min_s | 3 | 0.13792 |  | 0.0302955 | 0.110928 | 0.180231 |
| elapsed_s | 3 | 0.170189 |  | 0.0486719 | 0.135534 | 0.239021 |
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
| elapsed_max_s | 3 | 0.0709717 |  | 0.00979245 | 0.0572124 | 0.0792108 |
| elapsed_mean_s | 3 | 0.0492458 |  | 0.00585947 | 0.0445066 | 0.0575023 |
| elapsed_min_s | 3 | 0.0393545 |  | 0.00248152 | 0.0359819 | 0.0418811 |
| elapsed_s | 3 | 0.0485294 |  | 0.0078973 | 0.0428829 | 0.0596976 |
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
| arcadedb | 155492c2f7710979abfeed42b68b65e31fa95a7fd204d37585a62878f9d8c1d1 | 10 | True | True |
| ladybug | 155492c2f7710979abfeed42b68b65e31fa95a7fd204d37585a62878f9d8c1d1 | 10 | True | True |

### tag_cooccurrence

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 526e9967c0daa8d13464bc4d80764b3c29f354c6c56b0b43bbf7e2473519a703 | 10 | True | True |
| ladybug | 526e9967c0daa8d13464bc4d80764b3c29f354c6c56b0b43bbf7e2473519a703 | 10 | True | True |

### top_accepted_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | d3212f9008dc74363c3c91a2a0524caeca7c0152abb74705cefed08aa1e82503 | 10 | True | True |
| ladybug | d3212f9008dc74363c3c91a2a0524caeca7c0152abb74705cefed08aa1e82503 | 10 | True | True |

### top_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 61f3be3d7d7a0f211aaad9171597a9706dd03365ed4b90d7e6ca05fae7bd6ab4 | 10 | True | True |
| ladybug | 61f3be3d7d7a0f211aaad9171597a9706dd03365ed4b90d7e6ca05fae7bd6ab4 | 10 | True | True |

### top_askers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | a024896d12c8d03616031e5258e99a2b874571f7b38da2ab3ed898f19049771e | 10 | True | True |
| ladybug | a024896d12c8d03616031e5258e99a2b874571f7b38da2ab3ed898f19049771e | 10 | True | True |

### top_badges

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 61f2dab3769105304440cbf21baeafc65a02490784cfd507f5dc5b3d780aa477 | 10 | True | True |
| ladybug | 61f2dab3769105304440cbf21baeafc65a02490784cfd507f5dc5b3d780aa477 | 10 | True | True |

### top_questions_by_score

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 8ae48f2ff3e6b0ba88732c73f1ecdcc97c189c733f5546fc152ef080bbf2db49 | 10 | True | True |
| ladybug | 8ae48f2ff3e6b0ba88732c73f1ecdcc97c189c733f5546fc152ef080bbf2db49 | 10 | True | True |

### top_questions_by_total_comments

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | bc63940adee8094bf65bf43163b577d43c10bffcc646187404f068a3f15e8655 | 10 | True | True |
| ladybug | bc63940adee8094bf65bf43163b577d43c10bffcc646187404f068a3f15e8655 | 10 | True | True |

### top_tags_by_questions

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 2d776db39b29c30b50142a15a6bfc5d570a884a6de3e7237cc65bb5de3c664ad | 10 | True | True |
| ladybug | 2d776db39b29c30b50142a15a6bfc5d570a884a6de3e7237cc65bb5de3c664ad | 10 | True | True |
