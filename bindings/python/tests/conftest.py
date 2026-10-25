"""
Shared pytest fixtures and configuration for ArcadeDB tests.
"""

import os
import shutil
import sys
import tempfile
import threading

import pytest

# A test file that cannot run here is not collected, so nothing is reported as skipped: a skip means
# a test that should have run, and scripts/check_test_skips.py fails the CI job on any skip.
collect_ignore = []
# Files that cannot run on Windows (native-wheel/parity/parity_wheel.py reads this table too: it passes every file to pytest by name,
# and a file named on the command line is collected even when it is in collect_ignore).
WINDOWS_NOT_APPLICABLE = {
    # test_sigint.py sends SIGINT to a child process, which Windows cannot deliver
    "test_sigint.py": "SIGINT to a child process",
    # LadybugDB's compiled module does not load in this process on Windows (it falls back to a C-API library its
    # wheel does not ship), so the Cypher half of the equivalence checks runs on Linux and macOS (#347)
    "test_equivalence_ladybug.py": "LadybugDB does not load on Windows",
}
if sys.platform == "win32":
    collect_ignore.extend(WINDOWS_NOT_APPLICABLE)
if os.environ.get("ARCADEDB_BACKEND", "jpype").lower() != "native":
    # Java -> Python upcalls (Python functions in SQL) exist on the native backend only
    collect_ignore.append("test_native_udf.py")
    # the native library's start-up output (#477) can only be checked with the native library loaded
    collect_ignore.append("test_native_startup_runtime.py")
if not os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")):
    # the upstream pull request branch has no docs/ directory
    collect_ignore.append("test_docs_examples.py")


# ARCADEDB_BACKEND=native (experimental, branch native-spike only): the same suite runs against libarcadedb. A test
# that needs a Java object API raises NotOnNativeYet and is reported as a skip whose reason starts with "NOTYET";
# a file about the JVM or the JPype wheel is not collected and listed in NATIVE_NOT_APPLICABLE.
NATIVE_NOT_APPLICABLE = {
    "test_jvm.py": "JVM start-up and settings",
    "test_jvm_args.py": "JVM arguments",
    "test_jvm_payload.py": "JVM bridge payload",
    "test_jar_provenance.py": "jar fingerprint of the JPype wheel",
    "test_java_package_shadowing.py": "JPype package import hooks",
    "test_wheel_platform_tag.py": "JPype wheel tag",
    "test_wheel_size.py": "JPype wheel size",
    "test_server_packaging.py": "JPype wheel contents",
    "test_runtime_cache.py": "JRE runtime cache of the JPype wheel",
}
if os.environ.get(
    "ARCADEDB_BACKEND", "jpype"
).lower() == "native" and not os.environ.get("NATIVE_PARITY_ALL"):
    collect_ignore.extend(NATIVE_NOT_APPLICABLE)


