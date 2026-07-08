# l2 / olap / small

| backend | n | build_s | top_degree_mean_ms | same_city_edges_mean_ms | friend_age_by_city_mean_ms | peak_mib_sum | manifests |
|---|---|---|---|---|---|---|---|
| arcadedb_graph_embedded | 5 | 31.2±0.31 | 86.4±1.5 | 580±17 | 596±9.7 | 7.49e+03±40 | 20260707T204452Z |
| arcadedb_graph_server | 5 | 70.9±0.48 | 94.7±2.6 | 611±14 | 644±21 | 6.2e+03±60 | 20260707T204452Z |
| ladybug_graph | 5 | 2.6±0.058 | 17.3±0.27 | 69.6±0.35 | 66.8±0.44 | 509±15 | 20260707T204452Z |
| neo4j_graph | 5 | 49.2±0.61 | 510±9.7 | 823±18 | 858±6.9 | 9.56e+03±21 | 20260707T204452Z |
