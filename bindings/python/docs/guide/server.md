# Server Mode

ArcadeDB Python bindings include a full HTTP server with the Studio web UI. This guide covers server setup, configuration, and management.

## Overview

Server mode provides:

- **HTTP REST API**: Access your database via HTTP
- **Studio Web UI**: Visual database explorer and query editor
- **Multi-database Management**: Host multiple databases
- **Authentication**: User management and security
- **Development & Production**: Suitable for both environments

## Quick Start

### Basic Server

Start a server with default configuration:

```python
import arcadedb_embedded as arcadedb

# Create and start server
server = arcadedb.create_server("./databases")
server.start()

print(f"🚀 Server started at: {server.get_studio_url()}")
print("📊 Access Studio UI in your browser")

# Keep server running
input("Press Enter to stop server...")
server.stop()
```

### Context Manager

Use a context manager for automatic cleanup:

```python
with arcadedb.create_server("./databases") as server:
    print(f"🚀 Server running at: {server.get_studio_url()}")

    # Server automatically stops on exit
    input("Press Enter to stop...")
```

## Server Configuration

### Basic Configuration

```python
server = arcadedb.create_server(
    root_path="./databases",
    root_password="my_secure_password",
    config={
        "http_port": 2480,
        "host": "0.0.0.0",
        "mode": "development"
    }
)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `root_path` | `"./databases"` | Directory for database storage |
| `root_password` | None | Root user password (recommended) |
| `http_port` | 2480 | HTTP API/Studio port (binding pins to a single port; Java default is the 2480-2489 range) |
| `host` | "0.0.0.0" | Host to bind to |
| `mode` | "development" | Server mode (`development` or `production`) |

## Multi-Process Access

ArcadeDB's embedded mode uses file-based locking, which prevents multiple processes from accessing the same database simultaneously. **Server mode solves this problem** by providing a central HTTP endpoint that multiple processes (or applications) can connect to.

### Why Use Server Mode for Multi-Process?

#### ❌ Embedded mode - Only ONE process can access the database

```python
import arcadedb_embedded as arcadedb

# Process 1
db1 = arcadedb.create_database("./mydb")  # Gets file lock

# Process 2 (different Python process)
db2 = arcadedb.create_database("./mydb")  # ❌ ERROR: Lock conflict!
```

#### ✅ Server mode - Multiple processes/apps can access

```python
import arcadedb_embedded as arcadedb

# Start server once (Process 1)
with arcadedb.create_server("./databases") as server:
    print(f"Server at: {server.get_studio_url()}")

    # Now ANY number of clients can connect via HTTP
    # - Web applications
    # - Background workers
    # - Data analysis scripts
    # - Multiple Python processes

    input("Server running... Press Enter to stop")
```

### Benefits of Server Mode

1. **True Multi-Process Access**: Multiple Python processes can work with the same database
2. **Language Agnostic**: Access from JavaScript, Java, Python, curl, etc.
3. **Network Access**: Remote applications can connect
4. **Web UI**: Built-in Studio for visual database exploration
5. **Production Ready**: Proper authentication and security

### When to Use Each Mode

| Use Case | Mode | Reason |
|----------|------|--------|
| Single script/notebook | Embedded | Zero setup; keep everything in-process |
| Agent/AI workloads in one process | Embedded | Fast, low-latency, no network hop |
| Multi-process on one machine | Server | One shared endpoint avoids file locks |
| Web app / API clients | Server | Network access for many clients |
| Distributed workers / pipelines | Server | Parallel workers connect concurrently |
| Production deployment | Server | Central auth, HTTP, remote access |

### Multi-Threaded Access

Within a **single Python process**, multiple threads can safely share an embedded database:

```python
import arcadedb_embedded as arcadedb
from threading import Thread

# Use context manager so the database closes cleanly after threads finish
with arcadedb.create_database("./mydb") as db:
    db.schema.create_document_type("Log")

    def worker(thread_id):
        # ✅ Multiple threads in SAME process can share the database
        with db.transaction():
            rec = db.new_document("Log")
            rec.set("thread", thread_id).save()

# Start multiple threads
threads = [Thread(target=worker, args=(i,)) for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

db.close()
```

For more details, see [Concurrency Tests](../development/testing/test-concurrency.md).

## Next Steps

- **[Graph Operations](graphs.md)**: Visualize graphs in Studio
- **[Vector Search](vectors.md)**: Add vector search to your server
- **[Data Import](import.md)**: Bulk import data into server databases
