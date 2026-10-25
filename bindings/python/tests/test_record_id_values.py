"""A record id inside a row: the same behaviour on the JVM wheel and the native wheel.

The contract (docs/api/results.md, "Record ids in rows"):

- a record id that sits in a row value (``SELECT @rid``, a LINK property, a list of links) is an
  RID object, not text: ``str(rid)`` is the text (``"#10:5"``), two RIDs of the same record are
  equal and hash alike, and RIDs sort by bucket and position;
- ``getBucketId()``, ``getPosition()``, ``toString()`` and ``isValid()`` work on it (the Java
  ``RID`` has them; the native wheel's ``RID`` offers the same names);
- an RID goes back in as a query parameter, and to ``lookup_by_rid``, as itself or as its text;
- ``get_rid()`` is text (or ``None``) on every wheel.

Before this file the JVM wheel handed out a Java ``RID`` and the native wheel its own ``RID``
class, and nothing pinned what the two had in common. Comparing an RID with a string (``rid ==
"#10:5"``) is False on the JVM wheel and True on the native wheel, so it is not part of the
contract: compare ``str(rid)``.
"""

import re

import pytest

RID_TEXT = re.compile(r"^#\d+:\d+$")


@pytest.fixture
def graph_db(temp_db):
    db = temp_db
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")
    db.command("sql", "CREATE PROPERTY Person.friend LINK")
    with db.transaction():
        db.command("sql", "CREATE VERTEX Person SET name = 'ann'").close()
        db.command("sql", "CREATE VERTEX Person SET name = 'bob'").close()
        db.command("sql", "CREATE VERTEX Person SET name = 'cy'").close()
        for target in ("bob", "cy"):
            db.command(
                "sql",
                "CREATE EDGE Knows FROM (SELECT FROM Person WHERE name = 'ann') "
                f"TO (SELECT FROM Person WHERE name = '{target}')",  # nosec B608 - test-owned literals
            ).close()
        db.command(
            "sql",
            "UPDATE Person SET friend = (SELECT @rid FROM Person WHERE name = 'bob') "
            "WHERE name = 'ann'",
        ).close()
    return db


def _rid_of(db, name):
    return (
        db.query("sql", "SELECT @rid AS r FROM Person WHERE name = ?", name)
        .first()
        .get("r")
    )


def test_rid_in_a_row_prints_as_its_text(graph_db):
    rid = _rid_of(graph_db, "ann")
    assert not isinstance(rid, str)
    assert RID_TEXT.match(str(rid))
    assert f"{rid}" == str(rid)
    assert f"x{rid}x" == f"x{str(rid)}x"


def test_every_row_path_gives_the_same_kind_of_value(graph_db):
    sql = "SELECT @rid AS r FROM Person WHERE name = 'ann'"
    via_get = graph_db.query("sql", sql).first().get("r")
    via_list = graph_db.query("sql", sql).to_list()[0]["r"]
    via_dict = graph_db.query("sql", sql).first().to_dict()["r"]
    via_iter = next(iter(graph_db.query("sql", sql).iter_dicts()))["r"]
    assert type(via_get) is type(via_list) is type(via_dict) is type(via_iter)
    assert str(via_get) == str(via_list) == str(via_dict) == str(via_iter)


def test_same_record_is_equal_and_hashes_alike(graph_db):
    first = _rid_of(graph_db, "ann")
    second = _rid_of(graph_db, "ann")
    other = _rid_of(graph_db, "bob")
    assert first == second
    assert not (first != second)
    assert first != other
    assert hash(first) == hash(second)
    assert len({first, second, other}) == 2
    assert {first: "x"}[second] == "x"


def test_rids_sort_by_bucket_and_position(graph_db):
    rids = [
        r["r"] for r in graph_db.query("sql", "SELECT @rid AS r FROM Person").to_list()
    ]
    assert len(rids) == 3

    def by_numbers(rid):
        bucket, position = str(rid)[1:].split(":")
        return int(bucket), int(position)

    assert [str(r) for r in sorted(rids)] == [
        str(r) for r in sorted(rids, key=by_numbers)
    ]
    lowest, highest = sorted(rids)[0], sorted(rids)[-1]
    assert lowest < highest
    assert highest > lowest
    assert lowest <= lowest
    assert highest >= highest


def test_bucket_and_position_accessors(graph_db):
    rid = _rid_of(graph_db, "bob")
    bucket, position = (int(part) for part in str(rid)[1:].split(":"))
    assert int(rid.getBucketId()) == bucket
    assert int(rid.getPosition()) == position
    assert str(rid.toString()) == str(rid)
    assert bool(rid.isValid()) is True


