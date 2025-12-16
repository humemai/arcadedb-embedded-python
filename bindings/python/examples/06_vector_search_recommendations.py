#!/usr/bin/env python3
"""
Example 06: Vector Search Movie Recommendations

Demonstrates vector embeddings and HNSW indexing for semantic movie search.
Compares traditional graph queries with vector similarity search.

PERFORMANCE OPTIMIZATION
-------------------------
Graph-Based Collaborative Filtering Performance:
• Full mode: Comprehensive but slow (24-39s per query on large dataset)
  - Analyzes all users who rated the query movie highly
  - Processes 100K+ intermediate results from graph traversal fanout
  - Best for offline batch recommendations

• Fast mode: Sampled with 150-300x speedup (0.1-0.2s per query)
  - Limits intermediate results to 25K (approximately 50 users' worth)
  - Uses nested SELECT with LIMIT before GROUP BY aggregation
  - Still produces high-quality recommendations
  - Best for real-time recommendations

For the large dataset (20M ratings), use these environment variables:
  ARCADEDB_JVM_MAX_HEAP="8g" ARCADEDB_JVM_ARGS="-Xms8g"

KNOWN ISSUES: ArcadeDB Bugs and Limitations
--------------------------------------------

1. **NOTUNIQUE Index Breaks String Equality (ArcadeDB Bug)**:
   Creating a NOTUNIQUE index on a string property AFTER loading a large
   dataset (86K+ records) causes the = operator to return 0 results for
   exact string matches, while LIKE continues to work correctly.

   Example:
   - Before index: WHERE title = 'Toy Story (1995)' → 1 result ✓
   - After index:  WHERE title = 'Toy Story (1995)' → 0 results ✗
   - After index:  WHERE title LIKE 'Toy Story (1995)' → 1 result ✓

   WORKAROUND: This script does NOT create a NOTUNIQUE index on Movie.title.
   We use the = operator for exact title matching (works without index) and
   rely on the Movie[movieId] UNIQUE index for fast MATCH traversals.

2. **FULL_TEXT Index Wrong Semantics**:
   FULL_TEXT index changes the = operator to perform tokenized word search
   instead of exact matching, returning semantically incorrect results.

   Example with FULL_TEXT index:
   - WHERE title = 'Toy Story (1995)' → 1,686 results (any movie with
     "Toy", "Story", or "1995" in title) ✗

   CONCLUSION: FULL_TEXT is NOT suitable for exact title matching.

3. **HNSW Metadata Persistence**: Once embeddings and indexes are created,
   they cannot be completely removed and recreated on the same vertices.
   The HNSW graph metadata (edges, vectorMaxLevel property) persists even
   after dropping the index.

   WORKAROUND: Use SEPARATE properties and edge types for each model
   (embedding_v1/embedding_v2 with edge types Movie_v1/Movie_v2).

4. **JSONL Export/Import Broken for Vectors**: Float arrays are NOT properly
   preserved during JSONL export/import:
   - Embeddings exported as Java toString() strings: "[F@113ee1ce"
   - Original vector data (384 floats) is completely lost
   - HNSW index edges are not exported at all

   IMPACT: Cannot backup/restore vector databases using JSONL format.
   After import, embeddings must be regenerated and indexes rebuilt.

Features:
- Real embeddings using sentence-transformers (two models for comparison)
- HNSW vector indexing for fast similarity search
- Compare graph-based vs vector-based recommendations (4 methods)
- Performance timing and optimization strategies

Dataset: MovieLens small (9,742 movies from Example 05)

Usage:
    # Import from JSONL export (recommended)
    python 06_vector_search_recommendations.py \\
        --import-jsonl ./exports/movielens_graph_small_db.jsonl.tgz

    # Use existing database
    python 06_vector_search_recommendations.py \\
        --source-db my_test_databases/movielens_graph_small_db

The default implementation uses JVector (graph index combining HNSW hierarchy
with Vamana/DiskANN). The legacy implementation uses hnswlib (pure HNSW).
JVector is much faster:

small dataset:
```
| Component (Vector-Related Only) | **Default (JVector)**   | **Legacy (HNSWlib)**   | **Difference / Notes**                |
| ------------------------------- | ----------------------- | ---------------------- | ------------------------------------- |
| **Index Build – Model 1**       | **0.1 s**               | **99.5 s**             | Legacy is **~995× slower**            |
| **Index Build – Model 2**       | **0.1 s**               | **93.4 s**             | Same pattern                          |
| **Total Index Build Time**      | **0.2 s**               | **192.9 s**            | Legacy is **~1000× slower overall**   |
| **First Vector Query**          | 1.2–1.6 s (lazy build)  | 0.01–0.02 s            | Default slow only on first query      |
| **Subsequent Vector Queries**   | **0.002–0.004 s**       | **0.01–0.02 s**        | Default slightly faster               |
| **Vector Search Quality**       | ⚠️ Mostly similar       | ⚠️ Mostly similar      | Only distance scaling differs         |
```

large dataset:
```
| Metric                     | **JVector**              | **HNSW (hnswlib)**    |
| -------------------------- | ------------------------ | --------------------- |
| **Index build (2 models)** | **~1.4 s**               | **~3,240 s (54 min)** |
| **First vector query**     | ~13 s (lazy graph build) | ~0.2 s                |
| **Subsequent queries**     | **~0.002–0.003 s**       | ~0.02–0.05 s          |
| **Total vector time**      | **~28 s**                | **~3,241 s**          |
| **Query result match**     | ⚠️ Mostly similar        | ⚠️ Mostly similar     |
```

The default JVector index delivers massive performance gains over hnswlib (≈1000× faster
index build and ~5–20× faster queries on 10k–86k vectors), but it consistently returns
different neighbor sets for the same embeddings and queries. The results remain
semantically reasonable, suggesting a design tradeoff (e.g., lazy graph construction and
different traversal heuristics).

As of 13-Dec-2025, we ran into some issues:

- "Vector search is much faster than hnswlib, but returns different neighbors"
  https://github.com/ArcadeData/arcadedb/issues/2914.

"""

