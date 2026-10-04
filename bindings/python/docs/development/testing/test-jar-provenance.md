# JAR Provenance Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jar_provenance.py)

The wheel can say which engine it carries, not just which version it is.
`jar_fingerprint()` hashes each JAR's entries (name and content), not its file, and
leaves out only zip timestamps and the `buildNumber`, `timestamp`, and `branch` lines of
`com/arcadedb/arcadedb.properties`. The last four tests pin that on real JARs built in a
temporary directory.

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

### test_per_jar_digests_are_the_real_digests

Spot-check of the largest JAR: `file_sha256` equals the SHA-256 of the file on disk,
`bytes` its size, and `sha256` the content digest recomputed independently from its zip
entries.

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

### test_a_rebuild_of_the_same_code_has_the_same_fingerprint

Two lib directories with the same entries, differing as a CI source build of 26.9.1
differed from the official image: zip timestamps, the `buildNumber`, `timestamp`, and
`branch` lines, and here the compression too. Asserts every JAR's `file_sha256` differs,
every JAR's `sha256` and both combined hashes are equal, and `build_number` reports each
set's own `buildNumber`.

### test_one_changed_class_changes_the_fingerprint

One flipped bit in one class changes `sha256` and `engine_sha256`, and only that JAR's
digest.

### test_only_the_three_build_lines_are_ignored

A changed `version` line in `arcadedb.properties` changes `engine_sha256`.

### test_build_number_is_the_engine_jars

On the installed JARs, `build_number` equals the `buildNumber` line of the engine JAR,
read independently. For a directory without an engine JAR it is `None`.

## Running

```bash
uv run pytest bindings/python/tests/test_jar_provenance.py -v
```
