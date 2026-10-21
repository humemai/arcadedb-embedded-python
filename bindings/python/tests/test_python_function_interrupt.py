"""A real Ctrl-C during a statement that calls a Python function always arrives as KeyboardInterrupt.

The signal can land in the function, in the engine between two calls, or on entering the callback
(where the exception leaves it as JPype's PyExceptionProxy and the engine wraps it). Each of these
used to come out differently (KeyboardInterrupt, or ArcadeDBError). Not run on Windows, where a
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
