# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-04T21:00:03Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 4
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:3f359ca6b9a9b4fde4cfda499cd6951e802a6aae6e930134f1aaf3f664184696
  - arcadedb_docker_tag: 26.3.1-SNAPSHOT
  - arcadedb_embedded: 26.3.1.dev0
  - graphqlite: 0.3.7
  - python_memory: builtin
  - real_ladybug: 0.15.1
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1.dev0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000 | 0 | 1 | 10 | shuffled | 1,034.695 | 15.58 | 158.432 | 8,178.223 | 1,242.996 |
| ladybug | sweep10_t01_r01_ladybug_s00001 | 1 | 1 | 10 | shuffled | 99.995 | 0 | 25.366 | 2,886.656 | 1,818.688 |
| python_memory | sweep10_t01_r01_python_memory_s00003 | 3 | 1 | 10 | shuffled | 33.652 | 0 | 80.396 | 2,985.535 | 942.699 |
| sqlite_native | sweep10_t01_r01_sqlite_native_s00002 | 2 | 1 | 10 | shuffled | 40.109 | 0.001 | 31.677 | 751.68 | 1,079.73 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 10 | 157.794 | 231.148 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 10 | 1,097.402 | 1,748.383 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 10 | 7,896.043 | 8,479.679 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 10 | 520.544 | 960.075 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 10 | 944.897 | 1,338.54 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 10 | 1,120.04 | 1,351.959 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 10 | 1,640.131 | 2,084.902 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 10 | 248.741 | 337.7 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 10 | 878.947 | 1,228.091 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 10 | 1,336.75 | 1,438.751 | 10 | True |
| ladybug | 1 | asker_answerer_pairs | 10 | 497.998 | 508.775 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 10 | 175.854 | 195.119 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 10 | 414.717 | 483.679 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 10 | 119.905 | 161.001 | 10 | True |
| ladybug | 1 | top_answerers | 10 | 169.973 | 203.624 | 10 | True |
| ladybug | 1 | top_askers | 10 | 207.577 | 244.386 | 10 | True |
| ladybug | 1 | top_badges | 10 | 245.548 | 284.199 | 10 | True |
| ladybug | 1 | top_questions_by_score | 10 | 2.342 | 2.677 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 10 | 591.697 | 600.493 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 10 | 108.153 | 130.668 | 10 | True |
| python_memory | 1 | asker_answerer_pairs | 10 | 2,954.243 | 3,192.896 | 10 | True |
| python_memory | 1 | questions_with_most_answers | 10 | 285.562 | 325.039 | 10 | True |
| python_memory | 1 | tag_cooccurrence | 10 | 1,545.324 | 1,658.644 | 10 | True |
| python_memory | 1 | top_accepted_answerers | 10 | 1,367.105 | 1,739.381 | 10 | True |
| python_memory | 1 | top_answerers | 10 | 157.831 | 183.387 | 10 | True |
| python_memory | 1 | top_askers | 10 | 282.325 | 297.972 | 10 | True |
| python_memory | 1 | top_badges | 10 | 220.153 | 242.497 | 10 | True |
| python_memory | 1 | top_questions_by_score | 10 | 174.963 | 197.505 | 10 | True |
| python_memory | 1 | top_questions_by_total_comments | 10 | 838.745 | 917.216 | 10 | True |
| python_memory | 1 | top_tags_by_questions | 10 | 210.864 | 224.178 | 10 | True |
| sqlite_native | 1 | asker_answerer_pairs | 10 | 247.044 | 258.067 | 10 | True |
| sqlite_native | 1 | questions_with_most_answers | 10 | 22.858 | 23.921 | 10 | True |
| sqlite_native | 1 | tag_cooccurrence | 10 | 1,118.195 | 1,157.286 | 10 | True |
| sqlite_native | 1 | top_accepted_answerers | 10 | 81.741 | 82.688 | 10 | True |
| sqlite_native | 1 | top_answerers | 10 | 55.332 | 57.641 | 10 | True |
| sqlite_native | 1 | top_askers | 10 | 70.055 | 72.47 | 10 | True |
| sqlite_native | 1 | top_badges | 10 | 392.635 | 468.545 | 10 | True |
| sqlite_native | 1 | top_questions_by_score | 10 | 102.334 | 110.098 | 10 | True |
| sqlite_native | 1 | top_questions_by_total_comments | 10 | 869.386 | 905.728 | 10 | True |
| sqlite_native | 1 | top_tags_by_questions | 10 | 33.12 | 36.866 | 10 | True |

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
