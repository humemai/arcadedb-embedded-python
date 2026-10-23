"""The import-time CPU check of the native backend, on fake cpuinfo and feature sets (no real hardware needed)."""

import logging

import pytest
from arcadedb_embedded import ArcadeDBError
from arcadedb_embedded._native import cpu

V3 = "fpu sse sse2 avx avx2 bmi1 bmi2 fma f16c abm movbe"
X86_CPUINFO = (
    "processor\t: 0\nvendor_id\t: GenuineIntel\nflags\t\t: {flags}\nbogomips\t: 5000\n"
)
ARM_CPUINFO = (
    "processor\t: 0\nBogoMIPS\t: 108.00\nFeatures\t: {flags}\nCPU implementer\t: 0x41\n"
)


@pytest.fixture(autouse=True)
def _no_skip_env(monkeypatch):
    monkeypatch.delenv(cpu.SKIP_ENV, raising=False)


def test_a_v3_cpu_passes():
    cpu.check_cpu("x86-64-v3", machine="x86_64", plat="linux", flags=V3.split())


def test_lzcnt_counts_under_either_cpuinfo_name():
    cpu.check_cpu(
        "x86-64-v3",
        machine="x86_64",
        plat="linux",
        flags=V3.replace("abm", "lzcnt").split(),
    )


def test_avx2_missing_names_the_feature_the_baseline_and_the_fallback():
    flags = (
        "fpu sse2 avx bmi1 fma f16c abm movbe".split()
    )  # Celeron J4125: AVX but no AVX2 or BMI2
    with pytest.raises(ArcadeDBError) as e:
        cpu.check_cpu("x86-64-v3", machine="x86_64", plat="linux", flags=flags)
    text = str(e.value)
    assert "AVX2, BMI2" in text
    assert "x86-64-v3" in text and "Illegal instruction" in text
    assert "arcadedb-embedded (JVM)" in text
    assert cpu.SKIP_ENV in text


def test_a_proxmox_default_cpu_type_misses_everything_after_sse4():
    flags = "fpu sse sse2 ssse3 sse4_1 sse4_2 popcnt cx16".split()
    with pytest.raises(
        ArcadeDBError, match="AVX, AVX2, BMI1, BMI2, FMA, F16C, LZCNT, MOVBE"
    ):
        cpu.check_cpu("x86-64-v3", machine="x86_64", plat="linux", flags=flags)


def test_the_cpuinfo_text_is_parsed_per_architecture():
    assert "avx2" in cpu.parse_cpuinfo(X86_CPUINFO.format(flags=V3), "x86_64")
    assert "atomics" in cpu.parse_cpuinfo(
        ARM_CPUINFO.format(flags="fp asimd atomics cpuid"), "aarch64"
    )
    assert cpu.parse_cpuinfo("model name : x", "x86_64") == []


def test_a_pi_4_without_atomics_is_refused_by_an_armv8_1_image():
    flags = cpu.parse_cpuinfo(
        ARM_CPUINFO.format(flags="fp asimd evtstrm crc32 cpuid"), "aarch64"
    )
    with pytest.raises(ArcadeDBError, match="LSE atomics"):
        cpu.check_cpu("armv8.1-a", machine="aarch64", plat="linux", flags=flags)


def test_an_arm64_cpu_with_atomics_passes():
    cpu.check_cpu(
        "armv8.1-a", machine="aarch64", plat="linux", flags="fp asimd atomics".split()
    )


def test_compatibility_images_never_check():
    cpu.check_cpu("compatibility", machine="x86_64", plat="linux", flags=["sse2"])
    cpu.check_cpu("compatibility", machine="aarch64", plat="linux", flags=["fp"])


def test_an_unreadable_cpu_does_not_block(monkeypatch, caplog):
    def boom(machine):
        raise OSError("no /proc")

    monkeypatch.setattr(cpu, "_linux_flags", boom)
    with caplog.at_level(logging.DEBUG, logger=cpu.__name__):
        cpu.check_cpu("x86-64-v3", machine="x86_64", plat="linux")
    assert "cannot read the CPU features" in caplog.text
    cpu.check_cpu(
        "x86-64-v3", machine="x86_64", plat="linux", flags=[]
    )  # a cpuinfo with no flags line


def test_the_skip_env_var_passes_a_cpu_below_the_baseline(monkeypatch):
    monkeypatch.setenv(cpu.SKIP_ENV, "1")
    cpu.check_cpu("x86-64-v3", machine="x86_64", plat="linux", flags=["sse2"])


def test_windows_checks_avx2():
    cpu.check_cpu("x86-64-v3", machine="AMD64", plat="win32", windows_missing=[])
    with pytest.raises(ArcadeDBError, match="AVX2"):
        cpu.check_cpu(
            "x86-64-v3", machine="AMD64", plat="win32", windows_missing=["AVX2"]
        )


def test_macos_and_unknown_machines_pass():
    cpu.check_cpu("x86-64-v3", machine="arm64", plat="darwin")
    cpu.check_cpu("x86-64-v3", machine="x86_64", plat="darwin")
    cpu.check_cpu("x86-64-v3", machine="riscv64", plat="linux", flags=["x"])
