#!/usr/bin/env python3
"""
Example 03: Vector Search - Semantic Similarity

⚠️  EXPERIMENTAL FEATURE ⚠️
Vector search in ArcadeDB is currently under active development and may have bugs.
This example demonstrates the API and concepts, but is not recommended for
production use until the vector implementation stabilizes.

This example demonstrates vector embeddings and semantic similarity search using
ArcadeDB's HNSW (Hierarchical Navigable Small World) index.

Key Concepts:
- Storing vector embeddings (simulated sentence embeddings)
- Creating HNSW indexes for fast nearest-neighbor search
- Finding semantically similar documents using cosine similarity
- Understanding vector search parameters (dimensions, distance functions)
- Index population strategies and performance characteristics

Implementation Status:
- Current: Uses jelmerk/hnswlib (Java port)
- Future: Will migrate to datastax/jvector (better performance)
- See docs/examples/03_vector_search.md for detailed comparison

Potential Use Cases (when stable):
- Semantic document search (find similar articles, papers)
- RAG (Retrieval-Augmented Generation) for LLMs
- Recommendation systems (find similar products, content)
- Duplicate detection (find near-duplicate text)
- Question answering (find relevant context)

Requirements:
- arcadedb-embedded
- NumPy (for vector operations and mock embeddings)

Note: This example uses mock embeddings for demonstration. In production:
- Use real embedding models (OpenAI, sentence-transformers, etc.)
- Store higher-dimensional vectors (384, 768, 1536 dimensions)
- Index vectors incrementally as you insert documents
- Consider metadata filtering strategies (see documentation)
- Test thoroughly as vector features may have known issues

About Vector Search:
Vector embeddings represent text/images as points in high-dimensional space.
Similar items are close together, enabling semantic search beyond keyword matching.
HNSW (Hierarchical Navigable Small World) enables logarithmic search time without
loading all vectors into memory.
"""

import argparse
import os
import shutil
import time

import arcadedb_embedded as arcadedb
import numpy as np

# Parse command line arguments
parser = argparse.ArgumentParser(description="Vector Search Example")
parser.add_argument(
    "--impl",
    choices=["default"],
    default="default",
    help="Vector index implementation: 'default' (JVector) or ",
)
args = parser.parse_args()

print("=" * 70)
print(f"🔍 ArcadeDB Python - Example 03: Vector Search ({args.impl.upper()})")
print("=" * 70)
print()
print("⚠️  EXPERIMENTAL: Vector search is under active development")
print("   This example demonstrates the API but may have known issues.")
print("   Not recommended for production use yet.")
print()

# -----------------------------------------------------------------------------
# Step 1: Create Database
# -----------------------------------------------------------------------------
print("Step 1: Creating database...")
step_start = time.time()

db_dir = "./my_test_databases"
db_path = os.path.join(db_dir, "vector_search_db")

# Clean up any existing database
if os.path.exists(db_path):
    shutil.rmtree(db_path)

if os.path.exists("./log"):
    shutil.rmtree("./log")

db = arcadedb.create_database(db_path)

print(f"   ✅ Database created at: {db_path}")
print("   💡 Using embedded mode - no server needed!")
print(f"   ⏱️  Time: {time.time() - step_start:.3f}s")
print()

# -----------------------------------------------------------------------------
# Step 2: Create Schema for Documents with Vectors
# -----------------------------------------------------------------------------
print("Step 2: Creating schema for document embeddings...")
step_start = time.time()

with db.transaction():
    # Create vertex type for documents
    # We use VERTEX (not DOCUMENT) so we can potentially create relationships
    db.schema.create_vertex_type("Article")

    # Properties
    db.schema.create_property("Article", "id", "STRING")
    db.schema.create_property("Article", "title", "STRING")
    db.schema.create_property("Article", "content", "STRING")
    db.schema.create_property("Article", "category", "STRING")

    # Vector property - MUST be ARRAY_OF_FLOATS for HNSW index
    # In production, this would be 384, 768, or 1536 dimensions
    db.schema.create_property("Article", "embedding", "ARRAY_OF_FLOATS")

    # Index for fast lookups using Schema API
    db.schema.create_index("Article", ["id"], unique=True)

