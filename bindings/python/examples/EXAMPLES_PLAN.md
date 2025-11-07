# ArcadeDB Python Examples - Planning Document

## Target User Personas

1. **Data Scientists**: Using embeddings, vector search, analytics
2. **Backend Developers**: Building APIs, microservices with embedded DB
3. **Graph Analysts**: Working with relationships, networks, social graphs
4. **ETL Engineers**: Importing data from various sources
5. **Application Developers**: Need simple embedded database for desktop/CLI apps

## 10 Practical Examples

### 1. **Getting Started: Simple Document Store** ✅ (Priority: CRITICAL)
**File**: `01_simple_document_store.py`
**Target**: First-time users, application developers
**Concepts**: Database creation, basic CRUD, context managers, transactions
**Why**: Every user needs this - absolute basics, shows Pythonic API
```python
# Create DB, insert documents, query, close
# Like SQLite but with documents
# Perfect for config storage, logs, simple apps
```

### 2. **Graph Basics: Social Network** (Priority: HIGH)
**File**: `02_social_network_graph.py`
**Target**: Graph analysts, developers new to graph DBs
**Concepts**: Vertices, edges, graph traversals, relationships
**Why**: Graph DB is ArcadeDB's strength, shows core value proposition
```python
# Person vertices, FRIEND_OF edges
# Find friends, friends-of-friends
# Shortest path between people
```

### 3. **Vector Search: Semantic Similarity** (Priority: HIGH)
**File**: `03_vector_embeddings_search.py`
**Target**: Data scientists, AI/ML engineers
**Concepts**: Vector storage, HNSW index, nearest neighbor search
**Why**: Hot topic (RAG, LLMs), differentiates from traditional DBs
```python
# Store text embeddings (OpenAI/sentence-transformers)
# Build HNSW index
# Find similar documents by cosine similarity
```

### 4. **CSV Import: Documents** ✅ (Priority: HIGH)
**File**: `04_csv_import_documents.py`
**Target**: ETL engineers, data analysts
**Concepts**: CSV → Documents, type inference, NULL handling, batch processing, index optimization
**Why**: Most common import scenario, production patterns
**Status**: ✅ Complete - MovieLens dataset with 124K records, automatic dataset download
```python
# CSV → Documents: Product catalog, user data, any tabular data
# Automatic dataset download (--size small|large)
# Custom type inference (BYTE, SHORT, INTEGER, LONG, FLOAT, DOUBLE, DECIMAL, STRING)
# Explicit schema definition BEFORE import
# NULL value handling (4,920 NULL values)
# Batch processing with commit_every parameter
# Index creation AFTER import (2-3x faster)
```

### 5. **CSV Import: Graph (Vertices & Edges)** ✅ (Priority: HIGH)
**File**: `05_csv_import_graph.py`
**Target**: Graph analysts, ETL engineers
**Concepts**: CSV → Vertices, CSV → Edges, foreign key resolution, relationship mapping, graph traversal, performance benchmarking
**Why**: Graph import is different from documents, common migration scenario, critical for understanding Java API vs SQL performance
**Status**: ✅ Complete - MovieLens dataset with comprehensive performance analysis
**Dataset**: MovieLens (reuses data from Example 04)
```python
# CSV → Vertices: Movie and User nodes from MovieLens dataset
# CSV → Edges: User RATED Movie relationships (from ratings.csv)
# CSV → Edges: Movie HAS_TAG Tag relationships (from tags.csv)
# Foreign key resolution (userId → User vertex, movieId → Movie vertex)
# Edge properties (rating score, timestamp)
# Graph queries: "Users who rated similar movies", "Movie recommendations"
# Performance benchmarking: Java API vs SQL, sync vs async, with/without indexes
# Key findings: java_noasync fastest (5,071 edges/sec), sync 2.5× faster than async
```
**Note**: ✅ Complete with 6 benchmark configurations, 10 validation queries, export/import roundtrip testing

