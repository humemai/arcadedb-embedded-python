# Runtime Cache Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_runtime_cache.py)

The dev-mode runtime cache must follow the wheel it was extracted from.

Running from a source checkout, the JARs and the JRE are extracted from the most recent wheel in `dist/` into `.runtime-cache/`. Until 2026-09-23 that cache was extracted once and trusted forever, so a source-tree run could execute against an old engine without the bridge jar, and nothing said why. None of these tests starts a JVM: they build small fake wheels and call the extraction helper directly.

## Test Cases

### 1) newest wheel is chosen by build time not by name

A reverse string sort ranks 26.9.1 above 26.10.1 because "9" > "1", so the newest wheel is picked by its modification time.

### 2) a rebuilt wheel replaces the cache and leaves nothing behind

A rebuilt wheel with the same filename replaces the extraction, and no file from the old one survives (a classpath carrying two engines is worse than an error).

### 3) an unchanged wheel is not re-extracted

The cache is still a cache: the same wheel does not pay extraction twice.

### 4) a cache from before stamping is treated as stale

A cache without the freshness stamp predates the fix and is re-extracted rather than trusted.

## Running

```bash
uv run pytest bindings/python/tests/test_runtime_cache.py -v
```
