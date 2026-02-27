# 09 Graph OLTP Matrix Summary

- Generated (UTC): 2026-02-27T12:38:11Z
- Dataset: stackoverflow-large
- Dataset size profile: large
- Label prefix: sweep09
- Total runs: 6

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
| run_label | sweep09_t01_r01_arcadedb_s00000, sweep09_t01_r01_ladybug_s00001, sweep09_t01_r02_arcadedb_s00002, sweep09_t01_r02_ladybug_s00003, sweep09_t01_r03_arcadedb_s00004, sweep09_t01_r03_ladybug_s00005 |
| seed | 0, 1, 2, 3, 4, 5 |
| threads | 1 |
| transactions | 25000, 250000 |

## Aggregated Metrics by DB + Threads

### DB: arcadedb, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 497.114 |  | 36.3913 | 468.167 | 548.439 |
| disk_after_load_bytes | 3 | 4631242319 | 4.3GiB | 2.93151e+07 | 4595795414 | 4667585662 |
| disk_after_oltp_bytes | 3 | 4.60415e+09 | 4.3GiB | 6.1221e+07 | 4552665534 | 4690176709 |
| disk_usage.du_bytes | 3 | 4.55277e+09 | 4.2GiB | 80288.1 | 4552663040 | 4552855552 |
| edge_count | 3 | 8.39289e+06 |  | 53819.9 | 8346858 | 8468404 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 548426 |  | 103.605 | 548285 | 548531 |
| edge_counts_by_type.ANSWERED | 3 | 1850140 |  | 1611.47 | 1848604 | 1852366 |
| edge_counts_by_type.ASKED | 3 | 701995 |  | 245.136 | 701820 | 702342 |
| edge_counts_by_type.COMMENTED_ON | 3 | 658716 |  | 55.7275 | 658638 | 658763 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2.06241e+06 |  | 38.7327 | 2062354 | 2062444 |
| edge_counts_by_type.EARNED | 3 | 399023 |  | 82.8224 | 398906 | 399090 |
| edge_counts_by_type.HAS_ANSWER | 3 | 1950971 |  | 301.882 | 1950609 | 1951348 |
| edge_counts_by_type.LINKED_TO | 3 | 7487.67 |  | 52.8226 | 7413 | 7527 |
| edge_counts_by_type.TAGGED_WITH | 3 | 213728 |  | 53805.2 | 169970 | 289518 |
| latency_summary.ops.delete.50 | 3 | 0.00307097 |  | 0.000536121 | 0.00257213 | 0.00381486 |
| latency_summary.ops.delete.95 | 3 | 0.0890653 |  | 0.0134158 | 0.0727356 | 0.105596 |
| latency_summary.ops.delete.99 | 3 | 0.336117 |  | 0.0294933 | 0.314458 | 0.377816 |
| latency_summary.ops.insert.50 | 3 | 0.00119075 |  | 0.000113817 | 0.0010982 | 0.00135107 |
| latency_summary.ops.insert.95 | 3 | 0.0266273 |  | 0.00395953 | 0.0231711 | 0.0321709 |
| latency_summary.ops.insert.99 | 3 | 0.0384645 |  | 0.00964444 | 0.0310128 | 0.0520837 |
| latency_summary.ops.read.50 | 3 | 0.000727102 |  | 6.4839e-05 | 0.000652452 | 0.000810543 |
| latency_summary.ops.read.95 | 3 | 0.00311681 |  | 0.000667516 | 0.00254303 | 0.00405289 |
| latency_summary.ops.read.99 | 3 | 0.0099991 |  | 0.00182085 | 0.00826628 | 0.0125151 |
| latency_summary.ops.update.50 | 3 | 0.000460978 |  | 3.99199e-05 | 0.000425271 | 0.000516702 |
| latency_summary.ops.update.95 | 3 | 0.00449114 |  | 0.000578408 | 0.00376441 | 0.00517967 |
| latency_summary.ops.update.99 | 3 | 0.00878665 |  | 0.00120058 | 0.00734113 | 0.0102807 |
| latency_summary.overall.50 | 3 | 0.000772233 |  | 7.31186e-05 | 0.000700453 | 0.000872584 |
| latency_summary.overall.95 | 3 | 0.0161531 |  | 0.00158524 | 0.0143902 | 0.018234 |
| latency_summary.overall.99 | 3 | 0.0556196 |  | 0.00810806 | 0.0447042 | 0.064119 |
| load_counts_time_s | 3 | 494.131 |  | 20.8267 | 464.678 | 508.868 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 483.792 |  | 73.2467 | 427.574 | 587.249 |
| load_stats.edges.ANSWERED | 3 | 1793.62 |  | 123.651 | 1619.37 | 1893.39 |
| load_stats.edges.ASKED | 3 | 895.942 |  | 225.25 | 694.052 | 1210.28 |
| load_stats.edges.COMMENTED_ON | 3 | 2179.24 |  | 426.819 | 1610.18 | 2638.1 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 2179.24 |  | 426.819 | 1610.18 | 2638.1 |
| load_stats.edges.EARNED | 3 | 802.34 |  | 71.1253 | 707.404 | 878.593 |
| load_stats.edges.HAS_ANSWER | 3 | 1647.58 |  | 313.111 | 1385.64 | 2087.74 |
| load_stats.edges.LINKED_TO | 3 | 10.5703 |  | 1.38606 | 9.30631 | 12.4998 |
| load_stats.edges.TAGGED_WITH | 3 | 1267.48 |  | 225.426 | 1093.55 | 1585.83 |
| load_stats.nodes.Badge | 3 | 1136.51 |  | 39.4479 | 1082.1 | 1174.36 |
| load_stats.nodes.Comment | 3 | 2349.76 |  | 417.904 | 2010.29 | 2938.46 |
| load_stats.nodes.Post | 3 | 2968.55 |  | 126.284 | 2816.62 | 3125.81 |
| load_stats.nodes.Tag | 3 | 4.39357 |  | 0.18942 | 4.21877 | 4.65676 |
| load_stats.nodes.User | 3 | 667.67 |  | 102.451 | 575.3 | 810.525 |
| load_time_s | 3 | 16207.6 |  | 785.735 | 15371 | 17259.2 |
| node_count | 3 | 7.7907e+06 |  | 92.7518 | 7790575 | 7790791 |
| node_counts_by_type.Answer | 3 | 1962560 |  | 61.8223 | 1962473 | 1962611 |
| node_counts_by_type.Badge | 3 | 1658998 |  | 75.0244 | 1658892 | 1659055 |
| node_counts_by_type.Comment | 3 | 2.72577e+06 |  | 13.4743 | 2725757 | 2725790 |
| node_counts_by_type.Question | 3 | 779597 |  | 14.7271 | 779578 | 779614 |
| node_counts_by_type.Tag | 3 | 258.333 |  | 37.677 | 225 | 311 |
| node_counts_by_type.User | 3 | 663517 |  | 59.2115 | 663440 | 663584 |
| op_counts.delete | 3 | 25042.7 |  | 184.321 | 24782 | 25174 |
| op_counts.insert | 3 | 24962.7 |  | 129.703 | 24785 | 25091 |
| op_counts.read | 3 | 150065 |  | 94.5457 | 149937 | 150162 |
| op_counts.update | 3 | 49929.3 |  | 293.836 | 49652 | 50336 |
| rss_peak_kb | 3 | 7853384 | 7.5GiB | 106336 | 7705868 | 7952444 |
| schema_time_s | 3 | 0.203315 |  | 0.0136766 | 0.189772 | 0.222045 |
| seed | 3 | 2 |  | 1.63299 | 0 | 4 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 226.715 |  | 24.1415 | 197.401 | 256.529 |
| total_time_s | 3 | 1115.38 |  | 119.391 | 974.548 | 1266.46 |
| transactions | 3 | 250000 |  | 0 | 250000 | 250000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|

