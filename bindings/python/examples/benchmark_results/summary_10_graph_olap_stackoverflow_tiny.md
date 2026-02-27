# 10 Graph OLAP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:12Z
- Dataset: stackoverflow-tiny
- Dataset size profile: tiny
- Label prefix: sweep10
- Total runs: 6
- Query samples: 60
- Cross-DB parity: True

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
| query_order | shuffled |
| query_runs | 10 |
| run_label | sweep10_r01_arcadedb_s00000, sweep10_r01_ladybug_s00001, sweep10_r02_arcadedb_s00002, sweep10_r02_ladybug_s00003, sweep10_r03_arcadedb_s00004, sweep10_r03_ladybug_s00005 |
| seed | 0, 1, 2, 3, 4, 5 |

## Aggregated Metrics by DB

### DB: arcadedb (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.418043 |  | 0.0238451 | 0.393493 | 0.45034 |
| disk_after_index_bytes | 3 | 2.80377e+07 | 26.7MiB | 5.06845e+06 | 24453780 | 35205587 |
| disk_after_load_bytes | 3 | 2.80377e+07 | 26.7MiB | 5.06845e+06 | 24453780 | 35205587 |
| disk_after_queries_bytes | 3 | 2.80377e+07 | 26.7MiB | 5.06845e+06 | 24453780 | 35205587 |
| disk_usage.du_bytes | 3 | 2.45091e+07 | 23.4MiB | 3861.75 | 24506368 | 24514560 |
| edge_count | 3 | 42088 |  | 0 | 42088 | 42088 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2142 |  | 0 | 2142 | 2142 |
| edge_counts_by_type.ANSWERED | 3 | 5618 |  | 0 | 5618 | 5618 |
| edge_counts_by_type.ASKED | 3 | 3563 |  | 0 | 3563 | 3563 |
| edge_counts_by_type.COMMENTED_ON | 3 | 4858 |  | 0 | 4858 | 4858 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5142 |  | 0 | 5142 | 5142 |
| edge_counts_by_type.EARNED | 3 | 3523 |  | 0 | 3523 | 3523 |
| edge_counts_by_type.HAS_ANSWER | 3 | 5767 |  | 0 | 5767 | 5767 |
| edge_counts_by_type.LINKED_TO | 3 | 786 |  | 0 | 786 | 786 |
| edge_counts_by_type.TAGGED_WITH | 3 | 10689 |  | 0 | 10689 | 10689 |
| index_time_s | 3 | 0.230472 |  | 0.0132803 | 0.216036 | 0.248094 |
| load_counts_time_s | 3 | 0.958989 |  | 0.101222 | 0.874598 | 1.10132 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 1.94977 |  | 0.864236 | 0.727683 | 2.5761 |
| load_stats.edges.ANSWERED | 3 | 4.24947 |  | 0.244327 | 4.02104 | 4.58821 |
| load_stats.edges.ASKED | 3 | 3.72643 |  | 0.14111 | 3.56757 | 3.91046 |
| load_stats.edges.COMMENTED_ON | 3 | 6.12145 |  | 1.32961 | 5.05861 | 7.99621 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 6.12145 |  | 1.32961 | 5.05861 | 7.99621 |
| load_stats.edges.EARNED | 3 | 3.87095 |  | 0.332244 | 3.53813 | 4.32459 |
| load_stats.edges.HAS_ANSWER | 3 | 2.29462 |  | 0.958849 | 1.52362 | 3.64617 |
| load_stats.edges.LINKED_TO | 3 | 0.260804 |  | 0.0292162 | 0.230729 | 0.300377 |
| load_stats.edges.TAGGED_WITH | 3 | 5.52868 |  | 1.38889 | 4.54507 | 7.49285 |
| load_stats.nodes.Badge | 3 | 3.56762 |  | 0.0833757 | 3.49367 | 3.68413 |
| load_stats.nodes.Comment | 3 | 3.58497 |  | 0.0632024 | 3.51985 | 3.67055 |
| load_stats.nodes.Post | 3 | 4.4982 |  | 0.922818 | 3.20824 | 5.31462 |
| load_stats.nodes.Tag | 3 | 1.83571 |  | 1.88893 | 0.49624 | 4.50707 |
| load_stats.nodes.User | 3 | 9.98934 |  | 1.98795 | 8.16856 | 12.7549 |
| load_time_including_index_s | 3 | 51.7099 |  | 3.88239 | 46.944 | 56.4537 |
| load_time_s | 3 | 51.4794 |  | 3.87776 | 46.7279 | 56.2265 |
| node_count | 3 | 40260 |  | 0 | 40260 | 40260 |
| node_counts_by_type.Answer | 3 | 5767 |  | 0 | 5767 | 5767 |
| node_counts_by_type.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| node_counts_by_type.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| node_counts_by_type.Question | 3 | 3825 |  | 0 | 3825 | 3825 |
| node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| node_counts_by_type.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| query_cold_time_s | 3 | 0.0577356 |  | 0.00387605 | 0.054544 | 0.0631909 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 3.69115 |  | 0.213056 | 3.3976 | 3.89674 |
| query_warm_mean_s | 3 | 0.034394 |  | 0.00204535 | 0.0315123 | 0.0360518 |
| rss_peak_kb | 3 | 981357 | 958.4MiB | 6320.42 | 973140 | 988512 |
| schema_time_s | 3 | 0.0806681 |  | 0.0153601 | 0.0590291 | 0.0931344 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| total_time_s | 3 | 57.3288 |  | 4.20687 | 52.1708 | 62.4755 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
| query_result_hash_stable | 3 | 3 | 0 | 1 |
| query_row_count_stable | 3 | 3 | 0 | 1 |

