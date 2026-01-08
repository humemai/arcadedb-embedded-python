# Data Import Guide

This guide covers strategies, best practices, and patterns for importing data into
ArcadeDB efficiently and reliably.

## Overview

ArcadeDB's Importer supports multiple data formats:

- **CSV**: Tabular data with headers
- **ArcadeDB JSONL export/import**: Full database export/restore via `IMPORT DATABASE`

**Key Features:**

- Automatic type inference
- Batch processing for performance
- Relationship/edge mapping
- Schema validation
- Error handling and recovery

## Quick Start

### CSV Import

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Importer

with arcadedb.create_database("./mydb") as db:
    db.schema.create_vertex_type("Product")

    importer = Importer(db)
    stats = importer.import_file(
        file_path="products.csv",
        format_type="csv",
        import_type="vertices",   # create vertices
        type_name="Product",
        typeIdProperty="id",      # REQUIRED for vertices/edges
        commitEvery=5000,         # batch size (default ~5000)
    )

    print("Import complete!", stats)

# Convenience helper (same importer under the hood, tested in bindings):
# arcadedb.import_csv(db, "products.csv", "Product", import_type="vertices", typeIdProperty="id")
```

### ArcadeDB JSONL Import (full database)

```python
# Import ArcadeDB JSONL export (schema + data)
db.command("sql", "IMPORT DATABASE file:///exports/mydb.jsonl.tgz WITH commitEvery = 50000")
```

## Format Selection

### CSV - Tabular Data

**Best For:**

- Spreadsheet data
- Relational database exports
- Time-series data
- Simple structured data

**Advantages:**

- Simple format
- Excel/LibreOffice compatible
- Wide tool support
- Human readable

**Disadvantages:**

- No nested structures
- Limited type information
- Relationships require separate files

**Example:**

```csv
id,name,email,age
1,Alice,alice@example.com,30
2,Bob,bob@example.com,25
```

---

### ArcadeDB JSONL - Full Database Restore

**Best For:**

- Re-importing ArcadeDB `EXPORT DATABASE` outputs
- Moving databases between environments
- Backups and restores with schema + data

**Advantages:**

- Preserves full database (schema, indexes, data)
- Single command: `IMPORT DATABASE file://...`
- Works with compressed `.jsonl.tgz` exports

**Disadvantages:**

- Full-database scope (not selective)
- Requires access to ArcadeDB server or embedded instance

## Schema Design

### Pre-create Schema

**Recommended:** Define schema before importing for better control and validation.

```python
with arcadedb.create_database("./mydb") as db:
    # Define schema using Python API (auto-transactions under the hood)
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "id", "STRING")
    db.schema.create_property("User", "name", "STRING")
    db.schema.create_property("User", "email", "STRING")
    db.schema.create_property("User", "age", "INTEGER")
    db.schema.create_index("User", ["id"], unique=True)
    db.schema.create_index("User", ["email"], unique=True)

    importer = Importer(db)
    importer.import_file(
        file_path="users.csv",
        format_type="csv",
        import_type="vertices",
        type_name="User",
        typeIdProperty="id",
    )
```

**Benefits:**

- Type safety
- Validation
- Better performance
- Prevents errors

---

### Let Importer Infer

**Quick Start:** Let importer create schema automatically.

```python
# No schema definition needed
from arcadedb_embedded import Importer

with arcadedb.create_database("./mydb") as db:
    importer = Importer(db)
    importer.import_file(
        file_path="users.csv",
        import_type="vertices",
        type_name="User",
        typeIdProperty="id",
    )
```

**Auto-inference:**

- Creates vertex type if missing
- Infers property types from data
- Creates properties as needed

**Trade-offs:**

- Quick to start
- Less control
- Types may be wrong
- No validation

---

### Hybrid Approach

**Best of Both:** Define critical fields, allow others to be inferred.

```python
with arcadedb.create_database("./mydb") as db:
    # Define only the critical parts; importer will add the rest
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "id", "STRING")
    db.schema.create_index("User", ["id"], unique=True)

    importer = Importer(db)
    importer.import_file(
        file_path="users.csv",
        format_type="csv",
        import_type="vertices",
        type_name="User",
        typeIdProperty="id",
    )
```

