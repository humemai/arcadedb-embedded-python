# Type Conversion API

The type_conversion module provides utilities for converting between Python and Java types when working with ArcadeDB's Java backend.

## Overview

The `type_conversion` module enables:

- **Automatic Conversion**: Seamless Python ↔ Java type conversion
- **Collection Handling**: Lists, sets, maps, and nested structures
- **Date/Time Support**: datetime, date, and time objects
- **Decimal Precision**: High-precision decimal numbers
- **Binary Data**: Bytes and byte arrays
- **Type Safety**: Validation and error handling

## Why Type Conversion?

ArcadeDB Python bindings wrap a Java database engine. When you:

- Set properties on records → Python values converted to Java
- Read properties from records → Java values converted to Python
- Pass query parameters → Python values converted to Java
- Receive query results → Java values converted to Python

The type_conversion module handles this automatically.

## Conversion Functions

### convert_python_to_java

```python
from arcadedb_embedded.type_conversion import convert_python_to_java

java_value = convert_python_to_java(python_value)
```

Convert Python value to Java object for ArcadeDB.

**Supported Conversions:**

| Python Type | Java Type |
|-------------|-----------|
| `None` | `null` |
| `bool` | `Boolean` |
| `int` | `Integer` or `Long` |
| `float` | `Double` |
| `str` | `String` |
| `bytes` | `byte[]` |
| `datetime` | `LocalDateTime` |
| `date` | `LocalDate` |
| `time` | `LocalTime` |
| `Decimal` | `BigDecimal` |
| `list` | `ArrayList` |
| `tuple` | `ArrayList` |
| `set` | `HashSet` |
| `dict` | `HashMap` |

**Example:**

```python
from arcadedb_embedded.type_conversion import convert_python_to_java
from datetime import datetime
from decimal import Decimal

# Primitive types
java_int = convert_python_to_java(42)
java_str = convert_python_to_java("hello")
java_bool = convert_python_to_java(True)

# Date/time
java_datetime = convert_python_to_java(datetime.now())

# Decimal
java_decimal = convert_python_to_java(Decimal("123.456"))

# Collections
java_list = convert_python_to_java([1, 2, 3])
java_dict = convert_python_to_java({"key": "value"})

# Nested structures
java_nested = convert_python_to_java({
    "users": [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ]
})
```

---

### convert_java_to_python

```python
from arcadedb_embedded.type_conversion import convert_java_to_python

python_value = convert_java_to_python(java_value)
```

Convert Java object to Python value.

**Supported Conversions:**

| Java Type | Python Type |
|-----------|-------------|
| `null` | `None` |
| `Boolean` | `bool` |
| `Integer`, `Long`, `Short`, `Byte` | `int` |
| `Float`, `Double` | `float` |
| `String` | `str` |
| `byte[]` | `bytes` |
| `LocalDateTime` | `datetime` |
| `LocalDate` | `date` |
| `LocalTime` | `time` |
| `BigDecimal` | `Decimal` |
| `List`, `ArrayList` | `list` |
| `Set`, `HashSet` | `set` |
| `Map`, `HashMap` | `dict` |

**Example:**

```python
from arcadedb_embedded.type_conversion import convert_java_to_python

# Read from database (automatic conversion)
result = list(db.query("sql", "SELECT FROM User WHERE username = 'alice'"))[0]

# Get Java property (automatically converted to Python)
username = result.get_property("username")  # str
age = result.get_property("age")            # int
tags = result.get_property("tags")          # list
profile = result.get_property("profile")    # dict

# Manual conversion (if needed)
java_obj = result._java_result.getElement().get()
java_property = java_obj.get("username")
python_value = convert_java_to_python(java_property)
```

## Type-Specific Conversions

### Integers

```python
from arcadedb_embedded.type_conversion import convert_python_to_java

# Small integers → Integer
java_int = convert_python_to_java(42)          # Java Integer

# Large integers → Long
java_long = convert_python_to_java(2**40)     # Java Long

# Reading integers
vertex = db.new_vertex("User")
vertex.set("age", 30)                          # Python int → Java Integer
age = vertex.get("age")                        # Java Integer → Python int
```

---

### Floats and Decimals

```python
from arcadedb_embedded.type_conversion import convert_python_to_java
from decimal import Decimal

# Float → Double
java_double = convert_python_to_java(3.14159)

# Decimal → BigDecimal (for precision)
java_decimal = convert_python_to_java(Decimal("123.456789"))

# Reading
vertex = db.new_vertex("Product")
vertex.set("price", 19.99)                     # float → Double
vertex.set("tax", Decimal("1.23"))             # Decimal → BigDecimal

price = vertex.get("price")                    # Double → float
tax = vertex.get("tax")                        # BigDecimal → Decimal
```

