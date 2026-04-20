# ArcadeDB Python Bindings Thin-Layer Audit

Date: 2026-04-19

Scope: `bindings/python/src/arcadedb_embedded`

Goal: evaluate whether the Python bindings remain a thin JPype layer over the embedded Java engine, with particular attention to:

- Python-side memory growth
- Python-side computation that should stay in Java
- eager conversion or materialization of Java data into Python objects
- convenience APIs that are reasonable vs APIs that should be tightened

## Current Status

Short version: the package is mostly architected the right way.

- Core database operations stay in Java and are surfaced lazily in Python.
- The main `Database.query()` and `Database.command()` paths return `ResultSet` wrappers rather than preloading all rows into Python at call time. See `core.py:54`, `core.py:63`, and `core.py:78`.
- The embedded runtime model is explicitly in-process JPype, so the Python process owns the JVM as part of the same OS process. See `jvm.py:104` and `jvm.py:228`.
- Document, vertex, edge, async, schema, import, export, and vector APIs are primarily wrapper-oriented, not reimplementations of engine behavior.

That said, the bindings are not thin in a strict end-to-end sense. They are better described as:

"thin by default in the core query/update path, but with a non-trivial convenience layer that eagerly converts and materializes data when asked."

That is not inherently wrong. It becomes a problem when convenience behavior leaks into normal, large-scale usage.

## What "Thin" Should Mean Here

For this project, a thin binding should follow these rules:

1. Query planning, index logic, graph traversal, vector search internals, and storage operations stay in Java.
2. Python mostly passes arguments, owns lightweight wrappers, and exposes ergonomic APIs.
3. Python should not eagerly copy large result sets, nested collections, or vector outputs unless the caller explicitly opts into a Python-native representation.
4. Any method that materializes large Python structures should be clearly marked as a convenience API, not the default hot path.

By that standard, the codebase is directionally correct but still has room to tighten the boundary.

## Important Framing: "Python Memory" vs JVM Memory

Because this package embeds the JVM with JPype, users will often attribute total process memory to "Python" even when the memory is actually Java heap or JVM-managed native state.

- JVM startup is in-process in `jvm.py:228`.
- Default heap handling adds `-Xmx4g` when no heap override is provided in `jvm.py:377`.
- The code also adds compact object headers when available in `jvm.py:365` and `jvm.py:366`.

Conclusion: the Python layer should stay small, but the overall process can still legitimately be large. This is expected for an embedded Java engine. The real question is whether Python is adding avoidable overhead on top of that JVM footprint.

## Module-by-Module Assessment

### 1. `core.py`

Status: good thin-wrapper foundation.

What is good:

- `Database.query()` and `Database.command()` return `ResultSet` wrappers instead of materialized rows. See `core.py:54`, `core.py:63`, and `core.py:78`.
- `DatabaseFactory` is a direct Java wrapper around `com.arcadedb.database.DatabaseFactory`. See `core.py:927` and `core.py:929`.
- Lookup and record wrapping stay mostly lightweight.

Where Python still does extra work:

- `lookup_by_key()` builds Java arrays in Python in `core.py:197` and `core.py:198`.
- vector index creation serializes metadata through JSON in `core.py:427`.

Assessment:

- This is acceptable bridge work.
- `core.py` is not the main problem area.

### 2. `jvm.py`

Status: appropriate ownership of JVM lifecycle.

What is good:

- Centralized JVM startup and configuration in `jvm.py:104` and `jvm.py:286`.
- Explicit heap and argument handling is the right place for this concern.

What matters for profiling:

- Default heap insertion in `jvm.py:377` means process size can be substantial even when Python itself is thin.

Assessment:

- Keep this model.
- The main improvement here is documentation and profiling clarity, not architectural change.

### 3. `graph.py`

Status: mostly thin wrappers with a materializing convenience layer.

What is good:

- `Document` stores the underlying Java record directly.
- property reads delegate to Java and convert only the requested value. See `graph.py:44` and `graph.py:48`.

Where Python gets heavier:

- `get_property_names()` eagerly converts the Java property-name collection to a Python list in `graph.py:78` and `graph.py:80`.
- `to_dict()` materializes the entire document into a Python dict in `graph.py:90` and `graph.py:92`.

Assessment:

