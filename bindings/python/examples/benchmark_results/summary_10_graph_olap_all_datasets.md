# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-10T14:58:08Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 10
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:c1db044c71db11c553065dc9fcccfceae444df12210bf352b12bfc18bae68790
  - arcadedb_docker_tag: 26.3.1
  - arcadedb_embedded: auto
  - graphqlite: auto
  - python_memory: builtin
  - real_ladybug: auto
  - sqlite_version: 3.46.1
  - wheel_file: arcadedb_embedded-26.3.1-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.3.1
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-large

### DB summary

| db | run_label | seed | threads | mem_limit | query_runs | query_order | status | exit_code | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| ladybug | sweep10_t01_r01_ladybug_s00000_m8g | 0 | 1 | 8g | 10 | shuffled | success |  | 422.884 | 0 | 96.807 | 5,489.176 | 5,828.965 |
| ladybug | sweep10_t04_r01_ladybug_s00000_m8g | 0 | 4 | 8g | 10 | shuffled | success |  | 356.625 | 0 | 26.637 | 5,458.129 | 5,828.953 |
| ladybug | sweep10_t08_r01_ladybug_s00000_m8g | 0 | 8 | 8g | 10 | shuffled | success |  | 339.706 | 0 | 16.797 | 5,532.594 | 5,829.074 |
| sqlite_native | sweep10_t01_r01_sqlite_native_s00001_m8g | 1 | 1 | 8g | 10 | shuffled | success |  | 229.738 | 0.001 | 123.993 | 1,239.809 | 3,465.574 |
| sqlite_native | sweep10_t04_r01_sqlite_native_s00001_m8g | 1 | 4 | 8g | 10 | shuffled | success |  | 213.838 | 0 | 111.305 | 1,239.883 | 3,465.574 |
| sqlite_native | sweep10_t08_r01_sqlite_native_s00001_m8g | 1 | 8 | 8g | 10 | shuffled | success |  | 215.737 | 0.001 | 111.169 | 1,239.664 | 3,465.574 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| ladybug | 1 | asker_answerer_pairs | 10 | 3,689.376 | 3,805.169 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 10 | 330.7 | 393.269 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 10 | 824.506 | 899.353 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 10 | 713.674 | 793.764 | 10 | True |
| ladybug | 1 | top_answerers | 10 | 135.496 | 191.64 | 10 | True |
| ladybug | 1 | top_askers | 10 | 487.697 | 556.221 | 10 | True |
| ladybug | 1 | top_badges | 10 | 114.571 | 178.455 | 2 | True |
| ladybug | 1 | top_questions_by_score | 10 | 11.27 | 48.069 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 10 | 3,137.794 | 3,259.26 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 10 | 233.08 | 294.335 | 10 | True |
| ladybug | 4 | asker_answerer_pairs | 10 | 1,028.881 | 1,165.236 | 10 | True |
| ladybug | 4 | questions_with_most_answers | 10 | 76.035 | 109.725 | 10 | True |
| ladybug | 4 | tag_cooccurrence | 10 | 216.873 | 246.691 | 10 | True |
| ladybug | 4 | top_accepted_answerers | 10 | 218.43 | 237.655 | 10 | True |
| ladybug | 4 | top_answerers | 10 | 39.351 | 77.018 | 10 | True |
| ladybug | 4 | top_askers | 10 | 151.761 | 191.588 | 10 | True |
| ladybug | 4 | top_badges | 10 | 37.811 | 82.094 | 2 | True |
| ladybug | 4 | top_questions_by_score | 10 | 3.797 | 6.572 | 10 | True |
| ladybug | 4 | top_questions_by_total_comments | 10 | 814.879 | 887.64 | 10 | True |
| ladybug | 4 | top_tags_by_questions | 10 | 72.802 | 102.289 | 10 | True |
| ladybug | 8 | asker_answerer_pairs | 10 | 573.613 | 638.838 | 10 | True |
| ladybug | 8 | questions_with_most_answers | 10 | 54.996 | 77.497 | 10 | True |
| ladybug | 8 | tag_cooccurrence | 10 | 135.732 | 164.998 | 10 | True |
| ladybug | 8 | top_accepted_answerers | 10 | 195.108 | 215.896 | 10 | True |
| ladybug | 8 | top_answerers | 10 | 22.296 | 28.806 | 10 | True |
| ladybug | 8 | top_askers | 10 | 125.348 | 145.8 | 10 | True |
| ladybug | 8 | top_badges | 10 | 21.135 | 44.791 | 2 | True |
| ladybug | 8 | top_questions_by_score | 10 | 3.874 | 8.298 | 10 | True |
| ladybug | 8 | top_questions_by_total_comments | 10 | 500.045 | 552.727 | 10 | True |
| ladybug | 8 | top_tags_by_questions | 10 | 44.956 | 59.771 | 10 | True |
| sqlite_native | 1 | asker_answerer_pairs | 10 | 4,328.865 | 4,650.484 | 10 | True |
| sqlite_native | 1 | questions_with_most_answers | 10 | 143.216 | 151.709 | 10 | True |
| sqlite_native | 1 | tag_cooccurrence | 10 | 2,138.416 | 2,405.425 | 10 | True |
| sqlite_native | 1 | top_accepted_answerers | 10 | 824.501 | 1,005.691 | 10 | True |
| sqlite_native | 1 | top_answerers | 10 | 187.65 | 198.931 | 10 | True |
| sqlite_native | 1 | top_askers | 10 | 137.73 | 150.921 | 10 | True |
| sqlite_native | 1 | top_badges | 10 | 246.737 | 268.06 | 2 | True |
| sqlite_native | 1 | top_questions_by_score | 10 | 415.474 | 469.998 | 10 | True |
| sqlite_native | 1 | top_questions_by_total_comments | 10 | 3,625.928 | 3,887.891 | 10 | True |
| sqlite_native | 1 | top_tags_by_questions | 10 | 77.341 | 85.348 | 10 | True |
| sqlite_native | 4 | asker_answerer_pairs | 10 | 3,675.076 | 3,949.574 | 10 | True |
| sqlite_native | 4 | questions_with_most_answers | 10 | 146.683 | 176.581 | 10 | True |
| sqlite_native | 4 | tag_cooccurrence | 10 | 2,023.366 | 2,125.062 | 10 | True |
| sqlite_native | 4 | top_accepted_answerers | 10 | 655.921 | 725.523 | 10 | True |
| sqlite_native | 4 | top_answerers | 10 | 188.579 | 196.243 | 10 | True |
| sqlite_native | 4 | top_askers | 10 | 133.462 | 142.483 | 10 | True |
| sqlite_native | 4 | top_badges | 10 | 206.662 | 233.038 | 2 | True |
| sqlite_native | 4 | top_questions_by_score | 10 | 392.526 | 452.99 | 10 | True |
| sqlite_native | 4 | top_questions_by_total_comments | 10 | 3,389.559 | 3,665.277 | 10 | True |
| sqlite_native | 4 | top_tags_by_questions | 10 | 76.63 | 90.94 | 10 | True |
| sqlite_native | 8 | asker_answerer_pairs | 10 | 3,649.531 | 3,901.04 | 10 | True |
| sqlite_native | 8 | questions_with_most_answers | 10 | 143.369 | 149.106 | 10 | True |
| sqlite_native | 8 | tag_cooccurrence | 10 | 2,027.874 | 2,211.635 | 10 | True |
| sqlite_native | 8 | top_accepted_answerers | 10 | 682.95 | 784.02 | 10 | True |
| sqlite_native | 8 | top_answerers | 10 | 188.864 | 198.447 | 10 | True |
| sqlite_native | 8 | top_askers | 10 | 133.557 | 138.106 | 10 | True |
| sqlite_native | 8 | top_badges | 10 | 207.102 | 233.49 | 2 | True |
| sqlite_native | 8 | top_questions_by_score | 10 | 409.254 | 470.625 | 10 | True |
| sqlite_native | 8 | top_questions_by_total_comments | 10 | 3,354.416 | 3,516.767 | 10 | True |
| sqlite_native | 8 | top_tags_by_questions | 10 | 79.061 | 85.764 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | row_counts_equal_across_dbs | all_values_equal_across_dbs |
|---|---|---|---|---|
| asker_answerer_pairs | ladybug, sqlite_native | True | True | True |
| questions_with_most_answers | ladybug, sqlite_native | True | True | True |
| tag_cooccurrence | ladybug, sqlite_native | True | True | True |
| top_accepted_answerers | ladybug, sqlite_native | True | True | True |
| top_answerers | ladybug, sqlite_native | True | True | True |
| top_askers | ladybug, sqlite_native | True | True | True |
| top_badges | ladybug, sqlite_native | True | True | True |
| top_questions_by_score | ladybug, sqlite_native | True | True | True |
| top_questions_by_total_comments | ladybug, sqlite_native | True | True | True |
| top_tags_by_questions | ladybug, sqlite_native | True | True | True |

