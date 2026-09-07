# 24 - Transactions, Database Commands and Time-Series Writes over HTTP

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/24_server_http_transactions_timeseries.py)

Example 23 showed the narrow client-server story: start the bundled server,
create a database, run commands over HTTP. This one covers the three server
features a second process needs next, none of which the embedded bindings wrap
because they are the server's own HTTP API:

- **one transaction across several requests**: `POST /api/v1/begin/{db}`
  returns an `arcadedb-session-id`; every command sent with that header belongs
  to the transaction until `/commit/{db}` or `/rollback/{db}`
- **database commands**: `close database` and `open database` sent to
  `POST /api/v1/server`, the served equivalent of closing and reopening an
  embedded database
- **time-series writes**: InfluxDB line protocol to `POST /api/v1/ts/{db}/write`
  with `?precision=s`, read back with plain SQL

## Run

```bash
uv run python examples/24_server_http_transactions_timeseries.py
```

Options: `--server-root` to keep the server directory, `--password`,
`--http-port` (falls back to a free port if taken).

## What you should see

The row count is 0 before the commit and 2 after it; the rolled-back insert
never appears; the database survives a close and reopen; 1,000 line-protocol
samples land and the newest reads back with SQL.

## Notes

- Standard-library HTTP only, as in example 23.
- The same TIMESERIES type is fed in-process by `db.async_executor().append_samples(...)`,
  which skips the parse and the socket. The HTTP path is what any client
  without the wheel gets. See the [Server Mode guide](../guide/server.md).
