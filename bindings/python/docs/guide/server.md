# Server Mode

ArcadeDB Python bindings include a full HTTP server with the Studio web UI. This guide covers server setup, configuration, and management.

## What it costs you

Server mode is bundled by default. It was briefly removed in 26.7.2 to slim
the wheel and restored after that broke downstream users, so the trade is
worth stating precisely rather than leaving you to guess.

**Disk.** The server stack is 12 JARs, measured against the 26.8.1 line:

| JAR | MB (uncompressed) | contains |
|---|---|---|
| `arcadedb-studio` | 2.60 | web UI assets, **no** `.class` files |
| `undertow-core` | 2.21 | HTTP server, 1,507 classes |
| `micrometer-core` | 0.87 | metrics, required at server startup |
| `arcadedb-server` | 0.66 | the server itself, 255 classes |
| `xnio-api` | 0.56 | undertow's IO layer |
| `wildfly-common` | 0.27 | |
| `jboss-threads` | 0.13 | |
| `xnio-nio` | 0.11 | |
| `micrometer-observation` | 0.08 | |
| `jboss-logging` | 0.06 | |
| `micrometer-commons` | 0.05 | |
| `wildfly-client-config` | 0.05 | |
| **total** | **7.65** | |

**The wheel grows by more than that sum, and it is worth knowing why.** Measured
on one machine, same commit, same platform, server excluded then included. The
jars and JRE columns are sizes *as stored in the wheel* (deflated), which is why
they add up to the wheel column:

| | wheel file | jars (in wheel) | bundled JRE (in wheel) |
|---|---|---|---|
| embedded only | 59.06 MiB | 20.70 MiB | 38.30 MiB |
| with server | **67.08 MiB** | 27.87 MiB | 39.10 MiB |
| delta | **+8.02 MiB (+13.6%)** | +7.17 MiB | +0.80 MiB |

Unpacked on disk the whole package is 94.45 MiB (31.28 MiB of jars across 63
files, 62.92 MiB of JRE).

The extra ~0.8 MiB beyond the JARs is the **bundled JRE**, not the JARs. The
build runs `jdeps` over the shipped JARs and `jlink`s a minimal runtime from
whatever modules it finds, so adding the server stack pulls in modules nothing
else needed. Comparing the two builds' module lists, exactly three are new:

```
embedded only  java.base java.compiler java.desktop java.net.http java.sql
               jdk.incubator.vector jdk.jfr jdk.management jdk.unsupported
with server    ... the same, plus java.naming, java.security.jgss,
               java.security.sasl
```

which are JNDI and the Kerberos/SASL authentication stack that Undertow needs.
The linked JRE goes from 62 MB to 63 MB on disk. Estimating this feature's
cost from JAR sizes alone understates it by roughly 10%.

**Memory and CPU, if you never call `create_server()`: about 10 ms, once.**
The JARs sit on the classpath and the JVM loads classes lazily, so nothing is
initialised, no threads start, and no heap is allocated for them. What you do
pay is a slightly longer classpath for the JVM to open at startup.

Measured by installing one wheel twice and deleting only the 12 server JARs
from one copy, so the engine and every other variable is identical. 16 fresh
processes per arm, interleaved, median [min-max] on one developer machine:

| | 51 JARs | 63 JARs | delta |
|---|---|---|---|
| JVM start | 0.131 s [0.128-0.136] | 0.141 s [0.135-0.151] | **+9.8 ms** |
| first database open + query | 0.343 s [0.329-0.385] | 0.335 s [0.322-0.382] | -8.7 ms |
| peak RSS | 216.9 MB | 201.2 MB | -15.7 MB |

Only the JVM-start row is a real effect; its ranges barely overlap. The other
two deltas are negative and their ranges overlap heavily, which is measurement
noise rather than a saving. So there is **no measurable memory cost** to
carrying the server JARs, and about 10 ms of one-time startup.

**If you do start a server**, `undertow-core` and `arcadedb-server` load and
Undertow starts listener threads and buffer pools. That is the real cost, and
it arrives when you ask for it.

**Studio specifically is free until browsed.** Its JAR contains 126 entries,
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

There is no `binary_port`. It was listed here and in the docstring until
2026-08-01 and was silently discarded: ArcadeDB has no such setting. Its ports
are `httpIncomingPort`, `httpsIncomingPort` and the per-protocol ones below.
2424 is OrientDB's legacy binary port and never applied to this engine.

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

**`redis_port` is honoured.** On 26.8.1 it was accepted and ignored: the
Redis listener bound the hardcoded 6379 while Postgres and Bolt bound what they
were given. Root-caused and filed as [ArcadeDB #5796][5796] (the Redis plugin
dropped the server's `ContextConfiguration` and read the static
`GlobalConfiguration` default), fixed upstream on 2026-08-07.
`tests/test_server_wire_protocols.py` checks that Redis binds the port it is
given.

[5796]: https://github.com/ArcadeData/arcadedb/issues/5796

