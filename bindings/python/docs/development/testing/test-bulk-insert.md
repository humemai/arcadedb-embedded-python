# Bulk Insert Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_bulk_insert.py)

Tests for Database.insert_many and AsyncExecutor.create_record.

There are 21 test functions, which collect as 22 test cases because one is
parametrized.

## Recommended Bulk Paths Land Every Row

`TestRecommendedBulkPathsLandEveryRow` runs a bulk load through each recommended path
and counts what was stored against what was submitted.

These tests exist because `ArcadeData/arcadedb#7615` went unnoticed: the async
executor's SQL command path discarded records above parallel level 1 before 26.10.1
(fixed in #7625), and no test
compared submitted rows with stored rows at a size where the loss shows. The sizes below
come from the original report.

### 1) insert many lands every document

Inserts 9,742 `BulkDoc` rows with `insert_many(..., commit_every=1_000)`. Asserts the
returned write count is 9,742, that `SELECT count(*)` agrees, and that `min(id)`,
`max(id)`, and `sum(id)` match the submitted ids, so the stored rows are the submitted
rows and not merely the right number of rows.

### 2) insert many parallel lands every document

Inserts the same 9,742 rows with `insert_many(..., parallel=True)`, which routes through
the executor's `createRecord` rather than through `command`. That path is measured
unaffected by #7615, and this test is what keeps it so. Asserts the returned count and
the stored count are both 9,742.

### 3) graph batch lands every vertex and edge

Parametrized over `parallel_flush` `False` and `True`. Creates 20,000 `BulkV` vertices
and 40,000 `BulkE` edges through `db.graph_batch(...)`, asserting one RID per submitted
vertex and then the two stored counts after `wait_completion()`. The async executor's
parallel level is set to 4 first, so the edge flush really does run on more than one
worker: that is the level at which the SQL command path loses records, and GraphBatch
does not.

## Test Cases

### 4) basic roundtrip

See the source for the exact assertions.

### 5) null values

See the source for the exact assertions.

### 6) empty

See the source for the exact assertions.

### 7) parallel

See the source for the exact assertions.

### 8) non json fallback

See the source for the exact assertions.

### 9) inside open transaction

See the source for the exact assertions.

## Parallel Mode Reports Failed Records

`TestInsertManyParallelReportsFailures`: a record the parallel writers fail to store
must fail the call. The maintainers' advice for an async bulk load
(`ArcadeData/arcadedb#8478`) is an error callback "so a failed record can't pass
silently"; the parallel mode submitted every record without one and returned the row
count it was given, so a rejected record was dropped while `insert_many` reported
success (the duplicate-key test fails on wheels before 2026-09-28).

### 10) duplicate key raises instead of dropping

A 4-bucket type with a UNIQUE index on `id`, and 1,000 rows carrying every key twice.
Asserts `insert_many(..., parallel=True)` raises `ArcadeDBError` naming the failed
records, and that no more than the 500 distinct keys were stored.

### 11) clean load still returns the count

The same schema with 1,000 distinct keys: the call returns 1,000 and 1,000 are stored.

## Other Cases

### 12) create and wait

See the source for the exact assertions.

### 13) callback

See the source for the exact assertions.

### 14) float array column to columns

See the source for the exact assertions.

### 15) numpy columns

See the source for the exact assertions.

### 16) primitive batch matches object path

primitive=True must store exactly what the Object[] path stores.

### 17) repeated tag values are stored distinctly

Memoised string conversion must not conflate or alias tag values.

### 18) primitive batch accepts plain sequences

Lists, not just ndarrays: the batch path types each column itself.

### 19) vector column to dataframe

See the source for the exact assertions.

## Inside A Caller's Transaction

`TestInsertManyInsideACallersTransaction`: `insert_many` inside an open transaction
belongs to that transaction, so `commit_every` is ignored and the caller's commit or
rollback decides the whole batch. The Java fast path committed and reopened the
caller's transaction every `commit_every` rows until 2026-09-26.

### 20) rollback after insert many leaves nothing

25 rows with `commit_every=10` inside `transaction()`, then an exception: asserts
nothing was stored.

### 21) commit after insert many keeps every row

The same load committed: asserts the call returns 25 and 25 are stored.

## Running

```bash
uv run pytest bindings/python/tests/test_bulk_insert.py -v
```