### DB: ladybug, Threads: 1 (runs=3)

#### Numeric Metrics

| Metric | Count | Mean | Mean (Human) | Stddev | Min | Max |
|---|---:|---:|---|---:|---:|---:|
| batch_size | 3 | 10000 |  | 0 | 10000 | 10000 |
| counts_time_s | 3 | 1.93064 |  | 0.271414 | 1.60108 | 2.26583 |
| disk_after_load_bytes | 3 | 6.11222e+09 | 5.7GiB | 58534.4 | 6112151180 | 6112294540 |
| disk_after_oltp_bytes | 3 | 6113937530 | 5.7GiB | 75303.5 | 6113844583 | 6114029021 |
| disk_usage.du_bytes | 3 | 6.2783e+09 | 5.8GiB | 1.25023e+06 | 6276685824 | 6279733248 |
| edge_count | 3 | 9586992 |  | 52966.2 | 9522053 | 9651793 |
| edge_counts_by_type.ACCEPTED_ANSWER | 3 | 547926 |  | 6.12826 | 547922 | 547935 |
| edge_counts_by_type.ANSWERED | 3 | 1.85696e+06 |  | 148.693 | 1856784 | 1857148 |
| edge_counts_by_type.ASKED | 3 | 703899 |  | 37.9561 | 703859 | 703950 |
| edge_counts_by_type.COMMENTED_ON | 3 | 658664 |  | 23.7206 | 658634 | 658692 |
| edge_counts_by_type.COMMENTED_ON_ANSWER | 3 | 2.06503e+06 |  | 20.155 | 2065009 | 2065057 |
| edge_counts_by_type.EARNED | 3 | 398122 |  | 44.4997 | 398083 | 398184 |
| edge_counts_by_type.HAS_ANSWER | 3 | 1.95724e+06 |  | 23.9768 | 1957213 | 1957271 |
| edge_counts_by_type.LINKED_TO | 3 | 4320.67 |  | 31.7525 | 4279 | 4356 |
| edge_counts_by_type.TAGGED_WITH | 3 | 1394829 |  | 52842.5 | 1330149 | 1459586 |
| latency_summary.ops.delete.50 | 3 | 0.0285599 |  | 0.00126 | 0.0273333 | 0.0302926 |
| latency_summary.ops.delete.95 | 3 | 0.0965411 |  | 0.0130658 | 0.0784539 | 0.108858 |
| latency_summary.ops.delete.99 | 3 | 0.16579 |  | 0.0400314 | 0.110312 | 0.203297 |
| latency_summary.ops.insert.50 | 3 | 0.0221745 |  | 0.0030972 | 0.0195467 | 0.0265232 |
| latency_summary.ops.insert.95 | 3 | 0.0545992 |  | 0.0120661 | 0.0378738 | 0.0658919 |
| latency_summary.ops.insert.99 | 3 | 0.0875242 |  | 0.00553553 | 0.0798734 | 0.0927857 |
| latency_summary.ops.read.50 | 3 | 0.00638947 |  | 0.00163623 | 0.00408935 | 0.00775857 |
| latency_summary.ops.read.95 | 3 | 0.0796355 |  | 0.0037796 | 0.0743581 | 0.083009 |
| latency_summary.ops.read.99 | 3 | 0.0922692 |  | 0.000464938 | 0.0916947 | 0.0928334 |
| latency_summary.ops.update.50 | 3 | 0.0216709 |  | 0.00332831 | 0.0192325 | 0.0263768 |
| latency_summary.ops.update.95 | 3 | 0.0572329 |  | 0.012393 | 0.0397866 | 0.067406 |
| latency_summary.ops.update.99 | 3 | 0.0899562 |  | 0.00357186 | 0.0852029 | 0.0938133 |
| latency_summary.overall.50 | 3 | 0.0174525 |  | 0.000875045 | 0.0163856 | 0.018529 |
| latency_summary.overall.95 | 3 | 0.0778828 |  | 0.00648107 | 0.0687696 | 0.0832868 |
| latency_summary.overall.99 | 3 | 0.095393 |  | 0.00246154 | 0.0920376 | 0.0978736 |
| load_counts_time_s | 3 | 1.49184 |  | 0.110721 | 1.39286 | 1.6464 |
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
| load_stats.edges.ACCEPTED_ANSWER | 3 | 1.22822 |  | 0.219623 | 0.998825 | 1.52426 |
| load_stats.edges.ANSWERED | 3 | 4.05181 |  | 0.636817 | 3.23685 | 4.79122 |
| load_stats.edges.ASKED | 3 | 1.41544 |  | 0.120591 | 1.2933 | 1.57959 |
| load_stats.edges.COMMENTED_ON | 3 | 1.92838 |  | 0.421419 | 1.43478 | 2.46443 |
| load_stats.edges.COMMENTED_ON_ANSWER | 3 | 6.2879 |  | 1.43532 | 4.45843 | 7.96421 |
| load_stats.edges.EARNED | 3 | 1.88413 |  | 0.320766 | 1.56637 | 2.32338 |
| load_stats.edges.HAS_ANSWER | 3 | 3.79319 |  | 0.997576 | 2.8224 | 5.1651 |
| load_stats.edges.LINKED_TO | 3 | 0.173164 |  | 0.0799043 | 0.0674546 | 0.260604 |
| load_stats.edges.TAGGED_WITH | 3 | 1.73639 |  | 0.329887 | 1.3586 | 2.16234 |
| load_stats.nodes.Answer | 3 | 45.9617 |  | 7.5672 | 39.2614 | 56.5385 |
| load_stats.nodes.Badge | 3 | 1.67173 |  | 0.275884 | 1.29093 | 1.93568 |
| load_stats.nodes.Comment | 3 | 25.4083 |  | 4.18689 | 21.5427 | 31.2254 |
| load_stats.nodes.Post | 3 | 76.0977 |  | 9.40745 | 67.4339 | 89.1734 |
| load_stats.nodes.Question | 3 | 30.136 |  | 1.86072 | 28.1725 | 32.635 |
| load_stats.nodes.Tag | 3 | 0.37739 |  | 0.0611906 | 0.291729 | 0.430854 |
| load_stats.nodes.User | 3 | 1.84467 |  | 0.218633 | 1.66231 | 2.15209 |
| load_time_s | 3 | 536.487 |  | 30.436 | 493.505 | 559.955 |
| node_count | 3 | 7783578 |  | 60.4649 | 7783496 | 7783640 |
| node_counts_by_type.Answer | 3 | 1.96081e+06 |  | 41.5559 | 1960749 | 1960840 |
| node_counts_by_type.Badge | 3 | 1657364 |  | 26.1661 | 1657345 | 1657401 |
| node_counts_by_type.Comment | 3 | 2724034 |  | 6.68331 | 2724025 | 2724041 |
| node_counts_by_type.Question | 3 | 777853 |  | 17.7451 | 777830 | 777873 |
| node_counts_by_type.Tag | 3 | 1748 |  | 8.04156 | 1740 | 1759 |
| node_counts_by_type.User | 3 | 661771 |  | 14.8997 | 661750 | 661783 |
| op_counts.delete | 3 | 2518.33 |  | 54.908 | 2448 | 2582 |
| op_counts.insert | 3 | 2512.67 |  | 63.3526 | 2433 | 2588 |
| op_counts.read | 3 | 14994.3 |  | 46.942 | 14933 | 15047 |
| op_counts.update | 3 | 4974.67 |  | 58.3686 | 4911 | 5052 |
| rss_peak_kb | 3 | 4.57486e+06 | 4.4GiB | 44548.6 | 4512848 | 4615492 |
| schema_time_s | 3 | 0.203226 |  | 0.0129887 | 0.192136 | 0.221452 |
| seed | 3 | 3 |  | 1.63299 | 1 | 5 |
| threads | 3 | 1 |  | 0 | 1 | 1 |
| throughput_ops_s | 3 | 42.8416 |  | 2.88015 | 40.3005 | 46.869 |
| total_time_s | 3 | 586.086 |  | 37.8092 | 533.402 | 620.34 |
| transactions | 3 | 25000 |  | 0 | 25000 | 25000 |

#### Boolean Metrics

| Metric | Count | True | False | True Ratio |
|---|---:|---:|---:|---:|
