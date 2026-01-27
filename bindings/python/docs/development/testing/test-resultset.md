# ResultSet Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_resultset.py){ .md-button }

There are 12 tests that exercise list/DataFrame conversion, chunking, counting, first/one helpers, iteration, empty handling, reusability, and metadata access.

## What the tests cover

- List conversion with `to_list(convert_types=True)` on three ordered `User` docs
- Optional Pandas conversion on three `Product` rows (skips if pandas missing)
- Chunked iteration of 250 `Item` docs into 100/100/50 batches
- `count()`, `first()`, and `one()` behaviors on simple datasets
- Iteration patterns over ten `IterTest` docs, including desc ordering for `first()`
- `__repr__` content, complex aggregation/filtering, empty handling, single-use ResultSet, and RID/vertex helpers

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

Creates 100 `Sales` rows with regions cycling North/South/East/West and decimal amounts. Aggregation query groups by region; each group count is 25. A filtered/ordered query for North returns the highest amount via `first()`.

### empty handling

Runs `SELECT FROM EmptyTest` with no rows. `to_list()` returns `[]`, `count()` returns 0, `first()` returns `None`, and `iter_chunks(size=10)` yields no chunks.

### reusability

Iterating a `ResultSet` consumes it: first iteration returns two `ReuseTest` rows; the second is empty. A fresh query yields two rows again.

### get_rid and get_vertex

For a `Person` vertex, `get_rid()` returns a string starting with `#`, and `get_vertex()` returns the underlying Java vertex with `name == 'Alice'`.

## Handy patterns from the tests

```python
# List conversion with type mapping
users = db.query("sql", "SELECT FROM User ORDER BY name").to_list(convert_types=True)

# Chunked iteration
chunks = list(db.query("sql", "SELECT FROM Item ORDER BY id").iter_chunks(size=100))

# Count without consuming to Python objects
count = db.query("sql", "SELECT FROM Counter").count()

# first() vs one()
first_row = db.query("sql", "SELECT FROM FirstTest ORDER BY value").first()
only_row = db.query("sql", "SELECT FROM OneTest WHERE value = 'unique'").one()
```

Key behaviors: ResultSet is single-use for iteration, `count()` runs server-side, `one()` validates cardinality, and empty results return `None` for `first()` and an empty list/chunks for conversions.
3. **Chunk large results** - Use `iter_chunks()` for memory efficiency
4. **Convert to DataFrame** - For data analysis
5. **Check for empty** - Use `first()` to check if results exist

## See Also

- **[Results API](../../api/results.md)** - Full API reference
- **[Query Guide](../../guide/core/queries.md)** - Query patterns
- **[Database Tests](test-core.md)** - Database operations
- **[Example 07: StackOverflow](../../examples/07_stackoverflow_multimodel.md)** - Complex queries
