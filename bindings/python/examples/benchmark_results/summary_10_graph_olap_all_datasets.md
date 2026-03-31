# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-31T14:59:10Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 3
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:535c81b4b423b38da3a8cd908b898efbde16de3f1a2db335bf8fca7220b4b2ea
  - arcadedb_docker_tag: 26.4.1-SNAPSHOT
  - arcadedb_embedded: 26.4.1.dev0
  - neo4j: 2026.02.3
  - python_memory: builtin
  - real_ladybug: 0.15.2
  - sqlite: builtin
  - wheel_file: arcadedb_embedded-26.4.1.dev0-cp312-cp312-manylinux_2_35_x86_64.whl
  - wheel_source: local_bindings_source
  - wheel_version: 26.4.1.dev0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- `gav_mode` is the ArcadeDB-only sweep dimension for Graph Analytical View usage: `on` or `off`.
- `gav_setup_s` is populated only for ArcadeDB runs where GAV was enabled.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- Query parity is evaluated via `result_hash` and `row_count` across DBs.

## Dataset: stackoverflow-medium

### DB summary

| db              | gav_mode | gav_setup_s | run_label                                          | seed | batch_size | mem_limit | threads | query_runs | query_order |  load_s | index_s | query_s | rss_peak_mib |    du_mib |
| --------------- | -------- | ----------: | -------------------------------------------------- | ---: | ---------: | --------- | ------: | ---------: | ----------- | ------: | ------: | ------: | -----------: | --------: |
| arcadedb_cypher | on       |       5.596 | sweep10_t04_r01_arcadedb_cypher_gavon_s00000_mem8g |    0 |      5,000 | 8g        |       4 |        100 | shuffled    | 320.573 |  33.158 | 143.114 |    7,996.777 | 4,010.199 |
| ladybug         |          |             | sweep10_t04_r01_ladybug_s00000_mem8g               |    0 |      5,000 | 8g        |       4 |        100 | shuffled    |  91.265 |       0 |  87.257 |    3,040.812 | 1,818.504 |
| neo4j           |          |             | sweep10_t04_r01_neo4j_s00000_mem8g                 |    0 |      5,000 | 8g        |       4 |        100 | shuffled    | 183.343 |   0.258 | 436.678 |    5,722.233 | 3,965.191 |

### Per-query latency (aggregated)

| db              | threads | query                           | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
| --------------- | ------: | ------------------------------- | ------: | --------------: | -------------: | ---------- | --------------------- |
| arcadedb_cypher |       4 | asker_answerer_pairs            |     100 |          69.914 |         73.502 | 0          | True                  |
| arcadedb_cypher |       4 | questions_with_most_answers     |     100 |         153.428 |        166.982 | 10         | True                  |
| arcadedb_cypher |       4 | tag_cooccurrence                |     100 |           69.55 |         73.957 | 0          | True                  |
| arcadedb_cypher |       4 | top_accepted_answerers          |     100 |          80.395 |         87.165 | 10         | True                  |
| arcadedb_cypher |       4 | top_answerers                   |     100 |         102.265 |         110.85 | 10         | True                  |
| arcadedb_cypher |       4 | top_askers                      |     100 |         148.948 |        158.801 | 10         | True                  |
| arcadedb_cypher |       4 | top_badges                      |     100 |          380.73 |        395.057 | 10         | True                  |
| arcadedb_cypher |       4 | top_questions_by_score          |     100 |         166.918 |        176.655 | 10         | True                  |
| arcadedb_cypher |       4 | top_questions_by_total_comments |     100 |         251.983 |        280.165 | 10         | True                  |
| arcadedb_cypher |       4 | top_tags_by_questions           |     100 |           5.551 |           5.95 | 10         | True                  |
| ladybug         |       4 | asker_answerer_pairs            |     100 |         197.989 |        226.504 | 10         | True                  |
| ladybug         |       4 | questions_with_most_answers     |     100 |          70.776 |         84.514 | 10         | True                  |
| ladybug         |       4 | tag_cooccurrence                |     100 |         165.572 |        202.696 | 10         | True                  |
| ladybug         |       4 | top_accepted_answerers          |     100 |          38.726 |         45.715 | 10         | True                  |
| ladybug         |       4 | top_answerers                   |     100 |           58.72 |         68.757 | 10         | True                  |
| ladybug         |       4 | top_askers                      |     100 |          64.453 |         78.536 | 10         | True                  |
| ladybug         |       4 | top_badges                      |     100 |          87.675 |        102.224 | 10         | True                  |
| ladybug         |       4 | top_questions_by_score          |     100 |           2.053 |          2.401 | 10         | True                  |
| ladybug         |       4 | top_questions_by_total_comments |     100 |         144.749 |        185.952 | 10         | True                  |
| ladybug         |       4 | top_tags_by_questions           |     100 |          39.509 |         42.066 | 10         | True                  |
| neo4j           |       4 | asker_answerer_pairs            |     100 |         612.361 |        704.339 | 10         | True                  |
| neo4j           |       4 | questions_with_most_answers     |     100 |         200.015 |        238.594 | 10         | True                  |
| neo4j           |       4 | tag_cooccurrence                |     100 |       1,588.736 |      1,731.906 | 10         | True                  |
| neo4j           |       4 | top_accepted_answerers          |     100 |          70.734 |         77.751 | 10         | True                  |
| neo4j           |       4 | top_answerers                   |     100 |         212.679 |        252.811 | 10         | True                  |
| neo4j           |       4 | top_askers                      |     100 |         327.561 |        385.324 | 10         | True                  |
| neo4j           |       4 | top_badges                      |     100 |         424.761 |        474.222 | 10         | True                  |
| neo4j           |       4 | top_questions_by_score          |     100 |          77.872 |          86.62 | 10         | True                  |
| neo4j           |       4 | top_questions_by_total_comments |     100 |         633.137 |        701.964 | 10         | True                  |
| neo4j           |       4 | top_tags_by_questions           |     100 |         217.488 |        258.036 | 10         | True                  |

