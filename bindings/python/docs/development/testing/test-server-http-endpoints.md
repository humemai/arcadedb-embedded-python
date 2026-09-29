# Server HTTP Endpoint Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_server_http_endpoints.py)

The three server HTTP features the bindings document but do not wrap (guide/server.md, "Transactions, Database Commands and Time-Series Writes over HTTP"): a transaction spanning several requests through arcadedb-session-id, server-level database commands, and line-protocol writes to a TIMESERIES type. A fourth test checks a projection read over HTTP.

There are 4 tests.

## Test Cases

### 1) transaction spans requests and rolls back

`POST /api/v1/begin` returns an `arcadedb-session-id`. Two inserts sent with that header are invisible to a session-less `count(*)` (0), and after `rollback` the count is still 0. A second session with two inserts and `commit` leaves a count of 2.

### 2) close and open database commands

`close database` and `open database` through `POST /api/v1/server` both return 200, and the row inserted before the close is still counted afterwards.

### 3) timeseries line protocol write

100 line-protocol samples posted to `/api/v1/ts/{db}/write?precision=s` return 200 or 204, `count(*)` on the TIMESERIES type is 100, and the latest sample's `value` is 99.0.

### 4) embedded and http projections agree

Inserts 300 rows over HTTP and asserts that `SELECT id, amount FROM R ORDER BY id LIMIT 100` over HTTP returns 100 rows with ids 0 through 99, then runs the same statement through the embedded handle of the served database (`server.get_database("httpx")`) and asserts the two lists of `(id, amount)` pairs are equal. Until 2026-09-29 it never ran the embedded query.

## Running

```bash
uv run pytest bindings/python/tests/test_server_http_endpoints.py -v
```
