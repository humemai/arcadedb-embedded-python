# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T13:11:58Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 24
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:08c19266ac0fee12e891534141ccc1e9ae6a493d3b69479feaad1261218395c4, arcadedata/arcadedb@sha256:5606b0f9f7f6d1f5d91ee5c62046074e230aaa73fa4984e8d303ad82038b5204, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585, ... (+2 more)
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - duckdb: auto
  - duckdb_runtime_version: 1.5.0
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=24, success=24, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 1 | 100 | shuffled | bulk_tuned_insert | 713.583 | 1,531.178 | 15,768.988 | 6,771.938 | 8,863.953 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 4 | 100 | shuffled | bulk_tuned_insert | 766.93 | 1,560.059 | 16,645.468 | 6,438.742 | 8,863.945 |
| arcadedb_sql | sweep08_t08_r01_arcadedb_sql_s00003_mem8g | 3 | 1 | 10,000 | 8g | 8 | 100 | shuffled | bulk_tuned_insert | 815.177 | 1,580.613 | 15,710.747 | 6,938.078 | 8,863.945 |
| duckdb | sweep08_t01_r01_duckdb_s00000_mem8g | 0 | 1 | 10,000 | 8g | 1 | 100 | shuffled | copy_csv | 507.563 | 0 | 17.46 | 6,414.094 | 17,541.422 |
| duckdb | sweep08_t04_r01_duckdb_s00000_mem8g | 0 | 1 | 10,000 | 8g | 4 | 100 | shuffled | copy_csv | 494.861 | 0 | 5.628 | 8,016.219 | 17,538.676 |
| duckdb | sweep08_t08_r01_duckdb_s00000_mem8g | 0 | 1 | 10,000 | 8g | 8 | 100 | shuffled | copy_csv | 496.671 | 0 | 4.037 | 7,747.883 | 17,537.418 |
| postgresql | sweep08_t01_r01_postgresql_s00002_mem8g | 2 | 1 | 10,000 | 8g | 1 | 100 | shuffled | copy_from_stdin | 584.426 | 46.119 | 376.271 | 3,494.324 | 16,071.297 |
| postgresql | sweep08_t04_r01_postgresql_s00002_mem8g | 2 | 1 | 10,000 | 8g | 4 | 100 | shuffled | copy_from_stdin | 496.397 | 30.609 | 114.205 | 2,634.801 | 16,071.211 |
| postgresql | sweep08_t08_r01_postgresql_s00001_mem8g | 1 | 1 | 10,000 | 8g | 8 | 100 | shuffled | copy_from_stdin | 504.869 | 38.45 | 115.498 | 2,742.203 | 16,071.254 |
| sqlite | sweep08_t01_r01_sqlite_s00000_mem8g | 0 | 1 | 10,000 | 8g | 1 | 100 | shuffled | executemany | 237.635 | 40.862 | 270.244 | 848.434 | 8,829.914 |
| sqlite | sweep08_t04_r01_sqlite_s00000_mem8g | 0 | 1 | 10,000 | 8g | 4 | 100 | shuffled | executemany | 267.511 | 43.902 | 302.047 | 845.719 | 8,829.918 |
| sqlite | sweep08_t08_r01_sqlite_s00000_mem8g | 0 | 1 | 10,000 | 8g | 8 | 100 | shuffled | executemany | 274.191 | 48.518 | 319.653 | 847.277 | 8,829.918 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 100 | 5,886.596 | 8,219.977 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 100 | 19,153.153 | 28,385.253 | 2 | True |
| arcadedb_sql | 1 | posthistory_by_type | 100 | 103,111.83 | 153,765.634 | 21 | True |
| arcadedb_sql | 1 | postlinks_by_type | 100 | 371.654 | 717.725 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 100 | 9,848.908 | 16,110.71 | 10 | True |
| arcadedb_sql | 1 | top_badges | 100 | 1,321.531 | 1,826.756 | 2 | True |
| arcadedb_sql | 1 | top_questions_by_score | 100 | 7,350.541 | 11,432.374 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 100 | 4.821 | 4.881 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 100 | 928.911 | 1,456.206 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 100 | 9,710.915 | 11,312.075 | 18 | True |
| arcadedb_sql | 4 | most_commented_posts | 100 | 3,986.642 | 5,629.178 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 100 | 9,486.546 | 14,795.809 | 2 | True |
| arcadedb_sql | 4 | posthistory_by_type | 100 | 129,516.118 | 200,952.414 | 21 | True |
| arcadedb_sql | 4 | postlinks_by_type | 100 | 296.541 | 450.861 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 100 | 7,545.26 | 15,234.209 | 10 | True |
| arcadedb_sql | 4 | top_badges | 100 | 1,195.966 | 1,498.008 | 2 | True |
| arcadedb_sql | 4 | top_questions_by_score | 100 | 4,601.116 | 11,811.383 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 100 | 2.909 | 4.455 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 100 | 838.373 | 1,123.776 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 100 | 8,984.22 | 10,524.056 | 18 | True |
| arcadedb_sql | 8 | most_commented_posts | 100 | 3,362.116 | 5,167.887 | 10 | True |
| arcadedb_sql | 8 | post_type_counts | 100 | 8,958.058 | 18,420.664 | 2 | True |
| arcadedb_sql | 8 | posthistory_by_type | 100 | 125,137.113 | 211,679.834 | 21 | True |
| arcadedb_sql | 8 | postlinks_by_type | 100 | 266.594 | 355.947 | 2 | True |
| arcadedb_sql | 8 | top_answers_by_score | 100 | 5,581.828 | 10,129.955 | 10 | True |
| arcadedb_sql | 8 | top_badges | 100 | 1,057.42 | 1,339.142 | 2 | True |
| arcadedb_sql | 8 | top_questions_by_score | 100 | 3,716.055 | 9,473.197 | 10 | True |
| arcadedb_sql | 8 | top_tags_by_count | 100 | 2.865 | 5.549 | 10 | True |
| arcadedb_sql | 8 | top_users_by_reputation | 100 | 740.621 | 987.799 | 10 | True |
| arcadedb_sql | 8 | votes_by_type | 100 | 8,283.871 | 9,607.743 | 18 | True |
| duckdb | 1 | most_commented_posts | 100 | 105.378 | 166.938 | 10 | True |
| duckdb | 1 | post_type_counts | 100 | 7.958 | 9.364 | 2 | True |
| duckdb | 1 | posthistory_by_type | 100 | 16.91 | 18.827 | 21 | True |
| duckdb | 1 | postlinks_by_type | 100 | 1.579 | 2.792 | 2 | True |
| duckdb | 1 | top_answers_by_score | 100 | 5.543 | 9.486 | 10 | True |
| duckdb | 1 | top_badges | 100 | 4.11 | 5.83 | 2 | True |
| duckdb | 1 | top_questions_by_score | 100 | 6.674 | 9.869 | 10 | True |
| duckdb | 1 | top_tags_by_count | 100 | 0.768 | 1.722 | 10 | True |
| duckdb | 1 | top_users_by_reputation | 100 | 3.492 | 6.559 | 10 | True |
| duckdb | 1 | votes_by_type | 100 | 21.202 | 23.329 | 18 | True |
| duckdb | 4 | most_commented_posts | 100 | 26.365 | 32.681 | 10 | True |
| duckdb | 4 | post_type_counts | 100 | 2.889 | 4.416 | 2 | True |
| duckdb | 4 | posthistory_by_type | 100 | 5.184 | 6.899 | 21 | True |
| duckdb | 4 | postlinks_by_type | 100 | 1.386 | 2.46 | 2 | True |
| duckdb | 4 | top_answers_by_score | 100 | 3.857 | 6.929 | 10 | True |
| duckdb | 4 | top_badges | 100 | 2.076 | 3.573 | 2 | True |
| duckdb | 4 | top_questions_by_score | 100 | 3.609 | 6.319 | 10 | True |
| duckdb | 4 | top_tags_by_count | 100 | 0.783 | 1.683 | 10 | True |
| duckdb | 4 | top_users_by_reputation | 100 | 2.919 | 5.106 | 10 | True |
| duckdb | 4 | votes_by_type | 100 | 6.302 | 7.516 | 18 | True |
| duckdb | 8 | most_commented_posts | 100 | 17.013 | 25.17 | 10 | True |
| duckdb | 8 | post_type_counts | 100 | 2.104 | 3.384 | 2 | True |
| duckdb | 8 | posthistory_by_type | 100 | 3.382 | 4.703 | 21 | True |
| duckdb | 8 | postlinks_by_type | 100 | 1.187 | 2.009 | 2 | True |
| duckdb | 8 | top_answers_by_score | 100 | 3.039 | 5.173 | 10 | True |
| duckdb | 8 | top_badges | 100 | 1.828 | 2.985 | 2 | True |
| duckdb | 8 | top_questions_by_score | 100 | 3.06 | 5.513 | 10 | True |
| duckdb | 8 | top_tags_by_count | 100 | 0.771 | 1.729 | 10 | True |
| duckdb | 8 | top_users_by_reputation | 100 | 3.072 | 5.978 | 10 | True |
| duckdb | 8 | votes_by_type | 100 | 3.921 | 4.966 | 18 | True |
| postgresql | 1 | most_commented_posts | 100 | 298.066 | 343.511 | 10 | True |
| postgresql | 1 | post_type_counts | 100 | 168.837 | 204.47 | 2 | True |
| postgresql | 1 | posthistory_by_type | 100 | 2,288.225 | 2,588.147 | 21 | True |
| postgresql | 1 | postlinks_by_type | 100 | 38.051 | 93.313 | 2 | True |
| postgresql | 1 | top_answers_by_score | 100 | 0.291 | 0.549 | 10 | True |
| postgresql | 1 | top_badges | 100 | 206.894 | 283.438 | 2 | True |
| postgresql | 1 | top_questions_by_score | 100 | 0.308 | 0.761 | 10 | True |
| postgresql | 1 | top_tags_by_count | 100 | 4.492 | 0.834 | 10 | True |
| postgresql | 1 | top_users_by_reputation | 100 | 0.307 | 0.483 | 10 | True |
| postgresql | 1 | votes_by_type | 100 | 756.535 | 842.255 | 18 | True |
| postgresql | 4 | most_commented_posts | 100 | 239.122 | 262.493 | 10 | True |
| postgresql | 4 | post_type_counts | 100 | 72.769 | 88.508 | 2 | True |
| postgresql | 4 | posthistory_by_type | 100 | 540.194 | 669.149 | 21 | True |
| postgresql | 4 | postlinks_by_type | 100 | 23.135 | 39.136 | 2 | True |
| postgresql | 4 | top_answers_by_score | 100 | 0.305 | 0.464 | 10 | True |
| postgresql | 4 | top_badges | 100 | 62.926 | 78.066 | 2 | True |
| postgresql | 4 | top_questions_by_score | 100 | 0.443 | 0.722 | 10 | True |
| postgresql | 4 | top_tags_by_count | 100 | 0.43 | 0.863 | 10 | True |
| postgresql | 4 | top_users_by_reputation | 100 | 0.403 | 0.679 | 10 | True |
| postgresql | 4 | votes_by_type | 100 | 201.602 | 227.719 | 18 | True |
| postgresql | 8 | most_commented_posts | 100 | 247.544 | 279.146 | 10 | True |
| postgresql | 8 | post_type_counts | 100 | 82.535 | 98.88 | 2 | True |
| postgresql | 8 | posthistory_by_type | 100 | 505.773 | 629.384 | 21 | True |
| postgresql | 8 | postlinks_by_type | 100 | 33.002 | 41.06 | 2 | True |
| postgresql | 8 | top_answers_by_score | 100 | 0.435 | 1.03 | 10 | True |
| postgresql | 8 | top_badges | 100 | 73.195 | 87.797 | 2 | True |
| postgresql | 8 | top_questions_by_score | 100 | 0.34 | 0.619 | 10 | True |
| postgresql | 8 | top_tags_by_count | 100 | 0.487 | 0.946 | 10 | True |
| postgresql | 8 | top_users_by_reputation | 100 | 0.391 | 0.799 | 10 | True |
| postgresql | 8 | votes_by_type | 100 | 210.425 | 232.674 | 18 | True |
| sqlite | 1 | most_commented_posts | 100 | 166.183 | 174.528 | 10 | True |
| sqlite | 1 | post_type_counts | 100 | 103.075 | 108.827 | 2 | True |
| sqlite | 1 | posthistory_by_type | 100 | 184.23 | 196.227 | 21 | True |
| sqlite | 1 | postlinks_by_type | 100 | 5.569 | 6.111 | 2 | True |
| sqlite | 1 | top_answers_by_score | 100 | 1,131.906 | 1,309.622 | 10 | True |
| sqlite | 1 | top_badges | 100 | 53.879 | 57.557 | 2 | True |
| sqlite | 1 | top_questions_by_score | 100 | 850.91 | 959.306 | 10 | True |
| sqlite | 1 | top_tags_by_count | 100 | 0.17 | 0.225 | 10 | True |
| sqlite | 1 | top_users_by_reputation | 100 | 0.087 | 0.11 | 10 | True |
| sqlite | 1 | votes_by_type | 100 | 205.66 | 220.33 | 18 | True |
| sqlite | 4 | most_commented_posts | 100 | 166.559 | 175.843 | 10 | True |
| sqlite | 4 | post_type_counts | 100 | 75.924 | 84.316 | 2 | True |
| sqlite | 4 | posthistory_by_type | 100 | 198.607 | 216.972 | 21 | True |
| sqlite | 4 | postlinks_by_type | 100 | 5.817 | 7.331 | 2 | True |
| sqlite | 4 | top_answers_by_score | 100 | 1,301.116 | 1,523.518 | 10 | True |
| sqlite | 4 | top_badges | 100 | 57.017 | 71.608 | 2 | True |
| sqlite | 4 | top_questions_by_score | 100 | 1,000.156 | 1,264.071 | 10 | True |
| sqlite | 4 | top_tags_by_count | 100 | 0.171 | 0.267 | 10 | True |
| sqlite | 4 | top_users_by_reputation | 100 | 0.111 | 0.208 | 10 | True |
| sqlite | 4 | votes_by_type | 100 | 214.107 | 238.543 | 18 | True |
| sqlite | 8 | most_commented_posts | 100 | 170.679 | 183.871 | 10 | True |
| sqlite | 8 | post_type_counts | 100 | 77.257 | 87.025 | 2 | True |
| sqlite | 8 | posthistory_by_type | 100 | 198.51 | 215.982 | 21 | True |
| sqlite | 8 | postlinks_by_type | 100 | 5.883 | 7.061 | 2 | True |
| sqlite | 8 | top_answers_by_score | 100 | 1,390.257 | 1,686.245 | 10 | True |
| sqlite | 8 | top_badges | 100 | 62.048 | 79.934 | 2 | True |
| sqlite | 8 | top_questions_by_score | 100 | 1,075.948 | 1,310.726 | 10 | True |
| sqlite | 8 | top_tags_by_count | 100 | 0.192 | 0.332 | 10 | True |
| sqlite | 8 | top_users_by_reputation | 100 | 0.512 | 0.24 | 10 | True |
| sqlite | 8 | votes_by_type | 100 | 214.233 | 233.785 | 18 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | hash_groups | all_hashes |
|---|---|---|---|---|
| most_commented_posts | arcadedb_sql, duckdb, postgresql, sqlite | True | c02fce1c41f3: arcadedb_sql, duckdb, postgresql, sqlite | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e |
| post_type_counts | arcadedb_sql, duckdb, postgresql, sqlite | True | c8efbbf3e909: arcadedb_sql, duckdb, postgresql, sqlite | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 |
| posthistory_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | c67f8c69f547: arcadedb_sql, duckdb, postgresql, sqlite | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b |
| postlinks_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | bb2f5bdb63e7: arcadedb_sql, duckdb, postgresql, sqlite | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 |
| top_answers_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 333d74b2cb34: arcadedb_sql, duckdb, postgresql, sqlite | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd |
| top_badges | arcadedb_sql, duckdb, postgresql, sqlite | True | f63586af2948: arcadedb_sql, duckdb, postgresql, sqlite | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd |
| top_questions_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 872279d216c1: arcadedb_sql, duckdb, postgresql, sqlite | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 |
| top_tags_by_count | arcadedb_sql, duckdb, postgresql, sqlite | True | 48c33c107b02: arcadedb_sql, duckdb, postgresql, sqlite | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec |
| top_users_by_reputation | arcadedb_sql, duckdb, postgresql, sqlite | True | 9c6a96d5e2a2: arcadedb_sql, duckdb, postgresql, sqlite | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 |
| votes_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | bf98e4b1c5d1: arcadedb_sql, duckdb, postgresql, sqlite | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e |

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 1 | 100 | shuffled | bulk_tuned_insert | 172.945 | 86.463 | 4,528.169 | 3,455.598 | 2,694.016 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 4 | 100 | shuffled | bulk_tuned_insert | 161.579 | 74.509 | 2,762.007 | 3,341.48 | 2,694.008 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 5,000 | 8g | 4 | 100 | shuffled | bulk_tuned_insert | 167.464 | 73.148 | 924.121 | 6,241.055 | 2,694.016 |
| duckdb | sweep08_t01_r01_duckdb_s00000_mem4g | 0 | 1 | 5,000 | 4g | 1 | 100 | shuffled | copy_csv | 139.812 | 0 | 3.237 | 2,372.527 | 5,133.613 |
| duckdb | sweep08_t04_r01_duckdb_s00000_mem4g | 0 | 1 | 5,000 | 4g | 4 | 100 | shuffled | copy_csv | 130.349 | 0 | 2.125 | 2,765.754 | 5,137.113 |
| duckdb | sweep08_t01_r01_duckdb_s00000_mem8g | 0 | 1 | 5,000 | 8g | 1 | 100 | shuffled | copy_csv | 123.204 | 0 | 3.262 | 2,373.992 | 5,132.867 |
| postgresql | sweep08_t01_r01_postgresql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 1 | 100 | shuffled | copy_from_stdin | 170.231 | 18.198 | 188.183 | 2,395.047 | 5,494.469 |
| postgresql | sweep08_t04_r01_postgresql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 4 | 100 | shuffled | copy_from_stdin | 172.095 | 11.786 | 36.58 | 2,306.328 | 5,494.352 |
| sqlite | sweep08_t01_r01_sqlite_s00000_mem4g | 0 | 1 | 5,000 | 4g | 1 | 100 | shuffled | executemany | 54.596 | 6.475 | 56.463 | 574.754 | 2,759.66 |
| sqlite | sweep08_t04_r01_sqlite_s00000_mem4g | 0 | 1 | 5,000 | 4g | 4 | 100 | shuffled | executemany | 61.087 | 7.616 | 60.118 | 574.055 | 2,759.723 |
| sqlite | sweep08_t01_r01_sqlite_s00000_mem8g | 0 | 1 | 5,000 | 8g | 1 | 100 | shuffled | executemany | 69.526 | 6.73 | 56.324 | 574.578 | 2,759.664 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 100 | 1,357.116 | 1,654.86 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 100 | 1,784.059 | 3,215.544 | 7 | True |
| arcadedb_sql | 1 | posthistory_by_type | 100 | 35,811.324 | 69,509.348 | 30 | True |
| arcadedb_sql | 1 | postlinks_by_type | 100 | 128.749 | 238.347 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 100 | 1,517.162 | 2,755.673 | 10 | True |
| arcadedb_sql | 1 | top_badges | 100 | 495.835 | 696.005 | 10 | True |
| arcadedb_sql | 1 | top_questions_by_score | 100 | 1,479.6 | 3,179.678 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 100 | 2.067 | 3.127 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 100 | 471.375 | 660.178 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 100 | 2,233.469 | 2,574.949 | 14 | True |
| arcadedb_sql | 4 | most_commented_posts | 200 | 1,051.601 | 1,486.169 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 200 | 1,312.744 | 2,211.076 | 7 | True |
| arcadedb_sql | 4 | posthistory_by_type | 200 | 10,564.026 | 22,902.258 | 30 | True |
| arcadedb_sql | 4 | postlinks_by_type | 200 | 112.584 | 152.572 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 200 | 1,301.617 | 4,397.22 | 10 | True |
| arcadedb_sql | 4 | top_badges | 200 | 411.097 | 512.123 | 10 | True |
| arcadedb_sql | 4 | top_questions_by_score | 200 | 1,145.996 | 3,203.739 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 200 | 2.612 | 3.819 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 200 | 396.677 | 529.981 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 200 | 2,130.402 | 2,416.507 | 14 | True |
| duckdb | 1 | most_commented_posts | 200 | 13.519 | 16.32 | 10 | True |
| duckdb | 1 | post_type_counts | 200 | 1.581 | 1.884 | 7 | True |
| duckdb | 1 | posthistory_by_type | 200 | 3.534 | 3.859 | 30 | True |
| duckdb | 1 | postlinks_by_type | 200 | 0.786 | 1.023 | 2 | True |
| duckdb | 1 | top_answers_by_score | 200 | 1.556 | 1.996 | 10 | True |
| duckdb | 1 | top_badges | 200 | 1.644 | 1.916 | 10 | True |
| duckdb | 1 | top_questions_by_score | 200 | 1.91 | 2.35 | 10 | True |
| duckdb | 1 | top_tags_by_count | 200 | 0.378 | 0.606 | 10 | True |
| duckdb | 1 | top_users_by_reputation | 200 | 2.117 | 2.504 | 10 | True |
| duckdb | 1 | votes_by_type | 200 | 5.007 | 5.458 | 14 | True |
| duckdb | 4 | most_commented_posts | 100 | 8.117 | 9.81 | 10 | True |
| duckdb | 4 | post_type_counts | 100 | 0.993 | 1.404 | 7 | True |
| duckdb | 4 | posthistory_by_type | 100 | 1.641 | 2.245 | 30 | True |
| duckdb | 4 | postlinks_by_type | 100 | 0.869 | 1.222 | 2 | True |
| duckdb | 4 | top_answers_by_score | 100 | 1.76 | 2.361 | 10 | True |
| duckdb | 4 | top_badges | 100 | 1.177 | 1.497 | 10 | True |
| duckdb | 4 | top_questions_by_score | 100 | 1.716 | 2.261 | 10 | True |
| duckdb | 4 | top_tags_by_count | 100 | 0.47 | 0.681 | 10 | True |
| duckdb | 4 | top_users_by_reputation | 100 | 1.984 | 3.053 | 10 | True |
| duckdb | 4 | votes_by_type | 100 | 1.999 | 2.666 | 14 | True |
| postgresql | 1 | most_commented_posts | 100 | 886.008 | 1,723.463 | 10 | True |
| postgresql | 1 | post_type_counts | 100 | 63.202 | 96.665 | 7 | True |
| postgresql | 1 | posthistory_by_type | 100 | 604.297 | 784.398 | 30 | True |
| postgresql | 1 | postlinks_by_type | 100 | 10.969 | 61.342 | 2 | True |
| postgresql | 1 | top_answers_by_score | 100 | 0.405 | 1.119 | 10 | True |
| postgresql | 1 | top_badges | 100 | 102.791 | 171.367 | 10 | True |
| postgresql | 1 | top_questions_by_score | 100 | 0.333 | 1.173 | 10 | True |
| postgresql | 1 | top_tags_by_count | 100 | 1.153 | 1.514 | 10 | True |
| postgresql | 1 | top_users_by_reputation | 100 | 0.446 | 1.213 | 10 | True |
| postgresql | 1 | votes_by_type | 100 | 211.505 | 279.286 | 14 | True |
| postgresql | 4 | most_commented_posts | 100 | 60.619 | 71.315 | 10 | True |
| postgresql | 4 | post_type_counts | 100 | 25.011 | 32.08 | 7 | True |
| postgresql | 4 | posthistory_by_type | 100 | 138.764 | 164.584 | 30 | True |
| postgresql | 4 | postlinks_by_type | 100 | 7.386 | 9.535 | 2 | True |
| postgresql | 4 | top_answers_by_score | 100 | 0.252 | 0.415 | 10 | True |
| postgresql | 4 | top_badges | 100 | 52.877 | 47.806 | 10 | True |
| postgresql | 4 | top_questions_by_score | 100 | 0.241 | 0.45 | 10 | True |
| postgresql | 4 | top_tags_by_count | 100 | 0.364 | 0.639 | 10 | True |
| postgresql | 4 | top_users_by_reputation | 100 | 0.283 | 0.514 | 10 | True |
| postgresql | 4 | votes_by_type | 100 | 79.334 | 84.917 | 14 | True |
| sqlite | 1 | most_commented_posts | 200 | 44.394 | 48.2 | 10 | True |
| sqlite | 1 | post_type_counts | 200 | 11.792 | 13.237 | 7 | True |
| sqlite | 1 | posthistory_by_type | 200 | 42.279 | 45.844 | 30 | True |
| sqlite | 1 | postlinks_by_type | 200 | 2.462 | 2.774 | 2 | True |
| sqlite | 1 | top_answers_by_score | 200 | 192.228 | 212.22 | 10 | True |
| sqlite | 1 | top_badges | 200 | 20.786 | 23.194 | 10 | True |
| sqlite | 1 | top_questions_by_score | 200 | 200.975 | 244.849 | 10 | True |
| sqlite | 1 | top_tags_by_count | 200 | 0.139 | 0.178 | 10 | True |
| sqlite | 1 | top_users_by_reputation | 200 | 0.073 | 0.088 | 10 | True |
| sqlite | 1 | votes_by_type | 200 | 48.053 | 52.66 | 14 | True |
| sqlite | 4 | most_commented_posts | 100 | 44.996 | 49.486 | 10 | True |
| sqlite | 4 | post_type_counts | 100 | 12.412 | 14.684 | 7 | True |
| sqlite | 4 | posthistory_by_type | 100 | 44.602 | 50.779 | 30 | True |
| sqlite | 4 | postlinks_by_type | 100 | 2.575 | 3.139 | 2 | True |
| sqlite | 4 | top_answers_by_score | 100 | 207.402 | 303.514 | 10 | True |
| sqlite | 4 | top_badges | 100 | 22.268 | 26.823 | 10 | True |
| sqlite | 4 | top_questions_by_score | 100 | 214.4 | 300.35 | 10 | True |
| sqlite | 4 | top_tags_by_count | 100 | 0.138 | 0.173 | 10 | True |
| sqlite | 4 | top_users_by_reputation | 100 | 0.076 | 0.129 | 10 | True |
| sqlite | 4 | votes_by_type | 100 | 51.488 | 58.586 | 14 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | hash_groups | all_hashes |
|---|---|---|---|---|
| most_commented_posts | arcadedb_sql, duckdb, postgresql, sqlite | True | 27b02cb14143: arcadedb_sql, duckdb, postgresql, sqlite | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 |
| post_type_counts | arcadedb_sql, duckdb, postgresql, sqlite | True | 33e9d5435597: arcadedb_sql, duckdb, postgresql, sqlite | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b |
| posthistory_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | a3e208f15018: arcadedb_sql, duckdb, postgresql, sqlite | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b |
| postlinks_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | cb48b32b69b1: arcadedb_sql, duckdb, postgresql, sqlite | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 |
| top_answers_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 7ae3696d8738: arcadedb_sql, duckdb, postgresql, sqlite | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 |
| top_badges | arcadedb_sql, duckdb, postgresql, sqlite | True | 82f14f38c32b: arcadedb_sql, duckdb, postgresql, sqlite | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 |
| top_questions_by_score | arcadedb_sql, duckdb, postgresql, sqlite | True | 2a54b3b1dadd: arcadedb_sql, duckdb, postgresql, sqlite | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce |
| top_tags_by_count | arcadedb_sql, duckdb, postgresql, sqlite | True | 10b7fad6634c: arcadedb_sql, duckdb, postgresql, sqlite | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf |
| top_users_by_reputation | arcadedb_sql, duckdb, postgresql, sqlite | True | b1f26ff3a874: arcadedb_sql, duckdb, postgresql, sqlite | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 |
| votes_by_type | arcadedb_sql, duckdb, postgresql, sqlite | True | 43e07f73af8b: arcadedb_sql, duckdb, postgresql, sqlite | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c |

