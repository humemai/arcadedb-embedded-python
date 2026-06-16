# Schema API

The Schema provides type management, index creation, and property definitions for documents, vertices, and edges.

## Overview

The `Schema` class enables:

- **Type Management**: Create document, vertex, and edge types
- **Property Definitions**: Define typed properties with constraints
- **Index Creation**: Create indexes for query optimization
- **Type Hierarchies**: Extend existing types
- **Schema Inspection**: Query existing schema definitions

!!! note "DSL-first recommendation"
    For application code, prefer ArcadeDB SQL DDL via `db.command("sql", ...)`.
    This page documents the Schema wrapper API for reference and advanced typed schema workflows.

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
    buckets: Optional[int] = None
) -> Any
```

Create a new vertex type. Returns the underlying Java `VertexType` object.

**Parameters:**

- `name` (str): Name of the vertex type
- `buckets` (Optional[int]): Number of buckets (engine default 3 when omitted)

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
    buckets: Optional[int] = None
) -> Any
```

Create a new edge type. Returns the underlying Java `EdgeType` object.

**Parameters:**

- `name` (str): Name of the edge type
- `buckets` (Optional[int]): Number of buckets (engine default 3 when omitted)

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
    buckets: Optional[int] = None
) -> Any
```

Create a new document type. Returns the underlying Java `DocumentType` object.

**Parameters:**

- `name` (str): Name of the document type
- `buckets` (Optional[int]): Number of buckets (engine default 3 when omitted)

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
schema.create_property(
    type_name: str,
    property_name: str,
    property_type: Union[str, PropertyType],
    of_type: Optional[str] = None
) -> Any
```

Create a property on a type. Returns the underlying Java `Property` object.

**Parameters:**

- `type_name` (str): Name of the type
- `property_name` (str): Name of the property
- `property_type` (str or `PropertyType`): ArcadeDB type (see types below)
- `of_type` (Optional[str]): Element type for `LIST`/`MAP` collections

**Returns:**

- Java `Property` object

**Property Types:**

The `PropertyType` enum (importable as `from arcadedb_embedded import PropertyType`)
defines the supported values:

- **Primitives**: `STRING`, `INTEGER`, `LONG`, `SHORT`, `BYTE`, `BOOLEAN`, `FLOAT`, `DOUBLE`, `DECIMAL`, `DATE`, `DATETIME`
- **Binary**: `BINARY`
- **Collections**: `LIST`, `MAP`, `EMBEDDED`
- **Links**: `LINK`
- **Vectors**: `ARRAY_OF_FLOATS`

Either the enum member or its string name may be passed.

**Example:**

```python
# Schema operations are auto-transactional
schema.create_vertex_type("User")

# String property
schema.create_property("User", "name", "STRING")

# Integer property (enum form)
from arcadedb_embedded import PropertyType
schema.create_property("User", "age", PropertyType.INTEGER)

# Date property
schema.create_property("User", "birthDate", "DATE")

# List property
schema.create_property("User", "tags", "LIST", of_type="STRING")

# Embedded property
schema.create_property("User", "profile", "EMBEDDED")
```

---

### get_or_create_property

```python
schema.get_or_create_property(
    type_name: str,
    property_name: str,
    property_type: Union[str, PropertyType],
    of_type: Optional[str] = None
) -> Any
```

Get an existing property or create it if it doesn't exist. Same parameters as
`create_property`. Returns the underlying Java `Property` object.

```python
prop = schema.get_or_create_property("User", "email", "STRING")
```

---

### drop_property

```python
schema.drop_property(type_name: str, property_name: str)
```

Drop a property from a type.

```python
schema.drop_property("User", "old_field")
```

!!! note "Property constraints"
    Constraints such as mandatory, not-null, default, and min/max are configured on the
    returned Java `Property` object (for example `prop.setMandatory(True)`) or via SQL
    DDL. The Python `Schema` wrapper itself only exposes property creation/removal.

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
- `index_type` (str or IndexType): Type of index (`"LSM_TREE"`, `"HASH"`, `"FULL_TEXT"`,
  `"LSM_VECTOR"`, `"GEOSPATIAL"`)

**Returns:**

- `Index`: Created index object

**Raises:**

