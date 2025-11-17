"""
Tests for Vector Index functionality.

Tests cover:
- Vector conversion utilities (to_java_float_array, to_python_array)
- VectorIndex operations (add_vertex, find_nearest)
- VectorIndex capacity management (get_max_capacity, get_size, get_stats, is_full)
- End-to-end vector search scenarios
"""

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import PropertyType, create_database


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test_vector_db")
    db = create_database(db_path)
    yield db
    db.drop()


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path (for compatibility with test_vector_search)."""
    return str(tmp_path / "test_vector_search_db")


class TestVectorConversion:
    """Test vector conversion utility functions."""

    def test_to_java_float_array_from_list(self, test_db):
        """Test converting Python list to Java float array."""
        vector = [0.1, 0.2, 0.3, 0.4]
        java_array = arcadedb.to_java_float_array(vector)

        # Verify conversion
        assert java_array is not None
        assert len(java_array) == 4
        assert abs(java_array[0] - 0.1) < 0.001
        assert abs(java_array[3] - 0.4) < 0.001

    def test_to_java_float_array_from_numpy(self, test_db):
        """Test converting NumPy array to Java float array."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy not available")

        vector = np.array([0.5, 0.6, 0.7, 0.8])
        java_array = arcadedb.to_java_float_array(vector)

        assert java_array is not None
        assert len(java_array) == 4
        assert abs(java_array[0] - 0.5) < 0.001
        assert abs(java_array[3] - 0.8) < 0.001

    def test_to_python_array_as_list(self, test_db):
        """Test converting Java array to Python list."""
        # Create Java array first
        vector = [1.0, 2.0, 3.0]
        java_array = arcadedb.to_java_float_array(vector)

        # Convert back to Python list
        py_list = arcadedb.to_python_array(java_array, use_numpy=False)

        assert isinstance(py_list, list)
        assert len(py_list) == 3
        assert abs(py_list[0] - 1.0) < 0.001
        assert abs(py_list[2] - 3.0) < 0.001

    def test_to_python_array_as_numpy(self, test_db):
        """Test converting Java array to NumPy array."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy not available")

        # Create Java array first
        vector = [1.0, 2.0, 3.0]
        java_array = arcadedb.to_java_float_array(vector)

        # Convert to NumPy array
        np_array = arcadedb.to_python_array(java_array, use_numpy=True)

        assert isinstance(np_array, np.ndarray)
        assert np_array.shape == (3,)
        assert abs(np_array[0] - 1.0) < 0.001
        assert abs(np_array[2] - 3.0) < 0.001


class TestVectorIndexCapacity:
    """Test VectorIndex capacity management methods."""

    def test_vector_index_get_max_capacity(self, test_db):
        """Test get_max_capacity returns the max_items parameter."""
        try:
            import numpy as np  # noqa: F401
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        # Create vector index with known capacity
        schema.create_vertex_type("CapacityTest")
        schema.create_property("CapacityTest", "embedding", "ARRAY_OF_FLOATS")

        max_capacity = 500
        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="CapacityTest",
                vector_property="embedding",
                dimensions=4,
                max_items=max_capacity,
                id_property="vector_id",
                distance_function="cosine",
            )

        # Test get_max_capacity
        assert index.get_max_capacity() == max_capacity

    def test_vector_index_get_size_empty(self, test_db):
        """Test get_size returns 0 for empty index."""
        try:
            import numpy as np  # noqa: F401
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        schema.create_vertex_type("SizeTest")
        schema.create_property("SizeTest", "embedding", "ARRAY_OF_FLOATS")

        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="SizeTest",
                vector_property="embedding",
                dimensions=4,
                max_items=100,
                id_property="vector_id",
                distance_function="cosine",
            )

        # Empty index should have size 0
        assert index.get_size() == 0

    def test_vector_index_get_size_with_items(self, test_db):
        """Test get_size returns correct count after adding items."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        schema.create_vertex_type("SizeTest2")
        schema.create_property("SizeTest2", "embedding", "ARRAY_OF_FLOATS")
        schema.create_property("SizeTest2", "vector_id", PropertyType.STRING)

        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="SizeTest2",
                vector_property="embedding",
                dimensions=4,
                max_items=100,
                id_property="vector_id",
                distance_function="cosine",
            )

            # Add 3 vertices
            for i in range(3):
                vertex = test_db._java_db.newVertex("SizeTest2")
                vector = np.array([0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i])
                vertex.set("embedding", arcadedb.to_java_float_array(vector))
                vertex.set("vector_id", f"vec_{i}")
                vertex.save()
                index.add_vertex(vertex)

        # Should have 3 items
        assert index.get_size() == 3

    def test_vector_index_get_stats(self, test_db):
        """Test get_stats returns correct statistics."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        schema.create_vertex_type("StatsTest")
        schema.create_property("StatsTest", "embedding", "ARRAY_OF_FLOATS")
        schema.create_property("StatsTest", "vector_id", PropertyType.STRING)

        max_capacity = 10
        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="StatsTest",
                vector_property="embedding",
                dimensions=4,
                max_items=max_capacity,
                id_property="vector_id",
                distance_function="cosine",
            )

            # Add 3 items (30% capacity)
            for i in range(3):
                vertex = test_db._java_db.newVertex("StatsTest")
                vector = np.array([0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i])
                vertex.set("embedding", arcadedb.to_java_float_array(vector))
                vertex.set("vector_id", f"stats_vec_{i}")
                vertex.save()
                index.add_vertex(vertex)

        stats = index.get_stats()

        # Verify stats structure
        assert isinstance(stats, dict)
        assert "size" in stats
        assert "max_capacity" in stats
        assert "usage_percent" in stats
        assert "remaining" in stats

        # Verify values
        assert stats["size"] == 3
        assert stats["max_capacity"] == max_capacity
        assert stats["usage_percent"] == 30.0
        assert stats["remaining"] == 7

    def test_vector_index_is_full(self, test_db):
        """Test is_full correctly identifies when index is at capacity."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        schema.create_vertex_type("FullTest")
        schema.create_property("FullTest", "embedding", "ARRAY_OF_FLOATS")
        schema.create_property("FullTest", "vector_id", PropertyType.STRING)

        # Create very small index
        max_capacity = 2
        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="FullTest",
                vector_property="embedding",
                dimensions=4,
                max_items=max_capacity,
                id_property="vector_id",
                distance_function="cosine",
            )

            # Should not be full initially
            assert not index.is_full()

            # Add first item
            vertex1 = test_db._java_db.newVertex("FullTest")
            vertex1.set(
                "embedding",
                arcadedb.to_java_float_array(np.array([0.1, 0.2, 0.3, 0.4])),
            )
            vertex1.set("vector_id", "full_vec_1")
            vertex1.save()
            index.add_vertex(vertex1)

            assert not index.is_full()  # Still room for 1 more

            # Add second item (fills to capacity)
            vertex2 = test_db._java_db.newVertex("FullTest")
            vertex2.set(
                "embedding",
                arcadedb.to_java_float_array(np.array([0.5, 0.6, 0.7, 0.8])),
            )
            vertex2.set("vector_id", "full_vec_2")
            vertex2.save()
            index.add_vertex(vertex2)

            # Now should be full
            assert index.is_full()

    def test_vector_index_stats_empty_index(self, test_db):
        """Test get_stats handles empty index correctly."""
        try:
            import numpy as np  # noqa: F401
        except ImportError:
            pytest.skip("NumPy not available for vector index test")

        schema = test_db.schema

        schema.create_vertex_type("EmptyStats")
        schema.create_property("EmptyStats", "embedding", "ARRAY_OF_FLOATS")

        with test_db.transaction():
            index = test_db.create_vector_index(
                vertex_type="EmptyStats",
                vector_property="embedding",
                dimensions=4,
                max_items=100,
                id_property="vector_id",
                distance_function="cosine",
            )

        stats = index.get_stats()

        assert stats["size"] == 0
        assert stats["max_capacity"] == 100
        assert stats["usage_percent"] == 0.0
        assert stats["remaining"] == 100


