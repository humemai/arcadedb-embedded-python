# Bulk Insert Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_bulk_insert.py)

Tests for Database.insert_many and AsyncExecutor.create_record.

There are 17 test functions, which collect as 18 test cases because one is
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

### 10) create and wait

See the source for the exact assertions.

### 11) callback

See the source for the exact assertions.

### 12) float array column to columns

See the source for the exact assertions.

### 13) numpy columns

See the source for the exact assertions.

### 14) primitive batch matches object path

primitive=True must store exactly what the Object[] path stores.

### 15) repeated tag values are stored distinctly

Memoised string conversion must not conflate or alias tag values.

### 16) primitive batch accepts plain sequences

Lists, not just ndarrays: the batch path types each column itself.

### 17) vector column to dataframe

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_bulk_insert.py -v
```
