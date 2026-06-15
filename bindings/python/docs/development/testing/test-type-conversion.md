# Type Conversion Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_type_conversion.py){ .md-button }

There are 10 tests covering Python ↔ Java type conversion: primitives (int, float, str, bool, None), date/datetime, Decimal, collections (list, set, dict), nested structures, the `property_names` accessor, and the `Result.to_dict()` / `Result.to_json()` helpers.

## Key Types

- Primitives: `int` ↔ Integer/Long, `float` ↔ Double, `str` ↔ String, `bool` ↔ Boolean, `None` ↔ null
- Date/Time: `datetime`, `date`, `time`
- Numeric: `Decimal` for precision
- Collections: `list`, `set`, `dict`
- Binary: `bytes`

**Pattern:**
```python
# test_basic_type_conversion inserts via SQL and verifies Python types on read
with db.transaction():
    db.command(
        "sql",
        """
        INSERT INTO TypeTest SET
            string_val = 'hello', int_val = 42,
            long_val = 9223372036854775807, float_val = 3.14,
            double_val = 2.71828, bool_val = true, null_val = null
        """,
    )

record = db.query("sql", "SELECT FROM TypeTest").first()
assert record.get("string_val") == "hello"
assert record.get("int_val") == 42
assert record.get("long_val") == 9223372036854775807
assert abs(record.get("float_val") - 3.14) < 0.01
assert record.get("bool_val") is True
assert record.get("null_val") is None
```

---

### test_decimal_conversion

Tests BigDecimal → Python `Decimal` conversion.

**What it tests:**

- A `DECIMAL` property round-trips to a Python `Decimal`
- Precision preservation (`Decimal("99.95")`)

**Pattern:**
```python
db.command("sql", "CREATE PROPERTY DecimalTest.price DECIMAL")
with db.transaction():
    db.command("sql", "INSERT INTO DecimalTest SET price = 99.95")

price = db.query("sql", "SELECT FROM DecimalTest").first().get("price")
assert isinstance(price, Decimal)
assert price == Decimal("99.95")
```

---

### test_date_conversion

Tests Java `Date` / `LocalDate` → Python `date` / `datetime` conversion.

**What it tests:**

- A `DATE` property (`date('2024-01-15')`) converts to a Python `date`/`datetime`
- A `DATETIME` property (`sysdate()`) converts to a Python `datetime`

**Pattern:**
```python
db.command("sql", "CREATE PROPERTY DateTest.created_date DATE")
db.command("sql", "CREATE PROPERTY DateTest.created_datetime DATETIME")
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO DateTest SET created_date = date('2024-01-15'), created_datetime = sysdate()",
    )

record = db.query("sql", "SELECT FROM DateTest").first()
assert isinstance(record.get("created_date"), (date, datetime))
assert isinstance(record.get("created_datetime"), datetime)
```

---

### test_collection_conversion

Tests Java collections (List, Map) → Python `list` / `dict` conversion.

**What it tests:**

- An inline SQL list (`['python', 'database', 'graph']`) becomes a Python `list`
- An inline SQL map becomes a Python `dict` with correct keys/values

**Pattern:**
```python
with db.transaction():
    db.command(
        "sql",
        """
        INSERT INTO CollectionTest SET
            tags = ['python', 'database', 'graph'],
            metadata = {'version': 1, 'active': true, 'name': 'test'}
        """,
    )

record = db.query("sql", "SELECT FROM CollectionTest").first()
assert isinstance(record.get("tags"), list)
assert isinstance(record.get("metadata"), dict)
assert record.get("metadata")["version"] == 1
```

---

### test_nested_collection_conversion

Tests conversion of nested collections.

**What it tests:**

- A nested SQL structure (`users` list of dicts + `settings` dict) converts recursively
- Nested list-of-dicts and nested dicts preserve their values

**Pattern:**
```python
with db.transaction():
    db.command(
        "sql",
        """
        INSERT INTO NestedTest SET
            nested_data = {
                'users': [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}],
                'settings': {'theme': 'dark', 'notifications': true}
            }
        """,
    )

nested = db.query("sql", "SELECT FROM NestedTest").first().get("nested_data")
assert nested["users"][0]["name"] == "Alice"
assert nested["settings"]["theme"] == "dark"
```

---

### test_property_names

Tests the `Result.property_names` property.

**What it tests:**

- `record.property_names` returns a `list` of the record's property names

**Pattern:**
```python
record = db.query("sql", "SELECT FROM PropsTest").first()
prop_names = record.property_names
assert isinstance(prop_names, list)
assert "name" in prop_names
assert "score" in prop_names
```

---

### test_to_dict_conversion

Tests the `Result.to_dict()` method.

**What it tests:**

- `to_dict(convert_types=True)` returns a Python `dict` with converted values
- `to_dict(convert_types=False)` returns a `dict` (values may remain Java objects)

