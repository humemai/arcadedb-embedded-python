# Python Bindings Refactor Plan

Date: 2026-04-01

This plan turns the architecture audit into concrete refactor work. The goal is to keep the Python bindings thin, keep heavy lifting in the Java backend, and make the embedded runtime more reliable.

## Goals

1. Keep the core bindings as delegation layers over Java and SQL.
2. Contain or reduce Python-owned behavior in the thick modules.
3. Improve lifecycle reliability, especially around JVM shutdown and async threads.
4. Separate example applications from benchmark infrastructure.

## Status Summary

Completed so far:

- vector search now raises instead of silently returning empty results on failure
- NumPy argument conversion is centralized in `core.py`
- CSV export streams `ResultSet` chunks instead of forcing eager materialization
- `vector.py` has a first containment pass that reduces duplicated search orchestration
- `ResultSet.count()` consumption semantics are documented more clearly
- `Database` now owns async executors and closes them automatically
- `AsyncExecutor.close()` is idempotent and covered by regression tests
- editable/source-based test runs can resolve runtime assets correctly
- pytest now shuts down the JVM cleanly by default instead of unconditionally using `os._exit(0)`
- server/client-server tests no longer self-skip under editable/source-based execution
- `type_conversion.py` now has a first containment pass that centralizes repeated Java class resolution for the core conversion paths
- `importer.py` now has explicit helper boundaries for settings assembly and async runtime-setting save/restore
- importer failure-path restoration is covered by regression tests
- critical installed-wheel paths in `core.py` and `exporter.py` now use direct `jpype.JClass(...)` loading instead of brittle package-style Java imports
- the top-level `bindings/python` layout is cleaner: build implementation files now live under `scripts/`, with a single `scripts/build.sh` entrypoint

Still outstanding:

- deeper `type_conversion.py` cleanup
- any additional importer thinning beyond the new helper extraction
- further `vector.py` thinning
- example/benchmark reclassification

## Phase 1: Safe Cleanup Wave

These changes are low-risk and improve correctness or transparency without changing the overall API shape.

Status: completed.

### 1. Remove silent vector failures

Target:

- `src/arcadedb_embedded/vector.py`

Actions:

- replace silent fallback `return []` paths with `ArcadeDBError`
- ensure all vector-search failures are visible to callers and tests

Reason:

- binding layers should not hide backend failures

Status:

- completed

### 2. Centralize NumPy argument conversion

Targets:

- `src/arcadedb_embedded/core.py`
- eventually `src/arcadedb_embedded/vector.py`

Actions:

- replace repeated ad hoc ndarray detection with one conversion helper
- standardize the NumPy detection strategy

Reason:

- avoid duplicated argument-marshaling logic

Status:

- completed in `core.py`
- remaining follow-up: decide whether `vector.py` should also reuse the same conversion path or stay specialized

### 3. Make CSV export stream result sets

Target:

- `src/arcadedb_embedded/exporter.py`

Actions:

- use chunked iteration for `ResultSet` export instead of `to_list()`

Reason:

- avoid hidden memory blowups for large results

Status:

- completed

## Phase 2: Thick Module Containment

Status: in progress.

### 4. Refactor `vector.py`

Targets:

- `src/arcadedb_embedded/vector.py`

Actions:

- isolate metadata inspection helpers from search execution helpers
- isolate quantization validation helpers
- reduce Python-side hit post-processing where possible
- evaluate whether RID-to-record materialization can move closer to Java or become optional

Desired outcome:

- `vector.py` becomes a thin integration layer plus a small amount of validation, not a mini vector runtime

Status:

- partially completed
- duplicated exact/approximate search orchestration was reduced
- exact and approximate search now share a common internal execution path for vector conversion, RID filtering, and result collection
- `lookup_by_key()` is reused before falling back to SQL lookup
- result-hit materialization now routes through `Database.lookup_by_rid()` instead of direct raw `java_db` access
- RID whitelist conversion now routes through the public `Database.to_java_rid()` helper instead of vector-specific raw database access
- the result-materialization path is now covered by a regression test
- remaining work: further reduce helper-layer thickness beyond the result-materialization path

### 5. Refactor `type_conversion.py`

Targets:

- `src/arcadedb_embedded/type_conversion.py`

Actions:

- make conversion rules more explicit and easier to audit
- add tests around recursion depth and nested structure behavior
- consider caching Java class handles used repeatedly
- document cost and semantics for automatic deep conversion

Desired outcome:

- predictable conversion layer with bounded complexity

Status:

- partially completed
- repeated Java class resolution is now centralized for the core conversion paths
- remaining work: decide whether further decomposition or additional conversion-edge tests are worth the extra complexity

