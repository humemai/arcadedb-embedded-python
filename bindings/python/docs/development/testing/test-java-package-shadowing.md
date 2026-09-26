# Java Package Shadowing Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_java_package_shadowing.py)

A folder named `java/` or `com/` must not change what a query returns.

Until 2026-09-23 the type converter resolved Java classes through JPype's `java` import hook, which resolves the top-level name through `sys.path` like any Python import. A `java/` directory on the path shadowed it, every typed conversion was skipped, and a Java String came back as a list of characters, with no error.

## Test Cases

### 1) a java or com folder on the path does not break conversion

Parametrized over `java` and `com`. Plants a folder of that name in a temporary working directory and runs a query from a subprocess started there, as `python app.py` from a project root would. Asserts the child imported the package under test, strings come back as `str`, and the typed branches still run (`datetime` for a DATETIME, `Decimal` for a DECIMAL).

It runs in a subprocess on purpose: in-process, JPype's `java` module is already in `sys.modules` before the test could plant a folder, so the test would pass with or without the fix.

## Running

```bash
uv run pytest bindings/python/tests/test_java_package_shadowing.py -v
```
