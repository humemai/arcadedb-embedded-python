"""The dense overlay's build count is a landing parameter (humemai/mmdbbench#27): `BENCH_MP_BUILDS`, default 3 (the owner, 2026-11-14: n=3 is the only plan, n=4 and n=5 are dropped).

`make_paper_tables.dense_mp_dir` hard-coded five builds per arm, so a campaign that landed at n=3 (three `mp_<arm>_b<k>.json`
files per arm) could never pass it. The count is now read from the environment in one place (`make_paper_tables.mp_builds()`).
The rule is unchanged: complete, absent, or refuse, pinned only, no fallback; only the number moves. The default is 3, so a
landing at n=3 needs no variable; BENCH_MP_BUILDS=5 still asks for five, and an arm missing at any n still refuses.

Plain functions with `unittest.mock` and no pytest fixture (the style of test_land_stage_branch.py), so they run under pytest or as
`python test_dense_mp_builds.py [name-substring ...]` from this directory. The last two of the first group and the end-to-end group
run the exporter on a copy of the publish fixture and need numpy and pandas, as the exporter does.
"""
import atexit
import contextlib
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PIN = "261100fix"
FIXTURE = HERE / "fixtures" / "publish_2611" / "results"


def _write(root, arms, builds, name="mp_{a}_b{b}.json"):
    root.mkdir(parents=True, exist_ok=True)
    for a in arms:
        for b in range(1, builds + 1):
            (root / name.format(a=a, b=b)).write_text("[]")


@contextlib.contextmanager
def _landing(builds=None):
    """(make_paper_tables, scratch results dir): the pin set, BENCH_MP_BUILDS set (or removed), and nothing left behind."""
    import make_paper_tables as M
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ), mock.patch.object(M, "RESULTS", d):
        os.environ["BENCH_ENGINE_COMMIT"] = PIN
        os.environ.pop("BENCH_MP_BUILDS", None)
        if builds is not None:
            os.environ["BENCH_MP_BUILDS"] = str(builds)
        yield M, Path(d)


def _refusal(fn, *args):
    """The message of the SystemExit the call raises; fails when it does not refuse."""
    try:
        fn(*args)
    except SystemExit as e:
        return str(e.code)
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not refuse")


def _big(M, d, builds):
    _write(d / f"dense_mp5_{PIN}", M.MP_ARMS, builds)
    return d / f"dense_mp5_{PIN}"


def _small(M, d, builds):
    _write(d / f"dense_mp5_small_{PIN}", M.MP_ARMS_SMALL, builds)
    return d / f"dense_mp5_small_{PIN}"


def test_three_builds_per_arm_pass_when_the_landing_says_three():
    with _landing(3) as (M, d):
        big, small = _big(M, d, 3), _small(M, d, 3)
        assert M.dense_mp_dir() == str(big)
        assert M.dense_mp_small_dir() == str(small)


def test_the_default_wants_three_and_names_the_count():
    with _landing() as (M, d):
        _big(M, d, 2), _small(M, d, 2)
        msg = _refusal(M.dense_mp_dir)
        assert "13 of 39 files missing" in msg and "3 builds per arm" in msg and "no fallback, re-run the arm" in msg
        msg = _refusal(M.dense_mp_small_dir)
        assert "10 of 30 files missing" in msg and "3 builds per arm" in msg


def test_three_builds_pass_by_default_and_five_only_when_the_landing_says_five():
    with _landing() as (M, d):
        big, small = _big(M, d, 3), _small(M, d, 3)
        assert M.dense_mp_dir() == str(big) and M.dense_mp_small_dir() == str(small)
        os.environ["BENCH_MP_BUILDS"] = "5"
        assert "files missing" in _refusal(M.dense_mp_dir) and "5 builds per arm" in _refusal(M.dense_mp_small_dir)
        _big(M, d, 5), _small(M, d, 5)
        assert M.dense_mp_dir() == str(big) and M.dense_mp_small_dir() == str(small)


def test_a_three_build_landing_names_three_in_its_refusal():
    with _landing(3) as (M, d):
        big = _big(M, d, 3)
        (big / "mp_qdrant_b3.json").unlink()
        msg = _refusal(M.dense_mp_dir)
        assert "1 of 39 files missing" in msg and "3 builds per arm" in msg and "mp_qdrant_b3.json" in msg


