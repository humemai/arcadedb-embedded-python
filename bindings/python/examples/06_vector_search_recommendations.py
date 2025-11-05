#!/usr/bin/env python3
"""
Example 06: Vector Search Movie Recommendations

Demonstrates vector embeddings and HNSW indexing for semantic movie search.
Compares traditional graph queries with vector similarity search.

PERFORMANCE OPTIMIZATION (NEW!)
--------------------------------
This script now automatically creates optimization indexes for graph queries:
- Movie (title): Speeds up movie lookup by title
- RATED (rating): Speeds up edge filtering by rating value

These indexes improve graph-based collaborative filtering from 40-60 seconds
to < 1 second on large datasets (86K movies). The script will create these
indexes automatically on first run.

For the large dataset, set these variables ARCADEDB_JVM_MAX_HEAP="8g"
ARCADEDB_JVM_ARGS="-Xms8g" so that sufficient memory is allocated.

KNOWN ISSUES: HNSW Vector Index Limitations
--------------------------------------------

1. **HNSW Metadata Persistence**: Once embeddings and indexes are created,
   they cannot be completely removed and recreated on the same vertices.
   The HNSW graph metadata (edges, vectorMaxLevel property) persists even
   after dropping the index.

   WORKAROUND: Use SEPARATE properties and edge types for each model
   (embedding_v1/embedding_v2 with edge types Movie_v1/Movie_v2).

2. **JSONL Export/Import Broken for Vectors**: Float arrays are NOT properly
   preserved during JSONL export/import:
   - Embeddings exported as Java toString() strings: "[F@113ee1ce"
   - Original vector data (384 floats) is completely lost
   - HNSW index edges are not exported at all

   IMPACT: Cannot backup/restore vector databases using JSONL format.
   After import, embeddings must be regenerated and indexes rebuilt.

Features:
- Real embeddings using sentence-transformers (two models for comparison)
- HNSW vector indexing for fast similarity search
- Compare graph-based vs vector-based recommendations
- Performance timing for all search methods

Dataset: MovieLens small (9,742 movies from Example 05)

Usage:
    # Import from JSONL export (recommended)
    python 06_vector_search_recommendations.py \\
        --import-jsonl ./exports/ml_graph_small_db.jsonl.tgz

    # Use existing database
    python 06_vector_search_recommendations.py \\
        --source-db my_test_databases/ml_graph_small_db
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


def generate_embeddings(db, model, model_name, property_suffix=""):
    """Generate and store embeddings for all movies.

    Args:
        db: Database instance
        model: Sentence transformer model
        model_name: Name of the embedding model
        property_suffix: Suffix for property names (e.g., "_v1", "_v2")

    Returns:
        Number of movies embedded
    """
    embedding_prop = f"embedding{property_suffix}"
    vector_id_prop = f"vector_id{property_suffix}"

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
    movies = list(db.query("sql", "SELECT FROM Movie ORDER BY movieId"))

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
        # Query movies inside transaction
        movies_result = db.query("sql", "SELECT * FROM Movie")

        for movie, embedding in zip(movies_result, embeddings):
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


def create_vector_index(db, property_suffix=""):
    """Create HNSW vector index on Movie embeddings and populate it.

    Args:
        db: Database instance
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

    print(f"\nCreating HNSW vector index for {embedding_prop}...")
    print(f"  edge_type={edge_type}, metric=cosine, m=16, ef=128")
    print(f"  max_items={num_movies:,} (based on movies with embeddings)")

    start_time = time.time()

    # Create index with correct max_items
    with db.transaction():
        index = db.create_vector_index(
            vertex_type="Movie",
            vector_property=embedding_prop,
            dimensions=384,
            max_items=num_movies,
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


def graph_based_recommendations(db, movie_title, limit=5):
    """Graph-based collaborative filtering.

    Uses graph traversal to find movies rated highly by users who rated
    the query movie highly.

    Args:
        db: Database instance
        movie_title: Title of query movie
        limit: Number of results to return

    Returns:
        Query time in seconds
    """
    # Find the movie
    movies = list(
        db.query(
            "sql", "SELECT FROM Movie WHERE title = :title", {"title": movie_title}
        )
    )

    if not movies:
        print(f"Movie not found: {movie_title}")
        return 0.0

    # Collaborative filtering query
    query = """
    SELECT other_movie.title as title,
           AVG(rating.rating) as avg_rating,
           COUNT(*) as rating_count
    FROM (
        MATCH {type: Movie, where: (title = :title), as: query_movie}
              .inE('RATED'){where: (rating >= 4.0), as: user_rating}
              .outV(){as: user}
              .outE('RATED'){where: (rating >= 4.0), as: rating}
              .inV(){where: (title <> :title), as: other_movie}
        RETURN other_movie, rating
    )
    GROUP BY other_movie.title
    ORDER BY avg_rating DESC, rating_count DESC
    """

    # Execute query and measure time
    start = time.time()
    all_results = list(db.query("sql", query, {"title": movie_title}))
    query_time = time.time() - start

    # Filter by minimum rating count (min 5 users)
    results = [rec for rec in all_results if rec.get_property("rating_count") >= 5][
        :limit
    ]

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

    # Find the movie
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
        import_cmd = f"IMPORT DATABASE file://{jsonl_path.absolute()}"
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


def optimize_graph_indexes(db):
    """Add optimization indexes for graph traversal queries.

    Indexes created:
    - Movie (title): Speed up movie lookup by title (graph query start)
    - RATED (rating): Speed up edge filtering by rating value

    These indexes dramatically improve graph-based collaborative filtering
    queries (from 40-60 seconds to < 1 second on large datasets).
    """
    print("\nOptimizing graph indexes...")
    print("-" * 80)

    # Check existing indexes
    existing_indexes = list(db.command("sql", "SELECT FROM schema:indexes"))
    index_names = [idx.get_property("name") for idx in existing_indexes]

    print(f"  Current indexes: {len(index_names)}")
    for name in sorted(index_names):
        print(f"    - {name}")

    # Create optimization indexes with retry logic
    indexes_to_create = [
        ("Movie", "title", "NOTUNIQUE"),
        ("RATED", "rating", "NOTUNIQUE"),
    ]

    created = []
    failed = []

    for idx, (table, column, uniqueness) in enumerate(indexes_to_create, 1):
        index_name = f"{table}[{column}]"

        if index_name in index_names:
            print(f"  ✓ {index_name} already exists")
            continue

        # Retry logic for compaction conflicts
        max_retries = 60  # Up to 60 attempts
        retry_delay = 10  # Wait 10 seconds between attempts
        index_created = False

        for attempt in range(1, max_retries + 1):
            try:
                start = time.time()
                with db.transaction():
                    sql = f"CREATE INDEX ON {table} ({column}) {uniqueness}"
                    db.command("sql", sql)
                elapsed = time.time() - start
                print(f"  ✓ Created {index_name} in {elapsed:.1f}s")
                created.append(index_name)
                index_created = True
                break
            except Exception as e:
                error_msg = str(e)

                # Check if retryable (compaction or index conflicts)
                is_compaction_error = (
                    "NeedRetryException" in error_msg
                    and "asynchronous tasks" in error_msg
                )
                is_index_error = (
                    "IndexException" in error_msg
                    and "Error on creating index" in error_msg
                )

                if is_compaction_error or is_index_error:
                    if attempt < max_retries:
                        elapsed = attempt * retry_delay
                        reason = (
                            "compaction running"
                            if is_compaction_error
                            else "index conflict"
                        )
                        print(
                            f"  ⏳ [{idx}/{len(indexes_to_create)}] "
                            f"Waiting for {reason} "
                            f"(attempt {attempt}/{max_retries}, "
                            f"{elapsed}s elapsed)..."
                        )
                        time.sleep(retry_delay)
                    else:
                        print(
                            f"  ❌ Failed to create {index_name} "
                            f"after {max_retries} retries"
                        )
                        failed.append(index_name)
                        break
                else:
                    # Non-retryable error
                    print(f"  ⚠️  Failed to create {index_name}: {error_msg}")
                    failed.append(index_name)
                    break

        if not index_created and index_name not in failed:
            print(f"  ⚠️  Skipping {index_name}")
            failed.append(index_name)

    if created:
        print(f"\n✓ Created {len(created)} optimization index(es)")
        print("  Graph queries should be significantly faster!")
    elif failed:
        print(f"\n⚠️  Failed to create {len(failed)} index(es)")
    else:
        print("\n✓ All optimization indexes already exist")

    print("-" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Example 06: Vector Search Movie Recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--db-path",
        required=True,
        type=str,
        help="Working database path (e.g., ml_graph_small_db_vectors)",
    )

    parser.add_argument(
        "--source-db",
        required=True,
        type=str,
        help="Source graph database path (e.g., ml_graph_small_db)",
    )

    parser.add_argument(
        "--import-jsonl",
        type=str,
        required=False,
        help="Import graph database from JSONL file (e.g., ./exports/ml_graph_small_db.jsonl.tgz)",
    )

    parser.add_argument(
        "--force-embed",
        action="store_true",
        required=False,
        help="Force re-generation of embeddings",
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
        # Optimize graph indexes FIRST (before any queries)
        optimize_graph_indexes(db)

        # Build vector indexes for 2 models
        print("\n" + "=" * 80)
        print("BUILDING VECTOR INDEXES")
        print("=" * 80)

        # Model 1: all-MiniLM-L6-v2
        model_1_name = "all-MiniLM-L6-v2"
        print(f"\nModel 1: {model_1_name}")
        model_1 = load_embedding_model(model_1_name)
        num_embedded = generate_embeddings(db, model_1, model_1_name, "_v1")
        print(f"✓ Embedded {num_embedded:,} movies")
        index_v1 = create_vector_index(db, property_suffix="_v1")

        # Model 2: paraphrase-MiniLM-L6-v2
        model_2_name = "paraphrase-MiniLM-L6-v2"
        print(f"\nModel 2: {model_2_name}")
        model_2 = load_embedding_model(model_2_name)
        num_embedded = generate_embeddings(db, model_2, model_2_name, "_v2")
        print(f"✓ Embedded {num_embedded:,} movies")
        index_v2 = create_vector_index(db, property_suffix="_v2")

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

            # Method 1: Graph-based
            print("\n1. Graph-Based (collaborative filtering):")
            graph_time = graph_based_recommendations(db, movie_title, limit=5)
            print(f"   ⏱️  {graph_time:.3f}s")

            # Method 2: Vector with model 1
            print(f"\n2. Vector ({model_1_name}):")
            vector1_time = vector_based_recommendations(
                db, index_v1, model_1, movie_title, "_v1", limit=5
            )
            print(f"   ⏱️  {vector1_time:.3f}s")

            # Method 3: Vector with model 2
            print(f"\n3. Vector ({model_2_name}):")
            vector2_time = vector_based_recommendations(
                db, index_v2, model_2, movie_title, "_v2", limit=5
            )
            print(f"   ⏱️  {vector2_time:.3f}s")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("• Graph-based: Finds movies liked by similar users")
    print("  - Leverages user behavior patterns")
    print("  - Requires rating data (cold start problem)")
    print()
    print("• Vector-based: Finds semantically similar movies")
    print("  - Works for new movies without ratings")
    print("  - Fast with HNSW index")
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
