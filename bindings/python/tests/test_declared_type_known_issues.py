"""Engine findings about declared properties that reach Python users (known-issues.md).

Each finding has a test of its documented workaround, which must keep passing, and a
strict `xfail` for the engine behavior itself. The strict `xfail` is a tripwire, as
`test_restore_sql.py` used for #6096: when an engine fix reaches the wheel the test starts
passing, the suite fails, and the known-issues.md entry is removed.

Upstream: ArcadeData/arcadedb #9014 and #9027 (a value that cannot be converted is stored
as NULL, and '' as 0), #9017 (CREATE PROPERTY mandatory + notnull over records that lack
the property, then ORDER BY drops them), #9021 (an index on INTEGER answers for a fractional
bound as if it were rounded).
"""

import math

import arcadedb_embedded as arcadedb
import pytest


def _five_records_one_without_v(db, name):
    db.command("sql", f"CREATE DOCUMENT TYPE {name}")
    with db.transaction():
        for i in range(1, 5):
            db.command(
                "sql", f"INSERT INTO {name} SET id = {i}, v = {i}"
            )  # nosec B608 - fixed names
        db.command("sql", f"INSERT INTO {name} SET id = 5")  # nosec B608 - fixed names


def _ids_by_v(db, name):
    query = f"SELECT id FROM {name} ORDER BY v"  # nosec B608 - fixed names
    return sorted(r.get("id") for r in db.query("sql", query))


@pytest.mark.xfail(
    strict=True,
    reason="ArcadeData/arcadedb#9017: CREATE PROPERTY (mandatory, notnull) is accepted over records "
    "that lack the property, and an index-ordered ORDER BY then drops them",
)
def test_order_by_keeps_records_after_constraints_declared_over_missing_values(
    temp_db_path,
):
    with arcadedb.create_database(temp_db_path) as db:
        _five_records_one_without_v(db, "Declared")
        db.command(
            "sql", "CREATE PROPERTY Declared.v INTEGER (mandatory true, notnull true)"
        )
        db.command("sql", "CREATE INDEX ON Declared (v) NOTUNIQUE")
        assert _ids_by_v(db, "Declared") == [1, 2, 3, 4, 5]


def test_order_by_workarounds_for_constraints_over_missing_values(temp_db_path):
    """known-issues.md: give every record the property first, or relax the constraints."""
    with arcadedb.create_database(temp_db_path) as db:
        _five_records_one_without_v(db, "Repaired")
        with db.transaction():
            db.command("sql", "UPDATE Repaired SET v = 0 WHERE v IS NULL")
        db.command(
            "sql", "CREATE PROPERTY Repaired.v INTEGER (mandatory true, notnull true)"
        )
        db.command("sql", "CREATE INDEX ON Repaired (v) NOTUNIQUE")
        assert _ids_by_v(db, "Repaired") == [1, 2, 3, 4, 5]

        _five_records_one_without_v(db, "Relaxed")
        db.command(
            "sql", "CREATE PROPERTY Relaxed.v INTEGER (mandatory true, notnull true)"
        )
        db.command("sql", "CREATE INDEX ON Relaxed (v) NOTUNIQUE")
        db.command("sql", "ALTER PROPERTY Relaxed.v MANDATORY false")
        db.command("sql", "ALTER PROPERTY Relaxed.v NOTNULL false")
        assert _ids_by_v(db, "Relaxed") == [1, 2, 3, 4, 5]


def _indexed_and_plain_integers(db):
    for name in ("Indexed", "Plain"):
        db.command("sql", f"CREATE DOCUMENT TYPE {name}")
        db.command("sql", f"CREATE PROPERTY {name}.i INTEGER")
    db.command("sql", "CREATE INDEX ON Indexed (i) NOTUNIQUE")
    with db.transaction():
        for value in (11, 12, 13):
            db.command(
                "sql", f"INSERT INTO Indexed SET i = {value}"
            )  # nosec B608 - fixed names
            db.command(
                "sql", f"INSERT INTO Plain SET i = {value}"
            )  # nosec B608 - fixed names


