# 21 - Server Mode And HTTP Access

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/21_server_mode_http_access.py){ .md-button }

This example demonstrates the narrow client-server workflow that already exists in the
Python bindings without introducing a separate remote client abstraction.

It covers:

- starting ArcadeDB server mode from the `arcadedb-embedded` package
- reading server metadata from `/api/v1/server`
- creating a database through the server-managed Java API
- creating schema through the HTTP command endpoint
- inserting records through embedded access in the same Python process
- logging in over HTTP and switching to bearer-token authentication
- querying and updating the same data through the HTTP API
- verifying HTTP-side changes back through embedded access

## Run

From `bindings/python/examples`:

```bash
python3 21_server_mode_http_access.py
```

Keep the server open so you can inspect Studio manually:

```bash
python3 21_server_mode_http_access.py --wait-for-enter
```

With a custom port and server root:

```bash
python3 21_server_mode_http_access.py --http-port 2491 --server-root ./my_test_databases/server_demo_alt
```

## Notes

- The repository is still embedded-first. This example exists to show the optional
  server-mode path that already works out of the box.
- The script uses Python's standard library `urllib` rather than adding a dedicated
  remote client wrapper or a new dependency.
- Database creation still happens through the existing server-managed Java API,
  because that is the supported path already used in the test suite.
- The example prefers `127.0.0.1:2481` by default to reduce clashes with any
  separately running local ArcadeDB server on the usual `2480` port. If that
  port is already in use, the script automatically falls back to a free local
  port and prints the chosen value.
- By default the example exits as soon as the scripted verification steps finish,
  which shuts the server down immediately. Use `--wait-for-enter` if you want time
  to open Studio and inspect the database before shutdown.

## Why This Example Exists

The package already documents and tests server mode, but the examples set was still
heavily weighted toward pure embedded workflows. This fills that gap with a small,
explicit demonstration of the current supported pattern: use the embedded package to
start the server, then mix embedded access and HTTP access when a shared endpoint is
more practical than direct file-based locking.
