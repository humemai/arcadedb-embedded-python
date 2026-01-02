# Schema Tests

The `test_schema.py` file contains **12 test classes** covering schema management, type creation, properties, and indexes.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/tests/test_schema.py){ .md-button }

## Overview

Schema tests cover:

- ✅ **Type Creation** - Vertex, edge, and document types
- ✅ **Type Queries** - Getting types and checking existence
- ✅ **Type Deletion** - Removing types from schema
- ✅ **Property Creation** - Adding properties to types
- ✅ **Property Deletion** - Removing properties
- ✅ **Index Creation** - LSM_TREE, HNSW, FULL_TEXT indexes
- ✅ **Index Queries** - Getting and listing indexes
- ✅ **Index Deletion** - Removing indexes
- ✅ **Property Types** - All ArcadeDB property types
- ✅ **Vector Indexes** - HNSW configuration and operations

## Test Classes

### TestTypeCreation
Tests creating vertex, edge, and document types.

**Tests:**
- `test_create_vertex_type()` - Basic vertex type creation
- `test_create_edge_type()` - Basic edge type creation
- `test_create_document_type()` - Basic document type creation
- `test_create_type_with_buckets()` - Custom bucket count

**Pattern:**
```python
schema = db.schema

# Basic type
schema.create_vertex_type("User")

# With buckets
schema.create_vertex_type("Product", buckets=10)
```

---

### TestTypeQueries
Tests querying schema for types.

**Tests:**
- `test_get_type()` - Get type by name
- `test_exists_type()` - Check if type exists
- `test_get_types()` - List all types
- `test_get_type_properties()` - List type properties

**Pattern:**
```python
# Get type
user_type = schema.get_type("User")

# Check existence
if schema.exists_type("User"):
    print("User type exists")

# List all types
for type_obj in schema.get_types():
    print(type_obj.get_name())
```

---

### TestTypeDeletion
Tests removing types from schema.

**Tests:**
- `test_delete_type()` - Remove type
- `test_delete_type_with_data()` - Remove type with records

**Pattern:**
```python
schema.create_vertex_type("Temp")

# Delete type
schema.delete_type("Temp")

assert not schema.exists_type("Temp")
```

---

### TestPropertyCreation
Tests adding properties to types.

**Tests:**
- `test_create_property()` - Basic property
- `test_create_property_with_type()` - Typed property
- `test_create_list_property()` - List property
- `test_create_embedded_property()` - Embedded property
- `test_property_constraints()` - Mandatory, not null, defaults

**Pattern:**
```python
user_type = schema.get_type("User")

# Basic property
user_type.create_property("name", "STRING")

# With constraints
name_prop = user_type.get("name")
name_prop.set_mandatory(True)
name_prop.set_not_null(True)

# List property
user_type.create_property("tags", "LIST", of_type="STRING")
```

---

### TestPropertyDeletion
Tests removing properties from types.

**Tests:**
- `test_delete_property()` - Remove property
- `test_delete_property_with_data()` - Remove property with data

**Pattern:**
```python
user_type = schema.get_type("User")
user_type.create_property("temp", "STRING")

# Delete property
user_type.delete_property("temp")

assert user_type.get("temp") is None
```

---

### TestIndexCreation
Tests creating indexes on types.

**Tests:**
- `test_create_lsm_index()` - LSM_TREE index
- `test_create_unique_index()` - Unique index
- `test_create_composite_index()` - Multi-property index
- `test_create_fulltext_index()` - Full-text search index

**Pattern:**
```python
# Unique index
schema.create_index("User", ["username"], unique=True)

# Composite index
schema.create_index("Event", ["userId", "timestamp"])

# Full-text index
schema.create_index("Article", ["content"], index_type="FULL_TEXT")
```

---

### TestIndexQueries
Tests querying indexes.

**Tests:**
- `test_get_indexes()` - List all indexes
- `test_get_type_indexes()` - Get indexes for type
- `test_get_index_properties()` - Get indexed properties