def _matching(db, name, condition, bound):
    query = f"SELECT i FROM {name} WHERE {condition}"  # nosec B608 - fixed names
    return sorted(r.get("i") for r in db.query("sql", query, {"b": bound}))


@pytest.mark.xfail(
    strict=True,
    reason="ArcadeData/arcadedb#9021: an index on an INTEGER answers for a bound with a fraction as if "
    "it were rounded (i = 12.5 returns 12, i < 12.5 misses 12)",
)
@pytest.mark.parametrize("condition", ["i = :b", "i >= :b", "i < :b"])
def test_index_agrees_with_scan_for_a_fractional_bound(temp_db_path, condition):
    with arcadedb.create_database(temp_db_path) as db:
        _indexed_and_plain_integers(db)
        assert _matching(db, "Indexed", condition, 12.5) == _matching(
            db, "Plain", condition, 12.5
        )


def test_rounded_bound_workaround_for_a_fractional_bound(temp_db_path):
    """known-issues.md: ceil for >= and <, floor for > and <=, and no equality query for a
    bound that is not an integer."""
    bound = 12.5
    rounded = {
        "i >= :b": math.ceil(bound),
        "i > :b": math.floor(bound),
        "i <= :b": math.floor(bound),
        "i < :b": math.ceil(bound),
    }
    with arcadedb.create_database(temp_db_path) as db:
        _indexed_and_plain_integers(db)
        for condition, integer_bound in rounded.items():
            assert _matching(db, "Indexed", condition, integer_bound) == _matching(
                db, "Plain", condition, bound
            ), condition


def _stored_integer(db, value):
    """Write `value` to a declared INTEGER with Document.set and read it back (None when stored NULL)."""
    with db.transaction():
        doc = db.new_document("N").set("tag", "x").set("i", value)
        doc.save()
    row = db.query("sql", "SELECT i FROM N WHERE tag = 'x'").first()
    with db.transaction():
        db.command("sql", "DELETE FROM N")
    return row.get("i")


@pytest.mark.xfail(
    strict=True,
    reason="ArcadeData/arcadedb#9014: a bool, list, or dict written to a declared INTEGER is stored as NULL "
    "instead of being refused",
)
@pytest.mark.parametrize(
    "value", [True, [1, 2], {"a": 1}], ids=["bool", "list", "dict"]
)
def test_an_inconvertible_value_is_refused_not_stored_as_null(temp_db_path, value):
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE N")
        db.command("sql", "CREATE PROPERTY N.i INTEGER")
        with pytest.raises(
            Exception
        ):  # noqa: B017 - the engine's Java IllegalArgumentException
            _stored_integer(db, value)


@pytest.mark.xfail(
    strict=True,
    reason="ArcadeData/arcadedb#9027: an empty string bound to a declared INTEGER is stored as 0",
)
def test_an_empty_string_is_not_stored_as_zero(temp_db_path):
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE N")
        db.command("sql", "CREATE PROPERTY N.i INTEGER")
        try:
            with db.transaction():
                db.command("sql", "INSERT INTO N SET tag = 'x', i = :v", {"v": ""})
        except Exception:  # noqa: BLE001 - a refusal is what a fixed engine does
            return
        assert db.query("sql", "SELECT i FROM N WHERE tag = 'x'").first().get("i") != 0


def _to_int(value):
    """known-issues.md: convert in Python first; an empty string means no value."""
    return None if value == "" else int(value)


def test_convert_in_python_workaround_for_inconvertible_values(temp_db_path):
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE N")
        db.command("sql", "CREATE PROPERTY N.i INTEGER")
        for bad in ([1, 2], {"a": 1}):
            with pytest.raises(TypeError):
                _to_int(bad)
        assert _stored_integer(db, _to_int("7")) == 7
        assert _stored_integer(db, _to_int(True)) == 1
        assert _stored_integer(db, _to_int("")) is None
