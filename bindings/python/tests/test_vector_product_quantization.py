"""
PRODUCT (PQ) vector quantization after ArcadeData/arcadedb#10545 (issue #10514).

A PRODUCT index walks its graph on the in-memory PQ codes and re-ranks the best
`k * rerankOversample` candidates on the stored vectors. The vector guide's "Product
quantization in SQL" section shows the statements these tests run: the
`CREATE INDEX ... METADATA` settings (`rerankOversample`, `fusedPQ`, `pqTrainingLimit`)
and the per-query `rerank` option of `vectorNeighbors`. They fail on the 26.10.2 wheel,
which has neither the settings nor the option, and pass on the engine the suite builds
against.
"""

import arcadedb_embedded as arcadedb
import numpy as np
import pytest
from arcadedb_embedded import create_database

DIMS = 32
COUNT = 2000
K = 10


@pytest.fixture
def test_db(tmp_path):
    db = create_database(str(tmp_path / "test_vector_pq_db"))
    yield db
    db.drop()


@pytest.fixture(scope="module")
def corpus():
    rng = np.random.default_rng(7)
    vectors = rng.standard_normal((COUNT, DIMS)).astype(np.float32)
    queries = rng.standard_normal((20, DIMS)).astype(np.float32)
    return vectors, queries


def _exact_neighbors(vectors, query, k=K):
    distances = ((vectors - query) ** 2).sum(axis=1)
    order = np.argsort(distances)[:k]
    return [int(i) for i in order], distances


def _make_index(db, vectors, metadata=""):
    """The statement the guide shows, on a corpus big enough to train 64 clusters."""
    db.command("sql", "CREATE DOCUMENT TYPE PqDoc")
    db.command("sql", "CREATE PROPERTY PqDoc.id INTEGER")
    db.command("sql", "CREATE PROPERTY PqDoc.embedding ARRAY_OF_FLOATS")
    db.command(
        "sql",
        "CREATE INDEX ON PqDoc (embedding) LSM_VECTOR METADATA "
        f'{{"dimensions": {DIMS}, "similarity": "EUCLIDEAN", '
        '"quantization": "PRODUCT", "pqSubspaces": 8, "pqClusters": 64'
        f"{metadata}}}",
    )
    with db.transaction():
        for i, vec in enumerate(vectors):
            db.command(
                "sql",
                "INSERT INTO PqDoc SET id = ?, embedding = ?",
                i,
                arcadedb.to_java_float_array(vec.tolist()),
            )
    _build(db)


def _build(db):
    """Searches before the graph exists are answered exactly from the delta scan."""
    db.schema.get_vector_index("PqDoc", "embedding").build_graph_now()


def _search(db, query, options="{ efSearch: 100 }", k=K):
    return db.query(
        "sql",
        "SELECT id, distance FROM "  # nosec B608 - test-owned option literals
        f"(SELECT expand(vectorNeighbors('PqDoc[embedding]', ?, {k}, {options})))",  # nosec B608
        arcadedb.to_java_float_array(query.tolist()),
    ).to_list()


def _metadata(db):
    index = db.schema.get_index_by_name("PqDoc[embedding]")
    if "TypeIndex" in index.getClass().getName():
        index = index.getSubIndexes().get(0)
    return index.getMetadata()


def _recall(db, vectors, queries, options):
    hits = 0
    for query in queries:
        wanted, _ = _exact_neighbors(vectors, query)
        found = [r["id"] for r in _search(db, query, options)]
        hits += len(set(wanted) & set(found))
    return hits / (K * len(queries))


