# Importer API

The `Importer` class and convenience functions provide high-performance data import
capabilities for ArcadeDB. For full-database migrations, use ArcadeDB's native JSONL
export/import via the `IMPORT DATABASE file://...` SQL command (see JSONL example
below).

## Overview

The importer uses streaming parsers for memory efficiency and performs batch
transactions (default 1000 records per commit) for optimal performance. It can import
data as documents, vertices, or edges depending on your schema needs.

**Supported Formats:**

- **CSV/TSV**: Comma or tab-separated values (recommended for bulk imports)
- **ArcadeDB JSONL export/import**: Use `IMPORT DATABASE file://...` via SQL for full database moves (see example)
- **XML**: Supports document/vertex imports via Java importer

## Module Functions

Convenience functions for common import tasks without creating an `Importer` instance.
These call the underlying Java importer (CSV/TSV) or native SQL for full-database JSONL
imports.

### `import_csv(database, file_path, type_name, **options)`

Import CSV or TSV files as documents, vertices, or edges.

**Parameters:**

- `database` (Database): Database instance
- `file_path` (str): Path to CSV/TSV file
- `type_name` (str): Target type name
- `**options`: Format-specific options
    - `delimiter` (str): Field delimiter (default: ',', use '\t' for TSV)
    - `header` (bool): File has header row (default: True)
    - `commitEvery` (int): Records per transaction (default: 5000)
    - `import_type` (str): `"documents"` (default), `"vertices"`, or `"edges"`
    - `typeIdProperty` (str): Unique ID column when importing vertices/edges (e.g., "id")
    - `typeIdType` (str): Type of the ID column (e.g., "String", "Long")
    - `edgeFromField` (str): Column name for edge source IDs/RIDs (REQUIRED for edges)
    - `edgeToField` (str): Column name for edge target IDs/RIDs (REQUIRED for edges)
    - `verboseLevel` (int): Java importer logging level 0-3 (default: 2)

**Examples:**

**Import as Documents:**

```python
stats = arcadedb.import_csv(db, "people.csv", "Person")
```

**Import as Vertices:**

```python
stats = arcadedb.import_csv(
    db, "users.csv", "User",
    import_type="vertices",
    typeIdProperty="id",
    typeIdType="String",
    commitEvery=500
)
```

**Import as Edges:**

```python
stats = arcadedb.import_csv(
    db, "follows.csv", "Follows",
    import_type="edges",
    edgeFromField="from_rid",
    edgeToField="to_rid",
    # REQUIRED to enable FK resolution when using IDs (and required by API)
    typeIdProperty="id",
    typeIdType="String"
)
```

**Full-Database Import (JSONL):**

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./restored_db") as db:
    db.command("sql", "IMPORT DATABASE file:///export.jsonl.tgz WITH commitEvery = 50000")
```

For XML imports, use the `Importer` class directly (see below) with `format_type='xml'`.

---

## Importer Class

For more control over the import process, use the `Importer` class directly.

### `Importer(database)`

**Constructor:**

**Parameters:**

- `database` (Database): Database instance to import into

**Example:**

```python
from arcadedb_embedded import Importer

db = arcadedb.open_database("./mydb")
importer = Importer(db)
```

---

### `import_file(file_path, format_type=None, import_type="documents", type_name=None, **options)`

Import data from a file with auto-detection or explicit format specification.

**Parameters:**

- `file_path` (str): Path to file to import
- `format_type` (Optional[str]): Format type ('csv', 'xml'); auto-detected from extension if None
- `import_type` (str): `"documents"` (default), `"vertices"`, or `"edges"`
- `type_name` (Optional[str]): Target type name
- `**options`: Format-specific options (e.g., `delimiter`, `header`, `commitEvery`, `typeIdProperty`, `edgeFromField`, `edgeToField`)

**Returns:**

- `Dict[str, Any]`: Import statistics

**Raises:**

- `ArcadeDBError`: If file not found, format unsupported, or import fails

**Example:**

```python
importer = Importer(db)