- `ArcadeDBError`: If type doesn't exist or index creation fails

**Example:**

```python
# Schema operations are auto-transactional
# Unique index on username
schema.create_index("User", ["username"], unique=True)

# Exact-match lookup index
schema.create_index("Order", ["customerId"], index_type="HASH")

# Composite index
schema.create_index("Event", ["userId", "timestamp"])

# Full-text index
schema.create_index("Article", ["content"], index_type="FULL_TEXT")
```

**Index choice rules of thumb:**

- Use `HASH` for exact-match lookups when you do not need ranges or ordered scans.
- Use `LSM_TREE` when you need ranges, sorting, or a safe general-purpose default.
- Use `FULL_TEXT`, `LSM_VECTOR`, and `GEOSPATIAL` only for their specialized query
  types.
- `HASH` can be unique or non-unique. The index structure and uniqueness constraint are
  separate choices.

**SQL DSL equivalents:**

- `CREATE INDEX ON User (email) UNIQUE` -> unique `LSM_TREE`
- `CREATE INDEX ON User (email) NOTUNIQUE` -> non-unique `LSM_TREE`
- `CREATE INDEX ON User (email) UNIQUE_HASH` -> unique `HASH`
- `CREATE INDEX ON Order (customerId) NOTUNIQUE_HASH` -> non-unique `HASH`
- `CREATE INDEX ON Article (content) FULL_TEXT` -> `FULL_TEXT`
- `CREATE INDEX ON Doc (embedding) LSM_VECTOR ...` -> `LSM_VECTOR`
- `CREATE INDEX ON Place (location) GEOSPATIAL` -> `GEOSPATIAL`

**Vector (JVector) Parameters:**

!!! note
    `schema.create_index()` only accepts `type_name`, `property_names`, `unique`, and
    `index_type`. It does **not** take the JVector tuning parameters below. To configure a
    vector index from Python, use [`db.create_vector_index()`](database.md#create_vector_index)
    (which exposes `max_connections`, `beam_width`, `dimensions`, etc.), or SQL
    `CREATE INDEX ... LSM_VECTOR METADATA {...}`.

- **max_connections**: Max connections per node (default: 16; typical 8-32). Maps to
  JVector `maxConnections`.
- **beam_width**: Beam width for build/search (default: 100; typical 64-200). Maps to
  JVector `beamWidth`.
- **dimensions**: Vector size (must match your embeddings).
- **ef_search**: Query-time exact-search beam width override via SQL
  `vectorNeighbors(..., k, ef_search)`. Leave unset to use ArcadeDB's default/adaptive
  behavior.

## Type Inspection

### get_type

```python
schema.get_type(type_name: str) -> Optional[Type]
```

Get a type by name.

**Parameters:**

- `type_name` (str): Name of the type

**Returns:**

- `Optional[Type]`: Java `DocumentType`/`VertexType`/`EdgeType` object, or `None` if not
  found. Methods on this object are the underlying Java methods exposed by JPype
  (camelCase, e.g. `getName()`, `countType(True)`).

**Example:**

```python
# Check if type exists
user_type = schema.get_type("User")
if user_type:
    print(f"User type exists: {user_type.getName()}")
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

- `List[Any]`: All types in the schema as Java type objects

**Example:**

```python
for type_obj in schema.get_types():
    print(f"Type: {type_obj.getName()}")
```

---

### Type Methods

`get_type()` and `get_types()` return the raw Java type objects. Their methods are the
underlying Java methods exposed by JPype using camelCase names (for example `getName()`,
`getProperties()`, `getIndexesByProperties(...)`).

```python
type_obj = schema.get_type("User")

# Get type info (Java methods via JPype)
name = type_obj.getName()

# Get properties (Java Property objects)
for prop in type_obj.getProperties():
    print(f"{prop.getName()}: {prop.getType()}")
```

!!! tip "Prefer SQL for inspection"
    For schema inspection in application code, prefer SQL such as
    `db.query("sql", "SELECT FROM schema:types")` /
    `db.query("sql", "SELECT FROM schema:indexes")`, which returns Python-friendly
    `Result` rows instead of raw Java objects.

## Complete Example

```python
import arcadedb_embedded as arcadedb

# Create database with context manager to ensure clean close
with arcadedb.create_database("./social_network") as db:
    # Create schema (auto-transactional)
    # User vertex type
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "username", "STRING")
    db.schema.create_property("User", "email", "STRING")
    db.schema.create_property("User", "age", "INTEGER")
    db.schema.create_property("User", "tags", "LIST", of_type="STRING")
    db.schema.create_property("User", "createdAt", "DATETIME")

    # Post vertex type
    db.schema.create_vertex_type("Post")
    db.schema.create_property("Post", "title", "STRING")
    db.schema.create_property("Post", "content", "STRING")
    db.schema.create_property("Post", "timestamp", "DATETIME")

    # Follows edge type
    db.schema.create_edge_type("Follows")
    db.schema.create_property("Follows", "since", "DATETIME")

    # Likes edge type
    db.schema.create_edge_type("Likes")
    db.schema.create_property("Likes", "timestamp", "DATETIME")

    # Create indexes
    db.schema.create_index("User", ["username"], unique=True)
    db.schema.create_index("Post", ["timestamp"])

    # Verify schema (get_types() returns raw Java type objects)
    print("\n📋 Schema Summary:")
    for type_obj in db.schema.get_types():
        print(f"\nType: {type_obj.getName()}")
        for prop in type_obj.getProperties():
            print(f"    - {prop.getName()}: {prop.getType()}")
