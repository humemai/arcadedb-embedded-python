# Wheel Platform Tag Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_wheel_platform_tag.py)

Regression tests for issue #4037: wheel manylinux platform tag.

There are 7 tests.

## Test Cases

### 1) max glibc in dir picks highest

See the source for the exact assertions.

### 2) parse wheel tag extracts version and arch

See the source for the exact assertions.

### 3) main succeeds when tag matches

See the source for the exact assertions.

### 4) main fails when tag higher than jre

Reproduces issue #4037: wheel tagged manylinux_2_35 but JRE only needs GLIBC_2.34.

### 5) main fails when tag lower than jre

A too-low tag would let the wheel install on systems where the JRE cannot run.

### 6) module exposes public api

Sanity check: the verifier module imports without errors and exposes its API.

### 7) dunder version matches distribution metadata

__version__ must equal the installed distribution version.

## Running

```bash
uv run pytest bindings/python/tests/test_wheel_platform_tag.py -v
```
