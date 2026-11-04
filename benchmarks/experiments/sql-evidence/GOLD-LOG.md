
## 2026-11-05 04:59 KST: card example match-while corrected (before any generation)

card_check.py on ArcadeDB 26.10.2 (dbbench:arcadedb-26.10.2): 29 of 30 examples correct; `match-while` returned Bob as well. In the toy data Bob is at depth 3 from badge 7 (Grace, Frank, Ann, Bob). The engine is right: `while:` gates further expansion, not inclusion, so `while: ($depth < 3)` expands from depths 0 to 2 and returns depth 3. The card sentence and the example's expected rows were corrected; the query text is unchanged. The prompt file changed before the first generation, so the frozen set is the corrected one.

## 2026-11-05 04:59 KST: A10 does not reproduce on SQLite (portability, not a gold error)

`SELECT count(*) AS n FROM Tag WHERE name LIKE '%The%'` matches case-insensitively on SQLite (its LIKE folds ASCII case by default) and case-sensitively on DuckDB and PostgreSQL, so the counts differ. The DuckDB reference answer stands; the portability score reports this as an engine-specific difference.
