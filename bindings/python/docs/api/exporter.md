# Exporter API

The Exporter provides utilities for exporting database content to various formats including JSONL, GraphML, and GraphSON.

!!! tip "Using Context Managers"
    For automatic resource cleanup, prefer using context managers:
    ```python
    with arcadedb.open_database("./mydb") as db:
        export_database(db, "./export.jsonl", format="jsonl")
    # Database automatically closed
    ```
    Examples below show explicit `db.close()` for clarity, but context managers are recommended in production.

## Overview

The `exporter` module enables:

- **JSONL Export**: Newline-delimited JSON format
- **GraphML Export**: XML-based graph format
- **GraphSON Export**: JSON graph format (TinkerPop)
- **CSV Export**: Comma-separated values
- **Selective Export**: Export specific types or queries
- **Progress Tracking**: Monitor export progress

## Exporting Database

### export_database

```python
from arcadedb_embedded.exporter import export_database

export_database(
    db,
    output_file: str,
    format: str = "jsonl",
    types: Optional[List[str]] = None,
    query: Optional[str] = None,
    progress_callback: Optional[Callable] = None
)
```

Export entire database or filtered content.

**Parameters:**

- `db`: Database instance
- `output_file` (str): Output file path
- `format` (str): Export format (`"jsonl"`, `"graphml"`, `"graphson"`, `"csv"`)
- `types` (Optional[List[str]]): Export only specific types
- `query` (Optional[str]): SQL query to filter records
- `progress_callback` (Optional[Callable]): Progress callback

**Example:**

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

# Open database
db = arcadedb.open_database("./mydb")

# Export entire database
export_database(db, "./export.jsonl", format="jsonl")

# Export specific types
export_database(db, "./users.jsonl", format="jsonl", types=["User", "Admin"])

# Export with query
export_database(
    db,
    "./active_users.jsonl",
    format="jsonl",
    query="SELECT FROM User WHERE active = true"
)

# Export with progress
def progress(current, total):
    percent = (current / total) * 100
    print(f"Progress: {percent:.1f}% ({current}/{total})")

export_database(db, "./export.jsonl", progress_callback=progress)

db.close()
```

## Export Formats

### JSONL (Newline-Delimited JSON)

```python
from arcadedb_embedded.exporter import export_database

# Export to JSONL
export_database(db, "./export.jsonl", format="jsonl")
```

**Output Format:**

```json
{"@rid":"#1:0","@type":"User","username":"alice","age":30}
{"@rid":"#1:1","@type":"User","username":"bob","age":25}
{"@rid":"#2:0","@type":"Post","title":"Hello World","content":"..."}
```

**Features:**

- ✅ One record per line
- ✅ Streaming-friendly
- ✅ Easy to parse
- ✅ Includes @rid and @type
- ✅ Best for re-import

---

### GraphML (XML Graph Format)

```python
from arcadedb_embedded.exporter import export_database

# Export to GraphML
export_database(db, "./export.graphml", format="graphml")
```

**Output Format:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="directed">
    <node id="#1:0">
      <data key="username">alice</data>
      <data key="age">30</data>
    </node>
    <edge id="#3:0" source="#1:0" target="#1:1">
      <data key="since">2020-01-01</data>
    </edge>
  </graph>
</graphml>
```

**Features:**

- ✅ Standard XML format
- ✅ Supported by many graph tools
- ✅ Human-readable
- ✅ Preserves graph structure
- ✅ Best for visualization tools

---

### GraphSON (JSON Graph Format)

```python
from arcadedb_embedded.exporter import export_database

# Export to GraphSON
export_database(db, "./export.json", format="graphson")
```

**Output Format:**

```json
{
  "vertices": [
    {
      "id": "#1:0",
      "label": "User",
      "properties": {
        "username": [{"value": "alice"}],
        "age": [{"value": 30}]
      }
    }
  ],
  "edges": [
    {
      "id": "#3:0",
      "label": "Follows",
      "outV": "#1:0",
      "inV": "#1:1",
      "properties": {
        "since": "2020-01-01"
      }
    }
  ]
}
```

**Features:**

- ✅ TinkerPop-compatible
- ✅ JSON format
- ✅ Graph structure
- ✅ Best for TinkerPop tools

---

### CSV (Comma-Separated Values)

```python
from arcadedb_embedded.exporter import export_database

# Export to CSV
export_database(db, "./users.csv", format="csv", types=["User"])
```

