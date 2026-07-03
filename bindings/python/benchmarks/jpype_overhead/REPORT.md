# JPype Overhead Report: Java vs Python Bindings

Date: 2026-07-04 (overnight run) · Machine: tk laptop (diagnostic numbers — NOT for
the paper; paper numbers must be re-measured on tk@mini) · Engine: 26.8.1-SNAPSHOT
wheel (`arcadedb_embedded-26.8.1.dev0`, cp312)

**Setup**: Java and Python ran the *same bytecode* — the wheel's bundled JARs on the
wheel's bundled JRE (Corretto 25.0.3) with the exact JVM flags `jvm.py` injects
(`--add-modules=jdk.incubator.vector`, `-Xmx4g`, etc.), on the same on-disk databases
and the same query vectors. Result parity verified: J-direct, P-raw-call and
P-wrapper return byte-identical top-50 RID lists. 20 warmup + 100 measured queries
per layer (12 reps for full-scan layers). Harness:
`benchmarks/jpype_overhead/{OverheadBench.java, bench_python.py, run_bench.sh}`.

## Headline: vector search (k=50, efSearch=100, 384-dim, COSINE)

Latency mean (p50) in ms:

| layer | what it measures | 100k vectors | 500k vectors |
|---|---|---|---|
| J-direct | `LSMVectorIndex.findNeighborsFromVector` from Java | 2.48 (2.37) | 12.45 (10.83) |
| J-SQL | `SELECT vectorNeighbors(...)` from Java | 3.49 (3.06) | 10.18 (9.46) |
| P-raw-call | same direct call via JPype, args pre-converted | 2.76 (2.55) | 12.11 (9.92) |
| P-rawconv | + query-vector marshaling inside timer | 2.53 (2.30) | 10.75 (8.34) |
| P-wrapper | `VectorIndex.find_nearest` (bindings wrapper) | 2.89 (2.77) | 9.83 (8.11) |
| **P-SQL** | `SELECT vectorNeighbors(?)` via `db.query` — **the example-12 / #3674 path** | **52.8 (52.3)** | **62.1 (61.1)** |

### Attribution

- **JPype call overhead is negligible**: P-raw-call ≈ J-direct at both scales
  (+0.3ms at 100k, within noise at 500k). The JVM does identical work; crossing the
  boundary per *call* is free-ish.
- **Query-vector marshaling is negligible**: ~8µs per 384-dim list (micro-bench),
  invisible at ms scale.
- **The wrapper's per-hit record re-fetch is small at k=50**: ~0.3–0.8ms
  (50 × ~15µs `lookup_by_rid`), but it is pure waste and grows linearly with k.
- **The SQL path costs ~50ms of pure Python-side materialization, flat across
  scales** (52.8−3.5 ≈ 49ms at 100k; 62.1−10.2 ≈ 52ms at 500k). Cause: each of the
  50 returned neighbors carries its full document — including the 384-float
  `vector` property — and `Result.get("res")` recursively converts everything via
  `convert_java_to_python`. Micro-bench: converting one 384-float Java list costs
  **1.12ms** → 50 × 1.12 ≈ 56ms. The benchmark (and any user of the SQL surface)
  pays ~15× Java latency to receive data it immediately discards.

**Conclusion: Luca is right and the engine is innocent.** Vector search through the
engine is at parity from Python. The 15× gap he observes is the Python bindings
converting the neighbors' embedding vectors (and other properties) element-by-element
during result materialization on the SQL path.

## Other surfaces (mean latency)

| workload | Java | Python | ratio | bottleneck |
|---|---|---|---|---|
| GROUP BY aggregation (100k rows scanned, ~14 rows out) | 72.8ms | 76.1ms | 1.05× | engine (parity) |
| Cypher traverse `*1..2` (count only) | 3.72ms | 3.94ms | 1.06× | engine (parity) |
| BM25 fulltext top-100 | 116ms | 118ms | 1.02× | engine (parity) |
| Cypher projection, 10k rows | 9.7ms | 95.4ms | **9.8×** | row materialization |
| Scan 100k rows × 1 int col | 43.5ms | 352ms | **8.1×** | per-row crossings |
| Scan 100k rows × 7 scalar cols (`.get` each) | 149ms | 2,780ms | **18.6×** | per-value conversion |
| Scan 100k rows × 7 cols (`to_dict`) | 149ms | 3,596ms | **24×** | + dict building |
| Scan 100k rows incl. 16-float array col | 66ms | 4,539ms | **69×** | list recursion |
| INSERT via SQL (per command, in tx) | 5.3µs | 10.1µs | 1.9× | per-command crossing |
| DB open | 2.0ms | 1.6ms | ~1× | parity |

