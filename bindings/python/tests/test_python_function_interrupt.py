"""A real Ctrl-C during a statement that calls a Python function always arrives as KeyboardInterrupt.

The signal can land in the function, in the engine between two calls, or on entering the callback
(where the exception leaves it as JPype's PyExceptionProxy and the engine wraps it). Each of these
used to come out differently (KeyboardInterrupt, or ArcadeDBError). When the signal also lands while
JPype converts the engine's exception, JPype fails with ``RuntimeError: Fatal error occurred``
(jpype-project/jpype#1496), which was an ArcadeDBError in about 5% of the runs; it is a
KeyboardInterrupt now. Not run on Windows, where a
signal cannot be sent to the own process like this (see test_sigint.py).
"""

import os
import signal
import threading
import time

import arcadedb_embedded as arcadedb
import numpy as np
import pytest


@pytest.fixture
def db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as database:
        database.command("sql", "CREATE DOCUMENT TYPE T")
        database.insert_columns("T", {"n": np.arange(300_000, dtype=np.int64)})
        database.register_function("plus_one", lambda x: x + 1)
        yield database


def test_sigint_during_a_query_that_calls_python_is_a_keyboard_interrupt(db):
    interrupted = 0
    for delay in (0.05, 0.09, 0.13, 0.17, 0.21, 0.25, 0.29, 0.33):
        timer = threading.Timer(delay, os.kill, (os.getpid(), signal.SIGINT))
        timer.start()
        try:
            db.query("sql", "SELECT sum(plus_one(n)) AS s FROM T").first()
            outcome = "completed"
        except KeyboardInterrupt:
            outcome = "interrupted"
            interrupted += 1
        finally:
            timer.cancel()
            timer.join()
        if outcome == "completed":
            try:  # a signal sent just after the end is delivered here, still a KeyboardInterrupt
                time.sleep(0.05)
            except KeyboardInterrupt:
                interrupted += 1
        # the database works as before
        assert db.count_type("T") == 300_000
    assert interrupted >= 1


class _JpypeLostTheRace:
    """Stands in for the Java database when JPype loses its race with Ctrl-C (jpype#1496).

    The engine handles a KeyboardInterrupt that left the Python function as a Java exception;
    JPype's conversion of it to Python fails with ``InterruptedException: sleep interrupted``
    and the call raises this plain RuntimeError, with nothing left for the bindings to read.
    """

    def query(self, *args):
        raise RuntimeError("Fatal error occurred")

    command = query


@pytest.mark.parametrize("method", ["query", "command"])
def test_jpypes_fatal_error_during_a_statement_is_a_keyboard_interrupt(
    db, method, monkeypatch
):
    monkeypatch.setattr(db, "_java_db", _JpypeLostTheRace())
    with pytest.raises(KeyboardInterrupt) as raised:
        getattr(db, method)("sql", "SELECT sum(plus_one(n)) AS s FROM T")
    # the text of JPype's error stays reachable
    assert "Fatal error occurred" in str(raised.value.__cause__)


def test_a_statement_that_fails_otherwise_is_still_an_arcadedb_error(db):
    with pytest.raises(arcadedb.ArcadeDBError) as raised:
        db.query("sql", "SELECT FROM NoSuchType")
    assert not isinstance(raised.value, KeyboardInterrupt)
