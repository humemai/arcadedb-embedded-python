"""
Python functions called from SQL and openCypher (``Database.register_function``) and
Python callbacks on record events (``Database.on``).
"""

import threading
from datetime import datetime
from decimal import Decimal

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded.callbacks import EVENTS


@pytest.fixture
def db(temp_db_path):
    with arcadedb.create_database(temp_db_path) as database:
        database.command("sql", "CREATE DOCUMENT TYPE Person")
        database.command("sql", "CREATE DOCUMENT TYPE Pet")
        database.command("sql", "CREATE VERTEX TYPE City")
        yield database


def _insert_people(db, names):
    with db.transaction():
        for name in names:
            db.command("sql", "INSERT INTO Person SET name = ?", name)


def _names(db, type_name="Person"):
    statement = f"SELECT name FROM {type_name} ORDER BY name"  # nosec B608 - literal
    rows = db.query("sql", statement).to_list()
    return [row["name"] for row in rows]


# --------------------------------------------------------------------------- functions


def test_function_in_select_and_where(db):
    _insert_people(db, ["Ann Lee", "Bob Ray"])
    db.register_function("slugify", lambda s: s.lower().replace(" ", "-"))

    rows = db.query("sql", "SELECT slugify(name) AS s FROM Person ORDER BY s").to_list()
    assert [row["s"] for row in rows] == ["ann-lee", "bob-ray"]

    rows = db.query(
        "sql", "SELECT name FROM Person WHERE slugify(name) = 'bob-ray'"
    ).to_list()
    assert [row["name"] for row in rows] == ["Bob Ray"]


def test_function_name_is_case_insensitive(db):
    db.register_function("shout", lambda s: s.upper() + "!")
    row = db.query("sql", "SELECT SHOUT('a') AS s").first()
    assert row.get("s") == "A!"


def test_function_receives_a_record_as_a_wrapper(db):
    _insert_people(db, ["Ann"])
    kinds = []

    def name_of(record):
        kinds.append(type(record).__name__)
        return record.get("name")

    db.register_function("name_of", name_of)
    row = db.query("sql", "SELECT name_of(@this) AS n FROM Person").first()
    assert row.get("n") == "Ann"
    assert kinds == ["Document"]


def test_function_receives_null_as_none_and_none_is_null(db):
    _insert_people(db, ["Ann", None])
    seen = []

    def describe(value):
        seen.append(value)
        return None if value is None else value.upper()

    db.register_function("describe", describe)
    rows = db.query("sql", "SELECT describe(name) AS d FROM Person").to_list()
    assert sorted(seen, key=lambda v: v or "") == [None, "Ann"]
    assert sorted(row["d"] or "" for row in rows) == ["", "ANN"]
    assert (
        db.query("sql", "SELECT FROM Person WHERE describe(name) IS NULL").to_list()[0][
            "name"
        ]
        is None
    )


def test_function_result_types(db):
    db.register_function("an_int", lambda: 7)
    db.register_function("a_float", lambda: 1.5)
    db.register_function("a_bool", lambda: True)
    db.register_function("a_text", lambda: "x")
    db.register_function("a_decimal", lambda: Decimal("1.25"))
    db.register_function("a_list", lambda: [1, 2, 3])
    db.register_function("a_dict", lambda: {"k": [1, "v"]})
    db.register_function("a_time", lambda: datetime(2026, 1, 2, 3, 4, 5))
    row = db.query(
        "sql",
        "SELECT an_int() AS i, a_float() AS f, a_bool() AS b, a_text() AS t, "
        "a_decimal() AS d, a_list() AS l, a_dict() AS m, a_time() AS ts",
    ).first()
    assert row.get("i") == 7
    assert row.get("f") == 1.5
    assert row.get("b") is True
    assert row.get("t") == "x"
    assert row.get("d") == Decimal("1.25")
    assert row.get("l") == [1, 2, 3]
    assert row.get("m") == {"k": [1, "v"]}
    assert row.get("ts") == datetime(2026, 1, 2, 3, 4, 5)


def test_function_arguments_arrive_as_python_values(db):
    got = []
    db.register_function("capture", lambda *args: got.append(args) or 0)
    db.query(
        "sql", "SELECT capture(1, 2.5, 'a', true, [1, 2], {'k': 'v'}, null) AS c"
    ).to_list()
    assert got == [(1, 2.5, "a", True, [1, 2], {"k": "v"}, None)]


