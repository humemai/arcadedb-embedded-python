# Java Package Shadowing Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_java_package_shadowing.py)

A folder named `java/` or `com/` must not change what a query returns.

The type converter resolves Java classes by name through the JVM, not through JPype's `java` import hook, which would resolve the top-level name through `sys.path`; a `java/` or `com/` directory would otherwise shadow it and return a Java String as a list of characters, with no error.

## Test Cases

### test_a_java_or_com_folder_on_the_path_does_not_break_conversion

Parametrized over `java` and `com`. Plants a folder of that name in a temporary working directory and runs a query from a subprocess started there, as `python app.py` from a project root would. Asserts the child imported the package under test, strings come back as `str`, the typed branches still run (`datetime` for a DATETIME, `Decimal` for a DECIMAL), and a list property comes back as `['x', 'yz']`.

It runs in a subprocess on purpose: in-process, JPype's `java` module is already in `sys.modules` before the test could plant a folder, so the test would pass with or without the fix.

## Running

```bash
uv run pytest bindings/python/tests/test_java_package_shadowing.py -v
```
