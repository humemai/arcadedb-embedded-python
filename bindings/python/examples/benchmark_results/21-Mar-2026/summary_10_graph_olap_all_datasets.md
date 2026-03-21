# 10 Graph OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-21T09:58:09Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep10
- Total result files: 3
- Versions/digest observed:
  - arcadedb_docker_digest: arcadedata/arcadedb@sha256:6f1f08f5d05cb615d15ba346b4845cae7b42f0199b8c41bf26bcad2d44d1e8e1
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
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 1 | 100 | shuffled | 5,275.918 | 124.897 | 3,579.275 | 19,691.93 | 3,968.625 |
| arcadedb_cypher | sweep10_t04_r01_arcadedb_cypher_s00000_mem32g | 0 | 10,000 | 32g | 4 | 100 | shuffled | 4,213.075 | 118.659 | 3,080.738 | 22,526.727 | 12,750.77 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 5,570.237 | 5,908.688 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 5,526.184 | 5,862.689 | 10 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 9,482.2 | 10,028.321 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 2,099.57 | 2,218.911 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 5,499.615 | 5,972.924 | 10 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 2,792.708 | 3,054.129 | 10 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 612.482 | 643.059 | 0 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 677.699 | 709.593 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 3,529.851 | 3,778.004 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 0.822 | 0.887 | 0 | True |
| arcadedb_cypher | 4 | asker_answerer_pairs | 100 | 4,480.625 | 4,582.059 | 0 | True |
| arcadedb_cypher | 4 | questions_with_most_answers | 100 | 4,817.117 | 4,973.486 | 10 | True |
| arcadedb_cypher | 4 | tag_cooccurrence | 100 | 7,854.832 | 8,063.965 | 10 | True |
| arcadedb_cypher | 4 | top_accepted_answerers | 100 | 1,741.305 | 1,790.794 | 0 | True |
| arcadedb_cypher | 4 | top_answerers | 100 | 5,296.858 | 5,564.993 | 10 | True |
| arcadedb_cypher | 4 | top_askers | 100 | 2,606.288 | 2,727.699 | 10 | True |
| arcadedb_cypher | 4 | top_badges | 100 | 627.793 | 644.721 | 0 | True |
| arcadedb_cypher | 4 | top_questions_by_score | 100 | 611.463 | 629.337 | 10 | True |
| arcadedb_cypher | 4 | top_questions_by_total_comments | 100 | 2,768.819 | 2,896.979 | 10 | True |
| arcadedb_cypher | 4 | top_tags_by_questions | 100 | 0.897 | 0.996 | 0 | True |

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

## Dataset: stackoverflow-medium

### DB summary

| db | run_label | seed | batch_size | mem_limit | threads | query_runs | query_order | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|
| arcadedb_cypher | sweep10_t01_r01_arcadedb_cypher_s00000_mem8g | 0 | 5,000 | 8g | 1 | 100 | shuffled | 434.235 | 36.63 | 833.175 | 7,825.812 | 1,236.176 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb_cypher | 1 | asker_answerer_pairs | 100 | 1,233.885 | 1,386.094 | 0 | True |
| arcadedb_cypher | 1 | questions_with_most_answers | 100 | 127.818 | 150.954 | 0 | True |
| arcadedb_cypher | 1 | tag_cooccurrence | 100 | 4,983.282 | 5,516.738 | 10 | True |
| arcadedb_cypher | 1 | top_accepted_answerers | 100 | 471.383 | 569.966 | 0 | True |
| arcadedb_cypher | 1 | top_answerers | 100 | 131.821 | 164.886 | 0 | True |
| arcadedb_cypher | 1 | top_askers | 100 | 132.372 | 158.915 | 0 | True |
| arcadedb_cypher | 1 | top_badges | 100 | 243.469 | 293.549 | 0 | True |
| arcadedb_cypher | 1 | top_questions_by_score | 100 | 212.404 | 259.069 | 10 | True |
| arcadedb_cypher | 1 | top_questions_by_total_comments | 100 | 792.841 | 984.922 | 10 | True |
| arcadedb_cypher | 1 | top_tags_by_questions | 100 | 0.854 | 1.125 | 0 | True |

### Cross-DB query parity checks

| query | dbs | hash_equal_across_dbs | hash_groups | row_counts_equal_across_dbs | row_count_groups | all_values_equal_across_dbs |
|---|---|---|---|---|---|---|
| asker_answerer_pairs | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| questions_with_most_answers | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| tag_cooccurrence | arcadedb_cypher | True | 526e9967c0da: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_accepted_answerers | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_answerers | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_askers | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_badges | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
| top_questions_by_score | arcadedb_cypher | True | 8ae48f2ff3e6: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_questions_by_total_comments | arcadedb_cypher | True | 1a16e6548b34: arcadedb_cypher | True | 10: arcadedb_cypher | True |
| top_tags_by_questions | arcadedb_cypher | True | 4f53cda18c2b: arcadedb_cypher | True | 0: arcadedb_cypher | True |
