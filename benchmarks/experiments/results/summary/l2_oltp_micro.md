# l2 / oltp / micro

| backend | n | build_s | point_p50_ms | hop1_p50_ms | hop2_p50_ms | write_p50_ms | peak_mib_sum | manifests |
|---|---|---|---|---|---|---|---|---|
| arcadedb_graph_embedded | 1 | 0.63 | 0.661 | 1.03 | 2.14 | 2.83 | 481 | 20260707T203650Z |
| arcadedb_graph_server | 1 | 2.41 | 1.58 | 1.92 | 3.09 | 4.05 | 1.18e+03 | 20260707T203650Z |
| ladybug_graph | 1 | 0.12 | 0.135 | 0.748 | 2.56 | 5.86 | 171 | 20260710T081923Z |
| neo4j_graph | 1 | 2.17 | 8.33 | 7.98 | 6.42 | 14.5 | 5.17e+03 | 20260707T203650Z |