### DB: ladybug (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 1000 |  | 0 | 1000 | 1000 |
| counts_time_s | 3 | 0.0984108 |  | 0.00140646 | 0.0969441 | 0.100308 |
| disk_after_index_bytes | 3 | 48935102 | 46.7MiB | 0 | 48935102 | 48935102 |
| disk_after_load_bytes | 3 | 48935102 | 46.7MiB | 0 | 48935102 | 48935102 |
| disk_after_queries_bytes | 3 | 48935102 | 46.7MiB | 0 | 48935102 | 48935102 |
| disk_usage.du_bytes | 3 | 4.90059e+07 | 46.7MiB | 7723.49 | 49000448 | 49016832 |
| edge_count | 3 | 42088 |  | 0 | 42088 | 42088 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 2142 |  | 0 | 2142 | 2142 |
| edge_counts_by_type.ANSWERED | 3 | 5618 |  | 0 | 5618 | 5618 |
| edge_counts_by_type.ASKED | 3 | 3563 |  | 0 | 3563 | 3563 |
| edge_counts_by_type.COMMENTED_ON | 3 | 4858 |  | 0 | 4858 | 4858 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 5142 |  | 0 | 5142 | 5142 |
| edge_counts_by_type.EARNED | 3 | 3523 |  | 0 | 3523 | 3523 |
| edge_counts_by_type.HAS_ANSWER | 3 | 5767 |  | 0 | 5767 | 5767 |
| edge_counts_by_type.LINKED_TO | 3 | 786 |  | 0 | 786 | 786 |
| edge_counts_by_type.TAGGED_WITH | 3 | 10689 |  | 0 | 10689 | 10689 |
| index_time_s | 3 | 0 |  | 0 | 0 | 0 |
| load_counts_time_s | 3 | 0.0498708 |  | 0.0128982 | 0.0347493 | 0.0662661 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 0.0530647 |  | 0.0141984 | 0.0347033 | 0.0692835 |
| load_stats.edges.ANSWERED | 3 | 0.0520542 |  | 0.0115112 | 0.0357859 | 0.0607083 |
| load_stats.edges.ASKED | 3 | 0.0641309 |  | 0.0173716 | 0.0431137 | 0.0856562 |
| load_stats.edges.COMMENTED_ON | 3 | 0.0613387 |  | 0.00658023 | 0.0546746 | 0.0702958 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 0.0641835 |  | 0.00272694 | 0.0608344 | 0.0675139 |
| load_stats.edges.EARNED | 3 | 0.0538453 |  | 0.00851771 | 0.0427647 | 0.0634773 |
| load_stats.edges.HAS_ANSWER | 3 | 0.0522209 |  | 0.0120416 | 0.0353825 | 0.0628428 |
| load_stats.edges.LINKED_TO | 3 | 0.0522497 |  | 0.0094565 | 0.039356 | 0.0617709 |
| load_stats.edges.TAGGED_WITH | 3 | 0.0546916 |  | 0.0126716 | 0.0368958 | 0.0654156 |
| load_stats.nodes.Answer | 3 | 0.888413 |  | 0.832732 | 0.258014 | 2.06507 |
| load_stats.nodes.Badge | 3 | 0.118017 |  | 0.0417821 | 0.0633929 | 0.164842 |
| load_stats.nodes.Comment | 3 | 0.16855 |  | 0.061715 | 0.116067 | 0.255184 |
| load_stats.nodes.Post | 3 | 1.79445 |  | 0.768471 | 0.708291 | 2.36946 |
| load_stats.nodes.Question | 3 | 0.906034 |  | 0.853896 | 0.24052 | 2.11145 |
| load_stats.nodes.Tag | 3 | 1.23217 |  | 1.45607 | 0.11437 | 3.28876 |
| load_stats.nodes.User | 3 | 1.35213 |  | 1.66057 | 0.121792 | 3.69962 |
| load_time_including_index_s | 3 | 6.47876 |  | 3.90351 | 3.24525 | 11.9704 |
| load_time_s | 3 | 6.47876 |  | 3.90351 | 3.24525 | 11.9704 |
| node_count | 3 | 40260 |  | 0 | 40260 | 40260 |
| node_counts_by_type.Answer | 3 | 5767 |  | 0 | 5767 | 5767 |
| node_counts_by_type.Badge | 3 | 10000 |  | 0 | 10000 | 10000 |
| node_counts_by_type.Comment | 3 | 10000 |  | 0 | 10000 | 10000 |
| node_counts_by_type.Question | 3 | 3825 |  | 0 | 3825 | 3825 |
| node_counts_by_type.Tag | 3 | 668 |  | 0 | 668 | 668 |
| node_counts_by_type.User | 3 | 10000 |  | 0 | 10000 | 10000 |
| query_cold_time_s | 3 | 0.0207384 |  | 0.00146001 | 0.0186743 | 0.0218164 |
| query_runs | 3 | 10 |  | 0 | 10 | 10 |
| query_time_s | 3 | 2.35069 |  | 0.253643 | 2.00917 | 2.61644 |
| query_warm_mean_s | 3 | 0.023532 |  | 0.00266272 | 0.0199776 | 0.0263862 |
| rss_peak_kb | 3 | 778735 | 760.5MiB | 14638.8 | 762028 | 797676 |
| schema_time_s | 3 | 0.171776 |  | 0.034784 | 0.123194 | 0.202753 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| total_time_s | 3 | 9.39299 |  | 4.1218 | 6.27665 | 15.2173 |

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
| elapsed_max_s | 3 | 0.0431327 |  | 0.0122355 | 0.0323095 | 0.0602365 |
| elapsed_mean_s | 3 | 0.0229607 |  | 0.00382207 | 0.0191923 | 0.0282007 |
| elapsed_min_s | 3 | 0.013274 |  | 0.000450232 | 0.012639 | 0.013633 |
| elapsed_s | 3 | 0.0180882 |  | 0.000830728 | 0.017236 | 0.0192146 |
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
| elapsed_max_s | 3 | 0.0846282 |  | 0.0268578 | 0.0490289 | 0.113897 |
| elapsed_mean_s | 3 | 0.0316447 |  | 0.00472213 | 0.0257178 | 0.0372731 |
| elapsed_min_s | 3 | 0.0153039 |  | 0.0012982 | 0.0134797 | 0.0163958 |
| elapsed_s | 3 | 0.0279931 |  | 0.000956067 | 0.0269043 | 0.0292318 |
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
| elapsed_max_s | 3 | 0.217852 |  | 0.0399816 | 0.186287 | 0.274262 |
| elapsed_mean_s | 3 | 0.142579 |  | 0.0107943 | 0.134149 | 0.157816 |
| elapsed_min_s | 3 | 0.0868125 |  | 0.00321099 | 0.0822768 | 0.0892711 |
| elapsed_s | 3 | 0.139725 |  | 0.0032309 | 0.13519 | 0.142479 |
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
| elapsed_max_s | 3 | 0.0848265 |  | 0.0124744 | 0.0731447 | 0.102116 |
| elapsed_mean_s | 3 | 0.0391045 |  | 0.00104537 | 0.0381052 | 0.0405477 |
| elapsed_min_s | 3 | 0.0229835 |  | 0.00109886 | 0.0214474 | 0.0239556 |
| elapsed_s | 3 | 0.0376134 |  | 0.00523425 | 0.0302532 | 0.0419765 |
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
| elapsed_max_s | 3 | 0.0520786 |  | 0.00328345 | 0.0492706 | 0.0566854 |
| elapsed_mean_s | 3 | 0.0273221 |  | 0.00430089 | 0.0239924 | 0.0333951 |
| elapsed_min_s | 3 | 0.0160711 |  | 0.000910476 | 0.0154002 | 0.0173583 |
| elapsed_s | 3 | 0.0245153 |  | 0.00568761 | 0.0194104 | 0.0324509 |
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
| elapsed_max_s | 3 | 0.036231 |  | 0.00285205 | 0.0342133 | 0.0402644 |
| elapsed_mean_s | 3 | 0.0216747 |  | 0.00213458 | 0.0188653 | 0.024036 |
| elapsed_min_s | 3 | 0.0129499 |  | 0.00073522 | 0.0119727 | 0.013746 |
| elapsed_s | 3 | 0.0215188 |  | 0.00427093 | 0.0156116 | 0.0255635 |
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
| elapsed_max_s | 3 | 0.0296024 |  | 0.00766105 | 0.0218399 | 0.0400293 |
| elapsed_mean_s | 3 | 0.0165912 |  | 0.00135074 | 0.015148 | 0.0183966 |
| elapsed_min_s | 3 | 0.0107191 |  | 0.000586832 | 0.00990152 | 0.0112514 |
| elapsed_s | 3 | 0.0142989 |  | 0.000907009 | 0.0130188 | 0.0150101 |
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
| elapsed_max_s | 3 | 0.0236129 |  | 0.00822315 | 0.0173206 | 0.0352287 |
| elapsed_mean_s | 3 | 0.0086609 |  | 0.0016949 | 0.00733881 | 0.0110534 |
| elapsed_min_s | 3 | 0.00403404 |  | 0.000215659 | 0.00378442 | 0.00431061 |
| elapsed_s | 3 | 0.00596778 |  | 0.00063712 | 0.00508404 | 0.00656176 |
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
| elapsed_max_s | 3 | 0.0398639 |  | 0.00193976 | 0.0372069 | 0.0417833 |
| elapsed_mean_s | 3 | 0.02567 |  | 0.00339272 | 0.0224214 | 0.0303522 |
| elapsed_min_s | 3 | 0.016666 |  | 0.00264606 | 0.0141656 | 0.0203273 |
| elapsed_s | 3 | 0.0258756 |  | 0.00503224 | 0.0217955 | 0.0329654 |
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
| elapsed_max_s | 3 | 0.0614454 |  | 0.00842133 | 0.0496104 | 0.0685151 |
| elapsed_mean_s | 3 | 0.0310732 |  | 0.00259761 | 0.027404 | 0.0330619 |
| elapsed_min_s | 3 | 0.0190848 |  | 0.00152439 | 0.0173635 | 0.0210695 |
| elapsed_s | 3 | 0.0241234 |  | 0.0022414 | 0.0215526 | 0.0270147 |
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
| elapsed_max_s | 3 | 0.0293612 |  | 0.0275375 | 0.00667596 | 0.0681174 |
| elapsed_mean_s | 3 | 0.00658727 |  | 0.00333842 | 0.00375183 | 0.0112742 |
| elapsed_min_s | 3 | 0.00289392 |  | 0.000199252 | 0.00266337 | 0.00314951 |
| elapsed_s | 3 | 0.00377639 |  | 0.000329211 | 0.00349855 | 0.00423884 |
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
| elapsed_max_s | 3 | 0.0773649 |  | 0.00456041 | 0.0710866 | 0.0817821 |
| elapsed_mean_s | 3 | 0.025606 |  | 0.00518043 | 0.0187157 | 0.0312071 |
| elapsed_min_s | 3 | 0.0049475 |  | 0.000347336 | 0.00459862 | 0.0054214 |
| elapsed_s | 3 | 0.00847419 |  | 0.00186683 | 0.0065496 | 0.0110016 |
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
| elapsed_max_s | 3 | 0.0886535 |  | 0.00604963 | 0.0822258 | 0.0967572 |
| elapsed_mean_s | 3 | 0.0404775 |  | 0.00947122 | 0.02816 | 0.0511932 |
| elapsed_min_s | 3 | 0.0106586 |  | 0.00046933 | 0.0101023 | 0.0112503 |
| elapsed_s | 3 | 0.0389285 |  | 0.0289359 | 0.0156386 | 0.0797131 |
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
| elapsed_max_s | 3 | 0.0765276 |  | 0.0065138 | 0.0683122 | 0.0842443 |
| elapsed_mean_s | 3 | 0.0247813 |  | 0.00384355 | 0.0206993 | 0.0299307 |
| elapsed_min_s | 3 | 0.00719086 |  | 0.000920463 | 0.00590944 | 0.00802994 |
| elapsed_s | 3 | 0.00992171 |  | 0.000301117 | 0.00958586 | 0.0103164 |
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
| elapsed_max_s | 3 | 0.0827157 |  | 0.00392039 | 0.0771806 | 0.0857601 |
| elapsed_mean_s | 3 | 0.0249203 |  | 0.00197688 | 0.0224355 | 0.0272723 |
| elapsed_min_s | 3 | 0.00719786 |  | 0.000110915 | 0.00704169 | 0.00728869 |
| elapsed_s | 3 | 0.0103676 |  | 0.00221899 | 0.0080502 | 0.0133588 |
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
| elapsed_max_s | 3 | 0.0740631 |  | 0.00441332 | 0.0678449 | 0.077637 |
| elapsed_mean_s | 3 | 0.0192132 |  | 0.00138651 | 0.0174196 | 0.0207963 |
| elapsed_min_s | 3 | 0.0067753 |  | 0.000455968 | 0.00630307 | 0.00739169 |
| elapsed_s | 3 | 0.00795515 |  | 0.000289145 | 0.00755525 | 0.00822902 |
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
| elapsed_max_s | 3 | 0.0766367 |  | 0.00281104 | 0.0726843 | 0.0789826 |
| elapsed_mean_s | 3 | 0.0178857 |  | 0.00673773 | 0.0121394 | 0.0273414 |
| elapsed_min_s | 3 | 0.00460847 |  | 0.000419861 | 0.00412226 | 0.00514674 |
| elapsed_s | 3 | 0.00687432 |  | 0.00106196 | 0.00544477 | 0.00798774 |
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
| elapsed_max_s | 3 | 0.00367769 |  | 0.00274546 | 0.00161171 | 0.00755763 |
| elapsed_mean_s | 3 | 0.00160328 |  | 0.000365073 | 0.00134335 | 0.00211957 |
| elapsed_min_s | 3 | 0.00102361 |  | 0.000130966 | 0.000848532 | 0.00116348 |
| elapsed_s | 3 | 0.00137583 |  | 4.33897e-05 | 0.00133443 | 0.00143576 |
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
| elapsed_max_s | 3 | 0.0859532 |  | 0.00459185 | 0.0795524 | 0.0901022 |
| elapsed_mean_s | 3 | 0.054299 |  | 0.00895764 | 0.0424787 | 0.0641549 |
| elapsed_min_s | 3 | 0.0126705 |  | 0.00060069 | 0.0118682 | 0.0133135 |
| elapsed_s | 3 | 0.0599506 |  | 0.0248428 | 0.025387 | 0.0826883 |
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
| elapsed_max_s | 3 | 0.0598772 |  | 0.0333706 | 0.0126858 | 0.0838218 |
| elapsed_mean_s | 3 | 0.0171529 |  | 0.0087744 | 0.0076457 | 0.0288127 |
| elapsed_min_s | 3 | 0.00529178 |  | 0.000330133 | 0.00491786 | 0.00572085 |
| elapsed_s | 3 | 0.00712212 |  | 0.000443011 | 0.00655293 | 0.00763345 |
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
| arcadedb | 79bf80c5a25416bf63023d2129b4ec4e0deb92c499e6b826aeb454174fb7b086 | 10 | True | True |
| ladybug | 79bf80c5a25416bf63023d2129b4ec4e0deb92c499e6b826aeb454174fb7b086 | 10 | True | True |

