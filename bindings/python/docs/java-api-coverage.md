# Java API Coverage Analysis

This section provides a practical mapping between the ArcadeDB Java API and the
Python bindings surface in this repository. It reflects the current code in
`arcadedb_embedded` rather than a theoretical, full Java surface comparison.

## Executive Summary

The Python bindings expose the **core database, schema, graph, vector, async,
import/export, and server workflows** needed for typical application usage. Most
omissions are **low-level JVM internals** (WAL details, bucket scanning, binary
protocol, server plugins, clustering) that are not typically used from Python.

### Coverage by Area (Qualitative)

| Area | Status | Notes |
| --- | --- | --- |
| Core Database | ✅ Supported | `DatabaseFactory`, `Database`, transactions, lookups, async helpers |
| Query Execution | ✅ Supported | SQL, OpenCypher, MongoDB, GraphQL passthrough |
| Schema & Indexes | ✅ Supported | Types, properties, LSM_TREE/HASH/FULL_TEXT/LSM_VECTOR/GEOSPATIAL indexes |
| Graph API | ✅ Supported | SQL/OpenCypher graph workflows plus `Document`/`Vertex`/`Edge` wrapper compatibility |
| Vector Search | ✅ Supported | JVector indexes + NumPy conversion helpers |
| Async Execution | ✅ Supported | `AsyncExecutor` plus record-level and SQL/Cypher async flows |
| Data Import | ✅ Supported | SQL import workflows plus a narrow `db.import_documents(...)` wrapper for document files |
| Data Export | ✅ Supported | JSONL/GraphML/GraphSON + CSV for query results |
| Server Mode | ✅ Supported | Embedded server lifecycle + Studio access |
| Advanced/Low-level | ❌ Not exposed | WAL internals, binary protocol, HA/replication, plugins |

### Detailed Coverage

#### 1. Core Database Operations

**DatabaseFactory:**

- ✅ `create()`, `open()`, `exists()`

**Database:**

- ✅ `query(language, query, *args)` and `command(language, command, *args)`
- ✅ Transactions: `begin()`, `commit()`, `rollback()`, `transaction()`
- ✅ Records: `new_document()`, `new_vertex()`, `lookup_by_rid()`, `lookup_by_key()`
- ✅ Utilities: `count_type()`, `drop()`, `get_name()`, `get_database_path()`, `is_open()`, `close()`
- ✅ Configuration: `set_auto_transaction()`, `set_read_your_writes()`
- ✅ Async execution: `async_executor()`
- ✅ Export helpers: `export_database()` and `export_to_csv()`

**Not directly exposed:** bucket scans, WAL internals, low-level binary protocol

#### 2. Query Execution

All query languages supported by the underlying ArcadeDB engine can be used via
`db.query()` and `db.command()`:

- ✅ SQL
- ✅ OpenCypher
- ✅ MongoDB query syntax
- ✅ GraphQL

**ResultSet & Results:**

- ✅ Pythonic iteration (`__iter__`, `__next__`)
- ✅ `has_next()`, `next()`
- ✅ `get()`, `has_property()`, `get_property_names()`
- ✅ `to_json()`, `to_dict()` (Python enhancement)

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
- ✅ OpenCypher patterns: `MATCH (a:User)-[:FOLLOWS]->(b) RETURN b`
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
    MATCH (user:User {name: 'Alice'})-[:FOLLOWS]->(friend)
    RETURN friend.name
