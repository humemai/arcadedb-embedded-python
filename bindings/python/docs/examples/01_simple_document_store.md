# Simple Document Store Example

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/01_simple_document_store.py){ .md-button }

This comprehensive example demonstrates ArcadeDB's document capabilities using a task management system. You'll learn about data types, NULL handling, SQL operations, and the differences between document and graph storage models.

## Overview

The example creates a task management system showcasing:

- **Rich Data Types** - STRING, BOOLEAN, INTEGER, FLOAT, DECIMAL, DATE, DATETIME, LIST with element types, and Arrays
- **NULL Handling** - INSERT with NULL, UPDATE to NULL, queries with IS NULL/IS NOT NULL
- **SQL Operations** - Complete CRUD workflow with ArcadeDB SQL
- **Built-in Functions** - date() for date literals, uuid() for unique IDs, sysdate() for dynamic timestamps
- **Record Types** - Understanding Documents vs Vertices vs Edges
- **Schema Flexibility** - Typed properties for performance with schema-optional flexibility
- **Type Safety** - Validated array data with element type specification

## Key Learning Points

### 1. Data Type Support

ArcadeDB provides comprehensive data type support with NULL handling:

```python
from datetime import date
import uuid
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./task_db") as db:
    # Schema operations are auto-transactional (no wrapper needed)
    db.schema.create_document_type("Task")
    db.schema.create_property("Task", "title", "STRING")
    db.schema.create_property("Task", "priority", "STRING")
    db.schema.create_property("Task", "completed", "BOOLEAN")
    db.schema.create_property("Task", "tags", "LIST", of_type="STRING")
    db.schema.create_property("Task", "created_date", "DATE")
    db.schema.create_property("Task", "due_datetime", "DATETIME")
    db.schema.create_property("Task", "estimated_hours", "FLOAT")
    db.schema.create_property("Task", "priority_score", "INTEGER")
    db.schema.create_property("Task", "cost", "DECIMAL")
    db.schema.create_property("Task", "task_id", "STRING")

    # Insert with Python objects (auto-converted) and UUID
    with db.transaction():
        task = db.new_document("Task")
        task.set("title", "Write documentation")
        task.set("priority", "medium")
        task.set("completed", False)
        task.set("tags", ["work", "writing"])
        task.set("created_date", date(2024, 1, 16))
        task.set("due_datetime", None)
        task.set("estimated_hours", 8.0)
        task.set("priority_score", 70)
        task.set("cost", None)
        task.set("task_id", str(uuid.uuid4()))
        task.save()
```

### 2. SQL Functions and NULL Queries

Learn about built-in functions and NULL handling:

```python
from datetime import datetime
import uuid
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./task_db") as db:
    # Insert with Python-native types (UUID, datetime handled by converter)
    with db.transaction():
        task = db.new_document("Task")
        task.set("title", "Buy groceries")
        task.set("task_id", str(uuid.uuid4()))
        task.set("created_date", date(2024, 1, 15))
        task.set("due_datetime", datetime(2024, 1, 20, 18, 0, 0))
        task.set("cost", 150.00)
        task.save()

    # Query for NULL values (reads don't need transaction)
    print("Tasks with NULL due_datetime:")
    result = db.query("sql", "SELECT title, due_datetime, cost FROM Task WHERE due_datetime IS NULL")
    for record in result:
        print(f"  Title: {record.get('title')}, Due: {record.get('due_datetime')}, Cost: {record.get('cost')}")

    print("\nTasks with NULL cost:")
    result = db.query("sql", "SELECT title, due_datetime, cost FROM Task WHERE cost IS NULL")
    for record in result:
        print(f"  Title: {record.get('title')}, Due: {record.get('due_datetime')}, Cost: {record.get('cost')}")

    # UPDATE via API (fetch + mutate in transaction)
    with db.transaction():
        for record in db.query("sql", "SELECT FROM Task WHERE title = 'Call dentist'"):
            doc = record.get_element()
            doc.set("cost", None)
            doc.set("estimated_hours", None)
            doc.save()
```

### 3. Record Types Explained

Understanding when to use different record types:

- **Document** - Like database tables, for simple data storage
- **Vertex** - Graph nodes representing entities
- **Edge** - Graph connections representing relationships

### 4. Advanced Features

The example demonstrates:

- **NULL Values** - Optional fields with IS NULL/IS NOT NULL queries
- **Type-Safe Arrays** - LIST with of_type parameter for validated collections
- **DECIMAL Handling** - Java BigDecimal conversion via float(str(value))
- **DATETIME Literals** - String literals automatically parsed to DATETIME type
- **Schema-Optional Flexibility** - Define properties for performance, add ad-hoc fields when needed
- **Query Optimization** - Using typed properties and indexes

## Running the Example

```bash
cd bindings/python/examples/
python 01_simple_document_store.py
```

Expected output includes:

- Database creation and schema setup
- Sample tasks with various data types and NULL values
- Query demonstrations including NULL checks
- UPDATE operations setting values to NULL
- File structure explanation

## Database Structure

After running, examine the created files:

```text
my_test_databases/task_db/
├── configuration.json    # Database configuration
├── schema.json           # Type definitions with LIST OF STRING
├── Task_*.bucket         # Data storage files with tasks
├── dictionary.*.dict     # String compression dictionary
└── statistics.json       # Database statistics
```

## Next Steps

After mastering this example:

1. **Explore Graph Operations** - Learn about vertices and edges
2. **Try Vector Search** - Modern AI/ML integration
3. **Review API Documentation** - Deep dive into advanced features

## Common Questions

**Q: How does ArcadeDB handle NULL values?**
A: All ArcadeDB types support NULL by default. You can INSERT NULL, UPDATE to NULL, and query with IS NULL/IS NOT NULL operators.

**Q: How do I create a LIST with STRING elements?**
A: In Python API: `db.schema.create_property("Task", "tags", "LIST", of_type="STRING")`.
In SQL: `CREATE PROPERTY Task.tags LIST OF STRING`. Both create a type-safe list of
strings.

**Q: Why use typed properties?**
A: They provide better performance, validation, and enable advanced features like indexes. But ArcadeDB is schema-optional - you can still add properties dynamically.

**Q: When should I use Documents vs Vertices?**
A: Use Documents for simple data storage (like SQL tables). Use Vertices when you need to model relationships between entities with Edges.

**Q: How do I handle Java BigDecimal in Python?**
A: Convert via string first: `float(str(decimal_value))`. Direct conversion from Java BigDecimal to Python float requires string intermediary.

**Q: Can I mix data types?**
A: Yes! ArcadeDB is schema-flexible. You can add properties dynamically while benefiting from typed properties where defined.

---

*Need help? Check our [troubleshooting guide](../development/troubleshooting.md) or [open an issue](https://github.com/humemai/arcadedb-embedded-python/issues).*
