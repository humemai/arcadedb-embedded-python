# JVM Args Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm_args.py){ .md-button }

Covers JVM argument construction for the embedded runtime.

## What's Covered

- Defaults when no explicit JVM args are provided.
- Merging the `ARCADEDB_JVM_ARGS` env fallback while preserving mandatory flags:
    - `-Djava.awt.headless=true`
    - `--add-modules=jdk.incubator.vector`
    - `--enable-native-access=ALL-UNNAMED`
    - `-Dfile.encoding=UTF8`
    - `-Dpolyglot.engine.WarnInterpreterOnly=false`
    - `-XX:+UseCompactObjectHeaders`
- Keeping the maximum value when multiple `-Xmx` flags are supplied.
- Ensuring a default heap (`-Xmx4g`) is injected if the user omits it.
- Respecting the user's explicit choice and avoiding duplicate flags when they already provide them.
- `ARCADEDB_JVM_ERROR_FILE` handling via `-XX:ErrorFile=...`.
- `common_pool_parallelism`: injecting `-Djava.util.concurrent.ForkJoinPool.common.parallelism=<n>`, overriding any env-provided value, and rejecting values below 1.

## Run

```bash
pytest tests/test_jvm_args.py -v
```
