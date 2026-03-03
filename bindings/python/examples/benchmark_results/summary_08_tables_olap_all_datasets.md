# 08 Tables OLAP Matrix Summary — All Dataset Sizes

- Generated (UTC): 2026-03-03T14:39:59Z
- Dataset: all
- Dataset size profile: all
- Label prefix: sweep08
- Total result files: 4
- Run status files: total=4, success=4, failed=0
- Note: `load_*` is ingest only, `index_*` is post-ingest index build, and `query_*` is OLAP query-suite execution.
- DB summary timing/memory/disk columns are single-run values (no averaging).
- `run_label` identifies the benchmark run(s) included in each DB summary row.

## Dataset: stackoverflow-small

### DB summary

| db | run_label | seed | runs | threads | query_runs | query_order | ingest_mode | load_s | index_s | query_s | rss_peak_mib | du_mib |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| arcadedb | sweep08_t01_r01_arcadedb_s00000 | 0 | 1 | 1 | 10 | shuffled | bulk_tuned_insert | 82.652 | 19.813 | 40.26 | 1,817.934 | 583.336 |
| duckdb | sweep08_t01_r01_duckdb_s00002 | 2 | 1 | 1 | 10 | shuffled | copy_csv | 54.565 | 0.947 | 0.205 | 581.676 | 1,160.238 |
| postgresql | sweep08_t01_r01_postgresql_s00003 | 3 | 1 | 1 | 10 | shuffled | copy_from_stdin | 60.316 | 3.821 | 5.476 | 870.176 | 1,472.148 |
| sqlite | sweep08_t01_r01_sqlite_s00001 | 1 | 1 | 1 | 10 | shuffled | executemany | 19.29 | 1.706 | 1.169 | 511.328 | 594.57 |

### Per-query latency (aggregated)

| db | threads | query | samples | elapsed_mean_ms | elapsed_p95_ms | row_counts | hash_stable_within_db |
|---|---:|---|---:|---:|---:|---|---|
| arcadedb | 1 | most_commented_posts | 10 | 346.784 | 484.035 | 10 | True |
| arcadedb | 1 | post_type_counts | 10 | 361.886 | 570.355 | 6 | True |
| arcadedb | 1 | posthistory_by_type | 10 | 1,254.722 | 1,777.293 | 30 | True |
| arcadedb | 1 | postlinks_by_type | 10 | 58.692 | 214.597 | 2 | True |
| arcadedb | 1 | top_answers_by_score | 10 | 332.905 | 469.317 | 10 | True |
| arcadedb | 1 | top_badges | 10 | 185.791 | 246.423 | 10 | True |
| arcadedb | 1 | top_questions_by_score | 10 | 246.79 | 498.518 | 10 | True |
| arcadedb | 1 | top_tags_by_count | 10 | 2.502 | 6.15 | 10 | True |
| arcadedb | 1 | top_users_by_reputation | 10 | 296.898 | 539.952 | 10 | True |
| arcadedb | 1 | votes_by_type | 10 | 937.779 | 1,152.807 | 14 | True |
| duckdb | 1 | most_commented_posts | 10 | 4.768 | 5.963 | 10 | True |
| duckdb | 1 | post_type_counts | 10 | 1.058 | 1.534 | 6 | True |
| duckdb | 1 | posthistory_by_type | 10 | 1.665 | 1.703 | 30 | True |
| duckdb | 1 | postlinks_by_type | 10 | 0.677 | 0.943 | 2 | True |
| duckdb | 1 | top_answers_by_score | 10 | 2.112 | 2.627 | 10 | True |
| duckdb | 1 | top_badges | 10 | 1.383 | 1.942 | 10 | True |
| duckdb | 1 | top_questions_by_score | 10 | 3.072 | 8.404 | 10 | True |
| duckdb | 1 | top_tags_by_count | 10 | 0.506 | 0.848 | 10 | True |
| duckdb | 1 | top_users_by_reputation | 10 | 2.311 | 2.625 | 10 | True |
| duckdb | 1 | votes_by_type | 10 | 2.206 | 2.804 | 14 | True |
| postgresql | 1 | most_commented_posts | 10 | 188.097 | 532.036 | 10 | True |
| postgresql | 1 | post_type_counts | 10 | 76.595 | 207.869 | 6 | True |
| postgresql | 1 | posthistory_by_type | 10 | 178.072 | 402.553 | 30 | True |
| postgresql | 1 | postlinks_by_type | 10 | 1.752 | 2.122 | 2 | True |
| postgresql | 1 | top_answers_by_score | 10 | 0.411 | 0.579 | 10 | True |
| postgresql | 1 | top_badges | 10 | 38.6 | 79.317 | 10 | True |
| postgresql | 1 | top_questions_by_score | 10 | 0.411 | 0.541 | 10 | True |
| postgresql | 1 | top_tags_by_count | 10 | 0.399 | 0.596 | 10 | True |
| postgresql | 1 | top_users_by_reputation | 10 | 0.415 | 0.879 | 10 | True |
| postgresql | 1 | votes_by_type | 10 | 62.141 | 84.379 | 14 | True |
| sqlite | 1 | most_commented_posts | 10 | 16.858 | 18.989 | 10 | True |
| sqlite | 1 | post_type_counts | 10 | 4.954 | 5.444 | 6 | True |
| sqlite | 1 | posthistory_by_type | 10 | 15.611 | 19.28 | 30 | True |
| sqlite | 1 | postlinks_by_type | 10 | 0.559 | 0.62 | 2 | True |
| sqlite | 1 | top_answers_by_score | 10 | 25.212 | 27.975 | 10 | True |
| sqlite | 1 | top_badges | 10 | 10.613 | 11.702 | 10 | True |
| sqlite | 1 | top_questions_by_score | 10 | 23.773 | 27.115 | 10 | True |
| sqlite | 1 | top_tags_by_count | 10 | 0.105 | 0.141 | 10 | True |
| sqlite | 1 | top_users_by_reputation | 10 | 0.091 | 0.137 | 10 | True |
| sqlite | 1 | votes_by_type | 10 | 18.201 | 21.66 | 14 | True |

