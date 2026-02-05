# Example 07: Stack Overflow Multi-Model Database

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/07_stackoverflow_multimodel.py){ .md-button }

This example demonstrates a complete **multi-model workflow** using the Stack Overflow
data dump. It combines **Documents**, **Graph**, and **Vectors** into a single cohesive
system, showcasing ArcadeDB's true multi-model capabilities.

## 🎯 Goals

1.  **Phase 1: Document Import**: Import XML data (Posts, Users, Tags, Comments, Votes) into ArcadeDB documents.
2.  **Phase 2: Graph Creation**: Build a graph by creating edges between documents.
3.  **Phase 3: Vector Embeddings**: Generate embeddings for Posts and Tags to enable semantic search.
4.  **Phase 4: Analytics**: Perform complex analytics using SQL, OpenCypher, and Vector Search.

## 📊 Dataset

The example supports multiple dataset sizes from the [Stack Exchange Data Dump](https://archive.org/details/stackexchange).

**Note:** Download the dataset first with `python download_data.py stackoverflow-<size>` before running this example.

| Dataset | Size (XML) | Records | Recommended Heap |
| :--- | :--- | :--- | :--- |
| **Tiny** (`cs.stackexchange.com`) | ~34 MB | ~100K | 2 GB |
| **Small** (`stats.stackexchange.com`) | ~642 MB | ~1.5M | 8 GB |
| **Medium** (`stackoverflow.com` subset) | ~2.9 GB | ~5M | 32 GB |
| **Large** (`stackoverflow.com` full) | ~323 GB | ~350M | 64+ GB |

## 🚀 Usage

Run the example from the `examples/` directory:

```bash
cd bindings/python/examples

# Run all phases with the small dataset
python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phases 1 2 3 4

# Increase JVM heap for larger datasets
python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phases 1 2 3 4 --heap-size 8g

# Run only Phase 1 (Import)
python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phases 1
```

## 🏗️ Architecture

### Phase 1: Document Import (XML → Documents)

We use ArcadeDB’s **Java XML importer** (via Python bindings) for fast, streaming XML import.
The script still uses `lxml` to analyze schemas and create types/properties before import.

> **Note on XML limits**: Stack Exchange XML may exceed the JDK’s default entity size limits.
> The Python bindings relax these XML limits by default when starting the JVM. If you pass
> custom JVM args, keep the `jdk.xml.*` flags (or keep `disable_xml_limits=True`).

**Schema:**

- **Post**: `Id`, `Title`, `Body`, `Score`, `ViewCount`, `CreationDate`, ...
- **User**: `Id`, `DisplayName`, `Reputation`, `AboutMe`, ...
- **Tag**: `Id`, `TagName`, `Count`, ...
- **Comment**: `Id`, `PostId`, `UserId`, `Text`, ...
- **Vote**: `Id`, `PostId`, `UserId`, `VoteTypeId`, ...

**Key Techniques:**

- **Java XML Importer**: Uses ArcadeDB’s production importer for streaming XML ingestion.
- **Schema Analysis**: Uses `lxml` to infer fields/types and pre-create document types.
- **Batching**: Uses importer batch commits for high-throughput inserts.

### Phase 2: Graph Creation (Documents → Graph)

We transform the document store into a graph by creating relationships.

**Edges:**

- `User -[ASKED]-> Post` (Question)
- `User -[ANSWERED]-> Post` (Answer)
- `Post -[ANSWER_TO]-> Post` (Answer links to Question)
- `Post -[HAS_TAG]-> Tag`
- `User -[COMMENTED]-> Post`
- `User -[VOTED]-> Post`

**Key Techniques:**

- **RID-Based Pagination**: Efficiently iterates through millions of records using `@rid > last_rid`.
- **Index-Based Lookups**: Uses `lookupByKey` (O(1)) instead of SQL `IN` (O(N)) for massive speedups in vertex resolution.
- **Nested Queries**: Prevents data loss during pagination by decoupling the scan (RID-based) from the filter (SQL-based).

### Phase 3: Vector Embeddings (Graph → Vectors)

We add a semantic layer by generating embeddings for text content.

**Embeddings:**

- **Post**: `Title` + `Body` → 384-dimensional vector.
- **Tag**: `TagName` → 384-dimensional vector.

**Key Techniques:**

- **JVector**: Uses state-of-the-art graph-based indexing (HNSW + DiskANN/Vamana) for fast approximate nearest neighbor search.
- **Sentence Transformers**: Uses `all-MiniLM-L6-v2` (or similar) to generate high-quality embeddings.

### Phase 4: Analytics (Multi-Model Queries)

We demonstrate the power of combining all three models.

**Example Queries:**

1.  **Graph**: "Find the top 10 users who answered questions about 'python'."
2.  **Vector**: "Find questions semantically similar to 'How to parse XML in Python?'"
3.  **Hybrid**: "Find similar questions (Vector) that have a score > 10 (Document) and were asked by high-reputation users (Graph)."

## 💡 Key Learnings

1.  **Pagination Matters**: When iterating over millions of records, standard `OFFSET/LIMIT` is too slow. Use **RID-based pagination** (`WHERE @rid > :last_rid LIMIT :batch_size`).
2.  **Filter Carefully**: When combining RID pagination with SQL filters, use **nested queries** to ensure you don't skip records due to sparse matches.
3.  **Index Lookups**: For graph creation, always use **index lookups** (`lookupByKey`) to find vertices. It is orders of magnitude faster than SQL queries.
4.  **Batching**: Always use batching (`BatchContext`) for imports and updates to minimize transaction overhead.
