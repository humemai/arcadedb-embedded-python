# 26 - Cross-Model Transaction Atomicity

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/26_cross_model_transaction_atomicity.py)

One operation across three models: a vector search finds the nearest products,
a graph hop expands to what is related to the best hit, and a document update
bumps a counter on all of them. In ArcadeDB that is one transaction. The
example runs it cleanly, then interrupts it between the writes twenty times in
two ways:

- **inside a transaction**: the exception rolls everything back, torn 0 of 20
- **without one**: each write commits on its own, torn 20 of 20

This is the small version of the project page's
[cross-model table](https://humem.ai/projects/arcadedb#crossmodel), which applies
the same interruption to every engine in that lane (see the
[benchmark overview](../benchmarks/index.md)). The composed Qdrant plus Neo4j
stack there is left torn every time, because no transaction spans its two engines.

## Run

From `bindings/python/examples`:

```bash
python 26_cross_model_transaction_atomicity.py --products 2000 --trials 20
```

The database is created under `./my_test_databases/cross_model_atomicity` (`--db-path`).

## Notes

- Synthetic data, no download; a few seconds end to end.
- The interruption is an exception raised between the writes. A process that
  dies at that point leaves the same state, because an uncommitted transaction
  is discarded on reopen.