print("   ✅ Created Article vertex type with embedding property")
print("   💡 Vector property type: ARRAY_OF_FLOATS (required for HNSW)")
print(f"   ⏱️  Time: {time.time() - step_start:.3f}s")
print()

# -----------------------------------------------------------------------------
# Step 3: Create Mock Document Embeddings
# -----------------------------------------------------------------------------
print("Step 3: Creating sample documents with mock embeddings...")
print()

# Using realistic dimensions like sentence-transformers models
# - all-MiniLM-L6-v2: 384 dimensions (most popular, good balance)
# - all-mpnet-base-v2: 768 dimensions (higher quality)
# - OpenAI text-embedding-3-small: 1536 dimensions
EMBEDDING_DIM = 384  # Matching sentence-transformers/all-MiniLM-L6-v2

print(f"   💡 Using {EMBEDDING_DIM}D embeddings (like sentence-transformers)")
print("   💡 In production, use real models: OpenAI, sentence-transformers, etc.")
print()

# Set random seed for reproducibility
np.random.seed(42)


# Pre-compute uniformly distributed category base vectors on unit sphere
# This ensures categories are maximally separated in embedding space
def generate_uniform_sphere_points(n_points, dimensions):
    """
    Generate points uniformly distributed on unit sphere using Gaussian method.

    Generates random points from standard normal distribution, then normalizes.
    This produces a uniform distribution on the sphere surface (Muller 1959).

    Args:
        n_points: Number of points to generate
        dimensions: Dimensionality of the sphere

    Returns:
        numpy.ndarray: Array of shape (n_points, dimensions) with unit vectors
    """
    # Generate from standard normal distribution
    points = np.random.randn(n_points, dimensions)

    # Normalize each point to unit length
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    points = points / norms

    return points


# Generate category base vectors once (will be used by create_mock_embedding)
CATEGORY_BASE_VECTORS = None


def initialize_category_vectors(num_categories, dimensions):
    """Initialize uniformly distributed category base vectors."""
    global CATEGORY_BASE_VECTORS
    CATEGORY_BASE_VECTORS = generate_uniform_sphere_points(num_categories, dimensions)


def create_mock_embedding(category, doc_id):
    """
    Create a realistic mock embedding based on category.

    Simulates how real embeddings work:
    - Categories uniformly distributed on unit sphere (maximally separated)
    - Each document has unique but related embedding within category
    - Normalized to unit length (standard for cosine similarity)

    Args:
        category: Document category (e.g., "category_1", "category_2", ...)
        doc_id: Unique document ID (for variation within category)

    Returns:
        numpy.ndarray: Normalized 384D embedding vector
    """
    # Extract category number from "category_N" format
    category_num = int(category.split("_")[1]) - 1  # 0-indexed

    # Get pre-computed uniformly distributed base vector for this category
    category_vector = CATEGORY_BASE_VECTORS[category_num]

    # Add small document-specific variation
    doc_seed = hash(doc_id) % 1000000
    doc_rng = np.random.RandomState(doc_seed)

    # Mix 85% category vector + 15% random noise for realistic clustering
    # Real embeddings have ~0.7-0.95 similarity within same topic
    noise = doc_rng.randn(EMBEDDING_DIM) * 0.15
    embedding = category_vector + noise

    # Normalize to unit length (standard practice for cosine similarity)
    embedding = embedding / np.linalg.norm(embedding)

    return embedding


# Generate a realistic dataset of 10,000 documents across 10 categories
# This simulates a large knowledge base or documentation corpus
NUM_DOCUMENTS = 10000
NUM_CATEGORIES = 100
DOCS_PER_CATEGORY = NUM_DOCUMENTS // NUM_CATEGORIES

print(
    f"   💡 Generating {NUM_DOCUMENTS:,} documents "
    f"across {NUM_CATEGORIES} categories..."
)
print()

