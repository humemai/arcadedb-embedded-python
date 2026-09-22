# E2 + prose numbers crib (not a table; quoted in text)

- ArcadeDB (one txn): hybrid p50 1.96 [1.6--2.3] ms, p99 3.42 [2.4--139] ms; torn state 0/10 trials
- SurrealDB (one txn): hybrid p50 11.86 [7.5--16.8] ms, p99 13.39 [8.6--24.3] ms; torn state 0/5 trials
- Qdrant+Neo4j (composed): hybrid p50 79.43 [17.6--144] ms, p99 93.43 [23.6--160] ms; torn state 10/10 trials
