# Graph API Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_graph_api.py){ .md-button }

There are 18 tests covering Pythonic wrappers (Document, Vertex, Edge classes) and their methods.

## Overview

Tests validate:

- Vertex/Document/Edge wrapper creation via `db.new_vertex()`, `db.new_document()`, `db.new_edge()`
- Fluent interface (chaining `.set()` calls)
- Property access via `.get()` and `.set()`
- Edge creation between vertices with kwargs
- Query result conversion to wrappers (`.get_vertex()`, `.get_edge()`, `.get_element()`)
- Wrapper methods: `.save()`, `.modify()`, `.delete()`, `.out()`, `.in()`, `.both()`, `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()`, `.traversal()`, `.to_dict()`
- Immutable vs mutable behavior (query results vs direct creation)

## Test Cases

### Wrapper Creation

- **vertex_wrapper_creation**: Creates vertex via `db.new_vertex()`, chains `.set()`, verifies properties and isinstance Vertex
- **document_wrapper_creation**: Creates document via `db.new_document()`, chains `.set()`, verifies properties and isinstance Document
- **new_edge_pythonic_method**: Creates edge via vertex method `.new_edge(type, target, **kwargs)`, verifies Edge instance and properties

### Query Result Conversion

- **get_vertex_from_query_results**: Queries vertex, calls `.get_vertex()` for wrapper, tests `.modify()` for mutation, verifies update
- **get_edge_from_query_results**: Queries edge, calls `.get_edge()` for wrapper, verifies Edge instance and properties
- **get_element_generic_wrapper**: Tests `.get_element()` returns appropriate wrapper type (Vertex, Document, or Edge)

### Vertex Methods & Traversal

- **vertex_methods**: Tests `.get_rid()`, `.get_type_name()`, `.delete()`, `.to_dict()` on Vertex wrapper
- **edge_methods**: Tests `.get_from()`, `.get_to()`, `.get_type()` on Edge wrapper
- **graph_traversal_out**: Uses `.out(edge_type)` to traverse outgoing edges; verifies connected vertices
- **graph_traversal_in**: Uses `.in(edge_type)` to traverse incoming edges
- **graph_traversal_both**: Uses `.both()` to traverse both directions
- **graph_traversal_chain**: Chains traversal methods (`.out().in().both()`) and counts results
- **edge_direction_helpers**: Uses `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()` with label filters and validates connected endpoints

### Advanced Features

- **graph_traversal_with_filter**: Chains `.out().filter(...)` with predicates; validates result filtering
- **complex_graph_operations**: Multi-step graph construction (create vertices, link with edges, traverse, update, delete); validates all steps
- **document_vs_vertex_wrappers**: Tests both Document and Vertex types in same DB; verifies wrapper distinction
- **edge_create_update_delete**: Creates, updates properties, deletes edges; verifies state changes

## Pattern

```python
# Create and chain
vertex = db.new_vertex("Person")
vertex.set("name", "Alice").set("age", 30).save()

# Query and convert
results = db.query("sql", "SELECT FROM Person")
person = list(results)[0].get_vertex()

# Traverse
friends = person.out("Knows")  # Returns iterator or list of connected vertices

# Modify
mutable = person.modify()
mutable.set("age", 31).save()

# Delete
person.delete()
```

## Key Methods

- **Creation**: `db.new_vertex(type)`, `db.new_document(type)`, `db.new_edge(type, target, **kwargs)`
- **Query conversion**: `.get_vertex()`, `.get_edge()`, `.get_element()`
- **Property access**: `.get(key)`, `.set(key, value)`
- **Persistence**: `.save()`, `.delete()`, `.modify()`
- **Traversal**: `.out(edge_type)`, `.in(edge_type)`, `.both()`, `.get_out_edges()`, `.get_in_edges()`, `.get_both_edges()`, `.traversal()`
- **Introspection**: `.get_rid()`, `.get_type_name()`, `.to_dict()`