# Tests that exercise the JVM itself, so the native backend (no JVM, no jars) has nothing to run. Skipped before they start, at
# collection time, with the reason (reported as "NA-JVM: <why>"). The key is "<file>::[<Class>::]<test function>": every parameter
# of the function, or one parameter id as in "test_x.py::test_y[java]". A test is listed only when it reaches into the JVM on purpose:
# it builds or reads a Java object (jpype.JClass, a Java array, db._java_db, _java_index, the bridge classes), counts JPype bridge
# crossings, or patches a hook of the JPype path. A failure text never puts a test on this list, and a failing test is never turned
# into a skip: a test whose behaviour native shares has to pass on native, and one that fails there is a bug to file (an
# xfail(strict=True) naming the BACKLOG-bindings.md row, so it turns red when fixed), not an entry here.
# A feature the native wheel lacks on purpose raises NotOnNativeYet from the native code, which pytest_runtest_makereport reports as NOTYET.
JAVA_CLASS = "builds a java.* object through JPype"
JAVA_ARRAY = "builds a Java array through JPype (jpype.JArray)"
JAVA_DB = "reads the Java database behind the wrapper (db._java_db)"
JAVA_INDEX = "reads the Java index behind the wrapper (_java_index: getClass, metadata)"
BRIDGE_COUNT = (
    "counts or intercepts the JPype bridge crossings (an internal of the JPype path)"
)
NATIVE_NA_JVM_TESTS = {
    # JVM start-up, signals and settings
    "test_sigint.py::test_ctrl_c_raises_keyboard_interrupt_and_runs_cleanup[java]": "a Java call blocked in JPype's SIGINT handler (#179)",
    "test_sigint.py::test_interrupt_true_keeps_the_jvm_handling_sigint": "start_jvm(interrupt=True): the JVM handles SIGINT",
    "test_docs_examples.py::test_docs_installation_jvm_examples": "documents start_jvm() and jvm_kwargs",
    "test_server_wire_protocols.py::test_the_host_reaches_exactly_the_listener_bind_settings": "reads the engine's GlobalConfiguration through the JVM",
    "test_server_wire_protocols.py::test_wire_listeners_stay_on_loopback_by_default": "reads the server's GlobalConfiguration through the JVM",
    "test_server_wire_protocols.py::test_host_applies_to_every_wire_listener": "reads the server's GlobalConfiguration through the JVM",
    "test_server_wire_protocols.py::test_a_protocol_host_overrides_the_server_host_for_that_protocol_only": "reads the server's GlobalConfiguration through the JVM",
    "test_sql_constraints_and_maintenance.py::test_backup_check_and_rebuild_index_statements": "sets GlobalConfiguration.SERVER_BACKUP_DIRECTORY through the JVM",
    "test_vector_params_verification.py::TestVectorParams::test_jvm_heap_check": "reads java.lang.Runtime through JPype",
    "test_vector_params_verification.py::TestVectorParams::test_wrapper_default_matches_engine_default": "reads the engine default through java.lang.String and GlobalConfiguration",
    "test_vector_params_verification.py::TestVectorParams::test_omitted_max_connections_reaches_the_index": "reads the engine default through java.lang.String and GlobalConfiguration",
    "test_vector_sql.py::TestVectorSearchOptionsSql::test_where_map_and_condition": "picks the expected behaviour by com.arcadedb.Constants.getRawVersion() through JPype",
    "test_vector_sql.py::TestVectorSearchOptionsSql::test_where_combines_with_filter": "picks the expected behaviour by com.arcadedb.Constants.getRawVersion() through JPype",
    # Java objects built or read by the test
    "test_conversion_fixes.py::test_java_instants_convert_without_losing_microseconds": JAVA_CLASS,
    "test_type_conversion.py::test_offset_datetime_conversion": JAVA_CLASS,
    "test_type_conversion.py::test_scalar_list_crosses_as_one_array_with_the_same_types": "asserts the converted value is a java.util.ArrayList",
    "test_type_conversion.py::TestPrimitiveArrayFormats::test_int_array": JAVA_ARRAY,
    "test_type_conversion.py::TestPrimitiveArrayFormats::test_long_array": JAVA_ARRAY,
    "test_percall_calls.py::test_float_array_conversion_gives_a_float_array": 'asserts the converted value is a Java float[] (getClass() == "[F")',
    "test_typed_rows.py::test_java_values_sql_cannot_produce": JAVA_CLASS,
    "test_typed_rows.py::test_value_python_cannot_hold_raises_as_before": JAVA_CLASS,
    "test_typed_rows.py::test_object_array_raises_as_before": JAVA_ARRAY,
    "test_typed_rows.py::test_iter_dicts_reads_one_row_at_a_time": "builds a Java InternalResultSet",
    "test_typed_rows.py::test_vertex_edges_match_the_engine_iteration": "the oracle is the Java Vertex.getEdges iteration",
    "test_typed_rows.py::test_vector_search_hits_match_the_per_hit_path": "the oracle is the Java vector index (findNeighborsFromVector)",
    "test_typed_rows.py::test_a_batch_of_wide_rows_ends_at_a_few_megabytes": "calls the bridge's typed_rows.nextRows on the Java result set",
    "test_typed_rows.py::test_the_batch_says_whether_the_result_set_is_drained": "calls the bridge's typed_rows.nextRows on the Java result set",
    "test_graph_api.py::test_document_wrap_static_method": "wraps the Java object behind a result (_java_result)",
    "test_legacy_temporal_implementations.py::test_the_engine_hands_back_the_configured_class_holding_the_utc_instant": JAVA_DB,
    "test_graph_batch.py::test_graph_batch_leaves_the_callers_wal_setting_alone": JAVA_DB,
    "test_transaction_config.py::test_set_wal_flush_is_database_wide": JAVA_DB,
    "test_run_in_transaction_retry.py::test_contended_commits_spend_their_budget_before_failing": JAVA_DB,
    # Java exceptions thrown and engine hooks set from the test
    "test_run_in_transaction_retry.py::test_every_need_retry_exception_is_retried": "throws Java exceptions (com.arcadedb.exception.*) from the test",
    "test_run_in_transaction_retry.py::test_the_budget_is_spent_before_the_conflict_reaches_the_caller": "throws Java exceptions (com.arcadedb.exception.*) from the test",
    "test_run_in_transaction_retry.py::test_the_wait_the_refusing_side_asked_for_is_honored": "throws Java exceptions (com.arcadedb.exception.*) from the test",
    "test_run_in_transaction_retry.py::test_the_wait_is_capped_by_retry_after_max_wait": "throws Java exceptions (com.arcadedb.exception.*) from the test",
    "test_run_in_transaction_retry.py::test_a_block_that_committed_part_of_its_work_is_not_replayed": "throws a Java ConcurrentModificationException from the test (native: test_run_in_transaction_partial_commit.py)",
    "test_graph_batch.py::test_graph_batch_outside_the_callers_transactions": "sets GraphBatch.TEST_BEFORE_VERTEX_COMMIT_HOOK, a Java static, through JPype",
    "test_graph_batch.py::test_graph_batch_create_vertices_refuses_before_any_commit_attempt": "sets GraphBatch.TEST_BEFORE_VERTEX_COMMIT_HOOK, a Java static, through JPype",
    "test_graph_batch.py::test_graph_batch_create_vertices_keyboard_interrupt_rolls_back": "patches GraphBatch._create_vertices_json_bulk, the JPype path's bulk call",
    # parameter conversion and bridge crossings of the JPype path
    "test_parameter_binding.py::test_each_parameter_shape_reaches_one_java_overload": "inspects the Java Database overloads through JPype",
    "test_parameter_binding.py::test_async_parameters_reach_one_java_overload": "inspects the Java DatabaseAsyncExecutor overloads through JPype",
    "test_parameter_binding.py::TestScalarParametersTakeTheShortPath::test_a_java_array_value_is_not_converted_and_binds_as_before": JAVA_ARRAY,
    "test_parameter_binding.py::TestScalarParametersTakeTheShortPath::test_non_scalars_keep_the_general_path": "counts JPype parameter conversions",
    "test_parameter_binding.py::TestScalarParametersTakeTheShortPath::test_a_subclass_of_a_scalar_is_not_assumed_to_be_one": "counts JPype parameter conversions",
    "test_resultset.py::test_to_dict_one_crossing_matches_the_per_property_path": "needs the bridge jar's RowAccess class",
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_to_list_makes_one_call_for_a_short_result": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_to_list_of_an_empty_result_makes_one_call": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_to_json_list_makes_one_call_for_a_short_result": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_a_full_batch_still_ends_on_the_next_call": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_a_drained_set_reads_as_empty_and_is_not_an_error": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_python_does_not_cross_the_bridge_to_close_a_drained_set": BRIDGE_COUNT,
    "test_resultset.py::TestSmallResultsCostOneBridgeCall::test_the_bridge_closes_what_it_drains_and_only_that": BRIDGE_COUNT,
    "test_vector.py::TestLSMVectorIndex::test_lsm_vector_search_looks_up_all_hits_in_one_bridge_call": BRIDGE_COUNT,
    "test_vector.py::TestLSMVectorIndex::test_lsm_vector_search_uses_database_rid_conversion": "intercepts Database.to_java_rid, the JPype path's RID conversion",
    # the Java index behind the wrapper
    "test_vector.py::TestLSMVectorIndex::test_create_vector_index_with_pq_params": JAVA_INDEX,
    "test_vector.py::TestLSMVectorIndex::test_create_vector_index_with_custom_id_property": JAVA_INDEX,
    "test_vector.py::TestLSMVectorIndex::test_lsm_vector_search_approximate_product": JAVA_INDEX,
    "test_vector.py::TestLSMVectorIndex::test_lsm_vector_search_approximate_typeindex": JAVA_INDEX,
    **{
        f"test_vector_params_verification.py::TestVectorParams::{name}": JAVA_INDEX
        for name in (
            "test_quantization_param",
            "test_store_vectors_in_graph_param",
            "test_encoding_param",
            "test_add_hierarchy_param",
            "test_per_index_cache_params",
            "test_quantization_none",
            "test_quantization_binary",
            "test_quantization_product",
        )
    },
}


