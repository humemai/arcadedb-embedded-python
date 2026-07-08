# l2 / olap / medium

| backend | n | build_s | top_degree_mean_ms | same_city_edges_mean_ms | friend_age_by_city_mean_ms | peak_mib_sum | manifests |
|---|---|---|---|---|---|---|---|
| arcadedb_graph_embedded | 5 | 601±4.2 | 1.01e+03±32 | 1.07e+04±3.2e+02 | 1.12e+04±2.8e+02 | 1.73e+04±2.5e+02 | 20260707T211743Z |
| arcadedb_graph_server | 5 | 1.1e+03±7.7 | 1.09e+03±13 | 1.12e+04±2.4e+02 | 1.17e+04±3.6e+02 | 1.66e+04±1.3e+02 | 20260707T211743Z |
| ladybug_graph | 5 | 20.8±0.28 | 57.8±0.87 | 282±1.6 | 272±1.3 | 3.2e+03±52 | 20260707T211743Z |
| neo4j_graph | 5 | 503±3 | 1.39e+04±3.1e+02 | 2.21e+04±5e+02 | 2.24e+04±2.2e+02 | 2e+04±67 | 20260707T211743Z |
