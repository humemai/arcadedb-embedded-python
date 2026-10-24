"""Float vectors cross the bridge as one binary matrix, not as JSON text or one JPype call per element.

A list of 128 floats written as JSON text cost Python about 450 ns a number and the engine's parser about the same again, so
a vector load spent most of its time on the text (bridge class ``FloatVectors``). For a property declared ARRAY_OF_FLOATS the
engine converts every number of a list to float, so a float32 matrix stores the same values as the list did: these tests pin
that equality with doubles a float32 cannot hold, pin which values keep the JSON path (exact doubles on an undeclared property,
ragged or null vectors), and cover every entry point: ``insert_many`` (also parallel), ``insert_columns`` with a 2-D float32
column, ``GraphBatch.create_vertices``, ``Document.set`` with a numpy array, and the ``allowed_rids`` filter of a vector search.
"""

from datetime import datetime

import arcadedb_embedded as arcadedb
import numpy as np
import pytest
from arcadedb_embedded import type_conversion

DIM = 8
N = 50


@pytest.fixture
def vec_db(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE Doc")
    temp_db.command("sql", "CREATE PROPERTY Doc.id LONG")
    temp_db.command("sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
    temp_db.command(
        "sql", "CREATE DOCUMENT TYPE Plain"
    )  # embedding undeclared: the list keeps its doubles
    temp_db.command("sql", "CREATE VERTEX TYPE Vx")
    temp_db.command("sql", "CREATE PROPERTY Vx.id LONG")
    temp_db.command("sql", "CREATE PROPERTY Vx.embedding ARRAY_OF_FLOATS")
    temp_db.command("sql", "CREATE DOCUMENT TYPE Parent")
    temp_db.command("sql", "CREATE PROPERTY Parent.embedding ARRAY_OF_FLOATS")
    temp_db.command("sql", "CREATE DOCUMENT TYPE Child EXTENDS Parent")
    return temp_db


def _doubles(n=N, dim=DIM, seed=7):
    """float64 values a float32 cannot hold, so a path that kept doubles or lost bits shows."""
    return np.random.default_rng(seed).random((n, dim)) * 1000.0 + 1e-3


def _rows(x):
    return [{"id": i, "embedding": x[i].tolist()} for i in range(len(x))]


def _stored(db, type_name):
    """{id: stored vector as float64} for every record of the type."""
    out = {}
    query = (
        f"SELECT id, embedding FROM {type_name}"  # nosec B608 - test-owned type name
    )
    for r in db.query("sql", query).to_list():
        out[r["id"]] = np.array(r["embedding"], dtype=np.float64)
    return out


def _assert_float32_of(stored, x):
    assert sorted(stored) == list(range(len(x)))
    for i, vec in stored.items():
        assert np.array_equal(vec, x[i].astype(np.float32).astype(np.float64)), i


class TestDecision:
    """split_float_vectors takes a property out of the JSON only when the float32 matrix stores the same values."""

    def _split(self, db, type_name, rows):
        return type_conversion.split_float_vectors(
            db.get_java_database(), type_name, rows
        )

    def test_a_declared_vector_column_is_taken_out(self, vec_db):
        rows = _rows(_doubles())
        rest, names, matrices = self._split(vec_db, "Doc", rows)
        assert [str(n) for n in names] == ["embedding"]
        assert len(matrices) == 1
        assert rest == [{"id": i} for i in range(N)]
        assert "embedding" in rows[0], "the caller's rows are not changed"

    def test_numpy_rows_and_ints_are_taken_out(self, vec_db):
        assert (
            self._split(
                vec_db, "Doc", [{"embedding": np.arange(DIM, dtype=np.float64)}] * 3
            )
            is not None
        )
        assert (
            self._split(
                vec_db, "Doc", [{"embedding": [1, 2, 3]}, {"embedding": [1.5, 2, 3]}]
            )
            is not None
        )

    def test_the_inherited_declaration_counts(self, vec_db):
        assert self._split(vec_db, "Child", _rows(_doubles())) is not None

    @pytest.mark.parametrize(
        "rows",
        [
            [{"embedding": [1.0, 2.0]}, {"embedding": [1.0, 2.0, 3.0]}],  # ragged
            [{"embedding": [1.0, 2.0]}, {"embedding": None}],  # a null
            [{"embedding": [1.0, 2.0]}, {"id": 3}],  # missing in a row
            [{"embedding": ["a", "b"]}, {"embedding": ["c", "d"]}],  # not numbers
            [{"embedding": [True, False]}, {"embedding": [False, True]}],  # booleans
            [{"embedding": []}, {"embedding": []}],  # no dimension
            [{"embedding": 1.5}, {"embedding": 2.5}],  # a scalar
        ],
    )
    def test_anything_else_stays_in_the_json(self, vec_db, rows):
        assert self._split(vec_db, "Doc", rows) is None

    def test_an_undeclared_property_stays_in_the_json(self, vec_db):
        assert self._split(vec_db, "Plain", _rows(_doubles())) is None
        assert self._split(vec_db, "NoSuchType", _rows(_doubles())) is None


class TestInsertMany:
    def test_list_vectors_store_what_the_engine_stores_for_a_list(self, vec_db):
        x = _doubles()
        assert vec_db.insert_many("Doc", _rows(x)) == N
        _assert_float32_of(_stored(vec_db, "Doc"), x)
        # the reference: the per-record path, where the engine converts the list itself
        with vec_db.transaction():
            for i in range(N):
                vec_db.new_document("Parent").set(
                    "embedding", [float(v) for v in x[i]]
                ).set("id", i).save()
        reference = {
            r.get("id"): np.array(r.get("embedding"), dtype=np.float64)
            for r in vec_db.query("sql", "SELECT id, embedding FROM Parent")
        }
        for i, vec in _stored(vec_db, "Doc").items():
            assert np.array_equal(vec, reference[i])

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_numpy_rows(self, vec_db, dtype):
        x = _doubles()
        rows = [{"id": i, "embedding": x[i].astype(dtype)} for i in range(N)]
        assert vec_db.insert_many("Doc", rows) == N
        _assert_float32_of(_stored(vec_db, "Doc"), x)

    def test_an_undeclared_property_keeps_its_doubles(self, vec_db):
        x = _doubles()
        assert vec_db.insert_many("Plain", _rows(x)) == N
        got = _stored(vec_db, "Plain")
        for i in range(N):
            assert np.array_equal(got[i], x[i])

    def test_numpy_rows_on_an_undeclared_property(self, vec_db):
        x = _doubles()
        vec_db.insert_many(
            "Plain",
            [
                {"id": 0, "embedding": x[0]},
                {"id": 1, "embedding": x[1].astype(np.float32)},
            ],
        )
        got = _stored(vec_db, "Plain")
        assert np.array_equal(
            got[0], x[0]
        )  # a float64 array is the list it would have been
        assert np.array_equal(got[1], x[1].astype(np.float32).astype(np.float64))

    def test_ragged_and_null_vectors_keep_the_json_path(self, vec_db):
        rows = [
            {"id": 0, "embedding": [1.0, 2.0]},
            {"id": 1, "embedding": [1.0, 2.0, 3.0]},
            {"id": 2, "embedding": None},
        ]
        assert vec_db.insert_many("Doc", rows) == 3
        got = {
            r["id"]: r["embedding"]
            for r in vec_db.query("sql", "SELECT id, embedding FROM Doc").to_list()
        }
        assert got[0] == [1.0, 2.0] and got[1] == [1.0, 2.0, 3.0] and got[2] is None

    def test_other_properties_still_cross_in_the_json(self, vec_db):
        vec_db.command("sql", "CREATE PROPERTY Doc.name STRING")
        x = _doubles(5)
        vec_db.insert_many(
            "Doc",
            [{"id": i, "name": f"n{i}", "embedding": x[i].tolist()} for i in range(5)],
        )
        names = {
            r["id"]: r["name"]
            for r in vec_db.query("sql", "SELECT id, name FROM Doc").to_list()
        }
        assert names == {i: f"n{i}" for i in range(5)}

    def test_a_chunk_boundary_and_a_row_count_that_is_not_a_chunk(self, vec_db):
        x = _doubles(23_000, 4)
        assert vec_db.insert_many("Doc", _rows(x), commit_every=7_000) == 23_000
        got = _stored(vec_db, "Doc")
        assert len(got) == 23_000
        for i in (0, 9_999, 10_000, 22_999):
            assert np.array_equal(got[i], x[i].astype(np.float32).astype(np.float64))

    def test_parallel(self, vec_db):
        x = _doubles(200)
        assert vec_db.insert_many("Doc", _rows(x), parallel=True) == 200
        _assert_float32_of(_stored(vec_db, "Doc"), x)

    def test_the_vector_survives_a_rolled_back_batch_not_at_all(self, vec_db):
        x = _doubles(5)
        with pytest.raises(RuntimeError):
            with vec_db.transaction():
                vec_db.insert_many("Doc", _rows(x))
                raise RuntimeError("abandon")
        assert _stored(vec_db, "Doc") == {}


class TestInsertColumns:
    def test_a_two_dimensional_float32_column(self, vec_db):
        x = _doubles().astype(np.float32)
        assert vec_db.insert_columns("Doc", {"id": np.arange(N), "embedding": x}) == N
        stored = _stored(vec_db, "Doc")
        for i in range(N):
            assert np.array_equal(stored[i], x[i].astype(np.float64))

    def test_parallel(self, vec_db):
        x = _doubles(120).astype(np.float32)
        assert (
            vec_db.insert_columns(
                "Doc", {"id": np.arange(120), "embedding": x}, parallel=True
            )
            == 120
        )
        assert len(_stored(vec_db, "Doc")) == 120

    def test_a_column_of_numpy_rows_is_no_longer_a_type_error(self, vec_db):
        x = _doubles(10).astype(np.float32)
        vec_db.insert_columns(
            "Doc", {"id": np.arange(10), "embedding": [x[i] for i in range(10)]}
        )
        assert len(_stored(vec_db, "Doc")) == 10

    def test_other_two_dimensional_columns_are_refused(self, vec_db):
        with pytest.raises(ValueError, match="one-dimensional"):
            vec_db.insert_columns(
                "Doc", {"id": np.arange(N), "embedding": _doubles()}
            )  # float64
        with pytest.raises(ValueError, match="one-dimensional"):
            vec_db.insert_columns(
                "Doc",
                {"id": np.arange(N), "embedding": np.zeros((N, 0), dtype=np.float32)},
            )
        assert (
            vec_db.query("sql", "SELECT count(*) AS c FROM Doc").first().get("c") == 0
        )

    def test_a_row_count_that_differs_is_refused_before_anything_is_written(
        self, vec_db
    ):
        with pytest.raises(ValueError, match="differ in length"):
            vec_db.insert_columns(
                "Doc",
                {"id": np.arange(N + 1), "embedding": _doubles().astype(np.float32)},
            )
        assert (
            vec_db.query("sql", "SELECT count(*) AS c FROM Doc").first().get("c") == 0
        )


class TestCreateVertices:
    def _ids(self, db, type_name="Vx"):
        query = f"SELECT id, embedding FROM {type_name}"  # nosec B608 - test-owned type name
        return {
            r["id"]: np.array(r["embedding"], dtype=np.float64)
            for r in db.query("sql", query).to_list()
        }

    def test_list_vectors(self, vec_db):
        x = _doubles()
        with vec_db.graph_batch() as gb:
            rids = gb.create_vertices("Vx", _rows(x))
        assert len(rids) == N and len(set(rids)) == N
        _assert_float32_of(self._ids(vec_db), x)
        # the RIDs come back in row order
        for i in (0, 17, N - 1):
            query = f"SELECT id FROM {rids[i]}"  # nosec B608 - a RID from this test
            assert vec_db.query("sql", query).first().get("id") == i

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_numpy_rows(self, vec_db, dtype):
        x = _doubles()
        with vec_db.graph_batch() as gb:
            gb.create_vertices(
                "Vx", [{"id": i, "embedding": x[i].astype(dtype)} for i in range(N)]
            )
        _assert_float32_of(self._ids(vec_db), x)

    def test_one_value_json_cannot_carry_sends_only_its_chunk_the_typed_way(
        self, vec_db
    ):
        vec_db.command("sql", "CREATE PROPERTY Vx.born DATETIME")
        x = _doubles(10)
        rows = _rows(x)
        rows[4]["born"] = datetime(2020, 1, 2, 3, 4, 5)
        with vec_db.graph_batch() as gb:
            rids = gb.create_vertices("Vx", rows)
        assert len(rids) == 10
        _assert_float32_of(self._ids(vec_db), x)
        assert vec_db.query("sql", "SELECT born FROM Vx WHERE id = 4").first().get(
            "born"
        ) == datetime(2020, 1, 2, 3, 4, 5)

    def test_rows_with_no_properties_and_none_rows(self, vec_db):
        with vec_db.graph_batch() as gb:
            assert len(gb.create_vertices("Vx", [None, {}, {"id": 5}])) == 3
        assert vec_db.query("sql", "SELECT count(*) AS c FROM Vx").first().get("c") == 3

    def test_an_empty_list(self, vec_db):
        with vec_db.graph_batch() as gb:
            assert gb.create_vertices("Vx", []) == []


class TestDocumentSet:
    @pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int64])
    def test_a_numpy_array_is_a_property_value(self, vec_db, dtype):
        v = (_doubles(1)[0] * 10).astype(dtype)
        with vec_db.transaction():
            vec_db.new_document("Doc").set("id", 1).set("embedding", v).save()
        got = _stored(vec_db, "Doc")[1]
        assert np.array_equal(got, v.astype(np.float32).astype(np.float64))

    def test_convert_python_to_java_float32_is_one_float_array(self, vec_db):
        v = np.arange(DIM, dtype=np.float32)
        java = type_conversion.convert_python_to_java(v)
        assert str(java.getClass().getName()) == "[F"
        assert list(java) == list(v)


