# Record Wrappers (Document, Vertex, Edge)

The Python API provides Pythonic wrapper classes for database records: `Document`,
`Vertex`, and `Edge`. These wrappers hide the underlying Java implementation and provide
a clean Python interface.

## Overview

| Class | Purpose | Usage |
|-------|---------|-------|
| `Document` | Base wrapper for all records (documents, vertices, edges) | Property access, modification, deletion |
| `Vertex` | Wrapper for graph vertices | Creating edges, traversal |
| `Edge` | Wrapper for graph edges | Accessing source/target vertices |

## Document Wrapper

The `Document` class is the base wrapper for all record types. Use it for documents and
as the base class for `Vertex` and `Edge`.

### Creating Documents

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.graph import Document, Vertex, Edge

with arcadedb.create_database("/tmp/mydb") as db:
    # Schema operations are auto-transactional
    db.schema.create_document_type("Note")

    # Create a document
    with db.transaction():
        doc = db.new_document("Note")
        doc.set("title", "My Note")
        doc.set("content", "Important information")
        doc.save()

        # Get the RID for later retrieval
        doc_id = str(doc.get_identity())
        print(f"Created document: {doc_id}")
```

### Properties and Methods

#### `set(key, value) -> Document`

Set a property on the document. Returns self for chaining.

```python
doc.set("name", "Alice")
doc.set("age", 30)
doc.set("active", True)

# Chaining
doc.set("name", "Bob").set("age", 25).save()
```

#### `get(key) -> Any`

Get a property value.

```python
name = doc.get("name")
age = doc.get("age")
email = doc.get("email")  # Returns None if not found
email = doc.get("email") or "unknown"  # Use default pattern
```

#### `get_property_names() -> List[str]`

Get all property names on the document.

```python
props = doc.get_property_names()
print(f"Properties: {props}")
# Output: Properties: ['name', 'age', 'active']
```

#### `has_property(key) -> bool`

Check if a property exists.

```python
if doc.has_property("email"):
    email = doc.get("email")
else:
    print("Email not set")
```

#### `save() -> Document`

Save changes to the database. Returns self.

```python
doc.set("name", "Updated Name")
doc.save()  # Persists changes
```

#### `delete() -> None`

Delete the document from the database.

**⚠️ Important Limitation:** Only works on objects from `lookup_by_rid()` or newly
created objects, not on query results. Use SQL DELETE for query results.

```python
# ✅ Works on fresh lookup
with db.transaction():
    doc = db.lookup_by_rid("#1:0")
    doc.delete()

# ✅ Works on newly created
with db.transaction():
    doc = db.new_document("Note")
    doc.set("title", "Test")
    doc.save()
    doc.delete()

# ❌ Doesn't work on query results
results = db.query("sql", "SELECT FROM Note WHERE title = 'Test'")
for doc in results:
    doc.delete()  # No-op!

# ✅ Use SQL DELETE instead
with db.transaction():
    db.command("sql", "DELETE FROM Note WHERE title = 'Test'")
```

#### `to_dict() -> dict`

Convert the document to a Python dictionary.

```python
doc_dict = doc.to_dict()
print(doc_dict)
# Output: {'name': 'Alice', 'age': 30, 'active': True, '@rid': '#1:0', '@type': 'Note'}
```

#### `get_identity() -> str`

Get the Record ID (RID) of the document.

```python
rid = doc.get_identity()
print(rid)  # Output: #1:0
```

#### `get_type_name() -> str`

Get the type name of the document.

```python
type_name = doc.get_type_name()
print(type_name)  # Output: Note
```

#### `modify() -> Document`

Get a mutable version of the document. Useful for immutable query results.

```python
# Query results are often immutable
results = db.query("sql", "SELECT FROM Note LIMIT 1")
immutable_doc = results[0]

# Get mutable version for modification
with db.transaction():
    mutable_doc = immutable_doc.modify()
    mutable_doc.set("updated", True).save()
```

#### `wrap(java_object) -> Document`

Static method to wrap Java objects as Python wrappers. Automatically detects type.

```python
from arcadedb_embedded.graph import Document

# Wrap Java object and automatically detect type
wrapped = Document.wrap(java_object)
# Returns: Document, Vertex, or Edge depending on actual type
```

## Vertex Wrapper

The `Vertex` class extends `Document` with graph-specific methods for creating and
traversing edges.

### Creating Vertices

```python
# Schema operations are auto-transactional
db.schema.create_vertex_type("Person")

with db.transaction():
    alice = db.new_vertex("Person")
    alice.set("name", "Alice")
    alice.set("age", 30)
    alice.save()

    print(f"Created vertex: {alice.get_identity()}")
```

### Graph Methods

#### `new_edge(edge_type, target_vertex, **properties) -> Edge`

Create an edge from this vertex to another vertex.

```python
with db.transaction():
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()

    # Create edge
    edge = alice.new_edge("Knows", bob)
    edge.set("since", 2020)
    edge.save()
```

#### `get_out_edges() -> List[Edge]`

Get all outgoing edges from this vertex.

```python
outgoing = alice.get_out_edges()
for edge in outgoing:
    target = edge.get_out()
    print(f"Alice -> {target.get('name')}")
```

## Edge Wrapper

The `Edge` class represents a connection between vertices with optional properties.

### Edge Properties

Edges have the same property methods as documents:

```python
edge = alice.new_edge("Knows", bob)
edge.set("since", 2020)
edge.set("strength", 0.9)
edge.save()

print(edge.get("since"))  # Output: 2020
edge.get_property_names()  # ['since', 'strength']
```

### Graph Methods

#### `get_in() -> Vertex`

Get the source (in) vertex of the edge.

```python
source = edge.get_in()
print(f"Source: {source.get('name')}")
```

#### `get_out() -> Vertex`

Get the target (out) vertex of the edge.

```python
target = edge.get_out()
print(f"Target: {target.get('name')}")
```

## Best Practices

### 1. Always Save After Set

```python
# ❌ Bad - changes not persisted
with db.transaction():
    doc.set("name", "Alice")
# No save!

# ✅ Good
with db.transaction():
    doc.set("name", "Alice")
    doc.save()
```

### 2. Use Fresh Lookups for Delete

```python
# ❌ Don't delete query results
results = db.query("sql", "SELECT FROM Note")
for doc in results:
    doc.delete()  # Doesn't work!

# ✅ Use fresh lookup
with db.transaction():
    doc = db.lookup_by_rid("#1:0")
    doc.delete()

# ✅ Or use SQL
with db.transaction():
    db.command("sql", "DELETE FROM Note WHERE @rid = #1:0")
```

### 3. Create Indexes for Frequent Lookups

```python
db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")
```

### 4. Chain Methods for Brevity

```python
# Chaining
with db.transaction():
    doc = db.new_document("Note") \
        .set("title", "My Note") \
        .set("content", "Content") \
        .save()
```

## Deletion

See the [Graphs](../guide/graphs.md#deleting-records) guide for comprehensive deletion
documentation, including cascade behavior and best practices.

**Quick Reference:**

| Method | Works On | Best For |
|--------|----------|----------|
| `.delete()` | Fresh lookups, new objects | Interactive deletion |
| `SQL DELETE` | All situations | Reliable deletion |

```python
# SQL DELETE (recommended)
with db.transaction():
    db.command("sql", "DELETE FROM Note WHERE @rid = #1:0")

# Wrapper delete (on fresh lookup only)
with db.transaction():
    doc = db.lookup_by_rid("#1:0")
    doc.delete()
```
