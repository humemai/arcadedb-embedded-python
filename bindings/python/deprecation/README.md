# Deprecation shims for the old PyPI names

The Python bindings move to [ArcadeData/arcadedb-python](https://github.com/ArcadeData/arcadedb-python) as `arcadedb` (the native build) and `arcadedb-jvm` (the JVM build), both importing as `arcadedb`. This folder holds the last release of each old name: a pure-Python shim that depends on its replacement at the same version, warns once, and re-exports it. The old JVM package `arcadedb-embedded` points to `arcadedb-jvm` (the same build, so no silent change at run time) and the old native package `arcadedb-embedded-native` points to `arcadedb`. Users: see [MIGRATION.md](MIGRATION.md).

| Folder | PyPI project | Depends on | Version |
|---|---|---|---|
| `arcadedb-embedded/` | `arcadedb-embedded` (JVM) | `arcadedb-jvm==26.11.1` | 26.11.1 |
| `arcadedb-embedded-native/` | `arcadedb-embedded-native` (native) | `arcadedb==26.11.1` | 26.11.1 |

The shim modules are `arcadedb_embedded` (in both shims) and `arcadedb_native` (in `arcadedb-embedded-native` only: the old native package imported as `arcadedb_native`). The three `__init__.py` files differ only in their docstring and the constants `_OLD_DIST`, `_NEW_DIST`, `_NEW_MODULE` and `_NOTE`; `tests/test_deprecation_shims.py` checks that the rest is identical. The mapping above lives in one place, `TARGETS` in `build_shims.py`, together with the one assumption behind it: both `arcadedb` and `arcadedb-jvm` provide the import name `arcadedb` (the layout says so, but neither has a real release yet). `build_shims.py` refuses to build when a shim's `pyproject.toml` (name, description, dependencies, extras, `Replaced by` URL) or its `_NEW_DIST` and `_NEW_MODULE` constants disagree with `TARGETS`. The real package in `bindings/python/src` is not changed and does not warn: the benchmark harness imports it until the split.

## Build and test (never uploads)

```bash
python3 bindings/python/deprecation/build_shims.py --out /tmp/shims        # uv build, wheel + sdist of both
taskset -c 0-3 uv run pytest bindings/python/tests/test_deprecation_shims.py   # needs the real wheel installed, like the rest of the suite
```

`build_shims.py` checks each version with `scripts/check_version.py` first; add `--check-pypi` on cutover day to check it is the next version on PyPI (it fails once that version is published).

## Cutover day

1. Release `arcadedb-jvm` 26.11.1 and `arcadedb` 26.11.1 (the native build) from ArcadeData/arcadedb-python first. Check `pip download --no-deps arcadedb-jvm==26.11.1` and `arcadedb==26.11.1` work: the shims pin these exact versions. If the first final `arcadedb` is not out (only `26.11.1.devN`), do not publish the native shim: `arcadedb==26.11.1` does not match a dev release, so change its pin and version rule here first. The JVM shim can go out on its own once `arcadedb-jvm==26.11.1` exists.
2. Never push a `26.11.1` tag in this repository: `release-python-packages.yml` would build and publish the real wheels under `arcadedb-embedded`.
3. Build and check: `python3 bindings/python/deprecation/build_shims.py --out dist --check-pypi && uvx twine check dist/*`.
4. Publish both shims. Trusted publishing works only from a workflow, so either (a) register a trusted publisher on both PyPI projects (repository `humemai/arcadedb-embedded-python`, workflow `publish-deprecation-shims.yml`, environment `pypi`), add the workflow below to `.github/workflows/` (and to `FORK_GITHUB_ALLOWLIST` in `sync-upstream.sh` if another sync will still run), and dispatch it with `publish` on; or (b) upload from a laptop with `uvx twine upload dist/*` and a project-scoped API token.
5. In a clean environment: `pip install arcadedb-embedded==26.11.1` installs `arcadedb-jvm` (not `arcadedb`: check `pip list`), and `python -W default -c "import arcadedb_embedded"` shows one FutureWarning; for `arcadedb-embedded-native`, which installs `arcadedb`, `python -W default -c "import arcadedb_native"` shows one FutureWarning too.

```yaml
name: Publish deprecation shims
on:
  workflow_dispatch:
    inputs:
      publish:
        description: "Upload to PyPI (off: build and check only)"
        type: boolean
        default: false
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - name: Setup UV package manager
        run: |
          installer="$(mktemp)"
          curl -LsSf --retry 5 --retry-all-errors --retry-delay 5 -o "$installer" https://astral.sh/uv/0.12.0/install.sh
          sh "$installer"
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
      - run: python3 bindings/python/deprecation/build_shims.py --out dist --check-pypi
      - run: uvx twine check dist/*.whl dist/*.tar.gz
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: shims
          path: dist/
  publish:
    needs: build
    if: inputs.publish
    runs-on: ubuntu-24.04
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: shims
          path: dist/
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
        with:
          packages-dir: dist/
```
