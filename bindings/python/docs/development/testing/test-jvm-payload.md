# JVM Payload Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm_payload.py)

A Python list must never be what crosses into the JVM.

JPype copies a NumPy array across in one crossing and marshals a list element by element, so the cost scales with the length of every vector. The bulk paths decline a list silently, so a `.tolist()` on the way into the JVM runs, returns the right answer, and is slower. The analysis lives in `benchmarks/experiments/jvm_payload_check.py`; these tests run it from the suite so it rides CI without a workflow of its own.

## Test Cases

### test_the_check_has_not_gone_blind

Runs the checker's self-test first: a check that quietly stops matching looks exactly like a clean tree. Asserts it still finds the defects it exists for and still ignores the comparator patterns (Qdrant, Milvus, Chroma, MongoDB, Neo4j) that genuinely want Python lists.

### test_no_python_list_crosses_into_the_jvm

No file under `benchmarks/experiments`, `bindings/python/src`, `bindings/python/examples`, or `bindings/python/tests` carries a site where a `.tolist()` flows into a call that crosses into the JVM.

Each test skips when `benchmarks/experiments` is not checked out, because the bindings are distributed without it.

## Running

```bash
uv run pytest bindings/python/tests/test_jvm_payload.py -v
```
