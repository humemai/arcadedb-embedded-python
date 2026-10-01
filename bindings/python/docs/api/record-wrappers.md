# Record Wrappers (Document, Vertex, Edge)

The Python API provides wrapper classes for database records: `Document`, `Vertex`, and
`Edge`.

!!! note "Compatibility-oriented API"
    Prefer SQL/OpenCypher via `db.command(...)` and `db.query(...)` for normal schema,
    CRUD, and graph workflows. This page documents the wrapper layer for compatibility,
    targeted record manipulation, and wrapper-specific traversal helpers.

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

For application code, prefer `INSERT INTO ...` statements. Use `db.new_document(...)`
when you explicitly need the wrapper object in hand.

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded import Document, Vertex, Edge

with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Note")

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

#### `set(name, value) -> Document`

Set a property on the document. Returns self for chaining.

```python
doc.set("name", "Alice")
doc.set("age", 30)
doc.set("active", True)

# Chaining
doc.set("name", "Bob").set("age", 25).save()
```

#### `get(name, convert_types: bool = True) -> Any`

Get a property value. With `convert_types=True` (default) Java types are converted to
Python types; pass `False` to get the raw Java-backed value (equivalent to `get_raw`).

```python
name = doc.get("name")
age = doc.get("age")
email = doc.get("email")               # Returns None if not found
email = doc.get("email") or "unknown"  # Use default pattern
```

#### `get_raw(name) -> Any`

Get a property value without Java-to-Python conversion. Returns the raw Java-backed
value, or `None` if the property doesn't exist. Equivalent to
`get(name, convert_types=False)`.

```python
java_value = doc.get_raw("created_at")  # Raw Java object
```

#### `get_property_names() -> List[str]`

Get all property names on the document.

```python
props = doc.get_property_names()
print(f"Properties: {props}")
# Output: Properties: ['name', 'age', 'active']
```

#### `has_property(name) -> bool`

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