```

## Schema Evolution

```python
# Add property to an existing type (auto-transactional)
if db.schema.get_type("User").getProperty("phoneNumber") is None:
    db.schema.create_property("User", "phoneNumber", "STRING")
    print("✅ Added phoneNumber property")

# get_or_create_* helpers make evolution idempotent
db.schema.get_or_create_property("User", "phoneNumber", "STRING")
db.schema.get_or_create_index("User", ["email"], unique=True)
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

Property constraints are not exposed by the Python `Schema` wrapper. Apply them via SQL
DDL, or on the Java `Property` object returned by `create_property` (camelCase methods):

```python
# ✅ Recommended: SQL DDL for constraints (schema ops are auto-transactional)
db.schema.create_vertex_type("User")
db.command("sql", "CREATE PROPERTY User.username STRING (mandatory true, notnull true)")
db.command("sql", "CREATE PROPERTY User.age INTEGER (min 0, max 150)")

# Or configure the returned Java Property object directly
username = db.schema.create_property("User", "nickname", "STRING")
username.setMandatory(True)
username.setNotNull(True)
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
    db.schema.create_vertex_type("User")
    db.schema.create_property("User", "username", "STRING")
    db.schema.create_property("User", "email", "STRING")

    db.schema.create_index("User", ["username"], unique=True)

    print("✅ Schema initialized")

# Use it
init_schema(db)
```

### 2. Schema Export

```python
def export_schema(db):
    """Export schema to dict (get_types() yields raw Java type objects)."""
    schema_dict = {}

    for type_obj in db.schema.get_types():
        type_name = str(type_obj.getName())
        schema_dict[type_name] = {"properties": {}, "indexes": []}

        # Export properties (Java Property objects via JPype)
        for prop in type_obj.getProperties():
            schema_dict[type_name]["properties"][str(prop.getName())] = str(
                prop.getType()
            )

    return schema_dict

# Use it
schema_export = export_schema(db)
print(json.dumps(schema_export, indent=2))
```

!!! tip
    For schema export you can also query `db.query("sql", "SELECT FROM schema:types")`
    and `db.query("sql", "SELECT FROM schema:indexes")`, which return Python `Result`
    rows instead of raw Java objects.

### 3. Schema Migration

```python
def migrate_schema_v1_to_v2(db):
    """Migrate schema from v1 to v2 (idempotent via get_or_create_*)."""
    # Add new property if missing
    db.schema.get_or_create_property("User", "status", "STRING")
    print("✅ Ensured status property")

    # Add new index if missing
    db.schema.get_or_create_index("User", ["status"])
    print("✅ Ensured status index")

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
# ✅ Good: Check property exists on the Java type object (camelCase JPype methods)
user_type = schema.get_type("User")
if user_type is not None and user_type.existsProperty("email"):
    print(f"Email type: {user_type.getProperty('email').getType()}")
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
