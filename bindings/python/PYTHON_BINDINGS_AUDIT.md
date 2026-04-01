# ArcadeDB Embedded Python Bindings Audit

Date: 2026-04-01

## Scope

This report reviews the Python surface under `bindings/python` with a specific architectural question:

> Are the Python bindings staying thin, with heavy lifting delegated to the Java backend, or is too much logic accumulating in Python?

Reviewed scope:

- `src/arcadedb_embedded`: 16 Python files
- `tests`: 29 Python files
- `examples` and `examples/scripts`: 26 Python files

This was a broad and deep architectural audit, not a formal bug audit. The focus is layering, API posture, lifecycle, and whether the package teaches the right usage model.

## Executive Summary

The package is broadly in good shape.

The core binding layer is mostly thin and correctly delegates to Java. The best parts of the package are:

- `Database` / `Server` / `Transaction` lifecycle wrappers
- SQL-first posture for many advanced features
- direct reuse of Java-side capabilities instead of building parallel Python-native subsystems

The main architectural pressure points are not the basic wrappers. They are the convenience layers:

- type conversion
- result shaping
- vector helper APIs, though the result-materialization path is now thinner than it was at the start of this audit
- importer/exporter orchestration
- async callback bridging
- benchmark-heavy examples that look like application API guidance when they are really research tooling

The short version:

- `src`: mostly healthy, with a few thick modules that deserve refactoring
- `tests`: strong coverage, but they expose real JVM lifecycle and thread cleanup debt
- `examples`: newer SQL-first examples are aligned; some large benchmark scripts should be reclassified or moved out of `examples`
- build tooling is cleaner at the top level now, with build machinery consolidated under `bindings/python/scripts/` and a single `scripts/build.sh` entrypoint

## Architectural Standard Used In This Review

I used three classifications for source modules and examples:

- `thin`: Python mainly forwards calls, performs minimal marshaling, and keeps semantics in Java/SQL
- `acceptable wrapper`: Python adds ergonomic value, but the real logic still lives in Java or SQL
- `thick`: Python owns meaningful orchestration, transformation, policy, or algorithmic behavior that could drift from Java behavior or hide performance costs

For tests, the question is slightly different:

- Do tests reinforce a thin-wrapper architecture?
- Do they reveal lifecycle or concurrency debt?
- Do they push the API toward more Python-native abstraction than intended?

## Overall Findings

### What is working well

1. The package is still embedded-first.
2. The core API remains close to Java and SQL rather than inventing a separate Python-native database model.
3. Many advanced features are intentionally SQL-first, which is the right choice for a thin binding.
4. The public surface is reasonably coherent: `Database`, `Schema`, `ResultSet`, `ArcadeDBServer`, `VectorIndex`, `AsyncExecutor`, `GraphBatch`.

### Where thickness is accumulating

1. Recursive type conversion and result shaping.
2. Vector helper logic, especially metadata introspection and hit materialization.
3. Import/export orchestration and format handling.
4. Async callback bridge logic and runtime setting modulation.
5. Large benchmark scripts living in `examples`, where readers may mistake them for recommended application structure.

### The most important non-layering problem exposed by the repo

The test suite still has JVM shutdown and thread lifecycle problems serious enough to require forced interpreter exit after tests complete. That is not a “thinness” problem, but it is the biggest piece of technical debt visible in the Python package.

---

## Source Review

### Source Layer Summary

The source layer has a good shape overall:

- thin core wrappers around Java database/server objects
- focused convenience wrappers for records and results
- optional ergonomic layers for vectors, async execution, import/export

The package does not look like it is trying to reimplement ArcadeDB in Python. That is good.

The main caution is that several modules now do enough work that they are no longer just bindings. They are secondary subsystems.

### Source Classification Table

