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
        schema = test_db.schema

        # Create vector index with known capacity
        schema.create_vertex_type("CapacityTest")
        schema.create_property("CapacityTest", "embedding", "ARRAY_OF_FLOATS")

        max_capacity = 500
        index = test_db.create_legacy_vector_index(
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
        schema = test_db.schema

        schema.create_vertex_type("SizeTest")
        schema.create_property("SizeTest", "embedding", "ARRAY_OF_FLOATS")

        index = test_db.create_legacy_vector_index(
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

        index = test_db.create_legacy_vector_index(
            vertex_type="SizeTest2",
            vector_property="embedding",
            dimensions=4,
            max_items=100,
            id_property="vector_id",
            distance_function="cosine",
        )

        with test_db.transaction():
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
        schema = test_db.schema

        schema.create_vertex_type("StatsTest")
        schema.create_property("StatsTest", "embedding", "ARRAY_OF_FLOATS")
        schema.create_property("StatsTest", "vector_id", PropertyType.STRING)

        max_capacity = 10
        index = test_db.create_legacy_vector_index(
            vertex_type="StatsTest",
            vector_property="embedding",
            dimensions=4,
            max_items=max_capacity,
            id_property="vector_id",
            distance_function="cosine",
        )

        with test_db.transaction():
            # Add 3 items (30% capacity)
            for i in range(3):
                vertex = test_db._java_db.newVertex("StatsTest")
                vector = [0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i]
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
        schema = test_db.schema

        schema.create_vertex_type("FullTest")
        schema.create_property("FullTest", "embedding", "ARRAY_OF_FLOATS")
        schema.create_property("FullTest", "vector_id", PropertyType.STRING)

        # Create very small index
        max_capacity = 2
        index = test_db.create_legacy_vector_index(
            vertex_type="FullTest",
            vector_property="embedding",
            dimensions=4,
            max_items=max_capacity,
            id_property="vector_id",
            distance_function="cosine",
        )

        with test_db.transaction():
            # Should not be full initially
            assert not index.is_full()

            # Add first item
            vertex1 = test_db._java_db.newVertex("FullTest")
            vertex1.set(
                "embedding",
                arcadedb.to_java_float_array([0.1, 0.2, 0.3, 0.4]),
            )
            vertex1.set("vector_id", "full_vec_1")
            vertex1.save()
            index.add_vertex(vertex1)

            assert not index.is_full()  # Still room for 1 more

            # Add second item (fills to capacity)
            vertex2 = test_db._java_db.newVertex("FullTest")
            vertex2.set(
                "embedding",
                arcadedb.to_java_float_array([0.5, 0.6, 0.7, 0.8]),
            )
            vertex2.set("vector_id", "full_vec_2")
            vertex2.save()
            index.add_vertex(vertex2)

            # Now should be full
            assert index.is_full()

    def test_vector_index_stats_empty_index(self, test_db):
        """Test get_stats handles empty index correctly."""
        schema = test_db.schema

        schema.create_vertex_type("EmptyStats")
        schema.create_property("EmptyStats", "embedding", "ARRAY_OF_FLOATS")

        index = test_db.create_legacy_vector_index(
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


def test_cosine_distance_orthogonal_vectors(temp_db_path):
    """Test that orthogonal vectors have cosine distance = 1.0.

    Orthogonal vectors have cos(θ) = 0, so distance = 1 - 0 = 1.0.
    Uses standard basis vectors [1,0] and [0,1] in 2D.
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest")
            db.schema.create_property("VectorTest", "name", "STRING")
            db.schema.create_property("VectorTest", "vector", "ARRAY_OF_FLOATS")

        # Create orthogonal vectors: [1,0] and [0,1]
        if use_numpy:
            vectors = [
                ("x_axis", np.array([1.0, 0.0])),
                ("y_axis", np.array([0.0, 1.0])),
            ]
        else:
            vectors = [
                ("x_axis", [1.0, 0.0]),
                ("y_axis", [0.0, 1.0]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        index = db.create_legacy_vector_index(
            vertex_type="VectorTest",
            vector_property="vector",
            dimensions=2,
            id_property="name",
            distance_function="cosine",
            max_items=100,
        )

        with db.transaction():
            # Index vertices
            result = db.query("sql", "SELECT FROM VectorTest")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,0] - should find [0,1] with distance ~1.0
        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        # Find the orthogonal vector
        orthogonal = [n for n in neighbors if str(n[0].get("name")) == "y_axis"]
        assert len(orthogonal) == 1, "Should find orthogonal vector"
        distance = orthogonal[0][1]

        print(f"\n  Orthogonal vectors distance: {distance:.6f} (expected: 1.0)")
        assert (
            abs(distance - 1.0) < 0.01
        ), f"Orthogonal distance should be ~1.0, got {distance}"


def test_cosine_distance_parallel_vectors(temp_db_path):
    """Test that parallel vectors (same direction) have cosine distance = 0.0.

    Parallel vectors have cos(θ) = 1, so distance = 1 - 1 = 0.0.
    Tests with same angle but different magnitudes.
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest")
            db.schema.create_property("VectorTest", "name", "STRING")
            db.schema.create_property("VectorTest", "vector", "ARRAY_OF_FLOATS")

        # Create parallel vectors with different magnitudes
        if use_numpy:
            vectors = [
                ("v1", np.array([1.0, 1.0])),
                ("v2", np.array([2.0, 2.0])),  # Same direction, 2x magnitude
                ("v3", np.array([0.5, 0.5])),  # Same direction, 0.5x magnitude
            ]
        else:
            vectors = [
                ("v1", [1.0, 1.0]),
                ("v2", [2.0, 2.0]),
                ("v3", [0.5, 0.5]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        with db.transaction():
            index = db.create_legacy_vector_index(
                vertex_type="VectorTest",
                vector_property="vector",
                dimensions=2,
                id_property="name",
                distance_function="cosine",
                max_items=100,
            )

            result = db.query("sql", "SELECT FROM VectorTest")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,1] - should find all parallel vectors with distance ~0.0
        query = [1.0, 1.0] if not use_numpy else np.array([1.0, 1.0])
        neighbors = index.find_nearest(query, k=3)

        print("\n  Parallel vectors distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f} (expected: ~0.0)")
            assert (
                distance < 0.01
            ), f"Parallel vector {name} distance should be ~0.0, got {distance}"


def test_cosine_distance_opposite_vectors(temp_db_path):
    """Test that opposite vectors (180° apart) have cosine distance = 2.0.

    Opposite vectors have cos(θ) = -1, so distance = 1 - (-1) = 2.0.
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest")
            db.schema.create_property("VectorTest", "name", "STRING")
            db.schema.create_property("VectorTest", "vector", "ARRAY_OF_FLOATS")

        # Create opposite vectors
        if use_numpy:
            vectors = [
                ("positive", np.array([1.0, 0.0])),
                ("negative", np.array([-1.0, 0.0])),  # 180° opposite
            ]
        else:
            vectors = [
                ("positive", [1.0, 0.0]),
                ("negative", [-1.0, 0.0]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        with db.transaction():
            index = db.create_legacy_vector_index(
                vertex_type="VectorTest",
                vector_property="vector",
                dimensions=2,
                id_property="name",
                distance_function="cosine",
                max_items=100,
            )

            result = db.query("sql", "SELECT FROM VectorTest")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,0] - should find [-1,0] with distance ~2.0
        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        opposite = [n for n in neighbors if str(n[0].get("name")) == "negative"]
        assert len(opposite) == 1, "Should find opposite vector"
        distance = opposite[0][1]

        print(f"\n  Opposite vectors distance: {distance:.6f} (expected: 2.0)")
        assert (
            abs(distance - 2.0) < 0.01
        ), f"Opposite distance should be ~2.0, got {distance}"


def test_cosine_distance_45_degree_vectors(temp_db_path):
    """Test vectors at 45° angle have expected cosine distance.

    45° angle: cos(45°) = √2/2 ≈ 0.707, so distance = 1 - 0.707 ≈ 0.293.
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest")
            db.schema.create_property("VectorTest", "name", "STRING")
            db.schema.create_property("VectorTest", "vector", "ARRAY_OF_FLOATS")

        # Create vectors at 45° angle: [1,0] and [1,1]/√2 normalized
        if use_numpy:
            vectors = [
                ("x_axis", np.array([1.0, 0.0])),
                ("diagonal", np.array([1.0, 1.0])),  # 45° from x-axis
            ]
        else:
            vectors = [
                ("x_axis", [1.0, 0.0]),
                ("diagonal", [1.0, 1.0]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        with db.transaction():
            index = db.create_legacy_vector_index(
                vertex_type="VectorTest",
                vector_property="vector",
                dimensions=2,
                id_property="name",
                distance_function="cosine",
                max_items=100,
            )

            result = db.query("sql", "SELECT FROM VectorTest")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,0] - should find [1,1] with distance ~0.293
        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        diagonal = [n for n in neighbors if str(n[0].get("name")) == "diagonal"]
        assert len(diagonal) == 1, "Should find diagonal vector"
        distance = diagonal[0][1]

        expected = 1.0 - (1.0 / (2.0**0.5))  # 1 - cos(45°) ≈ 0.293
        print(f"\n  45° vectors distance: {distance:.6f} (expected: {expected:.6f})")
        assert (
            abs(distance - expected) < 0.01
        ), f"45° distance should be ~{expected}, got {distance}"


def test_cosine_distance_3d_orthogonal_vectors(temp_db_path):
    """Test 3D orthogonal vectors have cosine distance = 1.0.

    Tests standard basis vectors in 3D: [1,0,0], [0,1,0], [0,0,1].
    All pairs should be orthogonal with distance = 1.0.
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest3D")
            db.schema.create_property("VectorTest3D", "name", "STRING")
            db.schema.create_property("VectorTest3D", "vector", "ARRAY_OF_FLOATS")

        # Create 3D orthogonal basis vectors
        if use_numpy:
            vectors = [
                ("x_axis", np.array([1.0, 0.0, 0.0])),
                ("y_axis", np.array([0.0, 1.0, 0.0])),
                ("z_axis", np.array([0.0, 0.0, 1.0])),
            ]
        else:
            vectors = [
                ("x_axis", [1.0, 0.0, 0.0]),
                ("y_axis", [0.0, 1.0, 0.0]),
                ("z_axis", [0.0, 0.0, 1.0]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest3D")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        with db.transaction():
            index = db.create_legacy_vector_index(
                vertex_type="VectorTest3D",
                vector_property="vector",
                dimensions=3,
                id_property="name",
                distance_function="cosine",
                max_items=100,
            )

            result = db.query("sql", "SELECT FROM VectorTest3D")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,0,0] - should find [0,1,0] and [0,0,1] with distance ~1.0
        query = [1.0, 0.0, 0.0] if not use_numpy else np.array([1.0, 0.0, 0.0])
        neighbors = index.find_nearest(query, k=3)

        print("\n  3D orthogonal vectors distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")
            if name != "x_axis":  # Skip self
                assert (
                    abs(distance - 1.0) < 0.01
                ), f"3D orthogonal distance should be ~1.0, got {distance}"


def test_cosine_distance_3d_parallel_and_opposite(temp_db_path):
    """Test 3D parallel (distance=0) and opposite (distance=2) vectors.

    Parallel: [1,1,1] vs [2,2,2] → distance = 0
    Opposite: [1,1,1] vs [-1,-1,-1] → distance = 2
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        use_numpy = False

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTest3D")
            db.schema.create_property("VectorTest3D", "name", "STRING")
            db.schema.create_property("VectorTest3D", "vector", "ARRAY_OF_FLOATS")

        if use_numpy:
            vectors = [
                ("v1", np.array([1.0, 1.0, 1.0])),
                ("v2_parallel", np.array([2.0, 2.0, 2.0])),  # Parallel
                ("v3_opposite", np.array([-1.0, -1.0, -1.0])),  # Opposite
            ]
        else:
            vectors = [
                ("v1", [1.0, 1.0, 1.0]),
                ("v2_parallel", [2.0, 2.0, 2.0]),
                ("v3_opposite", [-1.0, -1.0, -1.0]),
            ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTest3D")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        with db.transaction():
            index = db.create_legacy_vector_index(
                vertex_type="VectorTest3D",
                vector_property="vector",
                dimensions=3,
                id_property="name",
                distance_function="cosine",
                max_items=100,
            )

            result = db.query("sql", "SELECT FROM VectorTest3D")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with [1,1,1]
        query = [1.0, 1.0, 1.0] if not use_numpy else np.array([1.0, 1.0, 1.0])
        neighbors = index.find_nearest(query, k=3)

        print("\n  3D parallel and opposite vectors:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")

            if "parallel" in name:
                assert (
                    distance < 0.01
                ), f"Parallel should have distance ~0, got {distance}"
            elif "opposite" in name:
                assert (
                    abs(distance - 2.0) < 0.01
                ), f"Opposite should have distance ~2, got {distance}"


def test_cosine_distance_high_dimensional(temp_db_path):
    """Test cosine distance in high dimensions (128D, typical for embeddings).

    Tests:
    - Orthogonal random vectors → distance ≈ 1.0
    - Parallel vectors (scaled) → distance ≈ 0.0
    - Opposite vectors → distance ≈ 2.0
    """
    try:
        import numpy as np

        use_numpy = True
    except ImportError:
        pytest.skip("NumPy required for high-dimensional test")

    with arcadedb.create_database(temp_db_path) as db:
        with db.transaction():
            db.schema.create_vertex_type("VectorTestHD")
            db.schema.create_property("VectorTestHD", "name", "STRING")
            db.schema.create_property("VectorTestHD", "vector", "ARRAY_OF_FLOATS")

        # Create high-dimensional test vectors (128D)
        dim = 128
        np.random.seed(42)  # Reproducible

        # Base vector
        base = np.random.randn(dim)
        base = base / np.linalg.norm(base)  # Normalize

        # Parallel vector (same direction, different magnitude)
        parallel = base * 2.5

        # Opposite vector (180° opposite)
        opposite = -base

        # Orthogonal vector (constructed to be perpendicular)
        orthogonal = np.random.randn(dim)
        # Make orthogonal using Gram-Schmidt
        orthogonal = orthogonal - np.dot(orthogonal, base) * base
        orthogonal = orthogonal / np.linalg.norm(orthogonal)

        # Verify orthogonality
        dot_product = np.dot(base, orthogonal)
        assert (
            abs(dot_product) < 0.01
        ), f"Vectors should be orthogonal, dot={dot_product}"

        vectors = [
            ("base", base),
            ("parallel", parallel),
            ("opposite", opposite),
            ("orthogonal", orthogonal),
        ]

        with db.transaction():
            for name, vector in vectors:
                vertex = db._java_db.newVertex("VectorTestHD")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        index = db.create_legacy_vector_index(
            vertex_type="VectorTestHD",
            vector_property="vector",
            dimensions=dim,
            id_property="name",
            distance_function="cosine",
            max_items=100,
        )

        with db.transaction():
            result = db.query("sql", "SELECT FROM VectorTestHD")
            for record in result:
                vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(vertex)

        # Query with base vector
        neighbors = index.find_nearest(base, k=4)

        print(f"\n  High-dimensional ({dim}D) cosine distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")

            if name == "parallel":
                assert (
                    distance < 0.01
                ), f"Parallel should have distance ~0, got {distance}"
            elif name == "opposite":
                assert (
                    abs(distance - 2.0) < 0.01
                ), f"Opposite should have distance ~2, got {distance}"
            elif name == "orthogonal":
                assert (
                    abs(distance - 1.0) < 0.1
                ), f"Orthogonal should have distance ~1, got {distance}"


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
        index = db.create_legacy_vector_index(
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
