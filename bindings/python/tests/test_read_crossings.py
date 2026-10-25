"""Crossings of the JVM read path (one JPype call is a few microseconds of dispatch).

Each read the bindings make used to cross into the JVM several times: ``Document.get_raw`` asked
``has()`` and then ``get()``, ``ResultSet.one()`` and ``count()`` crossed per row, ``lookup_by_key``
built two Java arrays per call, and the bookkeeping around ``with db.transaction()`` crossed twice
just to take the transaction-stack mark. Every test here pins two things: the number of calls into
the JVM (counted on a proxy of the Java object or bridge class, the technique of
``test_percall_calls.py``) and that the answer is the one the plain path gives (same value, same
errors, same result-set state), so a count cannot be bought with a change of behaviour.
"""

import datetime

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import core, results
from arcadedb_embedded.exceptions import ArcadeDBError


class Counting:
    """Counts the method calls made on a Java object or a Java class.

    Arguments that are themselves a ``Counting`` are unwrapped before the call, so the proxy of the
    database can be handed to a bridge class as it is. Return values are the real objects.
    """

    def __init__(self, target, log, label):
        self._target = target
        self._log = log
        self._label = label

    def __getattr__(self, name):
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        def call(*args, **kwargs):
            self._log.append(f"{self._label}.{name}")
            args = [a._target if isinstance(a, Counting) else a for a in args]
            return attr(*args, **kwargs)

        return call


