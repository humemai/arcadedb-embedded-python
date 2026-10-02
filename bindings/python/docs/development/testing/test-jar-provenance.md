# JAR Provenance Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jar_provenance.py)

The wheel can say which engine it carries, not just which version it is.

## Test Cases

### test_fingerprint_is_deterministic

Two calls return the same `sha256` and `count`, and `sha256` is 64 characters long.
Otherwise it cannot compare two installs.

### test_fingerprint_matches_what_is_on_disk

Asserts `count` equals the number of `.jar` files in `jar_dir`, `bytes` equals their
total size on disk, and `count > 0`.

### test_hash_actually_covers_every_jar_name_and_content

Recomputes the combined hash as a SHA-256 over the ordered (name, digest) pairs from
`jar_fingerprint(per_jar=True)` and asserts it equals `sha256`.

### test_per_jar_digests_are_the_real_file_digests

Spot-check against the bytes on disk, so the per-JAR list is evidence.

### test_renaming_a_jar_would_change_the_fingerprint

Name is hashed, not only content: swapping the digests of the first two JARs changes
the combined hash. With fewer than 2 JARs it returns without asserting.

### test_engine_hash_excludes_our_own_jar

engine_sha256 answers "same ArcadeDB?", sha256 answers "same build?". Asserts there is
at least one non-engine JAR, `engine_count == count - len(ours)`,
`engine_sha256 != sha256`, and that `engine_sha256` is the hash of exactly the engine
JARs.

### test_our_jar_list_still_matches_the_wheel

_OUR_JARS names a JAR that exists.

### test_exported_from_the_package_root

Harnesses record this next to engine_version, so it must be public.

## Running

```bash
uv run pytest bindings/python/tests/test_jar_provenance.py -v
```
