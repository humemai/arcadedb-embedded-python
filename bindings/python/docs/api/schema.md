# Schema API

The Schema provides type management, index creation, and property definitions for documents, vertices, and edges.

## Overview

The `Schema` class enables:

- **Type Management**: Create document, vertex, and edge types
- **Property Definitions**: Define typed properties with constraints
- **Index Creation**: Create indexes for query optimization
- **Type Hierarchies**: Extend existing types
- **Schema Inspection**: Query existing schema definitions

## Getting Schema

```python
import arcadedb_embedded as arcadedb

# Use context manager to ensure clean close
with arcadedb.create_database("./mydb") as db:
    # Create types (Schema operations are auto-transactional)
    # Vertex type
    user_type = db.schema.create_vertex_type("User")

    # Edge type
    follows_type = db.schema.create_edge_type("Follows")

    # Document type
    log_type = db.schema.create_document_type("LogEntry")
```

!!! note "Auto-Transactional"
    Schema operations (create type, create property, create index) are **auto-transactional**.
    Do **not** wrap them in `with db.transaction():` blocks.

## Type Creation Methods

### create_vertex_type

```python
schema.create_vertex_type(
    name: str,
    buckets: int = 3
) -> VertexType
```

Create a new vertex type.

**Parameters:**

- `name` (str): Name of the vertex type
- `buckets` (int): Number of buckets (default: 3)

**Returns:**

- `VertexType`: Created vertex type

**Example:**

```python
# Schema operations are auto-transactional
# Basic vertex type
user_type = schema.create_vertex_type("User")

# With custom buckets
product_type = schema.create_vertex_type("Product", buckets=10)
```

---

### create_edge_type

```python
schema.create_edge_type(
    name: str,
    buckets: int = 3
) -> EdgeType
```

Create a new edge type.

**Parameters:**

- `name` (str): Name of the edge type
- `buckets` (int): Number of buckets (default: 3)

**Returns:**

- `EdgeType`: Created edge type

**Example:**

```python
# Schema operations are auto-transactional
# Basic edge type
follows_type = schema.create_edge_type("Follows")

# With custom buckets
purchased_type = schema.create_edge_type("Purchased", buckets=5)
```

---

### create_document_type

```python
schema.create_document_type(
    name: str,
    buckets: int = 3
) -> DocumentType
```

Create a new document type.

**Parameters:**

- `name` (str): Name of the document type
- `buckets` (int): Number of buckets (default: 3)

**Returns:**

- `DocumentType`: Created document type

**Example:**

```python
# Schema operations are auto-transactional
# Basic document type
log_type = schema.create_document_type("LogEntry")

# With custom buckets
event_type = schema.create_document_type("Event", buckets=8)
```

## Property Definition

### create_property

```python
type_obj.create_property(
    property_name: str,
    property_type: str,
    of_type: Optional[str] = None
) -> Property
```

Create a property on a type.

**Parameters:**

- `property_name` (str): Name of the property
- `property_type` (str): ArcadeDB type (see types below)
- `of_type` (Optional[str]): Element type for collections

**Returns:**

- `Property`: Created property

**Property Types:**

- **Primitives**: `STRING`, `INTEGER`, `LONG`, `SHORT`, `BYTE`, `BOOLEAN`, `FLOAT`, `DOUBLE`, `DECIMAL`, `DATE`, `DATETIME`
- **Binary**: `BINARY`
- **Collections**: `LIST`, `MAP`, `EMBEDDED`
- **Links**: `LINK`

**Example:**

```python
# Schema operations are auto-transactional
user_type = schema.create_vertex_type("User")

# String property
user_type.create_property("name", "STRING")

# Integer property
user_type.create_property("age", "INTEGER")

# Date property
user_type.create_property("birthDate", "DATE")

# List property
user_type.create_property("tags", "LIST", of_type="STRING")

# Embedded property
user_type.create_property("profile", "EMBEDDED")
```

---

### Property with Constraints

```python
# Schema operations are auto-transactional
user_type = schema.create_vertex_type("User")

# Required property
name_prop = user_type.create_property("name", "STRING")
name_prop.set_mandatory(True)
name_prop.set_not_null(True)

# Property with default
status_prop = user_type.create_property("status", "STRING")
status_prop.set_default("active")

# Property with min/max
age_prop = user_type.create_property("age", "INTEGER")
age_prop.set_min(0)
age_prop.set_max(150)
```

## Index Creation

### create_index

```python
schema.create_index(
    type_name: str,
    property_names: List[str],
    unique: bool = False,
    index_type: Union[str, IndexType] = "LSM_TREE"
) -> Index
```

Create an index on a type.

**Parameters:**

- `type_name` (str): Name of the type
- `property_names` (List[str]): List of property names to index
- `unique` (bool): Whether the index should enforce uniqueness (default: `False`)
- `index_type` (str or IndexType): Type of index (`"LSM_TREE"`, `"FULL_TEXT"`)