## Performance Optimization

### Batch Size (`commitEvery`)

Control transaction batch size for memory vs. speed trade-off via the `commitEvery` option:

```python
from arcadedb_embedded import Importer
importer = Importer(db)

# Small batches: lower memory, more transactions
importer.import_file(
    file_path="large_file.csv",
    import_type="documents",
    type_name="Data",
    commitEvery=1000,
)

# Medium batches: balanced (default ~5000)
importer.import_file(
    file_path="large_file.csv",
    import_type="documents",
    type_name="Data",
    commitEvery=10000,
)

# Large batches: higher memory, fewer transactions
importer.import_file(
    file_path="large_file.csv",
    import_type="documents",
    type_name="Data",
    commitEvery=100000,
)
```

**Guidelines:**

| Dataset Size | Recommended Batch Size |
|--------------|------------------------|
| < 100K rows  | 1,000 - 10,000        |
| 100K - 1M    | 10,000 - 50,000       |
| > 1M rows    | 50,000 - 100,000      |

**Consider:**

- Available memory
- Record size
- Concurrent operations
- Disk I/O

---

### Parallel Processing

**Java Importer Uses Multi-threading by Default:**

The Java CSV importer automatically uses parallel processing with multiple threads:

```python
# Default: Uses (CPU count / 2) - 1 threads (minimum 1)
# Example: 8 CPU cores → 3 threads
stats = importer.import_file('large_file.csv', type_name='Data')

# Specify custom thread count
stats = importer.import_file(
    'large_file.csv',
    type_name='Data',
    parallel=8  # Use 8 threads
)

# Disable parallelism (single-threaded)
stats = importer.import_file(
    'large_file.csv',
    type_name='Data',
    parallel=1
)
```

**Important Notes:**

- The Java importer handles parallelism internally using native Java threads
- You don't need to split files manually for parallel processing
- The `parallel` parameter controls Java's internal thread pool
- Default is conservative: `(CPU_COUNT / 2) - 1` with minimum of 1
- For large imports, consider increasing to match your CPU cores

**Manual File Splitting (Advanced):**

For very large files or special requirements, you can split files and import chunks:

```python
import concurrent.futures
import os

def split_csv(input_file, chunk_size=100000):
    """Split large CSV into chunks."""
    chunks = []
    chunk_num = 0

    with open(input_file, 'r') as f:
        header = f.readline()

        chunk_file = f"chunk_{chunk_num}.csv"
        chunk_writer = open(chunk_file, 'w')
        chunk_writer.write(header)
        chunks.append(chunk_file)

        line_count = 0
        for line in f:
            chunk_writer.write(line)
            line_count += 1

            if line_count >= chunk_size:
                chunk_writer.close()
                chunk_num += 1
                chunk_file = f"chunk_{chunk_num}.csv"
                chunk_writer = open(chunk_file, 'w')
                chunk_writer.write(header)
                chunks.append(chunk_file)
                line_count = 0

        chunk_writer.close()

    return chunks

def import_chunk(db_path, chunk_file, vertex_type, type_id_property="id"):
    """Import single chunk as vertices."""
    from arcadedb_embedded import Importer
    with arcadedb.open_database(db_path) as db:
        importer = Importer(db)
        importer.import_file(
            file_path=chunk_file,
            import_type="vertices",
            type_name=vertex_type,
            typeIdProperty=type_id_property,
            commitEvery=10000,
        )
    os.remove(chunk_file)

# Split file
chunks = split_csv("large_data.csv", chunk_size=100000)

# Import in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(import_chunk, "./mydb", chunk, "Data", "id")
        for chunk in chunks
    ]

    for future in concurrent.futures.as_completed(futures):
        future.result()

print(f"Imported {len(chunks)} chunks")
```

---

### Disable Indexes During Import

For massive imports, temporarily disable indexes:

```python
# 1. Drop indexes (use schema API)
db.schema.drop_index("User[email]")
db.schema.drop_index("User[id]")

# 2. Import data (vertices)
stats = importer.import_file(
    file_path="huge_file.csv",
    import_type="vertices",
    type_name="User",
    typeIdProperty="id",
    commitEvery=100000,
)

# 3. Recreate indexes
db.schema.create_index("User", ["id"], unique=True)
db.schema.create_index("User", ["email"], unique=True)
```