**Redis now requires authentication, as of 26.8.1.** Earlier versions accepted
unauthenticated connections on the Redis port. A client that used to connect
anonymously must now present credentials, so enabling this plugin is a
breaking change for anything already talking to it. `arcadedb.redis.tls` is
new in the same release if you want the transport encrypted.

**The wire listeners bind all interfaces by default.** `host` tightens the HTTP
listener to loopback by default, but it does not reach the protocol plugins:
each one has its own host setting, and each defaults to `0.0.0.0`. Pass
`postgres_host`, `bolt_host`, or `redis_host` (for example `"127.0.0.1"`) to
bind a plugin to one interface. Without them, enabling a plugin on a
multi-homed or internet-facing machine exposes it beyond localhost.

### Arrow (ADBC) clients over the Postgres wire

From **26.10.1**, Arrow's native PostgreSQL ADBC driver
(`adbc-driver-postgresql`, measured with 1.12.0) connects to a server started
from this wheel with the Postgres plugin, and `fetch_arrow_table()` returns
Arrow tables directly. On **26.9.1 it cannot connect**: the driver's type
bootstrap fails with "Expected 5 or 6 columns from type resolver pg_type query
but got 0" (ArcadeDB [#7178][7178], fixed for 26.10.1).

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
Development builds before 2026-09-24 described computed columns as `varchar`
before execution, so the driver returned them as strings (`'3'`, not `3`), and
pgjdbc's `PreparedStatement` returned them as `String`; fixed for 26.10.1
(ArcadeDB [#8285][8285]).

**Bound parameters are served from indexes.** Postgres-wire clients send a
bound value as `$1`; from 26.10.1 an equality on an indexed property with a
`$1` uses the index, where earlier builds scanned the whole type (ArcadeDB
[#8288][8288]). pgjdbc also works at its default `prepareThreshold` from
26.10.1; earlier builds failed a prepared statement's sixth execution
(ArcadeDB [#8244][8244]).

Measured on a laptop against the 26.10.1 development wheel (engine
`3440a871a9`); `tests/test_server_wire_protocols.py` connects with the driver,
checks the typed columns, values, a bound parameter, and a computed column's
type, so the test fails the day any of it changes.

The other ADBC route, adbcBridge over the psqlodbc driver, is described in
ArcadeDB's announcement and was not measured here.

[7178]: https://github.com/ArcadeData/arcadedb/issues/7178
[8285]: https://github.com/ArcadeData/arcadedb/issues/8285
[8288]: https://github.com/ArcadeData/arcadedb/issues/8288
[8244]: https://github.com/ArcadeData/arcadedb/issues/8244

### Not bundled

Mongo wire, gRPC, and Raft replication are excluded from the wheel to keep it
installable: the shaded gRPC jar alone is 38 MB against 39 MB for the entire
engine payload, and the Raft jar is 80 MB. **This server is single-node by
construction** — it cannot replicate or fail over. Use the Docker distribution
for HA, gRPC, or Mongo-protocol access.

## Server Info Endpoint

The server exposes `/api/v1/server` for metadata such as version, server name,
and supported query languages:

```python
import requests
from requests.auth import HTTPBasicAuth

base_url = f"http://localhost:{server.get_http_port()}"
auth = HTTPBasicAuth("root", "password123")

info = requests.get(f"{base_url}/api/v1/server", auth=auth).json()
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
    f"{base_url}/api/v1/command/mydb",
    headers=headers,
    json={"language": "sql", "command": "SELECT FROM Person"},
)
```

## Transactions, Database Commands and Time-Series Writes over HTTP

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
`drop database`, `open database` and `close database`. Closing a database
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
- **Vertices and edges:** `POST /api/v1/batch?wal=true` (see
  [Graphs](graphs.md)).
- **Batch size:** 2,000 rows is reasonable; 5,000 to 10,000 can amortize a
  little more for small rows, 2,000 to 5,000 for vector rows. The curve is flat,
  so try 2k, 5k and 10k on your hardware and keep the best.
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
db1 = arcadedb.create_database("./mydb")  # Gets file lock

# Process 2 (different Python process)
db2 = arcadedb.create_database("./mydb")  # ❌ ERROR: Lock conflict!
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
| Production deployment | Server | Central auth, HTTP, remote access |

### Multi-Threaded Access

Within a **single Python process**, multiple threads can safely share an embedded database:

```python
import arcadedb_embedded as arcadedb
from threading import Thread

# Use context manager so the database closes cleanly after threads finish
with arcadedb.create_database("./mydb") as db:
    db.command("sql", "CREATE DOCUMENT TYPE Log")

    def worker(thread_id):
        # ✅ Multiple threads in SAME process can share the database
        with db.transaction():
            db.command("sql", "INSERT INTO Log SET thread = ?", thread_id)

    # Start multiple threads, and join them before the block closes the database
    threads = [Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
```

For more details, see [Concurrency Tests](../development/testing/test-concurrency.md).

## Next Steps

- **[Graph Operations](graphs.md)**: Visualize graphs in Studio
- **[Vector Search](vectors.md)**: Add vector search to your server
- **[Data Import](import.md)**: Bulk import data into server databases
