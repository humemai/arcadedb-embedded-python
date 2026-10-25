"""``find_nearest`` hands the native library its query vector as one float32 array, not as a Python list of floats.

A list of dim floats is walked by the codec (one ``_prep`` call per element) and then printed by ``json.dumps`` (one float repr per
element) on every search. A numpy array travels through the binary float32 side buffer instead (tag ``B``: a pointer and a count,
read by the library straight from the C buffer). ``find_nearest`` used to turn every query into a list with ``tolist()``, which
defeated that path for the callers that already hold an array.

The counts are calls, not seconds: they are deterministic. The agreement tests pin the other half: the array form and the list form
return the same neighbours at the same distances, and a query that is not a numeric vector is still refused.

Needs the native library, so conftest.py does not collect this file on the JPype backend (a skip there would fail
scripts/check_test_skips.py); it runs in the native parity run.
"""

import arcadedb_embedded as arcadedb
import numpy as np
import pytest
from arcadedb_embedded import ArcadeDBError
from arcadedb_embedded._native import codec
from arcadedb_embedded._native import database as native_database

DIM = 768
N = 60


@pytest.fixture
def index(temp_db_path):
    db = arcadedb.create_database(temp_db_path)
    db.command("sql", "CREATE VERTEX TYPE Doc")
    db.command("sql", "CREATE PROPERTY Doc.id INTEGER")
    db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    vectors = np.random.default_rng(7).standard_normal((N, DIM)).astype(np.float32)
    with db.transaction():
        for i in range(N):
            db.command(
                "sql", "INSERT INTO Doc SET id = ?, embedding = ?", i, vectors[i]
            )
    idx = db.create_vector_index("Doc", "embedding", dimensions=DIM)
    idx.vectors = vectors
    yield idx
    db.drop()


def _answer(hits):
    return [(record.get("id"), distance) for record, distance in hits]


class _PrepCalls:
    """Counts every ``codec._prep`` call made while installed, and those whose argument is one float of the vector."""

    def __init__(self, monkeypatch):
        self.total = 0
        self.floats = 0
        real = codec._prep

        def counting(value):
            self.total += 1
            if isinstance(value, float):
                self.floats += 1
            return real(value)

        monkeypatch.setattr(codec, "_prep", counting)


def test_an_array_query_makes_no_per_element_prep_calls(index, monkeypatch):
    calls = _PrepCalls(monkeypatch)
    index.find_nearest(index.vectors[3], k=5)
    assert calls.floats == 0
    assert (
        calls.total <= 4
    )  # the statement's own few parameters, whatever the dimension


def test_a_float64_array_and_a_list_query_make_no_per_element_calls_either(
    index, monkeypatch
):
    calls = _PrepCalls(monkeypatch)
    index.find_nearest(index.vectors[3].astype(np.float64), k=5)
    index.find_nearest(index.vectors[3].tolist(), k=5)
    assert calls.floats == 0
    assert calls.total <= 8


def test_the_query_travels_in_the_binary_side_buffer(index, monkeypatch):
    seen = []
    real = native_database.encode_params

    def recording(args, binary=False):
        encoded = real(args, binary)
        seen.append(encoded)
        return encoded

    monkeypatch.setattr(native_database, "encode_params", recording)
    index.find_nearest(index.vectors[3], k=5)
    # the search's own parameters are the call that carries DIM floats beside the text (the record lookups after it carry none)
    search = [text for text, _, floats in seen if floats == DIM]
    assert len(search) == 1
    assert '"B"' in search[0]


# -- the same answers


def test_every_form_of_the_query_returns_the_same_neighbours_at_the_same_distances(
    index,
):
    query = index.vectors[11]
    expected = _answer(index.find_nearest(query.tolist(), k=10))
    assert len(expected) == 10
    assert expected[0][0] == 11
    forms = {
        "float32 array": query,
        "float64 array": query.astype(np.float64),
        "tuple": tuple(query.tolist()),
        "list of numpy floats": list(query),
        "generator": (float(x) for x in query),
        "non-contiguous view": np.repeat(query, 2)[::2],
    }
    for name, form in forms.items():
        assert _answer(index.find_nearest(form, k=10)) == expected, name


def test_an_integer_array_is_a_numeric_query(index):
    ints = np.arange(DIM) % 5
    expected = _answer(index.find_nearest(ints.tolist(), k=5))
    assert _answer(index.find_nearest(ints, k=5)) == expected


def test_find_nearest_by_key_agrees_with_the_array_query(index):
    by_key = _answer(index.find_nearest_by_key(4, k=6))
    assert by_key == _answer(index.find_nearest(index.vectors[4], k=6))


def test_filter_and_ef_search_options_still_apply_to_an_array_query(index):
    everything = index.find_nearest(index.vectors[2], k=10)
    allowed = [record.get_rid() for record, _ in everything[:3]]
    hits = index.find_nearest(index.vectors[2], k=10, allowed_rids=allowed)
    assert {record.get_rid() for record, _ in hits} == set(allowed)
    assert _answer(index.find_nearest(index.vectors[2], k=10, ef_search=64))


# -- what is still refused


def test_a_query_of_the_wrong_dimension_is_refused_in_both_forms(index):
    with pytest.raises(ArcadeDBError):
        index.find_nearest(np.zeros(5, dtype=np.float32), k=3)
    with pytest.raises(ArcadeDBError):
        index.find_nearest([0.0] * 5, k=3)


@pytest.mark.parametrize(
    "bad", [[None] * DIM, ["x"] * DIM], ids=["None entries", "text entries"]
)
def test_a_query_that_is_not_numeric_is_refused(index, bad):
    # numpy would turn None into nan; the query must reach the engine as it was given
    with pytest.raises(ArcadeDBError):
        index.find_nearest(bad, k=3)