---

### Strings

```python
# String conversion (mostly transparent)
vertex = db.new_vertex("User")
vertex.set("name", "Alice")                    # str → String
name = vertex.get("name")                      # String → str

# Unicode handling
vertex.set("emoji", "Hello 👋 World 🌍")
emoji = vertex.get("emoji")                    # Full Unicode support
```

---

### Dates and Times

```python
from datetime import datetime, date, time

# datetime → LocalDateTime
vertex = db.new_vertex("Event")
vertex.set("timestamp", datetime.now())

# date → LocalDate
vertex.set("birthDate", date(1990, 1, 15))

# time → LocalTime
vertex.set("startTime", time(14, 30, 0))

# Reading back
timestamp = vertex.get("timestamp")            # datetime
birth_date = vertex.get("birthDate")           # date
start_time = vertex.get("startTime")           # time
```

---

### Binary Data

```python
# bytes → byte[]
binary_data = b"Hello World"
vertex = db.new_vertex("File")
vertex.set("data", binary_data)

# Reading back
data = vertex.get("data")                      # bytes
print(data.decode("utf-8"))                    # "Hello World"
```

---

### Lists and Sets

```python
# list → ArrayList
vertex = db.new_vertex("User")
vertex.set("tags", ["python", "java", "database"])
tags = vertex.get("tags")                      # list

# set → HashSet
vertex.set("roles", {"admin", "user"})
roles = vertex.get("roles")                    # set

# Nested lists
vertex.set("matrix", [[1, 2], [3, 4]])
matrix = vertex.get("matrix")                  # [[1, 2], [3, 4]]
```

---

### Dictionaries (Maps)

```python
# dict → HashMap
vertex = db.new_vertex("User")
vertex.set("profile", {
    "firstName": "Alice",
    "lastName": "Smith",
    "address": {
        "city": "New York",
        "zip": "10001"
    }
})

# Reading back
profile = vertex.get("profile")                # dict
print(profile["firstName"])                    # "Alice"
print(profile["address"]["city"])              # "New York"
```

## Query Parameter Conversion

```python
from datetime import datetime

# Query parameters are automatically converted
results = db.query(
    "sql",
    "SELECT FROM User WHERE age > ? AND createdAt > ?",
    25, datetime(2024, 1, 1)  # Python types converted to Java
)

# Reading results (automatically converted back to Python)
for result in results:
    name = result.get_property("name")         # str
    age = result.get_property("age")           # int
    created = result.get_property("createdAt") # datetime
```

## Collection Type Preservation

```python
# Lists preserve order
vertex = db.new_vertex("Sequence")
vertex.set("numbers", [3, 1, 4, 1, 5, 9])
numbers = vertex.get("numbers")                # [3, 1, 4, 1, 5, 9]

# Sets remove duplicates
vertex.set("unique", {3, 1, 4, 1, 5, 9})
unique = vertex.get("unique")                  # {1, 3, 4, 5, 9}

# Dicts preserve keys
vertex.set("mapping", {"a": 1, "b": 2, "c": 3})
mapping = vertex.get("mapping")                # {"a": 1, "b": 2, "c": 3}
```

## Complete Example

```python
import arcadedb_embedded as arcadedb
from datetime import datetime, date
from decimal import Decimal

# Create database
db = arcadedb.create_database("./type_demo", create_if_not_exists=True)

# Create schema
with db.transaction():
    db.command("sql", "CREATE VERTEX TYPE Product")

# Test all type conversions
with db.transaction():
    product = db.new_vertex("Product")

    # Primitives
    product.set("productId", 12345)                    # int
    product.set("name", "Laptop")                      # str
    product.set("inStock", True)                       # bool
    product.set("price", 999.99)                       # float
    product.set("tax", Decimal("50.00"))               # Decimal

    # Date/time
    product.set("createdAt", datetime.now())           # datetime
    product.set("releaseDate", date(2024, 1, 15))      # date

    # Collections
    product.set("tags", ["electronics", "laptop"])     # list
    product.set("categories", {"computers", "tech"})   # set

    # Nested structures
    product.set("specs", {
        "cpu": "Intel i7",
        "ram": "16GB",
        "storage": ["512GB SSD", "1TB HDD"]
    })                                                  # dict

    # Binary
    product.set("thumbnail", b"PNG\x89...")            # bytes

    product.save()

# Read back and verify types
results = list(db.query("sql", "SELECT FROM Product"))
product = results[0]

print(f"Product ID: {product.get_property('productId')} ({type(product.get_property('productId')).__name__})")
print(f"Name: {product.get_property('name')} ({type(product.get_property('name')).__name__})")
print(f"In Stock: {product.get_property('inStock')} ({type(product.get_property('inStock')).__name__})")
print(f"Price: {product.get_property('price')} ({type(product.get_property('price')).__name__})")
print(f"Tax: {product.get_property('tax')} ({type(product.get_property('tax')).__name__})")
print(f"Created At: {product.get_property('createdAt')} ({type(product.get_property('createdAt')).__name__})")
print(f"Tags: {product.get_property('tags')} ({type(product.get_property('tags')).__name__})")

db.close()
```