class TestAllowedRids:
    def _index(self, db):
        x = _doubles(40)
        with db.graph_batch() as gb:
            gb.create_vertices("Vx", _rows(x))
        db.command(
            "sql",
            "CREATE INDEX ON Vx (embedding) LSM_VECTOR METADATA "
            + '{"dimensions": %d, "similarity": "EUCLIDEAN"}' % DIM,
        )
        rids = {
            r["id"]: str(r["rid"])
            for r in db.query("sql", "SELECT id, @rid AS rid FROM Vx").to_list()
        }
        return db.schema.get_vector_index("Vx", "embedding"), x, rids

    def test_the_set_holds_one_rid_per_string(self, vec_db):
        index, _x, rids = self._index(vec_db)
        s = index._build_allowed_rids_set(
            list(rids.values())[:7] + [list(rids.values())[0]]
        )
        assert int(s.size()) == 7
        assert all(str(r) in set(rids.values()) for r in s)

    def test_text_rids_restrict_the_search(self, vec_db):
        index, x, rids = self._index(vec_db)
        allowed = [rids[i] for i in (3, 11, 25)]
        hits = index.find_nearest(x[11].astype(np.float32), k=5, allowed_rids=allowed)
        assert {str(h[0].get_rid()) for h in hits} <= set(allowed)
        assert str(hits[0][0].get_rid()) == rids[11]

    def test_rid_objects_and_text_mixed_still_work(self, vec_db):
        index, x, rids = self._index(vec_db)
        java_rid = vec_db.to_java_rid(rids[11])
        s = index._build_allowed_rids_set([java_rid, rids[3]])
        assert int(s.size()) == 2
