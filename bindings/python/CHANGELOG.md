# Changelog

Notable changes in `arcadedb-embedded`, the Python distribution of the ArcadeDB
engine. Engine changes are linked to their upstream issue or PR in
[ArcadeData/arcadedb](https://github.com/ArcadeData/arcadedb).

This file exists because the wheel bundles the engine: a change to ArcadeDB's
Java behaviour reaches Python users through `pip install` without passing
through anything they would think to read. Breaking changes are listed first
for each version.

## 26.8.1.dev22

### Engine

- **Sparse vector search runs a single query's scan in parallel**
  ([#5518](https://github.com/ArcadeData/arcadedb/pull/5518), closing
  [#4085](https://github.com/ArcadeData/arcadedb/issues/4085)). An
  `LSM_SPARSE_VECTOR` top-K now splits its RID space into disjoint ranges
  scanned concurrently and merged, instead of one thread walking the whole
  posting space. Results are unchanged: the split is exact, and where scores
  tie so closely that ordering could differ, the guarantee is that the answer
  is never worse than the serial one.

  On by default and adaptive. `arcadedb.sparseVectorScoringMaxPartitions`
  controls it: `0` (default) lets the engine decide and back off when the
  machine is busy, `1` disables splitting, and an explicit value above 1 forces
  that many ranges. **Leave it at 0 unless you have measured otherwise.** A
  forced split helps only when one query at a time must be as fast as possible
  with nothing else running; under concurrent load it is worse than not
  splitting at all, on latency and throughput together.

- **`LSM_VECTOR` no longer leaks `VectorLocation` objects**
  ([#5516](https://github.com/ArcadeData/arcadedb/issues/5516)). Re-storing
  embeddings for vertices that already had them accumulated in-memory entries
  that were never released, not by `DROP INDEX` and not by recreating the
  index. A workload that periodically re-embeds unchanged records grew until it
  hit `OutOfMemoryError`. Also makes the index compact itself once its file is
  mostly garbage.

## 26.8.1.dev21

### Breaking

- **A Cypher query that references a parameter you never bound now raises
  instead of returning NULL**
  ([#5501](https://github.com/ArcadeData/arcadedb/issues/5501)).

  ```python
  db.query("opencypher", "RETURN $threshold AS t")            # was: t = None
                                                              # now: raises
  db.query("opencypher", "RETURN $threshold AS t", {"threshold": 21})  # fine
  db.query("opencypher", "RETURN $threshold AS t", {"threshold": None})  # fine
  ```

  From Python the failure surfaces as `ArcadeDBError` wrapping
  `com.arcadedb.exception.CommandParameterMissingException`, whose message
  names what is missing (`Expected parameter(s): threshold`). Over Bolt it
  reports `Neo.ClientError.Statement.ParameterMissing`, matching Neo4j; over
  HTTP it is a 400. Binding a parameter to `None` explicitly still works:
  *bound to null* is not *unbound*. `EXPLAIN` is exempt, as in Neo4j;
  `PROFILE` is not.

  (In dev21 this arrived as a generic `CommandParsingException`. dev22 gives
  it a dedicated exception type and carries the missing names on the exception
  rather than only inside the message text, so you no longer have to parse the
  string apart.)

  The silence this replaces was the bug: a `WHERE NOT EXISTS { ... $id ... }`
  guard against a value nobody supplied became an unconditional `CREATE`.

  **If you relied on the old behaviour**, bind the parameter explicitly to
  `None` rather than omitting it.
