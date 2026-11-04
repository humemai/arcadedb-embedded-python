
## 2026-11-05 04:59 KST: card example match-while corrected (before any generation)

card_check.py on ArcadeDB 26.10.2 (dbbench:arcadedb-26.10.2): 29 of 30 examples correct; `match-while` returned Bob as well. In the toy data Bob is at depth 3 from badge 7 (Grace, Frank, Ann, Bob). The engine is right: `while:` gates further expansion, not inclusion, so `while: ($depth < 3)` expands from depths 0 to 2 and returns depth 3. The card sentence and the example's expected rows were corrected; the query text is unchanged. The prompt file changed before the first generation, so the frozen set is the corrected one.

## 2026-11-05 04:59 KST: A10 does not reproduce on SQLite (portability, not a gold error)

`SELECT count(*) AS n FROM Tag WHERE name LIKE '%The%'` matches case-insensitively on SQLite (its LIKE folds ASCII case by default) and case-sensitively on DuckDB and PostgreSQL, so the counts differ. The DuckDB reference answer stands; the portability score reports this as an engine-specific difference.

## 2026-11-05 05:02 KST: D03 SQL/PGQ crashes DuckDB at full size (engine failure, not a gold error)

gold_check on the full sf1 subset (9,892 persons, 180,623 friendships): the DuckDB container exited with code 139 (SIGSEGV) in job `D03::pgq` (DuckDB 1.5.6 + DuckPGQ 61f5d082); the restart rule recorded it as `engine_killed` and the other 22 jobs ran. The same gold was OK in the 500-person smoke. The gold stays as written: a generated D03 query that crashes the engine is scored as a failure, which is what a user of this engine would meet. Every other gold is OK on every arm at full size (5 ArcadeDB SQL golds are author-null, scored against the SQL reference rows). Upstream note owed on cwida/duckpgq-extension (our #335 thread or a new issue with this repro).
