# API Access Methods

ArcadeDB Python bindings provide **two distinct access methods** that can be used independently or together.

## Java API (Embedded Mode)

Direct JVM method calls via JPype - **recommended for most Python applications**.

### Characteristics

- **Transport**: Direct JVM method calls (no network)
- **Performance**: Fastest (no serialization/network overhead)
- **Use Cases**: Single-process applications, high-performance scenarios
- **Setup**: No server required (can be standalone or server-managed)

### Example

**Standalone Database (Most Common):**

```python
import arcadedb_embedded as arcadedb

# Direct database access - NO server needed
with arcadedb.create_database("./mydb") as db:
    # Create schema (auto-transactional)
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")

    # Insert data (requires transaction)
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice")
        person.set("age", 30)
        person.save()

    # Query data (SQL is fine for reads)
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")
```

**Server-Managed Database (Optional):**

```python
import arcadedb_embedded as arcadedb

# Server manages databases (still Java API calls)
server = arcadedb.create_server("./server_data", "password123")
server.start()

try:
    # "mydb" will be created at ./server_data/databases/mydb
    db = server.create_database("mydb")

    # Schema operations are auto-transactional
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")

    # Data operations require explicit transactions
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice")
        person.set("age", 30)
        person.save()

    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")

finally:
    server.stop()
```

## HTTP API (Server Mode)

REST requests over HTTP - **enables remote access and multi-language support**.

### Characteristics

- **Transport**: HTTP requests with JSON payloads
- **Performance**: Moderate (network + JSON serialization overhead)
- **Use Cases**: Multi-process applications, web services, remote access
- **Setup**: Requires server running

### Example

```python
import arcadedb_embedded as arcadedb
import requests
from requests.auth import HTTPBasicAuth

# Start server (using Java API)
server = arcadedb.create_server("./server_data", "password123")
server.start()

try:
    # Get server details
    base_url = f"http://localhost:{server.get_http_port()}"
    auth = HTTPBasicAuth("root", "password123")

    # Create database via HTTP (server-level command)
    response = requests.post(
        f"{base_url}/api/v1/server",
        auth=auth,
        json={"command": "CREATE DATABASE mydb"}
    )
    if not response.ok:
        raise RuntimeError(f"Server command failed: {response.status_code} {response.text}")

    # Create schema via HTTP
    response = requests.post(
        f"{base_url}/api/v1/command/mydb",
        auth=auth,
        json={"language": "sql", "command": "CREATE DOCUMENT TYPE Person"}
    )
    if not response.ok:
        raise RuntimeError(f"Create type failed: {response.status_code} {response.text}")

    # Insert data via HTTP
    response = requests.post(
        f"{base_url}/api/v1/command/mydb",
        auth=auth,
        json={
            "language": "sql",
            "command": "INSERT INTO Person SET name = 'Alice', age = 30"
        }
    )
    if not response.ok:
        raise RuntimeError(f"Insert failed: {response.status_code} {response.text}")
    # Note: HTTP commands are auto-transactional per request. For multi-statement atomicity, use
    # the HTTP transactional endpoints or perform batch writes with the embedded API via
    # `with db.transaction():`.

    # Query data via HTTP
    response = requests.post(
        f"{base_url}/api/v1/query/mydb",
        auth=auth,
        json={"language": "sql", "command": "SELECT FROM Person WHERE age > 25"}
    )
    result = response.json()

    for record in result.get("result", []):
        print(f"Name: {record.get('name')}")
    response = requests.post(
        f"{base_url}/api/v1/query/mydb",
        auth=auth,
        json={"language": "sql", "command": "SELECT FROM Person WHERE age > 25"}
    )
    result = response.json()

    for record in result["result"]:
        print(f"Name: {record['name']}")

    # Optional: inspect server info (includes available languages)
    response = requests.get(
        f"{base_url}/api/v1/server",
        auth=auth,
    )
    server_info = response.json()
    print("Available languages:", server_info.get("languages"))

finally:
    server.stop()
```

### Token-based authentication (optional)

For repeated requests, you can exchange Basic Auth for a session token and use
`Authorization: Bearer <token>` instead of sending credentials each time:

```python
# Login to receive a token
response = requests.post(
    f"{base_url}/api/v1/login",
    auth=auth,
)
token = response.json()["token"]

# Use Bearer token for subsequent requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    f"{base_url}/api/v1/query/mydb",
    headers=headers,
    json={"language": "sql", "command": "SELECT FROM Person"}
)
```

## Hybrid Usage

Both APIs can be used **simultaneously** on the same server:

```python
import arcadedb_embedded as arcadedb
import requests
from requests.auth import HTTPBasicAuth

# Start server
server = arcadedb.create_server("./hybrid", "password123")
server.start()

try:
    # Create database using Java API (fastest)
    db = server.create_database("hybriddb")

    # Schema operations are auto-transactional
    db.schema.create_document_type("Person")
    db.schema.create_property("Person", "name", "STRING")
    db.schema.create_property("Person", "age", "INTEGER")

    # Data operations require explicit transactions
    with db.transaction():
        person = db.new_document("Person")
        person.set("name", "Alice")
        person.set("age", 30)
        person.save()

    # Query same data using HTTP API (remote access)
    auth = HTTPBasicAuth("root", "password123")
    response = requests.post(
        f"http://localhost:{server.get_http_port()}/api/v1/query/hybriddb",
        auth=auth,
        json={"language": "sql", "command": "SELECT FROM Person"}
    )
    if not response.ok:
        raise RuntimeError(f"HTTP query failed: {response.status_code} {response.text}")

    result = response.json()
    print(f"HTTP API found {len(result['result'])} records")
    print(f"Record from HTTP: {result['result'][0]}")

finally:
    server.stop()
```

## Performance Comparison

| Aspect | Java API | HTTP API | Notes |
|--------|----------|----------|-------|
| **Initialization** | ~0.5s | ~0.8s | HTTP has connection overhead |
| **Insert Rate** | ~1000/s | ~300/s | Network + JSON serialization |
| **Query Rate** | ~500/s | ~200/s | Result serialization overhead |
| **Memory** | Lower | Higher | JSON serialization |
| **Latency** | ~1ms | ~5ms | Network round-trip |

*Performance numbers are approximate and depend on hardware, data size, and network conditions.*

## When to Use Each

### Use Java API When:

- Single Python process application
- Maximum performance required
- Complex data manipulation
- Batch processing
- Local development/testing

### Use HTTP API When:

- Multi-process architecture
- Remote database access
- Web applications/APIs
- Multiple programming languages
- Microservices architecture
- Cross-network access

### Use Both When:

- Local high-performance operations + remote monitoring
- Hybrid applications with embedded + web components
- Development (Java API) + production monitoring (HTTP API)

## Common Misconceptions

- ❌ **"Java API is only for Java"**
    - ✅ Java API is Python calling Java via JPype (fully Pythonic)
- ❌ **"HTTP API is inferior"**
    - ✅ HTTP API enables remote access (different purpose)
- ❌ **"Must choose one or the other"**
    - ✅ Both can be used simultaneously on the same server
- ❌ **"Performance difference means HTTP is broken"**
    - ✅ Performance difference is expected (network vs direct calls)