Set every property of a new record before its first `save()`. A record saved and then
changed in the same transaction is written a second time, and the second write grows it
inside its page: at 200,000 new vertices, 1,000 per transaction, saving each vertex once
measured 110,000 to 120,000 per second and saving it, setting one more property, and saving again
about 52,000 (ArcadeDB [#8735](https://github.com/ArcadeData/arcadedb/issues/8735)).

#### `delete() -> None`

Delete the document from the database.

**⚠️ Important Limitation:** Call it on a wrapper from `lookup_by_rid()` or on a newly
created object. Iterating a query yields `Result` rows, which have no `delete()`; use SQL
DELETE for query results.

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
for row in results:
    row.delete()  # AttributeError: a query row is a Result, not a Document

# ✅ Use SQL DELETE instead
with db.transaction():
    db.command("sql", "DELETE FROM Note WHERE title = 'Test'")
```

#### `to_dict(convert_types: bool = True) -> dict`

Convert the document to a Python dictionary of its properties (metadata like RID/type
is not included). Use `get_rid()` for the record ID if needed. Pass
`convert_types=False` to keep raw Java-backed values.

**Performance note:** `to_dict()` eagerly converts the full document into Python
data. For large scans or repeated wrapper access, prefer `get()` when you only need
specific fields.

```python
doc_dict = doc.to_dict()
print(doc_dict)
# Output: {'name': 'Alice', 'age': 30, 'active': True}

rid = doc.get_rid()
```

#### `get_identity()`

Get the record identity (the underlying Java RID object). For a string RID, use
`get_rid()` or wrap with `str(...)`.

```python
identity = doc.get_identity()
print(str(identity))  # Output: #1:0
```

#### `get_rid() -> str`

Get the Record ID (RID) as a string.

```python
rid = doc.get_rid()
print(rid)  # Output: #1:0
```

#### `get_type_name() -> str`

Get the type name of the document.

```python
type_name = doc.get_type_name()
print(type_name)  # Output: Note
```

#### `get_java_document()`

Expose the wrapped Java document object for low-level integrations. Use this only when
you need the underlying Java API directly (camelCase JPype methods); normal code should
stay on the Python wrapper.

```python
java_doc = doc.get_java_document()
print(java_doc.getTypeName())
```

#### `modify() -> Document`

Get a mutable version of the document. Records loaded from the database (by
`lookup_by_rid()` or through a query row's `get_element()`) are immutable until you call
it.

```python
# A query row is a Result; get_element() returns the (immutable) record wrapper
immutable_doc = db.query("sql", "SELECT FROM Note LIMIT 1").first().get_element()

# Get mutable version for modification
with db.transaction():
    mutable_doc = immutable_doc.modify()
    mutable_doc.set("updated", True).save()
```

#### `wrap(java_object) -> Document`

Static method to wrap Java objects as Python wrappers. Automatically detects type.

```python
from arcadedb_embedded import Document

# Wrap Java object and automatically detect type
wrapped = Document.wrap(java_object)
# Returns: Document, Vertex, or Edge depending on actual type
```

## Vertex Wrapper

The `Vertex` class extends `Document` with graph-specific methods for wrapper-based edge
creation and traversal.

### Creating Vertices

For most app code, prefer SQL/OpenCypher vertex creation and graph writes. Use
`db.new_vertex(...)` when you need direct wrapper manipulation.

```python
db.command("sql", "CREATE VERTEX TYPE Person")

with db.transaction():
    alice = db.new_vertex("Person")
    alice.set("name", "Alice")
    alice.set("age", 30)
    alice.save()

    print(f"Created vertex: {alice.get_identity()}")
```

### Graph Methods

#### `new_edge(label, target, **kwargs) -> Edge`

Create an edge from this vertex to another vertex. Keyword arguments become edge
properties.

```python
with db.transaction():
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()

    # Create edge: new_edge saves it, so pass its properties here
    edge = alice.new_edge("Knows", bob, since=2020)
```

#### `get_out_edges(*labels) -> List[Edge]`

Get outgoing edges from this vertex, optionally filtered by label.

```python
# All outgoing edges
outgoing = alice.get_out_edges()
for edge in outgoing:
    target = edge.get_in()
    print(f"Alice -> {target.get('name')}")

# Filter by edge type
knows = alice.get_out_edges("Knows")
assert all(e.get_in().get("name") in {"Bob", "Carol"} for e in knows)
```

#### `get_in_edges(*labels) -> List[Edge]`

Get incoming edges to this vertex, optionally filtered by label. On an edge type declared `UNIDIRECTIONAL` this returns nothing: only the outgoing side is stored, so use a Cypher pattern or SQL `MATCH`, which see the incoming side.

```python
incoming = alice.get_in_edges()
for edge in incoming:
    source = edge.get_out()
    print(f"{source.get('name')} -> Alice")

# Filter by edge type
knows_in = alice.get_in_edges("Knows")
```

#### `get_both_edges(*labels) -> List[Edge]`

Get both incoming and outgoing edges, optionally filtered by label.

```python
all_edges = alice.get_both_edges()
print(f"Degree: {len(all_edges)}")

knows_edges = alice.get_both_edges("Knows")
```

## Edge Wrapper

The `Edge` class represents a connection between vertices with optional properties.

### Edge Properties

Edges have the same property methods as documents:

```python
# new_edge saves the edge when it creates it: pass its properties as keyword
# arguments, because setting them afterwards and saving again writes it a second time
edge = alice.new_edge("Knows", bob, since=2020, strength=0.9)

print(edge.get("since"))  # Output: 2020
edge.get_property_names()  # ['since', 'strength']
```

### Graph Methods

#### `get_in() -> Vertex`

Get the incoming (destination/head) vertex of the edge. Wraps `getInVertex()`.

```python
destination = edge.get_in()
print(f"Destination: {destination.get('name')}")
```

#### `get_out() -> Vertex`

Get the outgoing (source/tail) vertex of the edge. Wraps `getOutVertex()`.

```python
source = edge.get_out()
print(f"Source: {source.get('name')}")
```

## Best Practices

### 1. Prefer SQL/OpenCypher for set-based CRUD

```python
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Note SET title = ?, content = ?",
        "My Note",
        "Content",
    )

results = db.query("sql", "SELECT FROM Note WHERE flagged = true")
```

Use wrappers when you specifically need object-style mutation, wrapper traversal, or a
single looked-up record.

### 2. Always Save After Set

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

### 3. Prefer SQL DELETE unless you already have a looked-up wrapper

```python
# ❌ Query rows have no delete()
results = db.query("sql", "SELECT FROM Note")
for row in results:
    row.delete()  # AttributeError

# ✅ Wrapper delete on an explicitly looked-up record
with db.transaction():
    doc = db.lookup_by_rid("#1:0")
    doc.delete()

# ✅ Convert query results to RIDs, then delete via lookup
with db.transaction():
    rids = [doc.get_rid() for doc in db.query("sql", "SELECT FROM Note WHERE flagged = true")]
    for rid in rids:
        db.lookup_by_rid(rid).delete()

# ✅ Default pattern for bulk or query-based delete
with db.transaction():
    db.command("sql", "DELETE FROM Note WHERE flagged = true")
```

### 4. Create Indexes for Frequent Lookups

```python
db.command("sql", "CREATE INDEX ON Person (name) NOTUNIQUE")
```

### 5. Chain Methods for Brevity

```python
# Chaining
with db.transaction():
    doc = db.new_document("Note") \
        .set("title", "My Note") \
        .set("content", "Content") \
        .save()
```
