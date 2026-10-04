"""Engine finding about positional parameters in UPDATE and DELETE (known-issues.md).

ArcadeData/arcadedb#9245 (open): since #9218, in 26.10.1 snapshots, the read side of an
UPDATE or DELETE is planned as a ``SELECT FROM <type> WHERE <where>`` and that plan is
shared through the execution plan cache under the SELECT's text, where every positional
``?`` prints the same. ``UPDATE A SET brand = ? WHERE sku = ?`` run after
``SELECT FROM A WHERE sku = ?`` then reads its WHERE from the SET value: it changes the
record whose sku is that value, not the one asked for, and reports ``count=1``. Named
parameters are not affected. 26.9.1 and snapshots before #9218 are not affected.

The tripwire is a strict ``xfail`` only on an engine that has #9218, which it recognizes by
the class #9218 added (``DmlSourcePlanKey``), not by running the bug: keyed on the cause,
a fix that keeps the class turns it into a strict XPASS, which fails the suite and is the
cue to remove the known-issues entry. On an engine without #9218 (26.9.1, older snapshots)
it is a plain test that passes. The CI wheel is built from the moving 26.10.1-SNAPSHOT
image, which has #9218, so CI sees the xfail.
"""

import arcadedb_embedded as arcadedb
import jpype
import pytest

REASON = (
    "ArcadeData/arcadedb#9245: since #9218 an UPDATE with positional parameters reuses "
    "the cached plan of SELECT FROM A WHERE sku = ? and reads its WHERE from the SET value"
)


def _engine_has_9218():
    """True when the engine plans the read side of UPDATE/DELETE through the plan cache."""
    try:
        jpype.JClass("com.arcadedb.query.sql.executor.DmlSourcePlanKey")
    except Exception:  # JPype raises TypeError for a class that is not there
        return False
    return True


def _products(db, name):
    db.command("sql", f"CREATE DOCUMENT TYPE {name}")
    db.command("sql", f"CREATE PROPERTY {name}.sku STRING")
    db.command("sql", f"CREATE PROPERTY {name}.brand STRING")
    db.command("sql", f"CREATE INDEX ON {name} (sku) UNIQUE")
    with db.transaction():
        for sku, brand in (("S1", "b1"), ("S2", "b2"), ("NEW", "b3")):
            db.command(
                "sql", f"INSERT INTO {name} SET sku = ?, brand = ?", sku, brand
            )  # nosec B608 - fixed names


def _brands(db, name):
    query = f"SELECT sku, brand FROM {name}"  # nosec B608 - fixed names
    return {r["sku"]: r["brand"] for r in db.query("sql", query).to_list()}


BEFORE = {"S1": "b1", "S2": "b2", "NEW": "b3"}
# The statement targets S2. NEW is the value it sets, so a WHERE that reads the SET
# parameter finds the record whose sku is NEW.
AFTER = {"S1": "b1", "S2": "NEW", "NEW": "b3"}


def test_positional_update_after_a_select_with_the_same_where(temp_db_path, request):
    """#9245: the UPDATE changes S2, and the record whose sku is the SET value keeps its
    brand."""
    with arcadedb.create_database(temp_db_path) as db:
        if _engine_has_9218():
            request.applymarker(
                pytest.mark.xfail(strict=True, raises=AssertionError, reason=REASON)
            )
        _products(db, "A")
        if _brands(db, "A") != BEFORE:
            pytest.fail(f"the records before the UPDATE are {_brands(db, 'A')}")
        assert db.query("sql", "SELECT FROM A WHERE sku = ?", "S1").to_list()

        with db.transaction():
            count = db.command(
                "sql", "UPDATE A SET brand = ? WHERE sku = ?", "NEW", "S2"
            ).to_list()

        assert (count, _brands(db, "A")) == ([{"count": 1}], AFTER)


def test_named_parameters_are_the_workaround(temp_db_path):
    """known-issues.md: the same SELECT and UPDATE with named parameters change S2."""
    with arcadedb.create_database(temp_db_path) as db:
        _products(db, "F")
        assert db.query(
            "sql", "SELECT FROM F WHERE sku = :sku", {"sku": "S1"}
        ).to_list()

        with db.transaction():
            count = db.command(
                "sql",
                "UPDATE F SET brand = :brand WHERE sku = :sku",
                {"brand": "NEW", "sku": "S2"},
            ).to_list()

        assert (count, _brands(db, "F")) == ([{"count": 1}], AFTER)
