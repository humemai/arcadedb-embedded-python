# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-31T09:34:16Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 12
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c386f75daa139e46622b3ab6e7a77baf6ca7e33131cae81936fbe1de4d50d43a
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - duckdb: unknown
  - duckdb_runtime_version: 1.5.1
  - postgresql_version: 18.3
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=12, success=12, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are means across runs in each DB group.
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_mean_s | index_mean_s | query_mean_s | rss_peak_mean_mib | du_mean_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem8g, sweep08_t04_r02_arcadedb_sql_s00004_mem8g, sweep08_t04_r03_arcadedb_sql_s00008_mem8g | 0, 4, 8 | 3 | 10,000 | 8g | 4 | 100 | shuffled | bulk_tuned_insert | 348.526 | 701.22 | 9,280.802 | 6,457.811 | 8,947.771 |
| duckdb | sweep08_t04_r01_duckdb_s00003_mem8g, sweep08_t04_r02_duckdb_s00007_mem8g, sweep08_t04_r03_duckdb_s00011_mem8g | 3, 7, 11 | 3 | 10,000 | 8g | 4 | 100 | shuffled | copy_csv | 407.278 | 0 | 4.049 | 7,433.434 | 17,547.422 |
| postgresql | sweep08_t04_r01_postgresql_s00001_mem8g, sweep08_t04_r02_postgresql_s00005_mem8g, sweep08_t04_r03_postgresql_s00009_mem8g | 1, 5, 9 | 3 | 10,000 | 8g | 4 | 100 | shuffled | copy_from_stdin | 579.422 | 29.34 | 220.825 | 3,461.137 | 16,129.931 |
| sqlite | sweep08_t04_r01_sqlite_s00002_mem8g, sweep08_t04_r02_sqlite_s00006_mem8g, sweep08_t04_r03_sqlite_s00010_mem8g | 2, 6, 10 | 3 | 10,000 | 8g | 4 | 100 | shuffled | executemany | 196.384 | 32.562 | 233.499 | 833.592 | 8,921.934 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 4 | most_commented_posts | 300 | 3,047.175 | 3,962.811 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 300 | 6,806.345 | 9,001.861 | 2 | True |
| arcadedb_sql | 4 | posthistory_by_type | 300 | 66,071.077 | 101,941.274 | 21 | True |
| arcadedb_sql | 4 | postlinks_by_type | 300 | 246.304 | 321.725 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 300 | 4,157.919 | 6,372.511 | 10 | True |
| arcadedb_sql | 4 | top_badges | 300 | 1,112.18 | 1,306.12 | 2 | True |
| arcadedb_sql | 4 | top_questions_by_score | 300 | 2,490.013 | 4,755.235 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 300 | 3.632 | 9.334 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 300 | 720.198 | 888.994 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 300 | 8,152.439 | 8,724.846 | 18 | True |
| duckdb | 4 | most_commented_posts | 300 | 19.855 | 20.826 | 10 | True |
| duckdb | 4 | post_type_counts | 300 | 2.116 | 2.403 | 2 | True |
| duckdb | 4 | posthistory_by_type | 300 | 4.243 | 4.641 | 21 | True |
| duckdb | 4 | postlinks_by_type | 300 | 0.718 | 0.996 | 2 | True |
| duckdb | 4 | top_answers_by_score | 300 | 2.334 | 2.705 | 10 | True |
| duckdb | 4 | top_badges | 300 | 1.324 | 1.566 | 2 | True |
| duckdb | 4 | top_questions_by_score | 300 | 2.141 | 2.503 | 10 | True |
| duckdb | 4 | top_tags_by_count | 300 | 0.345 | 0.572 | 10 | True |
| duckdb | 4 | top_users_by_reputation | 300 | 1.671 | 1.971 | 10 | True |
| duckdb | 4 | votes_by_type | 300 | 5.344 | 5.65 | 18 | True |
| postgresql | 4 | most_commented_posts | 300 | 215.657 | 238.739 | 10 | True |
| postgresql | 4 | post_type_counts | 300 | 64.127 | 72.971 | 2 | True |
| postgresql | 4 | posthistory_by_type | 300 | 1,598.568 | 2,720.494 | 21 | True |
| postgresql | 4 | postlinks_by_type | 300 | 16.639 | 19.752 | 2 | True |
| postgresql | 4 | top_answers_by_score | 300 | 0.207 | 0.303 | 10 | True |
| postgresql | 4 | top_badges | 300 | 72.742 | 101.292 | 2 | True |
| postgresql | 4 | top_questions_by_score | 300 | 0.219 | 0.339 | 10 | True |
| postgresql | 4 | top_tags_by_count | 300 | 0.408 | 0.743 | 10 | True |
| postgresql | 4 | top_users_by_reputation | 300 | 0.293 | 0.892 | 10 | True |
| postgresql | 4 | votes_by_type | 300 | 238.87 | 341.019 | 18 | True |
| sqlite | 4 | most_commented_posts | 300 | 159.186 | 162.831 | 10 | True |
| sqlite | 4 | post_type_counts | 300 | 72.848 | 76.022 | 2 | True |
| sqlite | 4 | posthistory_by_type | 300 | 186.41 | 194.64 | 21 | True |
| sqlite | 4 | postlinks_by_type | 300 | 5.492 | 5.741 | 2 | True |
| sqlite | 4 | top_answers_by_score | 300 | 942.241 | 979.821 | 10 | True |
| sqlite | 4 | top_badges | 300 | 51.06 | 52.945 | 2 | True |
| sqlite | 4 | top_questions_by_score | 300 | 710.576 | 738.698 | 10 | True |
| sqlite | 4 | top_tags_by_count | 300 | 0.133 | 0.147 | 10 | True |
| sqlite | 4 | top_users_by_reputation | 300 | 0.081 | 0.07 | 10 | True |
| sqlite | 4 | votes_by_type | 300 | 206.442 | 217.511 | 18 | True |

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