def test_a_missing_arm_refuses_at_any_n():
    for n in (3, 5):
        with _landing(n) as (M, d):
            big, small = _big(M, d, n), _small(M, d, n)
            for b in range(1, n + 1):
                (big / f"mp_chroma_b{b}.json").unlink()
                (small / f"mp_lancedb_b{b}.json").unlink()
            msg = _refusal(M.dense_mp_dir)
            assert f"{n} of {13 * n} files missing" in msg and "mp_chroma_b1.json" in msg, (n, msg)
            msg = _refusal(M.dense_mp_small_dir)
            assert f"{n} of {10 * n} files missing" in msg and "mp_lancedb_b1.json" in msg, (n, msg)


def test_an_arm_one_build_short_refuses_at_any_n():
    # at n=5 the parent refuses this too; at n=3 the parent refuses every three-build directory, so this is a control there
    for n in (3, 5):
        with _landing(n) as (M, d):
            big = _big(M, d, n)
            (big / f"mp_fp32_b{n - 1}.json").unlink()
            assert f"mp_fp32_b{n - 1}.json" in _refusal(M.dense_mp_dir)


def test_an_absent_overlay_is_still_not_a_refusal():
    for n in ("3", "5", None):
        with _landing(n) as (M, d):
            assert not os.path.isdir(M.dense_mp_dir())
            assert not os.path.isdir(M.dense_mp_small_dir())


def test_an_optional_arm_is_all_or_none_at_the_landing_count():
    with _landing(3) as (M, d):
        big = _big(M, d, 3)
        _small(M, d, 3)
        _write(big, ["pgvector"], 3)
        assert "pgvector" in M.mp_arms_present(small=False)
        (big / "mp_pgvector_b3.json").unlink()
        assert "optional arm pgvector has 2 of 3 builds" in _refusal(M.mp_arms_present, False)
        _write(big, ["pgvector"], 3)
        os.environ["BENCH_MP_BUILDS"] = "5"                     # a landing at n=5: the three files are a partial arm
        assert "optional arm pgvector has 3 of 5 builds" in _refusal(M._optional_arms_present, str(big), "x", ("pgvector",))
        assert "files missing" in _refusal(M.mp_arms_present, False)    # and the required arms refuse first


def test_the_native_overlay_is_all_or_none_at_the_landing_count():
    with _landing(3) as (M, d):
        big = _big(M, d, 3)
        _write(big, M.MP_INPROCESS_ARMS, 3, "mp_{a}_native_b{b}.json")
        assert M.dense_mp_dir() == str(big)
        (big / "mp_int8_native_b2.json").unlink()
        msg = _refusal(M.dense_mp_dir)
        assert "partial" in msg and "of 3 builds per arm" in msg
        _write(big, M.MP_INPROCESS_ARMS, 3, "mp_{a}_native_b{b}.json")
        os.environ["BENCH_MP_BUILDS"] = "5"
        assert "of 5 builds per arm" in _refusal(M._refuse_partial_native, str(big), "x")


def test_a_bad_count_refuses_and_names_the_variable():
    for raw in ("0", "-2", "three", "3.5", "1e1"):
        with _landing(raw) as (M, d):
            msg = _refusal(M.dense_mp_dir)
            assert "BENCH_MP_BUILDS" in msg and repr(raw) in msg, (raw, msg)


def test_a_blank_count_is_the_default_and_spaces_are_trimmed():
    with _landing("") as (M, d):
        assert M.mp_builds() == 3
        os.environ["BENCH_MP_BUILDS"] = " 5 "
        assert M.mp_builds() == 5
        os.environ["BENCH_MP_BUILDS"] = " 3 "
        assert M.mp_builds() == 3
        os.environ.pop("BENCH_MP_BUILDS")
        assert M.mp_builds() == M.MP_BUILDS_DEFAULT == 3


def test_the_variable_is_read_in_one_place():
    """Every reader of the build count calls make_paper_tables.mp_builds(); none reads the environment itself."""
    readers = []
    for fp in sorted(HERE.glob("*.py")):
        if fp.name.startswith("test_"):
            continue
        for i, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"environ(\.get\(|\[)\s*[\"']BENCH_MP_BUILDS[\"'](?!\]\s*=[^=])", line) or re.search(r"getenv\(\s*[\"']BENCH_MP_BUILDS", line):
                readers.append(f"{fp.name}:{i}")
    assert len(readers) == 1 and readers[0].startswith("make_paper_tables.py:"), readers


# --- land_stage --mp-builds N sets the one variable ----------------------------------------------------------------------------

