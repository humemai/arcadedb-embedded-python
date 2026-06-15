# Hash Index Schema Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_hash_index_schema.py){ .md-button }

These tests cover HASH index creation and discovery through the Python schema API, plus indexed `IN` parameter expansion.

## Covered Behavior

### 1) create, discover, and query

`test_hash_index_schema_create_discover_and_query` creates a HASH index through `schema.create_index(...)`, then verifies it is discoverable through `schema.get_indexes()`, `schema.exists_index(...)`, and `schema.get_index_by_name(...)`, and confirms equality queries still return the expected record.

### 2) get-or-create and force drop

`test_hash_index_schema_get_or_create_and_force_drop` verifies idempotent HASH index creation through `get_or_create_index(...)` (two calls return the same index name) and cleanup through `drop_index(..., force=True)`.

### 3) indexed IN parameter with a named list

`test_indexed_in_named_list_parameter_returns_rows` creates an `LSM_TREE` index and confirms that a Python list bound to a named parameter (`WHERE code IN :codes`) expands correctly and returns the matching rows.

## Runtime Guard

If the current packaged runtime does not support `IndexType.HASH`, these tests skip instead of failing spuriously.
