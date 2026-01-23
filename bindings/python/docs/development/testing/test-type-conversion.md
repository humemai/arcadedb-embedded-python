# Type Conversion Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_type_conversion.py){ .md-button }

These notes mirror the Python tests in [test_type_conversion.py]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_type_conversion.py). There are 10 tests covering Python ↔ Java type conversion: primitives (int, float, str, bool, None), datetime types, Decimal, collections (list, set, dict), binary, and round-trip verification. See [test_type_conversion.py]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_type_conversion.py) for all test implementations.

## Key Types

- Primitives: `int` ↔ Integer/Long, `float` ↔ Double, `str` ↔ String, `bool` ↔ Boolean, `None` ↔ null
- Date/Time: `datetime`, `date`, `time`
- Numeric: `Decimal` for precision
- Collections: `list`, `set`, `dict`
- Binary: `bytes`

**Pattern:**
```python
vertex = db.new_vertex("Test")

# Store primitives
vertex.set("int_val", 42)
vertex.set("float_val", 3.14)
vertex.set("str_val", "hello")
vertex.set("bool_val", True)
vertex.set("none_val", None)
vertex.save()

# Retrieve and verify types
result = db.query("sql", "SELECT FROM Test").first()
assert result.get("int_val") == 42
assert result.get("float_val") == 3.14
assert result.get("str_val") == "hello"
assert result.get("bool_val") is True
assert result.get("none_val") is None
```

---

### test_datetime_conversion
Tests datetime type conversion.

**What it tests:**
- datetime → LocalDateTime
- date → LocalDate
- time → LocalTime
- Timezone handling

**Pattern:**
```python
from datetime import datetime, date, time

vertex = db.new_vertex("Event")

# Store date/time
vertex.set("timestamp", datetime(2024, 1, 15, 14, 30, 0))
vertex.set("event_date", date(2024, 1, 15))
vertex.set("start_time", time(14, 30, 0))
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Event").first()
assert result.get("timestamp") == datetime(2024, 1, 15, 14, 30, 0)
assert result.get("event_date") == date(2024, 1, 15)
assert result.get("start_time") == time(14, 30, 0)
```

---

### test_decimal_conversion
Tests high-precision decimal conversion.

**What it tests:**
- Decimal → BigDecimal
- Precision preservation
- Financial calculations

**Pattern:**
```python
from decimal import Decimal

vertex = db.new_vertex("Product")

# Store decimal (for money)
vertex.set("price", Decimal("19.99"))
vertex.set("tax", Decimal("1.60"))
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Product").first()
price = result.get("price")
tax = result.get("tax")

assert isinstance(price, Decimal)
assert price == Decimal("19.99")
assert tax == Decimal("1.60")
```

---

### test_list_conversion
Tests list type conversion.

**What it tests:**
- list → ArrayList
- Order preservation
- Nested lists
- Mixed types in lists

**Pattern:**
```python
vertex = db.new_vertex("User")

# Store lists
vertex.set("tags", ["python", "java", "database"])
vertex.set("scores", [95, 87, 92])
vertex.set("nested", [[1, 2], [3, 4]])
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM User").first()
assert result.get("tags") == ["python", "java", "database"]
assert result.get("scores") == [95, 87, 92]
assert result.get("nested") == [[1, 2], [3, 4]]
```

---

### test_set_conversion
Tests set type conversion.

**What it tests:**
- set → HashSet
- Uniqueness preserved
- Order not guaranteed

**Pattern:**
```python
vertex = db.new_vertex("User")

# Store set
vertex.set("roles", {"admin", "user", "moderator"})
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM User").first()
roles = result.get("roles")

assert isinstance(roles, set)
assert len(roles) == 3
assert "admin" in roles
```

---

### test_dict_conversion
Tests dictionary type conversion.

**What it tests:**
- dict → HashMap
- Nested dictionaries
- Key/value preservation
- Complex structures

**Pattern:**
```python
vertex = db.new_vertex("User")

# Store dict
vertex.set("profile", {
    "firstName": "Alice",
    "lastName": "Smith",
    "age": 30,
    "address": {
        "city": "New York",
        "zip": "10001"
    }
})
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM User").first()
profile = result.get("profile")

assert profile["firstName"] == "Alice"
assert profile["address"]["city"] == "New York"
```

---

### test_binary_conversion
Tests binary data conversion.

**What it tests:**
- bytes → byte[]
- Binary data preservation
- Large binary data

**Pattern:**
```python
vertex = db.new_vertex("File")

# Store binary
binary_data = b"Hello World \x00\x01\x02"
vertex.set("data", binary_data)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM File").first()
retrieved = result.get("data")

assert isinstance(retrieved, bytes)
assert retrieved == binary_data
```

---

### test_none_null_conversion
Tests None/null handling.

**What it tests:**
- None → null
- null → None
- Optional properties
- Distinguishing None from missing

**Pattern:**
```python
vertex = db.new_vertex("User")

# Store None
vertex.set("middle_name", None)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM User").first()
assert result.get("middle_name") is None
```

---

### test_large_integer_conversion
Tests large integer handling.

**What it tests:**
- Small int → Integer
- Large int → Long
- Int range handling

**Pattern:**
```python
vertex = db.new_vertex("Test")

# Small integer
vertex.set("small", 42)

# Large integer (> 2^31)
vertex.set("large", 2 ** 40)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Test").first()
assert result.get("small") == 42
assert result.get("large") == 2 ** 40
```

---

### test_round_trip_conversion
Tests full round-trip preservation.

**What it tests:**
- Python → Java → Python
- All types preserved
- No data loss
- Value equality

**Pattern:**
```python
from datetime import datetime
from decimal import Decimal

# Original data
original = {
    "int": 42,
    "float": 3.14,
    "str": "hello",
    "bool": True,
    "datetime": datetime.now(),
    "decimal": Decimal("19.99"),
    "list": [1, 2, 3],
    "dict": {"key": "value"},
    "none": None
}

# Store
vertex = db.new_vertex("Test")
for key, value in original.items():
    vertex.set(key, value)
vertex.save()

# Retrieve
result = db.query("sql", "SELECT FROM Test").first()

# Verify all values match
for key, original_value in original.items():
    retrieved_value = result.get(key)
    assert retrieved_value == original_value, f"{key}: {retrieved_value} != {original_value}"
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