## Dataset: stackoverflow-xlarge

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| duckdb | sweep08_t08_r01_duckdb_s00000_mem32g | 0 | 1 | 25,000 | 32g | 8 | 100 | shuffled | copy_csv | 1,701.979 | 0 | 10.459 | 29,462.887 | 86,160.59 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| duckdb | 8 | most_commented_posts | 100 | 57.923 | 70.472 | 10 | True |
| duckdb | 8 | post_type_counts | 100 | 5.346 | 6.127 | 7 | True |
| duckdb | 8 | posthistory_by_type | 100 | 10.71 | 12.59 | 26 | True |
| duckdb | 8 | postlinks_by_type | 100 | 1.27 | 1.68 | 2 | True |
| duckdb | 8 | top_answers_by_score | 100 | 3.797 | 4.796 | 10 | True |
| duckdb | 8 | top_badges | 100 | 3.589 | 4.241 | 5 | True |
| duckdb | 8 | top_questions_by_score | 100 | 3.597 | 4.915 | 10 | True |
| duckdb | 8 | top_tags_by_count | 100 | 0.63 | 0.938 | 10 | True |
| duckdb | 8 | top_users_by_reputation | 100 | 2.582 | 3.418 | 10 | True |
| duckdb | 8 | votes_by_type | 100 | 14.405 | 16.124 | 18 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | hash_groups | all_hashes |
|---|---|---|---|---|
| most_commented_posts | duckdb | True | 678a2b58640c: duckdb | 678a2b58640cc193d20d659f22bde32cc556ecfe41923096e1bd8e3f56b1eccb |
| post_type_counts | duckdb | True | f33db3373a4b: duckdb | f33db3373a4b2d1eed5f567dd5f6ffd09834ca68b628afa552ff48df812f8e3b |
| posthistory_by_type | duckdb | True | 5f39e5aa3c05: duckdb | 5f39e5aa3c05b02cffd5f5099290b82050620c62fc09b8a047dd55e5f4c914a3 |
| postlinks_by_type | duckdb | True | 95bbc851337c: duckdb | 95bbc851337c6f02db82481c62e339bd4393e3e8b8987ff101c77da2e2f969e7 |
| top_answers_by_score | duckdb | True | d8964a679d7a: duckdb | d8964a679d7a80fab26c9728b999afe20774162e0195feb4bbc43ecc5cf9f93e |
| top_badges | duckdb | True | 9343896232b1: duckdb | 9343896232b134c387d479ec6ace244d6c85f85207e06b91635878f7221cedcd |
| top_questions_by_score | duckdb | True | 5967ccd791a9: duckdb | 5967ccd791a9cd8098535e28b2b28d80a8d8680ab931e2f7ad88a22d7d1e69be |
| top_tags_by_count | duckdb | True | 48c33c107b02: duckdb | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec |
| top_users_by_reputation | duckdb | True | 9c6a96d5e2a2: duckdb | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 |
| votes_by_type | duckdb | True | dd9432df9c17: duckdb | dd9432df9c1777d901d9e7363f1cd4fd09333e07c51f1701452768db725e7925 |
