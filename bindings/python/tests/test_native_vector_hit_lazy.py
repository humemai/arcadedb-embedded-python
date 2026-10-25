"""Native wheel: a ``find_nearest`` hit is built without the indexed vector and fills it on first use, with one lookup.

The values themselves are checked on both wheels in ``test_vector_hit_records.py``; this file counts what is shipped and looked up.
"""

import numpy as np
import pytest
from arcadedb_embedded.exceptions import ArcadeDBError

DIM = 8


@pytest.fixture
def lazy_db(temp_db, monkeypatch):
    temp_db.command("sql", "CREATE VERTEX TYPE Doc BUCKETS 4")
    temp_db.command("sql", "CREATE PROPERTY Doc.id INTEGER")
    temp_db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    rng = np.random.default_rng(5)
    vecs = rng.standard_normal((40, DIM)).astype(np.float32)
    with temp_db.transaction():
        for i in range(40):
            temp_db.command(
                "sql",
                "INSERT INTO Doc SET id = ?, name = ?, embedding = ?",
                i,
                f"n{i}",
                vecs[i].tolist(),
            )
    index = temp_db.create_vector_index(
        "Doc", "embedding", dimensions=DIM, id_property="id"
    )
    lookups = []
    original = type(temp_db).lookup_by_rid

    def counting(self, rid):
        lookups.append(str(rid))
        return original(self, rid)

    monkeypatch.setattr(type(temp_db), "lookup_by_rid", counting)
    return temp_db, index, vecs, lookups


def test_a_search_ships_no_vector_and_looks_up_nothing(lazy_db):
    db, index, vecs, lookups = lazy_db
    hits = index.find_nearest(vecs[2], k=6)
    assert len(hits) == 6
    for record, _ in hits:
        assert "embedding" not in record._props
        assert record.get("id") is not None and record.get("name")
        assert record.get_rid() and record.get_type_name() == "Doc"
    assert lookups == []


def test_the_vector_is_one_lookup_per_record_however_it_is_reached(lazy_db):
    db, index, vecs, lookups = lazy_db
    hits = index.find_nearest(vecs[2], k=4)
    first, second, third, fourth = (r for r, _ in hits)
    assert len(first.get("embedding")) == DIM
    assert len(first.get("embedding")) == DIM
    assert first.has_property("embedding")
    assert "embedding" in first.to_dict()
    assert "embedding" in first.get_property_names()
    assert len(lookups) == 1
    assert second.has_property("embedding")
    assert len(lookups) == 2
    assert "embedding" in third.to_dict()
    assert "embedding" in fourth.get_property_names()
    assert len(lookups) == 4
    assert sorted(lookups) == sorted(r.get_rid() for r, _ in hits)


def test_the_vector_of_a_closed_database_is_not_looked_up(lazy_db):
    db, index, vecs, lookups = lazy_db
    record, _ = index.find_nearest(vecs[2], k=1)[0]
    db.close()
    with pytest.raises(ArcadeDBError, match="closed"):
        record.get("embedding")
    assert lookups == []
