# Packaging design: arcadedb-embedded-native (preview)

Decided 2026-10-22. Status: local build and parity only; no CI workflow, no PyPI upload yet.

## Decisions

| Topic | Decision | Reason |
|---|---|---|
| Distribution name | `arcadedb-embedded-native` (separate PyPI project) | The JPype wheel and the native wheel have different runtimes, platforms, size and maturity; one project cannot carry both tags and the alpha classifier. |
| Import name | `arcadedb_native` (public API identical to `arcadedb_embedded`) | Side-by-side install without file conflicts. Switch: `import arcadedb_native as arcadedb`. |
| Shared Python code | Not duplicated in git. `build_wheel.py` copies `src/arcadedb_embedded` to `arcadedb_native` at build time, renames the package, and rewrites `import jpype` to a bundled stub (`_jpype_stub.py`) so the wheel has no JPype dependency. One line (`_native/__init__.py: _DEFAULT_BACKEND`) is flipped to `"native"`. | One source tree, one test suite; the build fails if any `jpype` import is left or the default-backend line is missing. |
| Native library | `libarcadedb.so` and `libjvector-x86_64.so` inside the package directory. `lib.py` already finds them next to itself and sets `ARCADEDB_NATIVE_LIBDIR`. | No search path or env var needed for users; `ARCADEDB_NATIVE_LIB` still overrides. |
| Wheel tag | `py3-none-manylinux_2_34_x86_64`, image built with `-march=compatibility` (baseline x86-64) | The library is loaded with ctypes, so it does not depend on the CPython ABI. 2.34 is the highest `GLIBC_` symbol version in `objdump -T libarcadedb.so` (libjvector: 2.14; `build_wheel.py` computes the tag from the library). Other NEEDED: libz.so.1, libm, libc, libstdc++, libgcc_s (manylinux-allowed). |
| Version | PEP 440 pre-release of the engine release the image links: `26.10.2a1` | The image is built from the **26.10.2 release jars** (Maven Central, `-Darcadedb.version=26.10.2`; `native-spike/pom.xml`), never a local SNAPSHOT: a SNAPSHOT in `~/.m2` is not reproducible. The bindings and the Java glue come from branch `native-preview` (`SOURCE_COMMIT` in `arcadedb_native/_build_info.py`). When the engine moves (26.11.1), rebuild with `ARCADEDB_ENGINE_VERSION=26.11.1` and publish `26.11.1a1`; a rebuild of the same engine increments `aN`. |
| Classifier | `Development Status :: 3 - Alpha` | Preview. |
| Licence | Apache-2.0 (`license = "Apache-2.0"`) plus the third-party texts below | ArcadeDB and the bindings are Apache-2.0. |
| Python requirement | `>=3.11`, no hard dependencies; extras numpy / arrow / pandas / polars | Same as the JPype wheel's optional stacks. |

## What must ship (licences)

The image links the GraalVM Substrate VM runtime and OpenJDK classes: GPLv2 **with the Classpath Exception**. The exception permits linking
and distribution with code under other licences. The wheel therefore ships, in `*.dist-info/licenses/`:

- `LICENSE` (Apache-2.0), `NOTICE`, `THIRD_PARTY_NOTICES.md` (Java libraries on the image classpath and their licences)
- `licenses/GraalVM-CE-LICENSE.txt` (GPLv2 + Classpath Exception), `GraalVM-native-image-LICENSE.txt`, `GraalVM-THIRD_PARTY_LICENSE.txt` (UPL-1.0 and others),
  copied from the GraalVM CE install at build time
- `licenses/Apache-2.0.txt`

`NOTICE` names the source locations of GraalVM and OpenJDK (GPL source availability). Oracle GraalVM (GFTC) is not used. Open items before a non-preview
release: regenerate `THIRD_PARTY_NOTICES.md` from the resolved classpath by tool (it is hand-written now), and have the GPL-with-CPE
source-offer wording reviewed. The Highway library `libjvector-x86_64.so` is taken unmodified from the jvector 4.0.2 jar (Apache-2.0).

## Build

```bash
# 1. the image, detached, through quiet_build (13 GB, builder -J-Xmx12g)
NEED_GB=13 JOB_MEM_GB=14 .notes/bench/tools/quiet_build.sh bash native-spike/scripts/preview-build.sh   # -> ~/build-scratch/native-lib/preview
# 2. the wheel
python bindings/python/native-wheel/build_wheel.py --lib-dir ~/build-scratch/native-lib/preview --version 26.10.2a1 --engine 26.10.2 --out <dir>
# 3. check the tag
uvx auditwheel show <dir>/dist/*.whl
```

Parity against the installed wheel (not the source tree): `.notes/bench/repros/native-preview-20261022/parity_wheel.py` runs the bindings tests
with `arcadedb_embedded` aliased to the installed `arcadedb_native`.

## Release scheme and publishing (fixed by the owner, for the later CI task)

- PyPI has a pending trusted publisher for project `arcadedb-embedded-native`: GitHub repo `humemai/arcadedb-embedded-python`, workflow
  file `.github/workflows/native-preview.yml`, environment `pypi-native`.
- The repo environment `pypi-native` exists and allows deployments only from tags matching `native-v*`.
- Release tag: `native-v<version>` (for example `native-v26.10.2a1`). The publish job must run in environment `pypi-native` with
  `permissions: id-token: write` and use `pypa/gh-action-pypi-publish`. No API token.
- The workflow does not exist yet (not part of this task). Image builds are heavy (about 13 GB, 6-10 min on 4 cores): paid-runner budget applies (builds only
  on `native-v*` tags or manual dispatch; the image build needs a manylinux_2_34-or-older container so the glibc floor is controlled).

## Open issues

- **arm64**: the Highway library exists for aarch64 in the jvector jar, but the image must be built natively on arm64 (no cross-compile in CE); a
  `manylinux_2_34_aarch64` wheel needs an arm64 runner. `-march` for the image must be chosen for arm64 (x86-64-v3 is x86 only).
- **CI**: GraalVM CE 25.4.4.1.1 download + checksum, the manylinux container (the laptop build host has glibc 2.43; the symbols used are still
  at most 2.34, but a container build makes that a guarantee), `auditwheel show` as a gate, wheel install + parity run on a clean runner, `twine check`.
- **x86-64-v3 reference image**: GraalVM CE 25.4 compiles for x86-64-v3 (AVX2, BMI2, FMA) by default. `auditwheel show` flags such a library ("x86_64_v3 instruction set") and grants only `linux_x86_64`; a manylinux tag promises baseline x86-64 (PEP 600). Decision (owner, 2026-10-22): the shipped image is built with `-march=compatibility`; the v3 image is kept as a reference build (`MARCH=x86-64-v3 preview-build.sh`) and measured against it. If `-march=compatibility` costs more than about 10% on any measured figure the owner decides; both images are kept. Measurement: `.notes/bench/repros/native-preview-20261022/measure-summary.txt` (untimed, same session, alternating, vc7 100k vectors + nv oltp/sql). `lib.py::_check_cpu` (clear error instead of SIGILL when avx2/bmi2/fma are missing) runs only for a v3 image: `build_wheel.py --march` writes `NATIVE_MARCH` into `_build_info.py`, and `compatibility` skips the check.
- **CE bug workaround**: `-H:-VectorAPISupport` (oracle/graal crash in `PanamaVectorUtilSupport.dotProductPreferred`); retest on newer CE.
- **Performance**: only untimed laptop directions exist; the README table must be replaced by the ab.py results from the benchmark machine.
