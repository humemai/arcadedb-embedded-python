# LadybugDB package + versions (updated 2026-08-28)

The experiments use the OFFICIAL LadybugDB package **`ladybug`** (0.18.1, from
LadybugDB/ladybug-python). Earlier they pinned `real_ladybug` (0.15.3), which is
published from a different repo (lbugdb/lbug) and is frozen; we switched after
LadybugDB shipped 0.18.1.

Versions pinned (all on PyPI):
- ArcadeDB: `arcadedb-embedded==26.8.1` (release; every paper row was re-measured on
  the PyPI 26.8.1 wheel on 2026-08-04, image sha256:d0dbe7c653c1).
- LadybugDB: `ladybug==0.18.1`.
- DuckDB 1.5.4, SQLite 3.46.1, Chroma 1.5.9 (unchanged).

The paper and poster were re-measured on mini and updated to these versions and
numbers (2026-07-11). Prior campaigns archived under results/archive_*.