- The base wrapper is thin.
- `to_dict()` is useful, but it is explicitly not thin.
- Property-name caching or lazy iteration would improve repeated access.

### 4. `results.py`

Status: mixed; lazy iterator core is good, but convenience APIs are a major materialization hotspot.

What is good:

- `ResultSet` itself is lazy.
- `__next__()` wraps one Java result at a time instead of preloading the full set.

Where Python gets heavy:

- `to_list()` materializes the full result set in `results.py:29` and `results.py:47`.
- `to_dataframe()` materializes via `to_list()` first in `results.py:49` and `results.py:77`.
- `iter_chunks()` is better than `to_list()`, but still converts each row to dicts in `results.py:79` and `results.py:102`.
- `property_names` and `get_property_names()` each call `list(self._java_result.getPropertyNames())` in `results.py:292` and `results.py:307`.
- `Result.to_dict()` materializes every property in `results.py:309`.
- `Result.__repr__()` also forces `to_dict()` in `results.py:350`, which is expensive for a debug representation.

Assessment:

- This is the highest-value refactor area if the goal is to be more consistently thin.
- The lazy iterator is good.
- The dict/list/DataFrame helpers should be treated as explicit opt-in materializers.

### 5. `type_conversion.py`

Status: functionally useful, but this is the main boundary-crossing layer where Java collections become Python collections.

What is good:

- Centralizing conversion logic here is the right design.
- Scalar conversions are appropriate and low risk.

Where Python gets heavy:

- `convert_java_to_python()` recursively converts maps, sets, lists, and general collections into Python containers in `type_conversion.py:128`, `type_conversion.py:221`, `type_conversion.py:227`, `type_conversion.py:230`, `type_conversion.py:233`, and `type_conversion.py:241`.
- `convert_python_to_java()` recursively creates Java collections in `type_conversion.py:250`, `type_conversion.py:279`, `type_conversion.py:287`, and `type_conversion.py:295`.

Assessment:

- This is reasonable for ergonomic APIs.
- It is not thin, and it should not be on a hot path unless the caller explicitly wants native Python objects.
- A future lazy or raw mode would improve large nested payload handling.

### 6. `vector.py`

Status: Java still performs the hard vector work, but Python does more result handling than ideal.

What is good:

- Search calls delegate to Java indexes.
- Vector graph logic, neighbor search, and similarity functions stay in the engine.

Where Python gets heavier:

- `to_java_float_array()` converts incoming vectors through Python lists in `vector.py:13` and `vector.py:39`.
- `to_python_array()` converts Java arrays to Python list or NumPy in `vector.py:45` and `vector.py:59`.
- `_wrap_pair_results()` builds a Python list of `(record, score)` tuples in `vector.py:267` and `vector.py:268`.
- `_collect_search_results()` aggregates across indexes and extends a Python list in `vector.py:317` and `vector.py:338`.
- `_sort_results()` sorts in Python in `vector.py:314`.

Assessment:

- The engine remains in charge of vector search itself, which is good.
- Python still does post-processing and aggregation that may become noticeable for larger `k` or multi-index cases.
- This is a good candidate for tightening if vector search becomes a performance focus.

### 7. `schema.py`

Status: acceptable wrapper with some eager list creation and verbose array bridging.

What is good:

- The schema API is mostly a Pythonic facade over Java schema calls.
- Type and index creation logic stays in Java.

Where Python gets heavier:

- `get_types()` materializes all types with `list(...)` in `schema.py:293`.
- index creation manually constructs Java string arrays in `schema.py:501` and `schema.py:560`.
- `get_indexes()` materializes all indexes in `schema.py:612`.
- vector index discovery iterates all schema indexes in `schema.py:721`.

Assessment:

- Mostly acceptable.
- This module is not a primary bottleneck, but there is cleanup room around manual `JArray` building and eager list conversion.

### 8. `async_executor.py`

Status: architecturally appropriate, but it intentionally routes work through Python callbacks.

What is good:

- Async execution itself stays in Java.
- Python serves as a callback bridge.

Where Python gets heavier:

- some key-based edge creation paths first convert iterables into lists in `async_executor.py:317`.
- multiple argument arrays are built through Python lists and `JObjectArray` in `async_executor.py:337` and `async_executor.py:340`.
- async result handling loops through every Java result row in Python callbacks in `async_executor.py:710` and `async_executor.py:711`.

