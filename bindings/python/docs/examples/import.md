# Data Import Examples

This page covers examples for importing data into ArcadeDB from various sources.

## CSV Import Examples

### Import Tabular Data (Documents)

**[Example 04 - CSV Import: Documents](04_csv_import_documents.md)**

Learn how to import CSV files as documents:

- Using the Importer API
- Defining schema mappings
- Handling data transformations
- Performance optimization

### Import Graph Data

**[Example 05 - CSV Import: Graph Database](05_csv_import_graph.md)**

Learn how to import CSV files as graph vertices and edges:

- Creating vertices from CSV
- Creating edges from relationships
- Bulk import optimization
- Real-world graph migration

## Importer API

The ArcadeDB Python bindings provide a powerful `Importer` class for efficient data loading.

### Basic CSV Import

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import import_csv

with arcadedb.create_database("./import_demo") as db:
    # Convenience helper: auto-detect CSV, create schema on-the-fly
    stats = import_csv(
        db,
        file_path="data.csv",
        type_name="MyType",
        commitEvery=5000,
    )
    print(stats)
```

### Import with Schema Types

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import import_csv

with arcadedb.create_database("./import_demo") as db:
    # Define schema up front so imports get typed correctly
    with db.transaction():
        db.schema.create_document_type("Product")
        db.schema.create_property("Product", "id", arcadedb.PropertyType.INTEGER)
        db.schema.create_property("Product", "name", arcadedb.PropertyType.STRING)
        db.schema.create_property("Product", "price", arcadedb.PropertyType.FLOAT)
        db.schema.create_property("Product", "inStock", arcadedb.PropertyType.BOOLEAN)

    stats = import_csv(
        db,
        file_path="products.csv",
        type_name="Product",
        commitEvery=5000,
    )
    print(stats)
```

### Bulk Import for Performance

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import import_csv

with arcadedb.create_database("./import_demo") as db:
    # Import in batches (import_csv handles commitEvery internally)
    stats = import_csv(
        db,
        file_path="large_dataset.csv",
        type_name="LargeType",
        commitEvery=10000,  # Commit every 10k records
        parallel=4,  # Optional: parallel importer threads
    )
    print(stats)
```

## Import Graph Data

### Create Vertices from CSV

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./graph_import_demo") as db:
    # Import vertices (CSV columns become properties)
    stats = arcadedb.import_csv(
        db,
        file_path="users.csv",
        type_name="User",
        import_type="vertices",
        typeIdProperty="userId",
        commitEvery=5000,
    )
    print(stats)
```

### Create Edges from CSV

```python
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./graph_import_demo") as db:
    # Import edges (FK resolution using typeIdProperty)
    stats = arcadedb.import_csv(
        db,
        file_path="follows.csv",
        type_name="Follows",
        import_type="edges",
        edgeFromField="follower_id",
        edgeToField="following_id",
        typeIdProperty="userId",
        commitEvery=5000,
    )
    print(stats)
```

## Multi-Model Import

Combine different import strategies for multi-model databases:

**[Example 07 - StackOverflow Multi-Model](07_stackoverflow_multimodel.md)**

See a complete example that combines:

- Document storage for questions/answers
- Graph relationships for user connections
- Vector embeddings for semantic search

## Performance Tips

### Optimize Import Speed

1. **Use Transactions**: Batch multiple inserts in one transaction
2. **Disable Indexes**: Temporarily disable indexes during bulk import
3. **Use Parallel Processing**: Split large files and import in parallel
4. **Tune commitEvery**: Adjust commitEvery (e.g., 1000-10000) for performance vs. transaction size

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("./import_demo") as db:
    # Example: Optimized bulk import
    # Drop heavy indexes before bulk insert (replace with your index names)
    db.schema.drop_index("MyType[id]")

    importer = Importer(db)

    # Bulk import (importer handles transactions internally)
    importer.import_file(
        file_path="huge_file.csv",
        type_name="MyType",
        commitEvery=5000
    )

    # Recreate indexes after import (schema ops are auto-transactional)
    db.schema.create_index("MyType", ["id"], unique=True)
```

## Additional Resources

- **[Importer API Documentation](../api/importer.md)** - Complete API reference
- **[Import Guide](../guide/import.md)** - In-depth import strategies
- **[Performance Guide](../guide/operations.md)** - Optimization techniques

## Source Code

View the complete import example source code:

- [`examples/04_csv_import_documents.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/04_csv_import_documents.py)
- [`examples/05_csv_import_graph.py`]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/05_csv_import_graph.py)
