"""Selftests of the post1 rerun tooling (post1_rows.py, make_post1_rerun_stages.py). Pure Python: no docker, no JVM, no timing.
Run as `uv run --no-project python test_post1_rerun.py`, or under pytest."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_post1_rows_selftest():
    import post1_rows
    assert post1_rows.selftest() == 0


def test_stage_generator_selftest():
    import make_post1_rerun_stages
    assert make_post1_rerun_stages.selftest() == 0


def test_build_only_is_off_by_default_in_the_lanes_and_the_runner():
    here = os.path.dirname(os.path.abspath(__file__))
    for lane in ("l1_tpc.py", "l2_graph.py", "e2_hybrid.py", "l3d_dense.py"):
        src = open(os.path.join(here, lane), encoding="utf-8").read()
        assert src.count('os.environ.get("BENCH_BUILD_ONLY") == "1"') == 1, lane
        assert src.count("post1_rows.finish_build_only(") == 1, lane
    runner = open(os.path.join(here, "runner.py"), encoding="utf-8").read()
    assert 'os.environ["BENCH_BUILD_ONLY"] = "1"' in runner and runner.count("if args.build_only:") == 1


if __name__ == "__main__":
    rc = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                print("FAIL", name, e)
                rc = 1
    sys.exit(rc)
