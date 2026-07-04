# Python Bindings vs Java Native: Performance & Memory Report

Five measurement/fix rounds, 2026-07-03 → 2026-07-04 · Engine 26.8.1-SNAPSHOT ·
Machine: maintainer laptop (diagnostic numbers — paper-grade numbers must be
re-measured on tk@mini) · Full history in the Appendix; raw data in
`results/all_results.csv`.

## Executive summary

Starting point: upstream (discussion #3674) observed vector search is fast in Java
but slow through the Python bindings. A controlled comparison — **identical JARs,
identical bundled JRE, identical JVM flags, identical on-disk databases and query
vectors, verified identical results** — confirmed it, located every source of
overhead, and fixed what mattered:

| | before | after | Java native |
|---|---|---|---|
| Vector search (SQL path, 100k×384, k=50) | 52.8ms (15×) | **5.09 ± 0.15ms (1.15×)** | 4.41 ± 0.24ms |
| Vector search, 500k (#3674 scale) | 62.1ms | **11.5ms (1.13×)** | 10.2ms |
| Bulk scan 100k rows × 7 cols | 4.54s (30×) | **0.50s (3.4×)** via `to_json_list()` | 149ms |
| Bulk edge ingest (GraphBatch, per edge) | 4.24µs (24×) | **0.57µs** via `new_edges()` | 0.1µs |
| CSV export, 100k rows | 2431ms | **498ms** | — |
| Threaded OLTP, 8 threads | crash | **44.6k qps** via `run_in_transaction()` | 106.6k qps |

**The engine was never the problem.** Raw JPype calls match Java (2.89 vs 3.17ms,
overlapping intervals), and every engine-bound operation measured at parity from the
start: GROUP BY 1.05×, Cypher traversal 1.06×, BM25 full-text 1.02×, UPDATE 1.2×,
DELETE 1.3×, INSERT 1.9× (on a 5µs op), `export_database` 1.02×, async submission
1.04×, DB open/lifecycle ~1×. All overhead lived in the Python-side *result
materialization and per-operation crossing* layers — and that is what the fixes
removed.

**Memory: acquitted.** No leaks (45-min soak, 2.65M mixed ops: post-GC heap flat at
28MB throughout; abandoned/undrained ResultSets GC cleanly), wrapper pinning is
~312 bytes/row and fully reclaimed, and baseline RSS is 121MB (`-Xmx4g` is a
ceiling, not a reservation).

**Two engine bugs found and filed upstream** (both worked around in the bindings):
- [#4967](https://github.com/ArcadeData/arcadedb/issues/4967) — `Result.toJSON()`
  renders primitive arrays as Java `toString` (`"[F@..."`).
- [#4991](https://github.com/ArcadeData/arcadedb/issues/4991) — JVM cannot exit
  after a *failed* `DatabaseFactory.open()`: the non-daemon "ArcadeDB AsyncFlush"
  thread is never stopped (reproduced in pure Java, `HangRepro.java`).

## What changed in the bindings

New/changed API (all with graceful fallbacks and regression tests; suite 358 passed):

| addition | purpose |
|---|---|
| `ResultSet.to_json_list(batch_size=)` / `iter_json_batches()` | bulk materialization via batched Java-side JSON serialization — one JPype crossing per batch instead of 2+C per row. JSON-native types (temporals as ISO strings) |
| `GraphBatch.new_edges(srcs, type, dsts)` | bulk property-less edge buffering (one crossing per batch; RIDs cross as one joined string because JPype converts string *lists* per-element) |
| `Database.run_in_transaction(fn, retries=)` | auto-retry on `ConcurrentModificationException`, matching Java's `transaction(lambda)`; a `with` block cannot re-run its body |
| `ResultSet.close()` + context manager | deterministic release, Java-idiom parity (measured optional — GC handles abandoned result sets) |
| plain Python lists/tuples/sets as query params | previously failed JPype varargs overload resolution; now converted to `java.util` collections |
| `jvm.py` atexit hook | stops the engine's leaked AsyncFlush thread so failed opens can't hang interpreter exit (workaround for #4991) |

Internal: buffer-protocol bulk conversion for Java primitive arrays (900µs → ~µs per
384-float vector), a self-populating exact-type converter dispatch cache (isinstance
chain runs once per *type*), cached JClass/java.time handles, Java-RID fast path in
vector search (no string round-trip), per-wrapper index/PQ-check caching,
`export_to_csv` streaming over JSON batches.

**The bridge jar**: `RowBatcher`/`EdgeBatcher` (~200 lines,
`bindings/python/src/java/com/arcadedb/python/`) compile into
`arcadedb-python-bridge.jar` during both wheel builds (`Dockerfile.build`,
`build-native.sh`). Bindings-scoped glue over public engine APIs — no engine code is
modified; Python falls back to pure-JPype paths if the jar is absent.

## Known limits (measured, documented, deliberately not chased)

- **Full-fidelity wide scans** (`to_list`, per-row `.get`) remain 15–21× Java: the
  per-row `hasNext`/`next`/`getProperty` crossings are the floor. `to_json_list()`
  covers the bulk use case at 3.4×; going further means Arrow-style columnar
  transport — not justified by any current workload.
- **Threading** scales to ~4 threads (JPype releases the GIL during engine calls),
  plateauing at ~45k qps vs Java's 107k at 8 threads — Python's per-op share under
  the GIL is the ceiling.
- **Async per-op Python callbacks** cost ~104µs vs 5.5µs Java (GIL-bound proxy per
  completion). Submission without callbacks is at parity (8.3 vs 8.0µs); guidance:
  batch + `wait_completion()`, never per-record callbacks.
- **Record mutation** (`modify().set().save()`) is 4.9× (16.5 vs 3.4µs) — three
  crossings per record; absolute cost small, bulk paths exist.
- **List-typed columns** convert per element (467µs/384 floats; a 10k-element LIST
  property costs 14.6ms via `.get()`). Use typed array properties
  (`ARRAY_OF_FLOATS` → buffer-protocol bulk path) or `to_json_list`.
- `to_json_list`'s speed costs a transient: 214MB peak heap vs 82MB for `to_list`
  on 100k×7 (scales with `batch_size`).

## Methodology

- Java baseline (`OverheadBench.java`) runs on the wheel's own JARs and bundled
  JRE (Corretto 25) with the exact flags `jvm.py` injects — same bytecode, same VM;
  only the caller differs. Compiled via the `maven:3.9-amazoncorretto-25` image.
- Layered Python measurements (`bench_python.py`, `bench_round5.py`) separate: raw
  JPype call → argument marshaling → wrapper logic → SQL path, so deltas attribute
  to a specific layer. Result parity asserted across layers/languages.
- 20 warmup + 100 measured iterations per layer (12 reps for full scans);
  mean/p50/p95/p99. Headline claims re-measured across **5 independent processes**
  (CV 1.6–5.5%); single-run numbers are point estimates and daytime desktop load
  adds up to ~30% drift.
- Memory truth from `MemoryMXBean` after forced dual-GC + `/proc` RSS
  (`bench_memory.py`); sustained behavior via a 45-min mixed-workload soak
  (`bench_soak.py`).
- Candidate fixes were **probed before implementation** (`probe_round2.py`,
  `probe_round3.py`) — this killed two plausible-but-slower designs
  (`Result.toMap()`, string-array marshaling) before they shipped.

## Reproducing

```bash
cd bindings/python/benchmarks/jpype_overhead
./run_bench.sh              # full battery (SKIP_500K=1 to skip the big one)
# individual phases: see headers of bench_python.py / bench_round5.py /
# bench_memory.py / bench_soak.py / OverheadBench.java
```

Databases/datasets are regenerable and gitignored; `results/all_results.csv` holds
every measured line (BEFORE rows unprefixed; `AFTER,`/`ROUND2,`/`ROUND3,`/`ROUND5,`
prefixes mark re-measurements). This harness doubles as the post-upstream-sync
regression check.

---

## Appendix: round-by-round history

**Round 0 — measurement (measure-only mandate).** Built the harness; found the 15×
vector gap and attributed it exactly: `query().first()` alone = 3.32ms (Java
parity); `row.get("res")` conversion alone = 49.1ms (50 neighbors × 384-float
vectors converted per-element at ~1.1ms each). Scans 19–69×; engine-bound ops at
parity. Ranked four fixes.

**Round 1 (commit fdcf3e78db).** Buffer-protocol bulk conversion for primitive
arrays, cached java.time/JClass handles, Java-RID fast path (no
str→re-parse→re-fetch per hit), cached index/PQ checks, plain-list query params.
Vector SQL 52.8 → 4.80ms; float-array scans 4.54 → 0.59s; `lookup_by_rid` 15.3 →
4.0µs. Two test failures caught real issues (PQ memoization on empty indexes must
not stick).

**Round 2 (commit 733e76518b).** Probes first: `Result.toMap()` measured *slower*
than per-column `getProperty` (41 vs 33µs/row) — rejected. Shipped the exact-type
converter dispatch cache instead: scans −20%, List conversion 712 → 467µs, vector
SQL 4.5ms, 500k at 11.5ms (1.13×).

**Round 3 (commit f860452133).** Batched row transport: probe showed 2436 → 397ms
on 100k×7; productized as the bridge jar + `to_json_list()` (0.50s, 3.4× Java).
Found #4967 (`toJSON` float[] bug) via regression test; bridge normalizes primitive
arrays itself.

**Round 4 (commit 55a3d09e2b).** Memory investigation: no ResultSet leak (10k
undrained `.first()` queries GC to baseline, flat over 5 waves), pinning 312B/row
fully reclaimed, baseline RSS 121MB, `to_json_list` transient peak documented.
`ResultSet.close()` + context manager added as hygiene. Multi-run stats: P-SQL
5.09±0.15 vs J-SQL 4.41±0.24ms.

**Round 5 (commit ec07d39912).** Coverage audit of all 16 modules drove new phases:
UPDATE/DELETE (parity), mutation (4.9×), GraphBatch (`new_edges` bulk 4.24 →
0.57µs/edge — after discovering both a flush-pollution artifact in the first
measurement *and* that JPype marshals string lists per-element, hence the
joined-string design), threaded OLTP (crash → 44.6k qps via `run_in_transaction`;
scaling real to ~4 threads), value-shape extremes, import/export
(`export_database` parity; `export_to_csv` 2431 → 498ms), 45-min soak (flat 28MB —
no leaks), and the #4991 exit-hang engine bug (pure-Java repro; bindings atexit
workaround).

Suite growth across the arc: 346 → 358 tests, green at every commit gate.