def test_vector_search(temp_db_path):
    """Test vector embeddings with HNSW similarity search.

    This test creates an HNSW vector index using the simplified Python API
    to enable nearest-neighbor similarity search on vector embeddings.
    Works with NumPy arrays (preferred) or plain Python lists.
    """
    # Try to use NumPy if available
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        # Create vertex type for vector embeddings
        with db.transaction():
            db.schema.create_vertex_type("EmbeddingNode")
            db.schema.create_property("EmbeddingNode", "name", "STRING")
            # Use ARRAY_OF_FLOATS for vector property (required for HNSW)
            db.schema.create_property("EmbeddingNode", "vector", "ARRAY_OF_FLOATS")

        # Create index in separate transaction (indexes need committed schema)
        with db.transaction():
            db.schema.create_index("EmbeddingNode", ["name"], unique=True)

        # Insert sample word embeddings (4-dimensional for simplicity)
        # In reality, embeddings would be 300-1536 dimensions
        if use_numpy:
            embeddings = [
                ("king", np.array([0.5, 0.3, 0.1, 0.2])),
                ("queen", np.array([0.52, 0.32, 0.08, 0.18])),  # Similar to king
                ("man", np.array([0.48, 0.25, 0.15, 0.22])),
                ("woman", np.array([0.50, 0.28, 0.12, 0.20])),
                ("cat", np.array([0.1, 0.8, 0.6, 0.3])),  # Different cluster
                ("dog", np.array([0.12, 0.82, 0.58, 0.32])),  # Similar to cat
            ]
        else:
            embeddings = [
                ("king", [0.5, 0.3, 0.1, 0.2]),
                ("queen", [0.52, 0.32, 0.08, 0.18]),  # Similar to king
                ("man", [0.48, 0.25, 0.15, 0.22]),
                ("woman", [0.50, 0.28, 0.12, 0.20]),
                ("cat", [0.1, 0.8, 0.6, 0.3]),  # Different cluster
                ("dog", [0.12, 0.82, 0.58, 0.32]),  # Similar to cat
            ]

        with db.transaction():
            for name, vector in embeddings:
                # Use the helper function to convert to Java array
                java_vector = arcadedb.to_java_float_array(vector)

                # Create vertex with Java array as vector property
                java_db = db._java_db
                vertex = java_db.newVertex("EmbeddingNode")
                vertex.set("name", name)
                vertex.set("vector", java_vector)
                vertex.save()

        # Test 1: Verify we can query and retrieve stored vectors
        result = db.query("sql", "SELECT FROM EmbeddingNode WHERE name = 'king'")
        records = list(result)
        assert len(records) == 1

        king_node = records[0]
        assert king_node.has_property("vector")
        assert king_node.has_property("name")
        assert king_node.get_property("name") == "king"

        vector = king_node.get_property("vector")
        # Convert to Python/NumPy array
        vector = arcadedb.to_python_array(vector, use_numpy=use_numpy)

        if use_numpy:
            assert isinstance(vector, np.ndarray)
            assert vector.shape == (4,)
        else:
            assert isinstance(vector, list)
            assert len(vector) == 4

        assert abs(vector[0] - 0.5) < 0.01  # Verify first component

        # Test 2: Create HNSW vector index using simplified API
        print("\nCreating HNSW vector index...")

        # Create index with simplified API
        with db.transaction():
            index = db.create_vector_index(
                vertex_type="EmbeddingNode",
                vector_property="vector",
                dimensions=4,
                id_property="name",  # Use name as ID
                distance_function="cosine",
                m=16,
                ef=128,
                max_items=1000,
            )

        print("  ✓ Created vector index")

        # Index existing vertices
        print("  Indexing existing vertices...")
        result = db.query("sql", "SELECT FROM EmbeddingNode")
        indexed_count = 0

        with db.transaction():
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)
                indexed_count += 1

        print(f"  ✓ Indexed {indexed_count} vertices")

        # Test 3: Perform similarity search with NumPy/list arrays
        print("\nTesting nearest-neighbor similarity search...")

        # Search for neighbors of "king" - should find "queen", "man", "woman"
        if use_numpy:
            king_vector = np.array([0.5, 0.3, 0.1, 0.2])
        else:
            king_vector = [0.5, 0.3, 0.1, 0.2]

        neighbors = index.find_nearest(king_vector, k=3)

        # Extract names from results
        neighbor_names = [str(vertex.get("name")) for vertex, distance in neighbors]

        print(f"  3 nearest neighbors to 'king': {neighbor_names}")
        assert "queen" in neighbor_names, "Expected 'queen' to be near 'king'"
        assert "man" in neighbor_names or "woman" in neighbor_names
        assert "cat" not in neighbor_names, "'cat' should be in different cluster"
        assert "dog" not in neighbor_names, "'dog' should be in different cluster"
        print("  ✓ Similarity search returns correct neighbors!")

        # Search for neighbors of "cat" - should find "dog"
        if use_numpy:
            cat_vector = np.array([0.1, 0.8, 0.6, 0.3])
        else:
            cat_vector = [0.1, 0.8, 0.6, 0.3]

        neighbors = index.find_nearest(cat_vector, k=2)
        neighbor_names = [str(vertex.get("name")) for vertex, distance in neighbors]

        print(f"  2 nearest neighbors to 'cat': {neighbor_names}")
        assert "dog" in neighbor_names, "Expected 'dog' to be near 'cat'"
        assert "king" not in neighbor_names, "'king' should be in different cluster"
        print("  ✓ Different cluster correctly separated!")

        print("\n✓ HNSW vector index fully functional with NumPy support!")