# Initialize uniformly distributed category vectors
initialize_category_vectors(NUM_CATEGORIES, EMBEDDING_DIM)
print(f"   ✅ Generated {NUM_CATEGORIES} uniformly distributed category base vectors")
print("      (Categories maximally separated on unit sphere)")
print()

documents = []
doc_counter = 1

for cat_num in range(1, NUM_CATEGORIES + 1):
    category = f"category_{cat_num}"

    for doc_num in range(1, DOCS_PER_CATEGORY + 1):
        doc_id = f"doc{doc_counter:05d}"
        title = f"Category {cat_num}: Document {doc_num}"
        content = f"This is a mock document about {category} topics..."

        documents.append(
            {
                "id": doc_id,
                "title": title,
                "content": content,
                "category": category,
            }
        )
        doc_counter += 1

# Insert documents with embeddings using BatchContext for optimal performance
print("   Inserting documents with embeddings...")
print("   💡 Using BatchContext for efficient bulk insertion")
step_start = time.time()

# Use BatchContext for efficient bulk insertion with progress tracking
with db.batch_context(
    batch_size=5000, parallel=4, progress=True, progress_desc="Inserting documents"
) as batch:
    for doc in documents:
        # Generate realistic mock embedding
        embedding = create_mock_embedding(doc["category"], doc["id"])

        # Convert numpy array to Java float array
        java_embedding = arcadedb.to_java_float_array(embedding)

        # Create vertex using batch context (automatically queued for async insertion)
        batch.create_vertex(
            "Article",
            id=doc["id"],
            title=doc["title"],
            content=doc["content"],
            category=doc["category"],
            embedding=java_embedding,
        )
    # BatchContext automatically waits for completion on exit

print(f"   ✅ Inserted {len(documents):,} documents with {EMBEDDING_DIM}D embeddings")
print(f"   ⏱️  Time: {time.time() - step_start:.3f}s")
print()

# -----------------------------------------------------------------------------
# Step 4: Create Vector Index
# -----------------------------------------------------------------------------
print(f"Step 4: Creating {args.impl.upper()} vector index...")
step_start = time.time()

# Determine max_items from document count
num_articles = db.count_type("Article")
print(f"   📊 Found {num_articles} articles to index")
print()

print(f"   💡 {args.impl.upper()} Parameters:")
print(f"      • dimensions: {EMBEDDING_DIM} (matches embedding size)")
print("      • distance_function: cosine (best for normalized vectors)")
print(
    "      • max_connections: 16 (connections per node, higher = more accurate but slower)"
)
print("      • beam_width: 128 (search quality, higher = more accurate)")
if args.impl == "hnsw":
    print(f"      • max_items: {num_articles} (set to actual document count)")
print()

with db.transaction():
    if args.impl == "default":
        # Create vector index (JVector implementation - recommended)
        index = db.create_vector_index(
            vertex_type="Article",
            vector_property="embedding",
            dimensions=EMBEDDING_DIM,
            distance_function="cosine",
            max_connections=16,
            beam_width=128,
        )
    else:  # legacy
        # Create legacy HNSW vector index
        index = db.create_legacy_vector_index(
            vertex_type="Article",
            vector_property="embedding",
            dimensions=EMBEDDING_DIM,
            max_items=num_articles,
            id_property="id",
            distance_function="cosine",  # Options: cosine, euclidean, inner_product
            m=16,
            ef=128,
            ef_construction=128,
        )

print(f"   ✅ Created {args.impl.upper()} vector index")
print(f"   ⏱️  Time: {time.time() - step_start:.3f}s")
print()