import argparse
import shutil
import sys
import time
from pathlib import Path

import arcadedb_embedded as arcadedb


def check_dependencies():
    """Check required dependencies."""
    try:
        import sentence_transformers

        print(f"✓ sentence-transformers {sentence_transformers.__version__}")
    except ImportError:
        print("ERROR: sentence-transformers not found")
        print("Install: pip install sentence-transformers")
        sys.exit(1)

    try:
        import numpy

        print(f"✓ numpy {numpy.__version__}")
    except ImportError:
        print("ERROR: numpy not found")
        print("Install: pip install numpy")
        sys.exit(1)


def load_embedding_model(model_name="all-MiniLM-L6-v2"):
    """Load sentence-transformers model (384 dimensions).

    Args:
        model_name: Model to load. Supported:
            - 'all-MiniLM-L6-v2' (default, 384 dims)
            - 'paraphrase-MiniLM-L6-v2' (384 dims)
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def generate_embeddings(db, model, model_name, property_suffix="", limit=None):
    """Generate and store embeddings for all movies.

    Args:
        db: Database instance
        model: Sentence transformer model
        model_name: Name of the embedding model
        property_suffix: Suffix for property names (e.g., "_v1", "_v2")
        limit: Max number of movies to process (for debugging)

    Returns:
        Number of movies embedded
    """
    embedding_prop = f"embedding{property_suffix}"
    vector_id_prop = f"vector_id{property_suffix}"

    # Ensure schema properties exist (required for LSM index)
    # Note: LSM index requires the property to be defined in the schema
    if not db.schema.exists_type("Movie"):
        print("ERROR: Movie type not found in schema")
        return 0

    try:
        db.schema.get_or_create_property("Movie", embedding_prop, "ARRAY_OF_FLOATS")
        db.schema.get_or_create_property("Movie", vector_id_prop, "STRING")
    except Exception as e:
        print(f"Warning: Failed to create schema properties: {e}")

    # Check if embeddings already exist for this property
    result = list(
        db.query(
            "sql",
            f"SELECT count(*) as count FROM Movie WHERE {embedding_prop} IS NOT NULL",
        )
    )
    if result and result[0].get_property("count") > 0:
        count = result[0].get_property("count")
        print(f"✓ Embeddings exist in {embedding_prop} ({count:,} movies)")
        return count

    print(f"\nGenerating embeddings for all movies using: {model_name}...")

    # Get all movies
    query = "SELECT FROM Movie ORDER BY movieId"
    if limit:
        query += f" LIMIT {limit}"

    movies = list(db.query("sql", query))

    if not movies:
        print("ERROR: No movies found")
        return 0

    total = len(movies)
    print(f"Processing {total:,} movies")

    # Prepare texts: "title genre1 genre2 genre3"
    texts = []
    for movie in movies:
        title = movie.get_property("title")
        genres = movie.get_property("genres") if movie.has_property("genres") else None

        # Build text for embedding
        if genres:
            genre_list = genres.split("|") if isinstance(genres, str) else genres
            text = f"{title} {' '.join(genre_list)}"
        else:
            text = title

        texts.append(text)

    # Generate embeddings (batch processing)
    print("Encoding to embeddings...")
    start_encode = time.time()

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        device="cpu",
    )

    elapsed_encode = time.time() - start_encode
    rate = total / elapsed_encode
    print(
        f"✓ Encoded {total:,} movies in {elapsed_encode:.1f}s "
        f"({rate:.0f} movies/sec)"
    )

    # Store embeddings using Java API
    print(f"Storing embeddings ({embedding_prop}, {vector_id_prop})...")
    start_store = time.time()

    with db.transaction():
        # Use the same movies list we generated embeddings for
        for movie, embedding in zip(movies, embeddings):
            # Get vertex, then modify to get mutable version
            java_vertex = movie._java_result.getElement().get().asVertex().modify()

            # Set embedding property with custom name
            java_embedding = arcadedb.to_java_float_array(embedding)
            java_vertex.set(embedding_prop, java_embedding)
            # Create vector_id property for HNSW index
            movie_id = str(movie.get_property("movieId"))
            java_vertex.set(vector_id_prop, movie_id)
            java_vertex.save()

    elapsed_store = time.time() - start_store
    print(f"✓ Stored {total:,} embeddings in {elapsed_store:.1f}s")

    return total


def create_vector_index(db, impl="default", property_suffix=""):
    """Create vector index on Movie embeddings and populate it.

    Args:
        db: Database instance
        impl: Implementation "default" (JVector) or "legacy" (HNSW)
        property_suffix: Suffix for property names (e.g., "_v1", "_v2")

    Returns:
        VectorIndex object
    """
    embedding_prop = f"embedding{property_suffix}"
    vector_id_prop = f"vector_id{property_suffix}"
    # Use unique edge_type for each index to avoid HNSW metadata conflicts
    edge_type = f"Movie{property_suffix}"

    # Count movies with embeddings to determine max_items
    query = f"SELECT FROM Movie WHERE {embedding_prop} IS NOT NULL"
    result_list = list(db.query("sql", query))
    num_movies = len(result_list)

    print(f"\nCreating {impl.upper()} vector index for {embedding_prop}...")
    if impl == "legacy":
        print(f"  edge_type={edge_type}, metric=cosine, m=16, ef=128")
        print(f"  max_items={num_movies:,} (based on movies with embeddings)")
    else:
        print("  metric=cosine, max_connections=16, beam_width=128")

    start_time = time.time()

    if impl == "default":
        index = db.create_vector_index(
            vertex_type="Movie",
            vector_property=embedding_prop,
            dimensions=384,
            distance_function="cosine",
            max_connections=16,
            beam_width=128,
        )
    else:  # legacy
        # Create index with correct max_items
        index = db.create_legacy_vector_index(
            vertex_type="Movie",
            vector_property=embedding_prop,
            dimensions=384,
            max_items=10000,
            id_property=vector_id_prop,
            edge_type=edge_type,
            distance_function="cosine",
            m=16,
            ef=128,
            ef_construction=128,
        )

        # Populate index with existing movies
        with db.transaction():
            for record in result_list:
                java_vertex = record._java_result.getElement().get().asVertex()
                index.add_vertex(java_vertex)

    elapsed = time.time() - start_time
    print(f"✓ Created and indexed {num_movies:,} movies in {elapsed:.1f}s")

    return index


def graph_based_recommendations(db, movie_title, limit=5, mode="full"):
    """Graph-based collaborative filtering.

    Uses graph traversal to find movies rated highly by users who rated
    the query movie highly.

    Args:
        db: Database instance
        movie_title: Title of query movie
        limit: Number of results to return
        mode: "full" for comprehensive (slow), "fast" for sampled (fast)

    Returns:
        Query time in seconds
    """
    # Find the movie by title, get movieId for fast MATCH (uses Movie[movieId] index)
    movies = list(
        db.query(
            "sql",
            "SELECT movieId FROM Movie WHERE title = :title",
            {"title": movie_title},
        )
    )

    if not movies:
        print(f"Movie not found: {movie_title}")
        return 0.0

    # Get movieId for indexed lookups
    query_movie_id = movies[0].get_property("movieId")

    if mode == "fast":
        # Fast mode: Limit intermediate results for 100-300x speedup
        # Sample ~50 users worth of data (50 * 500 ratings = 25,000 results)
        query = """
        SELECT FROM (
            SELECT other_movie.title as title,
                   AVG(rating.rating) as avg_rating,
                   COUNT(*) as rating_count
            FROM (
                SELECT * FROM (
                    MATCH {type: Movie, where: (movieId = :movieId), as: query_movie}
                          .inE('RATED'){where: (rating >= 4.0), as: user_rating}
                          .outV(){as: user}
                          .outE('RATED'){where: (rating >= 4.0), as: rating}
                          .inV(){where: (movieId <> :movieId), as: other_movie}
                    RETURN other_movie, rating
                )
                LIMIT 25000
            )
            GROUP BY other_movie.title
        )
        WHERE rating_count >= 5
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT :limit
        """
    else:
        # Full mode: Comprehensive but slow
        query = """
        SELECT FROM (
            SELECT other_movie.title as title,
                   AVG(rating.rating) as avg_rating,
                   COUNT(*) as rating_count
            FROM (
                MATCH {type: Movie, where: (movieId = :movieId), as: query_movie}
                      .inE('RATED'){where: (rating >= 4.0), as: user_rating}
                      .outV(){as: user}
                      .outE('RATED'){where: (rating >= 4.0), as: rating}
                      .inV(){where: (movieId <> :movieId), as: other_movie}
                RETURN other_movie, rating
            )
            GROUP BY other_movie.title
        )
        WHERE rating_count >= 5
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT :limit
        """

    # Execute query and measure time
    start = time.time()
    results = list(db.query("sql", query, {"movieId": query_movie_id, "limit": limit}))
    query_time = time.time() - start

    # Display results
    for i, rec in enumerate(results, 1):
        title = rec.get_property("title")[:48]
        avg_rating = rec.get_property("avg_rating")
        rating_count = rec.get_property("rating_count")
        print(f"    {i}. {title} ({avg_rating:.1f}★, {rating_count} users)")

    return query_time


def vector_based_recommendations(
    db, index, model, movie_title, property_suffix="", limit=5
):
    """Vector-based semantic similarity search.

    Args:
        db: Database instance
        index: Vector index to search
        model: Sentence transformer model
        movie_title: Title of query movie
        property_suffix: Suffix for property names
        limit: Number of results to return

    Returns:
        Query time in seconds
    """
    embedding_prop = f"embedding{property_suffix}"

    # Find the movie by title
    movies = list(
        db.query(
            "sql", "SELECT FROM Movie WHERE title = :title", {"title": movie_title}
        )
    )

    if not movies:
        print(f"Movie not found: {movie_title}")
        return 0.0

    query_movie = movies[0]

    # Get or generate embedding
    embedding = (
        query_movie.get_property(embedding_prop)
        if query_movie.has_property(embedding_prop)
        else None
    )

    if embedding is None:
        # Generate embedding for query movie
        title = query_movie.get_property("title")
        genres_val = (
            query_movie.get_property("genres")
            if query_movie.has_property("genres")
            else None
        )
        if genres_val:
            genre_list = (
                genres_val.split("|") if isinstance(genres_val, str) else genres_val
            )
            text = f"{title} {' '.join(genre_list)}"
        else:
            text = title
        embedding = model.encode([text], device="cpu")[0]
    else:
        # Convert Java array to numpy
        import numpy as np

        embedding = np.array(embedding, dtype=np.float32)

    # Vector search
    start = time.time()
    all_results = index.find_nearest(embedding, k=limit + 1)
    query_time = time.time() - start

    # Filter out the query movie
    query_title = query_movie.get_property("title")
    results = [
        (vertex, distance)
        for vertex, distance in all_results
        if vertex.get("title") != query_title
    ][:limit]

    # Display results
    for i, (vertex, distance) in enumerate(results, 1):
        title = vertex.get("title")[:48]
        print(f"    {i}. {title} (distance: {distance:.4f})")

    return query_time


def import_from_jsonl(jsonl_path: Path, target_db_path: Path) -> float:
    """Import database from JSONL export.

    Returns: import time in seconds
    """
    print(f"Importing from JSONL: {jsonl_path}")
    print(f"  → Target database: {target_db_path}")

    # Delete target if it exists
    if target_db_path.exists():
        shutil.rmtree(target_db_path)

    # Create empty database
    with arcadedb.create_database(str(target_db_path)) as db:
        pass  # Just create schema

    # Import using SQL command (IMPORT DATABASE auto-commits, no transaction needed)
    start_time = time.time()
    with arcadedb.open_database(str(target_db_path)) as db:
        # Convert Windows backslashes to forward slashes for SQL compatibility
        import_path = str(jsonl_path.absolute()).replace("\\", "/")
        import_cmd = f"IMPORT DATABASE file://{import_path}"
        db.command("sql", import_cmd)

    elapsed = time.time() - start_time

    # Count imported records
    with arcadedb.open_database(str(target_db_path)) as db:
        user_count = list(db.query("sql", "SELECT count(*) as count FROM User"))[
            0
        ].get_property("count")
        movie_count = list(db.query("sql", "SELECT count(*) as count FROM Movie"))[
            0
        ].get_property("count")
        rated_count = list(db.query("sql", "SELECT count(*) as count FROM RATED"))[
            0
        ].get_property("count")
        tagged_count = list(db.query("sql", "SELECT count(*) as count FROM TAGGED"))[
            0
        ].get_property("count")
        total_records = user_count + movie_count + rated_count + tagged_count

    print(f"  ✓ Imported {total_records:,} records in {elapsed:.2f}s")
    print(f"    ({total_records / elapsed:.0f} records/sec)")
    print(
        f"    Users: {user_count:,}, Movies: {movie_count:,}, "
        f"RATED: {rated_count:,}, TAGGED: {tagged_count:,}"
    )
    print()

    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Example 06: Vector Search Movie Recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--db-path",
        required=True,
        type=str,
        help="Working database path (e.g., movielens_graph_small_db_vectors)",
    )

    parser.add_argument(
        "--source-db",
        required=True,
        type=str,
        help="Source graph database path (e.g., movielens_graph_small_db)",
    )

    parser.add_argument(
        "--import-jsonl",
        type=str,
        required=False,
        help=(
            "Import graph database from JSONL file "
            "(e.g., ./exports/movielens_graph_small_db.jsonl.tgz)"
        ),
    )

    parser.add_argument(
        "--force-embed",
        action="store_true",
        required=False,
        help="Force re-generation of embeddings",
    )

    parser.add_argument(
        "--impl",
        choices=["default", "legacy"],
        default="default",
        help="Vector index implementation: 'default' (JVector, recommended) or 'legacy' (HNSW)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        required=False,
        help="Limit number of movies to process (for debugging)",
    )

    args = parser.parse_args()

    # Track overall timing
    script_start_time = time.time()

    print("=" * 80)
    print("Example 06: Vector Search Movie Recommendations".center(80))
    print("=" * 80)

    # Check dependencies
    print("\nChecking dependencies...")
    check_dependencies()

    # Setup: Always start fresh - either from JSONL or by copying from source
    work_db = Path(args.db_path)

    print("\nSetting up working database...")

    if args.import_jsonl:
        # Option 1: Import from JSONL
        jsonl_path = Path(args.import_jsonl)
        if not jsonl_path.exists():
            print(f"ERROR: JSONL file not found: {jsonl_path}")
            sys.exit(1)

        # Remove old working database
        if work_db.exists():
            print(f"  Removing old: {work_db}")
            shutil.rmtree(work_db)

        # Import from JSONL
        import_time = import_from_jsonl(jsonl_path, work_db)
        print(f"  ✓ Working database ready: {work_db}")
        print(f"  ⏱️  Import time: {import_time:.2f}s")
    else:
        # Option 2: Copy from source database
        source_db = Path(args.source_db)

        if not source_db.exists():
            print(f"ERROR: Source database not found: {source_db}")
            print("Run Example 05 first to create the graph database")
            print("Or use --import-jsonl to import from JSONL export")
            sys.exit(1)

        # Remove old working copy and create fresh one
        if work_db.exists():
            print(f"  Removing old: {work_db}")
            shutil.rmtree(work_db)

        print(f"  Copying fresh database from: {source_db}")
        shutil.copytree(source_db, work_db)
        print(f"  ✓ Working database ready: {work_db}")

    # Load database
    print(f"\nOpening database: {args.db_path}")

    with arcadedb.open_database(args.db_path) as db:
        # Build vector indexes for 2 models
        print("\n" + "=" * 80)
        print("BUILDING VECTOR INDEXES")
        print("=" * 80)

        # Model 1: all-MiniLM-L6-v2
        model_1_name = "all-MiniLM-L6-v2"
        print(f"\nModel 1: {model_1_name}")
        model_1 = load_embedding_model(model_1_name)
        num_embedded = generate_embeddings(
            db, model_1, model_1_name, "_v1", limit=args.limit
        )
        print(f"✓ Embedded {num_embedded:,} movies")
        index_v1 = create_vector_index(db, impl=args.impl, property_suffix="_v1")

        # Model 2: paraphrase-MiniLM-L6-v2
        model_2_name = "paraphrase-MiniLM-L6-v2"
        print(f"\nModel 2: {model_2_name}")
        model_2 = load_embedding_model(model_2_name)
        num_embedded = generate_embeddings(
            db, model_2, model_2_name, "_v2", limit=args.limit
        )
        print(f"✓ Embedded {num_embedded:,} movies")
        index_v2 = create_vector_index(db, impl=args.impl, property_suffix="_v2")

        # Run searches for 5 diverse movies
        test_movies = [
            "Toy Story (1995)",  # Animation, Family
            "Matrix, The (1999)",  # Sci-Fi, Action
            "Pulp Fiction (1994)",  # Crime, Drama
            "Forrest Gump (1994)",  # Drama, Romance
            "Jurassic Park (1993)",  # Adventure, Sci-Fi
        ]

        print("\n" + "=" * 80)
        print("COMPARING SEARCH METHODS")
        print("=" * 80)

        for movie_title in test_movies:
            print(f"\n{'='*80}")
            print(f"Query: {movie_title}")
            print("=" * 80)

            # Method 1: Graph-based Full (comprehensive but slow)
            print("\n1. Graph-Based Full (collaborative filtering - comprehensive):")
            graph_full_time = graph_based_recommendations(
                db, movie_title, limit=5, mode="full"
            )
            print(f"   ⏱️  {graph_full_time:.3f}s")

            # Method 2: Graph-based Fast (sampled, 150-300x faster)
            print("\n2. Graph-Based Fast (collaborative filtering - sampled):")
            graph_fast_time = graph_based_recommendations(
                db, movie_title, limit=5, mode="fast"
            )
            print(f"   ⏱️  {graph_fast_time:.3f}s")

            # Method 3: Vector with model 1
            print(f"\n3. Vector ({model_1_name}):")
            vector1_time = vector_based_recommendations(
                db, index_v1, model_1, movie_title, "_v1", limit=5
            )
            print(f"   ⏱️  {vector1_time:.3f}s")

            # Method 4: Vector with model 2
            print(f"\n4. Vector ({model_2_name}):")
            vector2_time = vector_based_recommendations(
                db, index_v2, model_2, movie_title, "_v2", limit=5
            )
            print(f"   ⏱️  {vector2_time:.3f}s")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("• Graph-based Full: Comprehensive collaborative filtering")
    print("  - Analyzes all users who rated the query movie")
    print("  - Most thorough but slow (24-39s per query)")
    print("  - Best for offline batch recommendations")
    print()
    print("• Graph-based Fast: Sampled collaborative filtering")
    print("  - Limits to ~50 users worth of data (25K intermediate results)")
    print("  - 150-300x faster (0.1-0.2s per query)")
    print("  - Still produces high-quality recommendations")
    print("  - Best for real-time recommendations")
    print()
    print("• Vector-based: Semantic similarity (HNSW index)")
    print("  - Finds movies with similar plot/genre descriptions")
    print("  - Fast (~0.2s) with no cold start problem")
    print("  - Works for new movies without ratings")
    print("  - Different models capture different similarities")
    print("=" * 80)

    # Overall timing summary
    script_elapsed = time.time() - script_start_time
    print("\n" + "=" * 80)
    print("OVERALL TIMING")
    print("=" * 80)
    minutes = script_elapsed / 60
    print(f"Total script execution time: {script_elapsed:.2f}s " f"({minutes:.1f} min)")
    print("=" * 80)


if __name__ == "__main__":
    main()
