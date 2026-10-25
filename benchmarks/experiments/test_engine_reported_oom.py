"""An engine's OWN out-of-memory error is an envelope failure, printed OOM, the same for every engine (PAGE-SPEC "a dash means that
and only that", DECISIONS #111).

Before this, `export_web._censored_cells` marked a cell OOM only for a kernel kill (`oom_killed`, or the served engine's own
`server_oom_killed`) and filed everything else under `err`. DuckPGQ's l2 OLTP sf1 cell on mini failed with rc=1 and DuckDB's own
`_duckdb.OutOfMemoryException` (DuckDB stopped itself at its default memory_limit inside the 8g container); the page printed `err`.
No stage needs to change: classification happens here, at export time, from the `error` text and the `client_log` the runner already
writes into every failed row.
"""
import pytest

import export_web as E

# The tail of the real `error` field of l2_duckpgq_graph_oltp_sf1_r1 (mini, runs_page_e85469273_2611.jsonl), verbatim.
DUCKDB_REAL = """^^^^^^^^^^^^^^^^^
_duckdb.OutOfMemoryException: Out of Memory Error: failed to allocate data of size 8.0 GiB (684.3 MiB/6.3 GiB used)

Possible solutions:
* Reducing the number of threads (SET threads=X)
* Disabling insertion-order preservation (SET preserve_insertion_order=false)
* Increasing the memory limit (SET memory_limit='...GB')

See also https://duckdb.org/docs/stable/guides/performance/how_to_tune_workloads"""

# The runner's own text for a kernel kill that printed nothing (runner.py, `detail`).
KERNEL_KILL = ("container exited 137 with no output (cgroup OOM kill: raise the envelope or bound the harness's peak memory)")


def _row(backend="duckpgq_graph", **kw):
    row = {"lane": "l2", "scale": "sf1", "backend": backend, "workload": "oltp", "mem_cap": "8g", "rc": 1, "oom_killed": False}
    row.update(kw)
    return row


@pytest.fixture()
def cells(monkeypatch, tmp_path):
    """`cells([row, ...])` -> what `_censored_cells` makes of a run log holding those rows. RESULTS is a temp dir so a `client_log`
    file can be put in `raw/` beside the rows."""
    (tmp_path / "raw").mkdir()
    monkeypatch.setattr(E, "RESULTS", tmp_path)
    monkeypatch.setattr(E, "_rule_censored", lambda taken, clean: {})      # the cap rule is another test's business
    monkeypatch.delenv("BENCH_ENGINE_COMMIT", raising=False)

    def run(rows):
        monkeypatch.setattr(E, "_run_log_rows", lambda: rows)
        monkeypatch.setattr(E, "_CENSORED_CACHE", None)
        return E._censored_cells()
    run.raw = tmp_path / "raw"
    return run


def _only(got):
    assert len(got) == 1
    return next(iter(got.values()))


# ---- the cases the task names ---------------------------------------------------------------------------------------------

def test_duckdb_own_out_of_memory_error_prints_oom(cells):
    secs = _only(cells([_row(error=DUCKDB_REAL)]))
    assert E._outcome_kind(secs) == ("envelope", "OOM")
    assert secs[1] == "8g"                       # the envelope the cell had, off the row's mem_cap


def test_java_out_of_memory_error_prints_oom(cells):
    text = ('Traceback (most recent call last):\n  File "l2_graph.py", line 1\njpype.JException: java.lang.OutOfMemoryError\n'
            "\tat java.base/java.util.Arrays.copyOf(Arrays.java:3482)")
    assert E._outcome_kind(_only(cells([_row("arcadedb_graph", error=text)]))) == ("envelope", "OOM")


def test_a_generic_error_stays_err(cells):
    secs = _only(cells([_row(error="ValueError: boom")]))
    assert E._outcome_kind(secs) == ("failed", "err")
    assert secs == "ValueError: boom"


def test_a_dropped_connection_stays_lost(cells):
    assert E._outcome_kind(_only(cells([_row(error="ServiceUnavailable: connection reset by peer")]))) == ("failed", "lost")


def test_the_kernel_kill_is_unchanged(cells):
    secs = _only(cells([_row(rc=137, oom_killed=True, error=KERNEL_KILL)]))
    assert E._outcome_kind(secs) == ("envelope", "OOM")
    assert secs[:2] == ("envelope", "8g")
    served = _only(cells([_row(rc=1, server_oom_killed="True", error="Name or service not known")]))
    assert E._outcome_kind(served) == ("envelope", "OOM")        # the served engine's own State.OOMKilled, as before


def test_a_timeout_is_still_a_timeout_whatever_the_log_says(cells):
    (cells.raw / "x.clientlog").write_text("java.lang.OutOfMemoryError")
    secs = _only(cells([_row(rc=124, error="timeout_after_7200s", client_log="x.clientlog")]))
    assert E._outcome_kind(secs) == ("censored", ">2h")