class TestProductQuantizationSql:
    def test_index_settings_reach_the_index(self, test_db, corpus):
        vectors, _ = corpus
        _make_index(
            test_db,
            vectors,
            ', "rerankOversample": 30, "pqTrainingLimit": 1500, "fusedPQ": false',
        )

        meta = _metadata(test_db)

        assert str(meta.quantizationType) == "PRODUCT"
        assert int(meta.rerankOversample) == 30
        assert int(meta.pqTrainingLimit) == 1500
        assert bool(meta.fusedPQ) is False
        assert int(meta.pqSubspaces) == 8
        assert int(meta.pqClusters) == 64

    def test_rerank_oversample_defaults_to_ten_and_fused_pq_to_off(
        self, test_db, corpus
    ):
        _make_index(test_db, corpus[0])

        meta = _metadata(test_db)

        assert int(meta.rerankOversample) == 10
        assert bool(meta.fusedPQ) is False

    def test_negative_rerank_oversample_is_refused(self, test_db):
        test_db.command("sql", "CREATE DOCUMENT TYPE PqDoc")
        test_db.command("sql", "CREATE PROPERTY PqDoc.embedding ARRAY_OF_FLOATS")

        with pytest.raises(Exception, match="rerankOversample must be at least 0"):
            test_db.command(
                "sql",
                "CREATE INDEX ON PqDoc (embedding) LSM_VECTOR METADATA "
                f'{{"dimensions": {DIMS}, "quantization": "PRODUCT", '
                '"rerankOversample": -1}',
            )

    def test_default_search_returns_exact_distances_and_good_recall(
        self, test_db, corpus
    ):
        vectors, queries = corpus
        _make_index(test_db, vectors)

        for query in queries[:5]:
            _, exact = _exact_neighbors(vectors, query)
            rows = _search(test_db, query)
            assert len(rows) == K
            for row in rows:
                assert row["distance"] == pytest.approx(
                    float(exact[row["id"]]), rel=1e-4
                )

        assert _recall(test_db, vectors, queries, "{ efSearch: 100 }") >= 0.9

    def test_rerank_zero_returns_pq_estimates_with_lower_recall(self, test_db, corpus):
        vectors, queries = corpus
        _make_index(test_db, vectors)

        reranked = _recall(test_db, vectors, queries, "{ efSearch: 100 }")
        pq_only = _recall(test_db, vectors, queries, "{ efSearch: 100, rerank: 0 }")
        assert pq_only < reranked

        # the distances are PQ estimates, not the exact ones
        _, exact = _exact_neighbors(vectors, queries[0])
        rows = _search(test_db, queries[0], "{ efSearch: 100, rerank: 0 }")
        assert any(
            row["distance"] != pytest.approx(float(exact[row["id"]]), rel=1e-4)
            for row in rows
        )

    def test_negative_rerank_option_is_refused(self, test_db, corpus):
        _make_index(test_db, corpus[0])

        with pytest.raises(Exception, match="rerank must be >= 0"):
            _search(test_db, corpus[1][0], "{ rerank: -1 }")

    def test_fused_pq_index_returns_k_results(self, test_db, corpus):
        vectors, queries = corpus
        test_db.command("sql", "CREATE DOCUMENT TYPE PqDoc")
        test_db.command("sql", "CREATE PROPERTY PqDoc.id INTEGER")
        test_db.command("sql", "CREATE PROPERTY PqDoc.embedding ARRAY_OF_FLOATS")
        test_db.command(
            "sql",
            "CREATE INDEX ON PqDoc (embedding) LSM_VECTOR METADATA "
            f'{{"dimensions": {DIMS}, "similarity": "EUCLIDEAN", '
            '"quantization": "PRODUCT", "pqSubspaces": 8, "pqClusters": 256, '
            '"fusedPQ": true}',
        )
        with test_db.transaction():
            for i, vec in enumerate(vectors):
                test_db.command(
                    "sql",
                    "INSERT INTO PqDoc SET id = ?, embedding = ?",
                    i,
                    arcadedb.to_java_float_array(vec.tolist()),
                )

        _build(test_db)

        assert bool(_metadata(test_db).fusedPQ) is True
        assert len(_search(test_db, queries[0])) == K


class TestProductQuantizationHelpers:
    def test_find_nearest_answers_like_sql_on_a_product_index(self, test_db, corpus):
        """With rerankOversample 0 both return the PQ scores; the exact walk would not."""
        vectors, queries = corpus
        _make_index(test_db, vectors, ', "rerankOversample": 0')
        index = test_db.schema.get_vector_index("PqDoc", "embedding")
        query = queries[0]

        sql_rows = _search(test_db, query)
        found = index.find_nearest(query, k=K, ef_search=100)

        assert [rec.get("id") for rec, _ in found] == [r["id"] for r in sql_rows]
        assert [score for _, score in found] == pytest.approx(
            [r["distance"] for r in sql_rows]
        )
        _, exact = _exact_neighbors(vectors, query)
        assert any(
            score != pytest.approx(float(exact[rec.get("id")]), rel=1e-4)
            for rec, score in found
        )

    def test_find_nearest_returns_exact_distances_by_default(self, test_db, corpus):
        vectors, queries = corpus
        _make_index(test_db, vectors)
        index = test_db.schema.get_vector_index("PqDoc", "embedding")

        found = index.find_nearest(queries[0], k=K, ef_search=100)

        _, exact = _exact_neighbors(vectors, queries[0])
        assert len(found) == K
        for rec, score in found:
            assert score == pytest.approx(float(exact[rec.get("id")]), rel=1e-4)

    def test_create_vector_index_passes_the_new_settings(self, test_db, corpus):
        vectors, _ = corpus
        test_db.command("sql", "CREATE VERTEX TYPE PqVertex")
        test_db.command("sql", "CREATE PROPERTY PqVertex.embedding ARRAY_OF_FLOATS")
        index = test_db.create_vector_index(
            "PqVertex",
            "embedding",
            dimensions=DIMS,
            distance_function="euclidean",
            quantization="PRODUCT",
            pq_subspaces=8,
            pq_clusters=64,
            rerank_oversample=25,
            fused_pq=False,
        )

        meta = index.get_metadata()

        assert meta["rerank_oversample"] == 25
        assert meta["fused_pq"] is False
        assert meta["pq_subspaces"] == 8

    def test_get_metadata_reports_the_engine_defaults(self, test_db):
        test_db.command("sql", "CREATE VERTEX TYPE PqVertex")
        test_db.command("sql", "CREATE PROPERTY PqVertex.embedding ARRAY_OF_FLOATS")
        index = test_db.create_vector_index(
            "PqVertex", "embedding", dimensions=DIMS, quantization="PRODUCT"
        )

        meta = index.get_metadata()

        assert meta["rerank_oversample"] == 10
        assert meta["fused_pq"] is False

    @pytest.mark.parametrize("setting", ["rerank_oversample", "fused_pq"])
    def test_new_settings_require_product_quantization(self, test_db, setting):
        test_db.command("sql", "CREATE VERTEX TYPE PqVertex")
        test_db.command("sql", "CREATE PROPERTY PqVertex.embedding ARRAY_OF_FLOATS")

        with pytest.raises(arcadedb.ArcadeDBError, match="require quantization"):
            test_db.create_vector_index(
                "PqVertex",
                "embedding",
                dimensions=DIMS,
                quantization="INT8",
                **{setting: 5 if setting == "rerank_oversample" else True},
            )