**Output Format:**

```csv
@rid,@type,username,age,email
#1:0,User,alice,30,alice@example.com
#1:1,User,bob,25,bob@example.com
```

**Features:**

- ✅ Spreadsheet-compatible
- ✅ Simple format
- ✅ Best for single types
- ⚠️ Flat structure (no nesting)

## Selective Export

### Export Specific Types

```python
from arcadedb_embedded.exporter import export_database

# Export only User vertices
export_database(db, "./users.jsonl", types=["User"])

# Export multiple types
export_database(db, "./social.jsonl", types=["User", "Post", "Follows"])
```

---

### Export with Query

```python
from arcadedb_embedded.exporter import export_database

# Export active users
export_database(
    db,
    "./active_users.jsonl",
    query="SELECT FROM User WHERE active = true"
)

# Export recent posts
export_database(
    db,
    "./recent_posts.jsonl",
    query="SELECT FROM Post WHERE timestamp > date('2024-01-01')"
)

# Export subgraph
export_database(
    db,
    "./user_network.jsonl",
    query="""
        SELECT FROM (
            SELECT expand(both('Follows')) FROM User WHERE username = 'alice'
        )
    """
)
```

## Progress Tracking

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Simple progress callback
def show_progress(current, total):
    percent = (current / total) * 100
    print(f"Progress: {percent:.1f}% ({current:,}/{total:,})")

export_database(db, "./export.jsonl", progress_callback=show_progress)

db.close()
```

**Progress Callback Signature:**

```python
def progress_callback(current: int, total: int) -> None:
    """
    Called periodically during export.

    Args:
        current: Number of records exported so far
        total: Total number of records to export
    """
    pass
```

## Advanced Examples

### Export with Progress Bar

```python
from tqdm import tqdm
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Get total count
total = sum(t.count_records() for t in db.schema.get_types())

# Create progress bar
pbar = tqdm(total=total, desc="Exporting", unit=" records")

def update_progress(current, total):
    pbar.update(current - pbar.n)

export_database(db, "./export.jsonl", progress_callback=update_progress)

pbar.close()
db.close()
```

---

### Export Multiple Formats

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Export to multiple formats
formats = [
    ("./export.jsonl", "jsonl"),
    ("./export.graphml", "graphml"),
    ("./export.json", "graphson"),
    ("./users.csv", "csv")
]

for output_file, format in formats:
    print(f"Exporting to {format}...")
    export_database(db, output_file, format=format)
    print(f"✅ Exported to {output_file}")

db.close()
```

---

### Export Per Type

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Export each type to separate file
for type_obj in db.schema.get_types():
    type_name = type_obj.get_name()
    output_file = f"./exports/{type_name}.jsonl"

    print(f"Exporting {type_name}...")
    export_database(db, output_file, types=[type_name])
    print(f"✅ Exported {type_obj.count_records()} {type_name} records")

db.close()
```

---

### Export with Filtering

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database

db = arcadedb.open_database("./mydb")

# Export by date ranges
export_configs = [
    ("2024_01.jsonl", "SELECT FROM Event WHERE timestamp >= date('2024-01-01') AND timestamp < date('2024-02-01')"),
    ("2024_02.jsonl", "SELECT FROM Event WHERE timestamp >= date('2024-02-01') AND timestamp < date('2024-03-01')"),
    ("2024_03.jsonl", "SELECT FROM Event WHERE timestamp >= date('2024-03-01') AND timestamp < date('2024-04-01')"),
]

for output_file, query in export_configs:
    print(f"Exporting to {output_file}...")
    export_database(db, output_file, query=query)
    print(f"✅ Exported {output_file}")

db.close()
```

## Complete Example

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.exporter import export_database
import os
from datetime import datetime

def export_with_metadata(db, output_dir="./exports"):
    """Export database with metadata and multiple formats"""

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Export to multiple formats
    exports = [
        (f"{output_dir}/full_{timestamp}.jsonl", "jsonl", None),
        (f"{output_dir}/graph_{timestamp}.graphml", "graphml", None),
        (f"{output_dir}/users_{timestamp}.csv", "csv", ["User"]),
    ]

    print(f"🚀 Starting export at {timestamp}")

    for output_file, format, types in exports:
        print(f"\n📦 Exporting to {format}...")

        # Progress callback
        def progress(current, total):
            if current % 1000 == 0:  # Log every 1000 records
                percent = (current / total) * 100
                print(f"  Progress: {percent:.1f}% ({current:,}/{total:,})")

        export_database(
            db,
            output_file,
            format=format,
            types=types,
            progress_callback=progress
        )

        file_size = os.path.getsize(output_file)
        file_size_mb = file_size / (1024 * 1024)
        print(f"  ✅ Exported to {output_file} ({file_size_mb:.2f} MB)")

    print(f"\n✅ Export complete")

