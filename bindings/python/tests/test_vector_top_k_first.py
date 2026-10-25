"""``VectorIndex.find_nearest`` merges the hits of the bucket indexes by score and loads only the final k.

A type with B buckets has B vector indexes. The search used to load and wrap every hit of every
bucket (B * k record lookups) to keep k. These tests pin the result (same k records, same order, same
scores as a stable merge of the per-bucket hit lists) and the cost (k records loaded, not B * k).
JVM wheel only: they read the Java hit lists of the bucket indexes.
"""

import numpy as np
import pytest

BUCKETS = 4
DIM = 16
COUNT = 300


@pytest.fixture
def index(temp_db):
    temp_db.command("sql", f"CREATE VERTEX TYPE Doc BUCKETS {BUCKETS}")
    temp_db.command("sql", "CREATE PROPERTY Doc.id INTEGER")
    temp_db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    rng = np.random.default_rng(11)
    vectors = rng.standard_normal((COUNT, DIM)).astype(np.float32)
    with temp_db.transaction():
        for i in range(COUNT):
            temp_db.command(
                "sql",
                "INSERT INTO Doc SET id = ?, embedding = ?",
                i,
                vectors[i].tolist(),
            )
    idx = temp_db.create_vector_index(
        "Doc", "embedding", dimensions=DIM, id_property="id"
    )
    assert len(list(idx._iter_lsm_indexes())) == BUCKETS
    return idx


def _queries(count=8):
    rng = np.random.default_rng(5)
    return [rng.standard_normal(DIM).astype(np.float32) for _ in range(count)]


def _reference(idx, query, k):
    """Stable merge of the raw per-bucket hit lists: what the search must return."""
    from arcadedb_embedded import to_java_float_array

    java_vector = to_java_float_array(query)
    merged = []
    for bucket_index in idx._iter_lsm_indexes():
        pairs = idx._find_neighbor_pairs(
            bucket_index,
            java_vector=java_vector,
            k=k,
            allowed_rids_set=None,
            approximate=False,
        )
        merged.extend((float(p.getSecond()), str(p.getFirst())) for p in pairs)
    merged.sort(key=lambda item: item[0])
    return merged[:k]


@pytest.mark.parametrize("k", [1, 5, 10, 50, 400])
def test_same_records_order_and_scores_as_a_merge_of_the_buckets(index, k):
    for query in _queries():
        hits = index.find_nearest(query, k=k)
        expected = _reference(index, query, k)
        assert [(float(score), record.get_rid()) for record, score in hits] == [
            (score, rid) for score, rid in expected
        ]
        assert [s for _, s in hits] == sorted(s for _, s in hits)


def test_loads_and_wraps_only_k_records(index, monkeypatch):
    import arcadedb_embedded.core as core

    wrapped = []
    original = core._wrap_java_record

    def counting(record, database):
        wrapped.append(record)
        return original(record, database)

    monkeypatch.setattr(core, "_wrap_java_record", counting)
    hits = index.find_nearest(_queries(1)[0], k=10)
    assert len(hits) == 10
    assert len(wrapped) == 10  # was BUCKETS * 10


def test_without_the_bridge_jar_it_loads_only_k_and_answers_the_same(
    index, monkeypatch
):
    import arcadedb_embedded.graph as graph

    query = _queries(1)[0]
    with_bridge = [(r.get_rid(), s) for r, s in index.find_nearest(query, k=10)]

    lookups = []
    original = type(index)._lookup_record_by_rid

    def counting(self, rid):
        lookups.append(rid)
        return original(self, rid)

    monkeypatch.setattr(graph, "_graph_calls", lambda: None)
    monkeypatch.setattr(type(index), "_lookup_record_by_rid", counting)
    without_bridge = [(r.get_rid(), s) for r, s in index.find_nearest(query, k=10)]
    assert without_bridge == with_bridge
    assert len(lookups) == 10  # was BUCKETS * 10