def _native():
    return os.environ.get("ARCADEDB_BACKEND", "jpype").lower() == "native"


def pytest_collection_modifyitems(config, items):
    if not _native():
        return
    for item in items:
        # "<file>::[<Class>::]<function>[<param id>]", the file without its directory
        test_id = f"{item.path.name}::{item.nodeid.split('::', 1)[-1]}"
        reason = NATIVE_NA_JVM_TESTS.get(test_id) or NATIVE_NA_JVM_TESTS.get(
            test_id.split("[", 1)[0]
        )
        if reason:
            item.add_marker(pytest.mark.skip(reason=f"NA-JVM: {reason}"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On the native backend, report a test as NOTYET when the native code raised NotOnNativeYet.

    That is the one explicit signal: the native code path names a feature the wheel does not have (yet) by raising a dedicated
    exception, the exception itself or an exception raised from it. Nothing else is turned into a skip. In particular no failure text
    is matched: a text such as "assert None is not None" or "KeyError: 'flush'" is also what a real bug looks like.
    """
    outcome = yield
    if not _native():
        return
    report = outcome.get_result()
    if call.excinfo is None or report.passed:
        return
    from arcadedb_embedded._native import NotOnNativeYet

    exc, seen = call.excinfo.value, 0
    while exc is not None and seen < 8:
        if isinstance(exc, NotOnNativeYet):
            report.outcome = "skipped"
            report.longrepr = (
                str(item.fspath),
                item.location[1] or 0,
                f"NOTYET: {exc}",
            )
            return
        exc, seen = exc.__cause__, seen + 1


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # HotSpot routinely raises access violations it handles itself
    # (safepoints, implicit null checks). On Windows, pytest's faulthandler
    # prints a fatal-looking Python stack for each one even though nothing
    # crashed. Disable it there; real crashes still fail the run, and
    # faulthandler_timeout's hang dump does not depend on it.
    # trylast: pytest's own faulthandler plugin enables it in its
    # pytest_configure, and a conftest hook otherwise runs before that.
    # This hook was dead from 2026-07-25 to 2026-09-29: a second
    # pytest_configure further down replaced it (test_jvm_args pins it now).
    import sys

    if sys.platform == "win32":
        import faulthandler

        if faulthandler.is_enabled():
            faulthandler.disable()


# A test still running this long gets every Java thread's stack on stderr,
# shortly before faulthandler_timeout (600 s in pyproject.toml) dumps the
# Python threads. The Python dump alone shows a test waiting inside a Java
# call and nothing about why, which is all a Windows vector-search hang left
# behind twice (humemai/arcadedb-embedded-python#10).
JAVA_DUMP_AFTER_S = float(os.environ.get("ARCADEDB_TEST_JAVA_DUMP_AFTER_S", "540"))


def dump_java_threads(reason, out=None):
    """Write every Java thread's name, state, and stack to `out` (stderr).

    Returns False when the JVM is not running, so there is nothing to dump.
    """
    import jpype

    out = out or sys.stderr
    if not jpype.isJVMStarted():
        return False
    traces = jpype.JClass("java.lang.Thread").getAllStackTraces()
    lines = [f"=== Java threads: {reason} ==="]
    for thread in traces.keySet():
        lines.append(
            f'"{thread.getName()}" daemon={thread.isDaemon()} state={thread.getState()}'
        )
        lines.extend(f"    at {frame}" for frame in traces.get(thread))
    out.write("\n".join(lines) + "\n")
    out.flush()
    return True


def _dump_java_threads_for(nodeid, capman):
    # Captured output of a test that never finishes is lost when the job is
    # killed, so the dump goes past pytest's capture, as a debugger's would.
    try:
        if capman is not None:
            with capman.global_and_fixture_disabled():
                dump_java_threads(
                    f"{nodeid} still running after {JAVA_DUMP_AFTER_S:.0f} s"
                )
        else:
            dump_java_threads(f"{nodeid} still running after {JAVA_DUMP_AFTER_S:.0f} s")
    except Exception as exc:  # the dump is evidence; it must not fail the run
        sys.stderr.write(f"Java thread dump failed: {exc!r}\n")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    capman = item.config.pluginmanager.getplugin("capturemanager")
    timer = threading.Timer(
        JAVA_DUMP_AFTER_S, _dump_java_threads_for, args=(item.nodeid, capman)
    )
    timer.daemon = True
    timer.start()
    try:
        return (yield)
    finally:
        timer.cancel()


# Shared test password used by server-mode tests. ArcadeDB requires >= 8 chars.
# Hardcoded test fixture, not a real credential.
TEST_PASSWORD = "test12345"  # nosec B105


@pytest.fixture
def temp_server_root():
    """Create a temporary server root directory."""
    temp_dir = tempfile.mkdtemp(prefix="arcadedb_test_server_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    temp_dir = tempfile.mkdtemp(prefix="arcadedb_test_db_")
    db_path = os.path.join(temp_dir, "test_db")
    yield db_path
    # Cleanup
    if os.path.exists(temp_dir):
        # Force garbage collection to release file handles (Windows fix)
        import gc

        gc.collect()

        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, files might still be locked by Java process
            # Wait a bit and try again
            import time

            time.sleep(0.5)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                # If still locked, ignore (OS will clean up temp eventually)
                pass


@pytest.fixture
def temp_db():
    """Create a temporary database, yield it, and clean up."""
    import arcadedb_embedded as arcadedb

    temp_dir = tempfile.mkdtemp(prefix="arcadedb_test_db_")
    db_path = os.path.join(temp_dir, "test_db")

    db = arcadedb.create_database(db_path)
    yield db

    # Cleanup
    # Database has is_open(), not is_closed(): the old call raised
    # AttributeError, the bare except swallowed it, and the directory was
    # removed under a still-open database, which the engine then failed to
    # flush at JVM shutdown ("Failed to allocate sparse segment component ...
    # No such file or directory", 2026-09-07). No fixture test ever closed.
    try:
        if db.is_open():
            db.close()
    except Exception as exc:  # noqa: BLE001
        # Never silent: a swallowed teardown is how the is_closed() bug hid for
        # ten months. Warn so it shows in the summary, but do not fail the test
        # that just passed for a close-time problem it did not cause.
        import warnings

        warnings.warn(f"temp_db teardown: close failed: {exc!r}", stacklevel=1)

    # Force garbage collection to release file handles (Windows fix)
    import gc

    gc.collect()

    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, files might still be locked by Java process
            import time

            time.sleep(0.5)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                pass


@pytest.fixture
def temp_dir_factory():
    """Factory fixture to create multiple temporary directories with cleanup."""
    temp_dirs = []

    def _create_temp_dir(prefix="arcadedb_test_"):
        """Create a temporary directory and register it for cleanup."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        temp_dirs.append(temp_dir)
        return temp_dir

    yield _create_temp_dir

    # Cleanup all created directories
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def pytest_unconfigure(config):
    """
    Prefer graceful JVM shutdown after pytest completes.

    The old test suite used `os._exit(0)` unconditionally because JVM shutdown
    used to hang. The suite now exits cleanly after explicit async-executor
    ownership cleanup, so graceful shutdown is the default behavior.

    `ARCADEDB_PYTEST_FORCE_EXIT=1` is retained only as an emergency override
    for debugging future shutdown regressions.
    """
    import sys

    from arcadedb_embedded.jvm import shutdown_jvm

    # Flush all output to ensure we see test results
    sys.stdout.flush()
    sys.stderr.flush()

    if os.environ.get("ARCADEDB_PYTEST_FORCE_EXIT", "0") == "1":
        os._exit(0)

    shutdown_jvm()


def pytest_sessionfinish(session, exitstatus):
    """Session finish hook."""
    pass


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Terminal summary hook."""
    pass
