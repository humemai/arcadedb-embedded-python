# ResultSet Tests

The `test_resultset.py` file contains **12 tests** covering query result handling, iteration patterns, and data conversion.

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/python-embedded/bindings/python/tests/test_resultset.py){ .md-button }

## Overview

ResultSet tests cover:

- ✅ **List Conversion** - Converting results to list
- ✅ **DataFrame Conversion** - Pandas DataFrame integration
- ✅ **Chunked Iteration** - Processing results in batches
- ✅ **Count/First/One** - Common result patterns
- ✅ **Iteration Patterns** - for loops, comprehensions, generators
- ✅ **Empty Handling** - Zero-result queries
- ✅ **Reusability** - Multiple iterations
- ✅ **RID and Vertex Access** - Record metadata

## Test Coverage

### test_resultset_to_list
Tests converting ResultSet to Python list.

**What it tests:**
- Creating query results
- Converting to list with `list(results)`
- List contains all results
- Results are iterable

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User")

# Convert to list
users = list(results)

assert len(users) == 100
for user in users:
    print(user.get_property("name"))
```

---

### test_resultset_to_dataframe
Tests Pandas DataFrame conversion.

**What it tests:**
- Converting results to DataFrame
- Column names match properties
- Data types preserved
- DataFrame operations work

**Pattern:**
```python
import pandas as pd

results = db.query("sql", "SELECT FROM User")

# Convert to DataFrame
df = results.to_dataframe()

assert len(df) == 100
assert "name" in df.columns
assert "age" in df.columns

# Use DataFrame operations
print(df.describe())
print(df['age'].mean())
```

---

### test_resultset_iter_chunks
Tests chunked iteration for large results.

**What it tests:**
- Iterating in chunks of N records
- Memory-efficient processing
- All records processed
- Useful for large datasets

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User")

# Process in chunks of 10
for chunk in results.iter_chunks(chunk_size=10):
    assert len(chunk) <= 10
    # Process chunk
    process_batch(chunk)
```

---

### test_resultset_count
Tests counting results.

**What it tests:**
- `len(list(results))` for count
- Count without full iteration
- Works with empty results

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User WHERE age > 18")

count = len(list(results))
assert count == 75
```

---

### test_resultset_first
Tests getting first result.

**What it tests:**
- `results.first()` returns first record
- Returns None if empty
- Doesn't iterate all results

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User ORDER BY age DESC")

# Get first (oldest) user
oldest = results.first()
assert oldest is not None
assert oldest.get_property("age") == 65

# Empty result
empty = db.query("sql", "SELECT FROM User WHERE age > 200")
assert empty.first() is None
```

---

### test_resultset_one
Tests getting single expected result.

**What it tests:**
- `results.one()` returns single record
- Raises error if multiple results
- Raises error if empty
- Useful for unique queries

**Pattern:**
```python
# Should return exactly one
results = db.query("sql", "SELECT FROM User WHERE username = 'alice'")
user = results.one()
assert user.get_property("username") == "alice"

# Multiple results - raises error
results = db.query("sql", "SELECT FROM User")
try:
    user = results.one()  # Error: multiple results
except ValueError as e:
    print(f"Expected error: {e}")

# Empty results - raises error
results = db.query("sql", "SELECT FROM User WHERE username = 'nobody'")
try:
    user = results.one()  # Error: no results
except ValueError as e:
    print(f"Expected error: {e}")
```

---

### test_resultset_iteration_patterns
Tests various iteration patterns.

**What it tests:**
- for loop iteration
- List comprehension
- Generator expressions
- `next()` and manual iteration

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User")

# For loop
for user in results:
    print(user.get_property("name"))

# List comprehension
names = [u.get_property("name") for u in results]

# Generator expression
ages = (u.get_property("age") for u in results)

# Manual iteration
results = db.query("sql", "SELECT FROM User")
user1 = next(results)
user2 = next(results)
```

---

### test_result_representation
Tests result object representation.

**What it tests:**
- `str(result)` returns readable string
- `repr(result)` for debugging
- Property access methods

**Pattern:**
```python
result = db.query("sql", "SELECT FROM User").first()

