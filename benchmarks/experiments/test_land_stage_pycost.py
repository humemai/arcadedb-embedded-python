"""land_stage pulls the Python-cost file of the pin and commits it (the 26.10.1 chain's qRJ, CAMPAIGN section 7 row 29).

Run with `python -m pytest test_land_stage_pycost.py -q -rs` from this directory.

qRJ is a host-side stage: it writes $HOME/pycost/mini_results_<pin>.csv outside the tree, and the landing is what puts it where
export_web reads it (`jpype_overhead/results/mini_results_<pin>.csv`, preferred over the tracked file) and commits it. Without the step
a qRJ landing published the table from the September file with every gate green.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage as L  # noqa: E402


def _runner(tmp_path, content):
    calls = []

    def run(cmd, check=True):
        calls.append(cmd)
        if content is not None:
            Path(cmd[-1]).write_text(content)
    return run, calls


def test_a_landing_scoped_away_from_pycost_does_not_touch_it(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "PYCOST_DIR", tmp_path)
    run, calls = _runner(tmp_path, "x,RESULT,1\n")
    assert L.pull_pycost("d36b4ca3a", {"l2", "e2"}, run=run) is None and calls == []


def test_the_file_is_pulled_by_pin_and_counted(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(L, "PYCOST_DIR", tmp_path)
    run, calls = _runner(tmp_path, "MINI,RUN1,j,RESULT,1\nMINI,RUN1,j,RESULT,2\nMINI,RUN1,j,PROVENANCE,{}\n")
    got = L.pull_pycost("d36b4ca3a", set(), host="mini", run=run)
    assert got == tmp_path / "mini_results_d36b4ca3a.csv" and got.exists()
    assert calls[0][:3] == ["scp", "-q", "mini:~/pycost/mini_results_d36b4ca3a.csv"]
    assert "2 RESULT line(s)" in capsys.readouterr().out
    assert L.pull_pycost("d36b4ca3a", {"pycost"}, run=run) == got        # named explicitly, still lands


def test_no_file_on_the_host_yet_is_said_and_leaves_nothing_behind(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(L, "PYCOST_DIR", tmp_path)
    run, _ = _runner(tmp_path, None)
    assert L.pull_pycost("d36b4ca3a", set(), run=run) is None
    assert "has not run at this pin" in capsys.readouterr().out and not list(tmp_path.iterdir())


def test_an_empty_file_is_not_a_table_and_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "PYCOST_DIR", tmp_path)
    run, _ = _runner(tmp_path, "\n")
    assert L.pull_pycost("d36b4ca3a", set(), run=run) is None and not list(tmp_path.iterdir())


def test_the_landing_commits_what_it_pulled_and_the_path_is_where_export_web_reads():
    src = (HERE / "land_stage.py").read_text()
    assert "[str(_pycost.relative_to(REPO))] if _pycost else []" in src
    assert "_pycost = pull_pycost(args.pin," in src
    ew = (HERE / "export_web.py").read_text()
    assert 'OVERHEAD.with_name(f"mini_results_{os.environ[\'BENCH_ENGINE_COMMIT\'].strip()}.csv")' in ew
    assert L.PYCOST_DIR == HERE.parent / "python-bindings" / "jpype_overhead" / "results"
