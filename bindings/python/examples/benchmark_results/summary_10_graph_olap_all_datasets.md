# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 4
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-small

### DB summary

| db | run_label | seed | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000 | 0 | 1 | 10 | shuffled | 319.458 | 5.993 | 55.278 | 2,408.453 | 289.273 |
| ladybug | sweep10_t01_r01_ladybug_s00001 | 1 | 1 | 10 | shuffled | 28.849 | 0 | 9.102 | 1,489.008 | 428.086 |
| python_memory | sweep10_t01_r01_python_memory_s00003 | 3 | 1 | 10 | shuffled | 8.228 | 0 | 19.499 | 792.941 | 213.645 |
| sqlite_native | sweep10_t01_r01_sqlite_native_s00002 | 2 | 1 | 10 | shuffled | 11.968 | 0.001 | 6.439 | 540.512 | 240.945 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 10 | 66.853 | 138.129 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 10 | 401.001 | 495.294 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 10 | 2,055.131 | 2,400.529 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 10 | 199.026 | 364.881 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 10 | 444.607 | 575.075 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 10 | 567.261 | 920.856 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 10 | 847.046 | 1,280.165 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 10 | 99.791 | 182.489 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 10 | 343.268 | 501.945 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 10 | 501.391 | 704.657 | 10 | True |
| ladybug | 1 | asker_answerer_pairs | 10 | 194.917 | 214.565 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 10 | 33.835 | 84.309 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 10 | 135.373 | 162.301 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 10 | 60.608 | 87.974 | 10 | True |
| ladybug | 1 | top_answerers | 10 | 66.25 | 108.82 | 10 | True |
| ladybug | 1 | top_askers | 10 | 80.528 | 108.364 | 10 | True |
| ladybug | 1 | top_badges | 10 | 117.626 | 136.602 | 10 | True |
| ladybug | 1 | top_questions_by_score | 10 | 11.194 | 47.595 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 10 | 172.555 | 219.989 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 10 | 34.317 | 64.089 | 10 | True |
| python_memory | 1 | asker_answerer_pairs | 10 | 629.519 | 767.89 | 10 | True |
| python_memory | 1 | questions_with_most_answers | 10 | 99.246 | 148.084 | 10 | True |
| python_memory | 1 | tag_cooccurrence | 10 | 322.12 | 417.14 | 10 | True |
| python_memory | 1 | top_accepted_answerers | 10 | 211.836 | 264.268 | 10 | True |
| python_memory | 1 | top_answerers | 10 | 51.066 | 65.09 | 10 | True |
| python_memory | 1 | top_askers | 10 | 128.578 | 222.121 | 10 | True |
| python_memory | 1 | top_badges | 10 | 103.159 | 134.151 | 10 | True |
| python_memory | 1 | top_questions_by_score | 10 | 70.998 | 130.518 | 10 | True |
| python_memory | 1 | top_questions_by_total_comments | 10 | 264.96 | 352.085 | 10 | True |
| python_memory | 1 | top_tags_by_questions | 10 | 65.552 | 83.211 | 10 | True |
| sqlite_native | 1 | asker_answerer_pairs | 10 | 63.104 | 87.665 | 10 | True |
| sqlite_native | 1 | questions_with_most_answers | 10 | 8.094 | 11.834 | 10 | True |
| sqlite_native | 1 | tag_cooccurrence | 10 | 178.586 | 250.613 | 10 | True |
| sqlite_native | 1 | top_accepted_answerers | 10 | 30.127 | 41.632 | 10 | True |
| sqlite_native | 1 | top_answerers | 10 | 21.145 | 30.745 | 10 | True |
| sqlite_native | 1 | top_askers | 10 | 27.19 | 38.215 | 10 | True |
| sqlite_native | 1 | top_badges | 10 | 97.938 | 132.516 | 10 | True |
| sqlite_native | 1 | top_questions_by_score | 10 | 12.224 | 16.054 | 10 | True |
| sqlite_native | 1 | top_questions_by_total_comments | 10 | 168.754 | 232.31 | 10 | True |
| sqlite_native | 1 | top_tags_by_questions | 10 | 8.499 | 13.221 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | row_counts_equal_across_dbs | all_values_equal_across_dbs |
|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher, ladybug, python_memory, sqlite_native | False | False | False |
| questions_with_most_answers | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| tag_cooccurrence | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| top_accepted_answerers | arcadedb_cypher, ladybug, python_memory, sqlite_native | False | False | False |
| top_answerers | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| top_askers | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| top_badges | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| top_questions_by_score | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
| top_questions_by_total_comments | arcadedb_cypher, ladybug, python_memory, sqlite_native | False | True | False |
| top_tags_by_questions | arcadedb_cypher, ladybug, python_memory, sqlite_native | True | True | True |
