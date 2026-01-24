# Server Pattern Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py){ .md-button }

These notes mirror the Python tests in [test_server_patterns.py]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py). There are 6 tests covering three access patterns: standalone embedded, server-managed embedded, and HTTP API (remote access). All tests validate expected usage flows and performance characteristics.

## The 3 Access Patterns

1. **Standalone**: `db = arcadedb.create_database("./mydb")` — simplest, no server overhead
2. **Server-managed**: `server.start()` → `db = server.create_database()` — HTTP API available simultaneously
3. **HTTP API**: `requests.post(url, json=...)` — remote/cross-process access

## Test Cases

### 1) recommended server pattern

Starts server first, creates database through server, and validates both embedded access and HTTP availability. Asserts connection to studio URL and data retrieval via Java API. See [test_server_patterns.py#L24-L78]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py#L24-L78).

### 2) thread safety

Creates server-managed database with 20 items, then spawns 5 threads concurrently querying ranges. Asserts all threads access successfully without errors. See [test_server_patterns.py#L81-L147]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py#L81-L147).

### 3) context manager

Uses `with arcadedb.create_server(...) as server:` for automatic start/stop, creates database, inserts note, verifies count. See [test_server_patterns.py#L150-L183]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py#L150-L183).

### 5) embedded performance comparison

Creates both standalone and server-managed databases with 500 complex multi-field records and runs 100 varied queries (filters, aggregations, date ranges, LIKE patterns). Measures time and ops/sec. Asserts server-managed performance is similar (within 1.5x, typically 0.99x) to standalone. Validates that embedded access through server is direct JVM call, not HTTP. See [test_server_patterns.py#L289-L436]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py#L289-L436).

### 6) HTTP API access pattern

Starts server, creates database via Java API (HTTP API lacks create), inserts 5 products via HTTP, queries via HTTP (returns JSON), performs 100 mixed CRUD ops (inserts, filtered queries, updates, aggregations, LIKE searches) via both HTTP and Java API. Records time and ops/sec. Calculates ratio (HTTP typically 5–7x slower) and per-op overhead (~0.7–1ms). Uses `requests.Session()` with auth for realistic connection pooling. See [test_server_patterns.py#L439-L760]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_patterns.py#L439-L760).

## Quick Patterns

**Just need a database:**
```python
db = arcadedb.create_database("./mydb")
```

**Need HTTP API available:**
```python
server = arcadedb.create_server(root_path="./databases")
server.start()
db = server.create_database("mydb")
# Java API is direct JVM call (0.99x perf of standalone)
# HTTP also available at http://localhost:2480
```

**Pre-populating before server:**
```python
db = arcadedb.create_database("./temp_db")
# ... populate ...
db.close()  # ⚠️ Release file lock!
# Move to server directory, then start server
```

**Remote/HTTP access:**
```python
import requests
session = requests.Session()
session.auth = ("root", "password")
r = session.post("http://localhost:2480/api/v1/query/mydb",
                  json={"language": "sql", "command": "SELECT ..."})
# 5–7x slower than Java API, ~0.7ms overhead per op
```
