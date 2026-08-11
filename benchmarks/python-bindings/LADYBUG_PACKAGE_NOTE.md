# LadybugDB package + versions (updated 2026-07-11)

The experiments use the OFFICIAL LadybugDB package **`ladybug`** (0.18.1, from
LadybugDB/ladybug-python). Earlier they pinned `real_ladybug` (0.15.3), which is
published from a different repo (lbugdb/lbug) and is frozen; we switched after
LadybugDB shipped 0.18.1.

Versions pinned (all on PyPI):
- ArcadeDB: `arcadedb-embedded==26.7.2` (release). This also corrects an earlier
  paper misstatement: the 2026-07-05 run actually used `26.8.1.dev0` (upstream's
  pom said 26.8.1-SNAPSHOT at build time; that line was later renamed and
  released as 26.7.2), while the paper stated 26.7.2. Re-measured on the real
  26.7.2 release so the text is now true.
- LadybugDB: `ladybug==0.18.1`.
- DuckDB 1.5.4, SQLite 3.46.1, Chroma 1.5.9 (unchanged).

The paper and poster were re-measured on mini and updated to these versions and
numbers (2026-07-11). Prior campaigns archived under results/archive_*.