**Pattern:**
```python
# Get all indexes
for index in schema.get_indexes():
    print(index.get_name())

# Get indexes for type
user_type = schema.get_type("User")
for index in user_type.get_indexes():
    print(f"Index: {index.get_property_names()}")
```

---

### TestIndexDeletion
Tests removing indexes.

**Tests:**
- `test_delete_index()` - Remove index
- `test_delete_index_by_name()` - Remove by index name

**Pattern:**
```python
# Create index
schema.create_index("User", ["email"], unique=True)

# Delete index
schema.drop_index("User[email]")
```

---

### TestPropertyTypes
Tests all ArcadeDB property types.

**Tests:**
- `test_string_property()` - STRING type
- `test_integer_property()` - INTEGER type
- `test_long_property()` - LONG type
- `test_float_property()` - FLOAT type
- `test_double_property()` - DOUBLE type
- `test_boolean_property()` - BOOLEAN type
- `test_date_property()` - DATE type
- `test_datetime_property()` - DATETIME type
- `test_binary_property()` - BINARY type
- `test_list_property()` - LIST type
- `test_map_property()` - MAP type

**Pattern:**
```python
type_obj = schema.create_vertex_type("AllTypes")

# Create all property types
type_obj.create_property("name", "STRING")
type_obj.create_property("age", "INTEGER")
type_obj.create_property("score", "DOUBLE")
type_obj.create_property("active", "BOOLEAN")
type_obj.create_property("birthDate", "DATE")
type_obj.create_property("tags", "LIST", of_type="STRING")
```

---

### TestIntegration
Tests complete schema workflows.

**Tests:**
- `test_complete_schema_setup()` - Full schema creation
- `test_schema_migration()` - Evolving schema
- `test_schema_export_import()` - Schema serialization

**Pattern:**
```python
# Complete schema setup
schema = db.schema

# Create types
user_type = schema.create_vertex_type("User")
post_type = schema.create_vertex_type("Post")
likes_type = schema.create_edge_type("Likes")

# Add properties
user_type.create_property("username", "STRING")
user_type.create_property("email", "STRING")
post_type.create_property("title", "STRING")
post_type.create_property("content", "STRING")

# Create indexes
schema.create_index("User", ["username"], unique=True)

schema.create_index("User", ["email"], unique=True)
```

## Test Patterns

### Type Creation
```python
schema = db.schema

# In transaction
with db.transaction():
    schema.create_vertex_type("User")
    schema.create_edge_type("Follows")
```

### Property Definition
```python
user_type = schema.get_type("User")

# Add property
user_type.create_property("name", "STRING")

# Set constraints
prop = user_type.get("name")
prop.set_mandatory(True)
prop.set_not_null(True)
```

### Index Creation
```python
# Unique index
schema.create_index("User", ["username"], unique=True)
```

## Common Assertions

```python
# Type exists
assert schema.exists_type("User")

# Type has property
user_type = schema.get_type("User")
assert user_type.get("name") is not None

# Index exists
indexes = user_type.get_indexes()
assert len(indexes) > 0

# Property type
prop = user_type.get("age")
assert str(prop.get_type()) == "INTEGER"
```

## Key Takeaways

1. **Create in transactions** - Schema operations need transactions
2. **Check existence** - Use `exists_type()` before creating
3. **Set constraints** - Use `set_mandatory()`, `set_not_null()`
4. **Index frequently queried** - Properties used in WHERE clauses
5. **Use appropriate types** - Match property types to data
6. **Configure HNSW** - Tune M, efConstruction, ef for vectors

## See Also

- **[Schema API](../../api/schema.md)** - Full API reference
- **[Example 02: Social Network](../../examples/02_social_network_graph.md)** - Schema patterns
- **[Example 03: Vector Search](../../examples/03_vector_search.md)** - HNSW indexes
- **[Architecture Guide](../architecture.md)** - Schema design principles
