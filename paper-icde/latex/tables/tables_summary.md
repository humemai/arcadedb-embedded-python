# E2 + prose numbers crib (not a table; quoted in text)

- ArcadeDB (one txn): hybrid p50 3.36 [3.20--3.49] ms, p99 11.29 [10.46--12.04] ms; torn state 0/5 trials
- SurrealDB (one txn): hybrid p50 7.02 [6.94--7.06] ms, p99 7.93 [7.83--8.18] ms; torn state 0/5 trials
- Qdrant+Neo4j (composed): hybrid p50 22.35 [20.64--24.41] ms, p99 35.22 [29.79--37.41] ms; torn state 5/5 trials