### 6. **Vector Search: Movie Recommendations** 🚧 (Priority: MEDIUM)
**File**: `06_vector_search_movies.py`
**Target**: Data scientists, AI/ML engineers
**Concepts**: Document embeddings, vector similarity, semantic search on real data
**Why**: Practical vector search application using familiar dataset
**Status**: 🚧 Planned
**Dataset**: MovieLens (reuses data from Example 04)
```python
# Generate embeddings from movie titles + genres
# Store vectors in ArcadeDB with metadata
# Find similar movies using HNSW index
# Combine vector similarity with rating data
# "Movies similar to X that users also liked"
```
**Note**: Demonstrates vector search with real-world use case (recommendations)

### 7. **Multi-Model: Stack Overflow Q&A** 🚧 (Priority: HIGH)
**File**: `07_stackoverflow_multimodel.py`
**Target**: Backend developers, full-stack engineers, data scientists
**Concepts**: Documents + Graph + Vectors in one system, complex queries, multi-model integration
**Why**: Comprehensive showcase of ArcadeDB's multi-model capabilities with rich dataset
**Status**: 🚧 In Progress
**Dataset**: Stack Exchange XML data dump (8 XML files: Posts, Users, Tags, Comments, Votes, Badges, PostLinks, PostHistory)
**Dataset Sizes**:
- Small (cs.stackexchange.com): ~1.4M records, ~650MB, 668 tags
- Medium (stats.stackexchange.com): ~5M records, ~2.5GB, 1,612 tags
- Large (stackoverflow.com): ~350M records, ~325GB, 65K tags
**Scope**: Single comprehensive Python file (~800-1000 lines) with class-based architecture

## Architecture: Three Phases in ONE File

### **Phase 1: Document Import (SchemaBuilder + DocumentImporter classes)**
Import 8 XML files → 8 Document types with schema-first approach
```python
class SchemaBuilder:
    """Creates ArcadeDB schema from analyzed JSON schema"""
    def load_schema(json_path)          # Load stackoverflow_schema.json
    def create_document_types()         # CREATE DOCUMENT TYPE Post, User, etc.
    def create_properties()             # CREATE PROPERTY with explicit types
    def handle_type_conflicts()         # Use STRING for INTEGER+DATETIME conflicts

class DocumentImporter:
    """Imports XML → Documents with streaming parser"""
    def import_entity(xml_path, entity)  # Stream XML, batch insert
    def convert_types()                  # STRING → INTEGER/DATETIME conversion
    def handle_nulls()                   # Missing attributes = NULL
    def batch_commit()                   # Commit every 5,000-10,000 records
    def create_indexes_after_import()    # Primary keys + foreign keys
```

**Documents Created**:
- Post (22 attrs): Id, PostTypeId, Title, Body, Tags, OwnerUserId, CreationDate, Score, etc.
- User (12 attrs): Id, DisplayName, Reputation, AboutMe, Location, CreationDate, etc.
- Tag (5 attrs): Id, TagName, Count, ExcerptPostId, WikiPostId
- Comment (7 attrs): Id, PostId, UserId, Text, Score, CreationDate, UserDisplayName
- Vote (6 attrs): Id, PostId, UserId, VoteTypeId, BountyAmount, CreationDate
- Badge (6 attrs): Id, UserId, Name, Date, Class, TagBased
- PostLink (5 attrs): Id, PostId, RelatedPostId, LinkTypeId, CreationDate
- PostHistory (10 attrs): Id, PostId, UserId, PostHistoryTypeId, Text, Comment, CreationDate, etc.