| File | Classification | Notes |
| --- | --- | --- |
| `src/arcadedb_embedded/__init__.py` | acceptable wrapper | Public surface re-export layer; clean and conventional |
| `src/arcadedb_embedded/exceptions.py` | thin | Minimal custom exception surface |
| `src/arcadedb_embedded/transactions.py` | thin | Small context manager, exactly the right amount of Python |
| `src/arcadedb_embedded/citation.py` | thin | Small metadata helper |
| `src/arcadedb_embedded/core.py` | acceptable wrapper | Core wrapper; mostly delegation with argument conversion |
| `src/arcadedb_embedded/server.py` | acceptable wrapper | Server lifecycle wrapper over Java server |
| `src/arcadedb_embedded/graph.py` | acceptable wrapper | Thin object wrappers for document, vertex, edge |
| `src/arcadedb_embedded/schema.py` | acceptable wrapper | Pythonic schema API over Java schema calls |
| `src/arcadedb_embedded/jvm.py` | acceptable wrapper | JVM bootstrap is necessarily thicker, but still infrastructure-focused |
| `src/arcadedb_embedded/results.py` | thick | Result materialization and convenience APIs own real behavior |
| `src/arcadedb_embedded/type_conversion.py` | thick | Large recursive conversion subsystem |
| `src/arcadedb_embedded/vector.py` | acceptable wrapper leaning thick | Significant Python-side vector behavior and metadata handling remain, but recent containment work has removed some direct raw-Java coupling |
| `src/arcadedb_embedded/async_executor.py` | acceptable wrapper leaning thick | Valuable wrapper, but callback bridge and orchestration logic are substantial |
| `src/arcadedb_embedded/graph_batch.py` | acceptable wrapper leaning thick | Thin in spirit, but batching/property-matrix logic is non-trivial |
| `src/arcadedb_embedded/importer.py` | thick | Runtime settings orchestration and import config handling |
| `src/arcadedb_embedded/exporter.py` | thick | Format handling, CSV writing, file policy |

### File-by-File Notes

#### `__init__.py`

This is a clean export surface. It does not add logic and is doing the right thing by collecting the public API in one place.

Assessment: keep as-is.

#### `exceptions.py`

This is exactly what it should be: minimal, stable, and boring.

Assessment: keep thin.

#### `transactions.py`

This is also exactly right. It gives Python a natural context-manager interface while keeping transaction semantics in the database engine.

Assessment: keep thin.

#### `citation.py`

A small metadata helper. No architectural concerns.

Assessment: keep thin.

#### `core.py`

This is the heart of the binding and it is mostly well-behaved.

Good:

- `query()` and `command()` delegate directly to Java.
- transaction APIs are simple.
- lifecycle and close checks are explicit.
- high-level helpers like `async_executor()`, `graph_batch()`, `import_documents()`, and `schema` are surfaced from here without burying the user in package internals.

Concerns:

- NumPy detection is duplicated and somewhat ad hoc.
- some convenience helpers, especially vector/index setup and lookup methods, put more policy in Python than a pure binding would.
- close semantics have to special-case server-managed databases by parsing error messages.

Assessment: acceptable wrapper.

Recommendation:

- centralize Python-to-Java argument conversion instead of repeating NumPy handling patterns
- avoid message-string-based lifecycle branching where possible

#### `server.py`

This stays close to the Java server and mostly just translates config and lifecycle. That is the right role.

Good:

- clear embedded-first posture
- context-manager lifecycle
- minimal surface area

Concerns:

- Python-side config-key mapping can become a hidden policy layer if it grows
- finalizer cleanup in `__del__` is pragmatic but inherently unreliable

Assessment: acceptable wrapper.

Recommendation:

- keep config translation narrow
- prefer explicit lifecycle over destructor-based cleanup

#### `graph.py`

These are thin, useful wrappers.

Good:

- record wrapping stays simple
- `Vertex` and `Edge` mostly forward to Java behavior
- conversion hooks are kept at property boundaries

Concerns:

- repeated Java type checks are fine now, but could become a performance smell if this layer grows further

Assessment: acceptable wrapper.

Recommendation:

- keep this layer as record ergonomics only, not a graph logic layer

#### `schema.py`