### 6. Refactor `results.py`

Targets:

- `src/arcadedb_embedded/results.py`

Actions:

- document clearly that `count()` consumes the iterator
- consider adding a non-destructive counting path only if Java exposes it cheaply
- evaluate moving dataframe-specific helpers behind a more optional boundary

Desired outcome:

- result convenience remains useful without hiding semantics

Status:

- partially completed
- `count()` consumption semantics are now documented more clearly
- remaining work: optional-boundary cleanup and any non-destructive counting strategy evaluation

### 7. Refactor import/export orchestration

Targets:

- `src/arcadedb_embedded/importer.py`
- `src/arcadedb_embedded/exporter.py`

Actions:

- isolate settings assembly and restoration logic
- make runtime-setting mutation explicit and testable
- document which parts are Python convenience versus engine behavior

Desired outcome:

- these modules remain helpers, not policy-heavy subsystems

Status:

- partially completed
- `exporter.py` now streams result sets for CSV export
- `importer.py` now isolates settings assembly and runtime setting save/restore in explicit helpers
- importer failures now have regression coverage proving runtime settings are restored
- remaining work: any broader importer API simplification beyond the new helper extraction

## Phase 3: Lifecycle Reliability

Status: largely completed for the highest-risk issues, with follow-up cleanup still pending.

### 8. Eliminate forced pytest exit

Targets:

- `tests/conftest.py`
- `src/arcadedb_embedded/async_executor.py`
- `src/arcadedb_embedded/jvm.py`
- any background-thread ownership path tied to JPype / Java async executors

Actions:

- identify the threads that keep the process alive
- verify all async executors are closed in tests and in production wrappers
- add targeted lifecycle tests for clean executor shutdown
- remove `os._exit(0)` once shutdown is stable

Desired outcome:

- test suite completes with normal interpreter shutdown

Status:

- completed for the default test path
- async executor ownership is tracked by `Database`
- async executor shutdown is idempotent and covered by targeted regression tests
- the full Python bindings suite now returns cleanly after `pytest.main(['-q'])`
- `ARCADEDB_PYTEST_FORCE_EXIT=1` remains available only as an emergency override

### 9. Tighten resource cleanup semantics

Targets:

- `src/arcadedb_embedded/server.py`
- `src/arcadedb_embedded/core.py`
- tests using temp databases and temp servers

Actions:

- prefer explicit lifecycle guarantees over destructor cleanup
- reduce cleanup sleeps and GC-driven workarounds where feasible

Desired outcome:

- more predictable test and app cleanup behavior

Status:

- partially completed
- centralized async executor cleanup on `Database.close()` is in place
- server capability detection for tests now uses the resolved runtime JAR path
- remaining work: reduce destructor reliance and other cleanup workarounds outside the async executor path

## Phase 4: Examples Reorganization

Status: not started.

### 10. Reclassify benchmark scripts

Targets:

- `examples/07_*` through `examples/12_*`
- `examples/README.md`

Actions:

- split examples into normal examples vs benchmark/research scripts
- move the largest harnesses to a benchmark-oriented section or directory
- make sure new users land on SQL-first, embedded-first examples first

Desired outcome:

- examples teach the intended package posture more clearly

Status:

- not started

### 11. Rework the thickest example

Target:

- `examples/06_vector_search_recommendations.py`

Actions:

- simplify or reframe it as an experimental application script
- reduce Python-owned recommendation logic where practical

Desired outcome:

- examples do not encourage heavy Python-side database logic

Status:

- not started

## Recommended Execution Order

1. Finish `type_conversion.py` containment.
2. Clean up importer orchestration.
3. Do a second `vector.py` thinning pass if still warranted.
4. Reclassify examples and benchmark harnesses.

## Suggested Work Breakdown

### Wave A

- vector error visibility
- argument conversion cleanup
- streaming CSV export

Status:

- completed

### Wave B

- `vector.py` decomposition
- `results.py` semantics cleanup
- import/export settings isolation

Status:

- in progress

### Wave C

- async shutdown investigation
- remove forced pytest exit
- restore server/client-server test execution under editable/source-based runs

Status:

- completed for the current suite path

### Wave D

- examples reorganization and README cleanup

Status:

- not started

## Success Criteria

1. No silent failure paths in core user-facing helper layers.
2. No unnecessary Python-side materialization in large-result utilities.
3. Thick modules are smaller, more explicit, and more testable.
4. Test suite no longer depends on forced interpreter termination by default.
5. Examples present embedded-first, SQL-first usage as the default mental model.
