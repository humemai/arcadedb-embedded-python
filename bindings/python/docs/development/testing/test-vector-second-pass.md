# Vector Second-Pass Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_vector_second_pass.py)

A repeated query set returns the same neighbours as its first pass, so a faster second pass is not a different answer. Nothing here measures timing.

## Test Cases

### 1) second pass returns identical neighbours

Inserts 500 seeded random 16-dimension vectors under a COSINE `LSM_VECTOR` index, then runs 10 `vectorNeighbors` queries for k=5 twice. Asserts both passes return the same ids in the same order, with 5 per query.

## Running

```bash
uv run pytest bindings/python/tests/test_vector_second_pass.py -v
```
