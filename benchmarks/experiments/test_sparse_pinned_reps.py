"""The sparse lane's pinned-rows guard follows the landing's n (the owner, 2026-11-14: n=3 is the only plan, n=4 and n=5 are dropped).

`make_paper_tables._pinned_sparse_rows` demanded five l3s rows per tier (`len(...) < 5`), so a landing at n=3 was "incomplete" and the
sparse table refused. The count is now `mp_builds()` (BENCH_MP_BUILDS, default 3), the same one reader the dense overlay uses
(humemai/mmdbbench#27). The rule is unchanged: all three tiers complete at one engine identity, else None; no row at all is `{}` (absent).

Plain functions with `unittest.mock`, no pytest fixture: run under pytest or as `python test_sparse_pinned_reps.py`.
"""
import contextlib
import io
import os
import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PIN = "abcdef1234567"
ARM = "arcadedb_sparse_embedded"
TIERS = ("tiny", "small", "medium")


def _rows(per_tier, builds=("jvm",), tiers=TIERS, short=None):
    """Synthetic l3s rows at the pin: `per_tier` rows per tier per build; `short` = (build, tier, n) gives that cell n rows instead."""
    out = []
    for b in builds:
        for t in tiers:
            n = short[2] if short and short[:2] == (b, t) else per_tier
            for rep in range(1, n + 1):
                out.append({"lane": "l3s", "backend": ARM, "scale": t, "rep": rep, "engine_commit": PIN, "engine_version": "26.11.1",
                            "engine_backend": b})
    return out


def _call(rows, bench_mp_builds=None, build=None):
    """(result of _pinned_sparse_rows, stderr text) with the pin set, BENCH_MP_BUILDS set or removed, and load_canonical replaced."""
    import make_paper_tables as M
    err = io.StringIO()
    with mock.patch.dict(os.environ), mock.patch.object(M, "load_canonical", lambda: rows), contextlib.redirect_stderr(err):
        os.environ["BENCH_ENGINE_COMMIT"] = PIN
        os.environ.pop("BENCH_MP_BUILDS", None)
        os.environ.pop("BENCH_ENGINE_BACKEND", None)
        if bench_mp_builds is not None:
            os.environ["BENCH_MP_BUILDS"] = str(bench_mp_builds)
        res = M._pinned_sparse_rows(ARM, build)
    return res, err.getvalue()


def test_three_rows_per_tier_are_complete_by_default():
    res, _ = _call(_rows(3))
    assert res is not None and set(res) == set(TIERS) and all(len(res[t]) == 3 for t in TIERS), res


def test_two_rows_in_one_tier_are_incomplete_by_default():
    res, err = _call(_rows(3, short=("jvm", "medium", 2)))
    assert res is None and "incomplete at ['medium']" in err, (res, err)


def test_a_landing_that_asks_for_five_needs_five_rows_per_tier():
    res, err = _call(_rows(3), bench_mp_builds=5)
    assert res is None and "incomplete at ['tiny', 'small', 'medium']" in err, (res, err)
    res, _ = _call(_rows(5), bench_mp_builds=5)
    assert res is not None and all(len(res[t]) == 5 for t in TIERS)


def test_no_row_at_all_is_absent_not_partial():
    res, _ = _call([])
    assert res == {}


def test_each_build_of_a_pair_needs_the_landing_count():
    both = _rows(3, builds=("jvm", "native"))
    res, _ = _call(both, build="all")
    assert res is not None and {len(v) for v in res.values()} == {6}, res
    short = _rows(3, builds=("jvm", "native"), short=("native", "small", 2))
    res, err = _call(short, build="all")
    assert res is None and "native build are incomplete" in err, (res, err)


def test_a_bad_count_refuses_and_names_the_variable():
    try:
        _call(_rows(3), bench_mp_builds="three")
    except SystemExit as e:
        assert "BENCH_MP_BUILDS" in str(e.code)
        return
    raise AssertionError("a bad BENCH_MP_BUILDS did not refuse")


def test_the_guard_holds_no_literal_five():
    import re
    src = (HERE / "make_paper_tables.py").read_text(encoding="utf-8")
    body = src[src.index("def _pinned_sparse_rows"):src.index("def _sparse_2681_rows")]
    assert not re.search(r"<\s*5\b|==\s*5\b|>=\s*5\b", body), "a literal 5 is still compared in _pinned_sparse_rows"


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