# Use it
db = arcadedb.open_database("./mydb")
export_with_metadata(db)
db.close()
```

## Re-importing Exported Data

### Import JSONL

```python
import arcadedb_embedded as arcadedb
import json

db = arcadedb.open_database("./new_db")

with open("./export.jsonl", "r") as f:
    with db.transaction():
        for line in f:
            data = json.loads(line)

            # Get type name
            type_name = data.pop("@type")
            rid = data.pop("@rid", None)

            # Create record
            if "V" in type_name:  # Vertex
                record = db.new_vertex(type_name)
            elif "E" in type_name:  # Edge
                # Handle edges separately
                continue
            else:  # Document
                record = db.new_document(type_name)

            # Set properties
            for key, value in data.items():
                record.set(key, value)

            record.save()

db.close()
```

## Best Practices

### 1. Use Appropriate Format

```python
# ✅ Good: Choose format for use case
export_database(db, "./backup.jsonl", format="jsonl")        # Re-import
export_database(db, "./viz.graphml", format="graphml")       # Visualization
export_database(db, "./analysis.csv", format="csv")          # Spreadsheet

# ❌ Bad: Wrong format for use case
export_database(db, "./backup.csv", format="csv")  # Can't preserve graph structure
```

### 2. Filter Large Exports

```python
# ✅ Good: Export only what you need
export_database(db, "./users.jsonl", types=["User"])
export_database(db, "./recent.jsonl", query="SELECT FROM Event WHERE timestamp > date('2024-01-01')")

# ❌ Bad: Export everything when you only need subset
export_database(db, "./everything.jsonl")  # Slow and large
```

### 3. Monitor Progress

```python
# ✅ Good: Track progress for large exports
def progress(current, total):
    print(f"Progress: {(current/total)*100:.1f}%")

export_database(db, "./export.jsonl", progress_callback=progress)

# ❌ Bad: No feedback for long-running export
export_database(db, "./large.jsonl")  # User has no idea how long it will take
```

### 4. Handle Errors Gracefully

```python
# ✅ Good: Handle export errors
try:
    export_database(db, "./export.jsonl", format="jsonl")
    print("✅ Export successful")
except Exception as e:
    print(f"❌ Export failed: {e}")
```

### 5. Organize Export Files

```python
# ✅ Good: Organize by timestamp and type
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
export_database(db, f"./exports/{timestamp}_full.jsonl")
export_database(db, f"./exports/{timestamp}_users.csv", types=["User"])

# ❌ Bad: Overwrite previous exports
export_database(db, "./export.jsonl")  # Overwrites previous export
```

## Troubleshooting

### Out of Memory

```python
# ✅ Good: Export in chunks
for type_obj in db.schema.get_types():
    type_name = type_obj.get_name()
    export_database(db, f"./exports/{type_name}.jsonl", types=[type_name])
```

### Slow Export Performance

```python
# ✅ Good: Use efficient format
export_database(db, "./export.jsonl", format="jsonl")  # Fast

# ⚠️ Slower: XML format
export_database(db, "./export.graphml", format="graphml")  # Slower
```

### File Already Exists

```python
import os

# ✅ Good: Check before export
output_file = "./export.jsonl"
if os.path.exists(output_file):
    os.remove(output_file)
    print(f"Removed existing {output_file}")

export_database(db, output_file)
```

## Performance Tips

1. **JSONL is fastest** - Use for backups and re-import
2. **Filter early** - Use queries to reduce export size
3. **Export by type** - Parallel exports for large databases
4. **Monitor memory** - Export in chunks if needed
5. **Compress output** - Gzip JSONL files for storage

## See Also

- **[Database API](database.md)** - Database operations
- **[Importer API](importer.md)** - Importing data
- **[Data Import Guide](../guide/import.md)** - Import patterns
- **[Example 05: CSV Import](../examples/05_csv_import_graph.md)** - CSV import examples
- **[Example 04: CSV Import (Tables)](../examples/04_csv_import_documents.md)** - Document import
