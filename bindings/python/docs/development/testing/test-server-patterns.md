# Server Pattern Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py){ .md-button }

There are 6 tests covering three access patterns: standalone embedded, server-managed embedded, and HTTP API (remote access). Four check correctness; the two comparisons (5 and 6) also print timings, which are for reading and are not asserted.

## The 3 Access Patterns

1. **Standalone**: `db = arcadedb.create_database("./mydb")`, simplest, no server
2. **Server-managed**: `server.start()` then `db = server.create_database("mydb")`; the HTTP API is available at the same time
3. **HTTP API**: `requests.post(url, json=...)` for remote or cross-process access

## Test Cases

### 1) recommended server pattern

Starts the server first and creates the database through it. Asserts the server reports started and its Studio URL, reads a record back through the embedded handle, then queries the same database over HTTP while the embedded handle is still open and asserts both rows come back.

### 2) thread safety

Creates a server-managed database with 20 items, then 5 threads query disjoint id ranges at once. Asserts no thread raised and each saw exactly its own four ids.

### 3) context manager

Uses `with arcadedb.create_server(...) as server:` for automatic start and stop, creates a database, inserts a note, asserts the count is 1, and asserts the server reports stopped after the block.

### 4) pattern 1: embedded first requires close

Creates a database in standalone embedded mode and populates it, closes it to release the file lock, moves it into the server's `databases/` directory, starts the server, and opens it with `server.get_database(...)`. Asserts the records survived the move, that an insert through the server lands, and that the new count is visible over HTTP.

### 5) embedded performance comparison

Creates a standalone and a server-managed database with 500 multi-field records each and runs the same 100 queries (filters, aggregations, date ranges, LIKE patterns) against both. Prints both times and their ratio. It shows that embedded access through a server is a direct JVM call, not HTTP; the ratio is printed, not asserted.

### 6) HTTP API access pattern

Starts a server and does everything else over HTTP: creates the database with the server command endpoint (`POST /api/v1/server`, `create database httpdb`), creates the schema, inserts 5 products, and queries them, asserting a 200 status at each step. It then runs 100 mixed CRUD operations over HTTP and through the Java API and prints both times. Uses `requests.Session()` with basic auth for connection pooling.

## Quick Patterns

**Just need a database:**

```python
db = arcadedb.create_database("./mydb")
```

**Need HTTP API available:**

```python
server = arcadedb.create_server(root_path="./databases", root_password="change-me")
server.start()
db = server.create_database("mydb")
# Java API calls are direct JVM calls; HTTP is also at http://localhost:2480
```

**Pre-populating before server:**

```python
db = arcadedb.create_database("./temp_db")
# ... populate ...
db.close()  # release the file lock first
# Move into <root_path>/databases/, then start the server
```

**Remote/HTTP access:**

```python
import requests
session = requests.Session()
session.auth = ("root", "change-me")
r = session.post("http://localhost:2480/api/v1/query/mydb",
                 json={"language": "sql", "command": "SELECT ..."})
```