This is a reasonable Pythonic overlay for schema operations. It saves users from writing SQL strings for basic schema tasks without trying to reinvent schema semantics.

Good:

- direct mapping to Java schema operations
- enums improve readability

Concerns:

- the more advanced schema surface becomes, the easier it is for the Python API to drift from SQL and Java behavior

Assessment: acceptable wrapper.

Recommendation:

- continue to expose simple, type-safe wrappers
- resist expanding this into a separate schema DSL

#### `jvm.py`

This is one of the thickest infrastructure modules, but it is justified. Embedding a JVM inside Python requires platform handling, bundled JRE resolution, argument merging, and startup constraints.

Good:

- explicit prevention of conflicting repeated startup configuration
- bundled JRE handling
- JVM argument normalization and defaults

Concerns:

- global JVM config state couples the entire process
- this is a natural source of “works in isolation, fails in a larger process” bugs
- shutdown remains weakly controlled

Assessment: acceptable wrapper.

Recommendation:

- document startup invariants very clearly
- keep all JVM policy concentrated here rather than spreading it elsewhere

#### `results.py`

This is a useful but definitely thick convenience layer.

Good:

- Python iteration support is valuable
- `first()`, `one()`, `iter_chunks()`, and `to_dataframe()` improve usability

Concerns:

- `to_list()` and `to_dataframe()` make it easy to materialize large result sets and hide the cost
- `count()` consumes the iterator, which is surprising behavior for many Python users
- the more transformation APIs live here, the more this module stops being a wrapper and starts being a result-processing toolkit

Assessment: thick.

Recommendation:

- document destructive iterator semantics explicitly
- consider moving pandas-specific behavior out of the core module
- keep result shaping thin enough that users understand when they are leaving engine-side execution and paying Python-side materialization costs

#### `type_conversion.py`

This is a substantial subsystem.

Good:

- broad Java-to-Python support improves ergonomics dramatically
- temporal and numeric conversion coverage is solid

Concerns:

- recursive conversion is complex and easy to grow accidentally
- this can become a silent performance sink for large nested results
- cycle handling is not obvious
- this is one of the main places where behavior lives in Python, not Java

Assessment: thick.

Recommendation:

- keep conversion rules minimal and predictable
- add explicit guidance on when users should prefer raw Java-side semantics versus converted Python values
- consider caching or otherwise optimizing repeated class-resolution paths if profiling shows cost here

#### `vector.py`

This is the most architecturally sensitive module in the package.

Good:

- it exposes Java vector capabilities in a Python-friendly way
- metadata helpers and approximate/exact search pathways are useful

Concerns:

- this module still owns a lot of vector-specific behavior: parameter validation, metadata inspection, quantization readiness checks, RID filtering, search result assembly, and Python-side hit wrapping
- `find_nearest()` and `find_nearest_approximate()` now share more of their execution path than before, but they still do more than bind Java methods; they orchestrate multi-step behavior in Python
- result-hit materialization now goes through `Database.lookup_by_rid()` instead of reaching directly into raw `java_db`, which is an improvement, but the overall hit-assembly path is still Python-owned
- silent failure paths were reduced, but the helper layer is still larger than ideal for a thin binding

Assessment: acceptable wrapper leaning thick.

Recommendation:

- continue reducing Python-owned orchestration where possible
- prefer direct Java-side APIs that return the right abstraction if available
- keep result materialization on public wrapper APIs rather than raw Java object access
- never silently swallow vector-search failures in the binding layer

#### `async_executor.py`

This is a solid wrapper, but it is not especially thin anymore.

Good:

- fluent configuration is useful
- callback bridging is necessary for JPype-based async integration
- explicit wait/close APIs are good

Concerns:

- callback bridge code is substantial and difficult to reason about
- manual callback wiring and state polling reflect the underlying Java model, but also leave Python with meaningful orchestration responsibility
- this is a likely source of thread-lifecycle issues

Assessment: acceptable wrapper leaning thick.

Recommendation:

- keep this clearly marked as advanced/experimental
- avoid broadening it further unless a stronger lifecycle model is in place

#### `graph_batch.py`

This is useful and reasonably aligned with the Java builder API.

Good:

- batching semantics remain Java-driven
- Python mainly assembles properties and RIDs

Concerns:

- property matrix assembly and transaction convenience logic are non-trivial
- batch helpers can easily become a mini-ingestion framework if expanded further

Assessment: acceptable wrapper leaning thick.

Recommendation:

- keep this as a narrow ingestion aid
- do not let it grow into a high-level graph ETL subsystem

#### `importer.py`

This module is clearly thicker than a simple binding.

Good:

- practical path/URI handling
- import result normalization is useful

Concerns:

- runtime async settings are mutated, then restored
- import configuration handling and policy live in Python
- this is orchestration logic, not just binding logic

Assessment: thick.

Recommendation:

- keep the wrapper narrow and strongly document it as a convenience layer
- if it grows further, isolate configuration objects and rollback semantics more explicitly

#### `exporter.py`

Also thicker than a pure binding.

Good:

- practical export ergonomics
- support for CSV export from result sets is useful

Concerns:

- file/directory policy is owned in Python
- CSV export is a Python-side serializer, not a binding feature
- materialization through `to_list()` can hide large memory costs

Assessment: thick.

Recommendation:

- if CSV convenience stays, document it as a Python utility rather than core database behavior
- prefer chunked/streaming export paths for large results

### Source Layer Verdict

The `src` layer is mostly healthy.

If the goal is “keep Python thin,” the priority is not to rewrite everything. It is to prevent additional logic from accumulating in the already-thick modules:

- `vector.py`
- `type_conversion.py`
- `results.py`
- `importer.py`
- `exporter.py`

Those five modules deserve the most architectural attention.

---

## Test Review

### Test Suite Summary

The test suite is strong in one very important way: it mostly tests the Python package as a real embedded integration layer over ArcadeDB rather than as an isolated pure-Python unit library.

That is the correct testing model for this project.

The tests also reveal several important truths about the package:

1. the package is file-backed and lifecycle-sensitive
2. server and embedded modes coexist but are not the same thing
3. many advanced features are package/runtime dependent
4. JVM shutdown and background-thread cleanup are still a serious problem

### Test Grouping

#### Infrastructure and lifecycle

Files:

- `tests/conftest.py`
- `tests/test_jvm_args.py`
- `tests/test_concurrency.py`

Findings:

- `conftest.py` is the clearest sign of technical debt in the repo. The suite uses forced process exit after pytest completes because JVM threads do not reliably shut down cleanly.
- temp-directory cleanup includes garbage collection and timing workarounds, especially for Windows file-lock behavior
- JVM startup behavior is treated as a real configurable subsystem, not a trivial bootstrap step

Assessment:

- this group strongly reinforces that lifecycle management is the hardest part of the binding

#### Core database behavior

Files:

- `tests/test_core.py`
- `tests/test_database_utils.py`
- `tests/test_transaction_config.py`
- `tests/test_resultset.py`
- `tests/test_type_conversion.py`

Findings:

- core operations are tested through SQL-first usage patterns
- result convenience behavior is well covered
- transaction configuration and read-your-writes behavior are treated as important runtime controls
- type conversion is a first-class concern of the public Python experience

Assessment:

- these tests mostly reinforce a thin wrapper over SQL/Java, with Python adding usability on top

#### Graph and schema surfaces

Files:

- `tests/test_graph_api.py`
- `tests/test_graph_batch.py`
- `tests/test_schema.py`
- `tests/test_hash_index_schema.py`
- `tests/test_graph_algorithms_sql.py`
- `tests/test_materialized_view_sql.py`
- `tests/test_geo_predicate_sql.py`
- `tests/test_timeseries_sql.py`

Findings:

- many graph, geo, timeseries, and analytical features are exercised through SQL rather than bespoke Python APIs
- that is a strong positive signal: the test suite pushes the package toward SQL-first behavior instead of wrapper proliferation
- `graph_batch` is tested as a helper for high-throughput ingestion, not as a general graph abstraction layer

Assessment:

- this group is well aligned with a thin-binding philosophy

#### Server access patterns

Files:

- `tests/test_server.py`
- `tests/test_server_patterns.py`

Findings:

- server-managed and embedded access patterns are explicitly distinguished
- tests emphasize the practical access rules: embedded-first, server-managed lifecycle, file locks, mixed embedded + HTTP usage
- the package does a good job of making these patterns visible rather than pretending there is one unified transport-neutral client model

Assessment:

- very good architectural guidance here

#### Async and import/export helpers

Files:

- `tests/test_async_executor.py`
- `tests/test_importer_api.py`
- `tests/test_import_database.py`
- `tests/test_exporter.py`

Findings:

- async behavior is clearly treated as advanced and stateful
- importer tests reveal runtime-setting mutation and restoration, confirming that import orchestration is not trivial
- exporter tests validate convenience behavior, but also normalize Python-side utility layers as part of the public package

Assessment:

- useful coverage, but these tests also show where the binding surface is getting thicker

#### Vector and NumPy support

Files:

- `tests/test_numpy_support.py`
- `tests/test_vector.py`
- `tests/test_vector_sql.py`
- `tests/test_vector_params_verification.py`

Findings:

- this is one of the deepest test areas in the package
- the suite covers vector indexes, SQL vector functions, approximate search knobs, NumPy conversion, and metadata propagation
- this confirms vector support is a major product area in the Python package, not just a minor helper

Assessment:

- strong coverage, but it also increases pressure on `vector.py` to remain disciplined and not become a parallel vector framework

#### Documentation and examples as contract

Files:

- `tests/test_docs_examples.py`

Findings:

- this is a strong practice
- examples and docs are effectively treated as part of the tested public contract

Assessment:

- keep this; it helps prevent docs/API drift

### Test Suite Strengths

1. Real integration testing, not just mocks.
2. Strong SQL-first validation for advanced features.
3. Good coverage of vector and server patterns.
4. Good use of docs/example validation as contract testing.

### Test Suite Risks and Debt

1. Forced interpreter exit in `conftest.py` remains the biggest red flag.
2. Cleanup and lock-release timing workarounds suggest lifecycle fragility.
3. Some advanced helper layers are normalized by tests in ways that may encourage further Python-side feature growth.

### Test Suite Verdict

The tests are generally aligned with the right architecture.

They do not suggest that the package is drifting into a Python-native database reimplementation.

What they do reveal is:

- lifecycle and JVM shutdown debt
- configuration complexity for async/import/runtime behavior
- a growing surface of convenience utilities that should stay carefully contained

---

## Examples Review

### Examples Layer Summary

The examples split into three distinct categories:

1. genuinely good SQL-first user examples
2. utility/profiling scripts
3. large benchmark/research harnesses that do not belong in the same mental bucket as normal examples

The examples are strongest when they explicitly say:

- Python is orchestration
- SQL and Java are where the real database behavior lives

The examples are weakest when a large benchmark harness lives in `examples/` and looks like a recommended application pattern.

### Example Categories

#### Category A: Strong SQL-first / thin-wrapper examples

Examples:

- `examples/01_simple_document_store.py`
- `examples/02_social_network_graph.py`
- `examples/03_vector_search.py`
- `examples/17_timeseries_end_to_end.py`
- `examples/18_geo_predicates_wkt.py`
- `examples/19_hash_index_exact_match.py`
- `examples/20_graph_algorithms_route_planning.py`
- `examples/21_server_mode_http_access.py`
- `examples/22_graph_analytical_view_sql.py`

Why these are good:

- they mostly use SQL or straightforward wrappers
- they teach the right posture
- they do not pretend Python is the database engine
- they keep application logic and database logic reasonably separated

Assessment:

- keep these as the examples users see first

