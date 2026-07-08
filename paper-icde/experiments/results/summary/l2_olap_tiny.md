# l2 / olap / tiny

| backend | n | build_s | top_degree_mean_ms | same_city_edges_mean_ms | friend_age_by_city_mean_ms | peak_mib_sum | manifests |
|---|---|---|---|---|---|---|---|
| arcadedb_graph_embedded | 5 | 3.19±0.04 | 15.9±2.9 | 67.5±6.5 | 80.2±2.3 | 2.02e+03±42 | 20260707T203801Z |
| arcadedb_graph_server | 5 | 8.49±0.09 | 17.9±1.4 | 60.7±2 | 64.8±3.5 | 3.64e+03±24 | 20260707T203801Z |
| ladybug_graph | 5 | 0.444±0.021 | 4.02±0.3 | 9.54±0.34 | 9.35±0.38 | 239±3.4 | 20260707T203801Z |
| neo4j_graph | 5 | 5.8±0.15 | 43.2±1.3 | 62.2±2.2 | 67.2±1.7 | 5.02e+03±17 | 20260707T203801Z |