### tag_cooccurrence

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 681e115aa8b9e11109a461411bff6b49723fa64db18e008cc9702f55212b7a1f | 10 | True | True |
| ladybug | 681e115aa8b9e11109a461411bff6b49723fa64db18e008cc9702f55212b7a1f | 10 | True | True |

### top_accepted_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 96e00eec2d752bb06045f6cfbc84612a66e0c6566627bcfd8819c3edda4c10ec | 10 | True | True |
| ladybug | 96e00eec2d752bb06045f6cfbc84612a66e0c6566627bcfd8819c3edda4c10ec | 10 | True | True |

### top_answerers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 50d8d042b3b244550202374f2e61b755ff9ff4823a408a112f228f08fe8e2c82 | 10 | True | True |
| ladybug | 50d8d042b3b244550202374f2e61b755ff9ff4823a408a112f228f08fe8e2c82 | 10 | True | True |

### top_askers

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 6516bfcfeaa4e0029675e82dbeeb825f63cdd023eb044f687a41f2e8650930a7 | 10 | True | True |
| ladybug | 6516bfcfeaa4e0029675e82dbeeb825f63cdd023eb044f687a41f2e8650930a7 | 10 | True | True |

### top_badges

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 443cba0d3bc973adc9a03a68b9d547c04c81e750731a4557de6f3b5a848d67c9 | 2 | True | True |
| ladybug | 443cba0d3bc973adc9a03a68b9d547c04c81e750731a4557de6f3b5a848d67c9 | 2 | True | True |

### top_questions_by_score

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 170740ccf8d95fcb62f63ff5632fcee8929a75bed7d8535c3eca671b40b398a1 | 10 | True | True |
| ladybug | 170740ccf8d95fcb62f63ff5632fcee8929a75bed7d8535c3eca671b40b398a1 | 10 | True | True |

### top_questions_by_total_comments

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | 3275e3c3a8197d94f524c7467b8316678d3410edd7cdd266a695be8e2b0216c4 | 10 | True | True |
| ladybug | 3275e3c3a8197d94f524c7467b8316678d3410edd7cdd266a695be8e2b0216c4 | 10 | True | True |

### top_tags_by_questions

| DB | Hashes | Row Counts | Hash Stable Within DB | Row Count Stable Within DB |
|---|---|---|---|---|
| arcadedb | ba3dc01cbf76f108a713c707dcadb5716ffebaae4ce4fdf93d36f8c473fb704a | 10 | True | True |
| ladybug | ba3dc01cbf76f108a713c707dcadb5716ffebaae4ce4fdf93d36f8c473fb704a | 10 | True | True |
