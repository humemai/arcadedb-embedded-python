"""Three repetitions are the default of every harness entry point that starts or plans a run (the owner, 2026-11-14: "fix rep default to 3
everywhere"; the n=4 and n=5 passes are dropped, DECISIONS #335 and #336).

Plain functions, no pytest fixture: run under pytest or as `python test_reps_default_three.py`.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _default_of_reps_flag(path):
    src = path.read_text(encoding="utf-8")
    found = re.findall(r"add_argument\(\s*\"--reps\",\s*type=int,\s*default=(\w+)", src)
    assert len(found) == 1, (path.name, found)
    return found[0]


def test_runner_reps_default_is_three():
    assert _default_of_reps_flag(HERE / "runner.py") == "3"


def test_the_bindings_benchmark_reps_default_is_three():
    assert _default_of_reps_flag(HERE.parent / "python-bindings" / "run.py") == "3"


def test_no_usage_line_tells_a_reader_to_run_five_reps():
    for path in (HERE / "runner.py", HERE.parent / "python-bindings" / "run.py"):
        bad = [l for l in path.read_text(encoding="utf-8").splitlines() if re.match(r"^(Paper|Official run)[^\n]*--reps 5\b", l.strip())]
        assert not bad, (path.name, bad)


def test_the_post1_generator_refuses_more_than_three_reps():
    for n in ("4", "5"):
        r = subprocess.run([sys.executable, str(HERE / "make_post1_rerun_stages.py"), "--dry-run", "--reps", n],
                           cwd=HERE, capture_output=True, text=True, timeout=300)
        assert r.returncode != 0 and "--reps is 1 to 3" in (r.stdout + r.stderr), (n, r.stdout[-300:], r.stderr[-300:])


def test_the_sparse_second_pass_sentences_do_not_claim_five_builds():
    src = (HERE / "export_web.py").read_text(encoding="utf-8")   # source text: importing export_web needs the whole run environment
    assert "median of five builds" not in src and "against five in the table above" not in src


if __name__ == "__main__":
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                bad += 1
                print("FAIL", name, repr(e)[:300])
    raise SystemExit(1 if bad else 0)
