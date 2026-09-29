# Server Wire Protocol Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_wire_protocols.py)

The wire protocols the wheel bundles are actually reachable.

There are 5 tests. Every test carries the `server_wire` marker (a module-level `pytestmark`). Tests 2, 3, and 5 call `pytest.importorskip` for their client (`psycopg`; `pyarrow` and `adbc_driver_postgresql`; `neo4j`), so without those packages they skip rather than fail; test 4 only probes the Redis port. The repo-root uv project installs all of them.

## Test Cases

### 1) plugins are opt in

A default server starts HTTP and nothing else.

### 2) postgres wire answers a query

Postgres wire is the binary protocol the wheel actually ships.

### 3) postgres wire answers arrow adbc

Arrow's native PostgreSQL ADBC driver connects and fetches typed columns, including a computed `count(*)` column as int64. Needs 26.10.1.

### 4) redis port setting is honored

arcadedb.redis.port is honoured, like the Postgres and Bolt ports.

### 5) bolt wire answers a cypher query

Connects with the `neo4j` driver over Bolt and asserts that `MATCH (i:Item) RETURN i.name AS name` returns a row named `alpha`.

## Running

```bash
uv run pytest bindings/python/tests/test_server_wire_protocols.py -v
```