@pytest.fixture
def db(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE T")
    temp_db.command("sql", "CREATE PROPERTY T.k INTEGER")
    temp_db.command("sql", "CREATE INDEX ON T (k) UNIQUE")
    with temp_db.transaction():
        for key in range(5):
            temp_db.command("sql", "INSERT INTO T SET k = ?, v = ?", key, key * 10)
    return temp_db


@pytest.fixture
def log(db, monkeypatch):
    """The list every counted call is appended to; the database and the bridge classes are counted."""
    calls = []
    real = {name: results._bridge_class(name) for name in ("RowAccess", "DbCalls")}
    monkeypatch.setattr(db, "_java_db", Counting(db._java_db, calls, "db"))
    for name, cls in real.items():
        monkeypatch.setitem(results._BRIDGE_CLASSES, name, Counting(cls, calls, name))
    monkeypatch.setattr(core, "_DB_CALLS", Counting(real["DbCalls"], calls, "DbCalls"))
    return calls


def _no_bridge(monkeypatch, *names):
    """Send ``names`` down the plain per-row path (the bridge class reported missing)."""
    for name in names:
        monkeypatch.setitem(results._BRIDGE_CLASSES, name, None)
    monkeypatch.setattr(core, "_DB_CALLS", False)


# ---------------------------------------------------------------- Document.get_raw


def test_get_raw_is_one_crossing_and_one_buffer_scan(db):
    doc = db.query("sql", "SELECT FROM T WHERE k = 3").first().get_element()
    calls = []
    doc._java_document = Counting(doc._java_document, calls, "doc")
    assert doc.get_raw("v") == 30
    assert calls == ["doc.get"]


def test_get_raw_absent_property_is_none_in_one_crossing(db):
    doc = db.query("sql", "SELECT FROM T WHERE k = 3").first().get_element()
    calls = []
    doc._java_document = Counting(doc._java_document, calls, "doc")
    assert doc.get_raw("missing") is None
    assert doc.get("missing") is None
    assert calls == ["doc.get", "doc.get"]


def test_get_raw_null_valued_and_absent_properties_both_read_none(db):
    """A property set to null and one never set read the same through get(); has() still tells them apart."""
    with db.transaction():
        doc = db.new_document("T")
        doc.set("k", 99)
        doc.set("nothing", None)
        doc.save()
        rid = doc.get_identity()
    with db.transaction():
        mutable = db.new_document("T")
        mutable.set("k", 100)
        mutable.set("nothing", None)
        assert mutable.get_raw("nothing") is None
        assert mutable.get_raw("never") is None
        assert mutable.has_property("nothing") is True
        assert mutable.has_property("never") is False
        mutable.save()
    stored = db.lookup_by_rid(str(rid))
    assert stored.get_raw("k") == 99
    assert stored.get_raw("never") is None


def test_get_raw_on_vertex_and_edge(db):
    db.command("sql", "CREATE VERTEX TYPE V")
    db.command("sql", "CREATE EDGE TYPE E")
    with db.transaction():
        a = db.command("sql", "CREATE VERTEX V SET name = 'a'").first().get_vertex()
        b = db.command("sql", "CREATE VERTEX V SET name = 'b'").first().get_vertex()
        edge = a.new_edge("E", b, w=7)
    vertex = db.query("sql", "SELECT FROM V WHERE name = 'a'").first().get_vertex()
    assert vertex.get_raw("name") == "a"
    assert vertex.get_raw("nope") is None
    assert edge.get_raw("w") == 7
    assert edge.get_raw("nope") is None


# ---------------------------------------------------------------- ResultSet.one() / count()


def _state(rs):
    return rs._closed, rs._exhausted


def test_one_is_one_crossing(db, log):
    rs = db.query("sql", "SELECT FROM T WHERE k = 3")
    del log[:]
    row = rs.one()
    assert len(log) == 1 and log[0].startswith("RowAccess."), log
    assert row.get("v") == 30
    assert _state(rs) == (True, True)


@pytest.mark.parametrize(
    "statement, message, state",
    [
        ("SELECT FROM T WHERE k = 99", "Query returned no results", (True, True)),
        ("SELECT FROM T", "Query returned multiple results", (True, False)),
    ],
)
def test_one_errors_and_state_match_the_plain_path(
    db, monkeypatch, statement, message, state
):
    seen = []
    for plain in (False, True):
        if plain:
            _no_bridge(monkeypatch, "RowAccess")
        rs = db.query("sql", statement)
        with pytest.raises(ValueError, match=message):
            rs.one()
        seen.append(_state(rs))
        with pytest.raises(ArcadeDBError if state == (True, False) else ValueError):
            rs.one()
    assert seen[0] == seen[1] == state


def test_one_on_a_closed_database_raises_like_the_plain_path(db, monkeypatch):
    rs = db.query("sql", "SELECT FROM T WHERE k = 3")
    db.close()
    with pytest.raises(ArcadeDBError, match="closed"):
        rs.one()


def test_count_is_one_crossing(db, log):
    rs = db.query("sql", "SELECT FROM T")
    del log[:]
    assert rs.count() == 5
    assert len(log) == 1 and log[0].startswith("RowAccess."), log
    assert _state(rs) == (True, True)
    assert rs.count() == 0  # exhausted: nothing remains, as before


def test_count_counts_only_the_remaining_rows(db):
    rs = db.query("sql", "SELECT FROM T")
    next(rs)
    next(rs)
    assert rs.count() == 3
    assert _state(rs) == (True, True)


def test_count_of_an_empty_result_and_after_close(db):
    assert db.query("sql", "SELECT FROM T WHERE k = 99").count() == 0
    rs = db.query("sql", "SELECT FROM T")
    rs.close()
    with pytest.raises(ArcadeDBError, match="closed before all its rows were read"):
        rs.count()


def test_count_matches_the_plain_path(db, monkeypatch):
    fast = db.query("sql", "SELECT FROM T WHERE k >= 2").count()
    _no_bridge(monkeypatch, "RowAccess")
    assert db.query("sql", "SELECT FROM T WHERE k >= 2").count() == fast == 3


# ---------------------------------------------------------------- lookup_by_key


def _plain_lookup_rid(db, type_name, keys, values):
    cursor = db.get_java_database().lookupByKey(
        type_name, core._string_array(keys), core._object_array(values)
    )
    return str(cursor.next().getIdentity()) if cursor.hasNext() else None


def test_lookup_by_key_is_one_crossing_without_java_arrays(db, log, monkeypatch):
    def boom(values):
        raise AssertionError("lookup_by_key built a Java array")

    monkeypatch.setattr(core, "_string_array", boom)
    monkeypatch.setattr(core, "_object_array", boom)
    del log[:]
    doc = db.lookup_by_key("T", ["k"], [3])
    assert log == ["DbCalls.lookupFirstKey"]
    assert doc.get("v") == 30
    del log[:]
    assert db.lookup_by_key("T", ["k"], [99]) is None
    assert log == ["DbCalls.lookupFirstKey"]


def test_lookup_by_key_composite_and_typed_keys_match_the_plain_path(db):
    db.command("sql", "CREATE DOCUMENT TYPE C")
    db.command("sql", "CREATE PROPERTY C.a STRING")
    db.command("sql", "CREATE PROPERTY C.b LONG")
    db.command("sql", "CREATE PROPERTY C.ts DATETIME")
    db.command("sql", "CREATE PROPERTY C.f DOUBLE")
    db.command("sql", "CREATE INDEX ON C (a, b) UNIQUE")
    db.command("sql", "CREATE INDEX ON C (ts) UNIQUE")
    db.command("sql", "CREATE INDEX ON C (f) UNIQUE")
    stamp = datetime.datetime(2026, 10, 25, 12, 30, 45)
    with db.transaction():
        db.command(
            "sql", "INSERT INTO C SET a = ?, b = ?, ts = ?, f = ?", "x", 7, stamp, 2.5
        )
        db.command(
            "sql",
            "INSERT INTO C SET a = ?, b = ?, ts = ?, f = ?",
            "y",
            8,
            datetime.datetime(2026, 1, 2, 3, 4, 5),
            3.5,
        )
    cases = [
        (["a", "b"], ["x", 7]),
        (["a", "b"], ["y", 8]),
        (["a", "b"], ["x", 8]),
        (["ts"], [stamp]),
        (["f"], [2.5]),
        (["f"], [9.5]),
    ]
    for keys, values in cases:
        found = db.lookup_by_key("C", keys, values)
        converted = [core.convert_python_to_java(v) for v in values]
        expected = _plain_lookup_rid(db, "C", keys, converted)
        assert (None if found is None else str(found.get_identity())) == expected, (
            keys,
            values,
        )
    assert db.lookup_by_key("C", ["a", "b"], ["x", 7]).get("f") == 2.5


def test_lookup_by_key_composite_is_one_crossing(db, log):
    db.command("sql", "CREATE DOCUMENT TYPE C2")
    db.command("sql", "CREATE PROPERTY C2.a STRING")
    db.command("sql", "CREATE PROPERTY C2.b LONG")
    db.command("sql", "CREATE INDEX ON C2 (a, b) UNIQUE")
    with db.transaction():
        db.command("sql", "INSERT INTO C2 SET a = 'x', b = 7")
    del log[:]
    assert db.lookup_by_key("C2", ["a", "b"], ["x", 7]) is not None
    assert log == ["DbCalls.lookupFirstKeys"]


def test_lookup_by_key_errors_stay_arcadedb_errors(db):
    with pytest.raises(ArcadeDBError):
        db.lookup_by_key("NoSuchType", ["k"], [1])
    with pytest.raises(ArcadeDBError):
        db.lookup_by_key("T", ["k", "v"], [1])  # more keys than values
    with pytest.raises(ArcadeDBError):
        db.lookup_by_key("T", [3], [1])  # a key name that is not a string


# ---------------------------------------------------------------- transaction bookkeeping


def test_transaction_stack_mark_is_one_crossing(db, log):
    expected = (False, db.get_java_database().getNestedTransactions())
    del log[:]
    assert db._transaction_stack_mark() == expected
    assert log == ["DbCalls.stackMark"]


def test_transaction_stack_mark_matches_the_engine_stack(db):
    java = db.get_java_database()
    base = java.getNestedTransactions()
    assert db._transaction_stack_mark() == (False, base)
    db.begin()
    inner = db._transaction_stack_mark()
    assert inner == (True, java.getNestedTransactions())
    db.begin()  # a nested level
    nested = db._transaction_stack_mark()
    assert nested == (True, java.getNestedTransactions())
    assert nested[1] == inner[1] + 1
    db.rollback()
    db.rollback()
    assert db._transaction_stack_mark() == (False, base)


def test_transaction_stack_mark_on_a_closed_database(db):
    db.close()
    with pytest.raises(ArcadeDBError, match="closed"):
        db._transaction_stack_mark()


def test_with_transaction_is_three_crossings(db, log):
    del log[:]
    with db.transaction():
        pass
    assert log == ["DbCalls.stackMark", "db.begin", "db.commit"], log


def test_run_in_transaction_crossings(db, log):
    del log[:]
    assert db.run_in_transaction(lambda: 41 + 1) == 42
    # The mark (1), begin, the commit witness (getTransactionIfExists, then getCommitCount on the
    # transaction object, which is not counted here) and commit: five crossings, six before.
    assert log == [
        "DbCalls.stackMark",
        "db.begin",
        "db.getTransactionIfExists",
        "db.commit",
    ], log
