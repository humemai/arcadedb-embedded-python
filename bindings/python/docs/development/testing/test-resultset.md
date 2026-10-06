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

### A small result costs one bridge call (`TestSmallResultsCostOneBridgeCall`)

A JPype call costs 3 to 4 microseconds, a fifth of a one-row read. `RowAccess.nextRows` and `RowBatcher.nextJsonBatch` return fewer rows than asked for only when the result set is drained, and close it themselves, so `to_list()` and `to_json_list()` make exactly one bridge call for a result that fits one batch, and no separate `close()` call.

- **`to_list()` makes one call for a short result**, including an empty one: a counting stand-in for the bridge class sees one `nextRows`, and the set is closed and exhausted
- **`to_json_list()` makes one call** for a short result
- **a full batch still ends on the next call**: exactly 512 rows (the `to_list()` batch) take two calls and return every row
- **a drained set reads as empty and is not an error**: `to_list()`, iteration, `first()`, and `iter_json_batches()` on a drained set return nothing, and `close()` stays idempotent
- **the bridge releases the engine cursor**: 60,000 documents walked in `@rid` pages of 5,000 with `to_list()` and `to_json_list()`, nobody calling `close()`, finish (a LIMIT that stops a parallel scan early parks its producers until the result set is closed, ArcadeData/arcadedb#8594)

### Results and records after their database is closed (`test_results_after_close.py`)

A result, a result set, or a record keeps the `Database` it came from alive and raises `ArcadeDBError` ("Database is closed") once that database is closed (humemai/arcadedb-embedded-python#117). Before, a record row read `{}`, a record property read `None`, and a plain scan raised a raw `TransactionException`.

- **reads through a closed database raise**: after `db.close()`, `to_list()` and iteration of two open result sets, and `get`, `to_dict`, `to_json`, `get_vertex`, `get_element`, `get_property_names`, `has_property`, and `get_out_edges` on a row and a vertex taken earlier, each raise.
- **a projection result set is refused, a projection or command row is not**: an unread `SELECT name ...` result set raises after `close()`, because its rows may still be read lazily; a `Result` taken from it (or from a command) before the close holds its own values and still reads (example 16 reads an `IMPORT DATABASE` result after closing its database).
- **a set read to its end stays empty**: after `to_list()` and `close()`, `to_list()` returns `[]`.
- **a result keeps its dropped database open**: a function that opens a database, queries it, and returns the rows and a vertex without closing anything returns real data after `gc.collect()`, where it returned `[{}, {}, {}]` and `{}`.
- **the kept database is open for the engine**: while those results live a second `open_database()` of the path raises "already in use"; once they are deleted it opens.
- **the reference does not leak the database**: with every result and record deleted the wrapper's `__del__` closes the database and the path opens again.

### Errors raised while rows are read (`test_resultset_read_errors.py`)

The engine computes rows lazily, so `query()` returns and a statement's error surfaces on the first or a later row (humemai/arcadedb-embedded-python#173). Before, it reached Python as the raw Java exception. Type `E` has one bucket, so rows come in insertion order.

- **the engine raises these errors while rows are read**: `SELECT 1 / (i - 1)` returns its first row, then raises on the second; checks the premise that the errors come from reading, not from `query()`.
- **every reader raises ArcadeDBError**: a division by zero (an ArcadeDB `ArithmeticErrorException`) and a `format()` that cannot apply `%d` (a JDK `IllegalArgumentException`), each on the first row and on the second, through iteration, `next()`, `to_list()` with and without type conversion, `iter_dicts()`, `iter_chunks()`, `count()`, `to_json_list()`, `iter_json_batches()`, `to_columns()` (also one row per batch), `to_arrow()`, and `to_dataframe()`. Each raises `ArcadeDBError` whose text holds the Java message and whose `__cause__` is the Java `RuntimeException`.
- **first() and one()**: `first()` on the first-row errors, and `one()` on all four, where the second-row error, not "multiple results", is what it raises.
- **a command result**: the same through `command()`.

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
