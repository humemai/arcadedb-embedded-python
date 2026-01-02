# Exporter Tests

The `test_exporter.py` file contains **5 test classes** covering database export to JSONL, GraphML, GraphSON, and CSV formats.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_exporter.py){ .md-button }

## Overview

Exporter tests cover:

- ✅ **JSONL Export** - Newline-delimited JSON format
- ✅ **GraphML Export** - XML-based graph format
- ✅ **GraphSON Export** - TinkerPop JSON format
- ✅ **CSV Export** - Comma-separated values
- ✅ **Round-Trip** - Export and re-import verification
- ✅ **Batch Integration** - Exporting with BatchContext
- ✅ **All Data Types** - Testing type preservation

## Test Classes

### TestDatabaseExport
Tests full database export to various formats.

**Tests:**
- Export entire database to JSONL
- Export with progress callback
- Selective export by type
- Export with query filter

**Pattern:**
```python
from arcadedb_embedded.exporter import export_database

# Export entire database
export_database(db, "./export.jsonl", format="jsonl")

# Export specific types
export_database(db, "./users.jsonl", types=["User"], format="jsonl")

# Export with query
export_database(
    db,
    "./active.jsonl",
    query="SELECT FROM User WHERE active = true",
    format="jsonl"
)
```

---

### TestCSVExport
Tests CSV export functionality.

**Tests:**
- Export single type to CSV
- CSV header generation
- Property value escaping
- Multiple types to separate CSV files

**Pattern:**
```python
# Export to CSV
export_database(db, "./users.csv", types=["User"], format="csv")

# Output: @rid,@type,username,age,email
```

---

### TestRoundTripExport
Tests export and re-import verification.

**Tests:**
- Export database to JSONL
- Import into new database
- Verify record count matches
- Verify properties preserved

**Pattern:**
```python
# Export
export_database(db1, "./export.jsonl", format="jsonl")

# Import
import json
with open("./export.jsonl") as f:
    with db2.transaction():
        for line in f:
            data = json.loads(line)
            # Recreate records

# Verify counts match
assert db1.count_type("User") == db2.count_type("User")
```

---

### TestExportWithBatchContext
Tests integration with BatchContext.

**Tests:**
- Creating large dataset with batch
- Exporting batch-created data
- Verifying export completeness

**Pattern:**
```python
# Create with batch
with db.batch_context() as batch:
    for i in range(10000):
        batch.create_vertex("User", userId=i)

# Export
export_database(db, "./batch_export.jsonl")
```

---

### TestAllDataTypes
Tests exporting all ArcadeDB data types.

**Tests:**
- STRING, INTEGER, LONG, FLOAT, DOUBLE
- BOOLEAN, DATE, DATETIME
- LIST, MAP, EMBEDDED
- BINARY data
- Type preservation during export

**Pattern:**
```python
# Create record with all types
vertex = db.new_vertex("AllTypes")
vertex.set("str_val", "text")
vertex.set("int_val", 42)
vertex.set("bool_val", True)
vertex.set("list_val", [1, 2, 3])
vertex.set("map_val", {"key": "value"})
vertex.save()

# Export
export_database(db, "./types.jsonl")

# Verify types preserved
```

## Test Patterns

### Basic Export
```python
from arcadedb_embedded.exporter import export_database

export_database(db, "./output.jsonl", format="jsonl")
```

### Selective Export
```python
# By type
export_database(db, "./users.jsonl", types=["User", "Admin"])

# By query
export_database(
    db,
    "./recent.jsonl",
    query="SELECT FROM Event WHERE timestamp > date('2024-01-01')"
)
```

### With Progress
```python
def progress(current, total):
    print(f"{current}/{total}")

export_database(db, "./export.jsonl", progress_callback=progress)
```

## Common Assertions

```python
# File exists
assert os.path.exists("./export.jsonl")

# File not empty
assert os.path.getsize("./export.jsonl") > 0

# Record count matches
with open("./export.jsonl") as f:
    line_count = sum(1 for _ in f)
assert line_count == expected_count
```

## Key Takeaways

1. **JSONL for backups** - Best format for re-import
2. **CSV for single types** - Good for spreadsheets
3. **GraphML for viz** - Visualization tools
4. **Filter exports** - Use types or queries
5. **Track progress** - Use callbacks for large exports

## See Also

- **[Exporter API](../../api/exporter.md)** - Full API reference
- **[Importer Tests](test-importer.md)** - Import functionality
- **[Example 05: CSV Import](../../examples/05_csv_import_graph.md)** - Import/export patterns
