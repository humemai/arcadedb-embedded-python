# Simple Document Store Example

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/01_simple_document_store.py){ .md-button }

This comprehensive example demonstrates ArcadeDB's document capabilities using a task management system. You'll learn about data types, NULL handling, SQL operations, and the differences between document and graph storage models.

## Overview

The example creates a task management system showcasing:

- **Rich Data Types** - STRING, BOOLEAN, INTEGER, FLOAT, DECIMAL, DATE, DATETIME, and LIST
- **NULL Handling** - INSERT with NULL, UPDATE to NULL, queries with IS NULL/IS NOT NULL
- **SQL Operations** - Complete CRUD workflow with ArcadeDB SQL
- **Python uuid4()** - Generating unique task IDs in Python and storing them as STRING
- **Record Types** - Understanding Documents vs Vertices vs Edges
- **Schema Flexibility** - Typed properties for performance with schema-optional flexibility
- **ResultSet helpers** - `to_list()`, `first()`, and `count_type()` with automatic type conversion

## Key Learning Points

### 1. Data Type Support

ArcadeDB provides comprehensive data type support with NULL handling:

```python
import uuid
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./task_db") as db:
    # Schema statements apply immediately (no transaction needed)
    db.command("sql", "CREATE DOCUMENT TYPE Task")
    db.command("sql", "CREATE PROPERTY Task.title STRING")
    db.command("sql", "CREATE PROPERTY Task.priority STRING")
    db.command("sql", "CREATE PROPERTY Task.completed BOOLEAN")
    db.command("sql", "CREATE PROPERTY Task.tags LIST")
    db.command("sql", "CREATE PROPERTY Task.created_date DATE")
    db.command("sql", "CREATE PROPERTY Task.due_datetime DATETIME")
    db.command("sql", "CREATE PROPERTY Task.estimated_hours FLOAT")
    db.command("sql", "CREATE PROPERTY Task.priority_score INTEGER")
    db.command("sql", "CREATE PROPERTY Task.cost DECIMAL")
    db.command("sql", "CREATE PROPERTY Task.task_id STRING")

    # Bind values as parameters; the engine converts each one to its
    # property's type (the date string to DATE, the list to LIST)
    with db.transaction():
        db.command(
            "sql",
            """
            INSERT INTO Task SET
                title = ?, priority = ?, completed = ?, tags = ?,
                created_date = ?, due_datetime = ?, estimated_hours = ?,
                priority_score = ?, cost = ?, task_id = ?
            """,
            "Write documentation",
            "medium",
            False,
            ["work", "writing"],
            "2024-01-16",
            None,
            8.0,
            70,
            None,
            str(uuid.uuid4()),
        )
```

### 2. NULL Queries and Updates

Query for NULL values and set values to NULL:

```python
import uuid
import arcadedb_embedded as arcadedb

with arcadedb.open_database("./task_db") as db:
    # Date and datetime strings are converted to the DATE/DATETIME property types
    with db.transaction():
        db.command(
            "sql",
            """
            INSERT INTO Task SET
                title = ?, task_id = ?, created_date = ?,
                due_datetime = ?, cost = ?
            """,
            "Buy groceries",
            str(uuid.uuid4()),
            "2024-01-15",
            "2024-01-20T18:00:00",
            150.00,
        )

    # Query for NULL values (reads don't need transaction)
    print("Tasks with NULL due_datetime:")
    result = db.query("sql", "SELECT title, due_datetime, cost FROM Task WHERE due_datetime IS NULL")
    for record in result:
        print(f"  Title: {record.get('title')}, Due: {record.get('due_datetime')}, Cost: {record.get('cost')}")

    print("\nTasks with NULL cost:")
    result = db.query("sql", "SELECT title, due_datetime, cost FROM Task WHERE cost IS NULL")
    for record in result:
        print(f"  Title: {record.get('title')}, Due: {record.get('due_datetime')}, Cost: {record.get('cost')}")

    # UPDATE via SQL
    with db.transaction():
        db.command(
            "sql",
            "UPDATE Task SET cost = null, estimated_hours = null WHERE title = ?",
            "Call dentist",
        )
```

### 3. Record Types Explained

Understanding when to use different record types:

- **Document** - Like database tables, for simple data storage
- **Vertex** - Graph nodes representing entities
- **Edge** - Graph connections representing relationships

### 4. Advanced Features

The example demonstrates:

- **NULL Values** - Optional fields with IS NULL/IS NOT NULL queries
- **LIST Properties** - `CREATE PROPERTY Task.tags LIST` storing string arrays
- **DECIMAL Handling** - DECIMAL values arrive as Python `decimal.Decimal`
- **DATETIME Literals** - String literals automatically parsed to DATETIME type
- **Schema-Optional Flexibility** - Define properties for performance, add ad-hoc fields when needed
- **Aggregation Queries** - GROUP BY on priority and completion status, plus `count_type()`

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
├── schema.json           # Type definitions, including the LIST property
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
A: Use SQL DDL: `CREATE PROPERTY Task.tags LIST` and store string arrays/lists in inserts and updates.
ArcadeDB validates values at write time for the declared property type.

**Q: Why use typed properties?**
A: They provide better performance, validation, and enable advanced features like indexes. But ArcadeDB is schema-optional - you can still add properties dynamically.

**Q: When should I use Documents vs Vertices?**
A: Use Documents for simple data storage (like SQL tables). Use Vertices when you need to model relationships between entities with Edges.

**Q: Can I mix data types?**
A: Yes! ArcadeDB is schema-flexible. You can add properties dynamically while benefiting from typed properties where defined.
