"""
Tests for LSM Vector Index functionality.

Tests cover:
- LSMVectorIndex creation
- LSMVectorIndex operations (find_nearest)
"""

import arcadedb_embedded as arcadedb
import pytest
from arcadedb_embedded import create_database


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test_lsm_vector_db")
    db = create_database(db_path)
    yield db
    db.drop()


class TestLSMVectorIndex:
    """Test LSM Vector Index functionality."""

    def test_create_vector_index(self, test_db):
        """Test creating a vector index (JVector implementation)."""
        # Create schema
        test_db.schema.create_vertex_type("Doc")
        test_db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

        # Create vector index
        try:
            index = test_db.create_vector_index("Doc", "embedding", dimensions=3)

            assert index is not None
            # Check if it's the wrapper
            from arcadedb_embedded.vector import VectorIndex

            assert isinstance(index, VectorIndex)

            # Verify it's listed in schema
            indexes = test_db.schema.list_vector_indexes()
            # Check if index name is present (format might vary)
            # LSM indexes often have names like Doc_0_123456
            # But list_vector_indexes should return them.
            # We just check if the list is not empty and contains something that looks like an index
            assert len(indexes) > 0
            # Optionally check if one of them starts with Doc
            found = any(str(idx).startswith("Doc") for idx in indexes)
            assert found, f"No index starting with Doc found in {indexes}"

        except Exception as e:
            pytest.fail(f"Failed to create LSM vector index: {e}")

    def test_lsm_vector_search(self, test_db):
        """Test searching in vector index (JVector implementation)."""
        # Create schema and index
        test_db.schema.create_vertex_type("Doc")
        test_db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

        index = test_db.create_vector_index("Doc", "embedding", dimensions=3)

        # Add some data
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

        with test_db.transaction():
            for i, vec in enumerate(vectors):
                v = test_db.new_vertex("Doc")
                v.set("embedding", arcadedb.to_java_float_array(vec))
                v.save()

        # Search
        query = [0.9, 0.1, 0.0]  # Close to first vector
        results = index.find_nearest(query, k=1)

        assert len(results) == 1
        vertex, distance = results[0]

        # Check if we got the correct vertex (first one)
        # Note: Distance metric depends on default (likely Cosine or Euclidean)
        # For Cosine, distance is 1 - similarity, so close to 0
        # For Euclidean, distance is small

        # Verify the embedding of the result
        res_embedding = arcadedb.to_python_array(vertex.get("embedding"))
        assert abs(res_embedding[0] - 1.0) < 0.001

    def test_get_vector_index_lsm(self, test_db):
        """Test retrieving an existing vector index (JVector implementation)."""
        # Create schema and index
        test_db.schema.create_vertex_type("Doc")
        test_db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

        test_db.create_vector_index("Doc", "embedding", dimensions=3)

        # Retrieve index
        index = test_db.schema.get_vector_index("Doc", "embedding")

        assert index is not None
        from arcadedb_embedded.vector import VectorIndex

        assert isinstance(index, VectorIndex)

    def test_lsm_index_size(self, test_db):
        """Test getting the size of an LSM vector index."""
        test_db.schema.create_vertex_type("Doc")
        test_db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")

        index = test_db.create_vector_index("Doc", "embedding", dimensions=3)

        # Initial size should be 0
        assert index.get_size() == 0

        # Add some data
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]

        with test_db.transaction():
            for vec in vectors:
                v = test_db.new_vertex("Doc")
                v.set("embedding", arcadedb.to_java_float_array(vec))
                v.save()

        # Size should be 2
        assert index.get_size() == 2

    def test_lsm_persistence(self, temp_db_path):
        """Test that LSM index persists across database restarts."""
        import arcadedb_embedded as arcadedb

        # 1. Create DB and Index
        with arcadedb.create_database(temp_db_path) as db:
            db.schema.create_vertex_type("Doc")
            db.schema.create_property("Doc", "embedding", "ARRAY_OF_FLOATS")
            db.create_vector_index("Doc", "embedding", dimensions=3)

            with db.transaction():
                v = db.new_vertex("Doc")
                v.set("embedding", arcadedb.to_java_float_array([1.0, 0.0, 0.0]))
                v.save()

        # 2. Reopen and Verify
        with arcadedb.open_database(temp_db_path) as db:
            index = db.schema.get_vector_index("Doc", "embedding")
            assert index is not None
            assert index.get_size() == 1

            results = index.find_nearest([1.0, 0.0, 0.0], k=1)
            assert len(results) == 1

    def test_lsm_cosine_distance_orthogonal_vectors(self, test_db):
        """Test that orthogonal vectors have cosine distance = 0.5 (JVector)."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTestOrthogonal")
        test_db.schema.create_property("VectorTestOrthogonal", "name", "STRING")
        test_db.schema.create_property(
            "VectorTestOrthogonal", "vector", "ARRAY_OF_FLOATS"
        )

        # Create LSM index
        index = test_db.create_vector_index(
            "VectorTestOrthogonal", "vector", dimensions=2
        )

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

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTestOrthogonal")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        # Query with [1,0] - should find [0,1] with distance ~0.5 (JVector normalized)
        # Note: JVector cosine distance = (1 - cos(theta)) / 2
        # Orthogonal: cos(90) = 0 -> distance = 0.5
        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        # Find the orthogonal vector
        orthogonal = [n for n in neighbors if str(n[0].get("name")) == "y_axis"]
        assert len(orthogonal) == 1, "Should find orthogonal vector"
        distance = orthogonal[0][1]

        print(f"\\n  Orthogonal vectors distance: {distance:.6f} (expected: 0.5)")
        assert (
            abs(distance - 0.5) < 0.01
        ), f"Orthogonal distance should be ~0.5, got {distance}"

    def test_lsm_euclidean_distance(self, test_db):
        """Test Euclidean distance metric (JVector implementation)."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTestEuclidean")
        test_db.schema.create_property("VectorTestEuclidean", "name", "STRING")
        test_db.schema.create_property(
            "VectorTestEuclidean", "vector", "ARRAY_OF_FLOATS"
        )

        # Create LSM index with EUCLIDEAN metric
        index = test_db.create_vector_index(
            "VectorTestEuclidean", "vector", dimensions=2, distance_function="EUCLIDEAN"
        )

        # Create vectors:
        # v1: [0.1, 0.1]
        # v2: [3.1, 4.1] -> Distance to v1 is 5. Squared distance is 25.
        # JVector Euclidean Similarity = 1 / (1 + d^2) = 1 / (1 + 25) = 1/26 ~= 0.038

        vectors = [
            ("origin", [0.1, 0.1]),
            ("point_3_4", [3.1, 4.1]),
        ]

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTestEuclidean")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        # Verify count
        count = test_db.count_type("VectorTestEuclidean")
        print(f"\nTotal vertices in DB: {count}")
        assert count == 2, f"Expected 2 vertices, found {count}"

        # Check index size
        idx_size = index.get_size()
        print(f"Index size: {idx_size}")

        # Query with [0.1, 0.1]
        query = [0.1, 0.1]
        neighbors = index.find_nearest(query, k=2)

        print(f"Neighbors found: {len(neighbors)}")
        for n in neighbors:
            print(f"  - {n[0].get('name')}: {n[1]}")

        # 1. Check exact match (origin)
        # Similarity should be 1.0 (1 / (1 + 0))
        origin = [n for n in neighbors if str(n[0].get("name")) == "origin"]
        assert len(origin) == 1
        assert (
            abs(origin[0][1] - 1.0) < 0.0001
        ), f"Origin similarity should be 1.0, got {origin[0][1]}"

        # 2. Check distant point
        # Similarity should be ~0.03846
        point = [n for n in neighbors if str(n[0].get("name")) == "point_3_4"]
        assert len(point) == 1
        expected_sim = 1.0 / (1.0 + 25.0)
        assert (
            abs(point[0][1] - expected_sim) < 0.0001
        ), f"Point similarity should be {expected_sim}, got {point[0][1]}"

        # 3. Check sorting (Higher score first)
        assert neighbors[0][0].get("name") == "origin", "Best match should be first"
        assert (
            neighbors[1][0].get("name") == "point_3_4"
        ), "Second match should be second"

    def test_lsm_cosine_distance_parallel_vectors(self, test_db):
        """Test that parallel vectors (same direction) have cosine distance = 0.0."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTestParallel")
        test_db.schema.create_property("VectorTestParallel", "name", "STRING")
        test_db.schema.create_property(
            "VectorTestParallel", "vector", "ARRAY_OF_FLOATS"
        )

        index = test_db.create_vector_index(
            "VectorTestParallel", "vector", dimensions=2
        )

        if use_numpy:
            vectors = [
                ("v1", np.array([1.0, 1.0])),
                ("v2", np.array([2.0, 2.0])),
                ("v3", np.array([0.5, 0.5])),
            ]
        else:
            vectors = [
                ("v1", [1.0, 1.0]),
                ("v2", [2.0, 2.0]),
                ("v3", [0.5, 0.5]),
            ]

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTestParallel")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        query = [1.0, 1.0] if not use_numpy else np.array([1.0, 1.0])
        neighbors = index.find_nearest(query, k=3)

        print("\\n  Parallel vectors distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f} (expected: ~0.0)")
            assert (
                distance < 0.01
            ), f"Parallel vector {name} distance should be ~0.0, got {distance}"

    def test_lsm_cosine_distance_opposite_vectors(self, test_db):
        """Test that opposite vectors (180° apart) have cosine distance = 1.0 (JVector)."""
        # Note: JVector cosine distance = (1 - cos(theta)) / 2
        # Opposite: cos(180) = -1 -> distance = (1 - (-1))/2 = 1.0
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTestOpposite")
        test_db.schema.create_property("VectorTestOpposite", "name", "STRING")
        test_db.schema.create_property(
            "VectorTestOpposite", "vector", "ARRAY_OF_FLOATS"
        )

        index = test_db.create_vector_index(
            "VectorTestOpposite", "vector", dimensions=2
        )

        if use_numpy:
            vectors = [
                ("positive", np.array([1.0, 0.0])),
                ("negative", np.array([-1.0, 0.0])),
            ]
        else:
            vectors = [
                ("positive", [1.0, 0.0]),
                ("negative", [-1.0, 0.0]),
            ]

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTestOpposite")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        opposite = [n for n in neighbors if str(n[0].get("name")) == "negative"]
        assert len(opposite) == 1, "Should find opposite vector"
        distance = opposite[0][1]

        print(f"\\n  Opposite vectors distance: {distance:.6f} (expected: 1.0)")
        assert (
            abs(distance - 1.0) < 0.01
        ), f"Opposite distance should be ~1.0, got {distance}"

    def test_lsm_cosine_distance_45_degree_vectors(self, test_db):
        """Test vectors at 45° angle have expected cosine distance."""
        # Note: JVector cosine distance = (1 - cos(theta)) / 2
        # 45 deg: cos(45) = 0.707 -> distance = (1 - 0.707)/2 = 0.146
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTest45")
        test_db.schema.create_property("VectorTest45", "name", "STRING")
        test_db.schema.create_property("VectorTest45", "vector", "ARRAY_OF_FLOATS")

        index = test_db.create_vector_index("VectorTest45", "vector", dimensions=2)

        if use_numpy:
            vectors = [
                ("x_axis", np.array([1.0, 0.0])),
                ("diagonal", np.array([1.0, 1.0])),
            ]
        else:
            vectors = [
                ("x_axis", [1.0, 0.0]),
                ("diagonal", [1.0, 1.0]),
            ]

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTest45")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        query = [1.0, 0.0] if not use_numpy else np.array([1.0, 0.0])
        neighbors = index.find_nearest(query, k=2)

        diagonal = [n for n in neighbors if str(n[0].get("name")) == "diagonal"]
        assert len(diagonal) == 1, "Should find diagonal vector"
        distance = diagonal[0][1]

        expected = (1.0 - (1.0 / (2.0**0.5))) / 2.0
        print(f"\\n  45° vectors distance: {distance:.6f} (expected: {expected:.6f})")
        assert (
            abs(distance - expected) < 0.01
        ), f"45° distance should be ~{expected}, got {distance}"

    def test_lsm_cosine_distance_3d_orthogonal_vectors(self, test_db):
        """Test 3D orthogonal vectors have cosine distance = 1.0."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTest3DOrthogonal")
        test_db.schema.create_property("VectorTest3DOrthogonal", "name", "STRING")
        test_db.schema.create_property(
            "VectorTest3DOrthogonal", "vector", "ARRAY_OF_FLOATS"
        )

        index = test_db.create_vector_index(
            "VectorTest3DOrthogonal", "vector", dimensions=3
        )

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

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTest3DOrthogonal")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        query = [1.0, 0.0, 0.0] if not use_numpy else np.array([1.0, 0.0, 0.0])
        neighbors = index.find_nearest(query, k=3)

        print("\\n  3D orthogonal vectors distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")
            if name != "x_axis":
                assert (
                    abs(distance - 0.5) < 0.01
                ), f"3D orthogonal distance should be ~0.5, got {distance}"

    def test_lsm_cosine_distance_3d_parallel_and_opposite(self, test_db):
        """Test 3D parallel (distance=0) and opposite (distance=1.0) vectors."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        test_db.schema.create_vertex_type("VectorTest3DParallel")
        test_db.schema.create_property("VectorTest3DParallel", "name", "STRING")
        test_db.schema.create_property(
            "VectorTest3DParallel", "vector", "ARRAY_OF_FLOATS"
        )

        index = test_db.create_vector_index(
            "VectorTest3DParallel", "vector", dimensions=3
        )

        if use_numpy:
            vectors = [
                ("v1", np.array([1.0, 1.0, 1.0])),
                ("v2_parallel", np.array([2.0, 2.0, 2.0])),
                ("v3_opposite", np.array([-1.0, -1.0, -1.0])),
            ]
        else:
            vectors = [
                ("v1", [1.0, 1.0, 1.0]),
                ("v2_parallel", [2.0, 2.0, 2.0]),
                ("v3_opposite", [-1.0, -1.0, -1.0]),
            ]

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTest3DParallel")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        query = [1.0, 1.0, 1.0] if not use_numpy else np.array([1.0, 1.0, 1.0])
        neighbors = index.find_nearest(query, k=3)

        print("\\n  3D parallel and opposite vectors:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")

            if "parallel" in name:
                assert (
                    distance < 0.01
                ), f"Parallel should have distance ~0, got {distance}"
            elif "opposite" in name:
                assert (
                    abs(distance - 1.0) < 0.01
                ), f"Opposite should have distance ~1.0, got {distance}"

    def test_lsm_cosine_distance_high_dimensional(self, test_db):
        """Test cosine distance in high dimensions (128D)."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("NumPy required for high-dimensional test")

        test_db.schema.create_vertex_type("VectorTestHD")
        test_db.schema.create_property("VectorTestHD", "name", "STRING")
        test_db.schema.create_property("VectorTestHD", "vector", "ARRAY_OF_FLOATS")

        dim = 128
        np.random.seed(42)

        base = np.random.randn(dim)
        base = base / np.linalg.norm(base)

        parallel = base * 2.5
        opposite = -base

        orthogonal = np.random.randn(dim)
        orthogonal = orthogonal - np.dot(orthogonal, base) * base
        orthogonal = orthogonal / np.linalg.norm(orthogonal)

        vectors = [
            ("base", base),
            ("parallel", parallel),
            ("opposite", opposite),
            ("orthogonal", orthogonal),
        ]

        index = test_db.create_vector_index("VectorTestHD", "vector", dimensions=dim)

        with test_db.transaction():
            for name, vector in vectors:
                vertex = test_db.new_vertex("VectorTestHD")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        neighbors = index.find_nearest(base, k=4)

        print(f"\\n  High-dimensional ({dim}D) cosine distances:")
        for vertex, distance in neighbors:
            name = str(vertex.get("name"))
            print(f"    {name}: {distance:.6f}")

            if name == "parallel":
                assert (
                    distance < 0.01
                ), f"Parallel should have distance ~0, got {distance}"
            elif name == "opposite":
                assert (
                    abs(distance - 1.0) < 0.01
                ), f"Opposite should have distance ~1.0, got {distance}"
            elif name == "orthogonal":
                assert (
                    abs(distance - 0.5) < 0.1
                ), f"Orthogonal should have distance ~0.5, got {distance}"

    def test_lsm_vector_search_comprehensive(self, test_db):
        """Test vector embeddings with LSM similarity search (comprehensive)."""
        try:
            import numpy as np

            use_numpy = True
        except ImportError:
            use_numpy = False

        # Create vertex type for vector embeddings
        test_db.schema.create_vertex_type("EmbeddingNodeLSM")
        test_db.schema.create_property("EmbeddingNodeLSM", "name", "STRING")
        test_db.schema.create_property("EmbeddingNodeLSM", "vector", "ARRAY_OF_FLOATS")

        # Create index
        index = test_db.create_vector_index("EmbeddingNodeLSM", "vector", dimensions=4)

        # Insert sample word embeddings (4-dimensional for simplicity)
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

        with test_db.transaction():
            for name, vector in embeddings:
                vertex = test_db.new_vertex("EmbeddingNodeLSM")
                vertex.set("name", name)
                vertex.set("vector", arcadedb.to_java_float_array(vector))
                vertex.save()

        # Search for neighbors of "king"
        if use_numpy:
            king_vector = np.array([0.5, 0.3, 0.1, 0.2])
        else:
            king_vector = [0.5, 0.3, 0.1, 0.2]

        neighbors = index.find_nearest(king_vector, k=3)
        neighbor_names = [str(vertex.get("name")) for vertex, distance in neighbors]

        print(f"\\n  3 nearest neighbors to 'king': {neighbor_names}")
        assert "queen" in neighbor_names, "Expected 'queen' to be near 'king'"
        assert "man" in neighbor_names or "woman" in neighbor_names
        assert "cat" not in neighbor_names, "'cat' should be in different cluster"
        assert "dog" not in neighbor_names, "'dog' should be in different cluster"

        # Search for neighbors of "cat"
        if use_numpy:
            cat_vector = np.array([0.1, 0.8, 0.6, 0.3])
        else:
            cat_vector = [0.1, 0.8, 0.6, 0.3]

        neighbors = index.find_nearest(cat_vector, k=2)
        neighbor_names = [str(vertex.get("name")) for vertex, distance in neighbors]

        print(f"  2 nearest neighbors to 'cat': {neighbor_names}")
        assert "dog" in neighbor_names, "Expected 'dog' to be near 'cat'"
        assert "king" not in neighbor_names, "'king' should be in different cluster"