### Cross-DB query parity checks

| query                           | dbs                             | hash_equal_across_dbs | hash_groups                                                 | row_counts_equal_across_dbs | row_count_groups                       | all_values_equal_across_dbs |
| ------------------------------- | ------------------------------- | --------------------- | ----------------------------------------------------------- | --------------------------- | -------------------------------------- | --------------------------- |
| asker_answerer_pairs            | arcadedb_cypher, ladybug, neo4j | False                 | 4f53cda18c2b: arcadedb_cypher; 99b21d499377: ladybug, neo4j | False                       | 0: arcadedb_cypher; 10: ladybug, neo4j | False                       |
| questions_with_most_answers     | arcadedb_cypher, ladybug, neo4j | True                  | 155492c2f771: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| tag_cooccurrence                | arcadedb_cypher, ladybug, neo4j | False                 | 4f53cda18c2b: arcadedb_cypher; 526e9967c0da: ladybug, neo4j | False                       | 0: arcadedb_cypher; 10: ladybug, neo4j | False                       |
| top_accepted_answerers          | arcadedb_cypher, ladybug, neo4j | True                  | d3212f9008dc: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_answerers                   | arcadedb_cypher, ladybug, neo4j | True                  | 61f3be3d7d7a: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_askers                      | arcadedb_cypher, ladybug, neo4j | True                  | a024896d12c8: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_badges                      | arcadedb_cypher, ladybug, neo4j | True                  | 61f2dab37691: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_questions_by_score          | arcadedb_cypher, ladybug, neo4j | True                  | 8ae48f2ff3e6: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_questions_by_total_comments | arcadedb_cypher, ladybug, neo4j | True                  | bc63940adee8: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |
| top_tags_by_questions           | arcadedb_cypher, ladybug, neo4j | True                  | 2d776db39b29: arcadedb_cypher, ladybug, neo4j               | True                        | 10: arcadedb_cypher, ladybug, neo4j    | True                        |

### Cross-DB mismatches only

| query                | majority_hash_dbs | differing_hash_dbs | majority_row_count_dbs | differing_row_count_dbs |
| -------------------- | ----------------- | ------------------ | ---------------------- | ----------------------- |
| asker_answerer_pairs | ladybug, neo4j    | arcadedb_cypher    | ladybug, neo4j         | arcadedb_cypher         |
| tag_cooccurrence     | ladybug, neo4j    | arcadedb_cypher    | ladybug, neo4j         | arcadedb_cypher         |
