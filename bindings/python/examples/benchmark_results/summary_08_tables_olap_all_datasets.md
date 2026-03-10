# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T20:52:42Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 12
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c1db044c71db11c553065dc9fcccfceae444df12210bf352b12bfc18bae68790
  - arcadedb_docker_tag: 26.3.1
  - arcadedb_embedded: auto
  - duckdb: auto
  - duckdb_runtime_version: 1.4.4
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1
- Run status files: total=12, success=12, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | runs | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_m8g | 0 | 1 | 1 | 10 | shuffled | bulk_tuned_insert | 721.757 | 1,397.427 | 1,778.791 | 6,792.742 | 8,908.938 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_m8g | 0 | 1 | 4 | 10 | shuffled | bulk_tuned_insert | 682.592 | 1,403.51 | 1,322.387 | 5,961.371 | 8,908.941 |
| arcadedb_sql | sweep08_t08_r01_arcadedb_sql_s00000_m8g | 0 | 1 | 8 | 10 | shuffled | bulk_tuned_insert | 680.008 | 1,411.462 | 1,324.07 | 5,939.211 | 8,908.938 |
| duckdb | sweep08_t01_r01_duckdb_s00002_m8g | 2 | 1 | 1 | 10 | shuffled | copy_csv | 484.272 | 11.319 | 1.334 | 6,557.051 | 18,354.637 |
| duckdb | sweep08_t04_r01_duckdb_s00002_m8g | 2 | 1 | 4 | 10 | shuffled | copy_csv | 456.705 | 10.336 | 0.498 | 6,492.137 | 18,348.895 |
| duckdb | sweep08_t08_r01_duckdb_s00002_m8g | 2 | 1 | 8 | 10 | shuffled | copy_csv | 438.186 | 9.235 | 0.309 | 6,984.016 | 18,350.641 |
| postgresql | sweep08_t01_r01_postgresql_s00003_m8g | 3 | 1 | 1 | 10 | shuffled | copy_from_stdin | 769.943 | 52.57 | 46.508 | 3,495.68 | 16,129.785 |
| postgresql | sweep08_t04_r01_postgresql_s00003_m8g | 3 | 1 | 4 | 10 | shuffled | copy_from_stdin | 672.932 | 43.453 | 34.748 | 3,491.449 | 16,129.844 |
| postgresql | sweep08_t08_r01_postgresql_s00003_m8g | 3 | 1 | 8 | 10 | shuffled | copy_from_stdin | 655.053 | 41.755 | 33.196 | 3,509.691 | 16,129.832 |
| sqlite | sweep08_t01_r01_sqlite_s00001_m8g | 1 | 1 | 1 | 10 | shuffled | executemany | 216.601 | 39.863 | 25.365 | 847.82 | 8,921.906 |
| sqlite | sweep08_t04_r01_sqlite_s00001_m8g | 1 | 1 | 4 | 10 | shuffled | executemany | 212.829 | 36.267 | 23.857 | 848.617 | 8,921.91 |
| sqlite | sweep08_t08_r01_sqlite_s00001_m8g | 1 | 1 | 8 | 10 | shuffled | executemany | 219.932 | 50.293 | 25.463 | 842.527 | 8,921.91 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 10 | 5,005.519 | 5,751.272 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 10 | 24,258.148 | 27,890.655 | 2 | True |
| arcadedb_sql | 1 | posthistory_by_type | 10 | 114,244.944 | 127,357.425 | 21 | True |
| arcadedb_sql | 1 | postlinks_by_type | 10 | 402.723 | 1,033.326 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 10 | 12,827.229 | 14,757.86 | 10 | True |
| arcadedb_sql | 1 | top_badges | 10 | 1,292.904 | 1,584.998 | 2 | True |
| arcadedb_sql | 1 | top_questions_by_score | 10 | 9,802.328 | 10,666.872 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 10 | 2.609 | 3.07 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 10 | 918.284 | 1,410.788 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 10 | 9,123.633 | 9,423.513 | 18 | True |
| arcadedb_sql | 4 | most_commented_posts | 10 | 3,328.806 | 3,544.173 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 10 | 7,693.372 | 11,588.254 | 2 | True |
| arcadedb_sql | 4 | posthistory_by_type | 10 | 101,757.833 | 111,411.931 | 21 | True |
| arcadedb_sql | 4 | postlinks_by_type | 10 | 274.188 | 409.307 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 10 | 6,743.97 | 11,740.934 | 10 | True |
| arcadedb_sql | 4 | top_badges | 10 | 1,027.764 | 1,242.186 | 2 | True |
| arcadedb_sql | 4 | top_questions_by_score | 10 | 2,482.911 | 3,488.93 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 10 | 3.31 | 6.397 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 10 | 752.916 | 934.998 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 10 | 8,171.765 | 8,981.778 | 18 | True |
| arcadedb_sql | 8 | most_commented_posts | 10 | 3,149.123 | 3,462.858 | 10 | True |
| arcadedb_sql | 8 | post_type_counts | 10 | 8,304.509 | 15,005.032 | 2 | True |
| arcadedb_sql | 8 | posthistory_by_type | 10 | 99,969.771 | 106,627.575 | 21 | True |
| arcadedb_sql | 8 | postlinks_by_type | 10 | 292.222 | 467.386 | 2 | True |
| arcadedb_sql | 8 | top_answers_by_score | 10 | 6,614.371 | 10,102.869 | 10 | True |
| arcadedb_sql | 8 | top_badges | 10 | 1,066.963 | 1,162.197 | 2 | True |
| arcadedb_sql | 8 | top_questions_by_score | 10 | 3,775.568 | 7,847.838 | 10 | True |
| arcadedb_sql | 8 | top_tags_by_count | 10 | 3.088 | 4.83 | 10 | True |
| arcadedb_sql | 8 | top_users_by_reputation | 10 | 779.867 | 980.365 | 10 | True |
| arcadedb_sql | 8 | votes_by_type | 10 | 8,450.586 | 9,005.172 | 18 | True |
| duckdb | 1 | most_commented_posts | 10 | 68.571 | 102.365 | 10 | True |
| duckdb | 1 | post_type_counts | 10 | 7.048 | 7.402 | 2 | True |
| duckdb | 1 | posthistory_by_type | 10 | 15.51 | 16.68 | 21 | True |
| duckdb | 1 | postlinks_by_type | 10 | 1.088 | 1.454 | 2 | True |
| duckdb | 1 | top_answers_by_score | 10 | 5.641 | 7.733 | 10 | True |
| duckdb | 1 | top_badges | 10 | 3.571 | 4.369 | 2 | True |
| duckdb | 1 | top_questions_by_score | 10 | 7.365 | 16.907 | 10 | True |
| duckdb | 1 | top_tags_by_count | 10 | 0.423 | 0.657 | 10 | True |
| duckdb | 1 | top_users_by_reputation | 10 | 2.655 | 3.842 | 10 | True |
| duckdb | 1 | votes_by_type | 10 | 20.895 | 26.21 | 18 | True |
| duckdb | 4 | most_commented_posts | 10 | 24.007 | 26.895 | 10 | True |
| duckdb | 4 | post_type_counts | 10 | 2.354 | 2.677 | 2 | True |
| duckdb | 4 | posthistory_by_type | 10 | 4.469 | 4.712 | 21 | True |
| duckdb | 4 | postlinks_by_type | 10 | 1.234 | 2.879 | 2 | True |
| duckdb | 4 | top_answers_by_score | 10 | 3.179 | 4.426 | 10 | True |
| duckdb | 4 | top_badges | 10 | 1.609 | 1.859 | 2 | True |
| duckdb | 4 | top_questions_by_score | 10 | 2.787 | 4.229 | 10 | True |
| duckdb | 4 | top_tags_by_count | 10 | 0.498 | 0.763 | 10 | True |
| duckdb | 4 | top_users_by_reputation | 10 | 2.306 | 2.892 | 10 | True |
| duckdb | 4 | votes_by_type | 10 | 6.623 | 11.942 | 18 | True |
| duckdb | 8 | most_commented_posts | 10 | 13.297 | 15.7 | 10 | True |
| duckdb | 8 | post_type_counts | 10 | 1.596 | 2.022 | 2 | True |
| duckdb | 8 | posthistory_by_type | 10 | 2.647 | 3.291 | 21 | True |
| duckdb | 8 | postlinks_by_type | 10 | 0.871 | 1.111 | 2 | True |
| duckdb | 8 | top_answers_by_score | 10 | 2.269 | 3.281 | 10 | True |
| duckdb | 8 | top_badges | 10 | 1.191 | 1.355 | 2 | True |
| duckdb | 8 | top_questions_by_score | 10 | 2.773 | 6.674 | 10 | True |
| duckdb | 8 | top_tags_by_count | 10 | 0.424 | 0.559 | 10 | True |
| duckdb | 8 | top_users_by_reputation | 10 | 1.958 | 2.382 | 10 | True |
| duckdb | 8 | votes_by_type | 10 | 3.323 | 3.915 | 18 | True |
| postgresql | 1 | most_commented_posts | 10 | 250.769 | 275.166 | 10 | True |
| postgresql | 1 | post_type_counts | 10 | 139.461 | 179.431 | 2 | True |
| postgresql | 1 | posthistory_by_type | 10 | 3,188.668 | 3,368.281 | 21 | True |
| postgresql | 1 | postlinks_by_type | 10 | 36.489 | 82.184 | 2 | True |
| postgresql | 1 | top_answers_by_score | 10 | 0.284 | 0.384 | 10 | True |
| postgresql | 1 | top_badges | 10 | 216.147 | 278.442 | 2 | True |
| postgresql | 1 | top_questions_by_score | 10 | 6.829 | 35.094 | 10 | True |
| postgresql | 1 | top_tags_by_count | 10 | 0.58 | 1.515 | 10 | True |
| postgresql | 1 | top_users_by_reputation | 10 | 0.631 | 2.316 | 10 | True |
| postgresql | 1 | votes_by_type | 10 | 810.412 | 890.492 | 18 | True |
| postgresql | 4 | most_commented_posts | 10 | 242.528 | 265.331 | 10 | True |
| postgresql | 4 | post_type_counts | 10 | 75.272 | 92.47 | 2 | True |
| postgresql | 4 | posthistory_by_type | 10 | 2,640 | 3,727.266 | 21 | True |
| postgresql | 4 | postlinks_by_type | 10 | 20.689 | 28.491 | 2 | True |
| postgresql | 4 | top_answers_by_score | 10 | 0.417 | 0.874 | 10 | True |
| postgresql | 4 | top_badges | 10 | 130.084 | 214.136 | 2 | True |
| postgresql | 4 | top_questions_by_score | 10 | 0.53 | 1.11 | 10 | True |
| postgresql | 4 | top_tags_by_count | 10 | 0.585 | 0.96 | 10 | True |
| postgresql | 4 | top_users_by_reputation | 10 | 0.791 | 2.64 | 10 | True |
| postgresql | 4 | votes_by_type | 10 | 363.194 | 462.721 | 18 | True |
| postgresql | 8 | most_commented_posts | 10 | 232.57 | 262.71 | 10 | True |
| postgresql | 8 | post_type_counts | 10 | 74.785 | 98.154 | 2 | True |
| postgresql | 8 | posthistory_by_type | 10 | 2,498.015 | 3,641.162 | 21 | True |
| postgresql | 8 | postlinks_by_type | 10 | 19.174 | 22.58 | 2 | True |
| postgresql | 8 | top_answers_by_score | 10 | 0.319 | 0.456 | 10 | True |
| postgresql | 8 | top_badges | 10 | 106.799 | 142.565 | 2 | True |
| postgresql | 8 | top_questions_by_score | 10 | 0.486 | 1.38 | 10 | True |
| postgresql | 8 | top_tags_by_count | 10 | 0.609 | 1.109 | 10 | True |
| postgresql | 8 | top_users_by_reputation | 10 | 1.822 | 8.769 | 10 | True |
| postgresql | 8 | votes_by_type | 10 | 384.311 | 488.175 | 18 | True |
| sqlite | 1 | most_commented_posts | 10 | 159.403 | 165.804 | 10 | True |
| sqlite | 1 | post_type_counts | 10 | 72.714 | 76.005 | 2 | True |
| sqlite | 1 | posthistory_by_type | 10 | 187.723 | 198.079 | 21 | True |
| sqlite | 1 | postlinks_by_type | 10 | 5.8 | 6.64 | 2 | True |
| sqlite | 1 | top_answers_by_score | 10 | 1,055.319 | 1,171.023 | 10 | True |
| sqlite | 1 | top_badges | 10 | 54.743 | 61.949 | 2 | True |
| sqlite | 1 | top_questions_by_score | 10 | 797.371 | 881.887 | 10 | True |
| sqlite | 1 | top_tags_by_count | 10 | 0.146 | 0.171 | 10 | True |
| sqlite | 1 | top_users_by_reputation | 10 | 0.101 | 0.268 | 10 | True |
| sqlite | 1 | votes_by_type | 10 | 202.418 | 215.919 | 18 | True |
| sqlite | 4 | most_commented_posts | 10 | 157.719 | 164.955 | 10 | True |
| sqlite | 4 | post_type_counts | 10 | 70.915 | 75.484 | 2 | True |
| sqlite | 4 | posthistory_by_type | 10 | 181.057 | 194.539 | 21 | True |
| sqlite | 4 | postlinks_by_type | 10 | 5.535 | 6.35 | 2 | True |
| sqlite | 4 | top_answers_by_score | 10 | 982.607 | 1,037.299 | 10 | True |
| sqlite | 4 | top_badges | 10 | 53.197 | 58.171 | 2 | True |
| sqlite | 4 | top_questions_by_score | 10 | 738.515 | 766.237 | 10 | True |
| sqlite | 4 | top_tags_by_count | 10 | 0.197 | 0.451 | 10 | True |
| sqlite | 4 | top_users_by_reputation | 10 | 0.111 | 0.319 | 10 | True |
| sqlite | 4 | votes_by_type | 10 | 195.112 | 211.854 | 18 | True |
| sqlite | 8 | most_commented_posts | 10 | 160.396 | 168.756 | 10 | True |
| sqlite | 8 | post_type_counts | 10 | 72.697 | 75.796 | 2 | True |
| sqlite | 8 | posthistory_by_type | 10 | 182.358 | 194.839 | 21 | True |
| sqlite | 8 | postlinks_by_type | 10 | 5.953 | 6.85 | 2 | True |
| sqlite | 8 | top_answers_by_score | 10 | 1,060.061 | 1,162.616 | 10 | True |
| sqlite | 8 | top_badges | 10 | 54.397 | 62.639 | 2 | True |
| sqlite | 8 | top_questions_by_score | 10 | 805.973 | 886.071 | 10 | True |
| sqlite | 8 | top_tags_by_count | 10 | 0.175 | 0.32 | 10 | True |
| sqlite | 8 | top_users_by_reputation | 10 | 0.105 | 0.265 | 10 | True |
| sqlite | 8 | votes_by_type | 10 | 203.422 | 222.503 | 18 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | all_hashes |
|---|---|---|---|
| most_commented_posts | arcadedb_sql, duckdb, postgresql, sqlite | True | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e |
| post_type_counts | arcadedb_sql, duckdb, postgresql, sqlite | True | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 |
| posthistory_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b |
| postlinks_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 |
| top_answers_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd |
| top_badges | arcadedb_sql, duckdb, postgresql, sqlite | True | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd |
| top_questions_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 |
| top_tags_by_count | arcadedb_sql, duckdb, postgresql, sqlite | True | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec |
| top_users_by_reputation | arcadedb_sql, duckdb, postgresql, sqlite | True | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 |
| votes_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e |