## Dataset: stackoverflow-tiny

### DB summary

| db | run_label | seed | threads | mem_limit | query_runs | query_order | status | exit_code | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_m2g | 0 | 1 | 2g | 10 | shuffled | success |  | 48.647 | 0.536 | 7.042 | 981.855 | 22.059 |
| ladybug | sweep10_t01_r01_ladybug_s00001_m2g | 1 | 1 | 2g | 10 | shuffled | success |  | 5.331 | 0 | 5.688 | 738.137 | 46.734 |
| python_memory | sweep10_t01_r01_python_memory_s00003_m2g | 3 | 1 | 2g | 10 | shuffled | success |  | 0.405 | 0 | 0.764 | 86.973 | 15.434 |
| sqlite_native | sweep10_t01_r01_sqlite_native_s00002_m2g | 2 | 1 | 2g | 10 | shuffled | success |  | 0.565 | 0.001 | 0.346 | 80.746 | 17.742 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 10 | 6.364 | 16.756 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 10 | 72.529 | 109.231 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 10 | 301.521 | 379.852 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 10 | 29.907 | 73.748 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 10 | 56.162 | 102.183 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 10 | 42.229 | 85.134 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 10 | 49.129 | 81.153 | 2 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 10 | 17.933 | 56.035 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 10 | 44.48 | 87.719 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 10 | 76.873 | 95.367 | 10 | True |
| ladybug | 1 | asker_answerer_pairs | 10 | 99.614 | 102.491 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 10 | 40.272 | 95.082 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 10 | 89.108 | 99.439 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 10 | 61.117 | 97.437 | 10 | True |
| ladybug | 1 | top_answerers | 10 | 51.112 | 95.098 | 10 | True |
| ladybug | 1 | top_askers | 10 | 24.422 | 90.368 | 10 | True |
| ladybug | 1 | top_badges | 10 | 81.025 | 95.893 | 2 | True |
| ladybug | 1 | top_questions_by_score | 10 | 1.337 | 2.347 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 10 | 89.526 | 107.032 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 10 | 21.258 | 83.163 | 10 | True |
| python_memory | 1 | asker_answerer_pairs | 10 | 16.761 | 20.64 | 10 | True |
| python_memory | 1 | questions_with_most_answers | 10 | 5.075 | 6.501 | 10 | True |
| python_memory | 1 | tag_cooccurrence | 10 | 14.242 | 18.887 | 10 | True |
| python_memory | 1 | top_accepted_answerers | 10 | 7.629 | 13.112 | 10 | True |
| python_memory | 1 | top_answerers | 10 | 3.96 | 5.168 | 10 | True |
| python_memory | 1 | top_askers | 10 | 3.959 | 5.128 | 10 | True |
| python_memory | 1 | top_badges | 10 | 1.708 | 2.121 | 2 | True |
| python_memory | 1 | top_questions_by_score | 10 | 4.419 | 11.642 | 10 | True |
| python_memory | 1 | top_questions_by_total_comments | 10 | 12.224 | 18.203 | 10 | True |
| python_memory | 1 | top_tags_by_questions | 10 | 4.904 | 7.831 | 10 | True |
| sqlite_native | 1 | asker_answerer_pairs | 10 | 4.225 | 5.814 | 10 | True |
| sqlite_native | 1 | questions_with_most_answers | 10 | 0.654 | 0.867 | 10 | True |
| sqlite_native | 1 | tag_cooccurrence | 10 | 10.606 | 12.622 | 10 | True |
| sqlite_native | 1 | top_accepted_answerers | 10 | 1.762 | 2.05 | 10 | True |
| sqlite_native | 1 | top_answerers | 10 | 1.378 | 1.713 | 10 | True |
| sqlite_native | 1 | top_askers | 10 | 1.634 | 2.236 | 10 | True |
| sqlite_native | 1 | top_badges | 10 | 1.496 | 2.228 | 2 | True |
| sqlite_native | 1 | top_questions_by_score | 10 | 0.974 | 1.379 | 10 | True |
| sqlite_native | 1 | top_questions_by_total_comments | 10 | 8.903 | 10.149 | 10 | True |
| sqlite_native | 1 | top_tags_by_questions | 10 | 0.77 | 1.022 | 10 | True |

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
