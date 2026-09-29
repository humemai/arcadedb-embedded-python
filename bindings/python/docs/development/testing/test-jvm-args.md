# JVM Args Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm_args.py){ .md-button }

Covers JVM argument construction for the embedded runtime.

There are 12 tests.

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
- `conftest.py` defines each `pytest_*` hook once (counted from its AST). A second `pytest_configure` had silently replaced the Windows faulthandler hook from 2026-07-25 to 2026-09-29.
- On Windows, faulthandler is off while the tests run (skipped elsewhere).
- `conftest.dump_java_threads()` lists the JVM's threads with their states and stacks; the conftest timer calls it for a test still running after 540 s, so a hang inside a Java call leaves the Java side in the CI log (humemai/arcadedb-embedded-python#10).

## Run

```bash
uv run pytest bindings/python/tests/test_jvm_args.py -v
```
