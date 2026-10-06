# Server Mode

ArcadeDB Python bindings include a full HTTP server with the Studio web UI. This guide covers server setup, configuration, and management.

## What it costs you

Server mode is bundled by default.

**Disk.** The server stack is these JARs, measured on the 26.10.1 wheel from PyPI;
the package sizes are in
[Installation](../getting-started/installation.md#whats-included):

| JAR | MB (uncompressed) | contains |
|---|---|---|
| `arcadedb-studio` | 2.88 | web UI assets, **no** `.class` files |
| `undertow-core` | 2.33 | HTTP server, 1,510 classes |
| `arcadedb-server` | 1.09 | the server itself, 373 classes |
| `micrometer-core` | 0.92 | metrics, required at server startup |
| `xnio-api` | 0.59 | undertow's IO layer |
| `wildfly-common` | 0.28 | |
| `jboss-threads` | 0.13 | |
| `xnio-nio` | 0.11 | |
| `micrometer-observation` | 0.08 | |
| `jboss-logging` | 0.06 | |
| `micrometer-commons` | 0.05 | |
| `wildfly-client-config` | 0.05 | |
| **total** | **8.58** | |

**Memory and CPU, if you never call `create_server()`.** The JARs sit on the
classpath and the JVM loads classes lazily, so nothing is initialised, no
threads start, and no heap is allocated for them.

**If you do start a server**, `undertow-core` and `arcadedb-server` load and
Undertow starts listener threads and buffer pools. That is the real cost, and
it arrives when you ask for it.

**Studio specifically is free until browsed.** Its JAR contains 120 entries,
all static JS/HTML/CSS/SVG/PNG, and **zero** `.class` files: it cannot execute
anything. Assets are read out of the zip only when a browser requests them.
(`tests/test_server_packaging.py` asserts this, so the claim fails loudly if a
future Studio release starts shipping code.)

### When to use the Docker distribution instead

Use the official ArcadeDB server image, not this, when you need multi-process
access, HA/replication, TLS termination, or a server whose lifetime is
independent of your Python process. In-process server mode is for the case
where one process wants both embedded access and an HTTP surface.

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
server = arcadedb.create_server("./databases", root_password="my_secure_password")
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
with arcadedb.create_server("./databases", root_password="my_secure_password") as server:
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
| `root_password` | None | Root user password (recommended). `None` on a fresh `root_path` makes `start()` prompt for it on stdin |
| `http_port` | 2480 | HTTP API/Studio port (binding pins to a single port; Java default is the 2480-2489 range) |
| `host` | "localhost" | Host to bind to |
| `mode` | "development" | Server mode (`development` or `production`). `production` also flushes the WAL at every commit (`arcadedb.txWalFlush=1`, unless you set it yourself), serves no Studio, and refuses LOAD CSV file URLs; see [Durability](core/transactions.md#durability-what-a-commit-survives) |

Any other key is forwarded to ArcadeDB as `arcadedb.<key with _ replaced by
.>`. That is how the wire protocols below are configured.

### Sizing the server's JVM

The server runs in the JVM of your Python process, so its heap and JVM flags are the
process's, and they are fixed when the JVM starts. `create_server()` takes no
`jvm_kwargs`: call `start_jvm(...)` before it, or construct the server with
`ArcadeDBServer(root_path, root_password, config, jvm_kwargs={...})`. Either has to
come before the first database or server in the process starts the JVM (see the
[JVM API](../api/jvm.md)).

```python
import arcadedb_embedded as arcadedb
from arcadedb_embedded.jvm import start_jvm

start_jvm(heap_size="8g")
server = arcadedb.create_server("./databases", root_password="my_secure_password")
```

### Serving a database you created in embedded mode

A server finds its databases in `<root_path>/databases/`. To serve one you created with
`create_database()`, close it first, because an open database holds the file lock. Then move
its directory into `<root_path>/databases/`, start the server, and open the database with
`server.get_database(name)`. Without the `close()` the server cannot open it
(`tests/test_server_patterns.py::test_pattern1_embedded_first_requires_close`). The shorter
route is `server.create_database(name)` on a started server, which registers the database
with the server from the start (see [Access Methods](../api-access-methods.md)).

## Wire Protocols

The wheel bundles three protocol plugins besides HTTP. They are **opt-in**: a
default server starts HTTP and Studio only, and 5432/6379/7687 stay closed.

```python
server = arcadedb.create_server(
    root_path="./databases",
    root_password="my_secure_password",
    config={
        "http_port": 2480,
        "server_plugins": (
            "Postgres:com.arcadedb.postgres.PostgresProtocolPlugin,"
            "Redis:com.arcadedb.redis.RedisProtocolPlugin,"
            "Bolt:com.arcadedb.bolt.BoltProtocolPlugin"
        ),
        "postgres_port": 5432,   # -> arcadedb.postgres.port
        "bolt_port": 7687,       # -> arcadedb.bolt.port
    },
)
```

| Protocol | Plugin class | Port setting | Verified |
|---|---|---|---|
| Postgres wire | `com.arcadedb.postgres.PostgresProtocolPlugin` | `postgres_port` | yes, connect + query |
| Bolt (Neo4j drivers) | `com.arcadedb.bolt.BoltProtocolPlugin` | `bolt_port` | yes, connect + Cypher |
| Redis | `com.arcadedb.redis.RedisProtocolPlugin` | `redis_port` | yes, binds the given port |

`tests/test_server_wire_protocols.py` speaks Postgres and Bolt with their real
clients (`psycopg`, `neo4j`) and checks that Redis binds its port, so these
rows are measured rather than inferred from the jars being present.

### Two things to know before exposing these

**Redis requires authentication.** A client must present credentials before
anything else; set `arcadedb.redis.tls` (`redis_tls`) to encrypt the transport.

**The wire listeners bind all interfaces by default.** `host` tightens the HTTP
listener to loopback by default, but it does not reach the protocol plugins:
each one has its own host setting, and each defaults to `0.0.0.0`. Pass
`postgres_host`, `bolt_host`, or `redis_host` (for example `"127.0.0.1"`) to
bind a plugin to one interface. Without them, enabling a plugin on a
multi-homed or internet-facing machine exposes it beyond localhost.

### Arrow (ADBC) clients over the Postgres wire

Arrow's native PostgreSQL ADBC driver (`adbc-driver-postgresql`, measured with
1.12.0) connects to a server started from this wheel with the Postgres plugin,
and `fetch_arrow_table()` returns Arrow tables directly.

```python
import adbc_driver_postgresql.dbapi as pg

with pg.connect("postgresql://root:<password>@localhost:5432/mydb") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT n, s, x FROM Typed WHERE n > $1", parameters=(10,))
        table = cur.fetch_arrow_table()   # a pyarrow.Table
```

**Declared properties and computed columns both arrive typed.** A property
declared in the schema (`LONG`, `STRING`, `DOUBLE`, `BOOLEAN`) comes back as
`int64`, `string`, `double`, `bool`, and a computed column as its real type:
`count(*)` and `max(n)` as `int64`, `sum(x)` as `double`, `n * 2` as `int64`.

**Bound parameters are served from indexes.** Postgres-wire clients send a
bound value as `$1`, and an equality on an indexed property with a `$1` uses
the index. pgjdbc works at its default `prepareThreshold`.

`tests/test_server_wire_protocols.py` connects with the driver and checks the
typed columns, their values, a bound parameter, and a computed column's type,
so the test fails the day any of it changes.

The other ADBC route, adbcBridge over the psqlodbc driver, is described in
ArcadeDB's announcement and was not measured here.

### Not bundled

Mongo wire, gRPC, and Raft replication are excluded from the wheel to keep it
installable. **This server is single-node by construction**: it cannot replicate
or fail over. Use the Docker distribution
for HA, gRPC, or Mongo-protocol access.

## Choosing a Protocol from Python

From Python, the client library often costs more than the protocol. ArcadeDB's own
documentation has a section on this, [Python: choosing a protocol](https://docs.arcadedb.com/arcadedb/how-to/connectivity/drivers/python-http#python-choosing-protocol),
and the advice below agrees with it and adds what we measured.

**One-row reads and writes (a point lookup, an update by key).**

1. **The Postgres wire** is the fastest single-row route. With `psycopg`, prefix an
   openCypher statement with `{cypher}`, or send SQL as is. Bind values with `%s`;
   psycopg sends them to the server as `$1`, `$2`. It needs the Postgres plugin (see
   [Wire Protocols](#wire-protocols)) and it is the one route in the table below
   that beats a hand-written HTTP client.
2. **HTTP over one persistent connection** comes next. Open the connection once and
   reuse it, with a login token if you like (see
   [Authentication Tokens](#authentication-tokens-http-api)). `requests.Session` is
   convenient but adds client time on every call.
3. **The official Python clients** are `arcadedb-driver` (HTTP, built on `httpx`) and
   `arcadedb-driver-grpc`. They run every statement shown in this guide and are the
   easiest way to get typed errors and transactions, but they add client work to
   every call. `arcadedb-driver-grpc` needs the gRPC plugin, which this wheel does
   not bundle (see [Not bundled](#not-bundled)), so it talks to the official server
   distribution only.
4. **Bolt through the `neo4j` driver** is for tooling that already speaks Bolt. On
   one-row reads it is slower than a persistent HTTP connection.

Measured on one laptop, one client thread, loopback, ArcadeDB 26.10.1, Python 3.14. These
are relative numbers (median call time as a multiple of one persistent `http.client`
connection, lower is faster), meant to rank the routes and not to predict your
latency:

| Route | One-row SQL read | One-row Cypher read | 100-row read (SQL / Cypher) |
|---|---|---|---|
| Postgres wire, `psycopg` | 0.45x | 0.48x | 0.57x / 0.69x |
| HTTP, one persistent connection (`http.client`) | 1x | 1x | 1x |
| `arcadedb-driver-grpc` | 1.2x | 1.3x | 1.8x / 2.2x |
| `neo4j` driver over Bolt | Cypher only | 1.6x | 7.1x on Cypher |
| `arcadedb-driver` (HTTP) | 3.2x | 3.4x | 2.0x / 2.3x |
| `requests.Session` | 4.0x | 4.1x | 2.1x / 2.3x |

Most of the difference is client code, not the server. A one-row call through
`arcadedb-driver` runs about 2,000 Python calls, against about 500 for a plain
`http.client` request, and the `neo4j` driver spends about 80 percent of its time in the
client process. The gRPC rows were measured against a JDK 25 server; on JDK 21 the same
one-row read was about 1.65x. Treat a difference under about 1.3x as a tie, and measure
your own workload before you change a client for these numbers.

**Large results (thousands of rows or more).** Prefer HTTP. Over Bolt the Python
driver spends about 5 microseconds of Python per record and fetches 1,000 records per
round trip by default; upstream measured it 4x to 10x slower than HTTP on large results and
advises raising `fetch_size` (for example `driver.session(fetch_size=-1)`). That advice
was measured on ArcadeDB 26.11.1, which batches Bolt records. On the 26.10.1 server in
this wheel a 10,000-row result did not get faster with it when we tried.

gRPC streaming with a batch size of 10,000 or more was the fastest route in upstream's
measurement of results of hundreds of thousands of rows. At the default batch size it
was slower than HTTP in ours (a 10,000-row Cypher read took about 3.3x as long, on a
26.11.1 pre-release build), so set the batch size explicitly and measure. When your code
runs in the same process as the database (embedded mode), skip the socket and read a
large result with [`to_arrow()`, `to_columns()`, or `to_json_list()`](../api/results.md).

**Bulk loads** go through HTTP: `INSERT INTO T CONTENT :rows` for documents, `/api/v1/batch`
for vertices and edges (see [Bulk Loading over the Server](#bulk-loading-over-the-server)).
The Postgres wire is the exception for rows that carry a vector. The official gRPC
client's `insert_stream` was no faster than HTTP loads in our measurement.

Reuse the connection on every route: opening a new one for each call costs more than
the choice of protocol.

## Server Info Endpoint

The server exposes `/api/v1/server` for metadata such as version, server name,
and supported query languages. Add `?mode=basic` when that is all you need: the
full form also computes a metrics section. To wait for
a server to come up, poll `/api/v1/ready`, which answers 204 without
authentication once the server accepts requests:

```python
import requests
from requests.auth import HTTPBasicAuth

base_url = f"http://localhost:{server.get_http_port()}"
auth = HTTPBasicAuth("root", "password123")

requests.get(f"{base_url}/api/v1/ready").raise_for_status()  # 204 once it is up
info = requests.get(f"{base_url}/api/v1/server?mode=basic", auth=auth).json()
print("Server version:", info.get("version"))
print("Languages:", info.get("languages"))
```

## Authentication Tokens (HTTP API)

If you make many HTTP requests, you can obtain a token once and use Bearer
authentication afterward:

```python
import requests
from requests.auth import HTTPBasicAuth

base_url = f"http://localhost:{server.get_http_port()}"
auth = HTTPBasicAuth("root", "password123")

# Exchange Basic Auth for a token
token = requests.post(f"{base_url}/api/v1/login", auth=auth).json()["token"]

# Use Bearer token in subsequent requests
headers = {"Authorization": f"Bearer {token}"}
requests.post(
    f"{base_url}/api/v1/query/mydb",
    headers=headers,
    json={"language": "sql", "command": "SELECT FROM Person"},
)
```

## Transactions, Database Commands, and Time-Series Writes over HTTP

Three server features the bindings do not wrap, because they are the server's
HTTP API rather than the embedded API. They matter as soon as a second process
talks to the server you started with `create_server()`.

### One transaction across several requests

`POST /api/v1/begin/{db}` opens a server-side transaction and returns its id in
the `arcadedb-session-id` response header. Send that header on every command
that belongs to the transaction, then `POST /api/v1/commit/{db}` or
`POST /api/v1/rollback/{db}` with the same header. Without the header each
command is its own transaction.

```python
import requests
from requests.auth import HTTPBasicAuth

base_url = f"http://localhost:{server.get_http_port()}"
s = requests.Session()
s.auth = HTTPBasicAuth("root", "password123")

r = s.post(f"{base_url}/api/v1/begin/mydb")
sid = r.headers["arcadedb-session-id"]
headers = {"arcadedb-session-id": sid}
s.post(f"{base_url}/api/v1/command/mydb", headers=headers,
       json={"language": "sql", "command": "INSERT INTO Person SET name = 'a'"})
s.post(f"{base_url}/api/v1/command/mydb", headers=headers,
       json={"language": "sql", "command": "INSERT INTO Person SET name = 'b'"})
s.post(f"{base_url}/api/v1/commit/mydb", headers=headers)   # or /rollback/mydb
```

A session that is never committed is discarded when it times out, so a client
that dies mid-operation leaves nothing half-written.

### Database commands

`POST /api/v1/server` takes server-level commands as JSON: `create database`,
`drop database`, `open database`, and `close database`. Closing a database
releases its files and page cache on the server; opening it again reads them
back, which is the served equivalent of closing and reopening an embedded
database.

```python
s.post(f"{base_url}/api/v1/server", json={"command": "create database mydb"})
s.post(f"{base_url}/api/v1/server", json={"command": "close database mydb"})
s.post(f"{base_url}/api/v1/server", json={"command": "open database mydb"})
```

### Time-series writes with line protocol

A `TIMESERIES` type accepts writes through `POST /api/v1/ts/{db}/write`, one
InfluxDB line-protocol sample per line, with `?precision=ns|us|ms|s` naming the
timestamp unit. The measurement name is the type name; tags and fields map to
the type's declared tags and fields.

```python
s.post(f"{base_url}/api/v1/command/mydb", json={
    "language": "sql",
    "command": "CREATE TIMESERIES TYPE Reading TIMESTAMP ts "
               "TAGS (sensor STRING) FIELDS (value DOUBLE)"})
body = "\n".join(f"Reading,sensor=s1 value={v} {1700000000 + i}"
                 for i, v in enumerate([1.0, 2.0, 3.0]))
s.post(f"{base_url}/api/v1/ts/mydb/write?precision=s",
       data=body.encode(), headers={"Content-Type": "text/plain"})
rows = s.post(f"{base_url}/api/v1/query/mydb", json={
    "language": "sql", "command": "SELECT count(*) AS n FROM Reading"}).json()["result"]
```

In-process, the same type is fed with `db.async_executor().append_samples(...)`
(see [Time Series End to End](../examples/17_timeseries_end_to_end.md)), which
skips the parse and the socket; the HTTP path is what any client without the
wheel gets.

After a bulk write, `COMPACT TIMESERIES TYPE Reading` through `/api/v1/command` seals the
samples still in the mutable tail and returns `mutableSamples` (0 once everything is
sealed), rather than waiting for the 60-second background pass (26.10.1,
`ArcadeData/arcadedb#8574`). See [`append_samples`](../api/async_executor.md#append_samples).
If the type's main query is an hourly aggregate, create it with `COMPACTION_INTERVAL 1 HOURS`
and leave `SHARDS` at its default (the `CREATE TIMESERIES TYPE` above takes both clauses
after `FIELDS`).

## Bulk Loading over the Server

Which served path loads fastest depends on what the rows carry. Measured on a
laptop on 26.10.1-SNAPSHOT with a lineitem-shaped type, 2,000 rows per request and the
write-ahead log on in every path (`ArcadeData/arcadedb#8337`), in rows per
second:

| Path | Plain rows | Rows with a 96-float vector |
|------|------------|-----------------------------|
| `sqlscript` of `INSERT ... SET` with the values in the text | 13k | 4.8k |
| `INSERT INTO T CONTENT :rows`, the batch bound as one parameter | 21k | 8.3k |
| Postgres wire, prepared `INSERT`, `executeBatch` | 12.6k | 12.1k |
| gRPC `BulkInsert`, official server only (gRPC is not bundled in the wheel) | 20.6k | 7.9k |

Upstream's recommendation, from the same issue:

- **Documents:** `POST /api/v1/command` with `INSERT INTO <Type> CONTENT :rows`
  and the batch bound as a list. The statement is parsed once and the rows
  travel as data, with no quoting to get wrong. gRPC `BulkInsert` is equally
  good if the client already speaks gRPC, on the official server only (gRPC is
  not bundled in the wheel).
- **Rows with a vector property:** the Postgres wire with `float4[]`
  parameters. HTTP and gRPC send each float as its own value, and neither has a
  packed vector encoding yet.
- **Vertices and edges:** `POST /api/v1/batch/{db}?wal=true` (see
  [Graphs](graphs.md)).
- **Batch size:** 2,000 rows is reasonable; 5,000 to 10,000 can amortize a
  little more for small rows, 2,000 to 5,000 for vector rows. The curve is flat,
  so try 2k, 5k, and 10k on your hardware and keep the best.
- **Durability:** all four paths commit through ordinary transactions with the
  WAL on. Only the `GraphBatch`-based loaders (`/api/v1/batch` and gRPC
  `GraphBatchLoad`, official server only) skip it unless you pass `wal=true`.

```python
rows = [{"k": i, "name": f"item-{i}", "x": i * 0.5} for i in range(2000)]
r = requests.post(
    "http://localhost:2480/api/v1/command/mydb",
    auth=("root", password),
    json={"language": "sql", "command": "INSERT INTO Item CONTENT :rows",
          "params": {"rows": rows}},
)
r.raise_for_status()
```

In-process, `db.insert_many(...)` is the equivalent and skips the parse and
the socket.

## Multi-Process Access

ArcadeDB's embedded mode uses file-based locking, which prevents multiple processes from accessing the same database simultaneously. **Server mode solves this problem** by providing a central HTTP endpoint that multiple processes (or applications) can connect to.

### Why Use Server Mode for Multi-Process?

#### ❌ Embedded mode - Only ONE process can access the database

```python
import arcadedb_embedded as arcadedb

# Process 1
db1 = arcadedb.open_database("./mydb")  # Gets file lock

# Process 2 (different Python process)
db2 = arcadedb.open_database("./mydb")  # ❌ ERROR: Lock conflict!
```

#### ✅ Server mode - Multiple processes/apps can access

```python
import arcadedb_embedded as arcadedb

# Start server once (Process 1)
with arcadedb.create_server("./databases", root_password="my_secure_password") as server:
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
| Long-lived production server | Official server distribution | Outlives any one Python process; see [When to use the Docker distribution instead](#when-to-use-the-docker-distribution-instead) |

### Multi-Threaded Access

Within a **single Python process**, multiple threads can share an embedded database.
Concurrent writers conflict: a transaction that loses raises
`ConcurrentModificationException` at commit, and `with db.transaction():` cannot retry
it. Write from threads with `db.run_in_transaction(fn)`, which rolls back and runs `fn`
again on a conflict (12 retries with a linear backoff by default; see
[`run_in_transaction`](../api/database.md#run_in_transaction)):

```python
import arcadedb_embedded as arcadedb
from threading import Thread

# Use context manager so the database closes cleanly after threads finish
with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Log")

    def worker(thread_id):
        # ✅ Multiple threads in SAME process can share the database
        db.run_in_transaction(
            lambda: db.command("sql", "INSERT INTO Log SET thread = ?", thread_id)
        )

    # Start multiple threads, and join them before the block closes the database
    threads = [Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
```

## Next Steps

- **[Graph Operations](graphs.md)**: Visualize graphs in Studio
- **[Vector Search](vectors.md)**: Add vector search to your server
- **[Data Import](import.md)**: Bulk import data into server databases
