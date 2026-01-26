# JVM Args Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm_args.py){ .md-button }

Covers JVM argument construction for the embedded runtime.

## What's Covered

- Defaults when no environment variables are set.
- Merging custom `ARCADEDB_JVM_ARGS` while preserving mandatory flags:
	- `-Djava.awt.headless=true`
	- `--add-modules=jdk.incubator.vector`
	- `--enable-native-access=ALL-UNNAMED`
- Ensuring a default heap (`-Xmx4g`) is injected if the user omits it.
- Avoiding duplicate flags when the user already provides them.
- `ARCADEDB_JVM_ERROR_FILE` handling via `-XX:ErrorFile=...`.

## Run

```bash
pytest tests/test_jvm_args.py -v
```
