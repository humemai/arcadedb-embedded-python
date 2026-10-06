# Server Packaging Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_packaging.py)

The server stack is actually IN the wheel, and the API is reachable.

## Test Cases

### 1) server jars are bundled

A JAR is present for each of `arcadedb-server`, `arcadedb-studio`, `undertow-core`, `xnio-api`, `xnio-nio`, `wildfly-common`, `jboss-logging`, `jboss-threads`, and `micrometer-core` (matched by name prefix). It fails, never skips.

### 2) server api is importable and exported

create_server / ArcadeDBServer are importable AND in __all__.

### 3) studio jar carries no classes

The studio JAR is present and contains no `.class` entries: Studio is static assets only, which is why bundling it is cheap.

### 4) server starts and serves http

Marked `server`; needs `requests` (`importorskip`). The bundled server starts, and `GET /api/v1/server` returns 200 with a `version` field.

## Running

```bash
uv run pytest bindings/python/tests/test_server_packaging.py -v
```