def test_link_property_is_a_rid_of_the_target(graph_db):
    bob = _rid_of(graph_db, "bob")
    row = graph_db.query("sql", "SELECT friend FROM Person WHERE name = 'ann'").first()
    assert row.get("friend") == bob
    assert type(row.get("friend")) is type(bob)
    record = (
        graph_db.query("sql", "SELECT FROM Person WHERE name = 'ann'")
        .first()
        .get_vertex()
    )
    assert record.get("friend") == bob
    assert record.to_dict()["friend"] == bob
    assert str(record.get("friend")) == graph_db.lookup_by_rid(str(bob)).get_rid()


def test_list_of_rids(graph_db):
    row = graph_db.query(
        "sql", "SELECT out('Knows').@rid AS ids FROM Person WHERE name = 'ann'"
    ).first()
    ids = row.get("ids")
    assert len(ids) == 2
    assert {str(i) for i in ids} == {
        str(_rid_of(graph_db, "bob")),
        str(_rid_of(graph_db, "cy")),
    }
    assert all(type(i) is type(_rid_of(graph_db, "bob")) for i in ids)


def test_rid_goes_back_in_as_a_parameter(graph_db):
    bob = _rid_of(graph_db, "bob")
    cy = _rid_of(graph_db, "cy")

    def names(rows):
        return sorted(r.get("name") for r in rows)

    assert names(
        graph_db.query("sql", "SELECT name FROM Person WHERE @rid = ?", bob)
    ) == ["bob"]
    assert names(
        graph_db.query("sql", "SELECT name FROM Person WHERE @rid = :r", {"r": bob})
    ) == ["bob"]
    # (a lone list argument is the parameter list itself, so a list value goes by name)
    assert names(
        graph_db.query(
            "sql", "SELECT name FROM Person WHERE @rid IN :ids", {"ids": [bob, cy]}
        )
    ) == ["bob", "cy"]
    # the text works as a parameter on both wheels as well
    assert names(
        graph_db.query("sql", "SELECT name FROM Person WHERE @rid = ?", str(bob))
    ) == ["bob"]


def test_lookup_by_rid_takes_the_rid_or_its_text(graph_db):
    bob = _rid_of(graph_db, "bob")
    assert graph_db.lookup_by_rid(bob).get("name") == "bob"
    assert graph_db.lookup_by_rid(str(bob)).get("name") == "bob"
    assert graph_db.lookup_by_rid(bob).get_rid() == str(bob)


def test_get_identity_is_the_same_kind_of_value(graph_db):
    bob = _rid_of(graph_db, "bob")
    vertex = graph_db.lookup_by_rid(str(bob))
    assert vertex.get_identity() == bob
    assert type(vertex.get_identity()) is type(bob)
    assert str(vertex.get_identity()) == vertex.get_rid()


def test_get_rid_is_text_for_every_kind_of_row(graph_db):
    record = graph_db.query("sql", "SELECT FROM Person WHERE name = 'ann'").first()
    assert isinstance(record.get_rid(), str) and RID_TEXT.match(record.get_rid())
    assert isinstance(record.get_vertex().get_rid(), str)

    edge = graph_db.query("sql", "SELECT FROM Knows").first()
    assert isinstance(edge.get_rid(), str) and RID_TEXT.match(edge.get_rid())
    assert isinstance(edge.get_edge().get_rid(), str)

    expanded = graph_db.query(
        "sql", "SELECT expand(out('Knows')) FROM Person WHERE name = 'ann'"
    ).first()
    assert isinstance(expanded.get_rid(), str)


def test_get_rid_of_a_projection(graph_db):
    # a projection of @rid is a row with that identity, an aliased one or an aggregate is not
    plain = graph_db.query(
        "sql", "SELECT @rid, name FROM Person WHERE name = 'ann'"
    ).first()
    assert plain.get_rid() == str(_rid_of(graph_db, "ann"))
    edge = graph_db.query("sql", "SELECT @rid FROM Knows").first()
    assert isinstance(edge.get_rid(), str) and RID_TEXT.match(edge.get_rid())
    assert (
        graph_db.query("sql", "SELECT @rid AS r, name FROM Person WHERE name = 'ann'")
        .first()
        .get_rid()
        is None
    )
    assert (
        graph_db.query("sql", "SELECT name FROM Person WHERE name = 'ann'")
        .first()
        .get_rid()
        is None
    )
    assert (
        graph_db.query("sql", "SELECT count(*) AS c FROM Person").first().get_rid()
        is None
    )
