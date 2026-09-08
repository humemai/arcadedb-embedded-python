# Server Packaging Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_packaging.py)

The server stack is actually IN the wheel, and the API is reachable.

There are 5 tests.

## Test Cases

### 1) server jars are bundled

Every JAR server mode needs is present. Fails, never skips.

### 2) server api is importable and exported

create_server / ArcadeDBServer are importable AND in __all__.

### 3) has server support agrees with reality

The skip-guard other server tests rely on must not lie.

### 4) studio jar carries no classes

Studio is static assets only, which is why bundling it is cheap.

### 5) server starts and serves http

End-to-end: the bundled stack actually starts and answers.

## Running

```bash
uv run pytest bindings/python/tests/test_server_packaging.py -v
```
