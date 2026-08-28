# Changelog

Notable changes in `arcadedb-embedded`, the Python distribution of the ArcadeDB
engine. Engine changes are linked to their upstream issue or PR in
[ArcadeData/arcadedb](https://github.com/ArcadeData/arcadedb).

This file exists because the wheel bundles the engine: a change to ArcadeDB's
Java behaviour reaches Python users through `pip install` without passing
through anything they would think to read. Breaking changes are listed first
for each version.

## Unreleased

### Breaking

- **Removed `arcadedb_embedded.cite()` and the `citation` module.** The helper
  resolved a release's Zenodo DOI by calling the Zenodo API at runtime, which
  put a network round trip and a third-party dependency inside a library whose
  purpose is in-process, offline database access, and it raised
  `ArcadeDBError` on any network that blocks zenodo.org. Cite the project with
  the metadata in `CITATION.cff` instead: GitHub renders it as "Cite this
  repository", and Zenodo reads it when archiving each release.

## 26.8.1

First stable release on the 26.8.1 line, synced to upstream's release commit
`87bdc67f1f` and nothing after it. The two commits that follow it upstream
bump the tree to 26.9.1-SNAPSHOT and are deliberately excluded.

### Security

This release carries upstream's 26.8.1 security work, which matters here
because the wheel bundles the server and every wire protocol it fixes:

- **Authentication is now enforced on the MongoDB and Redis wire protocols**,
  which previously accepted unauthenticated connections. Redis also gains TLS
  and a HELLO handshake. If you start a server with those plugins enabled,
  clients that used to connect anonymously now need credentials.
- **Authenticated principal is bound on more execution paths** so per-type
  ACLs are actually enforced: the async command worker, the gRPC transaction
  thread, and the batch/time-series HTTP handlers each previously ran without
  it.
- `GHSA-qwgr-2c45-63xx`: database-name validation prevents path traversal on
  create/drop.
- `GHSA-xmjm-8q85-g778`: a Cypher `range()` can no longer exhaust the heap.
- MCP server-administration tools enforce per-caller authorization.


### Breaking

- **`location_cache_size` is gone**, following its removal from the engine in
  [#5559](https://github.com/ArcadeData/arcadedb/issues/5559) and
  [#5568](https://github.com/ArcadeData/arcadedb/issues/5568). The engine
  dropped both the `arcadedb.vectorIndex.locationCacheSize` JVM property and
  the per-index `locationCacheSize` metadata key, and now rejects the key
  outright, so any wheel that still forwarded it could not create a vector
  index at all.

  It was never really a cache. A vector location is the only mapping from a
  vector id to its record, so bounding it did not spill to disk: it dropped
  vectors from searches and from `countEntries()`. Size the heap for the live
  vector set instead.

  `create_vector_index(..., location_cache_size=N)` now raises `ValueError`
  with that explanation rather than failing inside the Java builder, and
  `VectorIndex.get_metadata()` no longer reports a `location_cache_size` key.
  SQL `METADATA` blocks carrying `locationCacheSize` are rejected by the
  engine.

### Added

- **`ResultSet.to_arrow()`** returns a `pyarrow.Table` built from the same
  columnar bridge buffer `to_columns()` already uses, so it adds no Java and no
  jars to the wheel. It preserves validity bitmaps instead of widening nullable
  integers to float64/NaN the way `to_columns()` must. Requires the new
  optional `arrow` extra (`pip install arcadedb-embedded[arrow]`); without
  pyarrow installed it returns `None` so callers can fall back.

## 26.8.1.dev24

### Restored

- **Server mode is back.** `create_server()` / `ArcadeDBServer`, the HTTP API,
  and the Studio web UI ship in the wheel again, reversing the removal in
  26.7.2. If you pinned `26.7.1` to keep server mode, you can move forward.

  The removal traded a real feature for ~8 MB and was made without evidence
  that nobody used it. A downstream user told us otherwise on the removal
  commit itself, three weeks after it shipped in a stable release.

  **What it costs, measured on one Linux x86_64 build of the same commit:**

  | | wheel file | jars (in wheel) | bundled JRE (in wheel) |
  | --- | --- | --- | --- |
  | without server | 59.06 MiB | 20.70 MiB | 38.30 MiB |
  | with server | 67.08 MiB | 27.87 MiB | 39.10 MiB |
  | delta | **+8.02 MiB (+13.6%)** | +7.17 MiB | +0.80 MiB |

  The server stack is 12 JARs totalling 7.65 MiB uncompressed. The extra
  0.8 MiB is the bundled JRE, not the JARs: the build `jdeps`/`jlink`s a
  runtime from whatever the shipped JARs need, and the server pulls in
  `java.naming`, `java.security.jgss`, and `java.security.sasl` (JNDI and the
  Kerberos/SASL stack Undertow wants). Estimating the feature's cost from JAR
  sizes alone understates it by roughly 10%.

  **What it costs at runtime if you never call `create_server()`: essentially
  nothing.** The JARs sit on the classpath, the JVM loads classes lazily, no
  threads start and no heap is allocated. Studio is 126 entries of static
  JS/HTML/CSS and **zero** `.class` files, so it cannot execute anything until
  a browser asks for an asset.

- **The suite can no longer go quiet if the server disappears again.** Every
  pre-existing server test was guarded by `has_server_support()`, so when the
  JARs were dropped those tests *skipped* and the suite stayed green while the
  feature was gone. New `tests/test_server_packaging.py` asserts the JARs, the
  exported API, the honesty of the skip-guard itself, and a real HTTP round
  trip — and **fails** rather than skips. A deliberately slim wheel now means
  deleting that file on purpose.

### Fixed

- **Example 23 could not complete a server round trip.** Its readiness poll
  retried on `RuntimeError`, but a socket timeout raises `TimeoutError`, which
  is an `OSError` and not a `URLError`, so it escaped the retry loop instead of
  causing one more attempt. The per-attempt budget was 5.0 s and the first
  request measured 5.64 s, so the example failed on a machine where the server
  was working correctly.

  The first HTTP request after `start()` is genuinely slow: **5.64 s**, then
  0.70 s, then under 10 ms. Undertow and the REST handlers class-load lazily
  and the root password is verified with a deliberately expensive KDF, and both
  land on request one. If you poll for readiness, budget for it.

## 26.8.1.dev23

### Engine

- **TimeSeries `TAG` columns are dictionary-encoded**
  ([#5574](https://github.com/ArcadeData/arcadedb/pull/5574), closing
  [#5519](https://github.com/ArcadeData/arcadedb/issues/5519)). A mutable
  TimeSeries row is fixed-stride, so a `STRING` TAG previously reserved
  `2 + MAX_STRING_BYTES` = 258 bytes inline whether the value was
  `us-east-1` or empty. Tags are low-cardinality by definition, so nearly all
  of that was padding that still got written, flushed and shipped through the
  WAL. A TAG now holds a 4-byte id into a per-type dictionary.

  For a ten-tag schema (what TSBS `cpu` actually declares) the row stride goes
  **2,612 B to 72 B** and rows per 64K page **25 to 909**. A single-tag schema
  improves too, 290 B to 36 B.

  **Existing databases are unaffected and there is no in-place migration.**
  The row format is versioned per type: a type created by an earlier build
  keeps the inline layout, and only a newly created type gets the encoding. If
  you are benchmarking this, point it at a fresh database, or you will measure
  the old layout and see no change.

  `arcadedb.timeSeriesTagDictionaryMaxSize` (default 1M distinct values) turns
  a mis-declared high-cardinality TAG into a clear error rather than unbounded
  growth. STRING *fields* stay inline, deliberately: a field is where
  high-cardinality text belongs.

- **`LSM_VECTOR` publishes its location map atomically**
  ([#5568](https://github.com/ArcadeData/arcadedb/issues/5568)) instead of
  clearing and refilling it, so lookups no longer observe a partially rebuilt
  map.

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
