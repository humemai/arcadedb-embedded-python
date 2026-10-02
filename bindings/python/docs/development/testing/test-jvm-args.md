# JVM Args Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_jvm_args.py){ .md-button }

Covers JVM argument construction for the embedded runtime.

## What's Covered

- Defaults when no explicit JVM args are provided.
- Merging the `ARCADEDB_JVM_ARGS` environment variable while preserving mandatory flags:
    - `-Djava.awt.headless=true`
    - `--add-modules=jdk.incubator.vector`
    - `--enable-native-access=ALL-UNNAMED`
    - `-Dfile.encoding=UTF8`
    - `-Dpolyglot.engine.WarnInterpreterOnly=false`
    - `-XX:+UseCompactObjectHeaders`
    - the `--add-opens` flags, checked by package: `java.base/java.util.concurrent.atomic`, `java.base/java.nio.channels.spi`, and `java.base/java.lang`
- A default JVM crash log when no error file is set (an argument containing `hs_err_pid`).
- Keeping the maximum value when multiple `-Xmx` flags are supplied.
- Ensuring a default heap (`-Xmx4g`) is injected if the user omits it.
- Respecting the user's explicit choice and avoiding duplicate flags when they already provide them.
- `ARCADEDB_JVM_ERROR_FILE` handling via `-XX:ErrorFile=...`.
- `common_pool_parallelism`: injecting `-Djava.util.concurrent.ForkJoinPool.common.parallelism=<n>`, overriding any env-provided value, and rejecting values below 1.
- `conftest.py` defines each `pytest_*` hook once (counted from its AST).
- On Windows, faulthandler is off while the tests run (skipped elsewhere).
- `conftest.dump_java_threads()` lists the JVM's threads with their states and stacks; the conftest timer calls it for a test still running after `ARCADEDB_TEST_JAVA_DUMP_AFTER_S` seconds (540 by default), so a hang inside a Java call leaves the Java side in the CI log (humemai/arcadedb-embedded-python#10).

## Run

```bash
uv run pytest bindings/python/tests/test_jvm_args.py -v
```
