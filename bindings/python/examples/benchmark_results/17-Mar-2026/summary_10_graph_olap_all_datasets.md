# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-13T16:19:53Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 26
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:08c19266ac0fee12e891534141ccc1e9ae6a493d3b69479feaad1261218395c4, arcadedata/arcadedb@sha256:2b886906f2c10f831a56eaedbb8f3b5350fb7bf0940dcb2561dc34a260fbf3b9, arcadedata/arcadedb@sha256:bbd01ef59b1ea40c5af89171a48ab699ddf3b26e192cd92404539a62b447c585, ... (+1 more)
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: auto
  - duckdb: auto
  - graphqlite: auto
  - python_memory: builtin
  - real_ladybug: auto
  - sqlite_version: 3.46.1
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
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 1 | 100 | shuffled | 6,787.391 | 175.501 | 3,976.375 | 30,332.566 | 4,039.594 |
| arcadedb_cypher | sweep10_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 4 | 100 | shuffled | 7,420.009 | 148.152 | 4,679.181 | 14,860.934 | 4,039.594 |
| arcadedb_cypher | sweep10_t08_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 8 | 100 | shuffled | 6,149.502 | 128.021 | 4,003.029 | 14,603.973 | 4,039.586 |
| duckdb | sweep10_t01_r01_duckdb_s00000_mem8g | 0 | 10,000 | 8g | 1 | 100 | shuffled | 345.179 | 0 | 146.277 | 3,556.844 | 6,837.289 |
| duckdb | sweep10_t04_r01_duckdb_s00000_mem8g | 0 | 10,000 | 8g | 4 | 100 | shuffled | 341.622 | 0 | 54.812 | 4,303.328 | 6,833.793 |
| duckdb | sweep10_t08_r01_duckdb_s00000_mem8g | 0 | 10,000 | 8g | 8 | 100 | shuffled | 410.947 | 0 | 43.968 | 4,315.812 | 6,832.289 |
| ladybug | sweep10_t01_r01_ladybug_s00002_mem8g | 2 | 10,000 | 8g | 1 | 100 | shuffled | 477.448 | 0 | 919.989 | 5,561.555 | 5,828.738 |
| ladybug | sweep10_t04_r01_ladybug_s00002_mem8g | 2 | 10,000 | 8g | 4 | 100 | shuffled | 401.242 | 0 | 250.289 | 5,563.523 | 5,829.312 |
| ladybug | sweep10_t08_r01_ladybug_s00002_mem8g | 2 | 10,000 | 8g | 8 | 100 | shuffled | 422.852 | 0 | 139.157 | 5,428.852 | 5,828.918 |
| python_memory | sweep10_t01_r01_python_memory_s00000_mem16g | 0 | 10,000 | 16g | 1 | 100 | shuffled | 186.921 | 0 | 6,175.329 | 10,109.664 | 3,029.844 |
| sqlite | sweep10_t01_r01_sqlite_s00000_mem8g | 0 | 10,000 | 8g | 1 | 100 | shuffled | 246.934 | 0.001 | 1,185.689 | 1,240.238 | 3,465.602 |
| sqlite | sweep10_t04_r01_sqlite_s00000_mem8g | 0 | 10,000 | 8g | 4 | 100 | shuffled | 262.08 | 0.001 | 1,118.734 | 1,240.004 | 3,465.602 |
| sqlite | sweep10_t08_r01_sqlite_s00001_mem8g | 1 | 10,000 | 8g | 8 | 100 | shuffled | 257.276 | 0.001 | 1,174.008 | 1,240.457 | 3,465.605 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 4,704.574 | 5,002.339 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 4,732.371 | 5,156.878 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 12,451.42 | 13,253.775 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 1,810.616 | 1,903.213 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 5,102.459 | 5,490.737 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 2,486.447 | 2,835.964 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 1,394.189 | 1,488.587 | 2 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 669.876 | 701.523 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 3,176.158 | 3,621.033 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 3,234.12 | 3,389.384 | 10 | True |
| arcadedb_cypher | 4 | asker_answerer_pairs | 100 | 5,834.832 | 6,278.873 | 0 | True |
| arcadedb_cypher | 4 | questions_with_most_answers | 100 | 5,631.164 | 5,945.659 | 10 | True |
| arcadedb_cypher | 4 | tag_cooccurrence | 100 | 14,143.308 | 14,920.956 | 10 | True |
| arcadedb_cypher | 4 | top_accepted_answerers | 100 | 2,230.72 | 2,450.635 | 0 | True |
| arcadedb_cypher | 4 | top_answerers | 100 | 5,985.404 | 6,335.555 | 10 | True |
| arcadedb_cypher | 4 | top_askers | 100 | 3,057.768 | 3,413.892 | 10 | True |
| arcadedb_cypher | 4 | top_badges | 100 | 1,757.74 | 1,923.258 | 2 | True |
| arcadedb_cypher | 4 | top_questions_by_score | 100 | 848.515 | 931.731 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_total_comments | 100 | 3,473.395 | 3,770.251 | 10 | True |
| arcadedb_cypher | 4 | top_tags_by_questions | 100 | 3,827.069 | 4,084.797 | 10 | True |
| arcadedb_cypher | 8 | asker_answerer_pairs | 100 | 4,909.037 | 5,399.312 | 0 | True |
| arcadedb_cypher | 8 | questions_with_most_answers | 100 | 4,682.665 | 5,013.522 | 10 | True |
| arcadedb_cypher | 8 | tag_cooccurrence | 100 | 12,541.491 | 13,110.035 | 10 | True |
| arcadedb_cypher | 8 | top_accepted_answerers | 100 | 1,932.125 | 2,134.097 | 0 | True |
| arcadedb_cypher | 8 | top_answerers | 100 | 4,916.951 | 5,552.5 | 10 | True |
| arcadedb_cypher | 8 | top_askers | 100 | 2,513.668 | 2,851.411 | 10 | True |
| arcadedb_cypher | 8 | top_badges | 100 | 1,480.256 | 1,631.099 | 2 | True |
| arcadedb_cypher | 8 | top_questions_by_score | 100 | 752.444 | 829.183 | 10 | True |
| arcadedb_cypher | 8 | top_questions_by_total_comments | 100 | 2,967.125 | 3,131.108 | 10 | True |
| arcadedb_cypher | 8 | top_tags_by_questions | 100 | 3,332.868 | 3,545.187 | 10 | True |
| duckdb | 1 | asker_answerer_pairs | 100 | 362.235 | 419.004 | 10 | True |
| duckdb | 1 | questions_with_most_answers | 100 | 66.244 | 81.883 | 10 | True |
| duckdb | 1 | tag_cooccurrence | 100 | 145.841 | 162.783 | 10 | True |
| duckdb | 1 | top_accepted_answerers | 100 | 110.487 | 123.667 | 10 | True |
| duckdb | 1 | top_answerers | 100 | 127.521 | 150.295 | 10 | True |
| duckdb | 1 | top_askers | 100 | 68.075 | 80.813 | 10 | True |
| duckdb | 1 | top_badges | 100 | 32.734 | 42.999 | 2 | True |
| duckdb | 1 | top_questions_by_score | 100 | 1.779 | 2.003 | 10 | True |
| duckdb | 1 | top_questions_by_total_comments | 100 | 532.094 | 607.697 | 10 | True |
| duckdb | 1 | top_tags_by_questions | 100 | 14.147 | 15.575 | 10 | True |
| duckdb | 4 | asker_answerer_pairs | 100 | 98.54 | 109.723 | 10 | True |
| duckdb | 4 | questions_with_most_answers | 100 | 19.8 | 21.954 | 10 | True |
| duckdb | 4 | tag_cooccurrence | 100 | 53.581 | 60.358 | 10 | True |
| duckdb | 4 | top_accepted_answerers | 100 | 63.005 | 72.259 | 10 | True |
| duckdb | 4 | top_answerers | 100 | 61.792 | 72.208 | 10 | True |
| duckdb | 4 | top_askers | 100 | 48.527 | 53.866 | 10 | True |
| duckdb | 4 | top_badges | 100 | 15.795 | 20.414 | 2 | True |
| duckdb | 4 | top_questions_by_score | 100 | 1.117 | 1.487 | 10 | True |
| duckdb | 4 | top_questions_by_total_comments | 100 | 175.035 | 203.305 | 10 | True |
| duckdb | 4 | top_tags_by_questions | 100 | 9.193 | 10.67 | 10 | True |
| duckdb | 8 | asker_answerer_pairs | 100 | 73.03 | 103.369 | 10 | True |
| duckdb | 8 | questions_with_most_answers | 100 | 12.645 | 18.244 | 10 | True |
| duckdb | 8 | tag_cooccurrence | 100 | 39.611 | 59.585 | 10 | True |
| duckdb | 8 | top_accepted_answerers | 100 | 60.443 | 82.911 | 10 | True |
| duckdb | 8 | top_answerers | 100 | 46.439 | 69.878 | 10 | True |
| duckdb | 8 | top_askers | 100 | 48.765 | 57.507 | 10 | True |
| duckdb | 8 | top_badges | 100 | 14.317 | 22.993 | 2 | True |
| duckdb | 8 | top_questions_by_score | 100 | 1.342 | 2.567 | 10 | True |
| duckdb | 8 | top_questions_by_total_comments | 100 | 134.446 | 174.114 | 10 | True |
| duckdb | 8 | top_tags_by_questions | 100 | 6.578 | 8.152 | 10 | True |
| ladybug | 1 | asker_answerer_pairs | 100 | 3,381.674 | 3,712.743 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 100 | 317.202 | 395.147 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 100 | 784.725 | 893.524 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 100 | 685.836 | 804.56 | 10 | True |
| ladybug | 1 | top_answerers | 100 | 158.2 | 199.822 | 10 | True |
| ladybug | 1 | top_askers | 100 | 495.145 | 595.924 | 10 | True |
| ladybug | 1 | top_badges | 100 | 115.986 | 187.594 | 2 | True |
| ladybug | 1 | top_questions_by_score | 100 | 20.245 | 89.217 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 100 | 3,022.714 | 3,299.951 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 100 | 212.97 | 286.863 | 10 | True |
| ladybug | 4 | asker_answerer_pairs | 100 | 934.314 | 1,069.926 | 10 | True |
| ladybug | 4 | questions_with_most_answers | 100 | 84.337 | 110.962 | 10 | True |
| ladybug | 4 | tag_cooccurrence | 100 | 202.335 | 239.643 | 10 | True |
| ladybug | 4 | top_accepted_answerers | 100 | 192.729 | 242.001 | 10 | True |
| ladybug | 4 | top_answerers | 100 | 44.481 | 93.104 | 10 | True |
| ladybug | 4 | top_askers | 100 | 137.198 | 183.635 | 10 | True |
| ladybug | 4 | top_badges | 100 | 33.437 | 87.237 | 2 | True |
| ladybug | 4 | top_questions_by_score | 100 | 5.797 | 15.475 | 10 | True |
| ladybug | 4 | top_questions_by_total_comments | 100 | 805.587 | 894.762 | 10 | True |
| ladybug | 4 | top_tags_by_questions | 100 | 59.998 | 105.136 | 10 | True |
| ladybug | 8 | asker_answerer_pairs | 100 | 472.376 | 537.14 | 10 | True |
| ladybug | 8 | questions_with_most_answers | 100 | 47.366 | 80.388 | 10 | True |
| ladybug | 8 | tag_cooccurrence | 100 | 118.503 | 154.167 | 10 | True |
| ladybug | 8 | top_accepted_answerers | 100 | 150.916 | 189.656 | 10 | True |
| ladybug | 8 | top_answerers | 100 | 23.381 | 33.595 | 10 | True |
| ladybug | 8 | top_askers | 100 | 100.382 | 132.073 | 10 | True |
| ladybug | 8 | top_badges | 100 | 15.689 | 23.376 | 2 | True |
| ladybug | 8 | top_questions_by_score | 100 | 2.748 | 3.171 | 10 | True |
| ladybug | 8 | top_questions_by_total_comments | 100 | 415.67 | 476.065 | 10 | True |
| ladybug | 8 | top_tags_by_questions | 100 | 42.202 | 80.68 | 10 | True |
| python_memory | 1 | asker_answerer_pairs | 100 | 25,706.709 | 35,047.955 | 10 | True |
| python_memory | 1 | questions_with_most_answers | 100 | 2,442.184 | 2,924.105 | 10 | True |
| python_memory | 1 | tag_cooccurrence | 100 | 8,066.861 | 12,129.591 | 10 | True |
| python_memory | 1 | top_accepted_answerers | 100 | 16,579.88 | 23,413.476 | 10 | True |
| python_memory | 1 | top_answerers | 100 | 1,404.345 | 1,758.421 | 10 | True |
| python_memory | 1 | top_askers | 100 | 945.792 | 1,149.763 | 10 | True |
| python_memory | 1 | top_badges | 100 | 247.863 | 343.443 | 2 | True |
| python_memory | 1 | top_questions_by_score | 100 | 1,095.483 | 1,292.182 | 10 | True |
| python_memory | 1 | top_questions_by_total_comments | 100 | 4,486.047 | 5,548.268 | 10 | True |
| python_memory | 1 | top_tags_by_questions | 100 | 774.738 | 937.616 | 10 | True |
| sqlite | 1 | asker_answerer_pairs | 100 | 3,956.408 | 4,296.968 | 10 | True |
| sqlite | 1 | questions_with_most_answers | 100 | 144.478 | 167.464 | 10 | True |
| sqlite | 1 | tag_cooccurrence | 100 | 2,100.622 | 2,342.581 | 10 | True |
| sqlite | 1 | top_accepted_answerers | 100 | 723.769 | 870.408 | 10 | True |
| sqlite | 1 | top_answerers | 100 | 194.776 | 213.631 | 10 | True |
| sqlite | 1 | top_askers | 100 | 136.131 | 153.251 | 10 | True |
| sqlite | 1 | top_badges | 100 | 227.592 | 274.039 | 2 | True |
| sqlite | 1 | top_questions_by_score | 100 | 446.04 | 547.499 | 10 | True |
| sqlite | 1 | top_questions_by_total_comments | 100 | 3,586.197 | 3,855.379 | 10 | True |
| sqlite | 1 | top_tags_by_questions | 100 | 76.265 | 87.775 | 10 | True |
| sqlite | 4 | asker_answerer_pairs | 100 | 3,650.944 | 4,127.193 | 10 | True |
| sqlite | 4 | questions_with_most_answers | 100 | 141.352 | 164.163 | 10 | True |
| sqlite | 4 | tag_cooccurrence | 100 | 1,993.848 | 2,190.517 | 10 | True |
| sqlite | 4 | top_accepted_answerers | 100 | 699.89 | 820.428 | 10 | True |
| sqlite | 4 | top_answerers | 100 | 192.643 | 213.904 | 10 | True |
| sqlite | 4 | top_askers | 100 | 136.381 | 154.425 | 10 | True |
| sqlite | 4 | top_badges | 100 | 211.758 | 260.84 | 2 | True |
| sqlite | 4 | top_questions_by_score | 100 | 413.36 | 491.69 | 10 | True |
| sqlite | 4 | top_questions_by_total_comments | 100 | 3,433.281 | 3,742.345 | 10 | True |
| sqlite | 4 | top_tags_by_questions | 100 | 75.767 | 88.79 | 10 | True |
| sqlite | 8 | asker_answerer_pairs | 100 | 3,929.134 | 4,260.731 | 10 | True |
| sqlite | 8 | questions_with_most_answers | 100 | 142.029 | 157.785 | 10 | True |
| sqlite | 8 | tag_cooccurrence | 100 | 2,069.355 | 2,248.273 | 10 | True |
| sqlite | 8 | top_accepted_answerers | 100 | 716.769 | 841.959 | 10 | True |
| sqlite | 8 | top_answerers | 100 | 192.299 | 210.058 | 10 | True |
| sqlite | 8 | top_askers | 100 | 136.274 | 149.56 | 10 | True |
| sqlite | 8 | top_badges | 100 | 222.047 | 269.206 | 2 | True |
| sqlite | 8 | top_questions_by_score | 100 | 444.419 | 520.537 | 10 | True |
| sqlite | 8 | top_questions_by_total_comments | 100 | 3,550.1 | 3,775.628 | 10 | True |
| sqlite | 8 | top_tags_by_questions | 100 | 75.941 | 83.488 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 4f53cda18c2b: arcadedb_cypher; 50d35827e6c2: duckdb, ladybug, python_memory, sqlite | False | 0: arcadedb_cypher; 10: duckdb, ladybug, python_memory, sqlite | False |
| questions_with_most_answers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 0c1ff04cbc6b: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| tag_cooccurrence | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 9fdd63bd0adb: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_accepted_answerers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 4f53cda18c2b: arcadedb_cypher; 9a51a5e270a7: duckdb, ladybug, python_memory, sqlite | False | 0: arcadedb_cypher; 10: duckdb, ladybug, python_memory, sqlite | False |
| top_answerers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | d12124838677: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_askers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 0644552cf9d3: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_badges | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | e26bf9c71f40: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 2: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_questions_by_score | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 667618012867: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_questions_by_total_comments | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 92aaf16b0aca: arcadedb_cypher; a30c1e9e125b: duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False |
| top_tags_by_questions | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 280ede11e63d: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |

