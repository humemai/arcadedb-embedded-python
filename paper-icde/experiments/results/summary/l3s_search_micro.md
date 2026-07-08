# l3s / search / micro

| backend | n | build_s | query_p50_ms | query_p95_ms | query_p99_ms | qps | recall_at_10 | peak_mib_sum | manifests |
|---|---|---|---|---|---|---|---|---|---|
| arcadedb_sparse_embedded | 1 | 0.48 | 1.27 | 1.7 | 1.87 | 790 | 1 | 275 | 20260707T100032Z |
| arcadedb_sparse_server | 1 | 0.82 | 3.11 | 4.42 | 4.61 | 304 | 1 | 757 | 20260707T100032Z |
| elasticsearch_sparse | 1 | 1.38 | 3.04 | 3.75 | 3.99 | 330 | 0.992 | 2.64e+03 | 20260707T100032Z |
| milvus_sparse | 1 | 1.72 | 0.993 | 1.92 | 2.05 | 879 | 1 | 224 | 20260707T100032Z |
| qdrant_sparse | 1 | 0.17 | 0.642 | 0.783 | 0.901 | 1.52e+03 | 1 | 170 | 20260707T100032Z |