Assessment:

- This is acceptable if the feature goal is Python callbacks.
- It is not "thin" in the sense of zero Python involvement, but that is inherent to callback-based APIs.
- The main improvement area is reducing unnecessary intermediate Python lists before building Java arrays.

### 9. `graph_batch.py`

Status: mostly a builder wrapper, but batch property conversion is eager.

What is good:

- Batch creation and ingestion are delegated to Java.
- This is still a wrapper around a Java ingest API, not a Python reimplementation.

Where Python gets heavier:

- `_to_java_property_matrix()` builds nested Python and Java arrays eagerly in `graph_batch.py:244`, `graph_batch.py:247`, `graph_batch.py:255`, and `graph_batch.py:257`.

Assessment:

- Acceptable for current functionality.
- If very large property matrices become common, this is a candidate for streaming or chunked handoff.

### 10. `importer.py`

Status: good wrapper with modest conversion overhead.

What is good:

- Import execution is delegated to the Java importer.
- runtime async settings are managed on the Java side.

Where Python gets heavier:

- settings are copied into a Java `HashMap` in `importer.py:135`.
- import statistics are recursively converted back to Python via `_java_value_to_python()` in `importer.py:241`, `importer.py:247`, and `importer.py:252`.

Assessment:

- Reasonable and expected.
- Not a priority refactor area.

### 11. `exporter.py`

Status: appropriate wrapper with acceptable result conversion.

What is good:

- database export is delegated to Java exporter classes.
- CSV export supports chunked result processing through `iter_chunks()`.

Where Python gets heavier:

- settings are copied into a Java `HashMap` in `exporter.py:114` and `exporter.py:116`.
- exporter results are copied back into a Python dict in `exporter.py:126`.
- CSV export still materializes chunk dicts from `ResultSet` rows in `exporter.py:193`.

Assessment:

- This is acceptable convenience behavior.
- Not a major concern relative to `results.py` and `type_conversion.py`.

### 12. `server.py`

Status: thin, straightforward wrapper.

- JVM startup is delegated centrally in `server.py:40`.
- config translation is shallow and reasonable in `server.py:71`.
- server lifecycle methods call Java directly.

One caution:

- the `__del__` finalizer in `server.py:102` is pragmatic, but object finalizers are never a strong lifecycle guarantee.

Assessment:

- This module is fine.

### 13. `transactions.py`, `__init__.py`, `exceptions.py`, `citation.py`

Status: thin or negligible.

- `transactions.py` is a minimal context-manager wrapper.
- `__init__.py` is just API surface export.
- these are not contributing meaningfully to memory or computation concerns.

## Classification Summary

### Already Thin Enough

- `core.py`
- `jvm.py`
- `server.py`
- `transactions.py`
- `__init__.py`
- most of `importer.py`
- most of `exporter.py`

### Acceptable Convenience Layer

- `graph.py` `to_dict()` and property-name helpers
- `results.py` `iter_chunks()`
- `schema.py` list-returning helper methods
- `graph_batch.py` property-matrix conversion
- callback bridging in `async_executor.py`

### Strongest Refactor Candidates

- `results.py` full materializers and repeated property-name list creation
- `type_conversion.py` recursive eager collection conversion
- `vector.py` Python-side aggregation and sorting of search results

## What We Can Do Better

### Priority 1: Make materialization explicit, not ambient

Problem:

- `to_list()`, `to_dict()`, `to_dataframe()`, and recursive type conversion make it easy for users to accidentally pay a large Python memory cost.

What to do:

1. Document these methods as eager materializers.
2. Add raw or lazy alternatives that preserve Java-backed values where practical.
3. Prefer streaming examples in docs for large result sets.

Suggested direction:

- keep `ResultSet` lazy by default
- keep `Result.get()` scalar-friendly
- make full row and nested-collection conversion more obviously opt-in

### Priority 2: Cache repeated metadata lookups

Problem:

- property-name collections are repeatedly converted to Python lists in both `graph.py` and `results.py`.

What to do:

1. Cache property names on first access for `Document` and `Result` wrappers.
2. Avoid recomputing them inside `to_dict()` and `__repr__()`.

