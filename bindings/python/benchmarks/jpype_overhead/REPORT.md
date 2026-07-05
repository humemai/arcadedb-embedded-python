# Python Bindings vs Java Native: Performance & Memory Report

Measured 2026-07-03/04 · Engine 26.8.1-SNAPSHOT (lineage since renamed 26.7.2-SNAPSHOT upstream) · Maintainer laptop (diagnostic
numbers — paper-grade numbers must be re-measured on tk@mini) · Raw data:
`results/all_results.csv` · Change history: `git log bindings/python` (this work
spans commits `fdcf3e78db..686996e379`).

## Summary

Prompted by upstream's observation (discussion #3674) that vector search is fast in
Java but slow through the Python bindings, we benchmarked the bindings against
Java-native execution under strictly controlled conditions — **identical JARs,
identical bundled JRE, identical JVM flags, identical on-disk databases and query
vectors, verified identical results** — then fixed what measured slow.

Three conclusions:

1. **The engine was never the problem.** A raw JPype call into the engine costs the
   same as calling it from Java, and every engine-bound operation was at parity
   from the start. All overhead lived in the Python bindings' result-materialization
   and per-operation-crossing layers.
2. **After the fixes, every bulk path is at or near Java speed** (table below); the
   headline vector-search gap went from 15× to 1.15×.
3. **Memory is clean**: no leaks under sustained load, no meaningful Java-heap
   pinning by Python wrappers, and baseline RSS is 121MB (`-Xmx4g` is a ceiling,
   not a reservation).