**Output:**

```
Product ID: 12345 (int)
Name: Laptop (str)
In Stock: True (bool)
Price: 999.99 (float)
Tax: 50.00 (Decimal)
Created At: 2024-01-15 10:30:45.123456 (datetime)
Tags: ['electronics', 'laptop'] (list)
```

## Manual Conversion

Most of the time, conversions happen automatically. But you can manually convert when needed:

```python
from arcadedb_embedded.type_conversion import convert_python_to_java, convert_java_to_python

# Manual Python → Java
python_data = {"name": "Alice", "age": 30}
java_map = convert_python_to_java(python_data)

# Use Java object directly
java_record = db.new_vertex("User")._java_object
java_record.set("profile", java_map)

# Manual Java → Python
java_property = java_record.get("profile")
python_dict = convert_java_to_python(java_property)
print(python_dict)  # {"name": "Alice", "age": 30}
```

## Best Practices

### 1. Use Native Python Types

```python
# ✅ Good: Use Python types
vertex.set("tags", ["python", "java"])
vertex.set("count", 42)
vertex.set("timestamp", datetime.now())

# ❌ Bad: Manually convert (unnecessary)
from arcadedb_embedded.type_conversion import convert_python_to_java
vertex.set("tags", convert_python_to_java(["python", "java"]))  # Redundant
```

### 2. Use Decimal for Money

```python
from decimal import Decimal

# ✅ Good: Decimal for precise values
vertex.set("price", Decimal("19.99"))
vertex.set("tax", Decimal("1.60"))

# ❌ Bad: Float for money (precision loss)
vertex.set("price", 19.99)  # May lose precision
```

### 3. Consistent Collection Types

```python
# ✅ Good: Consistent types
vertex.set("tags", ["tag1", "tag2", "tag3"])  # All strings

# ⚠️ Mixed types work but can be confusing
vertex.set("mixed", [1, "two", 3.0, True])
```

### 4. Handle None Values

```python
# ✅ Good: Check for None
age = vertex.get("age")
if age is not None:
    print(f"Age: {age}")
else:
    print("Age not set")

# ❌ Bad: Assume value exists
print(f"Age: {vertex.get('age')}")  # May be None
```

## Type Conversion Limitations

### 1. Custom Python Classes

```python
# ❌ Custom classes not supported
class MyClass:
    def __init__(self, value):
        self.value = value

vertex.set("custom", MyClass(42))  # ❌ Error

# ✅ Convert to dict first
vertex.set("custom", {"value": 42})  # ✅ Works
```

### 2. Complex Nested Structures

```python
# ✅ Reasonable nesting works
vertex.set("data", {
    "level1": {
        "level2": {
            "level3": [1, 2, 3]
        }
    }
})

# ⚠️ Very deep nesting may impact performance
```

### 3. Large Binary Data

```python
# ✅ Small binary data
vertex.set("icon", b"PNG\x89...")  # OK

# ⚠️ Large binary data (consider file storage)
with open("large_file.bin", "rb") as f:
    data = f.read()  # May be very large
    vertex.set("file", data)  # May impact memory
```

## Troubleshooting

### Type Mismatch Errors

```python
# ❌ Error: Expected list, got dict
vertex.set("tags", {"tag1": 1})  # Wrong type

# ✅ Fix: Use correct type
vertex.set("tags", ["tag1"])
```

### Precision Loss with Floats

```python
# ⚠️ Float precision issues
price = 19.99
tax = 0.01
total = price + tax  # May not be exactly 20.00

# ✅ Use Decimal
from decimal import Decimal
price = Decimal("19.99")
tax = Decimal("0.01")
total = price + tax  # Exactly 20.00
```

### Date/Time Timezone Issues

```python
from datetime import datetime, timezone

# ⚠️ Naive datetime (no timezone)
now = datetime.now()  # Local time, no timezone

# ✅ Aware datetime (with timezone)
now_utc = datetime.now(timezone.utc)  # UTC time
```

## See Also

- **[Database API](database.md)** - Database operations
- **[Queries Guide](../guide/core/queries.md)** - Query parameters and usage
- **[Example 01: Document Store](../examples/01_simple_document_store.md)** - Basic type usage
- **[Python JPype Documentation](https://jpype.readthedocs.io/)** - Python-Java bridge
