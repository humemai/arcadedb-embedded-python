"""make_2611_stages.py emits the subset REP-MAJOR and in engine priority order (the user, 2026-10-23: "order the comparators in
priority ... do n=1 for all dbs and then do the n=2, etc.").

Run with `python -m pytest test_stage_generator_repmajor.py -q` from this directory.

Pass 1 of every stage first (core lanes, then the second list), then pass 2, then pass 3. Inside a lane the engines run in
ENGINE_PRIORITY. A stage runs one repetition (`--only-reps $PASS`); a pass above 1 runs a cell only when rep 1 of it was clean
(the rep-1-first rule), and the state that says which reps exist is a file, so a pass can be stopped and the next one resumed
with no regeneration. The bash is exercised for real here, against a stub runner.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2611_stages as G  # noqa: E402
from test_stage_generator_2611 import run, waits  # noqa: E402


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rm")
    out = tmp / "stages"
    r = run(["--second-list", "--after", "none", "--status-file", "none", "--reps", "3", "--out", str(out)], tmp)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    return out


def stage_pass(path):
    return int(re.search(r"^PASS=(\d+)", path.read_text(), re.M).group(1))


def test_the_chain_is_pass_1_of_every_stage_then_pass_2_then_pass_3(chain):
    files = sorted(chain.glob("*.sh"))
    passes = [stage_pass(f) for f in files]
    assert passes == sorted(passes) and set(passes) == {1, 2, 3}
    per_pass = [passes.count(p) for p in (1, 2, 3)]
    assert per_pass[0] >= 10 and per_pass[1] <= per_pass[0] and per_pass[2] <= per_pass[1]
    # the stages of a later pass are pass-1 stages, in the same order
    def roster(f):
        return re.search(r'^BACKENDS="([^"]*)"', f.read_text(), re.M).group(1)
    first = [roster(f) for f in files if stage_pass(f) == 1]
    second = [roster(f) for f in files if stage_pass(f) == 2]
    it = iter(first)
    assert all(any(r == x for x in it) for r in second)
    for prev, cur in zip(files, files[1:]):
        assert waits(cur) == [prev.stem]
    assert "rep pass 2 of 3" in files[per_pass[0]].read_text()


def test_every_cell_runs_one_rep_and_the_state_file_drives_the_passes(chain):
    for f in chain.glob("*.sh"):
        t = f.read_text()
        assert '--only-reps "$PASS"' in t and "--only-reps 1 " not in t and 'seq -s, 2 "$REPS"' not in t, f.name
        assert "rep_gate" in t and "REPSTATE=$HOME/rep-state-2026-11-$PIN.tsv" in t


def test_engines_run_in_priority_order_inside_every_stage(chain):
    for f in chain.glob("*.sh"):
        bes = re.search(r'^BACKENDS="([^"]*)"', f.read_text(), re.M).group(1).split()
        ranks = [G.engine_rank(b) for b in bes]
        assert ranks == sorted(ranks), (f.name, bes)
    # the stated order, on the documents lane that holds the most engines
    spec = next(s for s in G.subset_specs(G.parse_engines(None, "comparators"), G.parse_lanes("documents", False)))
    engs = []
    for b in G.stage_backends(spec):
        e = G.engine_of(b)
        if not engs or engs[-1] != e:
            engs.append(e)
    want = [e for e in G.ENGINE_PRIORITY if e in engs]
    assert engs == want and len(engs) >= 4   # (SurrealDB's documents cells at tpch1 are the biggest and have their own stage)


def test_priority_names_every_subset_engine_and_arcadedb_leads():
    assert set(G.ENGINES) <= set(G.ENGINE_PRIORITY)
    assert G.ENGINE_PRIORITY[0] == "arcadedb"
    assert list(G.ENGINE_PRIORITY[1:13]) == ["surrealdb", "arangodb", "postgresql", "mongodb", "redis", "qdrant-neo4j", "neo4j",
                                              "qdrant", "duckdb", "sqlite", "memgraph", "ladybug"]
    assert G.ENGINE_PRIORITY[-1] == "cratedb"
    # an engine whose adapter is not merged (cratedb) is not in ENGINES: skipped cleanly, nothing breaks; redis joined with its dense arm
    assert "redis" in G.ENGINES and "cratedb" not in G.ENGINES


def test_a_single_rep_keeps_the_ids_and_one_pass(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", "none", "--status-file", "none", "--reps", "1", "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 0
    assert {stage_pass(f) for f in out.glob("*.sh")} == {1}


# ------------------------------------------------------------------------------------------ the bash, for real
HARNESS = r"""
set -u
T=$1; PASS=$2; shift 2
S=$T/status; ID=qT; PIN=abc123; export HOME=$T; RF=rows.jsonl; REPS=${REPS:-3}; lane=l1tpc
say() { echo "$*" >> "$S"; }
cat "$T/helpers.sh" > "$T/h.sh"
source "$T/h.sh"
export PATH=$T/bin:$PATH
"$@"
"""


def _helpers(chain):
    t = (chain / "qS03.sh").read_text() if (chain / "qS03.sh").exists() else next(iter(sorted(chain.glob("*.sh")))).read_text()
    a = t.index("declare -A CENSORED_AT")
    m = re.search(r"^run_cell\(\) \{.*?^\}\n", t[a:], re.M | re.S)
    return t[a:a + m.end()]


@pytest.fixture()
def env(tmp_path, chain):
    (tmp_path / "bin").mkdir()
    stub = tmp_path / "bin" / "python3"
    stub.write_text('#!/bin/bash\necho "$*" >> "$T_CALLS"\nexit "$(cat "$T_RC")"\n')
    stub.chmod(0o755)
    (tmp_path / "helpers.sh").write_text(_helpers(chain))
    return tmp_path


def cell(env, pass_no, label, rc=0, reps=3):
    (env / "rc").write_text(str(rc))
    e = dict(os.environ, T_CALLS=str(env / "calls"), T_RC=str(env / "rc"), REPS=str(reps))
    p = subprocess.run(["bash", "-c", HARNESS, "bash", str(env), str(pass_no), "run_cell", label, "tpch1", "600", "surrealdb_tpc",
                        "q1", ""], env=e, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    calls = (env / "calls").read_text().splitlines() if (env / "calls").exists() else []
    return calls


def test_pass_1_runs_rep_1_and_pass_2_runs_rep_2_only_after_a_clean_rep_1(env):
    c = cell(env, 1, "l1tpc/tpch1/surrealdb_tpc/q1")
    assert len(c) == 1 and "--only-reps 1 " in c[0] and "--reps 3" in c[0]
    c = cell(env, 2, "l1tpc/tpch1/surrealdb_tpc/q1")
    assert len(c) == 2 and "--only-reps 2 " in c[1]
    c = cell(env, 3, "l1tpc/tpch1/surrealdb_tpc/q1")
    assert len(c) == 3 and "--only-reps 3 " in c[2]
    # a cell that never ran rep 1 is not run at pass 2
    before = len((env / "calls").read_text().splitlines())
    c = cell(env, 2, "l1tpc/tpch1/other/q1")
    assert len(c) == before
    assert "no clean rep 1, rep 2 not run" in (env / "status").read_text()


def test_a_failed_rep_1_is_not_repeated_and_a_restart_retries_it(env):
    assert len(cell(env, 1, "L", rc=1)) == 1
    assert len(cell(env, 2, "L")) == 1          # pass 2: rep 1 left no clean row, so nothing ran
    assert "rep 1 failed, not repeating it" in (env / "status").read_text()
    assert len(cell(env, 1, "L")) == 2          # the restart of pass 1 retries the failed cell ...
    assert len(cell(env, 1, "L")) == 2          # ... and a clean rep 1 is not rerun by a second restart
    assert len(cell(env, 2, "L")) == 3          # now pass 2 may run it


def test_a_stage_with_fewer_reps_stops_after_them(env):
    assert len(cell(env, 1, "M", reps=2)) == 1 and len(cell(env, 2, "M", reps=2)) == 2
    assert len(cell(env, 3, "M", reps=2)) == 2   # REPS=2 declared: no third pass for this cell


def test_stopping_after_pass_2_leaves_a_state_a_third_pass_can_use(env):
    cell(env, 1, "Z"), cell(env, 2, "Z")
    st = (env / "rep-state-2026-11-abc123.tsv").read_text().splitlines()
    assert st == ["Z\t1\tok", "Z\t2\tok"]
    assert len(cell(env, 3, "Z")) == 3