def test_a_clean_row_clears_the_cell(cells):
    assert cells([_row(error=DUCKDB_REAL), _row(rc=0, error=None)]) == {}      # same rule as for every other failure


# ---- the signature list ---------------------------------------------------------------------------------------------------

def test_every_signature_names_its_engine_and_cites_a_source():
    assert E.ENGINE_OOM_SIGNATURES
    for engine, needle, source in E.ENGINE_OOM_SIGNATURES:
        assert engine and needle and len(source) > 20, (engine, needle)
        assert needle == needle.lower(), f"{needle!r}: signatures are matched case-insensitively and written lower case"
    assert len({n for _, n, _ in E.ENGINE_OOM_SIGNATURES}) == len(E.ENGINE_OOM_SIGNATURES)


# One text per engine, each as the vendor prints it (see the sources in ENGINE_OOM_SIGNATURES).
SAMPLES = [
    ("duckdb", DUCKDB_REAL),
    ("java", "Exception in thread \"main\" java.lang.OutOfMemoryError"),
    ("postgresql", 'psycopg.errors.OutOfMemory: out of memory\nDETAIL:  Failed on request of size 1073741824 in memory context "ExecutorState".'),
    ("memgraph", "{neo4j_code: Memgraph.TransientError.MemgraphError.MemgraphError} {message: Memory limit exceeded!}"),
    ("memgraph", "Memory limit exceeded! Attempting to allocate a chunk of 1.00GiB which would put the current use to 9.00GiB"),
    ("neo4j", "{code: Neo.TransientError.General.OutOfMemoryError} {message: There is not enough memory to perform the current task.}"),
    ("neo4j", "{code: Neo.TransientError.General.MemoryPoolOutOfMemoryError} {message: The allocation of an extra 2.0 MiB would use more than the limit}"),
]


@pytest.mark.parametrize("engine,text", SAMPLES, ids=[f"{e}-{i}" for i, (e, _) in enumerate(SAMPLES)])
def test_each_engines_own_text_is_recognised(engine, text):
    assert E.engine_reported_oom(text) is not None


@pytest.mark.parametrize("text", [
    "", None, "ValueError: boom", "Increasing the memory limit (SET memory_limit='...GB')",
    "image-defaults arm is not at the image's defaults: heap 8g != 6g", "server_not_ready", "driver_no_output",
    # A MemoryError in the Python client is the HARNESS running out of memory, and a harness failure never gets an engine mark.
    "MemoryError: Unable to allocate 8.0 GiB for an array",
])
def test_text_that_is_not_an_engine_out_of_memory_error_is_not(text):
    assert E.engine_reported_oom(text) is None


# ---- the client log, for an error field whose 800-character tail lost the exception line --------------------------------------

def test_the_client_log_is_read_when_the_error_tail_lost_the_signature(cells):
    (cells.raw / "l2_x_r1.clientlog").write_text("java.lang.OutOfMemoryError\n" + "\tat a.b.C.d(C.java:1)\n" * 50)
    tail_only = "\tat a.b.C.d(C.java:1)\n" * 30
    secs = _only(cells([_row("arcadedb_graph", error=tail_only, client_log="l2_x_r1.clientlog")]))
    assert E._outcome_kind(secs) == ("envelope", "OOM")


def test_a_client_log_without_a_signature_and_a_missing_one_change_nothing(cells):
    (cells.raw / "l2_x_r1.clientlog").write_text("ValueError: boom\n")
    assert E._outcome_kind(_only(cells([_row(error="ValueError: boom", client_log="l2_x_r1.clientlog")]))) == ("failed", "err")
    assert E._outcome_kind(_only(cells([_row(error="ValueError: boom", client_log="gone.clientlog")]))) == ("failed", "err")


# ---- what the page says --------------------------------------------------------------------------------------------------

def test_the_note_does_not_claim_a_kernel_kill_for_an_engine_that_stopped_itself(cells):
    cell = _only(cells([_row(error=DUCKDB_REAL, client_peak_mib=6500.0)]))
    E._CENSORED_CACHE = {("l2", "sf1", "duckpgq_graph", "oltp"): cell}
    (note,) = E._censored_notes("l2")
    assert "8g memory envelope" in note and "6,500 MiB" in note
    assert "out-of-memory error" in note and "killed by the kernel" not in note
    assert "did not run out of time" in note


def test_the_kernel_kill_note_is_unchanged(cells):
    cell = _only(cells([_row(rc=137, oom_killed=True, error=KERNEL_KILL)]))
    E._CENSORED_CACHE = {("l2", "sf1", "duckpgq_graph", "oltp"): cell}
    (note,) = E._censored_notes("l2")
    assert "and was killed by the kernel, the same envelope every engine on this table had" in note


def test_the_legend_defines_oom_for_both_ways_of_getting_there():
    (legend,) = E._mark_legend({"OOM"})
    assert "kernel" in legend and "engine" in legend