#### Category B: Acceptable ingestion/integration examples

Examples:

- `examples/04_csv_import_documents.py`
- `examples/05_csv_import_graph.py`
- `examples/13_stackoverflow_hybrid_queries.py`
- `examples/14_lifecycle_timing.py`
- `examples/15_import_database_vs_transactional_table_ingest.py`
- `examples/16_import_database_vs_transactional_graph_ingest.py`

Observations:

- some of these are still fine as advanced examples
- `14_lifecycle_timing.py` is clearly a profiling example and is reasonable where it is
- `15` and `16` are useful, but they already read more like benchmark/comparison harnesses than ordinary user guidance

Assessment:

- acceptable, but they should be clearly labeled as benchmarking or comparative ingestion studies, not default application style

#### Category C: Benchmark and research harnesses

Examples:

- `examples/07_stackoverflow_tables_oltp.py`
- `examples/08_stackoverflow_tables_olap.py`
- `examples/09_stackoverflow_graph_oltp.py`
- `examples/10_stackoverflow_graph_olap.py`
- `examples/11_vector_index_build.py`
- `examples/12_vector_search.py`

Observations:

- these are large, multi-concern programs
- they do resource control, dataset handling, timing, cross-system comparisons, sometimes Docker orchestration, and substantial workload management
- that is not “bad,” but it is not ordinary API usage

Assessment:

- they are legitimate tools, but they are benchmark infrastructure
- they should be classified as such, and likely moved or more clearly separated from end-user examples

#### Category D: The problematic example

Example:

- `examples/06_vector_search_recommendations.py`

Why it stands out:

- this script puts more meaningful recommendation logic in Python than the rest of the examples do
- it risks teaching users that the right way to use ArcadeDB from Python is to build heavyweight graph/vector recommendation logic in Python around the engine, instead of keeping the heavy work in SQL/Java-side capabilities where possible

Assessment:

- this is the clearest example-file mismatch with the thin-binding philosophy

Recommendation:

- either reframe it explicitly as an experimental application script, or simplify it so the database-side behavior is the focus

#### Category E: Utility and internal scripts

Examples:

- `examples/download_data.py`
- `examples/scripts/_summary_helpers.py`
- `examples/scripts/run_examples_minimal.py`
- `examples/scripts/internal_vector_http_latency_probe.py`

Assessment:

- these are fine as infrastructure or internal tooling
- no architectural issue here as long as they are clearly understood as tooling, not library surface

### Examples Layer Strengths

1. Many newer examples are explicitly SQL-first.
2. Server-mode guidance stays narrow and avoids inventing a remote client abstraction.
3. Several examples clearly reflect the intended embedded-first posture.

### Examples Layer Risks

1. Benchmark infrastructure is mixed into `examples`, where it can blur the package’s intended usage model.
2. Some scripts are so large that they function more as research harnesses than examples.
3. Example 06 is the clearest case where Python-side application logic overshadows the binding role.

### Examples Layer Verdict

The examples are mostly aligned, but they need clearer separation between:

- user-facing examples
- profiling tools
- benchmark/research harnesses

That is the biggest cleanup opportunity in `examples`.

---

## Prioritized Recommendations

### Status Update (2026-04-01)

The recommendations below are no longer purely prospective. The following items have already been implemented:

- completed: centralized NumPy argument conversion in `core.py`
- completed: removed silent failure behavior from `vector.py` exact-search paths and now raise `ArcadeDBError`
- completed: streamed `ResultSet` CSV export in `exporter.py` instead of forcing `to_list()`
- completed: reduced duplicated vector-search orchestration in `vector.py` and reused `lookup_by_key()` where practical
- completed: exact and approximate vector search now share a common internal execution path instead of duplicating vector conversion, RID filtering, and result collection steps
- completed: clarified `ResultSet.count()` consumption semantics in `results.py`
- completed: database-owned async executor tracking and idempotent async executor shutdown in `core.py` and `async_executor.py`
- completed: lifecycle regression tests for executor ownership and idempotent close
- completed: editable-install fallback for missing generated version metadata and missing bundled runtime assets during local source-based testing
- completed: normal pytest shutdown now works across the full Python bindings test suite without unconditional `os._exit(0)`
- completed: server and client-server tests no longer self-skip under editable/source-based execution because capability detection now uses the resolved runtime JAR path
- completed: first `type_conversion.py` containment pass centralized and cached core Java class resolution without changing public behavior
- completed: first `importer.py` containment pass extracted settings assembly and runtime-setting save/restore into explicit helpers, with failure-path restoration covered by tests
- completed: `core.py` and `exporter.py` now avoid brittle JPype package-style imports on critical installed-wheel paths by loading Java classes directly

