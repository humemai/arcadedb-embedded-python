# Schema Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_schema.py){ .md-button }

## Overview

Schema tests cover:

- ✅ **Type Creation** - Document, vertex, and edge types, plus `get_or_create_*` variants
- ✅ **IndexType enum** - Includes current Java index values (`GEOSPATIAL`, `HASH`)
- ✅ **Type Queries** - Getting types and checking existence
- ✅ **Type Query Stability** - Repeated `get_types()` calls stay duplicate-free
- ✅ **Type Deletion** - Removing types from schema
- ✅ **Property Creation** - Adding properties to types, plus `get_or_create_property`
- ✅ **Property Deletion** - Removing properties
- ✅ **Index Creation** - LSM_TREE, unique, composite, FULL_TEXT indexes
- ✅ **Index Queries** - Getting and listing indexes
- ✅ **Index Deletion** - Removing indexes
- ✅ **Property Types** - All ArcadeDB property types, including LIST/MAP
- ✅ **Vector Indexes** - Retrieval/listing via Schema API and LSM vector index operations

## Test Classes

### TestTypeCreation

Tests creating document, vertex, and edge types, plus the `get_or_create_*` variants.

**Tests:**

- `test_create_document_type()` - Basic document type creation
- `test_create_vertex_type()` - Basic vertex type creation
- `test_create_edge_type()` - Basic edge type creation
- `test_create_type_with_buckets()` - Custom bucket count (`buckets=5`)
- `test_duplicate_type_creation_fails()` - Re-creating a type raises `ArcadeDBError`
- `test_get_or_create_document_type_new()` - `get_or_create` for a new document type
- `test_get_or_create_document_type_existing()` - `get_or_create` for an existing document type
- `test_get_or_create_vertex_type_new()` - `get_or_create` for a new vertex type
- `test_get_or_create_vertex_type_existing()` - `get_or_create` for an existing vertex type
- `test_get_or_create_edge_type_new()` - `get_or_create` for a new edge type
- `test_get_or_create_edge_type_existing()` - `get_or_create` for an existing edge type

**Pattern:**

```python
with arcadedb.create_database("./test_db") as db:
    schema = db.schema

    # Basic types
    schema.create_vertex_type("Person")
    schema.create_edge_type("Knows")

    # With buckets
    schema.create_document_type("DocWithBuckets", buckets=5)

    # Idempotent variant
    schema.get_or_create_vertex_type("NewVertex")
```

---

### IndexType enum (module-level)

**Test:**

- `test_index_type_enum_includes_new_java_index_types()` - Asserts the Python `IndexType` enum exposes current Java values: `IndexType.GEOSPATIAL.value == "GEOSPATIAL"` and `IndexType.HASH.value == "HASH"`

---

### TestTypeQueries

Tests querying schema for types.

**Tests:**

- `test_exists_type_true()` - `exists_type` returns `True` for an existing type
- `test_exists_type_false()` - `exists_type` returns `False` for a non-existent type
- `test_get_type_existing()` - `get_type` returns the type object for an existing type
- `test_get_type_non_existent()` - `get_type` returns `None` for a non-existent type
- `test_get_types()` - `get_types` lists all types
- `test_get_types_has_no_duplicates_across_repeated_calls()` - Repeated calls stay stable and duplicate-free

**Pattern:**

```python
with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")

    # Get type
    user_type = schema.get_type("User")

    # Check existence
    if schema.exists_type("User"):
        print("User type exists")

    # List all types
    for type_obj in schema.get_types():
        print(type_obj.getName())
```

---

### TestTypeDeletion

Tests removing types from schema.

**Tests:**

- `test_drop_type()` - `drop_type` removes a type
- `test_drop_non_existent_type_fails()` - Dropping a non-existent type raises `ArcadeDBError`

**Pattern:**

```python
with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_document_type("TempType")

    # Drop type
    schema.drop_type("TempType")

    assert not schema.exists_type("TempType")
```

---

### TestPropertyCreation

Tests adding properties to types.

**Tests:**

- `test_create_simple_property()` - Basic STRING property
- `test_create_integer_property()` - INTEGER property
- `test_create_list_property()` - LIST property using `of_type=PropertyType.STRING`
- `test_create_multiple_properties()` - Several properties on the same type
- `test_create_property_on_non_existent_type_fails()` - Raises `ArcadeDBError`
- `test_get_or_create_property_new()` - `get_or_create_property` for a new property
- `test_get_or_create_property_existing()` - `get_or_create_property` for an existing property

