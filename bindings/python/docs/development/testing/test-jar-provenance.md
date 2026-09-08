# JAR Provenance Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jar_provenance.py)

The wheel can say which engine it carries, not just which version it is.

There are 8 tests.

## Test Cases

### 1) fingerprint is deterministic

Same install, same answer. Otherwise it cannot compare two installs.

### 2) fingerprint matches what is on disk

count and bytes are read from the filesystem, not asserted.

### 3) hash actually covers every jar name and content

Recompute the combined hash from the per-JAR digests.

### 4) per jar digests are the real file digests

Spot-check against the bytes on disk, so the per-JAR list is evidence.

### 5) renaming a jar would change the fingerprint

Name is hashed, not only content.

### 6) engine hash excludes our own jar

engine_sha256 answers "same ArcadeDB?", sha256 answers "same build?".

### 7) our jar list still matches the wheel

_OUR_JARS names a JAR that exists.

### 8) exported from the package root

Harnesses record this next to engine_version, so it must be public.

## Running

```bash
uv run pytest bindings/python/tests/test_jar_provenance.py -v
```
