"""Tests for AsyncExecutor with SQL/Cypher-first usage."""

import shutil
import tempfile
import time
from pathlib import Path

import arcadedb_embedded as arcadedb
import pytest

# Submissions used by the record-loss tests. 9,742 is the count from the
# original report: 9,742 Movie vertices submitted, 2,436 stored.
LOSS_REPRO_ROWS = 9_742


def test_async_executor_sql_command_insert_is_exact_at_parallel_one():
    """Every command submitted at parallel level 1 becomes a row.

    This used to run at parallel level 4 and assert `count > 0`, which is the
    assertion shape that let ArcadeData/arcadedb#7615 through: at level 4 the
    executor stores a quarter of what it is given and `count > 0` still passes.
    """
    db_path = Path(tempfile.mkdtemp()) / "test_async_sql_insert"

    try:
        db = arcadedb.create_database(str(db_path))
        db.command("sql", "CREATE DOCUMENT TYPE Item")

        async_exec = db.async_executor().set_parallel_level(1).set_commit_every(1)

        for i in range(200):
            async_exec.command(
                "sql",
                "INSERT INTO Item SET id = ?, name = ?",
                callback=lambda _r: None,
                args=(i, f"Item{i}"),
            )

        async_exec.wait_completion()
        async_exec.close()

        count = db.query("sql", "SELECT count(*) as c FROM Item").first().get("c")
        assert int(count) == 200
        db.close()
    finally:
        shutil.rmtree(db_path, ignore_errors=True)


def test_async_executor_bulk_command_is_exact_at_parallel_one(temp_db):
    """A bulk load through the async command path, at the size that lost rows.

    Parallel level 1 is the only level at which this path is exact, which is
    why the recommended bulk paths are `Database.insert_many` and
    `Database.graph_batch` instead. See ArcadeData/arcadedb#7615.
    """
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Bulk")

    errors = []
    async_exec = db.async_executor().set_parallel_level(1).set_commit_every(1_000)
    async_exec.on_error(errors.append)

    for i in range(LOSS_REPRO_ROWS):
        async_exec.command("sql", "INSERT INTO Bulk SET id = :id", id=i)

    async_exec.wait_completion()
    async_exec.close()

    stored = int(db.query("sql", "SELECT count(*) AS c FROM Bulk").one().get("c"))
    assert stored == LOSS_REPRO_ROWS
    assert errors == []


@pytest.mark.skip(
    reason="ArcadeData/arcadedb#7615: the async executor silently discards "
    "commands above parallel level 1. Un-skip when the engine is fixed."
)
def test_async_executor_bulk_command_is_exact_at_parallel_four(temp_db):
    """The same load at parallel level 4, which is where the records go missing.

    Kept as a skipped test rather than an assertion of the broken behaviour, so
    it starts passing when upstream fixes the engine. Observed on
    arcadedb-engine 26.9.1 and 26.6.1, measured 2026-09-15: of 9,742 submitted,
    2,436, 5,742, and 7,742 stored across runs, with nothing raised, nothing
    logged, and `wait_completion()` returning normally. Only the executor-wide
    `on_error` handler fires, one ConcurrentModificationException per
    rolled-back batch. The assertion below is exact on purpose: how much is
    lost varies, so any tolerance would let the defect back through.
    """
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Bulk4")

    async_exec = db.async_executor().set_parallel_level(4).set_commit_every(1_000)
    for i in range(LOSS_REPRO_ROWS):
        async_exec.command("sql", "INSERT INTO Bulk4 SET id = :id", id=i)

    async_exec.wait_completion()
    async_exec.close()

    stored = int(db.query("sql", "SELECT count(*) AS c FROM Bulk4").one().get("c"))
    assert stored == LOSS_REPRO_ROWS


def test_async_executor_query_callback_collects_rows(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Person")

    with db.transaction():
        for i in range(20):
            db.command(
                "sql",
                "INSERT INTO Person SET id = :id, name = :name",
                {"id": i, "name": f"Person{i}"},
            )

    seen = []

    def on_row(row):
        seen.append(row.get("id"))

    async_exec = db.async_executor().set_parallel_level(2).set_commit_every(10)
    async_exec.query("sql", "SELECT id FROM Person ORDER BY id", on_row)
    async_exec.wait_completion()
    async_exec.close()

    assert seen == list(range(20))


def test_database_close_closes_owned_async_executor(temp_db_path):
    db = arcadedb.create_database(temp_db_path)
    db.command("sql", "CREATE DOCUMENT TYPE Msg")

    async_exec = db.async_executor().set_commit_every(1)
    async_exec.command("sql", "INSERT INTO Msg SET id = :id", id=1)
    async_exec.wait_completion()

    db.close()

    assert async_exec.is_closed() is True

    async_exec.close()


def test_async_executor_close_is_idempotent(temp_db):
    async_exec = temp_db.async_executor()

    async_exec.close()
    async_exec.close()

    assert async_exec.is_closed() is True


def test_async_executor_pending_and_processing_flags(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Msg")

    # parallel level 1: above it the submissions would be partly discarded
    # (ArcadeData/arcadedb#7615), which is noise this flag test does not need.
    async_exec = db.async_executor().set_parallel_level(1).set_commit_every(100)
    assert not async_exec.is_pending()

    for i in range(1000):
        async_exec.command("sql", "INSERT INTO Msg SET id = :id", id=i)

    saw_processing = False
    deadline = time.time() + 1.0
    while time.time() < deadline:
        if async_exec.is_processing():
            saw_processing = True
            break

        try:
            if async_exec._java_async.waitCompletion(0):
                break
        except Exception:  # noqa: BLE001
            # A poll inside a 1 s loop: a throw here means the executor has not
            # started yet, and the wait_completion() below is the real check.
            time.sleep(0.01)
            continue

        time.sleep(0.01)

    async_exec.wait_completion()
    assert async_exec.is_pending() is False

    async_exec.close()


def test_async_executor_getters_and_sync_modes(temp_db):
    db = temp_db
    async_exec = db.async_executor()

    async_exec.set_parallel_level(3)
    async_exec.set_commit_every(123)
    async_exec.set_back_pressure(40)
    async_exec.set_transaction_use_wal(False)
    async_exec.set_transaction_sync("yes_nometadata")

    assert async_exec.get_parallel_level() == 3
    assert async_exec.get_commit_every() == 123
    assert async_exec.get_back_pressure() >= 0
    assert async_exec.is_transaction_use_wal() is False
    assert async_exec.get_transaction_sync() == "yes_nometadata"
    assert async_exec.get_thread_count() >= 1

    async_exec.close()


def test_async_executor_command_error_callback(temp_db):
    db = temp_db
    errors = []

    def on_error(exc):
        errors.append(str(exc))

    async_exec = db.async_executor()
    async_exec.command(
        "sql",
        "INSERT INTO MissingType SET id = :id",
        error_callback=on_error,
        id=1,
    )
    async_exec.wait_completion()
    async_exec.close()

    assert errors, "Expected async error callback to be invoked"


def test_async_executor_global_callbacks(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Log")

    ok_calls = {"count": 0}
    err_calls = {"count": 0}

    def on_ok():
        ok_calls["count"] += 1

    def on_error(_exc):
        err_calls["count"] += 1

    async_exec = db.async_executor().on_ok(on_ok).on_error(on_error)

    for i in range(5):
        async_exec.command("sql", "INSERT INTO Log SET id = :id", id=i)

    async_exec.wait_completion()
    async_exec.close()

    assert ok_calls["count"] >= 1
    assert err_calls["count"] >= 0
