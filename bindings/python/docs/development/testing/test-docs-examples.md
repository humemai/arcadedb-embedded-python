# Documentation Example Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_docs_examples.py){ .md-button }

This test file validates representative Python snippets from the MkDocs documentation by executing them as real code, not just treating them as illustrative examples.

## Overview

The suite is organized into grouped scenarios rather than one pytest case per code fence.

It currently covers:

- Installation and distribution snippets
- Index and quickstart examples
- API access examples
- Transaction examples
- End-to-end example pages
- Core query guide examples
- Graph guide examples

That gives broad executable coverage across the docs tree while keeping failures readable and easy to map back to the affected page.

## Why This Exists

Documentation drift is easy to miss when examples are only reviewed visually.

This suite helps catch issues such as:

- imports that no longer match the public package surface
- examples that assume missing schema or seed data
- SQL or OpenCypher snippets that do not match ArcadeDB's actual dialect behavior
- setup fragments that need an isolated subprocess because JVM startup options are process-wide

## Test Strategy

The file uses a few complementary approaches:

- extract Python fences from Markdown pages
- execute standalone snippets in subprocesses
- wrap progressive guide snippets with seeded database setup when the page assumes prior context
- keep server-specific cases behind the existing server support checks

This is intentionally broader than a smoke test, but it does not try to execute every Python fence in the docs tree.

## Running These Tests

```bash
# Run the docs example suite
pytest tests/test_docs_examples.py -v

# Verbose output
pytest tests/test_docs_examples.py -v -s
```

## What To Update When Docs Change

If you add or substantially rewrite runnable Python examples in the documentation:

1. Update the relevant Markdown page.
2. Extend `tests/test_docs_examples.py` if the new example should be executable coverage.
3. Re-run `pytest tests/test_docs_examples.py -v`.

## Related Documentation

- [Testing Overview](overview.md)
- [Documentation Development](../documentation.md)
- [Quick Start](../../getting-started/quickstart.md)
- [Queries Guide](../../guide/core/queries.md)
- [Graph Operations Guide](../../guide/graphs.md)