**Returns:**

- `Index`: Created index object

**Raises:**

- `ArcadeDBError`: If type doesn't exist or index creation fails

**Example:**

```python
# Schema operations are auto-transactional
# Unique index on username
schema.create_index("User", ["username"], unique=True)

# Composite index
schema.create_index("Event", ["userId", "timestamp"])

# Full-text index
schema.create_index("Article", ["content"], index_type="FULL_TEXT")
```

**Vector (JVector) Parameters:**

- **max_connections**: Max connections per node (default: 32; typical 16-64). Maps to JVector `maxConnections`.
- **beam_width**: Beam width for build/search (default: 256; typical 128-400). Maps to JVector `beamWidth`.
- **dimensions**: Vector size (must match your embeddings).
- **overquery_factor**: Search-time candidate multiplier (default: 16; typical 8-32). Higher improves recall with slower search.

## Type Inspection

### get_type

```python
schema.get_type(type_name: str) -> Optional[Type]
```

Get a type by name.

**Parameters:**

- `type_name` (str): Name of the type

**Returns:**

- `Optional[Type]`: Type object, or None if not found

**Example:**

```python
# Check if type exists
user_type = schema.get_type("User")
if user_type:
    print(f"User type exists with {user_type.count_records()} records")
else:
    print("User type not found")
```

---

### exists_type

```python
schema.exists_type(type_name: str) -> bool
```

Check if type exists.

**Parameters:**

- `type_name` (str): Name of the type

**Returns:**

- `bool`: True if exists

**Example:**

```python
if not schema.exists_type("User"):
    schema.create_vertex_type("User")  # Schema ops are auto-transactional
```

---

### get_types

```python
schema.get_types() -> List[Type]
```

Get all types.

**Returns:**

- `List[Type]`: All types in schema

**Example:**

```python
for type_obj in schema.get_types():
    print(f"Type: {type_obj.get_name()}")
    print(f"  Records: {type_obj.count_records()}")
    print(f"  Properties: {[p.get_name() for p in type_obj.get_properties()]}")
```

---

### Type Methods

```python
type_obj = schema.get_type("User")

# Get type info
name = type_obj.get_name()
count = type_obj.count_records()
buckets = type_obj.get_buckets()

# Get properties
properties = type_obj.get_properties()
for prop in properties:
    print(f"{prop.get_name()}: {prop.get_type()}")

# Get specific property
username_prop = type_obj.get("username")
if username_prop:
    print(f"Type: {username_prop.get_type()}")
    print(f"Mandatory: {username_prop.is_mandatory()}")
    print(f"Not Null: {username_prop.is_not_null()}")

# Get indexes
indexes = type_obj.get_indexes()
for index in indexes:
    print(f"Index: {index.get_name()}")
    print(f"  Properties: {index.get_property_names()}")
    print(f"  Unique: {index.is_unique()}")
```

## Complete Example

```python
import arcadedb_embedded as arcadedb

# Create database with context manager to ensure clean close
with arcadedb.create_database("./social_network") as db:
    # Create schema (auto-transactional)
    # User vertex type
    user_type = db.schema.create_vertex_type("User")
    user_type.create_property("username", "STRING")
    user_type.create_property("email", "STRING")
    user_type.create_property("age", "INTEGER")
    user_type.create_property("tags", "LIST", of_type="STRING")
    user_type.create_property("createdAt", "DATETIME")

    # Make username required and unique
    username_prop = user_type.get("username")
    username_prop.set_mandatory(True)
    username_prop.set_not_null(True)

    # Post vertex type
    post_type = db.schema.create_vertex_type("Post")
    post_type.create_property("title", "STRING")
    post_type.create_property("content", "STRING")
    post_type.create_property("timestamp", "DATETIME")

    # Follows edge type
    follows_type = db.schema.create_edge_type("Follows")
    follows_type.create_property("since", "DATETIME")

    # Likes edge type
    likes_type = db.schema.create_edge_type("Likes")
    likes_type.create_property("timestamp", "DATETIME")

    # Create indexes
    db.schema.create_index("User", ["username"], unique=True)
    db.schema.create_index("Post", ["timestamp"])

    # Verify schema
    print("\n📋 Schema Summary:")
    for type_obj in db.schema.get_types():
        print(f"\nType: {type_obj.get_name()}")
        print(f"  Records: {type_obj.count_records()}")

        properties = type_obj.get_properties()
        if properties:
            print(f"  Properties:")
            for prop in properties:
                print(f"    - {prop.get_name()}: {prop.get_type()}")

        indexes = type_obj.get_indexes()
        if indexes:
            print(f"  Indexes:")
            for index in indexes:
                unique_str = " (UNIQUE)" if index.is_unique() else ""
                print(f"    - {index.get_name()}{unique_str}")
```