**Indexes Created** (after import):
```sql
-- Primary Keys (UNIQUE)
CREATE INDEX ON Post (Id) UNIQUE
CREATE INDEX ON User (Id) UNIQUE
CREATE INDEX ON Tag (TagName) UNIQUE

-- Foreign Keys (NOTUNIQUE) - for graph traversal
CREATE INDEX ON Post (OwnerUserId, ParentId, AcceptedAnswerId, PostTypeId) NOTUNIQUE
CREATE INDEX ON Comment (PostId, UserId) NOTUNIQUE
CREATE INDEX ON Vote (PostId, UserId, VoteTypeId) NOTUNIQUE
CREATE INDEX ON Badge (UserId, Name) NOTUNIQUE
CREATE INDEX ON PostLink (PostId, RelatedPostId, LinkTypeId) NOTUNIQUE
CREATE INDEX ON PostHistory (PostId, UserId) NOTUNIQUE

-- Temporal/Scoring (NOTUNIQUE)
CREATE INDEX ON Post (CreationDate, Score) NOTUNIQUE
CREATE INDEX ON User (Reputation) NOTUNIQUE
```

**Type Conflict Handling**:
```python
# Fields with DATETIME conflicts in large dataset → use STRING
CONFLICT_FIELDS = {
    'Posts': ['AcceptedAnswerId'],      # 38 DATETIME in 1M samples
    'Users': ['AccountId'],
    'Comments': ['Id'],                 # 7,255 DATETIME!
    'Votes': ['Id'],                    # 13,188 DATETIME!
    'Badges': ['Id', 'UserId'],
    'PostLinks': ['Id', 'PostId', 'RelatedPostId'],
    'Tags': ['ExcerptPostId', 'WikiPostId'],
}
# Strategy: Store as STRING, convert to INTEGER at query time (safe)
```

### **Phase 2: Graph Creation (GraphBuilder class)**
Convert Documents → Vertices + Edges
```python
class GraphBuilder:
    """Creates graph from documents"""
    def convert_to_vertices()           # Post/User/Tag documents → vertices
    def create_user_vertices()          # User documents → User vertices
    def create_post_vertices()          # Post documents → Post vertices (Q/A)
    def create_tag_vertices()           # Tag documents → Tag vertices
    def create_edges()                  # Create all relationship edges

    # Edge creation methods (use indexes for fast lookups)
    def create_asked_answered_edges()   # Post.OwnerUserId → User
    def create_answer_to_edges()        # Post.ParentId → Post (answers)
    def create_has_tag_edges()          # Post.Tags → Tag (parse pipe-delimited)
    def create_commented_edges()        # Comment.UserId → User, PostId → Post
    def create_voted_edges()            # Vote.UserId → User (if not NULL)
    def create_earned_badge_edges()     # Badge.UserId → User
    def create_linked_edges()           # PostLink relationships
```

**Vertices Created**:
- User vertex (from User document)
- Post vertex (from Post document, discriminate Question vs Answer via PostTypeId)
- Tag vertex (from Tag document)

**Edges Created**:
```python
# User → Post relationships
User -[ASKED]-> Post        # Post.PostTypeId = 1 (question)
User -[ANSWERED]-> Post     # Post.PostTypeId = 2 (answer)
User -[COMMENTED]-> Post    # From Comment.UserId → PostId
User -[VOTED]-> Post        # From Vote.UserId → PostId (if not NULL)

# Post → Post relationships
Post -[ANSWER_TO]-> Post    # Post.ParentId (answer to question)
Post -[LINKED_TO]-> Post    # From PostLink.PostId → RelatedPostId

# Post → Tag relationships
Post -[HAS_TAG]-> Tag       # Parse Post.Tags (pipe-delimited: "|python|sql|")

# User → Badge relationships
User -[EARNED_BADGE]-> Badge  # From Badge.UserId
```

**Graph Queries** (after Phase 2):
```sql
-- Find user's questions and answers
MATCH {User, as: u} -[ASKED|ANSWERED]-> {Post, as: p}
WHERE u.Id = 5
RETURN u.DisplayName, p.Title, p.Score

-- Find answers to a question
MATCH {Post, as: q} <-[ANSWER_TO]- {Post, as: a}
WHERE q.Id = 1000
RETURN a.Score, a.Body
ORDER BY a.Score DESC

-- Find posts by tag
MATCH {Post, as: p} -[HAS_TAG]-> {Tag, as: t}
WHERE t.TagName = 'python'
RETURN p.Title, p.Score

-- Find top contributors (users with most answers)
MATCH {User, as: u} -[ANSWERED]-> {Post, as: p}
RETURN u.DisplayName, count(p) as answer_count, u.Reputation
ORDER BY answer_count DESC
LIMIT 10
```

