# Server Wire Protocol Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_wire_protocols.py)

The wire protocols the wheel bundles are actually reachable.

Every test carries the `server_wire` marker (a module-level `pytestmark`). The Postgres, ADBC, and Bolt tests call `pytest.importorskip` for their client (`psycopg`; `pyarrow` and `adbc_driver_postgresql`; `neo4j`), so without those packages they skip rather than fail; the Redis test only probes the port. The repo-root uv project installs all of them.

## Test Cases

### 1) plugins are opt in

A default server starts HTTP and nothing else: the test asserts that HTTP serves and that 127.0.0.1:5432, 6379, and 7687 (the default Postgres, Redis, and Bolt ports) refuse connections. A local PostgreSQL, Redis, or Neo4j listening on its default port therefore fails it.

### 2) postgres wire answers a query

Postgres wire is the binary protocol the wheel actually ships. Connects with psycopg and asserts that `SELECT name FROM Item` returns a row containing `alpha`.

### 3) postgres wire answers arrow adbc

Arrow's native PostgreSQL ADBC driver connects and fetches typed columns: the four declared properties arrive as int64, string, double, and bool, the table round-trips, a `$1` parameter query returns `v2`, and a computed `count(*)` column arrives as int64 with the value 3. Needs 26.10.1.

### 4) redis port setting is honored

arcadedb.redis.port is honoured, like the Postgres and Bolt ports.

### 5) bolt wire answers a cypher query

Connects with the `neo4j` driver over Bolt and asserts that `MATCH (i:Item) RETURN i.name AS name` returns a row named `alpha`.

## Running

```bash
uv run pytest bindings/python/tests/test_server_wire_protocols.py -v
```
