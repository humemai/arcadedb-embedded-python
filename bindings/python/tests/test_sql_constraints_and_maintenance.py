"""The SQL forms the docs give for what #383 asked the bindings to wrap.

The bindings are DSL-first (`docs/api-access-methods.md`): property
constraints, type scans, the transaction isolation level and the admin
statements are each one SQL statement, so the docs show the statement and this
file runs it. A statement the documentation names and no test runs is a claim
nobody checked.

`COMPACT INDEX` runs in `test_sparse_quantization_compact.py`.
"""

import threading
import zipfile

import arcadedb_embedded as arcadedb
import jpype
import pytest
from arcadedb_embedded import ArcadeDBError


def _insert(db, statement):
    with db.transaction():
        db.command("sql", statement)


def test_create_property_constraints_refuse_bad_values(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Item")
    db.command(
        "sql",
        "CREATE PROPERTY Item.qty INTEGER (mandatory true, notnull true, min 0, max 100)",
    )
    db.command(
        "sql", "CREATE PROPERTY Item.code STRING (regexp '[A-Z]+', default 'AB')"
    )
    db.command("sql", "CREATE PROPERTY Item.tag STRING (readonly true)")

    # min, max, mandatory, notnull and regexp each refuse a record
    for bad in (
        "INSERT INTO Item SET qty = 101",
        "INSERT INTO Item SET qty = -1",
        "INSERT INTO Item SET code = 'ABC'",
        "INSERT INTO Item SET qty = null",
        "INSERT INTO Item SET qty = 1, code = 'abc'",
    ):
        with pytest.raises(ArcadeDBError, match="ValidationException"):
            _insert(db, bad)
    assert db.count_type("Item") == 0

    # a valid record is accepted and takes the default
    _insert(db, "INSERT INTO Item SET qty = 5, tag = 'first'")
    row = db.query("sql", "SELECT qty, code, tag FROM Item").first().to_dict()
    assert row == {"qty": 5, "code": "AB", "tag": "first"}

    # readonly: the value cannot change once the record exists
    with pytest.raises(ArcadeDBError, match="ValidationException"):
        _insert(db, "UPDATE Item SET tag = 'second'")
    assert db.query("sql", "SELECT tag FROM Item").first().get("tag") == "first"


def test_alter_property_changes_a_constraint_on_an_existing_property(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Item")
    db.command("sql", "CREATE PROPERTY Item.qty INTEGER")
    _insert(db, "INSERT INTO Item SET qty = 500")  # no max yet

    # a constraint the stored records already break is refused, not applied
    with pytest.raises(ArcadeDBError, match="violates it"):
        db.command("sql", "ALTER PROPERTY Item.qty MAX 100")
    _insert(db, "UPDATE Item SET qty = 50")

    db.command("sql", "ALTER PROPERTY Item.qty MAX 100")
    with pytest.raises(ArcadeDBError, match="ValidationException"):
        _insert(db, "INSERT INTO Item SET qty = 101")
    _insert(db, "INSERT INTO Item SET qty = 100")
    assert db.count_type("Item") == 2


def test_select_from_type_scans_subtypes(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Animal")
    db.command("sql", "CREATE DOCUMENT TYPE Dog EXTENDS Animal")
    db.command("sql", "CREATE DOCUMENT TYPE Puppy EXTENDS Dog")
    with db.transaction():
        db.command("sql", "INSERT INTO Animal SET name = 'a'")
        db.command("sql", "INSERT INTO Dog SET name = 'd'")
        db.command("sql", "INSERT INTO Puppy SET name = 'p'")

    names = {r["name"] for r in db.query("sql", "SELECT FROM Animal").to_list()}
    assert names == {"a", "d", "p"}
    names = {r["name"] for r in db.query("sql", "SELECT FROM Dog").to_list()}
    assert names == {"d", "p"}


def _versions_seen_by(db, level):
    """Read the counter, let another thread bump it, read again, in one transaction."""
    db.command("sql", f"BEGIN ISOLATION {level}")
    try:
        first = db.query("sql", "SELECT v FROM Counter").first().get("v")

        def bump():
            with db.transaction():
                db.command("sql", "UPDATE Counter SET v = v + 1")

        worker = threading.Thread(target=bump)
        worker.start()
        worker.join()
        second = db.query("sql", "SELECT v FROM Counter").first().get("v")
    finally:
        db.commit()
    return first, second


def test_begin_isolation_read_committed_vs_repeatable_read(temp_db):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Counter")
    _insert(db, "INSERT INTO Counter SET v = 1")

    first, second = _versions_seen_by(db, "READ_COMMITTED")
    assert (first, second) == (1, 2)  # the other thread's commit is visible

    first, second = _versions_seen_by(db, "REPEATABLE_READ")
    assert first == second == 2  # the committed 3 is not
    assert db.query("sql", "SELECT v FROM Counter").first().get("v") == 3


def test_backup_check_and_rebuild_index_statements(temp_db, tmp_path):
    db = temp_db
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.email STRING")
    db.command("sql", "CREATE INDEX ON Person (email) UNIQUE")
    with db.transaction():
        for i in range(20):
            db.command(
                "sql", f"INSERT INTO Person SET email = 'p{i}@x.org'"
            )  # nosec B608

    # CHECK DATABASE on a clean database reports no error
    report = db.command("sql", "CHECK DATABASE").first().to_dict()
    assert report["operation"] == "check database"
    assert report.get("totalErrors", 0) == 0
    report = db.command("sql", "CHECK DATABASE FIX").first().to_dict()
    assert report.get("totalErrors", 0) == 0

    # REBUILD INDEX re-indexes every record
    rebuilt = db.command("sql", "REBUILD INDEX *").first().to_dict()
    assert rebuilt["operation"] == "rebuild index"
    assert rebuilt["totalIndexed"] == 20
    assert not rebuilt.get("failedIndexes")
    assert len(rebuilt["indexes"]) >= 1
    one = db.command("sql", "REBUILD INDEX `Person[email]`").first()
    assert one.get("operation") == "rebuild index"

    # BACKUP DATABASE writes <arcadedb.server.backupDirectory>/<db name>/<file>
    config = jpype.JClass("com.arcadedb.GlobalConfiguration").SERVER_BACKUP_DIRECTORY
    config.setValue(str(tmp_path / "backups"))
    try:
        result = db.command("sql", "BACKUP DATABASE 'person.zip'").first().to_dict()
    finally:
        config.reset()
    assert result["result"] == "OK"
    archive = tmp_path / "backups" / str(db.get_name()) / "person.zip"
    assert archive.is_file()

    # the archive is the database: unzip it and open it
    restored = tmp_path / "restored"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(restored)
    with arcadedb.open_database(str(restored)) as copy:
        assert copy.count_type("Person") == 20
        found = copy.query(
            "sql", "SELECT FROM Person WHERE email = 'p7@x.org'"
        ).to_list()
        assert len(found) == 1
