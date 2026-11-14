"""Build-only rows of a rerun that have NO cell underneath them (2026-11-14, first landing of the n=3 rows).

The post2 rerun built every in-process ArcadeDB graph cell, including l2/sf1full/olap with the GAV default arm (gav=True, 6 rows: 3 reps on
each wheel). The 26.11.1 chains measured sf1full with GAV off only (make_2611_stages `_GAV_OFF`), so those rows have no full cell of an older
wheel to be merged into, `post1_rows.resolve` refuses them as a problem, and the whole landing stops with nothing merged.

`resolve(..., orphans="leave-out")` is the explicit, named exception: a build-only set with NO older wheel at all is left out of the landing and
listed by name in the decisions (a build-only row has no timed figure, so it is not a cell and there is nothing to publish); a set that
has a base cell which is short of repetitions, or build-only rows that are themselves short, stay problems. land_stage passes it with
`--post1-orphans leave-out`; the default is `refuse`, as before.

Light: pure Python, temporary files, no network. Run with pytest, or as plain functions from this directory.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import post1_rows as P  # noqa: E402


def _bo(rep, gav, label="26.11.1.post2"):
    return {"lane": "l2", "scale": "sf1full", "workload": "olap", "backend": "arcadedb_graph_embedded", "rep": rep, "gav": gav,
            "ts_utc": f"2026-11-1{rep}T00:00:00Z", "engine_version": label, "wheel_label": label, "engine_backend": "native", "rc": 0,
            "durability_class": "relaxed", "build_s": 100.0 + rep, "peak_rss_mb": 400, P.ROW_KIND: P.KIND_BUILD_ONLY}


def _full(rep, gav):
    r = {k: v for k, v in _bo(rep, gav, label="26.11.1").items() if k not in (P.ROW_KIND, "wheel_label")}
    r.update({"ts_utc": f"2026-11-0{rep}T00:00:00Z", "warm_q1_p50_ms": 2.5, "peak_rss_mb": 900})
    return r


def test_orphan_build_only_rows_are_a_problem_by_default_and_left_out_on_request():
    rows = [_full(i, False) for i in (1, 2, 3)] + [_bo(i, False) for i in (1, 2, 3)] + [_bo(i, True) for i in (1, 2, 3)]
    _out, _dec, prob = P.resolve(rows, 3)
    assert len(prob) == 1 and "no full cell" in prob[0], prob
    out, dec, prob = P.resolve(rows, 3, orphans="leave-out")
    assert not prob, prob
    assert len(out) == 3 and all(r.get("gav") is False for r in out), [(r.get("gav"), r.get(P.ROW_KIND)) for r in out]
    assert all(r["build_figures_wheel"] == "26.11.1.post2" for r in out)
    left = [d for d in dec if "LEFT OUT" in d]
    assert len(left) == 1 and "build-only" in left[0] and "3 row(s)" in left[0], dec


def test_leave_out_does_not_hide_a_short_orphan_set_or_a_short_base():
    short_orphan = [_bo(i, True) for i in (1, 2)]
    _o, _d, prob = P.resolve(short_orphan, 3, orphans="leave-out")
    assert len(prob) == 1 and "reps [1, 2] of the 3" in prob[0], prob
    short_base = [_full(i, True) for i in (1, 2)] + [_bo(i, True) for i in (1, 2, 3)]
    _o, _d, prob = P.resolve(short_base, 3, orphans="leave-out")
    assert len(prob) == 1 and "no complete cell" in prob[0], prob
    try:
        P.resolve([], 3, orphans="drop")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown orphans mode must be refused")


def test_land_stage_dry_run_passes_the_mode_through():
    import land_stage as L
    rows = [_full(i, False) for i in (1, 2, 3)]
    post = [_bo(i, False) for i in (1, 2, 3)] + [_bo(i, True) for i in (1, 2, 3)]
    for r in rows:
        r.update({"instrument": "2026-11", "engine_commit": "abc123def"})
    for r in post:
        r.update({"instrument": "2026-11", "engine_commit": "abc123def"})
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pulled, postf, scratch = root / "pulled.jsonl", root / "post.jsonl", root / "scratch"
        scratch.mkdir()
        (root / "results").mkdir()
        pulled.write_text("".join(json.dumps(r) + "\n" for r in rows))
        postf.write_text("".join(json.dumps(r) + "\n" for r in post))

        def sh(cmd, **kw):
            if cmd[0] == "scp" and str(cmd[-1]).endswith("runs_page_host_post2.jsonl"):
                shutil.copyfile(postf, cmd[-1])
            return mock.Mock(returncode=0)

        results = {}
        for mode in ("refuse", "leave-out"):
            argv = ["land_stage.py", "--pin", "abc123def", "--post1-reps", "3", "--post-tag", "post2", "--dry-run", "--message", "m"]
            if mode == "leave-out":
                argv += ["--post1-orphans", "leave-out"]
            env = {**__import__("os").environ, "BENCH_LAND_PULLED_FILE": str(pulled)}
            out = io.StringIO()
            with mock.patch.object(sys, "argv", argv), mock.patch.object(L, "SCRATCH", scratch), mock.patch.object(L.os, "environ", env), \
                    mock.patch.object(L, "RESULTS", root / "results"), mock.patch.object(L, "sh", sh), mock.patch.object(L.os, "execv", lambda *a, **k: None), \
                    mock.patch.object(L, "pull_pycost", lambda *a, **k: None), contextlib.redirect_stdout(out):
                try:
                    results[mode] = ("rc", L.main(), out.getvalue())
                except SystemExit as e:
                    results[mode] = ("exit", str(e.code), out.getvalue())
        assert results["refuse"][0] == "exit" and "no full cell" in results["refuse"][1], results["refuse"]
        assert results["leave-out"][0] == "rc" and results["leave-out"][1] == 0, results["leave-out"]
        assert "LEFT OUT" in results["leave-out"][2], results["leave-out"][2]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok  ", name)
