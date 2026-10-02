# Wheel Platform Tag Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_wheel_platform_tag.py)

Regression tests for `ArcadeData/arcadedb#4037`: wheel manylinux platform tag. The verifier these tests drive, `scripts/verify_wheel_platform_tag.py`, also gates every Linux wheel build (`scripts/Dockerfile.build`).

## Test Cases

### 1) max glibc in dir picks highest

`max_glibc_in_dir` returns `(2, 34)` for pseudo-ELF files that reference GLIBC 2.17 to 2.34.

### 2) parse wheel tag extracts version and arch

`parse_wheel_tag` on `arcadedb_embedded-26.4.2-py3-none-manylinux_2_34_x86_64.whl` returns `(2, 34)` and `"x86_64"`.

### 3) main succeeds when tag matches

`main()` returns 0 and prints OK when the wheel's tag equals the JRE's highest GLIBC version.

### 4) main fails when tag higher than jre

Reproduces `ArcadeData/arcadedb#4037`: wheel tagged manylinux_2_35 but JRE only needs GLIBC_2.34.

### 5) main fails when tag lower than jre

A too-low tag would let the wheel install on systems where the JRE cannot run.

### 6) module exposes public api

Sanity check: the verifier module imports without errors and exposes its API.

### 7) dunder version matches distribution metadata

`__version__` must equal the installed distribution version. When the distribution is not installed (a source checkout), the test returns without asserting.

## Running

```bash
uv run pytest bindings/python/tests/test_wheel_platform_tag.py -v
```
