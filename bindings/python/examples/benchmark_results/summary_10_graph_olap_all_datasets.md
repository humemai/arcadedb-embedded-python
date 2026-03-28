# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-28T10:46:26Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 3
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:130ab7d92ec23db22f1c50d43aa38a65d330eae807f68894b1e8b049aa0a47db
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - python_memory: builtin
  - sqlite: builtin
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- `gav_enabled` shows whether ArcadeDB queries ran after a Graph Analytical View was built.
- `gav_ready_wait_s` measures the wall-clock wait until the GAV reported `READY`.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-large

### DB summary

| db | gav_enabled | gav_ready_wait_s | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---:|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | True | 22.978 | sweep10_t01_r01_arcadedb_cypher_gavon_s00000_mem32g | 0 | 10,000 | 32g | 1 | 100 | shuffled | 3,068.547 | 135.327 | 622.235 | 30,111.59 | 3,968.652 |
| arcadedb_cypher | True | 28.165 | sweep10_t04_r01_arcadedb_cypher_gavon_s00000_mem32g | 0 | 10,000 | 32g | 4 | 100 | shuffled | 3,047.784 | 114.348 | 521.317 | 24,792.707 | 12,750.773 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 1,859.717 | 2,090.889 | 10 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 814.588 | 963.081 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 271.814 | 301.038 | 0 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 306.934 | 333.613 | 10 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 305.538 | 366.272 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 290.148 | 355.35 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 555.032 | 583.242 | 2 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 677.566 | 734.924 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 1,128.16 | 1,356.339 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 11.104 | 11.602 | 10 | True |
| arcadedb_cypher | 4 | asker_answerer_pairs | 100 | 1,409.815 | 1,502.995 | 10 | True |
| arcadedb_cypher | 4 | questions_with_most_answers | 100 | 743.904 | 751.157 | 10 | True |
| arcadedb_cypher | 4 | tag_cooccurrence | 100 | 238.017 | 239.707 | 0 | True |
| arcadedb_cypher | 4 | top_accepted_answerers | 100 | 247.749 | 257.557 | 10 | True |
| arcadedb_cypher | 4 | top_answerers | 100 | 278.238 | 294.659 | 10 | True |
| arcadedb_cypher | 4 | top_askers | 100 | 262.899 | 270.554 | 10 | True |
| arcadedb_cypher | 4 | top_badges | 100 | 504.518 | 509.061 | 2 | True |
| arcadedb_cypher | 4 | top_questions_by_score | 100 | 588.796 | 582.086 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_total_comments | 100 | 926.33 | 1,025.825 | 10 | True |
| arcadedb_cypher | 4 | top_tags_by_questions | 100 | 11.459 | 11.642 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher | True | 50d35827e6c2: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| questions_with_most_answers | arcadedb_cypher | True | 0c1ff04cbc6b: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| tag_cooccurrence | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_accepted_answerers | arcadedb_cypher | True | 9a51a5e270a7: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_answerers | arcadedb_cypher | True | d12124838677: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_askers | arcadedb_cypher | True | 0644552cf9d3: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_badges | arcadedb_cypher | True | e26bf9c71f40: arcadedb_cypher | True | 2: arcadedb_cypher | True |
| top_questions_by_score | arcadedb_cypher | True | 667618012867: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_questions_by_total_comments | arcadedb_cypher | True | a30c1e9e125b: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_tags_by_questions | arcadedb_cypher | True | 280ede11e63d: arcadedb_cypher | True | 10: arcadedb_cypher | True |

## Dataset: stackoverflow-medium

### DB summary

| db | gav_enabled | gav_ready_wait_s | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---:|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | True | 4.287 | sweep10_t01_r01_arcadedb_cypher_gavon_s00000_mem32g | 0 | 10,000 | 32g | 1 | 100 | shuffled | 270.18 | 34.621 | 160.191 | 7,205.773 | 1,226.992 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 78.471 | 91.331 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 162.922 | 190.306 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 76.098 | 87.601 | 0 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 87.282 | 102.201 | 10 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 108.303 | 123.948 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 164.761 | 204.425 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 414.879 | 432.386 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 195.106 | 215.251 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 306.821 | 358.817 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 5.8 | 6.968 | 10 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| questions_with_most_answers | arcadedb_cypher | True | 155492c2f771: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| tag_cooccurrence | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_accepted_answerers | arcadedb_cypher | True | d3212f9008dc: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_answerers | arcadedb_cypher | True | 61f3be3d7d7a: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_askers | arcadedb_cypher | True | a024896d12c8: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_badges | arcadedb_cypher | True | 61f2dab37691: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_questions_by_score | arcadedb_cypher | True | 8ae48f2ff3e6: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_questions_by_total_comments | arcadedb_cypher | True | bc63940adee8: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_tags_by_questions | arcadedb_cypher | True | 2d776db39b29: arcadedb_cypher | True | 10: arcadedb_cypher | True |
