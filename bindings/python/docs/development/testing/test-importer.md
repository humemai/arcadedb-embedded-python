# Data Import Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_importer.py){ .md-button }

There are 16 tests focused on CSV import (documents, vertices), delimiter handling, type inference nuances, NULL/empty values, stats, error cases, batch commits, Unicode, and a small performance smoke.

## Quick Start

### CSV Import (documents)

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./mydb") as db:
    db.schema.create_document_type("Person")

    stats = arcadedb.import_csv(db, "data.csv", type_name="Person")
    print(stats)
```

### CSV Import (vertices)

```python
with arcadedb.create_database("./mydb") as db:
    db.schema.create_vertex_type("Product")

    stats = arcadedb.import_csv(
        db,
        "products.csv",
        type_name="Product",
        import_type="vertices",
        typeIdProperty="id",
    )
```

## Test Cases

### 1) CSV as documents

Creates a `Person` document type and imports three rows; asserts stats `documents == 3`, `errors == 0`, and verifies properties for `Alice/New York`.

### 2) CSV as vertices

Creates a `Product` vertex type and imports three rows as vertices using `typeIdProperty="id"`; asserts `vertices == 3`, `documents == 0`, and checks `name/category` values.

### 3) Custom delimiter (TSV)

```python
csv_content = """name|age|city
Alice|30|NYC"""

stats = arcadedb.import_csv(db, "data.tsv", type_name="Item", delimiter="\t")
```

### 4) CSV type inference

```python
csv_content = """name,age,active,score,notes
Alice,30,true,98.5,
Bob,25,false,87.3,Some text"""

stats = arcadedb.import_csv(db, "data.csv", type_name="Person")

result = db.query("sql", "SELECT FROM Person WHERE name = 'Alice'")
alice = list(result)[0]

assert isinstance(record.get("count"), int)
assert isinstance(record.get("price"), float)
# Booleans are strings with the Java importer
assert isinstance(record.get("active"), str)
```

Type inference observations from tests:

- Numeric strings map to int/float
- Empty strings may be `None` or empty string, depending on importer/schema
- Boolean strings are imported as strings (e.g., "true", "false")

## Import Options

### Common Options

```python
stats = arcadedb.import_csv(
    db,
    file_path,
    type_name="MyType",
    commitEvery=1000,
)
```

### CSV Options

```python
stats = arcadedb.import_csv(
    db,
    "data.csv",
    type_name="Person",
    import_type="documents",  # "documents" or "vertices" (edges not covered in tests)
    delimiter=",",            # Field delimiter
    commitEvery=1000
)
```

Note: JSON/JSONL import via `IMPORT DATABASE` is not exercised in this test file.

## Import Statistics

Importer returns statistics:

```python
stats = arcadedb.import_csv(db, "data.csv", type_name="Person")

print(stats)
# {
#     'documents': 3,
#     'vertices': 0,
#     'edges': 0,
#     'errors': 0,
#     'duration_ms': 123
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

### ✅ Use appropriate batch size

```python
# Large files: increase batch size
arcadedb.import_csv(db, "huge_file.csv", type_name="Data", commitEvery=100)

# Small files: default is fine
arcadedb.import_csv(db, "small_file.csv", type_name="Data")
```

### ✅ Create types before importing

```python
# Define schema first for better performance
db.schema.create_document_type("Person")
arcadedb.import_csv(db, "people.csv", type_name="Person")
```

### ✅ Handle import errors

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
