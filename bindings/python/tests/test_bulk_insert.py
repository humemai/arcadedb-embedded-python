"""Tests for Database.insert_many and AsyncExecutor.create_record."""

import datetime

import pytest


def _count(db, type_name):
    q = f"SELECT count(*) AS n FROM {type_name}"  # nosec B608 - test-controlled
    return int(db.query("sql", q).to_list()[0]["n"])


class TestInsertMany:
    def test_basic_roundtrip(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Item")
        rows = [{"k": i, "name": f"item_{i}", "price": i * 1.5,
                 "active": i % 2 == 0, "tags": ["a", "b"], "meta": {"x": i}}
                for i in range(500)]
        n = temp_db.insert_many("Item", rows, commit_every=100)
        assert n == 500
        assert _count(temp_db, "Item") == 500
        got = temp_db.query(
            "sql", "SELECT FROM Item WHERE k = 7").to_list()[0]
        assert got["name"] == "item_7"
        assert got["price"] == pytest.approx(10.5)
        assert got["active"] is False
        assert list(got["tags"]) == ["a", "b"]

    def test_null_values(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Nul")
        n = temp_db.insert_many("Nul", [{"a": 1, "b": None}, {"a": None}])
        assert n == 2
        assert _count(temp_db, "Nul") == 2

    def test_empty(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Empty")
        assert temp_db.insert_many("Empty", []) == 0

    def test_parallel(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Par")
        rows = [{"k": i} for i in range(2000)]
        n = temp_db.insert_many("Par", rows, parallel=True)
        assert n == 2000
        assert _count(temp_db, "Par") == 2000

    def test_non_json_fallback(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Dated")
        rows = [{"k": i, "when": datetime.datetime(2026, 7, 25, 12, 0, i)}
                for i in range(3)]
        n = temp_db.insert_many("Dated", rows)
        assert n == 3
        assert _count(temp_db, "Dated") == 3

    def test_inside_open_transaction(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Tx")
        temp_db.begin()
        temp_db.insert_many("Tx", [{"k": 1}, {"k": 2}], commit_every=0)
        temp_db.commit()
        assert _count(temp_db, "Tx") == 2


class TestAsyncCreateRecord:
    def test_create_and_wait(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE ARec")
        ex = temp_db.async_executor()
        for i in range(100):
            doc = temp_db.new_document("ARec")
            doc.set("k", i)
            ex.create_record(doc)
        ex.wait_completion()
        assert _count(temp_db, "ARec") == 100

    def test_callback(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE CRec")
        seen = []
        ex = temp_db.async_executor()
        doc = temp_db.new_document("CRec")
        doc.set("k", 1)
        ex.create_record(doc, callback=lambda rec: seen.append(rec))
        ex.wait_completion()
        assert _count(temp_db, "CRec") == 1
        assert len(seen) == 1


class TestVectorColumns:
    """f4v/f8v columnar export: embedding columns as 2-D numpy arrays."""

    def test_float_array_column_to_columns(self, temp_db):
        import numpy as np
        import arcadedb_embedded as arcadedb

        temp_db.command("sql", "CREATE DOCUMENT TYPE Emb")
        temp_db.command("sql", "CREATE PROPERTY Emb.vid INTEGER")
        temp_db.command("sql", "CREATE PROPERTY Emb.v ARRAY_OF_FLOATS")
        with temp_db.transaction():
            for i in range(50):
                temp_db.command(
                    "sql", "INSERT INTO Emb SET vid = :i, v = :v",
                    {"i": i,
                     "v": arcadedb.to_java_float_array([i, i + 0.5, i + 0.25])})
        cols = temp_db.query("sql", "SELECT vid, v FROM Emb ORDER BY vid"
                             ).to_columns()
        assert cols is not None
        arr = cols["v"]
        assert isinstance(arr, np.ndarray) and arr.shape == (50, 3)
        assert arr[10][1] == np.float32(10.5)


class TestAppendSamplesNumpy:
    def test_numpy_columns(self, temp_db):
        import numpy as np

        temp_db.command(
            "sql",
            "CREATE TIMESERIES TYPE NpTs TIMESTAMP ts "
            "TAGS (host STRING) FIELDS (val DOUBLE) SHARDS 2")
        n = 10_000
        ts = np.arange(n, dtype=np.int64) * 1000
        vals = np.linspace(0.0, 1.0, n)
        hosts = [f"h{i % 4}" for i in range(n)]
        ex = temp_db.async_executor()
        ex.append_samples("NpTs", ts, hosts, vals)
        ex.wait_completion()
        got = temp_db.query(
            "sql", "SELECT count(*) AS n FROM NpTs").to_list()[0]["n"]
        assert int(got) == n

    def test_primitive_batch_matches_object_path(self, temp_db):
        """primitive=True must store exactly what the Object[] path stores.

        The primitive path exists to skip boxing (engine issue #5474), so the
        only thing that makes it worth having is that the samples it writes are
        indistinguishable from the path it replaces.
        """
        import numpy as np

        for type_name in ("PrimA", "PrimB"):
            temp_db.command(
                "sql",
                f"CREATE TIMESERIES TYPE {type_name} TIMESTAMP ts "
                "TAGS (host STRING) FIELDS (val DOUBLE, cnt LONG) SHARDS 2")

        n = 5_000
        ts = np.arange(n, dtype=np.int64) * 1000 + 1_700_000_000_000
        vals = np.linspace(-5.0, 5.0, n)
        cnts = np.arange(n, dtype=np.int64) % 7
        hosts = [f"h{i % 4}" for i in range(n)]

        ex = temp_db.async_executor()
        ex.append_samples("PrimA", ts, hosts, vals, cnts)
        ex.append_samples("PrimB", ts, hosts, vals, cnts, primitive=True)
        ex.wait_completion()

        def rows(type_name):
            return temp_db.query(
                "sql",
                f"SELECT ts, host, val, cnt FROM {type_name} WHERE host = 'h2' "
                f"AND ts BETWEEN {int(ts[0])} AND {int(ts[0]) + 200_000} "
                "ORDER BY ts",  # nosec B608 - test-owned type name
            ).to_list()

        boxed, primitive = rows("PrimA"), rows("PrimB")
        assert len(boxed) == len(primitive) and len(boxed) > 0
        for row_boxed, row_primitive in zip(boxed, primitive):
            for key in ("ts", "host", "val", "cnt"):
                assert row_boxed.get(key) == row_primitive.get(key), key

        counts = [
            int(temp_db.query(
                "sql",
                f"SELECT count(*) AS n FROM {t}",  # nosec B608 - test-owned type name
            ).to_list()[0]["n"])
            for t in ("PrimA", "PrimB")
        ]
        assert counts == [n, n]

    def test_primitive_batch_accepts_plain_sequences(self, temp_db):
        """Lists, not just ndarrays: the batch path types each column itself."""
        temp_db.command(
            "sql",
            "CREATE TIMESERIES TYPE PrimList TIMESTAMP ts "
            "TAGS (host STRING) FIELDS (val DOUBLE) SHARDS 1")
        n = 500
        ex = temp_db.async_executor()
        ex.append_samples(
            "PrimList",
            [1_700_000_000_000 + i * 1000 for i in range(n)],
            [f"h{i % 3}" for i in range(n)],
            [float(i) / 4 for i in range(n)],
            primitive=True,
        )
        ex.wait_completion()
        got = temp_db.query(
            "sql", "SELECT count(*) AS n FROM PrimList").to_list()[0]["n"]
        assert int(got) == n


class TestVectorColumnsDataFrame:
    def test_vector_column_to_dataframe(self, temp_db):
        import arcadedb_embedded as arcadedb

        pd = __import__("pytest").importorskip("pandas")
        temp_db.command("sql", "CREATE DOCUMENT TYPE EmbDf")
        temp_db.command("sql", "CREATE PROPERTY EmbDf.v ARRAY_OF_FLOATS")
        with temp_db.transaction():
            for i in range(10):
                temp_db.command(
                    "sql", "INSERT INTO EmbDf SET v = :v",
                    {"v": arcadedb.to_java_float_array([i, i + 1.0])})
        df = temp_db.query("sql", "SELECT v FROM EmbDf").to_dataframe()
        assert len(df) == 10
        assert len(df["v"].iloc[3]) == 2
