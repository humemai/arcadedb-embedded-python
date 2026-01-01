# Importer API

The `Importer` class and convenience functions provide high-performance data import capabilities for ArcadeDB. The Java importer supports CSV/TSV and XML. For full-database migrations, use ArcadeDB's native JSONL export/import via the `IMPORT DATABASE file://...` SQL command (see JSONL example below).

## Overview

The importer uses streaming parsers for memory efficiency and performs batch transactions (default 1000 records per commit) for optimal performance. It can import data as documents, vertices, or edges depending on your schema needs.

**Supported Formats:**
- **CSV/TSV**: Comma or tab-separated values
- **XML**: Attribute-focused importer
- **ArcadeDB JSONL export/import**: Use `IMPORT DATABASE file://...` via SQL for full database moves (see example)

## Module Functions

Convenience functions for common import tasks without creating an `Importer` instance. These call the underlying Java importer (CSV/TSV, XML) or native SQL for full-database JSONL imports.

### `import_csv(database, file_path, type_name, **options)`

Import CSV or TSV files as documents, vertices, or edges.

**Parameters:**
- `database` (Database): Database instance
- `file_path` (str): Path to CSV/TSV file
- `type_name` (str): Target type name
- `**options`: Format-specific options
    - `delimiter` (str): Field delimiter (default: ',', use '\t' for TSV)
    - `header` (bool): File has header row (default: True)
    - `commit_every` (int): Records per transaction (default: 1000)
    - `vertex_type` (str): Import as vertices (optional)
    - `edge_type` (str): Import as edges (optional)
    - `from_property` (str): Source column for edges (default: 'from')
    - `to_property` (str): Target column for edges (default: 'to')
    - `verbose` (bool): Print errors during import (default: False)

**Examples:**

**Import as Documents:**
```python
stats = arcadedb.import_csv(db, "people.csv", "Person")
```

**Import as Vertices:**
```python
stats = arcadedb.import_csv(
        db, "users.csv", "User",
        vertex_type="User",
        commit_every=500
)
```

**Import as Edges:**
```python
stats = arcadedb.import_csv(
        db, "follows.csv", "Follows",
        edge_type="Follows",
        from_property="user_rid",
        to_property="follows_rid",
        header=True
)
```

**Import TSV:**
```python
stats = arcadedb.import_csv(
        db, "data.tsv", "Data",
        delimiter='\t'
)
```

### ArcadeDB JSONL import (native SQL)

Use SQL `IMPORT DATABASE file://...` for JSONL exports produced by ArcadeDB. This preserves schema and data and is recommended for full migrations.

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./restored_db")
db.command("sql", "IMPORT DATABASE file:///tmp/export.jsonl.tgz WITH commitEvery = 50000")
db.close()
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

### `import_file(file_path, format_type=None, type_name=None, commit_every=1000, **options)`

Import data from a file with auto-detection or explicit format specification.

**Parameters:**
- `file_path` (str): Path to file to import
- `format_type` (Optional[str]): Format type ('csv', 'xml')
    - If None, auto-detects from file extension:
        - `.csv`, `.tsv` → 'csv'
        - `.xml` → 'xml'
- `type_name` (Optional[str]): Target type name (required for CSV)
- `commit_every` (int): Records per transaction (default: 1000)
- `**options`: Format-specific options (see individual format documentation)

**Returns:**
- `Dict[str, Any]`: Import statistics

**Raises:**
- `ArcadeDBError`: If file not found, format unsupported, or import fails

**Example:**
```python
importer = Importer(db)

# Auto-detect format from extension
stats = importer.import_file("data.json")
stats = importer.import_file("users.csv", type_name="User")

# Explicit format
stats = importer.import_file(
    "data.txt",
    format_type='csv',
    type_name="Record",
    delimiter='\t'
)
```

---

## Format-Specific Details

### JSON Format

**File Structure:**
- Single JSON object: `{...}`
- Array of objects: `[{...}, {...}]`
- Multiple root objects: `{...}\n{...}`

**Options:**
- `mapping` (Dict): Map JSON paths to database types (advanced)

**Type Inference:** The importer uses Java's `JSONImporterFormat` which automatically creates schema based on JSON structure.

**Example:**
```python
# data.json:
# [
#   {"name": "Alice", "age": 30, "city": "NYC"},
#   {"name": "Bob", "age": 25, "city": "LA"}
# ]

stats = arcadedb.import_json(db, "data.json", commit_every=1000)
```

---

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
- `vertex_type` (str): Import as vertices
- `edge_type` (str): Import as edges (requires `from_property` and `to_property`)
- `from_property` (str): Column name for edge source RID (default: 'from')
- `to_property` (str): Column name for edge target RID (default: 'to')

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
    vertex_type="User",
    delimiter=','
)
```

**Edges Example:**
```python
# relationships.csv:
# from_rid,to_rid,type,since
# #1:0,#1:1,FRIEND,2020
# #1:1,#1:2,COLLEAGUE,2021