**Pattern:**

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")

    # Basic property
    schema.create_property("User", "name", PropertyType.STRING)

    # Typed property
    schema.create_property("User", "age", PropertyType.INTEGER)

    # List property
    schema.create_property(
        "User", "tags", PropertyType.LIST, of_type=PropertyType.STRING
    )

    # Idempotent variant
    schema.get_or_create_property("User", "email", PropertyType.STRING)
```

---

### TestPropertyDeletion

Tests removing properties from types.

**Tests:**

- `test_drop_property()` - `drop_property` removes a property (verified by re-creating it)
- `test_drop_property_from_non_existent_type_fails()` - Raises `ArcadeDBError`

**Pattern:**

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "temp", PropertyType.STRING)

    # Drop property
    schema.drop_property("User", "temp")

    # Property no longer exists; it can be created again
    schema.create_property("User", "temp", PropertyType.STRING)
```

---

### TestIndexCreation

Tests creating indexes on types.

**Tests:**

- `test_create_simple_index()` - Single-property index
- `test_create_unique_index()` - Unique index (`unique=True`)
- `test_create_composite_index()` - Multi-property index
- `test_create_full_text_index()` - `IndexType.FULL_TEXT` index
- `test_create_lsm_tree_index()` - Explicit `IndexType.LSM_TREE` index
- `test_get_or_create_index_new()` - `get_or_create_index` for a new index
- `test_get_or_create_index_existing()` - `get_or_create_index` for an existing index

**Pattern:**

```python
from arcadedb_embedded import IndexType, PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "username", PropertyType.STRING)

    # Unique index
    schema.create_index("User", ["username"], unique=True)

    # Composite index
    schema.create_vertex_type("Person")
    schema.create_property("Person", "firstName", PropertyType.STRING)
    schema.create_property("Person", "lastName", PropertyType.STRING)
    schema.create_index("Person", ["firstName", "lastName"])

    # Full-text index
    schema.create_document_type("Article")
    schema.create_property("Article", "content", PropertyType.STRING)
    schema.create_index("Article", ["content"], index_type=IndexType.FULL_TEXT)
```

---

### TestIndexQueries

Tests querying indexes.

**Tests:**

- `test_exists_index_true()` - `exists_index` returns `True` for an existing index
- `test_exists_index_false()` - `exists_index` returns `False` for a non-existent index
- `test_get_indexes()` - `get_indexes` lists all indexes

**Pattern:**

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "email", PropertyType.STRING)
    schema.create_index("User", ["email"], unique=True)

    # Get all indexes
    for index in schema.get_indexes():
        print(index.getName(), index.getTypeName())

    # Check existence by index name (format: Type[property])
    name = schema.get_indexes()[0].getName()
    assert schema.exists_index(name)
```

---

### TestIndexDeletion

Tests removing indexes.

**Tests:**

- `test_drop_index()` - `drop_index` removes an index by its name
- `test_drop_non_existent_index_fails()` - Dropping a non-existent index raises `ArcadeDBError`

**Pattern:**

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "temp", PropertyType.STRING)
    schema.create_index("User", ["temp"])

    # Look up the generated index name, then drop it
    index_name = next(
        idx.getName()
        for idx in schema.get_indexes()
        if "User" in idx.getTypeName() and "temp" in idx.getName()
    )
    schema.drop_index(index_name)

    assert schema.exists_index(index_name) is False
```

---

### TestPropertyTypes

Tests all ArcadeDB property types.

**Tests:**

- `test_all_property_types()` - Creates one property for each scalar `PropertyType`: BOOLEAN, BYTE, SHORT, INTEGER, LONG, FLOAT, DOUBLE, DECIMAL, STRING, BINARY, DATE, DATETIME
- `test_complex_property_types()` - Creates LIST properties (with `of_type`) and a MAP property

**Pattern:**

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_document_type("AllTypes")

    # Scalar types
    schema.create_property("AllTypes", "intProp", PropertyType.INTEGER)
    schema.create_property("AllTypes", "stringProp", PropertyType.STRING)
    schema.create_property("AllTypes", "dateProp", PropertyType.DATE)

    # Complex types
    schema.create_property(
        "AllTypes", "tags", PropertyType.LIST, of_type=PropertyType.STRING
    )
    schema.create_property("AllTypes", "metadata", PropertyType.MAP)