### Cross-DB hash checks

| query | dbs | hash_equal_across_dbs | all_hashes |
|---|---|---|---|
| most_commented_posts | arcadedb, duckdb, postgresql, sqlite | True | a05cb33ead9487a77be11c66fec1bc9845a42406841fade9e69310b62194573b |
| post_type_counts | arcadedb, duckdb, postgresql, sqlite | True | 583c4cb89bb067d3395741ab6056db81efe8ad3147ced12c42d3cc5760ba121b |
| posthistory_by_type | arcadedb, duckdb, postgresql, sqlite | True | b058ed6623a14b524022e27e5643be600cf5a602686289e1cff80b2994135f8b |
| postlinks_by_type | arcadedb, duckdb, postgresql, sqlite | True | e8c8de04daedd0c8cd4e732882304daaa84dafcf63eee7de6896f0d933208033 |
| top_answers_by_score | arcadedb, duckdb, postgresql, sqlite | True | 27eaaec2da081e3b419caa6c483728c25f521bfb4ef7fd7f6c357e09d21465ad |
| top_badges | arcadedb, duckdb, postgresql, sqlite | True | 1e59f910a684c234878322c01b6e45610010ebc9717544d0896eebc9d6af100d |
| top_questions_by_score | arcadedb, duckdb, postgresql, sqlite | True | 461c67e3d5c6d7e876ae49d115cde78a8f297e801d2767b952ef7dc98eee1cc5 |
| top_tags_by_count | arcadedb, duckdb, postgresql, sqlite | True | ca7a21ae6b26cb8a1ad8a10043a681497762ad30c8220a6ebdbe0a63b6f87bd8 |
| top_users_by_reputation | arcadedb, duckdb, postgresql, sqlite | True | e6859c1bf08aedecbe35d8547cca8ffe5e0dbae3034edd87df52529d5e7fdb66 |
| votes_by_type | arcadedb, duckdb, postgresql, sqlite | True | 3ac0d5ce297f1de3e04386d747b3d8d7869bf0aa6de20c579b67328deed9f975 |
