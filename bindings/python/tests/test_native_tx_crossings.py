"""The native wheel spends the fewest library crossings a transaction needs.

Every ``arcadedb_n_tx`` call is one trip into the native library: a ctypes call, a malloc'd JSON reply, ``string_at``, a decode and a
``json.loads``. The reply of begin, commit and rollback already carries the whole transaction state (``active``, ``depth`` and
``commits``), so a caller that needs the state right after one of these calls must not ask for it again with a mark.

The counts are crossings, not seconds: they are deterministic. The behaviour tests next to them pin what the marks are for (a caller's
transaction is never rolled back by a nested block, a retry rolls the failed attempt back), so a lower count can not buy a different result.

Needs the native library, so conftest.py does not collect this file on the JPype backend (a skip there would fail
scripts/check_test_skips.py); it runs in the native parity run.
"""

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import ArcadeDBError
from arcadedb_embedded._native import lib

_OPS = {0: "begin", 1: "commit", 2: "rollback", 3: "mark"}


class _Crossings:
    """Counts every ``lib.call`` made while it is installed; ``tx`` is the sequence of ``arcadedb_n_tx`` operations."""

    def __init__(self, monkeypatch):
        self.calls = []
        real = lib.call

        def counting(name, *args):
            self.calls.append(_OPS[args[1]] if name == "arcadedb_n_tx" else name)
            return real(name, *args)

        monkeypatch.setattr(lib, "call", counting)

    @property
    def tx(self):
        return [c for c in self.calls if c in _OPS.values()]

    def reset(self):
        self.calls.clear()


@pytest.fixture
def db(temp_db_path):
    database = arcadedb.create_database(temp_db_path)
    database.command("sql", "CREATE DOCUMENT TYPE R")
    with (
        database.transaction()
    ):  # the thread's transaction context exists from here on, as it does in a running application
        pass
    yield database
    database.drop()


@pytest.fixture
def crossings(db, monkeypatch):
    return _Crossings(monkeypatch)


def _count(db):
    return db.query("sql", "SELECT count(*) AS c FROM R").first().get("c")


def _need_retry():
    error = ArcadeDBError(
        "Failed to commit transaction: ConcurrentModificationException"
    )
    error.native = {"retry": "need_retry", "retry_ms": 0}
    return error


# -- crossing counts


def test_run_in_transaction_happy_path_is_three_crossings(db, crossings):
    # the mark before begin (what this call owns), begin (its reply is the commit-count witness), commit
    assert db.run_in_transaction(lambda: 42) == 42
    assert crossings.calls == ["mark", "begin", "commit"]


def test_with_transaction_is_three_crossings(db, crossings):
    with db.transaction():
        pass
    assert crossings.calls == ["mark", "begin", "commit"]


def test_with_transaction_that_raises_is_three_crossings(db, crossings):
    with pytest.raises(ValueError):
        with db.transaction():
            raise ValueError("boom")
    assert crossings.calls == ["mark", "begin", "rollback"]


def test_run_in_transaction_that_raises_reads_the_state_once(db, crossings):
    # mark, begin, then one state read for the unwind: the rollback replies carry the state, so no is-active read and no commit-count read
    with pytest.raises(ValueError):
        db.run_in_transaction(lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert crossings.calls == ["mark", "begin", "mark", "rollback"]
    assert not db.is_transaction_active()


def test_run_in_transaction_retry_costs_one_unwind_and_one_attempt(db, crossings):
    attempts = []

    def fn():
        attempts.append(1)
        if len(attempts) == 1:
            raise _need_retry()
        return "done"

    assert db.run_in_transaction(fn, backoff_s=0) == "done"
    assert len(attempts) == 2
    assert crossings.calls == [
        *["mark", "begin", "mark", "rollback"],  # the refused attempt, unwound
        *["mark", "begin", "commit"],  # the attempt that commits
    ]


# -- what the marks are for: the same results at the lower count


def test_a_nested_block_that_fails_leaves_the_callers_transaction_open(db):
    with db.transaction():
        db.command("sql", "INSERT INTO R SET k = 1")
        with pytest.raises(ValueError):
            db.run_in_transaction(
                lambda: (
                    db.command("sql", "INSERT INTO R SET k = 2"),
                    (_ for _ in ()).throw(ValueError("boom")),
                )
            )
        assert db.is_transaction_active()
    assert _count(db) == 1


def test_a_nested_block_that_succeeds_commits_with_the_caller(db):
    with db.transaction():
        db.run_in_transaction(lambda: db.command("sql", "INSERT INTO R SET k = 1"))
        db.command("sql", "INSERT INTO R SET k = 2")
    assert _count(db) == 2


def test_a_refused_attempt_is_rolled_back_before_the_retry(db):
    attempts = []

    def fn():
        attempts.append(1)
        db.command("sql", "INSERT INTO R SET k = 1")
        if len(attempts) == 1:
            raise _need_retry()

    db.run_in_transaction(fn, backoff_s=0)
    assert len(attempts) == 2
    assert _count(db) == 1
    assert not db.is_transaction_active()


def test_a_duplicated_key_is_retried_once(db):
    attempts = []

    def fn():
        attempts.append(1)
        error = ArcadeDBError("duplicated key")
        error.native = {"retry": "duplicated_key", "retry_ms": 0}
        raise error

    with pytest.raises(ArcadeDBError):
        db.run_in_transaction(fn, backoff_s=0)
    assert len(attempts) == 2
    assert not db.is_transaction_active()


def test_an_error_without_a_retry_kind_is_raised_after_one_attempt(db):
    attempts = []

    def fn():
        attempts.append(1)
        raise ArcadeDBError("not a conflict")

    with pytest.raises(ArcadeDBError):
        db.run_in_transaction(fn, backoff_s=0)
    assert attempts == [1]
    assert not db.is_transaction_active()


def test_begin_commit_rollback_return_nothing(db):
    assert db.begin() is None
    assert db.rollback() is None
    assert db.begin() is None
    assert db.commit() is None
