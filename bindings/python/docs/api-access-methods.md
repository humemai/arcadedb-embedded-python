# API Access Methods

`arcadedb-embedded` is an **embedded-only** package: the ArcadeDB engine runs
inside your Python process and is accessed through direct JVM calls via JPype.
There is no bundled HTTP server.

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

## Need client-server or multi-process access?

An embedded database file can only be opened by **one process** at a time
(threads within that process are fine). If you need HTTP access, remote
clients, multiple languages, or several processes sharing one database, run
the official ArcadeDB server alongside — it is a separate deployment, not
part of this package:

```bash
docker run -d --name arcadedb -p 2480:2480 -p 2424:2424 \
  -e JAVA_OPTS="-Darcadedb.server.rootPassword=playwithdata" \
  arcadedata/arcadedb:latest
```

Then talk to it over its [HTTP/JSON API](https://docs.arcadedb.com/#HTTP-API)
from any process or language (e.g. Python `requests`), and use ArcadeDB
**Studio** in the browser at `http://localhost:2480`.

To move data between an embedded database and a server, use
[`export_database`](api/database.md) / SQL `IMPORT DATABASE` — the on-disk
format and export archives are fully compatible.

!!! info "History"
    Versions up to 26.7.1 bundled an optional server mode
    (`arcadedb.create_server`). It was removed to keep the package lean
    (~7MB of server-only JARs); the official server distribution is the
    supported client-server path.

## When to Use Each

### Use this package (embedded) when:

- Single Python process application
- Maximum performance required
- Local SQL/OpenCypher workflows
- Batch processing
- Local development/testing

### Use the official ArcadeDB server when:

- Multi-process architecture
- Remote database access
- Web applications/APIs
- Multiple programming languages
- Microservices architecture
- Studio web UI

## Common Misconceptions

- ❌ **"Embedded mode is only for Java"**
    - ✅ Embedded mode is Python calling Java via JPype (fully Pythonic)
- ❌ **"Embedded means no SQL"**
    - ✅ Full SQL, OpenCypher, vector search, and graph algorithms run in-process
- ❌ **"I need the server to use Studio on my embedded data"**
    - ✅ Export the database and import it into a standalone server when you need Studio