Pattern: **anything engine-bound is at parity; cost scales with the number of
values crossing the boundary**, at roughly 4–30µs per value depending on type.

## Micro-benchmarks (per call)

| operation | cost |
|---|---|
| `convert_java_to_python(384-float Java list)` | **1121µs** (~2.9µs/element) |
| `lookup_by_rid` (the wrapper's per-hit re-fetch) | 15.3µs |
| `convert_java_to_python(LocalDateTime)` | 8.8µs |
| `to_java_float_array` (384-dim list / numpy row) | 8.1µs / 4.5µs |
| `convert_java_to_python(Integer)` | 5.7µs |
| `convert_java_to_python(String)` | 0.45µs |

## Empirical validation of the attribution (validate_attribution.py)

Decomposing the P-SQL path on the 100k index (same 100 queries):

| step | mean |
|---|---|
| `db.query("sql", "SELECT vectorNeighbors(?)...").first()` — engine + row crossing, no conversion | **3.32ms** (≈ J-SQL 3.49ms → parity) |
| `row.get("res")` — Python-side conversion of the 50 neighbors, alone | **49.1ms** |
| sum | 52.4ms ≈ measured P-SQL 52.8ms ✓ |

And the proposed fix #1, measured on a 384-float Java array:

| conversion | per call |
|---|---|
| `convert_java_to_python` (current, per-element recursion) | 900µs |
| `list(jarray)` (JPype bulk to list) | 78µs (11×) |
| `np.frombuffer(memoryview(jarray))` (zero-copy view) | 0.48µs (1,900×) |
| `np.asarray(jarray, dtype=np.float32)` | **0.38µs (2,370×)** |

Projected effect of fix #1 alone: P-SQL vector search 52.8ms → ~4ms, i.e. **from 15×
slower than Java to ~1.2×**.

## Ranked fixes (not implemented in this pass — measure-only)

1. **Bulk-convert float arrays in `type_conversion.py`** (biggest win, fixes the
   headline). A Java `float[]`/`List<Float>` should convert via
   `numpy.frombuffer`/JPype bulk array copy (or `memoryview(jarray)`) instead of
   per-element recursion — turns 1.12ms into ~µs. Directly fixes P-SQL vector
   search (52ms → ~4ms expected) and the 69× embedding-column scans.
2. **Lazy/optional record materialization on the vector SQL path & wrapper**:
   `find_nearest` should stop re-fetching via `str(rid)` → `to_java_rid` →
   `lookupByRID` (vector.py:319–332, core.py:238–267) and pass the Java RID
   through; offer `include_records=False` (ids+scores only). Also cache
   `_iter_lsm_indexes`/PQ-readiness per index instead of per query
   (vector.py:185–219).
3. **Flatten `convert_java_to_python` dispatch** (type_conversion.py:159–233):
   hoist the in-loop `from java.time import ...` (:186) to module scope, reorder
   the isinstance chain by frequency, and dispatch on `type(value)` via a dict
   where possible. Targets the 5.7µs/int → sub-µs, cutting scalar scans ~3–5×.
4. **Row-level bulk fetch in `results.py`**: fetch all properties in one crossing
   (e.g. `result.toMap()` Java-side) instead of one `getProperty` call per column
   per row (results.py:356–365).
5. **Per-command overhead** (write path 1.9×): lowest priority; absolute cost is
   ~5µs and users batch anyway.

## Caveats

- Laptop, single run-day, `-Xmx4g`, default ArcadeDB profile (upstream's own
  benchmark sets `PROFILE=high-performance`; neither side used it here — deltas
  are caller-side so the comparison stands).
- At 500k, J-SQL measured slightly *faster* than J-direct (10.2 vs 12.5ms mean) —
  within run-to-run variance of the adaptive efSearch path; treat direct-vs-SQL
  Java deltas as noise-level, not signal.
- 100k lifecycle create/open dominated by first-JVM-start effects in run 1; medians
  reported.
- Raw per-step logs: `benchmarks/jpype_overhead/results/*.log`; consolidated lines
  in `all_results.csv`; datasets in `data_100k/` (`data_500k/` regenerable via
  `gen_dataset.py`).
