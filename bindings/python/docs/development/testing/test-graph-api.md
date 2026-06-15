# Graph API Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph_api.py){ .md-button }

There are 18 tests covering Pythonic wrappers (Document, Vertex, Edge classes) and their methods.

## Overview

Tests validate:

- Vertex/Document/Edge wrapper creation via `db.new_vertex()`, `db.new_document()`, and `vertex.new_edge()`
- Fluent interface (chaining `.set()` calls)
- Property access via `.get()` and `.set()`
- Edge creation between vertices with kwargs
- Query result conversion to wrappers (`.get_vertex()`, `.get_edge()`, `.get_element()`)
- Edge direction helpers: `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()` with optional label filters
- Wrapper methods: `.save()`, `.modify()`, `.delete()`, `.to_dict()`, `.has_property()`, `.get_property_names()`, `.get_identity()`, `.get_type_name()`
- Lookups via `db.lookup_by_key()` and `db.lookup_by_rid()`, plus `Document.wrap()`
- Immutable vs mutable behavior (query results vs direct creation)
- Delete semantics: vertex delete cascades to edges; edge delete leaves vertices intact

## Test Cases

### Wrapper Creation

- **vertex_wrapper_creation**: Creates vertex via `db.new_vertex()`, chains `.set()`, verifies properties and isinstance Vertex
- **document_wrapper_creation**: Creates document via `db.new_document()`, chains `.set()`, verifies properties and isinstance Document
- **new_edge_pythonic_method**: Creates edge via vertex method `.new_edge(type, target, **kwargs)`, verifies Edge instance and properties

### Query Result Conversion

- **get_vertex_from_query_results**: Queries vertex, calls `.get_vertex()` for wrapper, tests `.modify()` for mutation, verifies update
- **get_edge_from_query_results**: Queries edge, calls `.get_edge()` for wrapper, verifies Edge instance and properties
- **get_element_generic_wrapper**: Tests `.get_element()` returns appropriate wrapper type (Vertex for a vertex, Document for a document)
- **document_wrap_static_method**: Uses `Document.wrap()` on a raw Java element and verifies it auto-detects Vertex vs Document

### Edges & Traversal

- **edge_direction_helpers**: Uses `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()` with label filters and validates connected endpoints via `.get_in()` / `.get_out()`

### Lookups & Introspection

- **lookup_by_key_returns_wrapper**: Uses `db.lookup_by_key()` to find a vertex by indexed key; returns a Vertex wrapper, and returns `None` for a missing key
- **wrapper_identity_methods**: Tests `.get_identity()` and `.get_type_name()` on a Vertex wrapper
- **wrapper_property_methods**: Tests `.has_property()`, `.get_property_names()`, and `.to_dict()` on a Document wrapper

### Mutation

- **wrapper_modify_method**: Uses `.modify()` to obtain a mutable copy of a query result, updates it, and verifies the change persists
- **no_bidirectional_parameter**: Confirms `new_edge()` works without a `bidirectional` parameter and that the parameter is absent from its signature

### Deletion

- **wrapper_delete_method**: Creates a node then deletes it via SQL `DELETE`, verifying it is gone
- **vertex_delete_cascade**: Deletes a vertex via `.delete()` (after `lookup_by_rid`) and verifies its edge cascade-deletes
- **edge_delete_leaves_vertices**: Deletes an edge via `.delete()` and verifies both endpoint vertices remain
- **document_delete_sql**: Deletes a document using SQL `DELETE` and verifies removal
- **delete_via_wrapper_on_fresh_lookup**: Verifies `.delete()` works on an object returned from `db.lookup_by_rid()`

## Pattern

```python
# Create and chain
vertex = db.new_vertex("Person")
vertex.set("name", "Alice").set("age", 30).save()

# Query and convert
results = db.query("sql", "SELECT FROM Person")
person = list(results)[0].get_vertex()

# Edge direction helpers
out_edges = person.get_out_edges("Knows")
targets = {e.get_in().get("name") for e in out_edges}

# Modify
mutable = person.modify()
mutable.set("age", 31).save()

# Delete (looked up by RID)
node = db.lookup_by_rid(rid)
node.delete()
```

## Key Methods

- **Creation**: `db.new_vertex(type)`, `db.new_document(type)`, `vertex.new_edge(type, target, **kwargs)`
- **Query conversion**: `.get_vertex()`, `.get_edge()`, `.get_element()`, `Document.wrap()`
- **Lookups**: `db.lookup_by_key(type, keys, values)`, `db.lookup_by_rid(rid)`
- **Property access**: `.get(key)`, `.set(key, value)`, `.has_property(key)`, `.get_property_names()`
- **Persistence**: `.save()`, `.delete()`, `.modify()`
- **Edge helpers**: `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()`, `.get_in()`, `.get_out()`
- **Introspection**: `.get_identity()`, `.get_type_name()`, `.to_dict()`