```

---

### TestVectorIndexSchemaOps

Tests vector-index retrieval and listing via the Schema API.

**Tests:**

- `test_get_index_by_name_existing()` - `get_index_by_name` returns an existing index
- `test_get_index_by_name_non_existent()` - `get_index_by_name` returns `None` for a missing index
- `test_list_vector_indexes_empty()` - `list_vector_indexes` returns an empty list when no vector indexes exist
- `test_get_vector_index_non_existent()` - `get_vector_index` returns `None` when no index exists on the property
- `test_get_vector_index_wrong_type()` - `get_vector_index` returns `None` for a non-vector index

---

### TestIntegration

Tests complete schema workflows.

**Tests:**

- `test_create_complete_graph_schema()` - Creates vertex/edge types with properties and indexes (including a `FULL_TEXT` index on `Post.content`)
- `test_schema_modification_workflow()` - Adds properties and indexes to an existing type
- `test_get_or_create_idempotent_schema_creation()` - `get_or_create_*` methods are idempotent across repeated calls

**Pattern:**

```python
from arcadedb_embedded import IndexType, PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema

    # Create types
    schema.create_vertex_type("User")
    schema.create_vertex_type("Post")
    schema.create_edge_type("Follows")
    schema.create_edge_type("Wrote")

    # Add properties
    schema.create_property("User", "username", PropertyType.STRING)
    schema.create_property("User", "email", PropertyType.STRING)
    schema.create_property("Post", "content", PropertyType.STRING)

    # Create indexes
    schema.create_index("User", ["username"], unique=True)
    schema.create_index("User", ["email"], unique=True)
    schema.create_index("Post", ["content"], index_type=IndexType.FULL_TEXT)
```

---

### TestLSMVectorIndexSchemaOps

Tests LSM vector index schema operations created via `db.create_vector_index(...)`.

**Tests:**

- `test_list_lsm_vector_indexes()` - After `create_vector_index("Doc", "embedding", dimensions=3)`, `list_vector_indexes()` includes the new index
- `test_get_lsm_vector_index_existing()` - `get_vector_index("Doc", "embedding")` returns a `VectorIndex` instance
- `test_get_lsm_vector_index_persistence()` - `get_vector_index` can load a persisted LSM index; `get_size()` reflects inserted vectors

## Test Patterns

### Type Creation

```python
with arcadedb.create_database("./test_db") as db:
    # Schema operations are auto-transactional (no wrapper needed)
    db.schema.create_vertex_type("User")
    db.schema.create_edge_type("Follows")
```

### Property Definition

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")

    # Add properties
    schema.create_property("User", "name", PropertyType.STRING)
    schema.create_property(
        "User", "tags", PropertyType.LIST, of_type=PropertyType.STRING
    )
```

### Index Creation

```python
with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "username", PropertyType.STRING)

    # Unique index
    schema.create_index("User", ["username"], unique=True)
```

## Common Assertions

```python
from arcadedb_embedded import PropertyType

with arcadedb.create_database("./test_db") as db:
    schema = db.schema
    schema.create_vertex_type("User")
    schema.create_property("User", "name", PropertyType.STRING)

    # Type exists
    assert schema.exists_type("User")

    # Type object is retrievable
    assert schema.get_type("User") is not None

    # Index exists (after creating one)
    schema.create_index("User", ["name"])
    assert len(schema.get_indexes()) > 0
```

## Key Takeaways

1. **Schema ops are auto-transactional** - No wrapper needed for type/property/index creation
2. **Check existence** - Use `exists_type()` / `exists_index()` before creating
3. **Use `get_or_create_*`** - Idempotent type/property/index creation
4. **Index frequently queried** - Properties used in WHERE clauses
5. **Use `PropertyType` / `IndexType` enums** - Match property and index types to your data
6. **Vector indexes via the Schema API** - Use `create_vector_index()`, then
   `list_vector_indexes()` and `get_vector_index()` to retrieve them

## See Also

- **[Schema API](../../api/schema.md)** - Full API reference
- **[Example 02: Social Network](../../examples/02_social_network_graph.md)** - Schema patterns
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** - Vector indexes
- **[Architecture Guide](../architecture.md)** - Schema design principles
