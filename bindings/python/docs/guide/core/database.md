# Database Management

Comprehensive guide to database lifecycle, configuration, and resource management in ArcadeDB Python bindings.

## Overview

ArcadeDB databases are embedded, file-based databases stored on your local filesystem. The database lifecycle includes creation, opening, operations, and cleanup.

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

**Opening modes:**

- `READ_WRITE` (default): Full access
- `READ_ONLY`: Query-only access (coming soon to Python API)

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
├── configuration.json       # Database configuration
├── schema.json             # Schema definition
├── schema.prev.json        # Schema backup
├── dictionary.*.dict       # String dictionary
├── statistics.json         # Database statistics
├── User_0.*.bucket        # User type data files
├── HasFriend_0.*.bucket   # Edge type data files
└── .lock                  # Lock file (when open)
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

# User home directory
home = os.path.expanduser("~")
with arcadedb.create_database(f"{home}/databases/mydb"):
    pass
```

### Database Naming

**Rules:**

- ✅ Use alphanumeric characters
- ✅ Use underscores and hyphens
- ✅ Use forward slashes for paths
- ❌ Avoid spaces in names
- ❌ Avoid special characters

```python
# Good names
arcadedb.create_database("./my_database")
arcadedb.create_database("./project-data")
arcadedb.create_database("./data/production/main")

# Bad names
arcadedb.create_database("./my database")      # Space
arcadedb.create_database("./data@2024")        # Special char
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
            with db.transaction():
                db.command("sql", "CREATE VERTEX TYPE User")
                db.command("sql", "CREATE PROPERTY User.email STRING")
                db.command("sql", "CREATE INDEX ON User (email) UNIQUE")

                db.command("sql", "CREATE VERTEX TYPE Post")
                db.command("sql", "CREATE PROPERTY Post.title STRING")

                db.command("sql", "CREATE EDGE TYPE Authored")

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
        with new_db.transaction():
            # Create types
            new_db.command("sql", "CREATE VERTEX TYPE User")
            new_db.command("sql", "CREATE VERTEX TYPE Post")
            new_db.command("sql", "CREATE EDGE TYPE Authored")

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

### Singleton Database Pattern

```python
class DatabaseManager:
    """Singleton database manager."""

    _instance = None
    _db = None

    def __new__(cls, path: str):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._path = path
        return cls._instance

    def get_database(self):
        """Get or create database connection."""
        if self._db is None:
            if arcadedb.database_exists(self._path):
                self._db = arcadedb.open_database(self._path)
            else:
                self._db = arcadedb.create_database(self._path)
        return self._db

    def close(self):
        """Close database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

# Usage
manager = DatabaseManager("./mydb")
db = manager.get_database()

# Use database
result = db.query("sql", "SELECT FROM User")

# Later...
manager.close()
```

## Database Information

### Get Database Name

```python
with arcadedb.open_database("./mydb") as db:
    print(f"Database: {db.get_name()}")  # "mydb"
```

### Get Database Path

```python
with arcadedb.open_database("./mydb") as db:
    print(f"Path: {db.get_name()}")
    # Note: Currently returns name, full path API coming soon
```

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

### Graceful Shutdown

```python
import atexit
import signal

db = None

def cleanup():
    """Cleanup on exit."""
    global db
    if db is not None:
        try:
            if db.is_transaction_active():
                db.rollback()
            db.close()
            print("Database closed cleanly")
        except:
            pass

# Register cleanup handlers
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda s, f: cleanup())
signal.signal(signal.SIGINT, lambda s, f: cleanup())

# Use database
db = arcadedb.open_database("./mydb")
```

## Best Practices

### 1. Always Close Databases

```python
# ✓ Use context managers
with arcadedb.open_database("./mydb") as db:
    pass

# ✓ Or explicit close in finally
db = arcadedb.open_database("./mydb")
try:
    pass
finally:
    db.close()
```

### 2. Check Existence Before Creating

```python
# ✓ Check first
if arcadedb.database_exists("./mydb"):
    with arcadedb.open_database("./mydb") as db:
        pass
else:
    with arcadedb.create_database("./mydb") as db:
        pass

# ✗ Don't blindly create
db = arcadedb.create_database("./mydb")  # Error if exists!
```

### 3. Use Absolute Paths in Production

```python
import os

# ✓ Absolute path
db_path = os.path.abspath("./mydb")
with arcadedb.open_database(db_path) as db:
    pass

# ✗ Relative paths can be ambiguous
db = arcadedb.open_database("./mydb")  # Depends on CWD
```

### 4. Initialize Schema on Creation

```python
def get_or_create_database(path):
    if arcadedb.database_exists(path):
        return arcadedb.open_database(path)

    # Create with schema
    with arcadedb.create_database(path) as db:
        with db.transaction():
            # Define schema here
            db.command("sql", "CREATE VERTEX TYPE User")
            db.command("sql", "CREATE INDEX ON User (email) UNIQUE")

    return arcadedb.open_database(path)
```

### 5. Handle Concurrent Access

```python
# Only one process can open database at a time
# For multi-process: use server mode instead

# ✓ Single process, multiple threads
with arcadedb.open_database("./mydb") as db:
    # Each thread uses same db instance
    pass

# ✗ Multiple processes opening same database
# Process 1: arcadedb.open_database("./mydb")
# Process 2: arcadedb.open_database("./mydb")  # ERROR!
```

### 6. Backup Before Dropping

```python
import shutil

def safe_drop(db_path, backup_path):
    """Drop database with backup."""
    # Backup first
    shutil.copytree(db_path, backup_path)

    # Then drop
    with arcadedb.open_database(db_path) as db:
        db.drop()

    print(f"Database dropped, backup at {backup_path}")
```

### 7. Monitor Database Size

```python
import os

def get_database_size(db_path):
    """Get database size in MB."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(db_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # MB

# Usage
size_mb = get_database_size("./mydb")
print(f"Database size: {size_mb:.2f} MB")
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

### Database Path Normalization

```python
# ArcadeDB normalizes paths
with arcadedb.open_database("./mydb"):
    pass

with arcadedb.open_database("./mydb/"):  # Same as above
    pass

with arcadedb.open_database("mydb"):     # Different! (no ./)
    pass
```

## Troubleshooting

### "Database already exists"

```python
# Check first
if arcadedb.database_exists("./mydb"):
    with arcadedb.open_database("./mydb") as db:
        pass
else:
    with arcadedb.create_database("./mydb") as db:
        pass
```

### "Database not found"

```python
# Verify path
import os
db_path = "./mydb"
if not os.path.exists(db_path):
    print(f"Path doesn't exist: {db_path}")
    with arcadedb.create_database(db_path) as db:
        pass
```

### "Database is locked"

```python
# Another process has database open
# Solution 1: Close other process
# Solution 2: Remove .lock file if process crashed
import os
lock_file = "./mydb/.lock"
if os.path.exists(lock_file):
    os.remove(lock_file)
```

### Memory Usage

```python
import gc

# Force garbage collection after closing
with arcadedb.open_database("./mydb") as db:
    pass

gc.collect()  # Clean up Java objects
```

## See Also

- [Database API Reference](../../api/database.md) - Complete API documentation
- [Transactions](transactions.md) - Transaction management
- [Quick Start](../../getting-started/quickstart.md) - Getting started guide
- [Server Mode](../../api/server.md) - Multi-process database access
