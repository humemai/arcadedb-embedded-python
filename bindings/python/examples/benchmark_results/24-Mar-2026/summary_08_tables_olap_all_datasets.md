# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-24T19:19:11Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 2
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:85144b5986b475530a67d95659a93457c9b804e26ac22065af540822670de953
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: unknown
  - postgresql_image: postgres:latest
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Run status files: total=2, success=2, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | runs | batch_size | mem_limit | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb_sql | sweep08_t01_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 1 | 100 | shuffled | bulk_tuned_insert | 720.561 | 1,234.116 | 11,030.042 | 6,915.301 | 8,947.781 |
| arcadedb_sql | sweep08_t04_r01_arcadedb_sql_s00000_mem8g | 0 | 1 | 10,000 | 8g | 4 | 100 | shuffled | bulk_tuned_insert | 377.287 | 1,048.143 | 9,651.969 | 6,429.398 | 8,947.777 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_sql | 1 | most_commented_posts | 100 | 4,309.172 | 4,949.437 | 10 | True |
| arcadedb_sql | 1 | post_type_counts | 100 | 13,128.8 | 15,102.601 | 2 | True |
| arcadedb_sql | 1 | posthistory_by_type | 100 | 70,618.285 | 79,695.749 | 21 | True |
| arcadedb_sql | 1 | postlinks_by_type | 100 | 294.047 | 651.533 | 2 | True |
| arcadedb_sql | 1 | top_answers_by_score | 100 | 6,642.661 | 7,805.609 | 10 | True |
| arcadedb_sql | 1 | top_badges | 100 | 1,174.127 | 1,427.836 | 2 | True |
| arcadedb_sql | 1 | top_questions_by_score | 100 | 4,794.553 | 5,822.564 | 10 | True |
| arcadedb_sql | 1 | top_tags_by_count | 100 | 2.581 | 3.618 | 10 | True |
| arcadedb_sql | 1 | top_users_by_reputation | 100 | 761.452 | 1,030.319 | 10 | True |
| arcadedb_sql | 1 | votes_by_type | 100 | 8,573.784 | 9,265.897 | 18 | True |
| arcadedb_sql | 4 | most_commented_posts | 100 | 3,236.654 | 3,640.694 | 10 | True |
| arcadedb_sql | 4 | post_type_counts | 100 | 7,230.129 | 9,959.105 | 2 | True |
| arcadedb_sql | 4 | posthistory_by_type | 100 | 68,500.096 | 75,802.855 | 21 | True |
| arcadedb_sql | 4 | postlinks_by_type | 100 | 255.067 | 370.243 | 2 | True |
| arcadedb_sql | 4 | top_answers_by_score | 100 | 4,585.064 | 6,654.835 | 10 | True |
| arcadedb_sql | 4 | top_badges | 100 | 1,116.889 | 1,336.027 | 2 | True |
| arcadedb_sql | 4 | top_questions_by_score | 100 | 2,600.877 | 4,577.33 | 10 | True |
| arcadedb_sql | 4 | top_tags_by_count | 100 | 2.722 | 3.344 | 10 | True |
| arcadedb_sql | 4 | top_users_by_reputation | 100 | 743.909 | 898.359 | 10 | True |
| arcadedb_sql | 4 | votes_by_type | 100 | 8,247.036 | 8,841.54 | 18 | True |

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