**Speed Improvement:** 2-5x faster for large imports

---

## Error Handling

### Validation Before Import

```python
import csv

def validate_csv(file_path, required_columns):
    """Validate CSV before importing."""
    errors = []

    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Check headers
            missing = set(required_columns) - set(reader.fieldnames)
            if missing:
                errors.append(f"Missing columns: {missing}")
                return False, errors

            # Check data
            for i, row in enumerate(reader, start=2):
                # Validate required fields
                for col in required_columns:
                    if not row.get(col):
                        errors.append(f"Line {i}: Missing {col}")

                # Validate types (example)
                if row.get('age') and not row['age'].isdigit():
                    errors.append(f"Line {i}: Invalid age '{row['age']}'")

                # Stop after 100 errors
                if len(errors) >= 100:
                    errors.append("... more errors found")
                    return False, errors

        return len(errors) == 0, errors

    except Exception as e:
        return False, [f"File error: {e}"]

# Validate before import
valid, errors = validate_csv("users.csv", ["id", "name", "email"])
if valid:
    stats = importer.import_file(
        file_path="users.csv",
        import_type="vertices",
        type_name="User",
        typeIdProperty="id",
    )
    print("Imported:", stats)
else:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")
```

---

## Relationship Mapping

### CSV with Relationships

Import entities and relationships from separate CSV files:

```python
# Step 1: Import users
stats = importer.import_file(
    file_path="users.csv",
    import_type="vertices",
    type_name="User",
    typeIdProperty="id",
)

# Step 2: Import products
stats = importer.import_file(
    file_path="products.csv",
    import_type="vertices",
    type_name="Product",
    typeIdProperty="id",
)

# Step 3: Import relationships from CSV
# purchases.csv:
# user_id,product_id,date,amount
# 1,101,2024-01-15,29.99

import csv

with open("purchases.csv", 'r') as f:
    reader = csv.DictReader(f)

    with db.transaction():
        for row in reader:
            # Find vertices
            user_result = db.query("sql",
                f"SELECT FROM User WHERE id = '{row['user_id']}'")
            product_result = db.query("sql",
                f"SELECT FROM Product WHERE id = '{row['product_id']}'")

            if user_result.has_next() and product_result.has_next():
                user = user_result.next()
                product = product_result.next()

                # Create edge
                edge = user.new_edge("Purchased", product)
                edge.set("date", row['date'])
                edge.set("amount", float(row['amount']))
                edge.save()
```

---

### JSON with Embedded Relationships

```python
# orders.json structure:
# [
#   {
#     "order_id": "ORD123",
#     "customer": {"id": "CUST1", "name": "Alice"},
#     "items": [
#       {"product_id": "PROD1", "qty": 2},
#       {"product_id": "PROD2", "qty": 1}
#     ]
#   }
# ]

import json

with open("orders.json", 'r') as f:
    orders = json.load(f)

with db.transaction():
    for order in orders:
        # Create or find customer
        customer_id = order['customer']['id']
        customer_result = db.query("sql",
            f"SELECT FROM Customer WHERE id = '{customer_id}'")

        if customer_result.has_next():
            customer = customer_result.next()
        else:
            customer = db.new_vertex("Customer")
            customer.set("id", customer_id)
            customer.set("name", order['customer']['name'])
            customer.save()

        # Create order vertex
        order_vertex = db.new_vertex("Order")
        order_vertex.set("order_id", order['order_id'])
        order_vertex.save()

        # Link customer to order
        edge = customer.new_edge("Placed", order_vertex)
        edge.save()

        # Link order to products
        for item in order['items']:
            product_result = db.query("sql",
                f"SELECT FROM Product WHERE id = '{item['product_id']}'")

            if product_result.has_next():
                product = product_result.next()

                contains_edge = order_vertex.new_edge("Contains", product)
                contains_edge.set("quantity", item['qty'])
                contains_edge.save()
```

## See Also

- [Importer API Reference](../api/importer.md) - Complete API documentation
- [Import Examples](../examples/import.md) - Practical code examples
- [Database API](../api/database.md) - Database operations
- [Transactions](../api/transactions.md) - Transaction management
