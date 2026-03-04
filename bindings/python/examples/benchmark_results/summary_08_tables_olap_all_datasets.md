# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T21:00:03Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 4
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:3f359ca6b9a9b4fde4cfda499cd6951e802a6aae6e930134f1aaf3f664184696
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - duckdb: 1.4.4
  - duckdb_runtime_version: 1.4.4
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Run status files: total=4, success=4, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | runs | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb | sweep08_t01_r01_arcadedb_s00000 | 0 | 1 | 1 | 10 | shuffled | bulk_tuned_insert | 245.761 | 104.519 | 150.957 | 6,648.969 | 2,701.48 |
| duckdb | sweep08_t01_r01_duckdb_s00002 | 2 | 1 | 1 | 10 | shuffled | copy_csv | 130.771 | 3.746 | 0.413 | 1,882.516 | 5,304.34 |
| postgresql | sweep08_t01_r01_postgresql_s00003 | 3 | 1 | 1 | 10 | shuffled | copy_from_stdin | 150.317 | 16.203 | 17.875 | 1,879.84 | 5,503.367 |
| sqlite | sweep08_t01_r01_sqlite_s00001 | 1 | 1 | 1 | 10 | shuffled | executemany | 75.36 | 8.79 | 6.032 | 572.742 | 2,773.957 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb | 1 | most_commented_posts | 10 | 1,678.007 | 2,174.45 | 10 | True |
| arcadedb | 1 | post_type_counts | 10 | 1,462.4 | 1,926.29 | 7 | True |
| arcadedb | 1 | posthistory_by_type | 10 | 5,493.817 | 5,754.663 | 30 | True |
| arcadedb | 1 | postlinks_by_type | 10 | 260.273 | 693.12 | 2 | True |
| arcadedb | 1 | top_answers_by_score | 10 | 879.801 | 1,287.702 | 10 | True |
| arcadedb | 1 | top_badges | 10 | 698.271 | 875.525 | 10 | True |
| arcadedb | 1 | top_questions_by_score | 10 | 733.594 | 980.951 | 10 | True |
| arcadedb | 1 | top_tags_by_count | 10 | 4.446 | 7.92 | 10 | True |
| arcadedb | 1 | top_users_by_reputation | 10 | 640.915 | 921.815 | 10 | True |
| arcadedb | 1 | votes_by_type | 10 | 3,243.072 | 3,637.237 | 14 | True |
| duckdb | 1 | most_commented_posts | 10 | 17.915 | 20.627 | 10 | True |
| duckdb | 1 | post_type_counts | 10 | 1.853 | 2.235 | 7 | True |
| duckdb | 1 | posthistory_by_type | 10 | 4.29 | 4.709 | 30 | True |
| duckdb | 1 | postlinks_by_type | 10 | 0.875 | 1.208 | 2 | True |
| duckdb | 1 | top_answers_by_score | 10 | 2.017 | 2.214 | 10 | True |
| duckdb | 1 | top_badges | 10 | 2.066 | 2.468 | 10 | True |
| duckdb | 1 | top_questions_by_score | 10 | 2.417 | 2.979 | 10 | True |
| duckdb | 1 | top_tags_by_count | 10 | 0.479 | 0.765 | 10 | True |
| duckdb | 1 | top_users_by_reputation | 10 | 2.699 | 3.426 | 10 | True |
| duckdb | 1 | votes_by_type | 10 | 5.886 | 6.319 | 14 | True |
| postgresql | 1 | most_commented_posts | 10 | 625.28 | 724.365 | 10 | True |
| postgresql | 1 | post_type_counts | 10 | 90.467 | 144.858 | 7 | True |
| postgresql | 1 | posthistory_by_type | 10 | 625.945 | 740.871 | 30 | True |
| postgresql | 1 | postlinks_by_type | 10 | 26.401 | 77.3 | 2 | True |
| postgresql | 1 | top_answers_by_score | 10 | 0.568 | 1.238 | 10 | True |
| postgresql | 1 | top_badges | 10 | 122.252 | 183.145 | 10 | True |
| postgresql | 1 | top_questions_by_score | 10 | 0.426 | 0.651 | 10 | True |
| postgresql | 1 | top_tags_by_count | 10 | 0.478 | 0.695 | 10 | True |
| postgresql | 1 | top_users_by_reputation | 10 | 0.755 | 2.633 | 10 | True |
| postgresql | 1 | votes_by_type | 10 | 294.217 | 344.322 | 14 | True |
| sqlite | 1 | most_commented_posts | 10 | 52.009 | 75.675 | 10 | True |
| sqlite | 1 | post_type_counts | 10 | 14.251 | 20.775 | 7 | True |
| sqlite | 1 | posthistory_by_type | 10 | 50.859 | 73.191 | 30 | True |
| sqlite | 1 | postlinks_by_type | 10 | 3.093 | 4.616 | 2 | True |
| sqlite | 1 | top_answers_by_score | 10 | 193.534 | 245.165 | 10 | True |
| sqlite | 1 | top_badges | 10 | 25.851 | 40.135 | 10 | True |
| sqlite | 1 | top_questions_by_score | 10 | 202.077 | 247.422 | 10 | True |
| sqlite | 1 | top_tags_by_count | 10 | 0.168 | 0.271 | 10 | True |
| sqlite | 1 | top_users_by_reputation | 10 | 0.081 | 0.134 | 10 | True |
| sqlite | 1 | votes_by_type | 10 | 60.43 | 91.873 | 14 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | all_hashes |
|---|---|---|---|
| most_commented_posts | arcadedb, duckdb, postgresql, sqlite | True | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 |
| post_type_counts | arcadedb, duckdb, postgresql, sqlite | True | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b |
| posthistory_by_type | arcadedb, duckdb, postgresql, sqlite | True | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b |
| postlinks_by_type | arcadedb, duckdb, postgresql, sqlite | True | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 |
| top_answers_by_score | arcadedb, duckdb, postgresql, sqlite | True | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 |
| top_badges | arcadedb, duckdb, postgresql, sqlite | True | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 |
| top_questions_by_score | arcadedb, duckdb, postgresql, sqlite | True | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce |
| top_tags_by_count | arcadedb, duckdb, postgresql, sqlite | True | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf |
| top_users_by_reputation | arcadedb, duckdb, postgresql, sqlite | True | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 |
| votes_by_type | arcadedb, duckdb, postgresql, sqlite | True | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c |