**Pattern:**
```python
record = db.query("sql", "SELECT FROM DictTest").first()

data = record.to_dict(convert_types=True)
assert data["name"] == "test"
assert data["count"] == 42
assert isinstance(data["tags"], list)

data_raw = record.to_dict(convert_types=False)
assert isinstance(data_raw, dict)
```

---

### test_to_json_conversion

Tests the `Result.to_json()` method.

**What it tests:**

- `to_json()` returns a JSON `str` containing the stored field values

**Pattern:**
```python
record = db.query("sql", "SELECT FROM JsonTest").first()
json_str = record.to_json()
assert isinstance(json_str, str)
assert "test" in json_str
assert "42" in json_str
```

---

### test_python_to_java_conversion

Tests converting Python types to Java when setting properties via `new_document()`.

**What it tests:**

- `doc.set(...)` for `str`, `int`, `Decimal`, and `bool`
- `convert_python_to_java()` for `list`, `dict`, and `set`
- Round-trip retrieval (price may come back as `Decimal` or `float`; a set may convert to list/collection)

**Pattern:**
```python
from arcadedb_embedded.type_conversion import convert_python_to_java

with db.transaction():
    doc = db.new_document("PyToJavaTest")
    doc.set("name", "test")
    doc.set("count", 42)
    doc.set("price", Decimal("99.95"))
    doc.set("active", True)
    doc.set("tags", convert_python_to_java(["a", "b", "c"]))
    doc.set("metadata", convert_python_to_java({"key": "value"}))
    doc.set("unique_items", convert_python_to_java({"x", "y", "z"}))
    doc.save()
```

---

### test_array_conversion

Tests Java list → Python list conversion for `LIST` properties.

**What it tests:**

- `LIST` properties populated via `convert_python_to_java()` round-trip to Python `list`
- Order and contents are preserved (`numbers`, `names`)

**Pattern:**
```python
from arcadedb_embedded.type_conversion import convert_python_to_java

db.command("sql", "CREATE PROPERTY ArrayTest.numbers LIST")
with db.transaction():
    doc = db.new_document("ArrayTest")
    doc.set("numbers", convert_python_to_java([1, 2, 3, 4, 5]))
    doc.set("names", convert_python_to_java(["Alice", "Bob", "Charlie"]))
    doc.save()

record = db.query("sql", "SELECT FROM ArrayTest").first()
assert record.get("numbers")[0] == 1
assert "Alice" in record.get("names")
```

## Test Patterns

### Store and Retrieve

```python
# Store
vertex = db.new_vertex("Type")
vertex.set("property", value)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Type").first()
retrieved = result.get("property")

assert retrieved == value
```

### Test Type

```python
# Verify type after round-trip
value = 42
vertex.set("num", value)
vertex.save()

result = db.query("sql", "SELECT FROM Type").first()
retrieved = result.get("num")

assert isinstance(retrieved, int)
assert type(retrieved) == type(value)
```

### Collections

```python
# List
vertex.set("list", [1, 2, 3])

# Set
vertex.set("set", {1, 2, 3})

# Dict
vertex.set("dict", {"key": "value"})

vertex.save()
```

## Common Assertions

```python
# Type preserved
assert isinstance(result.get("int_val"), int)
assert isinstance(result.get("str_val"), str)

# Value equality
assert result.get("value") == expected_value

# Collection contents
assert len(result.get("list")) == 3
assert "item" in result.get("set")

# None handling
assert result.get("null_val") is None
```

## Supported Type Mappings

| Python Type | Java Type | Notes |
|-------------|-----------|-------|
| `None` | `null` | Null values |
| `bool` | `Boolean` | True/False |
| `int` | `Integer` / `Long` | Size-dependent |
| `float` | `Double` | 64-bit float |
| `str` | `String` | Unicode support |
| `bytes` | `byte[]` | Binary data |
| `datetime` | `LocalDateTime` | No timezone |
| `date` | `LocalDate` | Date only |
| `time` | `LocalTime` | Time only |
| `Decimal` | `BigDecimal` | High precision |
| `list` | `ArrayList` | Ordered |
| `tuple` | `ArrayList` | Becomes list |
| `set` | `HashSet` | Unique items |
| `dict` | `HashMap` | Key-value |

## Key Takeaways

1. **Use Decimal for money** - Avoid float precision issues
2. **Lists preserve order** - Sets don't
3. **None is null** - Distinguishable from missing
4. **Nested structures work** - Recursive conversion
5. **Types preserved** - Round-trip equality

## See Also

- **[Type Conversion API](../../api/type_conversion.md)** - Full API reference
- **[Database API](../../api/database.md)** - Database operations
- **[Example 01: Document Store](../../examples/01_simple_document_store.md)** - Type usage examples