def test_the_landing_flag_sets_the_variable_and_nothing_else():
    import land_stage as L
    with mock.patch.dict(os.environ):
        os.environ.pop("BENCH_MP_BUILDS", None)
        L.apply_mp_builds(0)                                    # the flag's default: the environment is left alone
        assert "BENCH_MP_BUILDS" not in os.environ
        L.apply_mp_builds(3)
        assert os.environ["BENCH_MP_BUILDS"] == "3"
        os.environ["BENCH_MP_BUILDS"] = "5"
        L.apply_mp_builds(3)                                    # the flag is the explicit one: it wins over the environment
        assert os.environ["BENCH_MP_BUILDS"] == "3"
        assert "at least 1" in _refusal(L.apply_mp_builds, -1)


def test_main_wires_the_flag_before_any_step_runs():
    import land_stage as L

    def forbidden(cmd, *a, **k):
        raise AssertionError(f"nothing may run before the refusal: {cmd}")

    argv = ["land_stage.py", "--pin", "abc123def", "--apply", "--message", "m", "--mp-builds", "3"]   # no --branch: refused right after
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ), mock.patch.object(sys, "argv", argv), \
            mock.patch.object(L, "SCRATCH", Path(d)), mock.patch.object(L, "sh", forbidden):
        os.environ.pop("BENCH_MP_BUILDS", None)
        msg = _refusal(L.main)
        assert "--apply needs --branch" in msg
        assert os.environ["BENCH_MP_BUILDS"] == "3"


# --- the page and the checks follow the variable, end to end -------------------------------------------------------------------

def _run(script, results, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("BENCH_")}
    env.update({"BENCH_RESULTS_DIR": str(results), "BENCH_ENGINE_COMMIT": PIN, "PYTHONHASHSEED": "0"}, **extra)
    return subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, env=env, capture_output=True, text=True, timeout=900)


_THREE = []


def _three_builds():
    """The publish fixture with builds 4 and 5 removed from both dense overlays: what a landing at n=3 pulls. Built once."""
    if _THREE:
        return _THREE[0]
    root = Path(tempfile.mkdtemp(prefix="dense-n3-"))
    atexit.register(shutil.rmtree, root, True)
    dest = root / "results"
    shutil.copytree(FIXTURE, dest)
    with gzip.open(dest / "runs.jsonl.gz", "rt") as src, open(dest / "runs.jsonl", "w") as out:
        shutil.copyfileobj(src, out)
    (dest / "runs.jsonl.gz").unlink()
    gone = 0
    for d in dest.glob("dense_mp5*"):
        for fp in list(d.glob("mp_*_b4.json")) + list(d.glob("mp_*_b5.json")):
            fp.unlink()
            gone += 1
    assert gone >= 2 * (13 + 10)          # at least the required arms of both sizes, two builds each
    _THREE.append(dest)
    return dest


def test_a_five_build_landing_refuses_the_three_build_fixture_and_names_the_count():
    proc = _run("make_paper_tables.py", _three_builds(), BENCH_MP_BUILDS="5")
    assert proc.returncode != 0
    assert "files missing" in proc.stderr and "5 builds per arm" in proc.stderr and "no fallback, re-run the arm" in proc.stderr


def test_the_tables_and_the_page_land_at_three_builds_by_default_and_say_three():
    res = _three_builds()
    proc = _run("make_paper_tables.py", res)             # no BENCH_MP_BUILDS: the default is three
    assert proc.returncode == 0, proc.stderr[-2000:]
    proc = _run("export_web.py", res)
    assert proc.returncode == 0, proc.stderr[-2000:]
    payload = json.loads((res / "web_benchmarks.json").read_text())
    dense = [t for t in payload["tables"] if t["id"] == "l3d"]
    assert dense
    text = " ".join(" ".join(t.get("conditions") or []) for t in dense)
    assert "over three builds" in text, text[-600:]
    assert "five builds" not in text and "over five" not in text
    # and an export that asks for five builds still refuses the same files
    assert _run("export_web.py", res, BENCH_MP_BUILDS="5").returncode != 0


if __name__ == "__main__":
    want = sys.argv[1:]
    bad = 0
    for name, fn in list(globals().items()):
        if not (name.startswith("test_") and callable(fn)) or (want and not any(w in name for w in want)):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except BaseException as e:  # noqa: BLE001 - a runner: report and go on
            bad += 1
            print(f"FAIL {name}: {type(e).__name__}: {str(e)[:300]}")
    print(f"{bad} failed")
    sys.exit(1 if bad else 0)
