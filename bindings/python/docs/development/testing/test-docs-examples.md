# Documentation Example Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_docs_examples.py){ .md-button }

This test file runs representative Python snippets from the MkDocs documentation as real code, each in its own subprocess, rather than treating them as illustrative examples.

## Overview

The suite is organized into grouped scenarios rather than one pytest case per code fence, one test per scenario:

- Installation and distribution snippets
- Index and quickstart examples
- API access examples
- Transaction examples
- Example pages (the simple document store page, plus a social-network script written in the test)
- Core query guide examples
- Graph guide examples

That gives broad executable coverage across the docs tree while keeping failures readable and easy to map back to the affected page.

## Why This Exists

Documentation drift is easy to miss when examples are only reviewed visually.

This suite helps catch issues such as:

- imports that no longer match the public package surface
- examples that assume missing schema or seed data
- SQL or OpenCypher snippets the engine rejects
- setup fragments that need an isolated subprocess because JVM startup options are process-wide

## Test Strategy

The file uses a few complementary approaches:

- extract Python fences from Markdown pages
- execute standalone snippets in subprocesses
- wrap progressive guide snippets with seeded database setup when the page assumes prior context
- mark server-specific cases `server`

This is intentionally broader than a smoke test, but it does not try to execute every Python fence in the docs tree.

A block is found by a piece of text it contains, and the test fails if no Python block on the page contains that text. A block passes when its subprocess exits 0 within 120 s; printed output is not compared. The module skips when `bindings/python/docs` is absent.

## What Each Test Runs

Page paths are relative to `bindings/python/docs/`.

- `test_docs_installation_and_distribution_examples`: blocks from `getting-started/installation.md` and `getting-started/distributions.md`.
- `test_docs_index_and_quickstart_examples`: blocks from `index.md` and `getting-started/quickstart.md`. The batch-insert snippet it also runs is a copy of the quickstart's, written in the test rather than extracted from the page, so an edit to that quickstart block is not caught.
- `test_docs_api_access_examples`: the access-path blocks from `api-access-methods.md`. It is marked `server`, and it skips without `requests` (`importorskip`).
- `test_docs_transaction_examples`: blocks from `guide/core/transactions.md`.
- `test_docs_example_pages`: the `INSERT INTO Task SET` block from `examples/01_simple_document_store.md`, run against a seeded `Task` schema. The social-network script in the same test is written in the test itself, not read from `examples/02_social_network_graph.md`, so an edit to that page is not caught; the script asserts the rows returned by one SQL `MATCH` query and one OpenCypher query.
- `test_docs_core_query_examples`: blocks from `guide/core/queries.md`, several of them run inside a database seeded with the data the page assumes.
- `test_docs_graph_guide_examples`: blocks from `guide/graphs.md`.

## Running These Tests

```bash
# Run the docs example suite (from the repository root)
uv run pytest bindings/python/tests/test_docs_examples.py -v

# Show printed output
uv run pytest bindings/python/tests/test_docs_examples.py -v -s
```

## What To Update When Docs Change

If you add or substantially rewrite runnable Python examples in the documentation:

1. Update the relevant Markdown page.
2. Extend `tests/test_docs_examples.py` if the new example should be executable coverage.
3. Re-run `uv run pytest bindings/python/tests/test_docs_examples.py -v`.

## Related Documentation

- [Testing Overview](overview.md)
- [Documentation Development](../documentation.md)
- [Quick Start](../../getting-started/quickstart.md)
- [Queries Guide](../../guide/core/queries.md)
- [Graph Operations Guide](../../guide/graphs.md)
