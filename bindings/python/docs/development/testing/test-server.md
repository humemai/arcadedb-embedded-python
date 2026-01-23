# Server Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_server.py){ .md-button }

These notes mirror the Python tests in [test_server.py]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_server.py). There are 4 tests covering server creation, database operations, custom config, and context managers. For advanced patterns (embedded + HTTP), see [Server Patterns](test-server-patterns.md).

## Test Cases

All 4 tests verify basic server workflows: starting server, creating/accessing databases, ensuring databases persist, and proper cleanup. See [test_server.py]({{ config.repo_url }}/blob/{{ config.extra.version }}/bindings/python/tests/test_server.py) for implementation.

## Quick Example

```python
import arcadedb_embedded as arcadedb

# Create and start server
server = arcadedb.create_server(
    root_path="./databases",
    root_password="mypassword"
)
server.start()

# Create database
# "mydb" will be created at ./databases/databases/mydb
db = server.create_database("mydb")

# Use it
db.schema.create_document_type("Person")  # Schema ops are auto-transactional
with db.transaction():
    person = db.new_document("Person")
    person.set("name", "Alice").save()

# Query
result = db.query("sql", "SELECT FROM Person")
for person in result:
    print(person.get("name"))

# Stop server
server.stop()
```

## Test Cases

### 1. Server Creation and Startup

**Test:** `test_server_creation`

```python
server = arcadedb.create_server(root_path="./databases")
server.start()

assert server.is_started()

server.stop()
assert not server.is_started()
```

### 2. Database Operations Through Server

**Test:** `test_server_database_operations`

```python
with arcadedb.create_server(root_path="./databases") as server:
    server.start()

    # Create database through server
    db = server.create_database("testdb")

    # Use Java API for operations
    db.schema.create_document_type("Person")
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice").save()

    # Query
    result = db.query("sql", "SELECT FROM Person")
    for person in result:
        print(person.get("name"))
```

### 3. Custom Configuration

**Test:** `test_server_custom_config`

```python
server = arcadedb.create_server(
    root_path="./databases",
    root_password="secure_password",
    config={
        "http_port": 8080,
        "host": "127.0.0.1",
        "mode": "production"
    }
)
server.start()

assert server.get_http_port() == 8080
```

### 4. Context Manager

**Test:** `test_server_context_manager`

```python
with arcadedb.create_server(root_path="./databases") as server:
    server.start()
    # Server automatically stopped on exit
```

## Running These Tests

```bash
# Run all server tests
pytest tests/test_server.py -v

# Run specific test
pytest tests/test_server.py::test_server_creation -v
```



## Related Documentation

- [Server Patterns](test-server-patterns.md) - Advanced patterns
- [Server API Reference](../../api/server.md)
- [Server Guide](../../guide/server.md)
- [Concurrency Tests](test-concurrency.md) - Multi-process access