The largest remaining items are deeper `type_conversion.py` cleanup, any further importer thinning beyond the first helper extraction pass, and examples reclassification.

### Priority 1: Fix lifecycle debt

The highest-priority issue in the Python package is not wrapper thickness. It is JVM/thread lifecycle behavior.

Status:

- completed: async executor ownership and cleanup are now centralized in the database wrapper
- completed: targeted lifecycle regression coverage exists for executor cleanup
- completed: the Python bindings test suite now returns cleanly after explicit JVM shutdown, and `os._exit(0)` is no longer the default path
- completed: server capability detection now works correctly for editable/source-based execution, so server/client-server coverage runs again instead of spuriously skipping

Actions:

- eliminate the need for forced interpreter exit after tests
- audit async executor thread shutdown behavior
- tighten server/database cleanup guarantees

### Priority 2: Contain the thick modules

The five modules to watch most closely are:

- `vector.py`
- `type_conversion.py`
- `results.py`
- `importer.py`
- `exporter.py`

Status:

- partially complete: `vector.py`, `results.py`, `exporter.py`, `type_conversion.py`, and `importer.py` have all received a first containment pass
- not done: `type_conversion.py` and `importer.py` still have deeper cleanup available beyond the initial helper extraction and caching pass

Actions:

- prevent these modules from accumulating additional policy
- document their trade-offs clearly
- push heavy semantics back into Java or SQL where practical

### Priority 3: Reclassify benchmark infrastructure

Status:

- not started: no reclassification or README-level relabeling has landed yet

Examples `07` through `12`, especially `11` and `12`, should be more clearly separated from ordinary examples.

Actions:

- move them into a benchmark or research area, or
- keep them in place but relabel them prominently in the examples README

### Priority 4: Tighten vector-layer behavior

`vector.py` is the most likely place for binding drift.

Status:

- partially complete: silent failure paths were removed, duplicated search orchestration was reduced, and RID materialization/whitelist conversion now flow through public `Database` wrapper APIs
- not done: broader Python-side vector post-processing and helper-layer size are still heavier than ideal

Actions:

- avoid silent failure paths
- reduce Python-side post-processing where possible
- make performance costs visible

### Priority 5: Keep advanced features SQL-first

This is already a strength of the repo and should remain a design rule.

Status:

- unchanged strength: the repo still largely follows this well
- no direct refactor work was needed here in the first cleanup waves

Actions:

- prefer SQL-first examples for timeseries, geo, graph algorithms, GAV, and advanced analytics
- avoid creating Python-native mini-frameworks around those features

---

## Final Verdict

The Python bindings are still mostly honoring the right architecture.

They are not, in general, trying to do the Java backend’s job in Python.

The core risk is not that the package is already “too Python-heavy” everywhere. The risk is more specific:

- a handful of convenience modules are getting thick
- JVM lifecycle is still rough, though async executor ownership is now in better shape than when this report was first written
- large benchmark scripts can distort the perceived package posture

If the project wants to keep the bindings thin, the right move is not broad simplification of everything. It is disciplined containment:

- keep core wrappers thin
- keep advanced features SQL-first
- constrain convenience-layer growth
- separate benchmarking infrastructure from normal examples
- fix lifecycle reliability so the embedding story is operationally strong, not just architecturally clean