Expected benefit:

- less repeated allocation
- lower overhead in common inspection and serialization paths

### Priority 3: Reduce Python-side vector post-processing

Problem:

- vector search results are aggregated and sorted in Python after Java has already done the expensive search work.

What to do:

1. investigate whether Java can produce a final ordered top-k directly across index views
2. if not, consider a lazy iterator of `(record, score)` rather than building a full Python list first

Expected benefit:

- lower Python memory overhead for larger `k`
- cleaner separation between engine work and presentation work

### Priority 4: Remove avoidable intermediate Python lists before Java array creation

Problem:

- several modules build Python lists only to immediately wrap them into `JArray`.

Where:

- `schema.py:501`
- `schema.py:560`
- `async_executor.py:337`
- `async_executor.py:340`
- `graph_batch.py:255`

What to do:

1. simplify array construction where JPype already accepts Python sequences
2. benchmark before and after to verify it is a real win and not just cosmetic cleanup

## What Should Not Change

Some behavior is correct and should remain in place.

1. The engine should stay embedded and in-process through JPype.
2. Query execution, indexing, traversal, async execution, vector search internals, import, export, and schema mutation logic should remain Java-owned.
3. Python should keep offering convenience helpers; the goal is not to eliminate ergonomics, only to make the cost boundaries explicit.

## Test Coverage: What Is Already Verified

The test suite is strong on functional correctness and API ergonomics.

Relevant coverage includes:

- JVM argument behavior in `tests/test_jvm_args.py`
- result helpers in `tests/test_resultset.py`
- type conversion behavior in `tests/test_type_conversion.py`
- NumPy interop in `tests/test_numpy_support.py`
- vector behavior in `tests/test_vector.py` and `tests/test_vector_sql.py`
- performance-oriented server comparisons in `tests/test_server_patterns.py`

Important observation:

- the current tests validate functionality of materializers such as `to_list()` and `to_dict()`, but they do not enforce thin-wrapper constraints or memory ceilings.
- there is some JVM-memory awareness in the suite, but not binding-level Python-memory profiling.

## Coverage Gaps

If the goal is to hold the thin-layer line over time, the current suite is missing some important tests.

### Missing 1: Python materialization budget tests

Examples:

- verify that iterating a large `ResultSet` row-by-row does not allocate a full result list
- verify that `iter_chunks()` only grows memory roughly with chunk size, not total result size

### Missing 2: Raw vs converted API tests

If lazy/raw alternatives are added, the suite should explicitly test:

- Java-backed values are preserved when requested
- eager conversion only occurs on explicit materialization calls

### Missing 3: Wrapper overhead profiling for large documents

Examples:

- repeated `property_names` access on the same result/document
- repeated `to_dict()` on the same wrapper
- nested collection conversion with large maps/lists

### Missing 4: Vector result handling overhead tests

Examples:

- large `k` nearest-neighbor calls
- multi-index aggregation behavior
- memory growth when converting vectors to Python/NumPy

## Practical Verdict

Current state:

- Architecture: good
- Core wrapper model: good
- Convenience layer discipline: mixed
- Thinness under heavy workloads: improvable

Rough scoring:

- core design correctness: high
- strict thin-wrapper consistency: medium
- ergonomics: high
- profiling clarity: medium-low

If nothing changes, the bindings are still valid and useful. The risk is not that they are fundamentally wrong. The risk is that users will accidentally use Python materialization helpers on large datasets and then conclude that the binding itself is heavy.

## Recommended Next Steps

### Short-Term

1. Add documentation warnings to eager helpers:
   - `ResultSet.to_list()`
   - `ResultSet.to_dataframe()`
   - `Result.to_dict()`
   - `Document.to_dict()`
2. Cache property names in `Result` and `Document`.
3. Avoid `to_dict()` work inside `Result.__repr__()`.

### Medium-Term

1. Add raw/lazy result access paths.
2. Add lazy or reduced-conversion modes in `type_conversion.py`.
3. simplify `JArray` handoff code where JPype already handles sequences well.

### Longer-Term

1. profile vector result aggregation to decide whether Python-side sorting should move or shrink.
2. add benchmark or profiling tests that guard against accidental regressions in Python-side allocation.

## Bottom Line