def test_function_exception_becomes_query_error(db):
    _insert_people(db, ["Ann"])

    def explode(value):
        raise ValueError(f"cannot handle {value}")

    db.register_function("explode", explode)
    with pytest.raises(arcadedb.ArcadeDBError) as error:
        db.query("sql", "SELECT explode(name) FROM Person").to_list()
    assert "explode" in str(error.value)
    assert "ValueError: cannot handle Ann" in str(error.value)

    # the database, and the function table, work as before
    assert db.query("sql", "SELECT 1 + 1 AS two").first().get("two") == 2


def test_function_base_exception_does_not_reach_the_jvm(db):
    def interrupt():
        raise KeyboardInterrupt("stop")

    db.register_function("interrupt", interrupt)
    with pytest.raises(arcadedb.ArcadeDBError, match="KeyboardInterrupt"):
        db.query("sql", "SELECT interrupt() AS x").to_list()


def test_function_argument_count_is_inferred(db):
    def two_or_three(a, b, c=0):
        return a + b + c

    db.register_function("sum_args", two_or_three)
    assert db.query("sql", "SELECT sum_args(1, 2) AS s").first().get("s") == 3
    assert db.query("sql", "SELECT sum_args(1, 2, 3) AS s").first().get("s") == 6
    for bad in ("SELECT sum_args(1)", "SELECT sum_args(1, 2, 3, 4)"):
        with pytest.raises(arcadedb.ArcadeDBError, match="sum_args"):
            db.query("sql", bad).to_list()

    db.register_function("count_args", lambda *args: len(args))
    assert (
        db.query("sql", "SELECT count_args(1, 2, 3, 4, 5) AS n").first().get("n") == 5
    )

    db.register_function("exactly_one", lambda x, y=0: x, max_args=1)
    with pytest.raises(arcadedb.ArcadeDBError, match="exactly_one"):
        db.query("sql", "SELECT exactly_one(1, 2)").to_list()


def test_function_registration_errors(db):
    with pytest.raises(ValueError):
        db.register_function("not a name", lambda: 1)
    with pytest.raises(ValueError):
        db.register_function("1abc", lambda: 1)
    with pytest.raises(TypeError):
        db.register_function("nope", "not callable")
    with pytest.raises(ValueError):
        db.register_function("bad_counts", lambda *a: 1, min_args=3, max_args=1)
    with pytest.raises(arcadedb.ArcadeDBError, match="keyword-only"):
        db.register_function("kw_only", lambda *, key: key)
    for engine_name in ("abs", "count", "toUpper", "id"):
        with pytest.raises(arcadedb.ArcadeDBError, match="already a function"):
            db.register_function(engine_name, lambda *a: 1)
    # the engine's own functions still work after the refusals
    assert db.query("sql", "SELECT abs(-3) AS a").first().get("a") == 3


def test_function_replace(db):
    db.register_function("which", lambda: "first")
    with pytest.raises(arcadedb.ArcadeDBError, match="replace=True"):
        db.register_function("which", lambda: "second")
    assert db.query("sql", "SELECT which() AS w").first().get("w") == "first"

    db.register_function("which", lambda: "second", replace=True)
    assert db.query("sql", "SELECT which() AS w").first().get("w") == "second"


def test_unregister_function(db):
    db.register_function("temp_fn", lambda: 1)
    statement = "SELECT temp_fn() AS x"
    assert db.query("sql", statement).first().get("x") == 1

    db.unregister_function("temp_fn")
    # the same statement text, which may have a cached plan, fails now
    with pytest.raises(arcadedb.ArcadeDBError, match="temp_fn"):
        db.query("sql", statement).to_list()
    with pytest.raises(arcadedb.ArcadeDBError, match="No Python function"):
        db.unregister_function("temp_fn")

    # the name can be registered again
    db.register_function("temp_fn", lambda: 2)
    assert db.query("sql", statement).first().get("x") == 2


def test_close_unregisters_the_functions_of_a_database(temp_db_path):
    with arcadedb.create_database(temp_db_path) as first:
        first.register_function("scoped_fn", lambda: 1)
        assert first.query("sql", "SELECT scoped_fn() AS x").first().get("x") == 1
    with arcadedb.open_database(temp_db_path) as second:
        with pytest.raises(arcadedb.ArcadeDBError, match="scoped_fn"):
            second.query("sql", "SELECT scoped_fn() AS x").to_list()
        # and the name is free again
        second.register_function("scoped_fn", lambda: 2)
        assert second.query("sql", "SELECT scoped_fn() AS x").first().get("x") == 2


