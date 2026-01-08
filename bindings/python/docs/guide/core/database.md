# Database Management

Comprehensive guide to database lifecycle, configuration, and resource management in
ArcadeDB Python bindings.

## Overview

ArcadeDB databases are embedded, file-based databases stored on your local filesystem.
The database lifecycle includes creation, opening, operations, and cleanup.

**Database Modes:**

- **Embedded**: Database runs in your Python process
- **In-Process**: Direct Java API access via JPype
- **File-Based**: Data persisted to disk

## Quick Start

### Create New Database

```python
import arcadedb_embedded as arcadedb

# Simple creation
with arcadedb.create_database("./mydb") as db:
    # Use the database
    db.schema.create_vertex_type("User")
    with db.transaction():
        vertex = db.new_vertex("User")
        vertex.set("name", "Alice")
        vertex.save()
```

### Open Existing Database

```python
# Open existing database
with arcadedb.open_database("./mydb") as db:
    # Query data
    result = db.query("sql", "SELECT FROM User")
    for user in result:
        print(user.get("name"))
```

### Check if Database Exists

```python
if arcadedb.database_exists("./mydb"):
    with arcadedb.open_database("./mydb") as db:
        pass
else:
    with arcadedb.create_database("./mydb") as db:
        pass
```

## Database Lifecycle

### 1. Creation

```python
import arcadedb_embedded as arcadedb

# Create new database
with arcadedb.create_database("./mydb") as db:
    print(f"Database created at: {db.get_name()}")
```

**What happens during creation:**

1. Directory `./mydb` created on filesystem
2. Schema files initialized
3. System files created (dictionary, configuration)
4. Database opened in READ_WRITE mode
5. Ready for operations

### 2. Opening

```python
# Open existing database
with arcadedb.open_database("./mydb") as db:
    print(f"Database opened: {db.get_name()}")
```

### 3. Using

```python
with arcadedb.open_database("./mydb") as db:
    # Create schema
    db.schema.create_vertex_type("Person")
    db.schema.create_property("Person", "name", "STRING")

    # Insert data
    with db.transaction():
        person = db.new_vertex("Person")
        person.set("name", "Bob")
        person.save()

    # Query data
    result = db.query("sql", "SELECT FROM Person")
    for person in result:
        print(person.get("name"))
```

### 4. Closing

```python
# Explicit close
db.close()

# Or use context manager (recommended)
with arcadedb.open_database("./mydb") as db:
    # Use database
    pass
# Automatically closed
```

**What happens during close:**

1. Active transactions rolled back
2. Buffers flushed to disk
3. Files closed
4. Resources released
5. Database removed from active instances

### 5. Dropping

```python
with arcadedb.open_database("./mydb") as db:
    # Drop database (deletes all files)
    db.drop()

# Database and all files are permanently deleted
```

⚠️ **Warning**: `drop()` is irreversible and deletes all data!

## DatabaseFactory Class

For advanced use cases, use `DatabaseFactory` directly:

```python
import arcadedb_embedded as arcadedb

# Create factory
factory = arcadedb.DatabaseFactory("./mydb")

# Open or create via factory
if factory.exists():
    print("Database exists")
    with factory.open() as db:
        with db.transaction():
            # Operations
            pass
else:
    print("Creating new database")
    with factory.create() as db:
        with db.transaction():
            # Operations
            pass
```

### Factory Pattern Benefits

- **Explicit control**: Clear separation of creation/opening logic
- **Reusability**: One factory for multiple operations
- **Configuration**: Set options before creating/opening

## Context Managers

### Database Context Manager

```python
# Automatic resource cleanup
with arcadedb.open_database("./mydb") as db:
    # Use database
    result = db.query("sql", "SELECT FROM User")
    for row in result:
        print(row.get("name"))
# Database automatically closed on exit
```

**Benefits:**

- ✅ Automatic close on normal exit
- ✅ Automatic close on exception
- ✅ Guaranteed resource cleanup
- ✅ Pythonic style

### Nested Context Managers

```python
# Open database and use transaction
with arcadedb.open_database("./mydb") as db:
    with db.transaction():
        vertex = db.new_vertex("User")
        vertex.set("name", "Charlie")
        vertex.save()
# Transaction committed, database closed
```

## Configuration

### Database Directory Structure

```
./mydb/
├── configuration.json      # Database configuration
├── schema.json             # Schema definition
├── schema.prev.json        # Schema backup
├── dictionary.*.dict       # String dictionary
├── statistics.json         # Database statistics
├── User_0.*.bucket         # User type data files
├── HasFriend_0.*.bucket    # Edge type data files
└── .lock                   # Lock file (when open)
```

### Database Location

```python
import os

# Relative path
with arcadedb.create_database("./mydb"):
    pass

# Absolute path
with arcadedb.create_database("/var/data/mydb"):
    pass

```

## Resource Management

### Proper Cleanup

```python
# ✓ Recommended: Context manager
with arcadedb.open_database("./mydb") as db:
    # Use database
    pass

# ✓ Acceptable: Explicit close
db = arcadedb.open_database("./mydb")
try:
    # Use database
    pass
finally:
    db.close()

# ✗ Bad: No cleanup
db = arcadedb.open_database("./mydb")
# Operations...
# Database never closed!
```

### Multiple Databases

```python
with arcadedb.open_database("./database1") as db1, \
     arcadedb.open_database("./database2") as db2:
    # Use both databases
    result1 = db1.query("sql", "SELECT FROM User")
    result2 = db2.query("sql", "SELECT FROM Product")

# Or with context managers
with arcadedb.open_database("./database1") as db1, \
     arcadedb.open_database("./database2") as db2:
    # Use both databases
    pass
```

