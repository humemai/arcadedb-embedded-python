# Server Wire Protocol Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_wire_protocols.py)

The wire protocols the wheel bundles are actually reachable.

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

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_server_wire_protocols.py -v
```