def test_function_in_opencypher_needs_a_namespaced_name(db):
    with db.transaction():
        db.command("sql", "CREATE VERTEX City SET name = 'New York'")
    db.register_function("py.slugify", lambda s: s.lower().replace(" ", "-"))

    rows = db.query(
        "opencypher", "MATCH (c:City) RETURN py.slugify(c.name) AS s"
    ).to_list()
    assert rows == [{"s": "new-york"}]
    # the same function from SQL
    row = db.query("sql", "SELECT py.slugify(name) AS s FROM City").first()
    assert row.get("s") == "new-york"

    # a bare name is rejected by the openCypher validator before it reaches the registry
    db.register_function("bare_slugify", lambda s: s)
    with pytest.raises(arcadedb.ArcadeDBError, match="Unknown function"):
        db.query("opencypher", "MATCH (c:City) RETURN bare_slugify(c.name)").to_list()


def test_function_failure_in_opencypher_is_a_query_error(db):
    with db.transaction():
        db.command("sql", "CREATE VERTEX City SET name = 'Oslo'")

    def explode(_):
        raise RuntimeError("cypher boom")

    db.register_function("py.explode", explode)
    with pytest.raises(arcadedb.ArcadeDBError, match="RuntimeError: cypher boom"):
        db.query("opencypher", "MATCH (c:City) RETURN py.explode(c.name)").to_list()


def test_function_called_from_an_engine_thread(db):
    thread_names = []

    def mark(value):
        thread_names.append(threading.current_thread().name)
        return value

    db.register_function("mark", mark)
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'x'")
    executor = db.async_executor()
    executor.command("sql", "INSERT INTO Pet SET name = mark('from async')")
    executor.wait_completion()
    assert _names(db, "Pet") == ["from async"]
    assert thread_names and all(isinstance(name, str) for name in thread_names)


def test_function_called_concurrently_from_python_threads(db):
    _insert_people(db, [f"n{i}" for i in range(50)])
    db.register_function("twice", lambda s: s + s)
    results, failures = [], []

    def run():
        try:
            rows = db.query("sql", "SELECT twice(name) AS t FROM Person").to_list()
            results.append(len(rows))
        except Exception as e:  # pragma: no cover - reported by the assertion
            failures.append(e)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not failures
    assert results == [50, 50, 50, 50]


# ------------------------------------------------------------------------------ events


def test_each_event_fires_once_per_change_with_the_record(db):
    log = []
    for event in EVENTS:
        db.on(
            event,
            lambda record, event=event: log.append(
                (event, record.get_type_name(), record.get("name"))
            ),
            "Person",
        )

    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Ann'")
    assert log == [
        ("before_create", "Person", "Ann"),
        ("after_create", "Person", "Ann"),
    ]

    del log[:]
    with db.transaction():
        db.command("sql", "UPDATE Person SET name = 'Anna' WHERE name = 'Ann'")
    assert [entry[0] for entry in log] == ["before_update", "after_update"]
    assert log[0][2] == "Anna"

    del log[:]
    with db.transaction():
        db.command("sql", "DELETE FROM Person WHERE name = 'Anna'")
    assert log == [
        ("before_delete", "Person", "Anna"),
        ("after_delete", "Person", "Anna"),
    ]


def test_events_fire_for_the_record_api_too(db):
    created, updated, deleted = [], [], []
    db.on("after_create", created.append, "Person")
    db.on("after_update", updated.append, "Person")
    db.on("after_delete", deleted.append, "Person")

    with db.transaction():
        document = db.new_document("Person")
        document.set("name", "Zed")
        document.save()
    assert [r.get("name") for r in created] == ["Zed"]
    assert isinstance(created[0], arcadedb.Document)
    rid = created[0].get_rid()

    with db.transaction():
        record = db.lookup_by_rid(rid)
        record.modify().set("name", "Zoe").save()
    assert [r.get("name") for r in updated] == ["Zoe"]

    with db.transaction():
        db.lookup_by_rid(rid).delete()
    assert [r.get_rid() for r in deleted] == [rid]


def test_events_fire_for_opencypher_writes(db):
    created = []
    db.on("after_create", lambda r: created.append(r.get("name")), "City")
    with db.transaction():
        db.command("opencypher", "CREATE (:City {name: 'Oslo'})")
    assert created == ["Oslo"]


def test_event_passes_vertex_wrappers(db):
    seen = []
    db.on("after_create", seen.append, "City")
    with db.transaction():
        vertex = db.new_vertex("City")
        vertex.set("name", "Oslo")
        vertex.save()
    assert len(seen) == 1 and isinstance(seen[0], arcadedb.Vertex)