### Database Locking

**Lock File:**

- Created when database opens: `.lock`
- Prevents concurrent access from same/different processes
- Automatically removed on clean close
- Manual removal only if process crashed

```python
# If database locked by another process
try:
    with arcadedb.open_database("./mydb"):
        pass
except Exception as e:
    print(f"Database locked: {e}")

    # Check if process is still running
    # If not, remove lock file
    import os
    lock_file = "./mydb/.lock"
    if os.path.exists(lock_file):
        os.remove(lock_file)
```

## Common Patterns

### Database Initialization

```python
def init_database(path: str):
    """Initialize database with schema."""
    # Create if doesn't exist
    if not arcadedb.database_exists(path):
        with arcadedb.create_database(path) as db:
            # Prefer Schema API for embedded usage (auto-transactional)
            db.schema.create_vertex_type("User")
            db.schema.create_property("User", "email", "STRING")
            db.schema.create_index("User", ["email"], unique=True)

            db.schema.create_vertex_type("Post")
            db.schema.create_property("Post", "title", "STRING")

            db.schema.create_edge_type("Authored")

            print(f"Database initialized at {path}")

    return arcadedb.open_database(path)

# Usage
with init_database("./myapp") as db:
    pass
```

### Database Reset

```python
def reset_database(path: str):
    """Drop and recreate database."""
    if arcadedb.database_exists(path):
        with arcadedb.open_database(path) as db:
            db.drop()
            print(f"Database dropped: {path}")

    with arcadedb.create_database(path) as db:
        print(f"Database created: {path}")

    return arcadedb.open_database(path)

# Usage
with reset_database("./mydb") as db:
    pass
```

### Database Backup Pattern

```python
import shutil
import datetime

def backup_database(db_path: str, backup_dir: str):
    """Backup database files."""
    # Close database first
    if arcadedb.database_exists(db_path):
        with arcadedb.open_database(db_path):
            pass  # Ensure clean state

    # Create backup with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{backup_dir}/backup_{timestamp}"

    # Copy database directory
    shutil.copytree(db_path, backup_path)
    print(f"Backup created: {backup_path}")

    return backup_path

# Usage
backup_path = backup_database("./mydb", "./backups")
```

### Database Migration

```python
def migrate_database(old_path: str, new_path: str):
    """Migrate data from old to new database."""
    with arcadedb.open_database(old_path) as old_db, \
         arcadedb.create_database(new_path) as new_db:
        # Copy schema
        # Create types (Schema API is auto-transactional)
        new_db.schema.create_vertex_type("User")
        new_db.schema.create_vertex_type("Post")
        new_db.schema.create_edge_type("Authored")

        # Copy data
        batch_size = 1000

        # Migrate users
        result = old_db.query("sql", "SELECT FROM User")
        users_batch = []
        for user in result:
            users_batch.append(user)

            if len(users_batch) >= batch_size:
                with new_db.transaction():
                    for u in users_batch:
                        new_user = new_db.new_vertex("User")
                        new_user.set("name", u.get("name"))
                        new_user.set("email", u.get("email"))
                        new_user.save()
                users_batch = []

        # Flush remaining
        if users_batch:
            with new_db.transaction():
                for u in users_batch:
                    new_user = new_db.new_vertex("User")
                    new_user.set("name", u.get("name"))
                    new_user.set("email", u.get("email"))
                    new_user.save()

        print("Migration complete")

# Usage
migrate_database("./old_db", "./new_db")
```

## Database Information

### Check Transaction Status

```python
with arcadedb.open_database("./mydb") as db:
    print(db.is_transaction_active())  # False

    with db.transaction():
        print(db.is_transaction_active())  # True

    print(db.is_transaction_active())  # False
```

## Error Handling

### Database Already Exists

```python
try:
    with arcadedb.create_database("./mydb") as db:
        pass
except Exception as e:
    print(f"Error: {e}")
    # Database already exists
    with arcadedb.open_database("./mydb") as db:
        pass
```

### Database Not Found

```python
try:
    with arcadedb.open_database("./nonexistent") as db:
        pass
except Exception as e:
    print(f"Database not found: {e}")
    # Create it
    with arcadedb.create_database("./nonexistent") as db:
        pass
```

### Database Locked

```python
import time

def open_with_retry(path, max_retries=3):
    """Open database with retry logic."""
    for attempt in range(max_retries):
        try:
            return arcadedb.open_database(path)
        except Exception as e:
            if "locked" in str(e).lower():
                if attempt < max_retries - 1:
                    print(f"Database locked, retry {attempt + 1}/{max_retries}")
                    time.sleep(1)
                    continue
            raise
    raise Exception("Failed to open database after retries")

# Usage
with open_with_retry("./mydb") as db:
    pass
```

## Advanced Topics

### JVM Lifecycle and Databases

```python
# JVM starts on first import
import arcadedb_embedded as arcadedb  # JVM starts here

# JVM runs for entire Python process
with arcadedb.create_database("./db1") as db1:
    pass

with arcadedb.open_database("./db1") as db2:  # Same JVM
    pass

# JVM shuts down when Python exits
```

### Multiple Databases, One JVM

```python
# All databases share the same JVM
with arcadedb.open_database("./database1") as db1, \
     arcadedb.open_database("./database2") as db2, \
     arcadedb.open_database("./database3") as db3:
    # Efficient: shared JVM resources
    pass
```

## See Also

- [Database API Reference](../../api/database.md) - Complete API documentation
- [Transactions](transactions.md) - Transaction management
- [Quick Start](../../getting-started/quickstart.md) - Getting started guide
- [Server Mode](../../api/server.md) - Multi-process database access