# String representation
print(str(result))  # Shows properties

# Repr for debugging
print(repr(result))  # Shows type and RID
```

---

### test_resultset_with_complex_queries
Tests results from complex queries.

**What it tests:**
- Aggregation queries
- JOIN queries
- Graph traversal results
- Computed properties

**Pattern:**
```python
# Aggregation
results = db.query("sql", "SELECT COUNT(*) as count, AVG(age) as avg_age FROM User")
stats = results.first()
count = stats.get_property("count")
avg_age = stats.get_property("avg_age")

# Graph traversal
results = db.query("sql", "SELECT expand(out('Follows')) FROM User WHERE username = 'alice'")
friends = list(results)

# Computed properties
results = db.query("sql", "SELECT name, age, age * 2 as double_age FROM User")
for result in results:
    print(result.get_property("double_age"))
```

---

### test_resultset_empty_handling
Tests handling empty query results.

**What it tests:**
- Empty ResultSet is falsy
- Iteration over empty results
- `first()` returns None
- List conversion returns empty list

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User WHERE age > 200")

# Empty check
if not results:
    print("No results")

# Iteration (no iterations)
for result in results:
    print("Never executed")

# First
assert results.first() is None

# List
assert list(results) == []
```

---

### test_resultset_reusability
Tests reusing ResultSet.

**What it tests:**
- ResultSet can be iterated multiple times
- Each iteration starts fresh
- Results cached or re-queried

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User")

# First iteration
count1 = len(list(results))

# Second iteration
count2 = len(list(results))

assert count1 == count2
```

---

### test_result_get_rid_and_vertex
Tests accessing record metadata.

**What it tests:**
- Getting RID with `get_rid()`
- Getting vertex/document with `to_vertex()`
- Accessing underlying Java object

**Pattern:**
```python
results = db.query("sql", "SELECT FROM User")
result = results.first()

# Get RID
rid = result.get_rid()
assert rid.startswith("#")

# Get as vertex
vertex = result.to_vertex()
assert vertex is not None

# Modify and save
vertex.set("modified", True)
vertex.save()
```

## Test Patterns

### Basic Iteration
```python
results = db.query("sql", "SELECT FROM User")

for result in results:
    name = result.get_property("name")
    age = result.get_property("age")
    print(f"{name}: {age}")
```

### List Conversion
```python
results = db.query("sql", "SELECT FROM User")
users = list(results)

print(f"Found {len(users)} users")
```

### DataFrame Conversion
```python
results = db.query("sql", "SELECT FROM User")
df = results.to_dataframe()

print(df.head())
print(df['age'].mean())
```

### First/One Patterns
```python
# Get first
user = db.query("sql", "SELECT FROM User ORDER BY age DESC").first()

# Get one (expect exactly one)
user = db.query("sql", "SELECT FROM User WHERE username = 'alice'").one()
```

### Chunked Processing
```python
results = db.query("sql", "SELECT FROM LargeTable")

for chunk in results.iter_chunks(chunk_size=1000):
    process_batch(chunk)
```

## Common Assertions

```python
# Result count
assert len(list(results)) == expected_count

# Has results
assert results.first() is not None

# Empty results
assert results.first() is None

# Property exists
result = results.first()
assert result.get_property("name") is not None

# Property value
assert result.get_property("age") == 30
```

## Key Takeaways

1. **Use first() for single** - More efficient than list()[0]
2. **Use one() for unique** - Validates exactly one result
3. **Chunk large results** - Use `iter_chunks()` for memory efficiency
4. **Convert to DataFrame** - For data analysis
5. **Check for empty** - Use `first()` to check if results exist

## See Also

- **[Results API](../../api/results.md)** - Full API reference
- **[Query Guide](../../guide/core/queries.md)** - Query patterns
- **[Database Tests](test-core.md)** - Database operations
- **[Example 07: StackOverflow](../../examples/07_stackoverflow_multimodel.md)** - Complex queries