### **Phase 3: Vector Search (VectorBuilder class)**
Add embeddings for semantic search
```python
class VectorBuilder:
    """Generates embeddings and creates vector indexes"""
    def generate_post_embeddings()      # Post.Title + Body → embedding
    def generate_tag_embeddings()       # Tag.TagName + Excerpt → embedding
    def generate_user_embeddings()      # User.DisplayName + AboutMe → embedding
    def create_vector_indexes()         # HNSW indexes for each
    def semantic_search()               # Find similar posts/tags/users
```

**Embeddings**:
```python
# Post embeddings (duplicate question detection)
Post.embedding = embed(Post.Title + "\n" + Post.Body)  # 384 dims
CREATE VECTOR INDEX ON Post (embedding) HNSW

# Tag embeddings (related tags)
Tag.embedding = embed(Tag.TagName + "\n" + Tag.ExcerptPostId.Body)
CREATE VECTOR INDEX ON Tag (embedding) HNSW

# User embeddings (similar expertise)
User.embedding = embed(User.DisplayName + "\n" + User.AboutMe)
CREATE VECTOR INDEX ON User (embedding) HNSW
```

**Vector Queries** (after Phase 3):
```python
# Find duplicate/similar questions
query_post = db.query("SELECT FROM Post WHERE Id = 1000")
similar_posts = index.find_nearest(query_post.embedding, k=10)

# Find related tags
query_tag = db.query("SELECT FROM Tag WHERE TagName = 'python'")
related_tags = index.find_nearest(query_tag.embedding, k=10)

# Find users with similar expertise
query_user = db.query("SELECT FROM User WHERE Id = 5")
similar_users = index.find_nearest(query_user.embedding, k=10)
```

**Multi-Model Queries** (combine all three):
```sql
-- Find Python experts (graph + aggregation)
MATCH {User, as: u} -[ANSWERED]-> {Post, as: p} -[HAS_TAG]-> {Tag, as: t}
WHERE t.TagName = 'python' AND p.Score >= 5
RETURN u.DisplayName, count(p) as answers, sum(p.Score) as total_score
ORDER BY total_score DESC LIMIT 10

-- Similar unanswered questions (vector + document filtering)
-- 1. Find similar questions via vector search
-- 2. Filter by AcceptedAnswerId IS NULL
-- 3. Rank by Score

-- Trending topics (graph analytics on tag co-occurrence)
MATCH {Post, as: p} -[HAS_TAG]-> {Tag, as: t1},
      {Post, as: p} -[HAS_TAG]-> {Tag, as: t2}
WHERE t1 != t2
RETURN t1.TagName, t2.TagName, count(p) as co_occurrence
ORDER BY co_occurrence DESC LIMIT 20
```

## Class Architecture

```python
class StackOverflowDatabase:
    """Main orchestrator - manages all three phases"""
    def __init__(db_path, dataset_size)
    def run_full_pipeline()              # Execute all phases
    def run_phase_1_documents()          # Import documents only
    def run_phase_2_graph()              # Add graph layer
    def run_phase_3_vectors()            # Add vector search
    def validate_each_phase()            # Check counts, run sample queries
    def export_database()                # Export to JSONL for reproducibility

class SchemaBuilder:
    """Phase 1: Schema creation"""

class DocumentImporter:
    """Phase 1: XML import"""

class GraphBuilder:
    """Phase 2: Graph layer"""

class VectorBuilder:
    """Phase 3: Vector search"""
```

## Dataset Options & Performance

**Small Dataset (cs.stackexchange.com)** - RECOMMENDED FOR DEVELOPMENT:
- 105K posts, 138K users, 668 tags, 195K comments
- ~650MB XML, imports in ~2-5 minutes
- Perfect for development and testing