### Cross-DB mismatches only

| query | majority_hash_dbs | differing_hash_dbs | majority_row_count_dbs | differing_row_count_dbs |
|---|---|---|---|---|
| asker_answerer_pairs | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher |
| top_accepted_answerers | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher |
| top_questions_by_total_comments | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | none |

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_mem8g | 0 | 5,000 | 8g | 1 | 100 | shuffled | 1,368.763 | 17.519 | 1,481.209 | 8,048.605 |  |
| arcadedb_cypher | sweep10_t04_r01_arcadedb_cypher_s00000_mem8g | 0 | 5,000 | 8g | 4 | 100 | shuffled | 1,244.19 | 11.243 | 1,312.03 | 5,875.602 |  |
| duckdb | sweep10_t01_r01_duckdb_s00000_mem4g | 0 | 5,000 | 4g | 1 | 100 | shuffled | 95.507 | 0 | 31.761 | 1,317.355 | 1,961.957 |
| duckdb | sweep10_t01_r01_duckdb_s00000_mem8g | 0 | 10,000 | 8g | 1 | 100 | shuffled | 82.54 | 0 | 32.258 | 1,391.656 | 1,962.203 |
| duckdb | sweep10_t04_r01_duckdb_s00000_mem4g | 0 | 5,000 | 4g | 4 | 100 | shuffled | 86.968 | 0 | 18.851 | 1,445.141 | 1,962.699 |
| ladybug | sweep10_t01_r01_ladybug_s00000_mem4g | 0 | 5,000 | 4g | 1 | 100 | shuffled | 105.383 | 0 | 288.42 | 2,902.891 | 1,818.285 |
| ladybug | sweep10_t04_r01_ladybug_s00000_mem4g | 0 | 5,000 | 4g | 4 | 100 | shuffled | 90.657 | 0 | 98.664 | 2,888.902 | 1,818.309 |
| python_memory | sweep10_t01_r01_python_memory_s00000_mem4g | 0 | 5,000 | 4g | 1 | 100 | shuffled | 34.663 | 0 | 908.991 | 2,986.238 | 942.723 |
| python_memory | sweep10_t04_r01_python_memory_s00000_mem4g | 0 | 5,000 | 4g | 4 | 100 | shuffled | 36.313 | 0 | 901.499 | 2,985.785 | 942.723 |
| sqlite | sweep10_t01_r01_sqlite_s00000_mem4g | 0 | 5,000 | 4g | 1 | 100 | shuffled | 55.976 | 0.001 | 403.322 | 639.988 | 1,107.266 |
| sqlite | sweep10_t04_r01_sqlite_s00000_mem4g | 0 | 5,000 | 4g | 4 | 100 | shuffled | 58.716 | 0.001 | 406.361 | 639.77 | 1,107.266 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 1,005.428 | 1,321.791 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 767.147 | 934.572 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 7,169.257 | 8,646.703 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 398.245 | 495.585 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 803.758 | 987.781 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 996.456 | 1,318.482 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 1,449.631 | 1,842.025 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 245.777 | 390.797 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 703.887 | 891.046 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 1,270.833 | 1,551.356 | 10 | True |
| arcadedb_cypher | 4 | asker_answerer_pairs | 100 | 941.234 | 1,141.648 | 0 | True |
| arcadedb_cypher | 4 | questions_with_most_answers | 100 | 691.916 | 832.178 | 10 | True |
| arcadedb_cypher | 4 | tag_cooccurrence | 100 | 6,156.995 | 7,346.238 | 10 | True |
| arcadedb_cypher | 4 | top_accepted_answerers | 100 | 377.747 | 456.954 | 0 | True |
| arcadedb_cypher | 4 | top_answerers | 100 | 725.966 | 893.803 | 10 | True |
| arcadedb_cypher | 4 | top_askers | 100 | 820.627 | 999.587 | 10 | True |
| arcadedb_cypher | 4 | top_badges | 100 | 1,416.212 | 1,740.949 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_score | 100 | 194.304 | 235.843 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_total_comments | 100 | 592.394 | 706.144 | 10 | True |
| arcadedb_cypher | 4 | top_tags_by_questions | 100 | 1,201.224 | 1,443.034 | 10 | True |
| duckdb | 1 | asker_answerer_pairs | 200 | 27.374 | 33.583 | 10 | True |
| duckdb | 1 | questions_with_most_answers | 200 | 5.09 | 6.294 | 10 | True |
| duckdb | 1 | tag_cooccurrence | 200 | 87.633 | 102.91 | 10 | True |
| duckdb | 1 | top_accepted_answerers | 200 | 16.14 | 18.716 | 10 | True |
| duckdb | 1 | top_answerers | 200 | 23.401 | 28.234 | 10 | True |
| duckdb | 1 | top_askers | 200 | 28.086 | 33.637 | 10 | True |
| duckdb | 1 | top_badges | 200 | 15.528 | 18.311 | 10 | True |
| duckdb | 1 | top_questions_by_score | 200 | 0.992 | 1.277 | 10 | True |
| duckdb | 1 | top_questions_by_total_comments | 200 | 104.555 | 129.434 | 10 | True |
| duckdb | 1 | top_tags_by_questions | 200 | 9.529 | 10.467 | 10 | True |
| duckdb | 4 | asker_answerer_pairs | 100 | 20.401 | 25.094 | 10 | True |
| duckdb | 4 | questions_with_most_answers | 100 | 5.506 | 6.489 | 10 | True |
| duckdb | 4 | tag_cooccurrence | 100 | 50.058 | 56.217 | 10 | True |
| duckdb | 4 | top_accepted_answerers | 100 | 11.202 | 13.754 | 10 | True |
| duckdb | 4 | top_answerers | 100 | 17.385 | 21.446 | 10 | True |
| duckdb | 4 | top_askers | 100 | 18.766 | 23.12 | 10 | True |
| duckdb | 4 | top_badges | 100 | 10.148 | 12.167 | 10 | True |
| duckdb | 4 | top_questions_by_score | 100 | 1.069 | 1.594 | 10 | True |
| duckdb | 4 | top_questions_by_total_comments | 100 | 45.119 | 54.825 | 10 | True |
| duckdb | 4 | top_tags_by_questions | 100 | 6.912 | 7.907 | 10 | True |
| ladybug | 1 | asker_answerer_pairs | 100 | 565.755 | 688.34 | 10 | True |
| ladybug | 1 | questions_with_most_answers | 100 | 201.815 | 279.619 | 10 | True |
| ladybug | 1 | tag_cooccurrence | 100 | 487.159 | 505.077 | 10 | True |
| ladybug | 1 | top_accepted_answerers | 100 | 145.69 | 199.155 | 10 | True |
| ladybug | 1 | top_answerers | 100 | 196.686 | 265.618 | 10 | True |
| ladybug | 1 | top_askers | 100 | 230.347 | 296.967 | 10 | True |
| ladybug | 1 | top_badges | 100 | 253.805 | 315.471 | 10 | True |
| ladybug | 1 | top_questions_by_score | 100 | 6.058 | 54.855 | 10 | True |
| ladybug | 1 | top_questions_by_total_comments | 100 | 678.884 | 790.546 | 10 | True |
| ladybug | 1 | top_tags_by_questions | 100 | 114.418 | 168.706 | 10 | True |
| ladybug | 4 | asker_answerer_pairs | 100 | 234.84 | 274.182 | 10 | True |
| ladybug | 4 | questions_with_most_answers | 100 | 82.692 | 103.898 | 10 | True |
| ladybug | 4 | tag_cooccurrence | 100 | 180.238 | 203.086 | 10 | True |
| ladybug | 4 | top_accepted_answerers | 100 | 38.409 | 49.76 | 10 | True |
| ladybug | 4 | top_answerers | 100 | 64.755 | 80.395 | 10 | True |
| ladybug | 4 | top_askers | 100 | 73.057 | 93.2 | 10 | True |
| ladybug | 4 | top_badges | 100 | 99.584 | 121.435 | 10 | True |
| ladybug | 4 | top_questions_by_score | 100 | 2.413 | 3.287 | 10 | True |
| ladybug | 4 | top_questions_by_total_comments | 100 | 166.575 | 211.279 | 10 | True |
| ladybug | 4 | top_tags_by_questions | 100 | 41.357 | 45.75 | 10 | True |
| python_memory | 1 | asker_answerer_pairs | 100 | 3,366.727 | 5,174.312 | 10 | True |
| python_memory | 1 | questions_with_most_answers | 100 | 320.645 | 475.012 | 10 | True |
| python_memory | 1 | tag_cooccurrence | 100 | 1,740.297 | 2,727.788 | 10 | True |
| python_memory | 1 | top_accepted_answerers | 100 | 1,548.61 | 2,438.059 | 10 | True |
| python_memory | 1 | top_answerers | 100 | 181.066 | 291.63 | 10 | True |
| python_memory | 1 | top_askers | 100 | 332.461 | 456.847 | 10 | True |
| python_memory | 1 | top_badges | 100 | 243.589 | 410.679 | 10 | True |
| python_memory | 1 | top_questions_by_score | 100 | 199.408 | 281.208 | 10 | True |
| python_memory | 1 | top_questions_by_total_comments | 100 | 916.68 | 1,427.58 | 10 | True |
| python_memory | 1 | top_tags_by_questions | 100 | 238.054 | 367.387 | 10 | True |
| python_memory | 4 | asker_answerer_pairs | 100 | 3,342.952 | 4,964.254 | 10 | True |
| python_memory | 4 | questions_with_most_answers | 100 | 319.147 | 479.96 | 10 | True |
| python_memory | 4 | tag_cooccurrence | 100 | 1,722.333 | 2,741.441 | 10 | True |
| python_memory | 4 | top_accepted_answerers | 100 | 1,520.679 | 2,303.404 | 10 | True |
| python_memory | 4 | top_answerers | 100 | 176.135 | 291.98 | 10 | True |
| python_memory | 4 | top_askers | 100 | 329.428 | 519.185 | 10 | True |
| python_memory | 4 | top_badges | 100 | 245.002 | 428.932 | 10 | True |
| python_memory | 4 | top_questions_by_score | 100 | 200.474 | 282 | 10 | True |
| python_memory | 4 | top_questions_by_total_comments | 100 | 918.999 | 1,522.118 | 10 | True |
| python_memory | 4 | top_tags_by_questions | 100 | 237.368 | 390.712 | 10 | True |
| sqlite | 1 | asker_answerer_pairs | 100 | 290.226 | 339.195 | 10 | True |
| sqlite | 1 | questions_with_most_answers | 100 | 21.62 | 23.926 | 10 | True |
| sqlite | 1 | tag_cooccurrence | 100 | 1,445.375 | 1,581.169 | 10 | True |
| sqlite | 1 | top_accepted_answerers | 100 | 138.914 | 154.804 | 10 | True |
| sqlite | 1 | top_answerers | 100 | 122.775 | 147.466 | 10 | True |
| sqlite | 1 | top_askers | 100 | 136.447 | 158.064 | 10 | True |
| sqlite | 1 | top_badges | 100 | 633.517 | 746.661 | 10 | True |
| sqlite | 1 | top_questions_by_score | 100 | 124.805 | 147.854 | 10 | True |
| sqlite | 1 | top_questions_by_total_comments | 100 | 587.428 | 628.633 | 10 | True |
| sqlite | 1 | top_tags_by_questions | 100 | 248.197 | 275.577 | 10 | True |
| sqlite | 4 | asker_answerer_pairs | 100 | 291.433 | 339.935 | 10 | True |
| sqlite | 4 | questions_with_most_answers | 100 | 23.185 | 26.098 | 10 | True |
| sqlite | 4 | tag_cooccurrence | 100 | 1,440.114 | 1,596.657 | 10 | True |
| sqlite | 4 | top_accepted_answerers | 100 | 140.672 | 163.06 | 10 | True |
| sqlite | 4 | top_answerers | 100 | 127.22 | 146.24 | 10 | True |
| sqlite | 4 | top_askers | 100 | 141.133 | 157.81 | 10 | True |
| sqlite | 4 | top_badges | 100 | 631.544 | 741.239 | 10 | True |
| sqlite | 4 | top_questions_by_score | 100 | 126.672 | 157.006 | 10 | True |
| sqlite | 4 | top_questions_by_total_comments | 100 | 603.323 | 643.756 | 10 | True |
| sqlite | 4 | top_tags_by_questions | 100 | 253.268 | 274.274 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 4f53cda18c2b: arcadedb_cypher; 99b21d499377: duckdb, ladybug, python_memory, sqlite | False | 0: arcadedb_cypher; 10: duckdb, ladybug, python_memory, sqlite | False |
| questions_with_most_answers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 155492c2f771: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| tag_cooccurrence | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 526e9967c0da: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_accepted_answerers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 4f53cda18c2b: arcadedb_cypher; d3212f9008dc: duckdb, ladybug, python_memory, sqlite | False | 0: arcadedb_cypher; 10: duckdb, ladybug, python_memory, sqlite | False |
| top_answerers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 61f3be3d7d7a: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_askers | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | a024896d12c8: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_badges | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 61f2dab37691: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_questions_by_score | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 8ae48f2ff3e6: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |
| top_questions_by_total_comments | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False | 1a16e6548b34: arcadedb_cypher; bc63940adee8: duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | False |
| top_tags_by_questions | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 2d776db39b29: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True | 10: arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | True |

