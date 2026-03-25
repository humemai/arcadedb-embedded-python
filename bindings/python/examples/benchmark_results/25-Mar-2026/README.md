These benchmark reruns reflect the recent Python vector updates after the March 2026
vector-index rewrite. Now ArcadeDB's vector has ef_serach, just like a normal HNSW-based
vector search.

## 11_vector_index_build

### Dataset: stackoverflow-medium

| backend      | mem_limit | threads | batch_size | count     | rows      | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib    |
| ------------ | --------- | ------- | ---------- | --------- | --------- | ----------- | ----------- | -------------- | -------- | ---------- | ------------ | ----------- | --------- |
| arcadedb_sql | 8g        | 8       | 10,000     | 1,242,391 | 1,242,391 | 408.651     | 0.43        | 366.85         | 39.816   | 1.514      | 6,924.27     | 2,780.691   | 2,780.734 |

### Dataset: stackoverflow-large

| backend      | mem_limit | threads | batch_size | count     | rows      | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib | du_mib     |
| ------------ | --------- | ------- | ---------- | --------- | --------- | ----------- | ----------- | -------------- | -------- | ---------- | ------------ | ----------- | ---------- |
| arcadedb_sql | 32g       | 8       | 10,000     | 5,461,227 | 5,461,227 | 1,888.01    | 0.408       | 1,733.282      | 154.189  | 0.094      | 26,966.902   | 12,229.754  | 12,229.594 |

## 12_vector_search

### Dataset: stackoverflow-medium

| backend      | mem_limit | k   | query_order | ef_search | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib    |
| ------------ | --------- | --- | ----------- | --------- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ | --------- |
| arcadedb_sql | 4g        | 50  | shuffled    | 100       | 1,000   | 0.91        | 225.69          | 277.485        | 228.453     | 2.317     | 225.812  | 0.011      | 3,542.203    | 2,780.754 |

### Dataset: stackoverflow-large

| backend      | mem_limit | k   | query_order | ef_search | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib | du_mib     |
| ------------ | --------- | --- | ----------- | --------- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ | ---------- |
| arcadedb_sql | 16g       | 50  | shuffled    | 100       | 1,000   | 0.913       | 248.323         | 285.659        | 256.732     | 7.981     | 248.425  | 0.021      | 13,561.09    | 12,229.613 |

## Notes

- HNSW indexing takes far less time than it used to be. stackoverflow-medium builds in
  under 7 minutes and stackoverflow-large builds in under 30 minutes on the current
  hardware with the current JVector implementation and defaults. This is a significant
  improvement over previous runs, which took multiple hours for the large dataset.
- But the memory usage is higher than before. As for the medium and large datasets, I
  had to allocate 8g and 32g, respectively, to the docker containers to avoid OOMs
  during indexing. The other vector dbs tested can carry out indexing with less than 4g
  and 16g, respectively.
- Fortunately, HNSW search needs less memory (half of the indexing memory), so the
  search runs with 4g and 16g, respectively, without OOMs. The average latency is about
  225ms for the medium dataset and 250ms for the large dataset, with recall around 91%
  for both. This latency is pretty high compared to the other vector dbs tested, which
  can be as fast as 10ms (see the previous benchmark summary for reference).