# -----------------------------------------------------------------------------
# Step 5: Populate Vector Index (Batch Indexing)
# -----------------------------------------------------------------------------
if args.impl == "legacy":
    print("Step 5: Populating vector index with existing documents...")
    print()
    print("   ⚠️  BATCH INDEXING: One-time operation for existing data")
    print()
    print("   💡 Production Best Practices:")
    print("      • INDEX AS YOU INSERT: Call index.add_vertex() during creation")
    print("      • AVOID RE-INDEXING: Batch approach is for initial load only")
    print("      • FILTERING: Build ONE index, use oversampling for filters")
    print("      • PERFORMANCE: ~13ms per document (HNSW graph + disk writes)")
    print()
    print("   📊 What happens during indexing:")
    print("      • HNSW graph built in RAM (algorithm execution)")
    print("      • Edges persisted to disk (~9KB per document)")
    print("      • Vertices updated with graph metadata")
    print("      • All within transaction for consistency")
    print()

    step_start = time.time()

    # Fetch all documents and add them to the index
    result = db.query("sql", "SELECT FROM Article ORDER BY id")

    with db.transaction():
        for record in result:
            # Get the underlying Java vertex object
            java_vertex = record._java_result.getElement().get().asVertex()

            # Add to vector index
            index.add_vertex(java_vertex)

    # Count how many we indexed (could also use count() method on result)
    indexed_count = db.count_type("Article")

    print(f"   ✅ Indexed {indexed_count:,} documents in HNSW index")
    print(f"   ⏱️  Time: {time.time() - step_start:.3f}s")
    per_doc_time = (time.time() - step_start) / indexed_count * 1000
    print(f"   ⏱️  Per-document indexing time: {per_doc_time:.2f}ms")
    print()
    print("   ⚠️  Note: This step is slow because we're batch-indexing existing data.")
    print("      In production, you'd typically index vectors as you insert them,")
    print("      not re-index the entire dataset.")
    print()
else:
    print("Step 5: Populating vector index...")
    print("   💡 LSM index automatically indexes existing records upon creation.")
    print("   ✅ Indexing handled by ArcadeDB engine.")

# -----------------------------------------------------------------------------
# Step 6: Perform Semantic Search
# -----------------------------------------------------------------------------
print("Step 6: Performing semantic similarity searches...")
step_start = time.time()

# Sample 10 random categories (or NUM_CATEGORIES if less than 10)
num_queries = min(10, NUM_CATEGORIES)
sampled_categories = np.random.choice(
    range(1, NUM_CATEGORIES + 1), size=num_queries, replace=False
)

print(f"   Running {num_queries} queries on randomly sampled categories...")
print()

for query_num, cat_num in enumerate(sampled_categories, 1):
    category = f"category_{cat_num}"

    print(f"   🔍 Query {query_num}: Find documents similar to Category {cat_num}")
    print()

    query_embedding = create_mock_embedding(category, f"query{query_num}")

    # Get top 5 most similar (smallest distances)
    most_similar = index.find_nearest(query_embedding, k=5)

    print("      Top 5 MOST similar documents (smallest distance):")
    for i, (vertex, distance) in enumerate(most_similar, 1):
        title = vertex.get("title")
        doc_category = vertex.get("category")
        print(f"      {i}. {title}")
        print(f"         Category: {doc_category}, Distance: {distance:.4f}")
    print()

    # Get all documents to find least similar
    # (HNSW doesn't have a "find_farthest" method, so we get more results)
    # Note: For LSM, getting ALL documents might be slow or limited by k
    k_limit = NUM_DOCUMENTS if args.impl == "legacy" else min(NUM_DOCUMENTS, 1000)
    all_results = index.find_nearest(query_embedding, k=k_limit)
    least_similar = list(all_results)[-5:]  # Last 5 = farthest

    print("      Top 5 LEAST similar documents (largest distance):")
    for i, (vertex, distance) in enumerate(least_similar, 1):
        title = vertex.get("title")
        doc_category = vertex.get("category")
        print(f"      {i}. {title}")
        print(f"         Category: {doc_category}, Distance: {distance:.4f}")
    print()

print(f"   ⏱️  All queries time: {time.time() - step_start:.3f}s")
print()

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
print("=" * 70)
print("✅ Vector search example completed successfully!")
print("=" * 70)
print()

db.close()

print(f"💡 Database preserved at: {db_path}")
print()