# Import CSV as vertices
stats = importer.import_file(
    file_path="users.csv",
    import_type="vertices",
    type_name="User",
    typeIdProperty="id",
    commitEvery=1000
)

# Import CSV as edges (RID-based)
stats = importer.import_file(
    file_path="follows.csv",
    import_type="edges",
    type_name="Follows",
    edgeFromField="from_rid",
    edgeToField="to_rid",
    typeIdProperty="id"
)
```

---

## Format-Specific Details

### CSV Format

**File Structure:**

```csv
name,age,city
Alice,30,NYC
Bob,25,LA
```

**Options:**

- `delimiter` (str): Field separator (default: ',')
    - Use `'\t'` for tab-separated (TSV)
- `header` (bool): First row contains column names (default: True)
    - If False, columns named `col_0`, `col_1`, etc.
- `import_type` (str): `"documents"`, `"vertices"`, or `"edges"`
- `typeIdProperty` (str): Unique ID column for vertices/edges
- `typeIdType` (str): Type of the ID column (e.g., `String`, `Long`)
- `edgeFromField` (str): Column for edge source IDs/RIDs
- `edgeToField` (str): Column for edge target IDs/RIDs

**Type Inference:** String values are automatically converted:

- `"true"`, `"false"` → boolean
- Valid integers → int
- Valid floats → float
- Everything else → string
- Empty strings → None

**Documents Example:**

```python
# people.csv:
# name,age,email
# Alice,30,alice@example.com
# Bob,25,bob@example.com

stats = arcadedb.import_csv(db, "people.csv", "Person")
```

**Vertices Example:**

```python
stats = arcadedb.import_csv(
    db, "users.csv", "User",
    import_type="vertices",
    typeIdProperty="id",
    delimiter=','
)
```

**Edges Example:**

```python
# relationships.csv:
# from_rid,to_rid,type,since
# #1:0,#1:1,FRIEND,2020
# #1:1,#1:2,COLLEAGUE,2021

# First create the schema (Schema API is preferred for embedded use)
db.schema.create_edge_type("Relationship")

# Then import (edges)
stats = arcadedb.import_csv(
    db, "relationships.csv", "Relationship",
    import_type="edges",
    edgeFromField="from_rid",
    edgeToField="to_rid",
    # Required when resolving vertices by ID
    typeIdProperty="id",
    typeIdType="String",
)
```

**Important for Edge Imports:**

- CSV must have header row (`header=True`)
- Source and target columns must contain valid RIDs (e.g., `#1:0`)
- Edge type must exist in schema before import
- Additional columns become edge properties

## Performance Tips

### Batch Size

The `commitEvery` parameter controls transaction size:

```python
# Smaller batches (safer, slower)
stats = arcadedb.import_csv(db, "data.csv", "Data", commitEvery=100)

# Larger batches (faster, more memory)
stats = arcadedb.import_csv(db, "data.csv", "Data", commitEvery=5000)
```

**Guidelines:**

- **Small files (<10K records)**: 1000-2000
- **Medium files (10K-1M records)**: 2000-5000
- **Large files (>1M records)**: 5000-10000

### Memory Efficiency

The importer uses streaming parsers:

- **CSV**: Line-by-line processing (very efficient)
- **XML**: Streaming parser; attributes and first-level child elements are supported

### XML Tips

For XML imports, prefer attributes for data fields and use `objectNestLevel`
to target the correct nesting level (for example, `<posts><row .../></posts>`
uses `objectNestLevel=1`).

### Schema Pre-Creation

Create types before import for better performance:

```python
# Create schema first (Schema API is auto-transactional)
db.schema.create_document_type("Person")
db.schema.create_property("Person", "email", "STRING")
db.schema.create_index("Person", ["email"], unique=True)

# Then import (type already exists)
stats = arcadedb.import_csv(db, "people.csv", "Person")
```

### Indexing Strategy

Create indexes AFTER import for faster loading:

```python
# Import without indexes (vertices)
stats = arcadedb.import_csv(
    db, "users.csv", "User",
    import_type="vertices",
    typeIdProperty="id"
)

# Create indexes after import (Schema API)
db.schema.create_index("User", ["email"], unique=True)
db.schema.create_index("User", ["username"], unique=True)
```

---

## Error Handling

The importer continues on row-level errors and reports them in statistics:

```python
stats = arcadedb.import_csv(
    db, "data.csv", "Data",
    verbose=True  # Print errors as they occur
)

if stats['errors'] > 0:
    print(f"Warning: {stats['errors']} records failed to import")
    print(f"Successfully imported: {stats['documents'] + stats['vertices']}")
```

**Common Errors:**

- **Type mismatch**: Value doesn't match schema constraint
- **Missing required fields**: Schema requires field not in data
- **Invalid RIDs** (edges): Referenced vertex doesn't exist
- **JSON parse errors**: Malformed JSON
- **Encoding issues**: Non-UTF-8 characters

**Error Recovery:**

```python
try:
    stats = importer.import_file("data.csv", type_name="Data")
except arcadedb.ArcadeDBError as e:
    print(f"Import failed: {e}")
    # File not found, format error, or critical failure
```

---

## Complete Examples

### Multi-Format Import Pipeline

```python
import arcadedb_embedded as arcadedb

# Open or create database (auto-closes)
with arcadedb.create_database("./import_demo") as db:
    # Create schema with embedded API
    db.schema.create_vertex_type("Person")
    db.schema.create_edge_type("Knows")

    # Import vertices from CSV
    stats = arcadedb.import_csv(
        db, "people.csv", "Person",
        import_type="vertices",
        typeIdProperty="id",
    )
    print(f"People: {stats['vertices']}")

    # Import edges from CSV
    stats2 = arcadedb.import_csv(
        db, "relationships.csv", "Knows",
        import_type="edges",
        edgeFromField="person1_id",
        edgeToField="person2_id",
        typeIdProperty="id",
        typeIdType="String",
    )
    print(f"Relationships: {stats2['edges']}")
```

### Large-Scale Import with Progress Tracking

```python
import arcadedb_embedded as arcadedb
import time

with arcadedb.create_database("./large_import") as db:
    # Create schema with embedded API
    db.schema.create_vertex_type("Product")

    # Import with progress monitoring
    print("Starting import...")
    start = time.time()

    stats = arcadedb.import_csv(
        db, "products.csv", "Product",
        import_type="vertices",
        typeIdProperty="id",
        commitEvery=10000,  # Large batches for performance
        verboseLevel=2  # Show importer logs
    )

    elapsed = time.time() - start

    print(f"\nImport complete!")
    print(f"Records: {stats['vertices']:,}")
    print(f"Errors: {stats['errors']}")
    print(f"Time: {elapsed:.2f}s")
    print(f"Rate: {stats['vertices'] / elapsed:.0f} records/sec")

    # Create indexes after import
```

### ArcadeDB JSONL Import (native export)

Use ArcadeDB's built-in SQL command to import JSONL exports created by `EXPORT DATABASE`.

```python
import arcadedb_embedded as arcadedb

import_path = "/exports/mydb.jsonl.tgz"  # JSONL export created by ArcadeDB

# Use context manager for lifecycle
with arcadedb.create_database("./restored_db") as db:
    # Use SQL IMPORT DATABASE with optional tuning parameters
    db.command("sql", f"IMPORT DATABASE file://{import_path} WITH commitEvery = 50000")

    print("Import complete!")
```

This approach preserves the full database (schema + data) and is the recommended path for large migrations or round-tripping ArcadeDB exports.

---

## See Also

- [Data Import Guide](../guide/import.md) - Comprehensive import strategies
- [Database API](database.md) - Database operations
- [Graph Operations Guide](../guide/graphs.md) - Working with graph data
- [Import Examples](../examples/import.md) - More practical examples
