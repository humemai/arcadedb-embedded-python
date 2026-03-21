# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-21T09:58:09Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 4
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:6f1f08f5d05cb615d15ba346b4845cae7b42f0199b8c41bf26bcad2d44d1e8e1
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - postgresql_image: postgres:latest
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=4, success=4, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 1 | 100 | shuffled | bulk_tuned_insert | 746.905 | 1,067.28 | 12,141.284 | 6,892.363 | 8,947.773 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 4 | 100 | shuffled | bulk_tuned_insert | 430.836 | 873.472 | 13,620.748 | 7,052.184 | 8,947.773 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 100 | 4,588.069 | 5,449.434 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 100 | 16,489.71 | 20,291.411 | 2 | True |
| arcadedb_sql | 1 | posthistory_by_type | 100 | 74,130.716 | 88,544.873 | 21 | True |
| arcadedb_sql | 1 | postlinks_by_type | 100 | 329.077 | 686.488 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 100 | 8,500.431 | 10,942.5 | 10 | True |
| arcadedb_sql | 1 | top_badges | 100 | 1,226.139 | 1,468.903 | 2 | True |
| arcadedb_sql | 1 | top_questions_by_score | 100 | 6,415.97 | 7,931.15 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 100 | 2.476 | 3.578 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 100 | 806.235 | 1,167.543 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 100 | 8,922.924 | 9,672.817 | 18 | True |
| arcadedb_sql | 4 | most_commented_posts | 100 | 3,372.736 | 4,102.991 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 100 | 9,786.951 | 20,953.128 | 2 | True |
| arcadedb_sql | 4 | posthistory_by_type | 100 | 101,559.762 | 119,353.594 | 21 | True |
| arcadedb_sql | 4 | postlinks_by_type | 100 | 268.367 | 345.886 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 100 | 6,742.547 | 12,844.51 | 10 | True |
| arcadedb_sql | 4 | top_badges | 100 | 1,134.611 | 1,381.022 | 2 | True |
| arcadedb_sql | 4 | top_questions_by_score | 100 | 3,827.854 | 8,395.761 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 100 | 3.155 | 8.957 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 100 | 755.989 | 934.662 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 100 | 8,754.181 | 9,564.449 | 18 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | hash_groups | all_hashes |
|---|---|---|---|---|
| most_commented_posts | arcadedb_sql | True | c02fce1c41f3: arcadedb_sql | c02fce1c41f359b916c969ac702f5b104f89fa0a83af6932be499104b4e9f68e |
| post_type_counts | arcadedb_sql | True | c8efbbf3e909: arcadedb_sql | c8efbbf3e9096255141e9fb9293cedda760661d3152e2dea16ca49020a94a226 |
| posthistory_by_type | arcadedb_sql | True | c67f8c69f547: arcadedb_sql | c67f8c69f5474ee6e74c88e85c99216b6abfb808081b8265b8514f5d484f017b |
| postlinks_by_type | arcadedb_sql | True | bb2f5bdb63e7: arcadedb_sql | bb2f5bdb63e7f8ea10d3f798bed8abaa6dcca613e5ab5a6aa353116072ed24a4 |
| top_answers_by_score | arcadedb_sql | True | 333d74b2cb34: arcadedb_sql | 333d74b2cb34df7431c98f6e51dda214805b4fc44503e032fc4f3d20fb0d0cdd |
| top_badges | arcadedb_sql | True | f63586af2948: arcadedb_sql | f63586af2948c09196ea768ded6e37e418f236999ba9980ef87a8647c3499ccd |
| top_questions_by_score | arcadedb_sql | True | 872279d216c1: arcadedb_sql | 872279d216c193da0f34b03820854cfee51faa1a068afb19eb19528d0c7372b4 |
| top_tags_by_count | arcadedb_sql | True | 48c33c107b02: arcadedb_sql | 48c33c107b024bde76cd98d99e706868256011a64763946bb65aaa00e331baec |
| top_users_by_reputation | arcadedb_sql | True | 9c6a96d5e2a2: arcadedb_sql | 9c6a96d5e2a2100a7c55e402fbe285fea8d999613ed0712fa87739d32c177d14 |
| votes_by_type | arcadedb_sql | True | bf98e4b1c5d1: arcadedb_sql | bf98e4b1c5d18244c411d7afcab3dd496ec0251aa9f59a6699d0c59d57d0d33e |

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 1 | 100 | shuffled | bulk_tuned_insert | 192.018 | 171.573 | 5,591.331 | 3,493.434 | 2,724.824 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem4g | 0 | 1 | 5,000 | 4g | 4 | 100 | shuffled | bulk_tuned_insert | 95.511 | 147.466 | 3,754.118 | 3,322.5 | 2,724.824 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 100 | 1,691.817 | 2,797.71 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 100 | 1,657.714 | 2,452.664 | 7 | True |
| arcadedb_sql | 1 | posthistory_by_type | 100 | 45,389.878 | 91,127.834 | 30 | True |
| arcadedb_sql | 1 | postlinks_by_type | 100 | 143.71 | 287.629 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 100 | 1,975.873 | 4,369.208 | 10 | True |
| arcadedb_sql | 1 | top_badges | 100 | 524.538 | 794.212 | 10 | True |
| arcadedb_sql | 1 | top_questions_by_score | 100 | 1,678.377 | 4,035.711 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 100 | 2.881 | 7.321 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 100 | 468.897 | 745.726 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 100 | 2,378.68 | 3,075.888 | 14 | True |
| arcadedb_sql | 4 | most_commented_posts | 100 | 1,775.517 | 3,467.105 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 100 | 2,372.319 | 6,621.375 | 7 | True |
| arcadedb_sql | 4 | posthistory_by_type | 100 | 24,070.449 | 45,939.722 | 30 | True |
| arcadedb_sql | 4 | postlinks_by_type | 100 | 127.8 | 198.763 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 100 | 2,957.221 | 8,177.408 | 10 | True |
| arcadedb_sql | 4 | top_badges | 100 | 514.384 | 800.92 | 10 | True |
| arcadedb_sql | 4 | top_questions_by_score | 100 | 2,695.22 | 7,995.078 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 100 | 4.224 | 11.028 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 100 | 566.77 | 1,061.102 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 100 | 2,455.676 | 3,080.261 | 14 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | hash_groups | all_hashes |
|---|---|---|---|---|
| most_commented_posts | arcadedb_sql | True | 27b02cb14143: arcadedb_sql | 27b02cb141431ef02fa2f2d15243072887cf08dcc6b5bfb4d6f28e215c8e0131 |
| post_type_counts | arcadedb_sql | True | 33e9d5435597: arcadedb_sql | 33e9d54355975240d8d5c20d94af1559065addbc2298a007a94092b251961f2b |
| posthistory_by_type | arcadedb_sql | True | a3e208f15018: arcadedb_sql | a3e208f1501878a30b9603318df202afe35a72776ca42d73352037aa7cce477b |
| postlinks_by_type | arcadedb_sql | True | cb48b32b69b1: arcadedb_sql | cb48b32b69b1d26dc4713fe71daab0d153d3d8d6987e22c945daa97cbd878031 |
| top_answers_by_score | arcadedb_sql | True | 7ae3696d8738: arcadedb_sql | 7ae3696d87382423f7981e5052a16e6dd4699caebf07b2abffd088f2455a5ab6 |
| top_badges | arcadedb_sql | True | 82f14f38c32b: arcadedb_sql | 82f14f38c32b9cde15837b0fb3ae26b64b7d19cdc73f23d7be66a4a228b329d2 |
| top_questions_by_score | arcadedb_sql | True | 2a54b3b1dadd: arcadedb_sql | 2a54b3b1dadd848f09dd04af765993963cbb07c39d02190e6e17006b0d4d99ce |
| top_tags_by_count | arcadedb_sql | True | 10b7fad6634c: arcadedb_sql | 10b7fad6634caa9729641545d3c950df2f96e60d532d77b9ae02a4d5a00553bf |
| top_users_by_reputation | arcadedb_sql | True | b1f26ff3a874: arcadedb_sql | b1f26ff3a8744fe79e831869a98460d8099d03ad818c8049db1a4d11eef09ec0 |
| votes_by_type | arcadedb_sql | True | 43e07f73af8b: arcadedb_sql | 43e07f73af8bfc3fdd49a810735bbde0f9ddb428f234ffbddd4e386a1779bd4c |
