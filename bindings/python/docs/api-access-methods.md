# API Access Methods

`arcadedb-embedded` runs the ArcadeDB engine **inside your Python process** and
talks to it through direct JVM calls via JPype. That is the primary mode and
the reason the package exists.

It also bundles an **optional in-process HTTP server** with the Studio web UI.
It is off until you call `create_server()`, and it lets the process that owns
the database expose that same data over HTTP to other processes and languages.
See [Server Mode](guide/server.md) for what it costs on disk (about +8 MB) and
at runtime (nothing until you start it).

So there are three ways to reach your data, and they compose:

| | How you call it | Who can reach it |
|---|---|---|
| **Embedded (Java API)** | Direct JVM calls, no network | This process only |
| **Server-managed** | Direct JVM calls, database owned by a running server | This process, plus HTTP clients |
| **HTTP API** | REST + JSON over a socket | Any process, any language, optionally remote |

## Java API (Embedded Mode)

Direct JVM method calls via JPype for embedded/local runtime access.

!!! note "DSL-first guidance"
    Prefer SQL/OpenCypher via `db.command(...)` and `db.query(...)` for schema, CRUD, and graph operations.
    Wrapper APIs remain available as compatibility/reference features, but examples and guides are standardized on DSL usage.

### Characteristics

- **Transport**: Direct JVM method calls (no network)
- **Performance**: Fastest (no serialization/network overhead)
- **Use Cases**: Single-process applications, high-performance scenarios
- **Setup**: Nothing beyond `pip install arcadedb-embedded` — no server, no Java installation

### Example

```python
import arcadedb_embedded as arcadedb

# Direct database access - NO server needed
with arcadedb.create_database("./mydb") as db:
    # Create schema (auto-transactional)
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")

    # Insert data (requires transaction)
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")

    # Query data (SQL is fine for reads)
    result = db.query("sql", "SELECT FROM Person WHERE age > 25")
    for record in result:
        print(f"Name: {record.get('name')}")
```

**Server-Managed Database (Optional):**

A server-managed database is still reached through direct JVM calls from the
owning process, so reads and writes here cost the same as embedded mode. The
difference is that the server also publishes it over HTTP.

```python
import arcadedb_embedded as arcadedb

# Server manages databases (still Java API calls)
server = arcadedb.create_server("./server_data", "password123")
server.start()

try:
    # "mydb" will be created at ./server_data/databases/mydb
    db = server.create_database("mydb")

    # Schema operations are auto-transactional
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")

    # Data operations require explicit transactions
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")

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
- **Performance**: Slower than embedded (socket round-trip + JSON on both ends)
- **Use Cases**: Multi-process applications, web services, remote access
- **Setup**: Requires a running server (`create_server()`, or the official
  ArcadeDB server distribution)

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
    # the HTTP transactional endpoints or embedded `with db.transaction():` blocks.

    # Query data via HTTP
    response = requests.post(
        f"{base_url}/api/v1/query/mydb",
        auth=auth,
        json={"language": "sql", "command": "SELECT FROM Person WHERE age > 25"}
    )
    result = response.json()

    for record in result.get("result", []):
        print(f"Name: {record.get('name')}")

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

!!! tip "The first HTTP request is much slower than the rest"
    Measured on one developer machine, in-process: first request **5.6 s**,
    second **0.7 s**, every one after that **under 10 ms**. Undertow and the
    REST handlers class-load lazily and the root password is verified with a
    deliberately expensive KDF, and both land on request one. If you poll for
    readiness after `start()`, give the first attempt a generous timeout — a
    tight one just turns warmup into a failure.

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

Both APIs can be used **simultaneously** on the same server, against the same
database, in one transaction-consistent store. This is the case in-process
server mode exists for: local code keeps full-speed embedded access while other
processes reach the same data over HTTP.

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
    db.command("sql", "CREATE DOCUMENT TYPE Person")
    db.command("sql", "CREATE PROPERTY Person.name STRING")
    db.command("sql", "CREATE PROPERTY Person.age INTEGER")

    # Data operations require explicit transactions
    with db.transaction():
        db.command("sql", "INSERT INTO Person SET name = 'Alice', age = 30")

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

Example 23 (`examples/23_server_mode_http_access.py`) is a runnable version of
this: it writes through embedded access and reads the same rows back over HTTP,
then writes over HTTP and reads back embedded.

## Cost of each access path

Embedded access is faster than HTTP for the obvious reason: no socket, no JSON
encode/decode, no auth check per call. How much faster depends entirely on your
payload shape and result size, so this guide deliberately does not print a
ratio — measure your own workload.

What is worth knowing structurally:

| Aspect | Embedded / server-managed | HTTP API |
|---|---|---|
| Transport | In-JVM call | TCP + HTTP + JSON |
| Result materialization | Python objects from JVM refs | Parse a JSON body |
| Transaction scope | Any block you want (`with db.transaction():`) | One request, unless you use the transactional endpoints |
| Reach | Owning process only | Any process, any language, optionally remote |
| First-call cost | JVM start (once) | Server warmup, ~5.6 s measured (once) |

For a measured, reproducible comparison of Python-side call overhead in the
embedded path, see `benchmarks/jpype_overhead/REPORT.md` in the repository.

## When to Use Each

### Use Embedded Mode When:

- Single Python process application
- Maximum performance required
- Local SQL/OpenCypher workflows
- Batch processing
- Local development/testing

### Use HTTP API When:

- Multi-process architecture
- Remote database access
- Web applications/APIs
- Multiple programming languages
- Microservices architecture
- Cross-network access
- You want Studio on live data

### Use Hybrid Access When:

- Local high-performance operations + remote monitoring
- Hybrid applications with embedded + web components
- Development (embedded) + production monitoring (HTTP API)

### Use the official ArcadeDB server distribution when:

In-process server mode ties the server's lifetime to your Python process. When
that is wrong for you, run the standalone server instead:

```bash
docker run -d --name arcadedb -p 2480:2480 -p 2424:2424 \
  -e JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
  arcadedata/arcadedb:latest
```

Choose it when you need a server that outlives any one client, HA/replication,
TLS termination, or the other wire protocols (Postgres, Redis, Mongo, Gremlin).
To move data across, use [`export_database`](api/database.md) / SQL
`IMPORT DATABASE` — the on-disk format and export archives are compatible.

## Common Misconceptions

- ❌ **"Embedded mode is only for Java"**
    - ✅ Embedded mode is Python calling Java via JPype (fully Pythonic)
- ❌ **"Embedded means no SQL"**
    - ✅ Full SQL, OpenCypher, vector search, and graph algorithms run in-process
- ❌ **"HTTP API is inferior"**
    - ✅ HTTP API enables remote access (different purpose)
- ❌ **"Must choose one or the other"**
    - ✅ Both can be used simultaneously on the same server
- ❌ **"Performance difference means HTTP is broken"**
    - ✅ Performance difference is expected (network vs direct calls)
- ❌ **"I need a separate server to use Studio on my embedded data"**
    - ✅ `create_server()` serves Studio from the same process that holds the database
