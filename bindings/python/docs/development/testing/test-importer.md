# Data Import Tests

The `test_importer.py` file contains **16 tests** covering CSV data import.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_importer.py){ .md-button }

## Overview

ArcadeDB Python bindings provide built-in importers for:

- ✅ **CSV** - Import as documents, vertices, or edges with batch transactions
- ✅ **ArcadeDB JSONL** - Full database import via `IMPORT DATABASE` SQL command

All importers support:

- Batch transaction commits (default: 1000 records)
- Type inference (CSV: string → int/float/bool/None)
- Error handling and statistics

## Import Capabilities Matrix

| Format | Documents | Vertices | Edges | Type Inference |
|--------|-----------|----------|-------|----------------|
| CSV | ✅ | ✅ | ✅ | ✅ |
| ArcadeDB JSONL | ✅ | ✅ | ✅ | ✅ (preserved from export) |

## Quick Start Examples

### CSV Import

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    # Create schema first (matches tested flow)
    db.schema.create_document_type("Person")

    stats = arcadedb.import_csv(
        db,
        "data.csv",
        type_name="Person",
    )
    print(stats)
```

### ArcadeDB JSONL Import

```python
# Import full database from JSONL export
with arcadedb.create_database("./restored_db") as db:
    db.command("sql", "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000")
```

## Test Cases

### CSV Import Tests (16 tests)

#### 1. CSV as Documents

```python
# Create CSV file
csv_content = """name,age,city
Alice,30,New York
Bob,25,Los Angeles
Charlie,35,Chicago"""

# Import
stats = arcadedb.import_csv(
    db,
    "people.csv",
    type_name="Person"
)

# Verify
result = db.query("sql", "SELECT FROM Person")
assert len(list(result)) == 3
```

#### 2. CSV as Vertices

```python
csv_content = """id,name,age
1,Alice,30
2,Bob,25"""

stats = arcadedb.import_csv(
    db,
    "people.csv",
    type_name="Person",
    import_type="vertices",
    typeIdProperty="id"
)

# Verify vertices created
result = db.query("sql", "SELECT FROM Person")
for person in result:
    assert hasattr(person, 'out')  # Vertices have out() method
```

#### 3. CSV as Edges

```python
# Requires pre-existing vertices with RIDs
csv_content = """from_rid,to_rid,since
#1:0,#1:1,2020
#1:1,#1:2,2021"""

stats = arcadedb.import_csv(
    db,
    "relationships.csv",
    type_name="Knows",
    import_type="edges",
    from_property="from_rid",
    to_property="to_rid"
)
```

#### 4. CSV with Custom Delimiter

```python
csv_content = """name|age|city
Alice|30|NYC"""

stats = arcadedb.import_csv(
    db,
    "data.csv",
    type_name="Person",
    delimiter="|"
)
```

#### 5. CSV Type Inference

```python
csv_content = """name,age,active,score,notes
Alice,30,true,98.5,
Bob,25,false,87.3,Some text"""

stats = arcadedb.import_csv(db, "data.csv", type_name="Person")

result = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
alice = list(result)[0]

# Types are inferred
assert isinstance(alice.get("age"), int)
assert isinstance(alice.get("active"), bool)
assert isinstance(alice.get("score"), float)
assert alice.get("notes") is None
```

**Type inference rules:**

- `"123"` → `int`
- `"3.14"` → `float`
- `"true"/"false"` → `bool`
- `""` (empty) → `None`
- Everything else → `str`

## Import Options

### Common Options (All Importers)

```python
stats = arcadedb.import_csv(
    db,
    file_path,
    type_name="MyType",
    commitEvery=1000,  # Commit every N records (default: 1000)
    **options
)
```

### CSV Options

```python
stats = arcadedb.import_csv(
    db,
    "data.csv",
    type_name="Person",
    import_type="documents",  # "documents", "vertices", or "edges"
    delimiter=",",            # Field delimiter (default: ",")
    quote_char='"',           # Quote character (default: '"')
    header=True,              # Has header row (default: True)
    commitEvery=1000
)
```

### ArcadeDB JSONL Options

```python
# Full database import via SQL
with arcadedb.create_database("./restored_db") as db:
    db.command("sql", "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000")
```

## Import Statistics

All importers return statistics:

```python
stats = arcadedb.import_csv(db, "data.csv", type_name="Person")

print(stats)
# {
#     'records_imported': 1000,
#     'duration_seconds': 1.23,
#     'records_per_second': 813.0,
#     'errors': 0
# }
```

## Running These Tests

```bash
# Run all import tests
pytest tests/test_importer.py -v

# Run with output
pytest tests/test_importer.py -v -s
```

## Best Practices

### ✅ DO: Use Appropriate Batch Size

```python
# Large files: increase batch size
arcadedb.import_csv(
    db,
    "huge_file.csv",
    type_name="Data",
    commitEvery=10000  # Fewer, larger transactions
)

# Small files: default is fine
arcadedb.import_csv(
    db,
    "small_file.csv",
    type_name="Data"
    # commitEvery=1000 (default)
)
```

### ✅ DO: Create Types Before Importing

```python
# Define schema first for better performance
db.command("sql", "CREATE DOCUMENT TYPE Person")
db.command("sql", "CREATE PROPERTY Person.age INTEGER")
db.command("sql", "CREATE INDEX ON Person(name) UNIQUE")

# Then import
arcadedb.import_csv(db, "people.csv", type_name="Person")
```

### ✅ DO: Handle Import Errors

```python
try:
    stats = arcadedb.import_csv(db, "data.csv", type_name="Person")
    print(f"Imported {stats['records_imported']} records")
except Exception as e:
    print(f"Import failed: {e}")
    # Handle error, rollback, etc.
```

## Related Documentation

- [Importer API Reference](../../api/importer.md)
- [Data Import Guide](../../guide/import.md)
- [Import Examples](../../examples/import.md)