# First create the schema
db.command("sql", "CREATE EDGE TYPE Relationship")

# Then import
stats = arcadedb.import_csv(
    db, "relationships.csv", "Relationship",
    edge_type="Relationship",
    from_property="from_rid",
    to_property="to_rid"
)
```

**Important for Edge Imports:**
- CSV must have header row (`header=True`)
- Source and target columns must contain valid RIDs (e.g., `#1:0`)
- Edge type must exist in schema before import
- Additional columns become edge properties

## Performance Tips

### Batch Size

The `commit_every` parameter controls transaction size:

```python
# Smaller batches (safer, slower)
stats = arcadedb.import_csv(db, "data.csv", "Data", commit_every=100)

# Larger batches (faster, more memory)
stats = arcadedb.import_csv(db, "data.csv", "Data", commit_every=5000)
```

**Guidelines:**
- **Small files (<10K records)**: 1000-2000
- **Medium files (10K-1M records)**: 2000-5000
- **Large files (>1M records)**: 5000-10000

### Memory Efficiency

The importer uses streaming parsers:
- **CSV**: Line-by-line processing (very efficient)
- **XML**: Streaming parser; keep attributes consistent across rows

### Schema Pre-Creation

Create types before import for better performance:

```python
# Create schema first
db.command("sql", """
    CREATE DOCUMENT TYPE Person
    IF NOT EXISTS
""")
db.command("sql", """
    CREATE PROPERTY Person.email STRING
""")
db.command("sql", """
    CREATE INDEX ON Person (email) UNIQUE
""")

# Then import (type already exists)
stats = arcadedb.import_csv(db, "people.csv", "Person")
```

### Indexing Strategy

Create indexes AFTER import for faster loading:

```python
# Import without indexes
stats = arcadedb.import_csv(db, "users.csv", "User", vertex_type="User")

# Create indexes after import
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
db.command("sql", "CREATE INDEX ON User (username) UNIQUE")
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

# Open or create database
db = arcadedb.create_database("./import_demo")

# Create schema
db.command("sql", "CREATE DOCUMENT TYPE User")
db.command("sql", "CREATE VERTEX TYPE Person")
db.command("sql", "CREATE EDGE TYPE Knows")

# Import documents from JSON
stats1 = arcadedb.import_json(db, "users.json")
print(f"Users: {stats1['documents']}")

# Import vertices from CSV
stats2 = arcadedb.import_csv(
    db, "people.csv", "Person",
    vertex_type="Person"
)
print(f"People: {stats2['vertices']}")

# Import edges from CSV
stats3 = arcadedb.import_csv(
    db, "relationships.csv", "Knows",
    edge_type="Knows",
    from_property="person1_rid",
    to_property="person2_rid"
)
print(f"Relationships: {stats3['edges']}")

db.close()
```

### Large-Scale Import with Progress Tracking

```python
import arcadedb_embedded as arcadedb
import time

db = arcadedb.create_database("./large_import")

# Create schema
db.command("sql", "CREATE VERTEX TYPE Product")

# Import with progress monitoring
print("Starting import...")
start = time.time()

stats = arcadedb.import_csv(
    db, "products.csv", "Product",
    vertex_type="Product",
    commit_every=10000,  # Large batches for performance
    verbose=True  # Show errors
)

elapsed = time.time() - start

print(f"\nImport complete!")
print(f"Records: {stats['vertices']:,}")
print(f"Errors: {stats['errors']}")
print(f"Time: {elapsed:.2f}s")
print(f"Rate: {stats['vertices'] / elapsed:.0f} records/sec")

# Create indexes after import
print("\nCreating indexes...")
db.command("sql", "CREATE INDEX ON Product (sku) UNIQUE")
db.command("sql", "CREATE INDEX ON Product (category) NOTUNIQUE")

db.close()
```

### ArcadeDB JSONL Import (native export)

Use ArcadeDB's built-in SQL command to import JSONL exports created by `EXPORT DATABASE`.

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./restored_db")
import_path = "/exports/mydb.jsonl.tgz"  # JSONL export created by ArcadeDB

# Use SQL IMPORT DATABASE with optional tuning parameters
db.command("sql", f"IMPORT DATABASE file://{import_path} WITH commitEvery = 50000")

print("Import complete!")
db.close()
```

This approach preserves the full database (schema + data) and is the recommended path for large migrations or round-tripping ArcadeDB exports.

---

## See Also

- [Data Import Guide](../guide/import.md) - Comprehensive import strategies
- [Database API](database.md) - Database operations
- [Graph Operations Guide](../guide/graphs.md) - Working with graph data
- [Import Examples](../examples/import.md) - More practical examples
