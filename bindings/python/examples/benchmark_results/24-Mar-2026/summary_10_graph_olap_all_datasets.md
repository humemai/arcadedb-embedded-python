# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-24T19:19:11Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 2
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:85144b5986b475530a67d95659a93457c9b804e26ac22065af540822670de953
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - python_memory: builtin
  - sqlite: builtin
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 1 | 100 | shuffled | 6,035.364 | 131.903 | 2,846.361 | 29,819.965 | 3,968.629 |
| arcadedb_cypher | sweep10_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 4 | 100 | shuffled | 3,738.254 | 115.099 | 2,098.662 | 25,973.844 | 12,750.77 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 4,027.705 | 4,230.53 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 1,889.474 | 2,017.994 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 11,367.838 | 11,754.523 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 4,031.48 | 4,324.977 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 1,155.683 | 1,248.01 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 1,067.739 | 1,151.224 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 670.552 | 709.973 | 0 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 699.242 | 733.924 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 3,551.651 | 3,889.342 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 0.88 | 0.958 | 0 | True |
| arcadedb_cypher | 4 | asker_answerer_pairs | 100 | 3,131.653 | 3,209.974 | 0 | True |
| arcadedb_cypher | 4 | questions_with_most_answers | 100 | 1,435.359 | 1,507.922 | 10 | True |
| arcadedb_cypher | 4 | tag_cooccurrence | 100 | 8,088.039 | 8,185.128 | 10 | True |
| arcadedb_cypher | 4 | top_accepted_answerers | 100 | 3,126.136 | 3,289.146 | 0 | True |
| arcadedb_cypher | 4 | top_answerers | 100 | 816.687 | 837.656 | 10 | True |
| arcadedb_cypher | 4 | top_askers | 100 | 705.765 | 714.381 | 10 | True |
| arcadedb_cypher | 4 | top_badges | 100 | 560.631 | 567.077 | 0 | True |
| arcadedb_cypher | 4 | top_questions_by_score | 100 | 584.123 | 593.34 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_total_comments | 100 | 2,536.068 | 2,626.582 | 10 | True |
| arcadedb_cypher | 4 | top_tags_by_questions | 100 | 0.86 | 0.964 | 0 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| questions_with_most_answers | arcadedb_cypher | True | 0c1ff04cbc6b: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| tag_cooccurrence | arcadedb_cypher | True | 9fdd63bd0adb: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_accepted_answerers | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_answerers | arcadedb_cypher | True | d12124838677: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_askers | arcadedb_cypher | True | 0644552cf9d3: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_badges | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_questions_by_score | arcadedb_cypher | True | 667618012867: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_questions_by_total_comments | arcadedb_cypher | True | 92aaf16b0aca: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_tags_by_questions | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
