# Hash Index Schema Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_hash_index_schema.py){ .md-button }

These tests cover HASH index creation and discovery through the Python schema API, a `UNIQUE_HASH` id path end to end, plus indexed `IN` parameter expansion.

## Covered Behavior

### 1) create, discover, and query

`test_hash_index_schema_create_discover_and_query` creates a HASH index through `schema.create_index(...)`, then verifies it is discoverable through `schema.get_indexes()`, `schema.exists_index(...)`, and `schema.get_index_by_name(...)`, and confirms equality queries still return the expected record.

### 2) get-or-create and force drop

`test_hash_index_schema_get_or_create_and_force_drop` verifies idempotent HASH index creation through `get_or_create_index(...)` (two calls return the same index name) and cleanup through `drop_index(..., force=True)`.

### 3) indexed IN parameter with a named list

`test_indexed_in_named_list_parameter_returns_rows` creates an `LSM_TREE` index and confirms that a Python list bound to a named parameter (`WHERE code IN :codes`) expands correctly and returns the matching rows.

### 4) the recommended id path: `UNIQUE_HASH`

`test_unique_hash_index_serves_id_lookup_update_and_delete` creates a `UNIQUE_HASH` index on an id with SQL (`CREATE INDEX ON Item (id) UNIQUE_HASH`), checks it is a unique `HASH` index, inserts 200 vertices, and confirms that `EXPLAIN` shows `FETCH FROM INDEX`, that a point lookup by SQL and by openCypher (`MATCH (n:Item {id: $id})`) returns the record, that an `UPDATE` and a `DELETE` by id change exactly that record, and that a duplicate key is rejected. It follows the ArcadeDB maintainers' advice for an id that is only read, updated and deleted by equality ([#9169](https://github.com/ArcadeData/arcadedb/issues/9169)). The same test passes on 26.9.1 and on 26.10.1; only the insert speed of a hash index differs between them (see the [queries guide](../../guide/core/queries.md#choosing-index-types-in-sql-dsl)).

## Runtime Guard

If the current packaged runtime does not support `IndexType.HASH`, the two schema-API HASH tests skip instead of failing spuriously. `test_indexed_in_named_list_parameter_returns_rows` uses `LSM_TREE` and the `UNIQUE_HASH` test uses SQL, so neither has such a guard.