## Schema Evolution

```python
# Add property to existing type (auto-transactional)
user_type = schema.get_type("User")
if not user_type.get("phoneNumber"):
    user_type.create_property("phoneNumber", "STRING")
    print("✅ Added phoneNumber property")

# Add index to existing type (auto-transactional)
if not any(idx.get_property_names() == ["email"]
           for idx in schema.get_type("User").get_indexes()):
    schema.create_index("User", ["email"], unique=True)
    print("✅ Added email index")
```

## Best Practices

### 1. Schema Ops Are Auto-Transactional

```python
# ✅ Correct
schema.create_vertex_type("User")
schema.create_edge_type("Follows")

# ❌ Unnecessary
with db.transaction():
    schema.create_vertex_type("User")
```

### 2. Check Existence Before Creating

```python
# ✅ Good: Check first
if not schema.exists_type("User"):
    schema.create_vertex_type("User")

# ❌ Bad: Don't check
schema.create_vertex_type("User")  # May error if exists
```

### 3. Create Indexes for Frequent Queries

```python
# ✅ Good: Index frequently queried properties
schema.create_index("Event", ["timestamp"])
schema.create_index("Event", ["userId", "timestamp"])
```

### 4. Use Appropriate Bucket Counts

```python
# ✅ Good: Scale buckets with data size
if expected_records < 100000:
    buckets = 3  # Default
elif expected_records < 1000000:
    buckets = 10
else:
    buckets = 20

schema.create_vertex_type("BigData", buckets=buckets)
```

### 5. Set Property Constraints

```python
# ✅ Good: Define constraints (schema ops are auto-transactional)
user_type = schema.create_vertex_type("User")

    # Required username
    username = user_type.create_property("username", "STRING")
    username.set_mandatory(True)
    username.set_not_null(True)

    # Valid age range
    age = user_type.create_property("age", "INTEGER")
    age.set_min(0)
    age.set_max(150)
```

## Common Patterns

### 1. Schema Initialization

```python
def init_schema(db):
    """Initialize schema if not exists"""
    if db.schema.exists_type("User"):
        print("Schema already initialized")
        return

    # Schema operations are auto-transactional
    user_type = db.schema.create_vertex_type("User")
    user_type.create_property("username", "STRING")
    user_type.create_property("email", "STRING")

    db.schema.create_index("User", ["username"], unique=True)

    print("✅ Schema initialized")

# Use it
init_schema(db)
```

### 2. Schema Export

```python
def export_schema(db):
    """Export schema to dict"""
    schema_dict = {}

    for type_obj in db.schema.get_types():
        type_name = type_obj.get_name()
        schema_dict[type_name] = {
            "type": type_obj.__class__.__name__,
            "properties": {},
            "indexes": []
        }

        # Export properties
        for prop in type_obj.get_properties():
            schema_dict[type_name]["properties"][prop.get_name()] = {
                "type": str(prop.get_type()),
                "mandatory": prop.is_mandatory(),
                "not_null": prop.is_not_null()
            }

        # Export indexes
        for index in type_obj.get_indexes():
            schema_dict[type_name]["indexes"].append({
                "name": index.get_name(),
                "properties": list(index.get_property_names()),
                "unique": index.is_unique()
            })

    return schema_dict

# Use it
schema_export = export_schema(db)
print(json.dumps(schema_export, indent=2))
```

### 3. Schema Migration

```python
def migrate_schema_v1_to_v2(db):
    """Migrate schema from v1 to v2"""
    user_type = db.schema.get_type("User")

    # Add new property
    if not user_type.get("status"):
        user_type.create_property("status", "STRING")
        print("✅ Added status property")

    # Add new index
    if not any(idx.get_property_names() == ["status"]
               for idx in user_type.get_indexes()):
        db.schema.create_index("User", ["status"])
        print("✅ Added status index")

# Use it
migrate_schema_v1_to_v2(db)
```

## Troubleshooting

### Type Already Exists Error

```python
# ✅ Good: Check first
if not schema.exists_type("User"):
    schema.create_vertex_type("User")
```

### Property Not Found

```python
# ✅ Good: Check property exists
user_type = schema.get_type("User")
email_prop = user_type.get("email")
if email_prop:
    print(f"Email type: {email_prop.get_type()}")
else:
    print("Email property not found")
```

### Index Creation Fails

```python
# ✅ Good: Create index (auto-transactional)
schema.create_index("User", ["username"], unique=True)
```

## See Also

- **[Database API](database.md)** - Database operations
- **[Transactions API](transactions.md)** - Transaction management
- **[Vector Search Guide](../guide/vectors.md)** - HNSW (JVector) indexes
- **[Example 03: Vector Search](../examples/03_vector_search.md)** - Real-world schema usage
- **[Example 02: Social Network](../examples/02_social_network_graph.md)** - Graph schema patterns
