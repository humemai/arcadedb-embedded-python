# Performance: Python Bindings vs Java

How much do the Python bindings cost compared to calling the ArcadeDB engine
from Java? Short answer: **for engine-bound work and every bulk path, at or
near parity**; per-row Python-side work is where overhead lives, and there is
a fast bulk API for each of those cases.

## Methodology

All numbers come from a controlled benchmark: the Java baseline runs on the
**exact same JARs and bundled JRE that ship inside the wheel**, with the exact
JVM flags the bindings inject, against identical on-disk databases and query
vectors — only the caller differs. Result parity is asserted across languages
(both sides must return the same rows/neighbors before a timing is accepted).
Headline numbers were re-measured across 5 independent processes and verified
on two machines. Full evidence, raw data, and reproduction steps:
[`benchmarks/jpype_overhead/REPORT.md`](https://github.com/humemai/arcadedb-embedded-python/blob/python-embedded/bindings/python/benchmarks/jpype_overhead/REPORT.md).

## Headline results

Ratios are Python time / Java-native time (lower is better; 1.0× = parity).

| Workload | Python vs Java | Notes |
|---|---|---|
| Vector search, SQL path (100k×384, k=50) | **1.15×** (5.1ms vs 4.4ms) | was 15× before the bulk-array fixes |
| Vector search, 500k vectors | **1.13×** | |
| `find_nearest()` wrapper | **1.08×** | |
| Typed bulk scan → numpy/pandas (100k×7 cols) | **~1.6×** | `to_columns()` / `to_dataframe()` |
| Bulk scan → list of dicts (100k×7 cols) | **~2.6×** | `to_json_list()` |
| Bulk edge ingest (`GraphBatch.new_edges()`) | **0.57µs/edge** | near the 0.1µs Java floor; with properties: 1.6µs |
| Bulk vertex creation (`GraphBatch.create_vertices()`) | **parity** (6.0 vs 6.2µs/vertex) | |
| GROUP BY, Cypher traversal, BM25 full-text, JSONL export | **1.02–1.06×** | engine-bound: at parity |
| INSERT / UPDATE / DELETE (per command, in tx) | **1.2–1.9×** | fixed per-command crossing on a ~5–30µs op |
| Async command submission | **1.04×** | |

The engine itself was never slower from Python — a raw JPype call into the
engine costs the same as a Java call. All overhead lives in Python-side result
materialization and per-operation crossings, which is what the bulk APIs
eliminate.

## Choosing a materialization API

Rule of thumb: **iterate when you're selective or the result is small; use the
bulk APIs when you're taking everything from a large result.**

- `first()` — one row.
- Direct iteration + `get()` — reading some columns, live records, or early
  exit; ideal for small/medium results.
- `to_columns()` / `to_dataframe()` — fastest bulk path into numpy/pandas,
  fully typed including `datetime64`.
- `to_arrow()` — the same columnar buffer as `to_columns()`, read into a
  `pyarrow.Table` instead of numpy. Requires the `arrow` extra
  (`pip install "arcadedb-embedded[arrow]"`); returns `None` if pyarrow is
  absent, so callers can fall back. Two reasons to prefer it, only one of
  which is speed:

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
- `to_json_list()` / `iter_json_batches()` — bulk plain dicts (temporals as
  ISO strings).
- `to_list()` — full Python-type fidelity (`datetime`, `Decimal`) when the
  result is not huge.

See the [Performance and Materialization](core/queries.md#performance-and-materialization)
section of the Queries guide for the full decision list with code examples.

## Known limits

Measured limits that remain by design, and the recommended pattern for each:

| Limit | Measured | Recommended pattern |
|---|---|---|
| Per-row materialization of huge results (`to_list`, per-row `.get()`) | 15–21× Java | Use `to_columns()`/`to_dataframe()` (~1.6×) or `to_json_list()` (~2.6×) for bulk consumption |
| Threading plateaus around 4 threads (~45k qps vs Java's 107k at 8 threads) | GIL bounds Python's per-op share | Keep write concurrency at ~4 threads with `run_in_transaction(retries=)`, or use multiprocessing for more parallelism |
| Async per-operation Python callbacks | ~104µs vs 5.5µs per completion | Submit without callbacks; batch and call `wait_completion()` — submission itself is at parity |
| Record mutation (`modify().set().save()`) | 16.5µs vs 3.4µs per record | Absolute cost is small; use SQL `UPDATE` or bulk ingest paths for volume |
| List-typed columns convert per element | 14.6ms for a 10k-element LIST via `.get()` | Prefer typed array properties (e.g. `ARRAY_OF_FLOATS`) or `to_json_list()` |

## Memory

| Question | Answer |
|---|---|
| Leaks under sustained load? | No — a 45-minute soak over 2.65M mixed operations shows post-GC heap flat from minute 1 to 45 |
| Baseline footprint | ~121MB RSS after JVM start |
| "`-Xmx4g` means it uses 4GB"? | No — `-Xmx` is a ceiling, not a reservation; the heap grows only as needed |
| Bulk APIs (`to_json_list`, `to_columns`) | Transient peak scales with `batch_size` and is fully reclaimed; under a small heap they degrade gracefully (slower, no OOM) |

## Full report

The complete evidence — before/after tables, layer-by-layer attribution,
memory soak data, the completeness-verification sweep, and reproduction
scripts — lives in
[`benchmarks/jpype_overhead/REPORT.md`](https://github.com/humemai/arcadedb-embedded-python/blob/python-embedded/bindings/python/benchmarks/jpype_overhead/REPORT.md).
Numbers were verified on two machines; expect ±30% drift on a loaded desktop.
