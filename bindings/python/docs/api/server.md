# Server API

The `ArcadeDBServer` class enables HTTP API access and the Studio web interface for managing and querying ArcadeDB databases. Perfect for interactive exploration, debugging, and web applications.

## Overview

The server provides:

- **HTTP REST API**: Query databases via HTTP endpoints
- **Studio Web UI**: Visual database exploration and query editor
- **Multi-database Management**: Create and access multiple databases
- **Remote Access**: Access from other applications via HTTP

For when to choose server mode over embedded mode, see the [Server Mode guide](../guide/server.md#when-to-use-each-mode).

## Module Function

### `create_server(root_path="./databases", root_password=None, config=None)`

Create an ArcadeDB server instance.

**Parameters:**

- `root_path` (str): Root directory for databases (default: `"./databases"`)
    - All databases will be created under this directory
    - Automatically created if it doesn't exist
- `root_password` (Optional[str]): Root user password (default: `None`)
    - **Strongly recommended for production**
    - At least 8 characters
    - If `None` on a fresh `root_path` (no root user stored yet), `start()`
      prompts for the root password on stdin, which blocks a script or service.
      There is no default password.
- `config` (Optional[Dict[str, Any]]): Configuration dictionary (default: `None`)
    - `http_port` (int): HTTP API port (default: 2480)
    - `host` (str): Host to bind to (default: "localhost"). Pass "0.0.0.0" explicitly to expose the server on all IPv4 interfaces, or "::" for all IPv6 interfaces.
    - `mode` (str): Server mode: "development", "test", or "production" (default: "development"). See [Mode Comparison](#mode-comparison)
    - Additional ArcadeDB configuration keys (see Advanced Configuration)

**Returns:**

- `ArcadeDBServer`: Server instance (not started)

**Example:**

```python
import arcadedb_embedded as arcadedb

# Basic server (development)
server = arcadedb.create_server(root_password="password123")

# Custom root path and password
server = arcadedb.create_server(
    root_path="./my_databases",
    root_password="my_secure_password123"
)

# Custom configuration
server = arcadedb.create_server(
    root_path="./dbs",
    root_password="secret123",
    config={
        "http_port": 8080,
        "host": "127.0.0.1",
        "mode": "production"
    }
)
```

---

## ArcadeDBServer Class

### Constructor

```python
ArcadeDBServer(
    root_path: str = "./databases",
    root_password: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    jvm_kwargs: Optional[dict] = None,
)
```

**Prefer using `create_server()` function instead**, unless you need `jvm_kwargs`.

**Parameters:**

- `root_path`, `root_password`, `config`: As for `create_server()`, with one
  difference: the constructor uses `root_path` as given, while `create_server()` first
  makes it absolute.
- `jvm_kwargs` (Optional[dict]): Keyword arguments for `start_jvm()`, for example
  `{"heap_size": "8g"}`. `create_server()` has no such parameter, so this is the way to
  pass JVM options when the server is the first thing to start the JVM. Once the JVM is
  running, options that differ from the ones it started with raise `ArcadeDBError`.

---

### `start()`

Start the ArcadeDB server and begin listening for connections.

**Raises:**

- `ArcadeDBError`: If server is already started or fails to start

**Example:**

```python
import arcadedb_embedded as arcadedb

server = arcadedb.create_server(root_password="password123")
server.start()

print(f"Server running at: {server.get_studio_url()}")

# ... do work ...

server.stop()
```

---

### `stop()`

Stop the ArcadeDB server and release resources.

**Note:** It's safe to call even if server isn't started.

**Example:**

```python
server = arcadedb.create_server(root_password="password123")
server.start()

try:
    # Do work
    pass
finally:
    server.stop()  # Always stop to clean up
```

---

### `is_started() -> bool`

Check if the server is currently running.

**Returns:**

- `bool`: `True` if server is running, `False` otherwise

**Example:**

```python
server = arcadedb.create_server(root_password="password123")
print(server.is_started())  # False

server.start()
print(server.is_started())  # True

server.stop()
print(server.is_started())  # False
```

---

### `get_database(name: str) -> Database`

Get an existing database from the server.

**Parameters:**

- `name` (str): Database name

**Returns:**

- `Database`: Database instance

**Raises:**

- `ArcadeDBError`: If server not started or database doesn't exist

**Example:**

```python
server = arcadedb.create_server(root_password="password123")
server.start()

# Get existing database
db = server.get_database("mydb")

# Use database
result = db.query("sql", "SELECT FROM Person")
for record in result:
    print(record.to_dict())

db.close()
server.stop()
```

---

### `create_database(name: str) -> Database`

Create a new database on the server.

**Parameters:**

- `name` (str): Database name
    - Alphanumeric and underscores recommended
    - Will be created under `root_path/databases/{name}/`

**Returns:**

- `Database`: New database instance

**Raises:**

- `ArcadeDBError`: If server not started or creation fails

**Example:**

```python
server = arcadedb.create_server(root_password="password123")
server.start()

# Create new database
db = server.create_database("products_db")

# Create schema
db.command("sql", "CREATE DOCUMENT TYPE Product")
db.command("sql", "CREATE PROPERTY Product.name STRING")
db.command("sql", "CREATE PROPERTY Product.price DECIMAL")

db.close()
server.stop()
```

**Important:** This method properly registers the database with the server, making it immediately visible in Studio UI.

---

### `get_http_port() -> int`

Get the HTTP port the server is listening on.

**Returns:**

- `int`: HTTP port number

**Example:**

```python
server = arcadedb.create_server(config={"http_port": 8080})
print(server.get_http_port())  # 8080
```

---

### `get_studio_url() -> str`

Get the full URL for the Studio web interface.

**Returns:**

- `str`: Studio URL (e.g., `"http://localhost:2480/"`)

**Example:**

```python
server = arcadedb.create_server(root_password="password123")
server.start()

print(f"Open Studio at: {server.get_studio_url()}")
# Open Studio at: http://localhost:2480/
```

---

### Context Manager Support

The server supports Python context managers for automatic start/stop:

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_server(root_password="password123") as server:
    # Server automatically started
    db = server.create_database("temp_db")
    db.command("sql", "CREATE DOCUMENT TYPE Test")

    # Use database
    with db.transaction():
        db.command("sql", "INSERT INTO Test SET value = ?", 42)

    db.close()

# Server automatically stopped when exiting 'with' block
```

---

## Configuration Options

### Basic Configuration

```python
config = {
    "http_port": 2480,           # HTTP API port
    "host": "localhost",         # Bind address (default loopback; "0.0.0.0" = all IPv4 interfaces)
    "mode": "development",       # "development", "test", or "production"
}

server = arcadedb.create_server(config=config)
```

### Mode Comparison

| Behaviour | `"development"` | `"test"` | `"production"` |
|-----------|-----------------|----------|----------------|
| Studio web UI | Served | Served | Not served, unless `"studio_enabled": True` (`arcadedb.studio.enabled`) |
| `detail` (cause chain) in HTTP error bodies | Included | Included | Omitted |
| Log level for user-triggered request errors | INFO | FINE | FINE |
| Log level for internal faults | SEVERE | WARNING | WARNING |
| WAL flush default (`arcadedb.txWalFlush`) | Unchanged | Unchanged | Set to 1 at start unless set explicitly |
| OpenCypher `LOAD CSV` from `file:` URLs (`arcadedb.opencypher.loadCsv.allowFileUrls`) | Unchanged | Unchanged | Disabled at start unless set explicitly |

The two production defaults are set on the process-wide configuration, so a database
the same Python process opens afterwards inherits them too. Production mode also logs a
checklist of settings at startup. A server in production mode serves no Studio page, so
`get_studio_url()` points at nothing there unless Studio is re-enabled.

**Recommendation:** Use `"development"` for local dev, `"production"` for deployment.

---

### Advanced Configuration

You can pass any ArcadeDB configuration via the `config` dict:

```python
config = {
    "http_port": 8080,
    "mode": "production",
    # Additional ArcadeDB settings (with _ instead of ., camelCase kept)
    "server_databaseDirectory": "./custom_dbs",
    "server_httpSessionExpireTimeout": 30,  # seconds
}

server = arcadedb.create_server(config=config)
```

**Note:** Python uses underscores (`_`), which are automatically converted to dots (`.`) for Java config keys. Keep the camelCase of the Java name:

- `server_httpSessionExpireTimeout` → `arcadedb.server.httpSessionExpireTimeout`

A key that names no ArcadeDB setting is stored and ignored without an error.

---

## Logging Configuration

ArcadeDB writes logs to multiple locations:

### 1. Application Logs

**Location:** `./log/arcadedb.log.*` (relative to working directory)

**Content:** Server startup, database operations, errors

**Cannot be changed** (hardcoded in Java)

### 2. Server Event Logs

**Location:** `{root_path}/log/server-event-log-*.jsonl`

**Content:** HTTP requests, connections, events

**Example:** `./databases/log/server-event-log-20240115-093000.0.jsonl`
(`server-event-log-YYYYMMDD-HHMMSS.N.jsonl`)

### 3. JVM Crash Logs

**Location:** `./log/hs_err_pid*.log` (default)

**Customize BEFORE the JVM starts:**

```python
import os

# Set custom crash log location
os.environ["ARCADEDB_JVM_ERROR_FILE"] = "/var/log/arcade/errors.log"

# Now import and use
import arcadedb_embedded as arcadedb

server = arcadedb.create_server(root_password="password123")
# Crash logs will go to /var/log/arcade/errors.log
```

**Important:** Must be set before the first server or database is created.

---

## HTTP API

Once the server is running, databases are reachable over HTTP (`/api/v1/query/{db}`,
`/api/v1/command/{db}`, and the other endpoints), with the `root` user and the password
given to `create_server()`. Server HTTP commands are auto-transactional per request. The
[Server Mode guide](../guide/server.md) covers authentication tokens, multi-request
transactions, database commands, and bulk loading over HTTP.

---

## Error Handling

```python
from arcadedb_embedded import ArcadeDBError

try:
    server = arcadedb.create_server(root_password="password123")
    server.start()

    # May fail if database doesn't exist
    db = server.get_database("nonexistent")

except ArcadeDBError as e:
    print(f"Error: {e}")
finally:
    if server.is_started():
        server.stop()
```

**Common Errors:**

- **Port already in use**: Another process using port 2480
    - Solution: Change `http_port` in config or stop conflicting process
- **Permission denied**: Cannot write to `root_path`
    - Solution: Check directory permissions
- **Database not found**: `get_database()` on non-existent DB
    - Solution: Use `create_database()` first

---

## See Also

- [Server Mode Guide](../guide/server.md) - Comprehensive server usage guide
- [Database API](database.md) - Database operations
- [Getting Started](../index.md) - Quick start tutorial
