"""CPU baseline check for a native image built above the platform baseline.

The wheels of ``arcadedb-embedded-native`` are built with ``-march=compatibility`` (baseline x86-64, generic armv8-a) and run on every CPU
of their platform, so for them ``check_cpu`` returns at once. A reference image built for a higher baseline (``MARCH=x86-64-v3``, GraalVM
CE's default on x86-64, or ``armv8.1-a`` on arm64) dies with ``Illegal instruction`` and no message on an older CPU; this check turns that
into an error that names the missing features. Pure Python, no native code, and it never blocks when the CPU cannot be read.
"""

import logging
import os
import platform
import sys

_log = logging.getLogger(__name__)

SKIP_ENV = "ARCADEDB_NATIVE_SKIP_CPU_CHECK"
FALLBACK = (
    "Install the arcadedb-embedded (JVM) package instead, which runs on any x86-64 CPU"
)

# x86-64-v3 as GraalVM and upstream ArcadeDB (ArcadeData/arcadedb#10624) define it: feature -> the /proc/cpuinfo flags that mean it
# (Linux reports LZCNT as "abm" on AMD and on Intel since Haswell).
X86_64_V3 = {
    "AVX": ("avx",),
    "AVX2": ("avx2",),
    "BMI1": ("bmi1",),
    "BMI2": ("bmi2",),
    "FMA": ("fma",),
    "F16C": ("f16c",),
    "LZCNT": ("lzcnt", "abm"),
    "MOVBE": ("movbe",),
}
# armv8.1-a adds the LSE atomics, which the Raspberry Pi 4 (Cortex-A72) and AWS Graviton1 (Cortex-A72) lack; /proc/cpuinfo calls them "atomics"
ARMV8_1_A = {"LSE atomics": ("atomics",)}
# Windows: IsProcessorFeaturePresent(PF_AVX2_INSTRUCTIONS_AVAILABLE); AVX2 is the one v3 feature it reports, and a CPU with AVX2 has the rest
PF_AVX2_INSTRUCTIONS_AVAILABLE = 40

BASELINES = {
    "x86-64-v3": (
        "x86-64-v3 (AVX, AVX2, BMI1, BMI2, FMA, F16C, LZCNT, MOVBE)",
        X86_64_V3,
    ),
    "armv8.1-a": ("armv8.1-a (LSE atomics)", ARMV8_1_A),
}


def required_baseline(march: str, machine: str):
    """The baseline an image built with ``march`` needs on ``machine``, or None when it runs on every CPU of the platform."""
    if march == "compatibility":
        return None
    machine = machine.lower()
    if machine in ("x86_64", "amd64"):
        return BASELINES["x86-64-v3"] if march in ("x86-64-v3", "native") else None
    if machine in ("aarch64", "arm64"):
        return BASELINES["armv8.1-a"] if march in ("armv8.1-a", "native") else None
    return None


def missing_features(baseline: dict, flags) -> list:
    """The features of ``baseline`` that none of its cpuinfo names appear in ``flags`` for. ``flags`` empty (unreadable): nothing is missing."""
    if not flags:
        return []
    have = set(flags)
    return [name for name, names in baseline.items() if not have.intersection(names)]


def parse_cpuinfo(text: str, machine: str):
    """The feature flags of the first CPU in ``/proc/cpuinfo`` text: the ``flags`` line on x86, ``Features`` on arm64. Empty when absent."""
    key = "features" if machine.lower() in ("aarch64", "arm64") else "flags"
    for line in text.splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip().lower() == key:
            return value.split()
    return []


def _linux_flags(machine: str):
    with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
        return parse_cpuinfo(f.read(), machine)


def _windows_missing(baseline: dict) -> list:
    import ctypes

    if baseline is not X86_64_V3:
        return []
    present = ctypes.windll.kernel32.IsProcessorFeaturePresent(
        PF_AVX2_INSTRUCTIONS_AVAILABLE
    )
    return [] if present else ["AVX2"]


def message(march: str, label: str, missing) -> str:
    return (
        f"This CPU cannot run the native library: it was built for {label} (-march={march}) and the CPU lacks {', '.join(missing)}. "
        f"Without this check the process would die with 'Illegal instruction'. {FALLBACK}, "
        f"or set {SKIP_ENV}=1 to run anyway at your own risk."
    )


def check_cpu(
    march: str, machine: str = None, plat: str = None, flags=None, windows_missing=None
) -> None:
    """Raise ``ArcadeDBError`` when the CPU lacks a feature the image's baseline needs. ``flags`` and ``windows_missing`` are test hooks."""
    from ..exceptions import ArcadeDBError

    if os.environ.get(SKIP_ENV):
        return
    machine = machine or platform.machine()
    plat = plat or sys.platform
    required = required_baseline(march, machine)
    if required is None:
        return
    label, baseline = required
    try:
        if plat.startswith("linux"):
            missing = missing_features(
                baseline, _linux_flags(machine) if flags is None else flags
            )
        elif plat == "win32":
            missing = (
                _windows_missing(baseline)
                if windows_missing is None
                else list(windows_missing)
            )
        else:  # macOS arm64 is always fine, and there is no macOS x86-64 wheel
            return
    except Exception as e:  # unreadable: never block
        _log.debug("CPU check skipped, cannot read the CPU features: %s", e)
        return
    if missing:
        raise ArcadeDBError(message(march, label, missing))
