"""The statement texts the native backend sends to the engine, on the native backend only (not collected on JPype).

The engine keeps parsed statements in a cache keyed by statement text (``arcadedb.sqlStatementCache``, 300 entries by default), and it
leaves a record id written in a FROM target as part of the text. A record id pasted into the text therefore makes one cache entry per
record. The wrappers send the record id as a parameter instead, so a traversal step or a lookup has one text for every record.
"""

import re

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded._native.database import NativeDatabase

RID_IN_TEXT = re.compile(r"#-?\d+:-?\d+")


@pytest.fixture
def texts(monkeypatch):
    """Every statement text handed to the engine, in order, while the fixture is active."""
    seen = []
    db_class = NativeDatabase
    original = db_class._exec

    def recording(self, flags, prefix, language, command, args):
        seen.append(command)
        return original(self, flags, prefix, language, command, args)

    monkeypatch.setattr(db_class, "_exec", recording)
    return seen


def _graph(db, count):
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")
    with db.transaction():
        people = [db.new_vertex("Person").set("n", i).save() for i in range(count)]
        for i in range(count - 1):
            people[i].new_edge("Knows", people[i + 1])
    return [p.get_rid() for p in people]


def test_a_step_has_one_text_for_every_record(temp_db_path, texts):
    count = 25
    with arcadedb.create_database(temp_db_path) as db:
        rids = _graph(db, count)
        del texts[:]
        vertices = [db.lookup_by_rid(rid) for rid in rids]
        looked_up = list(texts)
        del texts[:]
        for vertex in vertices[:-1]:
            vertex.get_out_edges("Knows")
            vertex.get_in_edges()
            vertex.get_both_edges()
        steps = list(texts)
        del texts[:]
        edges = [v.get_out_edges("Knows")[0] for v in vertices[:-1]]
        del texts[:]
        for edge in edges:
            edge.get_out()
            edge.get_in()
        ends = list(texts)
        del texts[:]
        with db.transaction():
            for vertex in vertices[:10]:
                vertex.modify().set("n", -1).save()
            for vertex in vertices[10:20]:
                vertex.delete()
        writes = list(texts)
    assert len(looked_up) == count and len(set(looked_up)) == 1
    assert (
        len(steps) == 3 * (count - 1) and len(set(steps)) == 3
    )  # outE('Knows'), inE(), bothE()
    assert len(ends) == 2 * (count - 1) and len(set(ends)) == 2  # inV(), outV()
    # the update and the delete are one text each (the transaction's own statements are not counted)
    assert len({t for t in writes if t.startswith("UPDATE")}) == 1
    assert len({t for t in writes if t.startswith("DELETE")}) == 1
    for text in looked_up + steps + ends + writes:
        assert not RID_IN_TEXT.search(text), text


def test_new_edge_text_depends_on_the_label_only(temp_db_path, texts):
    with arcadedb.create_database(temp_db_path) as db:
        rids = _graph(db, 2)
        db.command("sql", "CREATE EDGE TYPE Likes")
        with db.transaction():
            vertices = [db.lookup_by_rid(rid) for rid in rids]
            del texts[:]
            for _ in range(8):
                vertices[0].new_edge("Likes", vertices[1])
                vertices[1].new_edge("Likes", vertices[0], w=1)
            created = list(texts)
    assert len(created) == 16 and len(set(created)) == 2  # with and without CONTENT
    for text in created:
        assert not RID_IN_TEXT.search(text), text