The Python bindings are not doing the wrong kind of work at the architectural level.

The main issue is that the convenience layer currently makes it too easy to cross from:

- thin wrapper behavior

into:

- eager Python materialization

without a strong boundary signal.

The best next move is not a rewrite. It is to tighten that boundary, document it clearly, and add profiling-oriented tests so future convenience work does not quietly become default behavior.

## Profiler Script

The directory also contains a runnable profiler script:

- `profile_bindings.py`

It is meant to give repeatable baseline numbers for the current binding layer by
running representative scenarios in isolated subprocesses. That matters because
JPype can only start the JVM once per process, so single-process benchmarking
would blur JVM startup, heap growth, and scenario-level costs.

### What it measures

- JVM startup wall time
- database create / populate / close lifecycle cost
- lazy result iteration cost
- eager `ResultSet.to_list()` cost
- chunked `ResultSet.iter_chunks()` cost
- repeated `Document` / `Result` style `to_dict()` cost
- nested map/list conversion cost
- graph wrapper traversal cost
- `GraphBatch` ingest cost
- vector search cost
- vector search breakdown between Java neighbor search and Python-side wrapping
- lookup-by-key vs lookup-by-RID wrapper cost
- transaction batch insert cost
- async command and async query callback cost
- document import and CSV export cost
- process RSS and peak RSS
- Python heap allocations via `tracemalloc`
- JVM memory via `java.lang.Runtime`

### How to run it

From `bindings/python`:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py
```

Example with custom workload sizes:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py \
   --runs 3 \
   --records 10000 \
   --vector-records 3000 \
   --query-runs 100 \
   --heap-size 2g
```

Example using the built-in `smoke` preset:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py \
   --preset smoke \
   --runs 1 \
   --records 100 \
   --vector-records 120 \
   --vector-k 12 \
   --query-runs 20 \
   --async-parallel-level 2 \
   --async-commit-every 20 \
   --heap-size 1g
```

Available presets:

- `smoke`: quick sanity pass over lookup, transaction, vector breakdown, async, import, and CSV export
- `core`: core thin-wrapper and materialization paths without the broader integration-style scenarios
- `full`: all currently implemented scenarios

Example focusing on materialization-only scenarios:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py \
   --scenarios result_lazy_scan,result_to_list,result_iter_chunks,document_to_dict,nested_conversion
```

Example focusing on graph coverage:

```bash
/mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py \
   --scenarios graph_traversal,graph_batch_ingest \
   --graph-vertices 2000 \
   --graph-degree 3
```

### Output

The script prints a console summary and writes a timestamped JSON file into this
directory.

That JSON report is the main artifact to compare before and after refactors.

The console summary now also prints progress before and after each worker run so
long scenario batches no longer look hung while subprocesses are running.

### How to read the results

- `wall_total` tells you the scenario end-to-end time inside the worker process.
- `wall p95` and `wall p99` show tail latency across isolated runs when you use
   more than one run.
- `setup/overhead` is worker wall time minus scenario wall time. This is the
   easiest way to see how much of a run is JVM/process/database setup rather
   than the measured Python path itself.
- `query-runs` now defaults to `100` so graph/vector scenarios have a modest
   steady-state portion instead of being dominated by first-call noise.
- `rss_*_delta_bytes` shows process-memory growth across key phases.
- `python_peak_*_delta_bytes` shows Python allocation growth seen by
   `tracemalloc`. This is useful for spotting Python-side materialization, but it
   does not include JVM heap or native allocations.
- `jvm_*_bytes` snapshots show Java-side heap visibility.

### Suggested first comparisons

The most informative current comparisons are:

1. `result_lazy_scan` vs `result_to_list`
2. `result_to_list` vs `result_iter_chunks`
3. `document_to_dict` across repeated calls
4. `nested_conversion` to see how recursive collection conversion behaves
5. `graph_traversal` to see graph wrapper materialization and neighbor access cost
6. `graph_batch_ingest` to measure bulk graph creation overhead
7. `vector_search_breakdown`, especially `java_neighbor_search` vs
   `python_wrap_results` and `python_hydrate_records`
8. `jvm_startup` or `setup/overhead` vs everything else, to understand how much
   of total time is process/JVM setup rather than binding overhead
