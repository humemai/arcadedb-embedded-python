"""Python functions called from SQL and async callbacks, on the native backend (Java -> Python upcalls); not collected on JPype."""

import threading

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import ArcadeDBError


def test_a_python_function_in_a_select(temp_db):
    temp_db.register_function("py_double", lambda x: x * 2, 1, 1)
    row = temp_db.query("sql", "SELECT py_double(21) AS v").first()
    assert row.get("v") == 42


def test_a_python_function_reads_columns_and_returns_text(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE T")
    with temp_db.transaction():
        for i in range(3):
            temp_db.command("sql", "INSERT INTO T SET n = ?, s = ?", i, f"x{i}")
    temp_db.register_function("py_tag", lambda n, s: f"{s}:{n + 1}", 2, 2)
    rows = temp_db.query("sql", "SELECT py_tag(n, s) AS v FROM T ORDER BY n").to_list()
    assert [r["v"] for r in rows] == ["x0:1", "x1:2", "x2:3"]


def test_an_exception_in_the_function_fails_the_statement_with_its_text(temp_db):
    def boom(x):
        raise ValueError("no way")

    temp_db.register_function("py_boom", boom, 1, 1)
    with pytest.raises(ArcadeDBError, match="no way"):
        temp_db.query("sql", "SELECT py_boom(1) AS v").first()


def test_a_function_may_call_back_into_the_database(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE C")
    with temp_db.transaction():
        temp_db.command("sql", "INSERT INTO C SET k = 7")

    def count_c():
        return temp_db.query("sql", "SELECT count(*) AS c FROM C").first().get("c")

    temp_db.register_function("py_count_c", count_c, 0, 0)
    assert temp_db.query("sql", "SELECT py_count_c() AS v").first().get("v") == 1


def test_async_callbacks_run_on_a_writer_thread_and_see_the_record(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE A")
    seen, threads = [], set()

    def on_record(record):
        seen.append(record.get("n"))
        threads.add(threading.get_ident())

    executor = temp_db.async_executor()
    for n in range(20):
        doc = temp_db.new_document("A")
        doc.set("n", n)
        executor.create_record(doc, callback=on_record)
    executor.wait_completion()
    assert sorted(seen) == list(range(20))
    assert threading.get_ident() not in threads