**Medium Dataset (stats.stackexchange.com)**:
- 425K posts, 345K users, 1.6K tags, 819K comments
- ~2.5GB XML, imports in ~10-20 minutes

**Large Dataset (stackoverflow.com)** - PRODUCTION SCALE:
- 59M posts, 20M users, 65K tags, ~100M comments
- ~325GB XML, imports in hours (97GB Posts.xml alone!)
- Requires 8GB+ JVM heap, production server setup

**Note**: Largest example, demonstrates all three models working together

### 8. **Server Mode: HTTP API + Studio** (Priority: HIGH)
**File**: `08_server_mode_rest_api.py`
**Target**: Backend developers, DevOps engineers
**Concepts**: Server startup, HTTP API access, Studio UI, remote access, embedded + HTTP simultaneously
**Why**: Essential for production deployment, debugging with Studio, remote access patterns
**Status**: 🚧 Planned
```python
# Start embedded ArcadeDB server
# Access via HTTP REST API (queries, commands)
# Open Studio web interface for visual debugging
# Demonstrate both embedded + HTTP access to same database
# Show server configuration and security settings
# Use databases from previous examples (01-07) for demonstration
```
**Note**: Final example - shows production deployment patterns

## Implementation Strategy

### Phase 1: Core Fundamentals (Examples 1-3) ✅ COMPLETE
- Simple document store ✅
- Graph basics ✅
- Vector search ✅ (experimental)

### Phase 2: Import Patterns with MovieLens (Examples 4-6) ✅ MOSTLY COMPLETE
- CSV → Documents ✅ (Example 4 complete - MovieLens dataset)
- CSV → Graph ✅ (Example 5 complete - MovieLens as graph with comprehensive benchmarking)
- Vector search on documents 🚧 (Example 6 planned - MovieLens movie similarity)

### Phase 3: Multi-Model Integration (Example 7)
- Stack Overflow Q&A multi-model 🚧 (Documents + Graph + Vectors)
- Alternative dataset options available

### Phase 4: Production Deployment (Example 8)
- Server mode & HTTP API 🚧 (Production patterns, Studio UI)

## Documentation Structure

Each example should have:

1. **Code file** (`examples/0X_name.py`):
   - Clear comments explaining each step
   - Self-contained (runs without other files)
   - Includes sample data generation
   - Cleanup at the end
   - ~100-300 lines (simplified examples at lower end)

2. **Documentation page** (`docs/examples/0X_name.md`):
   - What this example demonstrates
   - Real-world use case
   - Key concepts explained
   - Full code with detailed explanations
   - Expected output
   - "Try it yourself" modifications
   - Link to related API docs

3. **MkDocs navigation** (`mkdocs.yml`):
   - New "Examples" section in nav
   - Ordered by complexity
   - Tagged by user persona

## Success Criteria

- ✅ Each example runs without errors
- ✅ Examples are self-contained (no external dependencies except arcadedb)
- ✅ Clear progression from simple to advanced
- ✅ Cover all major features (document, graph, vector, import)
- ✅ Real-world use cases users can adapt
- ✅ Proper resource cleanup (no leaked DB handles)
- ✅ Documented in MkDocs with explanations

## Notes

- Focus on **thin wrapper** nature - we're wrapping Java APIs, not reimplementing
- Show **Java interop** where relevant (e.g., when Java objects are exposed)
- Emphasize **embedded** benefits - no network, fast, self-contained
- Include **performance tips** specific to JPype/JVM integration
- Make examples **copy-pasteable** for quick starts

## Related Test Files (for reference)

- `test_core.py` - Basic operations, transactions, graph, vector
- `test_server.py` - Server mode, HTTP API
- `test_importer.py` - CSV, JSON, Neo4j import
- `test_concurrency.py` - Threading, file locking
- `test_server_patterns.py` - Access patterns, embedded vs HTTP
- `test_gremlin.py` - Gremlin query language
