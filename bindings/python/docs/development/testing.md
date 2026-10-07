# Testing

The tests live in `bindings/python/tests` and run against the built wheel with its bundled JRE.
One JVM serves a whole pytest session. CI runs the suite on Linux (x86_64 and ARM64), macOS
(ARM64), and Windows (x86_64), on every Python from 3.10 to 3.14; see
[CI Gates](ci-setup.md#ci-gates).

## Running the tests

1. Build the wheel: `cd bindings/python && ./scripts/build.sh` (Docker on Linux, Python 3.12 by
   default). It writes the wheel to `bindings/python/dist/` and, outside CI, refreshes the
   repo-root uv environment.
2. From the repository root (or `bindings/python`), run `uv run pytest`. The repo-root
   `pyproject.toml` is the test environment, pinned to Python 3.12, so it needs a cp312 wheel. To
   leave out the heavy example packages (torch, sentence-transformers), pass `--no-group
   examples` to `uv sync` and `uv run`.

CI does not use the uv environment: it installs the built wheel and a hand-maintained list of
test dependencies, then runs `pytest tests/` from `bindings/python`.

```bash
# Everything (from the repository root or bindings/python; from any other directory a bare
# run collects only that directory)
uv run pytest

# One file, one test, or a keyword (paths are relative to the repository root)
uv run pytest bindings/python/tests/test_core.py
uv run pytest bindings/python/tests/test_core.py::test_database_creation
uv run pytest -k "transaction"

# Stop at the first failure, rerun only the last failures, show printed output
uv run pytest -x
uv run pytest --lf
uv run pytest -v -s

# Coverage
uv run pytest --cov=arcadedb_embedded --cov-report=html
```

On Windows, run with `--capture=sys`: pytest's default fd capture can leave the JVM writing its
log lines to a handle that no longer belongs to it, and the test then hangs in that write
([#10](https://github.com/humemai/arcadedb-embedded-python/issues/10)).

## What each test file covers

Each file is named for what it tests, and each test has a name or docstring that says what it
asserts, so the list below stops at the file.

### Database, queries, and data types

| File | What it checks |
| --- | --- |
| `test_core.py` | Create, read, update, and delete, transactions and `run_in_transaction()`, SQL statements, full-text search, graph basics through SQL, `lookup_by_rid()`, result materialization |
| `test_cypher.py` | OpenCypher queries, path modes, and planner regressions |
| `test_parameter_binding.py` | Positional and named parameters reach the statement on every entry point, including a lone `None` and the async executor, and scalars skip the conversion walk |
| `test_database_utils.py` | `count_type`, `is_transaction_active`, `drop`, and the errors on a closed database |
| `test_transaction_config.py` | WAL flush, read-your-writes, and auto-transaction settings |
| `test_results_after_close.py` | What a result or record does after its `Database` is closed or dropped |
| `test_concurrency.py` | The file lock, thread safety, sequential reopen, a second process refused, and a mixed multi-thread workload |
| `test_async_executor.py` | Async commands, queries, callbacks, state flags, and `wait_completion` timeouts, with exact command-path counts at parallel levels 1 and 4 |
| `test_schema.py` | Types, properties, and indexes: create, discover, and drop |
| `test_schema_batching.py` | Schema statements apply at once, a rollback does not undo them, and many batch in one transaction |
| `test_type_conversion.py` | Python and Java type conversion in both directions |
| `test_conversion_fixes.py` | numpy booleans, `int` arrays beyond 32 bits, `lookup_by_key` with dates, `append_samples` with tag and boolean columns, and Java instants keeping microseconds |
| `test_numpy_support.py` | numpy arrays as command and query parameters and in a transaction |
| `test_logging_helper.py` | The internal `_logging` helper |

### Results, bulk ingest, import, and export

| File | What it checks |
| --- | --- |
| `test_resultset.py` | `Result` and `ResultSet` iteration, accessors, paging, and release of the engine cursor |
| `test_resultset_arrow.py` | `ResultSet.to_arrow()` |
| `test_columnar_readers.py` | `to_columns`, `to_dataframe`, and `to_arrow` on schemaless and DECIMAL data, at several batch sizes |
| `test_resultset_read_errors.py` | An engine error raised while a result set is read arrives as `ArcadeDBError` on every way of reading |
| `test_bulk_insert.py` | `Database.insert_many`, `AsyncExecutor.create_record`, vector columns, numpy `append_samples`, and what a failed call leaves behind |
| `test_insert_columns.py` | `Database.insert_columns`: typed values, nulls, the parallel mode, the rollback contract, and bad input refused before anything is written |
| `test_bulk_json_paths.py` | Values the JSON text of a bulk call cannot carry unchanged keep the call off the bulk path, so every entry point stores the same value or raises |
| `test_graph_batch.py` | `GraphBatch` buffering, flushing, failure handling, and the caller's transaction |
| `test_graph.py` | `GraphBatch.new_edges` and `create_vertices` bulk paths |
| `test_import_database.py` | SQL `IMPORT DATABASE` across CSV (documents, graphs, and time series), XML, Neo4j, Word2Vec, and RDF |
| `test_importer_api.py` | The `db.import_documents(...)` wrapper and `on_row_error` |
| `test_exporter.py` | JSONL database export, CSV result export, the error `graphml` and `graphson` raise, and round trips |

### Graphs, vectors, and SQL features

| File | What it checks |
| --- | --- |
| `test_graph_api.py` | Vertex, edge, and document wrappers and traversal helpers |
| `test_graph_algorithms_sql.py` | `shortestPath`, `dijkstra`, and `astar` |
| `test_geo_predicate_sql.py` | `geo.within` and `geo.intersects` (a boundary point returns a boolean; which one is not asserted) |
| `test_timeseries_sql.py` | `CREATE TIMESERIES TYPE`, range queries, bucketing, tag filters, and `COMPACT` |
| `test_materialized_view_sql.py` | Materialized view create, refresh, alter, and drop |
| `test_restore_sql.py` | `RESTORE DOCUMENT` and `RESTORE VERTEX`: the record count agrees with a full scan, and the record comes back intact |
| `test_hash_index_schema.py` | HASH index create, discover, idempotent `get_or_create_index`, force drop, the `UNIQUE_HASH` id path, and a named-list `IN` parameter on an `LSM_TREE` index |
| `test_vector.py` | `LSM_VECTOR` indexes: creation, search, filters, approximate search, quantization, persistence, and distance functions |
| `test_vector_sql.py` | The SQL vector functions, index creation, and search flows |
| `test_vector_params_verification.py` | Vector index parameter validation |
| `test_vector_delta_visibility.py` | Vectors written after a build are searchable, and deleted ones filtered, before any rebuild |
| `test_vector_second_pass.py` | A repeated query set returns the same neighbours as its first pass |
| `test_sparse_quantization_compact.py` | `LSM_SPARSE_VECTOR` weight precision, the settle step (`COMPACT INDEX`), the dense search beam argument, and INT8 rescoring |
| `test_cross_model_atomicity.py` | Search, hop, and update in one transaction survive an interruption with nothing torn; with one transaction per write they are torn every time |
| `test_example11_degree_matching.py` | `hnsw_m_from_max_connections()` in `examples/11_vector_index_build.py` halves `maxConnections`, never below 1, and accepts a string |

### Server

| File | What it checks |
| --- | --- |
| `test_server.py` | Server lifecycle, configuration, the Studio URL, databases through the Java API, and a failed start that must not hang process exit |
| `test_server_patterns.py` | Standalone embedded, server-managed embedded, and HTTP access, side by side |
| `test_server_http_endpoints.py` | The HTTP features the bindings document but do not wrap: multi-request transactions, server database commands, and line-protocol time-series writes, plus a projection read |
| `test_server_wire_protocols.py` | PostgreSQL (including a bound-parameter `{cypher}` query and Arrow ADBC), Bolt, and the Redis port setting, each with its real client; a default server opens none of their ports |
| `test_server_packaging.py` | The server stack is in the wheel and the API is reachable (fails, never skips) |

### JVM, packaging, and the gates

| File | What it checks |
| --- | --- |
| `test_jvm.py` | `start_jvm()` re-entry, close and reopen in one process, and exit with an unclosed database |
| `test_jvm_args.py` | JVM argument handling and the `conftest.py` hooks |
| `test_jvm_payload.py` | A static check that no Python list crosses into the JVM |
| `test_sigint.py` | Ctrl-C raises `KeyboardInterrupt` and runs cleanup once the JVM is started; `interrupt=True` keeps JPype's default (not collected on Windows) |
| `test_bridge_fixes.py` | Two fixes in the Java bridge: nested values read back as Python in the same transaction, and a date written as midnight UTC in any JVM time zone |
| `test_java_package_shadowing.py` | A folder named `java/` or `com/` must not change what a query returns |
| `test_runtime_cache.py` | The dev-mode runtime cache follows the wheel it was extracted from |
| `test_jar_provenance.py` | The wheel can say which engine it carries, not only which version it is |
| `test_wheel_platform_tag.py` | The wheel's manylinux platform tag, and `__version__` equals the installed distribution version |
| `test_wheel_size.py` | The wheel size gate: a wheel at or over 100 decimal megabytes fails the build |
| `test_check_test_skips.py` | The skip gate described below |

### Docs and open engine findings

| File | What it checks |
| --- | --- |
| `test_docs_examples.py` | Python blocks from the documentation run as code; see [Documentation example tests](#documentation-example-tests) |
| `test_count_pushdown_known_issues.py` | The openCypher count push-down and `BYTE` aggregate entries on [Known Engine Issues](../guide/known-issues.md): their workarounds pass, and plain regression tests assert the right answer (fixed in 26.11.1; they fail on the 26.10.1 wheel) |
| `test_light_edge_and_view_known_issues.py` | The two open entries on [Known Engine Issues](../guide/known-issues.md) about openCypher counts: a one-hop `count(*)` over `light_edges=True` edges in an edge type that is not `LIGHTWEIGHT`, and a pattern predicate over an edge type that a Graph Analytical View does not list. Plain tests of the workarounds and of the cases that are not affected, and strict `xfail` tripwires of the right counts (upstream #9378 and #9377) |
| `test_null_index_known_issues.py`, `test_declared_type_known_issues.py`, `test_dml_plan_cache_known_issues.py` | Plain regression tests for engine bugs that 26.10.1 fixed (null keys and index lookups, declared properties, positional parameters in a cached DML plan), with the workarounds that were documented for them |

## Markers

The markers are registered in `bindings/python/pyproject.toml` (`server`, `server_wire`, and
`integration`); the repo-root `pyproject.toml` mirrors that block.

| Marker | Tests |
| ------ | ----- |
| `server` | `test_server_creation`, `test_server_database_operations`, `test_server_custom_config`, `test_server_context_manager`, and `test_failed_server_start_does_not_hang_process_exit` in `test_server.py`, `test_server_starts_and_serves_http` in `test_server_packaging.py`, and `test_docs_api_access_examples` in `test_docs_examples.py` |
| `server_wire` | Every test in `test_server_wire_protocols.py` (module-level `pytestmark`) |

`integration` is registered, but no test uses it.

```bash
uv run pytest -m server
uv run pytest -m "not server"
```

`-m "not server"` leaves out only the tests marked `server`. Other tests start a server too:
`test_server_patterns.py`, `test_server_http_endpoints.py`, and `test_server_wire_protocols.py`
(marked `server_wire`). To leave out every server-starting test:

```bash
uv run pytest -m "not server and not server_wire" \
  --ignore=bindings/python/tests/test_server_patterns.py \
  --ignore=bindings/python/tests/test_server_http_endpoints.py
```

## Skips and expected failures

CI runs the suite with no skips: `scripts/check_test_skips.py` fails the `test` job on any skip
in the JUnit XML, and its list of accepted skips is empty (`tests/test_check_test_skips.py` tests
the gate). A skip is a test that should have run and did not, so the suite does not use one for
anything it can state otherwise:

- **A test file that cannot run on a platform is left out of collection**, not skipped:
  `tests/conftest.py` sets `collect_ignore` for `test_sigint.py` on Windows (it sends SIGINT to a
  child process) and for `test_docs_examples.py` on the upstream pull request branch, which has
  no `docs/`. A parametrized case Windows cannot create (a directory name with a question mark
  in `test_importer_api.py`) is not generated there.
- **An optional Python package** (numpy, pandas, pyarrow, requests, psycopg,
  adbc-driver-postgresql, neo4j) uses `pytest.importorskip` without a custom reason. A run
  without the package skips locally. CI installs every optional package the tests import (`numpy`,
  `pandas`, `pyarrow`, `requests`, `psycopg`, `neo4j`, `redis`, `adbc-driver-postgresql`), and a
  step fails the job if any test skipped for a missing import, so none of them skips there.
- **A bundled feature never skips**: OpenCypher, the geo and graph-algorithm SQL functions, time
  series, the HASH index, vector encodings, the importers, and the server stack run and fail when
  they are missing.

A skip that is truly unavoidable (a Windows limitation, a case that needs an engine fix that is
still upstream) goes on the list in `scripts/check_test_skips.py` with the platform, the reason,
and the upstream issue. For an engine bug prefer a strict `xfail`: it fails the suite as soon as
the fix reaches the engine the suite runs on, which is the cue to convert it to a plain test.
CI builds its wheel from upstream's current snapshot jars, so that can be days before a release
carries the fix. The entry stays on the Known Engine Issues page until a release that carries the
fix ships.

A passing run ends with a summary of the form `N passed`, or `N passed, K xfailed` while an engine
finding is open, with no failures or errors. The strict xfails are the open engine findings listed
on [Known Engine Issues](../guide/known-issues.md), and nothing skips. Run with `-rs` to see why a test skipped locally.

## Documentation example tests

`tests/test_docs_examples.py` runs Python blocks from the documentation as real code, each in its
own subprocess with its own working directory, so a snippet that starts the JVM cannot disturb
another. One test covers each group of pages (paths relative to `bindings/python/docs/`):

- `test_docs_installation_examples`: `getting-started/installation.md`.
- `test_docs_index_and_quickstart_examples`: `index.md` and `getting-started/quickstart.md`. The
  batch-insert snippet it also runs is a copy written in the test, so an edit to that quickstart
  block is not caught.
- `test_docs_api_access_examples` (marked `server`): the four access paths in
  `api-access-methods.md`.
- `test_docs_transaction_examples`: `guide/core/transactions.md`.
- `test_docs_example_pages`: the `INSERT INTO Task SET` block from
  `examples/01_simple_document_store.md`, against a seeded `Task` schema. The social-network
  script in the same test is written in the test, so an edit to `examples/02_social_network_graph.md`
  is not caught.
- `test_docs_core_query_examples`: `guide/core/queries.md`, several blocks inside a database seeded
  with the data the page assumes.
- `test_docs_graph_guide_examples`: `guide/graphs.md`.

The test finds a block by a piece of text it contains and fails if no Python block on the page
contains that text. A block passes when its subprocess exits 0 within 120 seconds; printed
output is not compared. Most Python blocks in the docs are not run. When you add or rewrite an
example that should stay runnable, edit the page, extend `tests/test_docs_examples.py` with a
needle for the new block, and rerun the file.

## Writing a test for this suite

1. **Use the shared fixtures** in `tests/conftest.py`: `temp_db_path` (a fresh database path),
   `temp_db` (an open database, closed and deleted afterwards), `temp_server_root`, and
   `temp_dir_factory`, or pytest's own `tmp_path`. Server tests use `TEST_PASSWORD` as the root
   password.
2. **A teardown warns; it never swallows.** A teardown that hides its own failure hides the bug
   with it. `temp_db` shows the pattern: it closes the database if it is still open and turns a
   failed close into a warning.
3. **Do not skip on what the wheel ships.** A test for the server stack, OpenCypher, or any other
   bundled feature runs and fails when the feature is missing: a guard that skips cannot notice
   the feature going missing (the server JARs left the wheel in 26.7.2 and the guarded tests
   skipped into a green suite). Skip only for an optional Python package, through
   `pytest.importorskip` without a custom reason, and leave a file that a platform cannot run
   out of collection (`collect_ignore` in `tests/conftest.py`). A server test carries
   `@pytest.mark.server`.
4. **One JVM serves the whole session.** A `start_jvm()` call with a different configuration
   raises "already started", and engine-wide settings carry from one test to the next, so run
   the full suite after adding a test. Anything that needs its own JVM, a crash, a lock held by
   another process, or an isolated `sys.path` runs in a subprocess.
5. **An optional dependency** goes through `pytest.importorskip("module")` with its default
   reason, so that CI fails when the module is missing. Add the module to the `test` extra in
   `bindings/python/pyproject.toml`, to the install step in
   `.github/workflows/test-python-bindings.yml`, and to the repo-root `pyproject.toml`.
6. **Hang diagnostics are built in.** A test still running after `ARCADEDB_TEST_JAVA_DUMP_AFTER_S`
   seconds (540 by default) prints every Java thread's stack, and `faulthandler_timeout` dumps
   the Python threads at 600 s. `ARCADEDB_PYTEST_FORCE_EXIT=1` ends the session with
   `os._exit(0)` instead of a JVM shutdown, for debugging a hang at exit.
7. **Bandit scans `tests/`** at low severity and low confidence. Put `# nosec B608` on the
   flagged line of an f-string SQL statement, as the existing tests do.

```python
import pytest

import arcadedb_embedded as arcadedb
from tests.conftest import TEST_PASSWORD


def test_insert_is_visible(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE Note")
    with temp_db.transaction():
        temp_db.command("sql", "INSERT INTO Note SET k = 1")
    assert temp_db.query("sql", "SELECT k FROM Note").to_list() == [{"k": 1}]


@pytest.mark.server
def test_server_starts(temp_server_root):
    with arcadedb.create_server(temp_server_root, root_password=TEST_PASSWORD) as server:
        assert server.is_started()
```