Two engine bugs were found and filed upstream:
[#4967](https://github.com/ArcadeData/arcadedb/issues/4967) (`Result.toJSON()`
renders primitive arrays as `"[F@..."` — still open, worked around by the
bridge's array normalization) and
[#4991](https://github.com/ArcadeData/arcadedb/issues/4991) (JVM cannot exit after
a failed `DatabaseFactory.open()` — non-daemon "ArcadeDB AsyncFlush" thread leaks;
reproduced in pure Java; **fixed upstream in 26.7.2**, so the bindings' atexit
workaround was removed and the exit-hang regression test now guards the engine fix).

## Results: before vs. after

### Paths that were slow — measured, fixed, re-measured

| workload | Java native | Python before | Python after | fixed by |
|---|---|---|---|---|
| Vector search, SQL path (100k×384, k=50) | 4.41 ± 0.24ms | 52.8ms (15×) | **5.09 ± 0.15ms (1.15×)** | bulk array conversion + dispatch cache |
| Vector search, 500k (#3674 scale) | 10.2ms | 62.1ms (6×) | **11.5ms (1.13×)** | same |
| Bulk scan, 100k rows × 7 cols | 149ms | 4.54s (30×) | **0.50s (3.4×)** | `to_json_list()` (batched transport) |
| Scan with float-array column, 100k | 66ms | 4.54s (69×) | **0.55s (8.3×)** | buffer-protocol array conversion |
| Bulk edge ingest (GraphBatch, per edge) | 0.1µs | 4.24µs (24×) | **0.57µs** | `new_edges()` bulk API |
| Bulk edge ingest with per-edge properties | — | 24.2µs | **1.6 ± 0.3µs (15×)** | `new_edges(properties=)` (JSON rows) |
| Bulk vertex creation (GraphBatch, per vertex) | 6.2µs | 22.3µs | **6.0 ± 0.3µs (parity)** | JSON-rows bridge path in `create_vertices()` |
| Typed bulk scan → numpy/pandas, 100k × 7 | 149ms | 3.44s via `to_list` | **240 ± 7ms (1.6×)** | `to_columns()` binary columnar transport; `to_dataframe()` rides it |
| CSV export, 100k rows | — | 2431ms | **498ms** | streaming over JSON batches |
| Threaded OLTP writers, 8 threads | 106.6k qps | crash (no retry) | **44.6k qps** | `run_in_transaction(retries=)` |
| `find_nearest` wrapper | 2.48ms (direct) | 2.89ms | **2.69ms (1.08×)** | RID fast path, cached index checks |
| Failed `open_database` → process exit | hangs (engine bug #4991) | hangs | **exits cleanly** | atexit workaround, since replaced by the upstream 26.7.2 fix |
| Plain Python list as query parameter | — | error (overload resolution) | **works** | collection conversion in `_convert_args` |

### Paths that were already at parity (no fix needed)

| workload | Java | Python | ratio |
|---|---|---|---|
| GROUP BY over 100k rows | 72.8ms | 76.1ms | 1.05× |
| Cypher traversal `*1..2` (count) | 3.7ms | 3.9ms | 1.06× |
| BM25 full-text top-100 | 116ms | 118ms | 1.02× |
| UPDATE / DELETE (indexed, per op) | 33.3 / 14.4µs | 40.6 / 18.3µs | 1.2× / 1.3× |
| INSERT (per command, in tx) | 5.3µs | 10.1µs | 1.9× on a 5µs op |
| `export_database` (JSONL, full DB) | 698ms | 711ms | 1.02× |
| Async command submission | 8.0µs | 8.3µs | 1.04× |
| DB create/open/first-query | ~ms | ~ms | ~1× |

### Memory

| question | verdict | evidence |
|---|---|---|
| Leaks under sustained load? | **No** | 45-min soak, 2.65M mixed ops: post-GC heap flat at 28MB from minute 1 to 45 |
| Unclosed/undrained ResultSets leak? | **No** | 10k undrained `.first()` queries GC to baseline, flat over repeated waves |
| Python wrappers pin Java heap? | **Negligible** | ~312 bytes/row while held, fully reclaimed on release |
| "Python uses gigabytes" | **Perception** | RSS after JVM start: 121MB; `-Xmx4g` is a max, not an allocation |
| `to_json_list` transient cost | **Real, bounded** | peak heap 214MB vs 82MB for `to_list` on 100k×7; scales with `batch_size` |

## What changed in the bindings

New/changed public API (all with fallbacks and regression tests; suite 352 passed after the embedded-only cut):

- `ResultSet.to_json_list(batch_size=)` / `iter_json_batches()` — bulk
  materialization via batched Java-side JSON serialization: one JPype crossing per
  batch instead of several per row. JSON-native types (temporals as ISO strings);
  `to_list()` remains the full-fidelity path.
- `GraphBatch.new_edges(srcs, type, dsts)` — bulk property-less edge buffering.
  RIDs cross as one semicolon-joined string: JPype converts a Python *list* of
  strings element-by-element, which would eat the batching win.
- `Database.run_in_transaction(fn, retries=)` — auto-retry on
  `ConcurrentModificationException`, matching Java's `transaction(lambda)`
  semantics (a `with` block cannot re-run its body).
- `ResultSet.close()` + context-manager support — deterministic release, Java-idiom
  parity (measured optional: GC handles abandoned result sets).
- Plain Python lists/tuples/sets now work as query parameters.
- `jvm.py` atexit hook — stopped the engine thread leaked by failed opens
  (#4991 workaround); removed once the engine fixed the root cause in 26.7.2.
  The subprocess regression test remains.
- `ResultSet.to_columns(batch_size=)` — binary columnar transport
  (`ColumnBatcher`; temporals incl. OffsetDateTime, storable since engine
  26.7.2): typed numpy columns (int64/float64/bool/datetime64[ms]),
  pandas-convention nulls, per-column JSON fallback for exotic types;
  `to_dataframe()` uses it automatically. Full type fidelity INCLUDING real
  datetimes — faster than the JSON path and typed, superseding the
  fidelity-vs-speed trade-off for scans.
- `new_edges(properties=)` and a JSON-rows bulk path inside `create_vertices()` —
  GraphBatch ingest with properties in one crossing per batch.

**Post-release regression, caught and fixed** (`bc9ec743f4`): the plain-list
parameter conversion initially broke the historical "a single list argument is
the positional-parameter array" idiom, silently null-ing multi-`?` INSERTs.
Found by running the real examples (the suite had no coverage for the idiom —
it does now). Single list/tuple → expands to N parameters; collections among
multiple args → single collection parameter.

Internal: buffer-protocol bulk conversion for Java primitive arrays (900µs → ~µs
per 384-float vector); a self-populating exact-type converter dispatch cache (the
isinstance chain runs once per *type*, not per value); cached JClass/java.time
handles; Java-RID fast path in vector search (no string round-trip + re-fetch per
hit); per-wrapper index/PQ-check caching; `export_to_csv` streams JSON batches.

**The bridge jar.** `RowBatcher`/`EdgeBatcher`/`VertexBatcher`/`ColumnBatcher` (~450 lines,
`bindings/python/src/java/com/arcadedb/python/`) compile into
`arcadedb-python-bridge.jar` during both wheel builds (`Dockerfile.build` and
`build-native.sh`) and ship inside the wheel next to the engine JARs. They are
bindings-scoped glue over public engine APIs — no engine code is modified — and the
Python side falls back to pure-JPype paths if the jar is absent.

## Known limits (measured, documented, deliberately not pursued)

- **Per-row materialization** (`to_list`, per-row `.get`) remains 15–21× Java —
  the per-row crossing floor. Every *bulk* use case now has a fast typed exit:
  `to_columns()`/`to_dataframe()` at 1.6× (full fidelity incl. datetime64) or
  `to_json_list()` at ~2.6×. The remaining gap only matters for row-at-a-time
  streaming consumption of huge results, which has no known customer.
- **Threading** scales to ~4 threads (JPype releases the GIL during engine calls)
  and plateaus at ~45k qps vs Java's 107k at 8 threads — Python's per-op share
  under the GIL is the ceiling.
- **Async per-op Python callbacks** cost ~104µs vs 5.5µs (GIL-bound proxy per
  completion). Submission without callbacks is at parity — batch +
  `wait_completion()`, never per-record callbacks.
- **Record mutation** (`modify().set().save()`): 16.5 vs 3.4µs (three crossings per
  record); absolute cost is small and bulk paths exist.
- **List-typed columns** convert per element (a 10k-element LIST property costs
  14.6ms via `.get()`). Prefer typed array properties (`ARRAY_OF_FLOATS` takes the
  bulk path) or `to_json_list()`.
- Cypher row-returning projections inherit the full-fidelity scan cost (9.2×);
  `to_json_list()` applies there too.

## Methodology

- The Java baseline (`OverheadBench.java`) runs on the wheel's own JARs and bundled
  JRE (Corretto 25) with the exact flags `jvm.py` injects — same bytecode, same VM,
  only the caller differs.
- Layered measurement (`bench_python.py`, `bench_round5.py`) separates raw JPype
  call → argument marshaling → wrapper logic → SQL path, so every delta attributes
  to a specific layer. Result parity is asserted across layers and languages.
- 20 warmup + 100 measured iterations per layer (12 reps for full scans), reporting
  mean/p50/p95/p99. Headline claims re-measured across **5 independent processes**
  (CV 1.6–5.5%). Single-run numbers are point estimates; desktop load adds up to
  ~30% drift.
- Memory: `MemoryMXBean` after forced dual-GC + `/proc` RSS (`bench_memory.py`);
  sustained behavior via a 45-min mixed-workload soak (`bench_soak.py`).
- Candidate fixes were probed before implementation (`probe_round2.py`,
  `probe_round3.py`); two plausible designs measured slower and were rejected
  (`Result.toMap()`, string-array marshaling).

## Wheel-size audit (2026-07-05)

Same quarantine-and-gate method applied to the wheel contents (82MB → **70.8MB**):

- **Cut (~11MB, feature-preserving; verified by full suite incl. server tests +
  examples run)**: `arcadedb-tracing` (4.4MB), `snappy-java` (2.4MB, engine uses
  LZ4 not snappy), `jackson-*` (2.1MB), `commons-math3` (2.0MB, zero users),
  `jline` (0.4MB, console-only). `micrometer` must stay — server startup
  requires it (found by bisection).
- **Kept deliberately**: Lucene stack (~7.5MB — FULL_TEXT tokenization +
  geospatial genuinely use it), JTS (geospatial).
- **Server mode removed (follow-up decision, 2026-07-05)**: the
  server/studio/undertow/xnio/micrometer set (~7.7MB uncompressed) was
  initially kept under the "small fraction" bar, then cut when the maintainer
  opted for an embedded-only package: wheel **70.8MB → 63.5MB**, 51 JARs.
  The official ArcadeDB server distribution is the supported client-server
  path. (micrometer's only consumer was server startup, so it went too.)
- **JRE lever**: initially judged dead — with the server jars present, the
  jdeps-detected module set measured within 1MB of the `java.se` umbrella.
  The audit also found the jdeps detection had been **silently broken** —
  `lucene-spatial-extras` declares a missing module and aborted the whole scan,
  so builds always used the fallback. Fixed in both build scripts (excluded from
  the scan, like jboss/wildfly). After the server removal the detected set
  shrank well below `java.se`, so the umbrella was dropped (2026-07-05):
  jlink now builds from the detected 16 modules — wheel **63.5MB → 61.6MB**,
  gated by the full suite + examples. Floor reached: the remaining candidates
  (java.desktop is statically required by jts-core/commons-lang3; native-symbol
  stripping; Lucene sub-jar bisection) are crumbs or rule-violations.

## Paper-grade verification on tk@mini (2026-07-05)

Independent machine (20 cores, idle), 5 runs/layer, same wheel:

| layer | mini | laptop | verdict |
|---|---|---|---|
| Vector J-SQL / P-SQL | 4.08 ± 0.17 / **4.45 ± 0.09ms (1.09×)** | 4.41 / 5.09 (1.15×) | replicated, tighter |
| J-direct / P-wrapper | 2.63 ± 0.06 / 2.91 ± 0.03ms (1.11×) | 2.48 / 2.69 (1.08×) | replicated |
| 100k×7 scan: Java / `to_columns` / `to_json_list` | 161 / **263 (1.63×)** / 398ms | 149 / 240 / ~390ms | replicated |
| `to_list` slow path | 3560ms (22×) | 3441ms (23×) | replicated |

## Appendix: completeness-verification sweep (2026-07-04, final)

After the fixes landed, an adversarial audit asked what the harness itself had
NOT covered. Each identified gap was then measured:

| audited gap | verdict | evidence |
|---|---|---|
| Memory of the new bulk APIs (`to_columns`) | **clean** | transient peak 180MB (vs 214 JSON / 82 to_list); 5 repeated-call waves GC flat at 27MB — no leak |
| Memory of bulk GraphBatch ingest | **clean** | 20k vertices + 60k prop-edges: peak 140MB during, returns to 22MB after close |
| Converter-cache boundedness | **bounded** | 8 dispatch-cache entries + 0 lazy JClass entries after a full mixed-type workload |
| Does the columnar ratio hold at 10× scale? | **yes, linear** | 1M×7-col: `to_columns` 2.64s (100k was 0.24s — 11× time for 10× rows); `to_json_list` 5.2s; Java all-column baseline 1.31s. All-column shapes (incl. array columns → JSON fallback) run ~2× slower than pure-scalar shapes — select columns explicitly for max speed |
| Very wide rows (50 columns × 10k) | **columnar wins grow with width** | `to_columns` 91ms vs JSON 211ms vs per-row `.get` 1010ms (11×) |
| Chunking actually exercised (>100k rows/batch) | **works** | 1M bulk edges at 1.69µs/edge (matches the 60k-scale 1.6µs), all 1M created |
| Tail latency (n=10k, not n=100) | **tight** | 2k-row `to_columns`: p50 2.4ms, p99 7.8ms, p99.9 9.6ms, max 15.6ms; 189 GC collections across 10k ops — spikes GC-correlated and bounded at ~6× median |
| Write-direction conversion (never measured) | **fine** | `convert_python_to_java`: dict(10) 41µs, list(100) 74µs, datetime 0.9µs, 1MB str 0.2µs — invisible next to per-command costs |
| Behavior under heap pressure | **graceful** | 100k×7 `to_columns` with `-Xmx512m`: completes (no OOM), 719ms (3× the 4g time), 30 GCs — chunking bounds Java-side buffers |
| Sustained soak incl. new APIs + threads (2h, 4.31M ops) | **bounded** | post-GC heap plateaus in a 758–990MB oscillating band with no monotonic trend through the final 4-thread window; the rise from v1's 28MB is the engine page cache legitimately tracking the workload's own database growth (the mix's graph-ingests grew the DB past 7GB), not a bindings leak |

One methodology lesson from the sweep: the v2 soak's graph-ingest ops grow the
database itself (7GB over the run), so the engine's page cache legitimately
grows with it — "flat heap" is only a valid pass criterion for non-growing
workloads; for growing ones the criterion is a plateau below the cache cap.

## Reproducing

```bash
cd bindings/python/benchmarks/jpype_overhead
./run_bench.sh              # full battery (SKIP_500K=1 to skip the big one)
# individual phases: see headers of bench_python.py / bench_round5.py /
# bench_memory.py / bench_soak.py / OverheadBench.java
```

Databases and datasets are regenerable and gitignored; `results/all_results.csv`
holds every measured line. This harness doubles as the post-upstream-sync
regression check: run it after large engine syncs and compare against the tables
above.
