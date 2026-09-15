# E2 + prose numbers crib (not a table; quoted in text)

- ArcadeDB (one txn): hybrid p50 2.03 [1.93--2.04] ms, p99 5.77 [5.2--6.6] ms; torn state 0/5 trials
- SurrealDB (one txn): hybrid p50 8.29 [8.2--8.4] ms, p99 9.63 [9.3--9.9] ms; torn state 0/5 trials
- Qdrant+Neo4j (composed): hybrid p50 20.65 [18.7--24.9] ms, p99 36.02 [27.8--38.2] ms; torn state 5/5 trials
