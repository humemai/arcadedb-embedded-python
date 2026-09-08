# Server HTTP Endpoint Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_http_endpoints.py)

The three server HTTP features the bindings document but do not wrap (guide/server.md, "Transactions, Database Commands and Time-Series Writes over HTTP"): a transaction spanning several requests through arcadedb-session-id, server-level database commands, and line-protocol writes to a TIMESERIES type.

There are 4 tests.

## Test Cases

### 1) transaction spans requests and rolls back

See the source for the exact assertions.

### 2) close and open database commands

See the source for the exact assertions.

### 3) timeseries line protocol write

See the source for the exact assertions.

### 4) embedded and http projections agree

The decomposition in example 23 rests on both paths answering the same rows; the wire format may cost time, never content.

## Running

```bash
uv run pytest bindings/python/tests/test_server_http_endpoints.py -v
```
