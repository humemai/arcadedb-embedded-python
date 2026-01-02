# Example 08: Server Mode, Studio & Concurrent HTTP Clients

This example demonstrates how to run ArcadeDB in **Server Mode**, which enables the HTTP REST API and the Studio Web UI while maintaining embedded Python access. It also showcases **concurrent load testing** and **polyglot querying** (SQL + Gremlin).

[View source code](https://github.com/humemai/arcadedb-embedded-python/blob/main/bindings/python/examples/08_server_mode_rest_api.py){ .md-button }

## Overview

!!! note "Embedded vs Server"
    The `arcadedb-embedded` Python library is primarily designed for **embedded usage** (running the database directly within your Python process for maximum performance). However, as shown in this example, it can also launch the full ArcadeDB server to support external clients (via HTTP/REST) or the Studio UI, effectively acting as a database server managed by Python.

ArcadeDB can run in two modes:

1.  **Embedded (Default)**: Direct JVM access, no network overhead, single process.
2.  **Server Mode**: Starts an HTTP server, enabling remote access and Studio UI.

This example shows how to start the server programmatically, simulate concurrent clients, and execute mixed workloads.

## Key Concepts

### 1. Starting the Server

You can start the server using `arcadedb.create_server()`. This starts the JVM and the embedded Jetty server.

```python
import arcadedb_embedded as arcadedb

# Configure and start server
server = arcadedb.create_server(
    root_path="./my_test_databases",
    root_password="playwithdata",  # Required for root access
    config={
        "http_port": 2480,
        "host": "0.0.0.0"
    }
)

server.start()
```

### 2. Accessing Studio

Once started, the **ArcadeDB Studio** is available at:

`http://localhost:2480`

You can log in with:
- **User**: `root`
- **Password**: `playwithdata`
- **Database**: `stackoverflow_small_db_graph`

### 3. Concurrent Client Simulation

The example uses Python's `concurrent.futures.ThreadPoolExecutor` to simulate multiple clients hitting the server simultaneously via the HTTP API.

```python
def demonstrate_concurrency(db_name, num_clients=6):
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
        futures = []
        for i, query_def in enumerate(WORKLOAD_QUERIES):
            # Distribute queries among simulated clients
            client_id = (i % num_clients) + 1
            futures.append(executor.submit(run_client_query, client_id, db_name, query_def))
```

### 4. Polyglot Workload

The workload consists of a mix of **SQL** and **Gremlin** queries to demonstrate the server's ability to handle different query languages concurrently.

**SQL Example:**
```sql
SELECT DisplayName, out('EARNED').size() as badge_count
FROM User
ORDER BY badge_count DESC LIMIT 1
```

**Gremlin Example:**
```groovy
g.V().hasLabel('User')
 .where(__.out('ASKED').in('HAS_ANSWER').in('ANSWERED'))
 .count()
```

## Running the Example

```bash
cd bindings/python/examples
python 08_server_mode_rest_api.py
```

**Expected Output:**

```text
================================================================================
 Example 08: Server Mode (Database: stackoverflow_small_db_graph)
================================================================================

Starting ArcadeDB Server...
✅ Server running on port 2480

================================================================================
 Demonstrating Concurrent HTTP Clients (Mixed Workload)
================================================================================
Simulating 6 concurrent clients executing 33 SQL and Gremlin queries...

Client 4 [Count Tag vertices]: Success (Count=668) in 0.371s
Client 1 [Count ASKED edges]: Success (Count=47121) in 0.130s
Client 2 [Count Question vertices]: Success (Count=48390) in 0.550s
...
Client 6 [Find users who answered their own questions]: Success (1 rows) in 2.267s

================================================================================
 Interactive Studio Session
================================================================================
The server is running. Open your browser to:
  👉 http://localhost:2480/

Credentials:
  Database: stackoverflow_small_db_graph
  User:     root
  Password: playwithdata

For more information, visit: https://docs.arcadedb.com/

[Press Ctrl+C to stop the server]
```

## When to Use Server Mode?

| Use Case | Embedded Mode | Server Mode |
|----------|---------------|-------------|
| **Single Python Script** | ✅ Best | ❌ Overkill |
| **Data Analysis (Pandas)** | ✅ Best | ❌ Slower |
| **Web App Backend** | ✅ Good | ✅ Good (if need external access) |
| **Debugging / Visualization** | ❌ No UI | ✅ **Studio UI** |
| **Multi-Process Access** | ❌ Locked | ✅ **HTTP API** |
| **Microservices** | ❌ Hard | ✅ **HTTP API** |

## Next Steps

This concludes the example series! You have learned:

1.  **Basics**: Documents, SQL, CRUD
2.  **Graph**: Vertices, Edges, Traversal
3.  **Vector**: Embeddings, Semantic Search
4.  **Import**: CSV, Batching, ETL
5.  **Advanced**: Multi-model, Hybrid Search
6.  **Server**: HTTP API, Studio, Concurrency

Explore the [User Guide](../guide/core/database.md) for more in-depth topics.
