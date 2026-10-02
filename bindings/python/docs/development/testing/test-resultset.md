# ResultSet Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_resultset.py){ .md-button }

These tests exercise list/DataFrame conversion, chunking, counting, first/one helpers, iteration, repr, complex queries, empty handling, reusability, RID/vertex helpers, JSON array serialization, the one-crossing `to_dict`, and the release of the engine-side cursor.

## What the tests cover

- List conversion with `to_list(convert_types=True)` on three ordered `User` docs
- Optional Pandas conversion on three `Product` rows (skips if pandas missing)
- Chunked iteration of 250 `Item` docs into 100/100/50 batches
- `count()`, `first()`, and `one()` behaviors on simple datasets
- Iteration patterns over ten `IterTest` docs, including desc ordering for `first()`
- `__repr__` content, complex aggregation/filtering, empty handling, single-use ResultSet, and RID/vertex helpers
- JSON array serialization in `to_json()`, the one-crossing `to_dict()`, and closing the engine-side cursor when a result set is exhausted or read with `first()`, `one()`, or `to_list()`

## Test-by-test

### to_list

Inserts Alice/Bob/Charlie, queries ordered by name, and calls `to_list(convert_types=True)` to get three dicts. Validates ordering and types.

### to_dataframe

Skips if pandas is absent. Inserts three `Product` rows, converts with `to_dataframe(convert_types=True)`, checks columns, length 3, and that the stock sum is 225.

### iter_chunks

Creates 250 `Item` docs, iterates with `iter_chunks(size=100)`, and asserts chunk sizes 100/100/50 plus boundary values (ids 0, 99, 200, 249).

### count

Inserts 50 `Counter` docs and calls `count()` (no list conversion). Expects 50.

### first

Inserts three `FirstTest` values, orders ascending, and expects `first()` to return the row with `value == "first"`. Empty query returns `None`.

### one

Inserts unique and duplicate `OneTest` rows. `one()` returns the unique row, raises `ValueError` on empty or multiple results (asserts message contains "no results" or "multiple").

### iteration patterns

Inserts ten `IterTest` docs. Uses list comprehension over the ResultSet, confirms 0..9, converts to list again, and checks `first()` on a DESC query returns 9.

### repr

Inserts one `ReprTest` row and asserts `repr(result)` is a string containing "Result" and properties.

### complex queries

Creates 100 `Sales` rows with regions cycling North/South/East/West and decimal amounts. Aggregation query groups by region; each group count is 25. A filtered/ordered query for North returns a `North` row through `first()`; the amount is not checked.

### empty handling

Runs `SELECT FROM EmptyTest` with no rows. `to_list()` returns `[]`, `count()` returns 0, `first()` returns `None`, and `iter_chunks(size=10)` yields no chunks.

### reusability

Iterating a `ResultSet` consumes it: first iteration returns two `ReuseTest` rows; the second is empty. A fresh query yields two rows again.

### get_rid and get_vertex

For a `Person` vertex, `get_rid()` returns a string starting with `#`, and `get_vertex()` returns a non-`None` vertex with `get('name') == 'Alice'`. (It returns the Python `Vertex` wrapper, or `None` when the row is not a vertex; the test does not cover the `None` case.)

### to_json with arrays

Inserts a `JsonArrayTest` row with `tags = ['a', 'b', 'c']` and asserts `to_json()` serializes the list property as a JSON array.

### to_dict in one crossing

`Result.to_dict()` reads a row in one bridge call (`RowAccess`); the test checks it gives exactly what reading each property on its own gives, with the same key order, for every value type (DATETIME, DATE, DECIMAL, and the rest of a mixed row). It then inserts 1,200 more rows and checks that `to_list()`, which fetches rows in batches (`RowAccess.nextRows`), returns the same dicts in the same order as reading each row on its own, including after `next(iter(rs))` has already taken a row from the same result set. It also calls the bridge lookup once before the JVM starts (when run alone), which must not be cached.

### The result set releases its engine cursor (`TestResultSetReleasesTheEngineCursor`)

Since 26.10.1's parallel scan (ArcadeData/arcadedb#8524) a query whose `LIMIT` is satisfied keeps its scan's producer threads parked until its result set is closed or ten minutes pass, and a few such result sets stall the next query that needs those threads (ArcadeData/arcadedb#8594). Example 05 hung that way on its fifth RID-paged page.

- **paging by iteration does not stall**: 300,000 documents in one bucket, walked with `SELECT @rid AS rid, k FROM Paged WHERE @rid > <last> LIMIT 5000`, each page iterated to its end; the walk runs in a daemon thread and must finish within 60 s with every row and 61 pages.
- **paging by to_list does not stall**: the same walk with `to_list()`.
- **exhaustion, first and one close the Java result set**: `list(rs)`, `to_list()`, `first()`, and `one()` each leave the result set closed.
- **a set closed before its end raises when read again**: after `first()`, each of `list()`, `to_list()`, `first()`, `count()`, `iter_json_batches()`, and `to_columns()` raises `ArcadeDBError` ("closed before"), and so does `to_list()` after a `with` block that took one row; a set read to its end reads as empty through `list()`, `to_list()`, `first()`, and `iter_json_batches()`.

## Handy patterns from the tests

```python
# List conversion with type mapping
users = db.query("sql", "SELECT FROM User ORDER BY name").to_list(convert_types=True)

# Chunked iteration
chunks = list(db.query("sql", "SELECT FROM Item ORDER BY id").iter_chunks(size=100))

# Count the remaining rows (iterates in Python and consumes the ResultSet)
count = db.query("sql", "SELECT FROM Counter").count()

# first() vs one()
first_row = db.query("sql", "SELECT FROM FirstTest ORDER BY value").first()
only_row = db.query("sql", "SELECT FROM OneTest WHERE value = 'unique'").one()
```

Key behaviors: ResultSet is single-use for iteration, `count()` iterates the rows in Python and consumes them (use `SELECT count(*)` to count in the engine), `one()` validates cardinality, and empty results return `None` for `first()` and an empty list/chunks for conversions. Exhaustion, `first()`, `one()`, and `to_list()` close the result set; if you stop reading early, use `with db.query(...) as rs:` or call `rs.close()`. Reading a set closed before its end raises `ArcadeDBError`.

## See Also

- **[Results API](../../api/results.md)** - Full API reference
- **[Query Guide](../../guide/core/queries.md)** - Query patterns
- **[Database Tests](test-core.md)** - Database operations
