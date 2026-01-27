# Database Utilities Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_database_utils.py){ .md-button }

There are 5 tests covering database creation helpers, schema initialization, test data generation, cleanup utilities, and type counting.

### test_create_test_database

Tests database creation helper functions.

**What it tests:**

- Creating clean test database
- Cleanup of existing database
- Context manager support

**Pattern:**
```python
# Create database with helper
db = create_test_database("./test_db")

assert db is not None
assert os.path.exists("./test_db")
```

---

### test_populate_test_data

Tests test data population utilities.

**What it tests:**

- Generating test vertices
- Creating test edges
- Populating with realistic data
- Configurable record counts

**Pattern:**
```python
from test_utils import populate_users, populate_posts

# Populate test users
populate_users(db, count=100)
assert db.count_type("User") == 100

# Populate test posts
populate_posts(db, user_count=100, posts_per_user=5)
assert db.count_type("Post") == 500
```

---

### test_count_all_types

Tests counting records across all types.

**What it tests:**

- Getting count for each type
- Summing total records
- Empty database handling

**Pattern:**
```python
from test_utils import count_all_types

# Get counts
counts = count_all_types(db)

assert counts["User"] == 100
assert counts["Post"] == 500

total = sum(counts.values())
assert total == 600
```

---

### test_cleanup_database

Tests database cleanup utilities.

**What it tests:**

- Removing all records
- Dropping all types
- Full database cleanup
- Cleanup without errors

**Pattern:**
```python
from test_utils import cleanup_database

# Populate database
populate_users(db, 100)

# Clean up
cleanup_database(db)

# Verify empty
assert db.count_type("User") == 0
```

---

### test_schema_initialization_helper

Tests schema setup helpers.

**What it tests:**

- Creating common schema patterns
- Social network schema
- Document store schema
- E-commerce schema templates

**Pattern:**
```python
from test_utils import init_social_schema

# Initialize social network schema
init_social_schema(db)

# Verify schema created
assert db.schema.exists_type("User")
assert db.schema.exists_type("Post")
assert db.schema.exists_type("Follows")
assert db.schema.exists_type("Likes")
```

## Test Patterns

### Database Setup

```python
from test_utils import create_test_database, init_social_schema

with create_test_database("./test_db") as db:
    init_social_schema(db)
    # ... continue with test ...
```

### Data Population

```python
from test_utils import populate_users, populate_edges

with db:  # Assuming db is created in context
    # Create users
    user_count = populate_users(db, 100)

    # Create relationships
    edge_count = populate_edges(db, "Follows", density=0.1)
```

### Cleanup

```python
from test_utils import cleanup_database

with create_test_database("./test_db") as db:
    try:
        # Test operations
        pass
    finally:
        cleanup_database(db)
        # Database automatically closed by context manager
```

## Utility Functions Reference

### create_test_database

```python
def create_test_database(path: str) -> Database:
    """Create a test database with cleanup."""
    if os.path.exists(path):
        shutil.rmtree(path)
    return arcadedb.create_database(path)
```

### populate_users

```python
def populate_users(db: Database, count: int) -> int:
    """Populate database with test users."""
    with db.transaction():
        for i in range(count):
            vertex = db.new_vertex("User")
            vertex.set("userId", i)
            vertex.set("username", f"user{i}")
            vertex.set("age", 18 + i % 50)
            vertex.save()
    return count
```

### count_all_types

```python
def count_all_types(db: Database) -> dict:
    """Get record count for all types."""
    counts = {}
    for type_obj in db.schema.get_types():
        type_name = type_obj.get_name()
        counts[type_name] = db.count_type(type_name)
    return counts
```

### cleanup_database

```python
def cleanup_database(db: Database):
    """Remove all records from database."""
    for type_obj in db.schema.get_types():
        type_name = type_obj.get_name()
        db.command("sql", f"DELETE FROM {type_name}")
```

## Common Assertions

```python
# Database created
assert db is not None
assert os.path.exists(db_path)

# Data populated
assert db.count_type("User") > 0

# Schema initialized
assert db.schema.exists_type("User")

# Database cleaned
assert sum(count_all_types(db).values()) == 0
```

## Key Takeaways

1. **Use helpers** - Reduce boilerplate in tests
2. **Always cleanup** - Use try/finally blocks
3. **Parameterize counts** - Make tests configurable
4. **Reusable schemas** - Create common patterns
5. **Check empty** - Verify cleanup worked

## See Also

- **[Database API](../../api/database.md)** - Database operations
- **[Testing Overview](overview.md)** - Testing strategies
- **[Core Tests](test-core.md)** - Core functionality tests
