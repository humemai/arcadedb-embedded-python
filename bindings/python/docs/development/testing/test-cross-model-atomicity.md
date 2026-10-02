# Cross-Model Atomicity Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cross_model_atomicity.py)

The project page's cross-model story, at test size: search, hop, and update in one transaction survive an interruption between the writes with nothing torn; the same writes, each committed in its own transaction, are torn every time.

## Test Cases

### test_one_transaction_is_never_torn_and_no_transaction_always_is

Builds 200 `Product` vertices with 8-float embeddings, one `RELATED` edge from each, a
UNIQUE index on `pid`, and an `EUCLIDEAN` `LSM_VECTOR` index. Five seeded queries each
run `vectorNeighbors(..., 3)`, follow `out('RELATED')` from the first hit, and increment
`views` on every product touched. A `RuntimeError` is injected after the second write,
and an operation counts as torn when `sum(views)` changed. The test asserts 0 of 5
operations are torn when all the writes share one transaction, and 5 of 5 when each
write commits in its own transaction.

## Running

```bash
uv run pytest bindings/python/tests/test_cross_model_atomicity.py -v
```