### Cross-DB mismatches only

| query | majority_hash_dbs | differing_hash_dbs | majority_row_count_dbs | differing_row_count_dbs |
|---|---|---|---|---|
| asker_answerer_pairs | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher |
| top_accepted_answerers | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher |
| top_questions_by_total_comments | duckdb, ladybug, python_memory, sqlite | arcadedb_cypher | arcadedb_cypher, duckdb, ladybug, python_memory, sqlite | none |

## Dataset: stackoverflow-xlarge

### DB summary

| db | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| duckdb | sweep10_t08_r01_duckdb_s00000_mem32g | 0 | 25,000 | 32g | 8 | 100 | shuffled | 1,829.186 | 0 | 180.539 | 14,137.699 | 33,979.32 |
| ladybug | sweep10_t08_r01_ladybug_s00000_mem32g | 0 | 25,000 | 32g | 8 | 100 | shuffled | 1,851.481 | 0 | 793.882 | 17,097.234 | 29,471.008 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| duckdb | 8 | asker_answerer_pairs | 100 | 302.202 | 383.243 | 10 | True |
| duckdb | 8 | questions_with_most_answers | 100 | 54.873 | 78.274 | 10 | True |
| duckdb | 8 | tag_cooccurrence | 100 | 311.052 | 397.316 | 10 | True |
| duckdb | 8 | top_accepted_answerers | 100 | 164.178 | 225.579 | 10 | True |
| duckdb | 8 | top_answerers | 100 | 161.856 | 212.514 | 10 | True |
| duckdb | 8 | top_askers | 100 | 111.757 | 147.398 | 10 | True |
| duckdb | 8 | top_badges | 100 | 80.42 | 118.279 | 5 | True |
| duckdb | 8 | top_questions_by_score | 100 | 1.752 | 3.688 | 10 | True |
| duckdb | 8 | top_questions_by_total_comments | 100 | 585.564 | 695.206 | 10 | True |
| duckdb | 8 | top_tags_by_questions | 100 | 29.303 | 39.637 | 10 | True |
| ladybug | 8 | asker_answerer_pairs | 100 | 2,740.961 | 3,109.65 | 10 | True |
| ladybug | 8 | questions_with_most_answers | 100 | 343.195 | 394.014 | 10 | True |
| ladybug | 8 | tag_cooccurrence | 100 | 949.987 | 999.401 | 10 | True |
| ladybug | 8 | top_accepted_answerers | 100 | 608.706 | 770.523 | 10 | True |
| ladybug | 8 | top_answerers | 100 | 113.845 | 168.859 | 10 | True |
| ladybug | 8 | top_askers | 100 | 128.892 | 180.11 | 10 | True |
| ladybug | 8 | top_badges | 100 | 86.577 | 102.174 | 5 | True |
| ladybug | 8 | top_questions_by_score | 100 | 9.25 | 56.737 | 10 | True |
| ladybug | 8 | top_questions_by_total_comments | 100 | 2,746.767 | 3,004.502 | 10 | True |
| ladybug | 8 | top_tags_by_questions | 100 | 207.816 | 222.027 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | duckdb, ladybug | True | 9d4f555e2f7a: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| questions_with_most_answers | duckdb, ladybug | True | 86596f45f86a: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| tag_cooccurrence | duckdb, ladybug | True | ae8d41d30b07: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_accepted_answerers | duckdb, ladybug | True | 97ea8a5c754a: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_answerers | duckdb, ladybug | True | b008983054ce: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_askers | duckdb, ladybug | True | fbb4b7b486f2: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_badges | duckdb, ladybug | True | 3221bfdf800b: duckdb, ladybug | True | 5: duckdb, ladybug | True |
| top_questions_by_score | duckdb, ladybug | True | ec7359269def: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_questions_by_total_comments | duckdb, ladybug | True | da5474cf3959: duckdb, ladybug | True | 10: duckdb, ladybug | True |
| top_tags_by_questions | duckdb, ladybug | True | 15b23b683177: duckdb, ladybug | True | 10: duckdb, ladybug | True |
