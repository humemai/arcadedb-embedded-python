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
from arcadedb_embedded import Importer

with arcadedb.create_database("import_demo") as db:
    # Create importer and import CSV to documents
    importer = Importer(db)

    importer.import_csv(
        file_path="data.csv",
        type_name="MyType",
        mapping={
            "id": "id",
            "name": "name",
            "value": "amount"
        }
    )
```

### Import with Type Conversion

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("import_demo") as db:
    importer = Importer(db)

    # Import with data type specification
    importer.import_csv(
        file_path="products.csv",
        type_name="Product",
        mapping={
            "product_id": ("id", int),
            "name": ("name", str),
            "price": ("price", float),
            "in_stock": ("inStock", bool)
        }
    )
```

### Bulk Import for Performance

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("import_demo") as db:
    # Use batch processing for large files
    importer = Importer(db)

    # Import in batches (importer handles transactions internally)
    importer.import_csv(
        file_path="large_dataset.csv",
        type_name="LargeType",
        batch_size=10000,  # Commit every 10k records
        mapping={"col1": "field1", "col2": "field2"}
    )
```

## Import Graph Data

### Create Vertices from CSV

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("graph_import_demo") as db:
    importer = Importer(db)

    # Import nodes
    importer.import_csv(
        file_path="users.csv",
        type_name="User",
        mapping={
            "user_id": "userId",
            "username": "name"
        },
        type_kind="VERTEX"
    )
```

### Create Edges from CSV

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.open_database("./graph_import_demo") as db:
    importer = Importer(db)

    # Import relationships
    importer.import_csv_edges(
        file_path="follows.csv",
        edge_type="Follows",
        from_vertex_type="User",
        to_vertex_type="User",
        from_field="follower_id",
        to_field="following_id"
    )
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
4. **Tune Batch Size**: Experiment with batch sizes (1000-10000 typical)

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("import_demo") as db:
    # Example: Optimized bulk import
    # Drop heavy indexes before bulk insert (replace with your index names)
    db.command("sql", "DROP INDEX MyType.id")

    importer = Importer(db)

    # Bulk import (importer handles transactions internally)
    importer.import_csv(
        file_path="huge_file.csv",
        type_name="MyType",
        batch_size=5000
    )

    # Recreate indexes after import (schema ops are auto-transactional)
    db.schema.create_index("MyType", ["id"], unique=True)
    db.command("sql", "REBUILD INDEX MyType.id")
```

## Database Migration

For migrating from other databases, see:
- **[Example 05](05_csv_import_graph.md)** - Neo4j to ArcadeDB migration pattern
- **[Importer API Reference](../api/importer.md)** - Full API documentation

## Additional Resources

- **[Importer API Documentation](../api/importer.md)** - Complete API reference
- **[Import Guide](../guide/import.md)** - In-depth import strategies
- **[Example 04: CSV Documents](04_csv_import_documents.md)** - Document import walkthrough
- **[Example 05: CSV Graph](05_csv_import_graph.md)** - Graph import walkthrough
- **[Performance Guide](../guide/operations.md)** - Optimization techniques

## Source Code

View the complete import example source code:
- [`examples/04_csv_import_documents.py`](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/04_csv_import_documents.py)
- [`examples/05_csv_import_graph.py`](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/05_csv_import_graph.py)
