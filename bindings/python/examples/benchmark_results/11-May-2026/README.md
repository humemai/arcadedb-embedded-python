# 11-May-2026 Benchmark Results

These summaries now report ArcadeDB build modes correctly across both build and search runs:

- `quantization` / `encoding` in the Example 11 build results are tracked correctly.
- `build_quantization` / `build_encoding` in the Example 12 search results now resolve correctly for reused Example 11 databases.
- Disk usage is saved for both build and search runs and carried into the generated summaries from the per-run `disk_usage_du*.json` artifacts.

## 11 Vector Index Build Matrix Summary

### Dataset: stackoverflow-medium

| backend      | quantization | encoding | mem_limit | threads | batch_size | count     | rows      | run_total_s | create_db_s | create_index_s | ingest_s | close_db_s | peak_rss_mib | db_size_mib |
| ------------ | ------------ | -------- | --------- | ------- | ---------- | --------- | --------- | ----------- | ----------- | -------------- | -------- | ---------- | ------------ | ----------- |
| arcadedb_sql | INT8         | NONE     | 8g        | 4       | 5,000      | 1,242,391 | 1,242,391 | 778.707     | 0.339       | 739.641        | 38.6     | 0.055      | 6,863.488    | 3,250.941   |
| arcadedb_sql | NONE         | INT8     | 8g        | 4       | 5,000      | 1,242,391 | 1,242,391 | 795.565     | 0.325       | 719.702        | 75.463   | 0.01       | 6,872.727    | 683.505     |
| arcadedb_sql | NONE         | NONE     | 8g        | 4       | 5,000      | 1,242,391 | 1,242,391 | 802.589     | 0.301       | 757.279        | 44.876   | 0.071      | 6,832.219    | 2,781.441   |

## 12 Vector Search Matrix Summary

### Dataset: stackoverflow-medium

| backend      | build_quantization | build_encoding | mem_limit | k   | query_runs | query_order | ef_search | queries | recall_mean | latency_ms_mean | latency_ms_p95 | run_total_s | open_db_s | search_s | close_db_s | peak_rss_mib |
| ------------ | ------------------ | -------------- | --------- | --- | ---------- | ----------- | --------- | ------- | ----------- | --------------- | -------------- | ----------- | --------- | -------- | ---------- | ------------ |
| arcadedb_sql | INT8               | NONE           | 4g        | 50  | 1          | shuffled    | 100       | 1,000   | 0.909       | 87.121          | 100.064        | 89.998      | 2.479     | 87.176   | 0.012      | 3,131.676    |
| arcadedb_sql | NONE               | INT8           | 4g        | 50  | 1          | shuffled    | 100       | 1,000   | 0.903       | 78.346          | 85.818         | 79.486      | 0.972     | 78.39    | 0.011      | 2,190.344    |
| arcadedb_sql | NONE               | NONE           | 4g        | 50  | 1          | shuffled    | 100       | 1,000   | 0.913       | 226.04          | 268.102        | 228.753     | 2.269     | 226.094  | 0.012      | 3,292.16     |
