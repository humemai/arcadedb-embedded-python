"""Opening a database read-only (#383).

`open_database(path, read_only=True)` and `DatabaseFactory.open(read_only=True)`
open the files in `ComponentFile.MODE.READ_ONLY`. A mode is not a query, so it
is the one part of #383 the bindings wrap: every other item there is a SQL
statement (see `test_sql_constraints_and_maintenance.py`).
"""

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import ArcadeDBError


@pytest.fixture
def populated_path(temp_db_path):
    """A closed database holding two `Note` documents."""
    with arcadedb.create_database(temp_db_path) as db:
        db.command("sql", "CREATE DOCUMENT TYPE Note")
        with db.transaction():
            db.command("sql", "INSERT INTO Note SET n = 1")
            db.command("sql", "INSERT INTO Note SET n = 2")
    return temp_db_path


def test_read_only_open_reads_and_refuses_writes(populated_path):
    with arcadedb.open_database(populated_path, read_only=True) as db:
        assert db.is_read_only()
        assert db.count_type("Note") == 2
        rows = db.query("sql", "SELECT n FROM Note ORDER BY n").to_list()
        assert [r["n"] for r in rows] == [1, 2]

        with pytest.raises(ArcadeDBError, match="read only"):
            with db.transaction():
                db.command("sql", "INSERT INTO Note SET n = 3")
        with pytest.raises(ArcadeDBError, match="read only"):
            db.command("sql", "CREATE DOCUMENT TYPE Other")

    # The refused writes left the files as they were.
    with arcadedb.open_database(populated_path) as db:
        assert not db.is_read_only()
        assert db.count_type("Note") == 2
        assert not db.schema.exists_type("Other")


def test_factory_open_read_only_and_default_is_writable(populated_path):
    factory = arcadedb.DatabaseFactory(populated_path)

    db = factory.open(read_only=True)
    try:
        assert db.is_read_only()
    finally:
        db.close()

    db = factory.open()
    try:
        assert not db.is_read_only()
        with db.transaction():
            db.command("sql", "INSERT INTO Note SET n = 3")
        assert db.count_type("Note") == 3
    finally:
        db.close()
