# Performance: Python Bindings vs Java

How much do the Python bindings cost compared to calling the ArcadeDB engine
from Java? Short answer: **for engine-bound work and every bulk path, at or
near parity**; per-row Python-side work is where overhead lives, and there is
a fast bulk API for each of those cases.

## Methodology

All numbers come from a controlled benchmark: the Java baseline runs on the
**exact same JARs and bundled JRE that ship inside the wheel**, with the exact
JVM flags the bindings inject, against identical on-disk databases and query
vectors; only the caller differs. Result parity is asserted across languages
(both sides must return the same rows/neighbors before a timing is accepted).
Headline numbers were re-measured across 5 independent processes and verified
on two machines. Full evidence, raw data, and reproduction steps:
[`benchmarks/python-bindings/jpype_overhead/REPORT.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/python-bindings/jpype_overhead/REPORT.md).

## Headline results

Ratios are Python time / Java-native time (lower is better; 1.0× = parity).

| Workload | Python vs Java | Notes |
|---|---|---|
| Vector search, SQL path (100k×384, k=50) | **1.15×** (5.1ms vs 4.4ms) | |
| Vector search, 500k vectors | **1.13×** | |
| `find_nearest()` wrapper | **1.08×** | |
| Typed bulk scan → numpy/pandas (100k×7 cols) | **~1.6×** | `to_columns()` / `to_dataframe()` |
| Bulk scan → list of dicts (100k×7 cols) | **~2.6×** | `to_json_list()`; `to_list()` reads rows the same way, with `date`, `datetime`, and `Decimal` values |
| Bulk edge ingest (`GraphBatch.new_edges()`) | **0.57µs/edge** | near the 0.1µs Java floor; with properties: 1.6µs |
| Bulk vertex creation (`GraphBatch.create_vertices()`) | **parity** (6.0 vs 6.2µs/vertex) | |
| GROUP BY, Cypher traversal, BM25 full-text, JSONL export | **1.02–1.06×** | engine-bound: at parity |
| INSERT / UPDATE / DELETE (per command, in tx) | **1.2–1.9×** | fixed per-command crossing on a ~5–30µs op |
| Async command submission | **1.04×** | |

The engine itself was never slower from Python: a raw JPype call into the
engine costs the same as a Java call. All overhead lives in Python-side result
materialization and per-operation crossings, which is what the bulk APIs
eliminate.

Per-operation crossings were cut for single-row work too. A statement with plain
scalar or Java-array parameters, `ResultSet.first()`, `Result.get()`, and
`Database.lookup_by_key()` each cross into the JVM once where they used to cross
two to six times (laptop, P cores 0-3, median of 11 interleaved runs, µs per call, wall):

| Single-row operation | Before | After |
|---|---|---|
| `query()` by key plus `first()` | 9.3 | 8.2 |
| `lookup_by_key()` | 12.2 | 4.6 |
| `command()` UPDATE, named parameters | 14.2 | 12.5 |
| `command()` UPDATE, positional parameters | 17.0 | 15.2 |
| `command()` INSERT with a vector parameter | 17.3 | 14.3 |
| Three-statement transaction | 61.0 | 55.7 |

Reading rows and walking the graph cross the JVM once per batch or per call now.
`ResultSet.to_list()` and `iter_dicts()` read rows through the bridge's `TypedRows`: Java writes
each batch as JSON, tags the values JSON cannot carry exactly (`DECIMAL`, `DATE`, `DATETIME`,
sets) and hands over everything else (RIDs, embedded documents, `float[]`) as the engine's own
object, so every value has the Python type it had before. `Vertex.get_out_edges()`,
`get_in_edges()`, `get_both_edges()`, and vector search results cross once per call instead of
once per edge or per hit. Laptop, P cores 0-3, 9 interleaved rounds per arm after a warm-up
round, medians (min-max) of the clean rounds, wall time per call; the ratio is the median of
the per-round ratios with its 95% interval:

| Operation | Before | After | After / before (95% interval) |
|---|---|---|---|
| `to_list()`, 10,000 rows x 9 mixed columns | 261.5 ms (253.7-271.2) | 36.9 ms (34.3-40.0) | 0.141 (0.135-0.142) |
| `to_list()`, 100 rows | 2.70 ms (2.63-2.85) | 0.44 ms (0.37-0.53) | 0.160 (0.146-0.183) |
| `to_list()`, 1 row | 85.0 us (83.4-96.4) | 74.8 us (64.4-82.1) | 0.854 (0.783-0.933) |
| `to_list()`, 2,000 rows of a 128-float vector | 19.0 ms (18.2-21.0) | 8.4 ms (8.0-9.8) | 0.440 (0.426-0.461) |
| `iter_dicts()`, 10,000 rows x 9 mixed columns | 279.1 ms (274.1-291.3) | 78.8 ms (78.0-84.0) | 0.278 (0.276-0.283) |
| `iter_dicts()`, 100 rows | 2.84 ms (2.78-2.95) | 0.86 ms (0.84-1.06) | 0.305 (0.295-0.314) |
| `iter_dicts()`, 1 row | 85.7 us (78.5-90.9) | 70.3 us (64.5-75.3) | 0.825 (0.790-0.876) |
| `get_out_edges()`, 5 edges per vertex | 12.0 us | 7.0 us | 0.557 (0.515-0.620) |
| `find_nearest()`, k = 100, 128 dimensions | 0.60 ms | 0.28 ms | 0.467 (0.436-0.546) |
| `find_nearest()`, k = 10, 128 dimensions | 0.24 ms | 0.21 ms | 0.880 (0.828-0.931) |

`to_json_list()` on the same 10,000-row scan took 32.2 ms in the same runs, so `to_list()` now
costs about the same and keeps the Python types.

## Choosing a materialization API

Rule of thumb: **iterate when you're selective or the result is small; use the
bulk APIs when you're taking everything from a large result.** The
[Performance and Materialization](core/queries.md#performance-and-materialization)
section of the Queries guide has the full decision list with code examples. The
one choice it does not weigh is `to_arrow()` against `to_columns()`:

`to_arrow()` reads the same columnar buffer as `to_columns()` into a
`pyarrow.Table` instead of numpy. It requires the `arrow` extra
(`pip install "arcadedb-embedded[arrow]"`) and returns `None` if pyarrow is
absent, so callers can fall back. There are two reasons to prefer it, only one
of which is speed:

**Types survive nulls.** `to_columns()` follows pandas conventions, so a
nullable `int64` column is promoted to `float64`/NaN, which loses the type
and loses precision above 2^53, and a nullable boolean degrades to a Python
list. Arrow carries a validity bitmap, so both keep their type.

**Strings are wrapped, not decoded.** The buffer already holds int32 offsets
plus a UTF-8 blob, which is exactly Arrow's string layout, so no per-row
`str` is built.

Time to a `pandas.DataFrame`, which is what a caller actually pays. 100k
rows, median of 5 after 2 warmups, one idle Linux host pinned to 12 CPUs,
`scripts/arrow_transport_probe.py`:

| result shape | `to_columns()` → df | `to_arrow()` → df | speedup |
|---|---|---|---|
| numeric only | 55.9 ms | 56.8 ms | **0.98×** |
| strings | 117.8 ms | 67.4 ms | **1.75×** |
| mixed, with nulls | 74.8 ms | 52.7 ms | **1.42×** |

So on purely numeric results `to_arrow()` is a wash and `to_columns()` is
fine. The speedup is not Arrow being faster in general, it is the string
decode and the null promotion not happening. Pick it for what your columns
are, not by default.

## Known limits

Measured limits that remain by design, and the recommended pattern for each:

| Limit | Measured | Recommended pattern |
|---|---|---|
| Per-row `.get()` loops over huge results | Each `get()` is a crossing into the JVM (about 1.5 us) | Use `to_list()` (261 ms to 37 ms on a 10,000-row, nine-property scan), `to_columns()`/`to_dataframe()` (~1.6×), or `to_json_list()` (~2.6×) for bulk consumption |
| Threading plateaus around 4 threads (~45k qps vs Java's 107k at 8 threads) | GIL bounds Python's per-op share | Keep write concurrency at ~4 threads with `run_in_transaction(retries=)`, or use multiprocessing for more parallelism |
| Async per-operation Python callbacks | ~104µs vs 5.5µs per completion | Not a bulk-write path; see [Bulk Ingest Recommendation](import.md#bulk-ingest-recommendation). Use `insert_many()`, `insert_columns()`, or `graph_batch()` for volume |
| Values pasted into the query text (`f"... WHERE id = {x}"`) | Indexed point lookup, 20k records: Cypher 0.87 ms vs 0.09 ms bound, SQL 0.48 ms vs 0.09 ms | Bind them: `?`/`:name` in SQL, `$name` in Cypher. Every distinct text is parsed again and churns the statement cache ([queries guide](core/queries.md#parameters)) |
| Record mutation (`modify().set().save()`) | 16.5µs vs 3.4µs per record | Absolute cost is small; use SQL `UPDATE` or bulk ingest paths for volume |
| List-typed columns convert per element via `.get()` | 14.6ms for a 10k-element LIST via `.get()` | Read the row with `to_list()`, or prefer typed array properties (e.g. `ARRAY_OF_FLOATS`) |

## Memory

| Question | Answer |
|---|---|
| Leaks under sustained load? | Not in the JVM: a 45-minute soak over 2.65M mixed operations shows post-GC heap flat from minute 1 to 45. On the Python side, JPype 1.7.1 keeps a Python object for every number that `Result.get()` returns (`to_list()` reads numbers from JSON text and does not); see [Known Engine Issues](known-issues.md) |
| Baseline footprint | ~121MB RSS after JVM start |
| "`-Xmx4g` means it uses 4GB"? | No: `-Xmx` is a ceiling, not a reservation; the heap grows only as needed |
| Bulk APIs (`to_json_list`, `to_columns`) | Transient peak scales with `batch_size` and is fully reclaimed; under a small heap they degrade gracefully (slower, no OOM) |

## Full report

The complete evidence (before/after tables, layer-by-layer attribution,
memory soak data, the completeness-verification sweep, and reproduction
scripts) lives in
[`benchmarks/python-bindings/jpype_overhead/REPORT.md`](https://github.com/humemai/arcadedb-embedded-python/blob/main/benchmarks/python-bindings/jpype_overhead/REPORT.md).
Numbers were verified on two machines; expect ±30% drift on a loaded desktop.
