"""RESTORE statement coverage for the Python bindings.

This family had no test at all. The gap was left open deliberately while
upstream #6069 was outstanding: RESTORE put the record back but did not fold
the bucket's record-count delta, so `SELECT count(*)` returned one fewer than
a full scan and the disagreement survived close and reopen. Pinning the broken
behaviour would have baked a bug into the suite, and pinning the correct
behaviour would have failed until the fix landed.

Fixed upstream in 86cb4673be, "fold the bucket record-count delta on RESTORE
DOCUMENT/VERTEX/EDGE". These tests assert the fixed semantics, so they also
serve as the regression guard.

The count-vs-scan comparison is the load-bearing assertion, not the row
contents. A wrong count came back with an ordinary success and no warning, so
nothing but asking the same question two ways could tell it apart from a
correct one.
"""

import arcadedb_embedded as arcadedb
import pytest


def _count_two_ways(db, type_name):
    """(count(*), rows a full scan returns). These must agree."""
    counted = db.query("sql", f"SELECT count(*) AS c FROM {type_name}").to_list()[0][
        "c"
    ]
    scanned = len(db.query("sql", f"SELECT FROM {type_name}").to_list())
    return counted, scanned


def test_restore_document_restores_the_record_count(temp_db_path):
    """count(*) must agree with a full scan after RESTORE, and after reopen.

    Reopening is half the test: the original bug persisted across close and
    reopen, which is what proved it was the stored count rather than a stale
    in-memory statistic.
    """
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE Note")
        with db.transaction():
            for i in range(3):
                db.command("sql", "INSERT INTO Note SET i = :i", {"i": i})

        rid = db.query("sql", "SELECT @rid AS r FROM Note WHERE i = 1").to_list()[0][
            "r"
        ]
        assert _count_two_ways(db, "Note") == (3, 3)

        with db.transaction():
            db.command("sql", f"DELETE FROM {rid}")
        assert _count_two_ways(db, "Note") == (2, 2)

        with db.transaction():
            db.command("sql", f"RESTORE DOCUMENT Note RID {rid} SET i = 1")
        assert _count_two_ways(db, "Note") == (
            3,
            3,
        ), "count(*) disagrees with a full scan after RESTORE (upstream #6069)"

    with arcadedb.open_database(temp_db_path) as db:
        assert _count_two_ways(db, "Note") == (3, 3), (
            "the count disagreement survived reopen, so it is the persisted "
            "count rather than a stale in-memory statistic (upstream #6069)"
        )


def test_restore_document_returns_the_record_intact(temp_db_path):
    """The restored record keeps its original RID and the SET properties.

    Delete and restore in SEPARATE transactions, which is the shape the
    upstream repro used and the only one that currently works; see the xfail
    below for what happens when they share a transaction.
    """
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE Note")
        with db.transaction():
            db.command("sql", "INSERT INTO Note SET i = 7, tag = 'keep'")

        rid = db.query("sql", "SELECT @rid AS r FROM Note").to_list()[0]["r"]
        with db.transaction():
            db.command("sql", f"DELETE FROM {rid}")
        with db.transaction():
            db.command(
                "sql", f"RESTORE DOCUMENT Note RID {rid} SET i = 7, tag = 'keep'"
            )

        rows = db.query("sql", "SELECT @rid AS r, i, tag FROM Note").to_list()
        assert len(rows) == 1
        assert str(rows[0]["r"]) == str(rid), "RESTORE should reuse the original RID"
        assert rows[0]["i"] == 7
        assert rows[0]["tag"] == "keep"


@pytest.mark.xfail(
    strict=True,
    reason="RESTORE in the same transaction as the DELETE: count(*) reports 1 "
    "while a full scan returns 0, and the disagreement survives reopen. Same "
    "count-vs-scan shape as #6069, which 86cb4673be fixed only for the "
    "separate-transaction case. strict=True so this XPASSes and fails the "
    "suite the day it is fixed, rather than sitting here unnoticed.",
)
def test_restore_in_same_transaction_as_delete(temp_db_path):
    """DELETE then RESTORE within one transaction loses the record.

    Not a regression: RESTORE does not parse at all on the 26.8.1 release
    ("no viable alternative at input 'RESTORE'"), so the statement has never
    shipped and there is no earlier behaviour to have regressed from.
    """
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE Note")
        with db.transaction():
            db.command("sql", "INSERT INTO Note SET i = 7")

        rid = db.query("sql", "SELECT @rid AS r FROM Note").to_list()[0]["r"]
        with db.transaction():
            db.command("sql", f"DELETE FROM {rid}")
            db.command("sql", f"RESTORE DOCUMENT Note RID {rid} SET i = 7")

        counted, scanned = _count_two_ways(db, "Note")
        assert (counted, scanned) == (
            1,
            1,
        ), f"count(*)={counted} but a full scan returned {scanned} rows"


def test_restore_vertex_restores_the_record_count(temp_db_path):
    """The fix covers VERTEX as well as DOCUMENT, so pin both.

    Named separately rather than parametrized because a vertex carries edge
    bookkeeping a document does not, so a future regression could plausibly
    hit one and not the other.
    """
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE VERTEX TYPE Person")
        with db.transaction():
            for name in ("a", "b", "c"):
                db.command("sql", "INSERT INTO Person SET name = :n", {"n": name})

        rid = db.query(
            "sql", "SELECT @rid AS r FROM Person WHERE name = 'b'"
        ).to_list()[0]["r"]

        with db.transaction():
            db.command("sql", f"DELETE FROM {rid}")
        assert _count_two_ways(db, "Person") == (2, 2)

        with db.transaction():
            db.command("sql", f"RESTORE VERTEX Person RID {rid} SET name = 'b'")
        assert _count_two_ways(db, "Person") == (3, 3), (
            "count(*) disagrees with a full scan after RESTORE VERTEX "
            "(upstream #6069)"
        )
