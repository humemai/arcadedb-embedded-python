# Bulk Insert Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_bulk_insert.py)

Tests for `Database.insert_many`, `AsyncExecutor.create_record` and `append_samples`,
`db.graph_batch`, and vector columns through `to_columns()`/`to_dataframe()`.

## Recommended Bulk Paths Land Every Row

`TestRecommendedBulkPathsLandEveryRow` runs a bulk load through each recommended path
and counts what was stored against what was submitted.

These tests exist because `ArcadeData/arcadedb#7615` went unnoticed: the async
executor's SQL command path discarded records above parallel level 1 before 26.10.1
(fixed in #7625), and no test
compared submitted rows with stored rows at a size where the loss shows. The sizes below
come from the original report.

### test_insert_many_lands_every_document

Inserts 9,742 `BulkDoc` rows with `insert_many(..., commit_every=1_000)`. Asserts the
returned write count is 9,742, that `SELECT count(*)` agrees, and that `min(id)`,
`max(id)`, and `sum(id)` match the submitted ids, so the stored rows are the submitted
rows and not merely the right number of rows.

### test_insert_many_parallel_lands_every_document

Inserts the same 9,742 rows with `insert_many(..., parallel=True)`, which routes through
the executor's `createRecord` rather than through `command`. That path is measured
unaffected by #7615, and this test is what keeps it so. Asserts the returned count and
the stored count are both 9,742.

### test_graph_batch_lands_every_vertex_and_edge

Parametrized over `parallel_flush` `False` and `True`. Creates 20,000 `BulkV` vertices
and 40,000 `BulkE` edges through `db.graph_batch(...)`, asserting one RID per submitted
vertex and then the two stored counts after `wait_completion()`. The parallel level
is set to 4 first, the level at which the SQL command path lost records on 26.9.1 and
earlier. The test counts what was stored and does not observe how many workers the
flush used.

## Test Cases

`TestInsertMany` covers smaller `insert_many` loads and edge cases.

### test_basic_roundtrip

Inserts 500 rows with `commit_every=100`. Asserts the call returns 500 and that 500
are stored, then reads back the row with `k = 7`: `name`, `price`, `active`, and
`tags` match what was submitted. The `meta` map is not read back.

### test_null_values

Two rows carrying `None` values: the call returns 2 and 2 are stored. The null
values are not read back.

### test_empty

An empty row list returns 0.

### test_parallel

2,000 rows with `parallel=True`: the call returns 2,000 and 2,000 are stored.

### test_non_json_fallback

Three rows carrying a `datetime` value, which `json.dumps` rejects, so they take the
per-row path instead of the JSON fast path. The call returns 3 and 3 are stored; the
`datetime` values are not read back.

### test_inside_open_transaction

`insert_many(..., commit_every=0)` between `begin()` and `commit()`: 2 rows are
stored.

## Parallel Mode Reports Failed Records

`TestInsertManyParallelReportsFailures`: a record the parallel writers fail to store
must fail the call. The maintainers' advice for an async bulk load
(`ArcadeData/arcadedb#8478`) is an error callback "so a failed record can't pass
silently"; the parallel mode submitted every record without one and returned the row
count it was given, so a rejected record was dropped while `insert_many` reported
success (the duplicate-key test fails on 26.9.1 and earlier).

### test_duplicate_key_raises_instead_of_dropping

A 4-bucket type with a UNIQUE index on `id`, and 1,000 rows carrying every key twice.
Asserts `insert_many(..., parallel=True)` raises `ArcadeDBError` whose message contains
"failed" (it reports how many records failed and the first failure), and that no more
than the 500 distinct keys were stored.

### test_clean_load_still_returns_the_count

The same schema with 1,000 distinct keys: the call returns 1,000 and 1,000 are stored.

## Other Cases

### test_create_and_wait

`TestAsyncCreateRecord`: 100 documents through `async_executor().create_record(...)`;
after `wait_completion()`, 100 are stored.

### test_callback

One document through `create_record(doc, callback=...)`: 1 is stored and the
callback runs once.

### test_float_array_column_to_columns

`TestVectorColumns`: 50 rows with a three-float `ARRAY_OF_FLOATS` column. `to_columns()`
returns that column as a `(50, 3)` numpy array, and `arr[10][1] == float32(10.5)`.

### test_numpy_columns

`TestAppendSamplesNumpy`: 10,000 samples from numpy columns through `append_samples`
into a 2-shard `TIMESERIES` type; 10,000 are stored.

### test_primitive_batch_matches_object_path

primitive=True must store exactly what the Object[] path stores.

### test_repeated_tag_values_are_stored_distinctly

Memoised string conversion must not conflate or alias tag values.

### test_primitive_batch_accepts_plain_sequences

Lists, not just ndarrays: the batch path types each column itself.

### test_vector_column_to_dataframe

`TestVectorColumnsDataFrame`, skipped without pandas: 10 rows with a two-float vector
column; `to_dataframe()` returns 10 rows and row 3's vector has 2 elements.

## Inside A Caller's Transaction

`TestInsertManyInsideACallersTransaction`: `insert_many` inside an open transaction
belongs to that transaction, so `commit_every` is ignored and the caller's commit or
rollback decides the whole batch. On 26.9.1 and earlier the Java fast path committed
and reopened the caller's transaction every `commit_every` rows.

### test_rollback_after_insert_many_leaves_nothing

25 rows with `commit_every=10` inside `transaction()`, then an exception: asserts
nothing was stored.

### test_commit_after_insert_many_keeps_every_row

The same load committed: asserts the call returns 25 and 25 are stored.

## Running

```bash
uv run pytest bindings/python/tests/test_bulk_insert.py -v
```
