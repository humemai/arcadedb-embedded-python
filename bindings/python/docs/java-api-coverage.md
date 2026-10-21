# Java API Coverage Analysis

This section provides a practical mapping between the ArcadeDB Java API and the
Python bindings surface in this repository. It reflects the current code in
`arcadedb_embedded` rather than a theoretical, full Java surface comparison.

## Executive Summary

The Python bindings expose the **core database, schema, graph, vector, async,
import/export, and server workflows** needed for typical application usage. Most
omissions are **low-level JVM internals** (WAL details, binary
protocol, clustering) that are not typically used from Python.

**The recommended path is the query languages.** Where the engine offers a SQL statement
for a feature, the bindings document the statement and wrap nothing: property
constraints, type scans, the transaction isolation level and the admin operations are
all `db.command(...)` / `db.query(...)` calls (table below). Python API exists for what a
query cannot express, such as opening a database read-only.

#### Java features reached through SQL

| Java API | SQL statement | Notes |
| --- | --- | --- |
| `Property.setMandatory/setReadonly/setNotNull/setMin/setMax/setRegexp/setDefaultValue` | `CREATE PROPERTY T.p TYPE (mandatory true, readonly true, notnull true, min 0, max 9, regexp '...', default x)`; `ALTER PROPERTY T.p MAX 5` | [Schema](api/schema.md#5-set-property-constraints) |
| `Database.scanType(type, polymorphic, callback)` | `SELECT FROM T` (subtypes included) | `AsyncExecutor.scan_type()` wraps the callback form |
| `Database.begin(TRANSACTION_ISOLATION_LEVEL)`, `setTransactionIsolationLevel` | `BEGIN ISOLATION READ_COMMITTED` or `REPEATABLE_READ` | [Transactions](api/transactions.md#isolation-level) |
| `Backup` | `BACKUP DATABASE 'name.zip'` | directory set by `arcadedb.server.backupDirectory` |
| `DatabaseChecker` | `CHECK DATABASE [FIX]` | |
| `Index` rebuild, compaction | `REBUILD INDEX name\|*`, `COMPACT INDEX name\|*` | |

These statements are covered in [SQL for Constraints, Scans, and Maintenance](api/database.md#sql-for-constraints-scans-and-maintenance).
The package bundles the optional in-process server (HTTP API + Studio); see
[Server Mode](guide/server.md). For a server whose lifetime is independent of
your Python process, or for HA/TLS, use the official ArcadeDB distribution.

### Coverage by Area (Qualitative)

| Area | Status | Notes |
| --- | --- | --- |
| Core Database | ✅ Supported | `DatabaseFactory`, `Database`, transactions, lookups, async helpers |
| Query Execution | ✅ Supported | SQL and OpenCypher |
| Schema & Indexes | ✅ Supported | Types, properties, LSM_TREE/HASH/FULL_TEXT/LSM_VECTOR/LSM_SPARSE_VECTOR/GEOSPATIAL indexes |
| Graph API | ✅ Supported | SQL/OpenCypher graph workflows plus `Document`/`Vertex`/`Edge` wrapper compatibility |
| Vector Search | ✅ Supported | JVector indexes + NumPy conversion helpers |
| Sparse Vectors | ✅ Supported | `LSM_SPARSE_VECTOR` indexes and `vector.sparseNeighbors(...)` through SQL |
| Graph Analytics | ✅ Supported | Graph Analytical Views (`CREATE`/`ALTER`/`REBUILD`/`DROP GRAPH ANALYTICAL VIEW`) and the `algo.*` procedures, through SQL and openCypher only; see the [Graph Analytics guide](guide/graph-analytics.md) |
| Time Series | ✅ Supported | `TIMESERIES` types through SQL, `async_executor().append_samples(...)` for bulk writes, and the server's `/api/v1/ts/{db}/write` endpoint; see the [Time Series guide](guide/timeseries.md) |
| Functions and Events | ✅ Supported | Python functions callable from SQL and OpenCypher (`register_function()`), Python callbacks on record create/update/delete (`on()`) |
| Async Execution | ✅ Supported | `AsyncExecutor` plus record-level and SQL/Cypher async flows, `scan_type()` |
| Data Import | ✅ Supported | SQL import workflows plus a narrow `db.import_documents(...)` wrapper for document files |
| Data Export | ✅ Supported | JSONL + CSV for query results |
| Server Mode | ✅ Supported | Embedded server lifecycle + Studio access |
| Advanced/Low-level | ❌ Not exposed | WAL internals, binary protocol, HA/replication |

### Detailed Coverage

#### 1. Core Database Operations

**DatabaseFactory:**

- ✅ `create()`, `open(read_only=False)`, `exists()`
- ✅ Read-only mode: `open_database(path, read_only=True)` and `open(read_only=True)`
  (`ComponentFile.MODE.READ_ONLY`)

**Database:**

- ✅ `query(language, query, *args)` and `command(language, command, *args)`
- ✅ Transactions: `begin()`, `commit()`, `rollback()`, `transaction()`
- ✅ Transaction helpers: `run_in_transaction()` (retries on concurrent-modification
  conflicts), `is_transaction_active()`
- ✅ Records: `new_document()`, `new_vertex()`, `lookup_by_rid()`, `lookup_by_key()`
- ✅ Bulk ingest: `insert_many()` (documents from rows), `insert_columns()` (documents from columns), `insert_dataframe()` and `insert_arrow()` (pandas or Polars DataFrames and Arrow tables into a document or vertex type, through `DocumentBatcher` and `GraphBatch`; no new Java), `graph_batch()` (vertices and edges)
- ✅ Import: `import_documents()` for document-shaped files
- ✅ Vector indexes: `create_vector_index()`
- ✅ Utilities: `count_type()`, `drop()`, `get_name()`, `get_database_path()`, `is_open()`,
  `is_read_only()`, `close()`
- ✅ `sqlscript`: `db.command("sqlscript", script)` and `db.query("sqlscript", script)` run several
  SQL statements as one script (see [Queries](guide/core/queries.md))
- ✅ Configuration: `set_auto_transaction()`, `set_read_your_writes()`,
  `is_read_your_writes()`, `set_wal_flush()`
- ✅ Async execution: `async_executor()`
- ✅ SQL and openCypher functions written in Python: `register_function()`, `unregister_function()` (engine `SQLFunction` through the bridge class `PythonFunctions`)
- ✅ Record events: `on()` and `EventHandle.remove()` for before/after create, update, and delete (engine `RecordEvents`, database-wide or per type, through the bridge class `PythonRecordEvents`). Read events (`BeforeRecordReadListener`, `AfterRecordReadListener`) are not exposed
- ✅ Export helpers: `export_database()` and `export_to_csv()`

**Not directly exposed:** WAL internals, low-level binary protocol. Type scans are
`SELECT FROM <type>`; `AsyncExecutor.scan_type()` is the callback form, and bucket scans
(`scanBucket`) are not wrapped.

#### 2. Query Execution

SQL and OpenCypher run through `db.query()` and `db.command()`:

- ✅ SQL
- ✅ OpenCypher

The GraphQL module ships in the wheel, but no test exercises it from Python. Gremlin and
the MongoDB query language are not bundled (`scripts/jar_exclusions.txt`).

**ResultSet & Results:**

- ✅ Pythonic iteration (`ResultSet.__iter__`, `__next__`)
- ✅ `ResultSet` helpers: `first()`, `one()`, `count()`, `close()`
- ✅ Row materialization: `to_list()` / `iter_dicts()` (full Python types), `to_json_list()` / `iter_json_batches()` (same list-of-dicts shape with JSON-native values; `to_list()` costs about the same), `iter_chunks()`
- ✅ Columnar materialization: `to_columns()`, `to_arrow()`, `to_dataframe()`
- ✅ `Result.get()`, `has_property()`, `get_property_names()`
- ✅ `Result.to_json()`, `to_dict()` (Python enhancement)

#### 3. Graph API

**Recommended approach: SQL/OpenCypher for graph writes and traversals, with wrapper
APIs available when you explicitly need record objects**

**Wrapper/record APIs available:**

- ✅ `db.new_vertex(type)` / `db.new_document(type)`
- ✅ `record.set(name, value)` / `record.save()` / `record.delete()` / `record.modify()`
- ✅ `vertex.new_edge(label, target, **props)` (bidirectionality controlled by EdgeType schema)
- ✅ `vertex.get_out_edges()`, `get_in_edges()`, `get_both_edges()`
- ✅ `db.lookup_by_rid(rid)` for direct record access

**Graph Traversals & Queries:**

- ✅ SQL traversal: `SELECT * FROM User WHERE out('Follows').name = 'Alice'`
- ✅ OpenCypher patterns: `MATCH (a:User)-[:Follows]->(b) RETURN b`
- ✅ Path finding, shortest paths, pattern matching

**Not exposed:** event listeners/callback hooks, low-level graph internals

**Recommended query-first approach:**

```python
# Create vertices via SQL
with db.transaction():
    db.command("sql", "INSERT INTO User SET id = 1, name = 'Alice'")
    db.command("sql", "INSERT INTO User SET id = 2, name = 'Bob'")
    db.command("sql", """
        CREATE EDGE Follows
        FROM (SELECT FROM User WHERE id = 1)
        TO (SELECT FROM User WHERE id = 2)
    """)

# Traverse via OpenCypher
result = db.query("opencypher", """
    MATCH (user:User {name: 'Alice'})-[:Follows]->(friend)
    RETURN friend.name
""")
```

**Wrapper/object APIs still available:**

```python
with db.transaction():
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()
    alice.new_edge("Follows", bob, since=date.today())  # saved by new_edge
```

#### 4. Schema & Index API

Full Pythonic Schema API available via `db.schema`:

- ✅ `create_document_type()`, `create_vertex_type()`, `create_edge_type()`
- ✅ `get_or_create_*()` helpers
- ✅ `create_property()`, `get_or_create_property()`, `drop_property()` (constraints through
  SQL, see above)
- ✅ `drop_type()`, `exists_type()`, `get_type()`, `get_types()`
- ✅ Indexes: `create_index()`, `get_or_create_index()`, `drop_index()`, `get_indexes()`,
  `exists_index()`, `get_index_by_name()`
- ✅ Vector indexes: SQL `CREATE INDEX ... LSM_VECTOR`, secondary/manual helper coverage,
  `get_vector_index()`, `list_vector_indexes()`

#### 5. Server Mode

**Supported:**

- ✅ `ArcadeDBServer(root_path, root_password, config)` / `create_server(...)` - Server initialization
- ✅ `start()`, `stop()`, context manager support
- ✅ `get_database()`, `create_database()` - Database management
- ✅ `get_studio_url()`, `get_http_port()` - Python enhancements
- ✅ Embedded and HTTP access to the same databases
- ✅ The bundled Postgres, Redis, and Bolt protocol plugins, started through
  `config={"server_plugins": ...}` (see [Wire Protocols](guide/server.md#wire-protocols))

**Not exposed:**

- ❌ HA/replication, advanced user/security management:
  run the official [ArcadeDB server](https://docs.arcadedb.com/#Server) for those

#### 6. Data Import

**Supported:**

- ✅ SQL `IMPORT DATABASE` for CSV/TSV documents
- ✅ SQL `IMPORT DATABASE` for CSV graph vertices and edges with ID resolution
- ✅ SQL `IMPORT DATABASE` for XML
- ✅ SQL `IMPORT DATABASE` for ArcadeDB JSONL exports
- ✅ SQL `IMPORT DATABASE` for RDF, Neo4j, and Word2Vec scenarios covered by tests
- ❌ SQL `IMPORT DATABASE` into a TIMESERIES type (a TIMESERIES type owns no document
  buckets; use `append_samples()` or the `/api/v1/ts/{db}/write` endpoint)
- ✅ `db.import_documents(...)` wrapper for document-shaped file imports via the Java importer
- ✅ Batch processing and automatic type inference where supported by the Java importer

The importer surface is intentionally still described conservatively in this repository.
Support exists, but the current repository guidance is:

- bulk table/document ingest: `db.insert_many(...)`
- bulk graph ingest: `GraphBatch`
- importer-based paths: available, but not the recommended default for bulk loads

#### 7. Data Export

- ✅ JSONL export - Full database backup format
- ✅ CSV export of query results via `export_to_csv()`
- ✅ Type filtering via `include_types` / `exclude_types`
- ✅ Compression when exporting JSONL (Java exporter)
- ❌ GraphML and GraphSON export: they come from the `arcadedb-gremlin` module, which the
  wheel excludes, so they raise `ArcadeDBError`

#### 8. Vector Search

- ✅ Vector index creation - SQL `CREATE INDEX ... LSM_VECTOR`
- ✅ NumPy array support - `to_java_float_array()`, `to_java_int_array()`, `to_java_byte_array()`, `to_python_array()`
- ✅ Similarity search - SQL `vectorNeighbors`, with the `efSearch`, `filter`, `where` (26.11.1 and later), `groupBy`, `groupSize` and `maxDistance` options
- ✅ Distance functions - cosine, euclidean, dot_product
- ✅ Index tuning parameters (connections, beam width, quantization), and in SQL `neighborOverflowFactor` and `alphaDiversityRelaxation`
- ✅ Sparse vectors - SQL `CREATE INDEX ... LSM_SPARSE_VECTOR` and `vector.sparseNeighbors`
- ✅ Automatic indexing of existing records
- ✅ List vector indexes - `schema.list_vector_indexes()`

#### 9. Advanced / Low-Level APIs Not Exposed

- ❌ WAL and storage internals
- ❌ Binary protocol and custom network stacks
- ❌ HA/replication, distributed clustering
- ❌ Plugins other than the bundled Postgres, Redis, and Bolt ones, and module management
- ❌ Custom query engines and DSLs

### Design Philosophy: Query-First Approach

The Python bindings follow a **"query-first, API-second"** philosophy, which is ideal
for Python developers. Instead of exposing every Java object, operations are enabled
through:

- **SQL DDL** for schema management, including property constraints
- **SQL statements** for scans, the isolation level, backup, integrity check and index maintenance
- **SQL/OpenCypher** for graph and document operations
- **Thin helper APIs** for transactions, vector search, and targeted record access
- **Python hooks** where no statement can do the job: `register_function()` (a Python function called from SQL and openCypher) and `on()` (a Python callback on record create, update, or delete)

For example, an index is one SQL statement and a graph query is one OpenCypher statement:

```python
db.command("sql", "CREATE INDEX ON User (email) UNIQUE_HASH")
db.query("opencypher", "MATCH (a)-[:Follows]->(b) RETURN b")
```

### Use Case Suitability

| Use Case | Suitable? | Notes |
| --- | --- | --- |
| Embedded database in Python app | ✅ Excellent | Core use case |
| Graph analytics with Cypher | ✅ Excellent | SQL and OpenCypher supported |
| Document store | ✅ Excellent | SQL and schema APIs |
| Vector similarity search | ✅ Excellent | JVector + NumPy integration |
| Development with Studio UI | ✅ Excellent | Server mode included |
| Data migration (CSV/XML/JSONL import) | ✅ Good | SQL import workflows exercised by tests |
| Async SQL commands as a bulk load | ❌ Not recommended | `async_executor().command(...)` is not a bulk-write path; see [Bulk Ingest Recommendation](guide/import.md#bulk-ingest-recommendation). Use `insert_many()`, `insert_columns()`, or `GraphBatch` |
| Multi-master replication | ❌ Not supported | Java server only |
| Custom query language | ❌ Not supported | Use built-in languages |