def test_type_filter_limits_the_events(db):
    on_person, on_everything = [], []
    db.on("after_create", lambda r: on_person.append(r.get_type_name()), "Person")
    db.on("after_create", lambda r: on_everything.append(r.get_type_name()))

    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'a'")
        db.command("sql", "INSERT INTO Pet SET name = 'b'")
        db.command("sql", "CREATE VERTEX City SET name = 'c'")
    assert on_person == ["Person"]
    assert sorted(on_everything) == ["City", "Person", "Pet"]


def test_type_filter_survives_schema_changes(db):
    seen = []
    db.on("after_create", lambda r: seen.append(r.get("name")), "Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")
    db.command("sql", "CREATE DOCUMENT TYPE Unrelated")
    _insert_people(db, ["after schema change"])
    assert seen == ["after schema change"]


def test_before_create_veto(db):
    db.on("before_create", lambda r: r.get("name") != "blocked", "Person")
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'ok'")
        db.command("sql", "INSERT INTO Person SET name = 'blocked'")
        document = db.new_document("Person")
        document.set("name", "blocked")
        document.save()
    assert _names(db) == ["ok"]


def test_before_update_veto(db):
    _insert_people(db, ["keep", "change"])
    db.on("before_update", lambda r: r.get("name") != "frozen", "Person")
    with db.transaction():
        db.command("sql", "UPDATE Person SET name = 'frozen' WHERE name = 'keep'")
        db.command("sql", "UPDATE Person SET name = 'changed' WHERE name = 'change'")
    assert _names(db) == ["changed", "keep"]


def test_before_delete_veto(db):
    _insert_people(db, ["protected", "removable"])
    db.on("before_delete", lambda r: r.get("name") != "protected", "Person")
    with db.transaction():
        db.command("sql", "DELETE FROM Person")
    assert _names(db) == ["protected"]


def test_none_and_true_allow_and_after_result_is_ignored(db):
    db.on("before_create", lambda r: None, "Person")
    db.on("before_create", lambda r: True, "Person")
    db.on("after_create", lambda r: False, "Person")
    _insert_people(db, ["a"])
    assert _names(db) == ["a"]


def test_remove_stops_the_callback(db):
    seen = []
    handle = db.on("after_create", lambda r: seen.append(r.get("name")), "Person")
    assert handle.active and handle.event == "after_create"
    assert handle.type_name == "Person"
    _insert_people(db, ["one"])

    handle.remove()
    assert not handle.active
    handle.remove()  # a second call does nothing
    _insert_people(db, ["two"])
    assert seen == ["one"]
    assert "removed" in repr(handle)


def test_remove_database_wide_and_context_manager(db):
    seen = []
    with db.on("after_create", lambda r: seen.append(r.get("name"))) as handle:
        _insert_people(db, ["in"])
    assert not handle.active
    _insert_people(db, ["out"])
    assert seen == ["in"]


def test_two_callbacks_on_one_event_both_fire(db):
    first, second = [], []
    db.on("after_create", first.append, "Person")
    db.on("after_create", second.append, "Person")
    _insert_people(db, ["x"])
    assert len(first) == 1 and len(second) == 1


def test_before_callback_exception_fails_the_operation(db):
    def explode(record):
        raise RuntimeError("no creating today")

    db.on("before_create", explode, "Person")
    with pytest.raises(arcadedb.ArcadeDBError) as error:
        _insert_people(db, ["x"])
    assert "before_create" in str(error.value)
    assert "RuntimeError: no creating today" in str(error.value)
    assert db.count_type("Person") == 0


def test_after_callback_exception_rolls_the_transaction_back(db):
    def explode(record):
        raise RuntimeError("after boom")

    handle = db.on("after_create", explode, "Person")
    with pytest.raises(arcadedb.ArcadeDBError, match="after_create.*after boom"):
        _insert_people(db, ["x", "y"])
    assert db.count_type("Person") == 0

    handle.remove()
    _insert_people(db, ["z"])
    assert _names(db) == ["z"]


def test_event_registration_errors(db):
    with pytest.raises(ValueError, match="Invalid event"):
        db.on("on_create", lambda r: None)
    with pytest.raises(TypeError):
        db.on("after_create", "not callable")
    with pytest.raises(arcadedb.ArcadeDBError, match="does not exist"):
        db.on("after_create", lambda r: None, "NoSuchType")


def test_calls_after_close_are_refused(temp_db_path):
    database = arcadedb.create_database(temp_db_path)
    database.close()
    with pytest.raises(arcadedb.ArcadeDBError, match="closed"):
        database.register_function("late", lambda: 1)
    with pytest.raises(arcadedb.ArcadeDBError, match="closed"):
        database.on("after_create", lambda r: None)