""")
```

**Wrapper/object APIs still available:**

```python
with db.transaction():
    alice = db.new_vertex("Person").set("name", "Alice").save()
    bob = db.new_vertex("Person").set("name", "Bob").save()
    alice.new_edge("Follows", bob, since=date.today()).save()
```

#### 4. Schema & Index API

Full Pythonic Schema API available via `db.schema`:

- ✅ `create_document_type()`, `create_vertex_type()`, `create_edge_type()`
- ✅ `get_or_create_*()` helpers
- ✅ `create_property()`, `drop_property()`
- ✅ `drop_type()`, `exists_type()`, `get_type()`, `get_types()`
- ✅ Indexes: `create_index()`, `drop_index()`, `get_indexes()`, `exists_index()`
- ✅ Vector indexes: `create_vector_index()` (on `Database`), `list_vector_indexes()`

#### 5. Server Mode

- ✅ `ArcadeDBServer(root_path, config)` - Server initialization
- ✅ `start()`, `stop()`, context manager support
- ✅ `get_database()`, `create_database()` - Database management
- ✅ `get_studio_url()`, `get_http_port()`
- ✅ Context manager support
- ✅ `get_studio_url()`, `get_http_port()` - Python enhancements
- ✅ Embedded and HTTP mode support
- ❌ Plugin management, HA/replication, advanced user/security management

#### 6. Data Import

**Supported:**

- ✅ SQL `IMPORT DATABASE` for CSV/TSV documents
- ✅ SQL `IMPORT DATABASE` for CSV graph vertices and edges with ID resolution
- ✅ SQL `IMPORT DATABASE` for XML
- ✅ SQL `IMPORT DATABASE` for ArcadeDB JSONL exports
- ✅ SQL `IMPORT DATABASE` for RDF, Neo4j, Word2Vec, and timeseries scenarios covered by tests
- ✅ `db.import_documents(...)` wrapper for document-shaped file imports via the Java importer
- ✅ Batch processing and automatic type inference where supported by the Java importer

The importer surface is intentionally still described conservatively in this repository.
Support exists, but the current repository guidance is:

- bulk table/document ingest: async SQL with a single async worker
- bulk graph ingest: `GraphBatch`
- importer-based paths: available, but not the recommended default because they have
    shown reliability issues, including OoM failures, in larger tests

#### 7. Data Export

- ✅ JSONL export - Full database backup format
- ✅ GraphML export - Graph visualization format
- ✅ GraphSON export - TinkerPop-compatible graph JSON
- ✅ CSV export of query results via `export_to_csv()`
- ✅ Type filtering via `include_types` / `exclude_types`
- ✅ Compression when exporting JSONL/GraphML/GraphSON (Java exporter)

#### 8. Vector Search

- ✅ Vector index creation - `create_vector_index()` (JVector)
- ✅ NumPy array support - `to_java_float_array()`, `to_python_array()`
- ✅ Similarity search - `VectorIndex.find_nearest()` and PQ approximate search
- ✅ Distance functions - cosine, euclidean, inner_product
- ✅ Index tuning parameters (connections, beam width, quantization)
- ✅ Automatic indexing of existing records
- ✅ List vector indexes - `schema.list_vector_indexes()`

#### 9. Advanced / Low-Level APIs Not Exposed

- ❌ WAL and storage internals
- ❌ Binary protocol and custom network stacks
- ❌ HA/replication, distributed clustering
- ❌ Server plugins and module management
- ❌ Custom query engines and DSLs

### Design Philosophy: Query-First Approach

The Python bindings follow a **"query-first, API-second"** philosophy, which is ideal
for Python developers. Instead of exposing every Java object, operations are enabled
through:

- **SQL DDL** for schema management
- **SQL/OpenCypher** for graph and document operations
- **Thin helper APIs** for transactions, vector search, and targeted record access

This approach is actually **cleaner and more maintainable** than direct API exposure:

```python
# Python way (clean):
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
db.query("cypher", "MATCH (a)-[:FOLLOWS]->(b) RETURN b")

# vs. hypothetical direct API (complex):
schema = db.getSchema()
type = schema.getType("User")
index_builder = schema.buildTypeIndex("User", ["email"])
index = index_builder.withUnique(true).create()
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
| Async bulk ingestion | ✅ Good | `AsyncExecutor` |
| Multi-master replication | ❌ Not supported | Java server only |
| Custom query language | ❌ Not supported | Use built-in languages |

### Conclusion

These bindings cover the **primary workflows** most Python developers need:

- Embedded multi-model database
- Graph, document, vector, and time-series data
- SQL and OpenCypher queries
- Server mode for Studio UI and HTTP access

They intentionally **do not expose** low-level JVM internals, clustering, and plugin
management. For those scenarios, use the Java APIs directly.

---

## 🚧 Future Work

- SQL-level vector syntax in ArcadeDB (when available upstream)
- Expanded performance benchmarks and scale testing
- Continued alignment with upstream Java releases

---

## 📝 License

Apache License 2.0

---

## 🙏 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python3 -m pytest tests/ -v`
5. Submit a pull request
