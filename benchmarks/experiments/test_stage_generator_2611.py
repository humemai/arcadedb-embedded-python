"""make_2611_stages.py: the next instrument's subset stages (selection, instrument, chain, release mode, refusals).

Run with `python -m pytest test_stage_generator_2611.py -q` from this directory.
"""
import os
import re
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2611_stages as G  # noqa: E402

COMMIT = "e854692736b48971f92dff78a1e727bc570bb6a2"
WHEEL = "arcadedb_embedded-26.10.2-cp312-cp312-manylinux_2_34_x86_64.whl"
REL_WHEEL = "arcadedb_embedded-26.11.1-cp312-cp312-manylinux_2_34_x86_64.whl"
DIGEST = "sha256:" + "ab" * 32
WSHA = "cd" * 32


def run(args, tmp_path=None, env_extra=None, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in ("BENCH_INSTRUMENT",) + tuple(drop)}
    if tmp_path is not None:
        wheel = tmp_path / WHEEL
        wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
        env.update(ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:e85469273", ARCADEDB_ENGINE_COMMIT=COMMIT)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(HERE / "make_2611_stages.py")] + args, cwd=HERE, env=env,
                          capture_output=True, text=True)


def waits(path):
    return re.findall(r'^while ! grep -qx "(\S+) ALL-DONE"', path.read_text(), re.M)


@pytest.fixture(scope="module")
def drafts(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("g")
    out = tmp / "stages"
    r = run(["--second-list", "--after", "qR20", "--out", str(out)], tmp)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    return out


def test_every_arm_is_in_the_subset_or_declared_outside():
    assert G.arm_problems() == []
    assert G.arm_problems(["brand_new_graph"]) != []


def test_every_stage_exports_the_instrument_and_writes_its_own_rows_file(drafts):
    files = sorted(drafts.glob("*.sh"))
    assert len(files) >= 10
    for f in files:
        t = f.read_text()
        assert re.search(r"^export BENCH_INSTRUMENT=2026-11$", t, re.M), f.name
        assert "instrument 2026-10" not in t
        assert 'runs_page_${PIN}_2611.jsonl' in t and 'runs_page_${PIN}.jsonl' not in t
        assert re.search(r"^REPS=3 ", t, re.M)
        # the export comes before the first python call
        assert t.index("export BENCH_INSTRUMENT=2026-11") < t.index("python3 ")
    assert G.lint_drafts(str(drafts)) == []


def test_the_chain_waits_on_the_previous_stage_and_the_first_on_after(drafts):
    files = sorted(drafts.glob("*.sh"))
    assert waits(files[0]) == ["qR20"]
    for prev, cur in zip(files, files[1:]):
        assert waits(cur) == [prev.stem]


def test_after_none_means_no_wait_and_after_is_required(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", "none", "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    assert waits(out / "qS01.sh") == []
    r = run(["--lanes", "graph", "--out", str(tmp_path / "o2")], tmp_path)
    assert r.returncode != 0 and "--after is required" in (r.stdout + r.stderr)


def test_the_subset_has_no_arm_outside_it_and_no_comparator_in_the_arcadedb_stages(drafts):
    for f in drafts.glob("*.sh"):
        for b in re.findall(r'^BACKENDS="([^"]*)"', f.read_text(), re.M)[0].split():
            assert G.engine_of(b) is not None and G.engine_of(b) != "arcadedb", (f.name, b)


def test_biggest_cells_run_last_in_the_core_block_and_the_second_list_follows():
    specs = G.subset_specs(G.parse_engines(None, "comparators"), G.parse_lanes(None, True))
    titles = [s[1] for s in specs]
    last_core = [i for i, s in enumerate(specs) if s[2] in G.CORE_LANES][-3:]
    assert all("biggest cells" in titles[i] for i in last_core)
    assert [s[2] for s in specs[last_core[-1] + 1:]] == ["lifecycle", "l3s", "l4"]
    big = [s for s in specs if "biggest cells" in s[1]]
    assert any(s[2] == "l3d" and s[4] == ["deep10m"] and all(b.startswith("memgraph_dense") for b in s[8]) for s in big)
    assert any(s[2] == "l1tpc" and s[4] == ["tpch1"] and all(b.startswith("surrealdb_tpc") for b in s[8]) for s in big)
    assert any(s[2] == "l2" and s[4] == ["sf1full"] for s in big)


def test_split_stages_schedule_exactly_the_cells_of_the_unsplit_list():
    engines, lanes = G.parse_engines(None, "comparators"), G.parse_lanes(None, True)
    for order in ("biggest-last", "paper"):
        stages = G.number(G.subset_specs(engines, lanes, order), "x")
        assert G.stage_problems(stages, engines, lanes) == [], order


def test_timescaledb_is_in_the_time_series_stage_unless_opted_out():
    engines, lanes = G.parse_engines(None, "comparators"), ["l4"]
    assert "timescaledb" in G.subset_specs(engines, lanes)[0][8]
    assert "timescaledb" not in G.subset_specs(engines, lanes, skip=(G.TIMESCALEDB,))[0][8]
    r = run(["--check", "--second-list", "--lanes", "timeseries", "--without-timescaledb"])
    assert r.returncode == 0 and "timescaledb" not in r.stdout.lower().replace("completes", "")


def test_the_new_engines_are_in_the_subset():
    for b, eng in (("neo4j_graph", "neo4j"), ("neo4j_dense_int8", "neo4j"), ("qdrant_dense", "qdrant"),
                   ("qdrant_sparse_uint8", "qdrant"), ("ladybug_graph", "ladybug"), ("ladybug_e2", "ladybug"),
                   ("timescaledb", "postgresql"), ("composed_qdrant_neo4j", "qdrant-neo4j")):
        assert G.engine_of(b) == eng, b
    assert G.engine_of("neo4j_e2") is None and G.is_outside("neo4j_e2")


# ------------------------------------------------------------------------------------------- --check refusals
def test_check_passes_for_the_default_selection():
    r = run(["--check", "--second-list"])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]


def test_check_refuses_an_engine_not_in_the_subset():
    r = run(["--check", "--engines", "falkordb"])
    assert r.returncode != 0 and "not in the subset" in (r.stdout + r.stderr)


def test_arcadedb_is_refused_in_the_comparator_mode_and_comparators_in_the_release_mode():
    r = run(["--check", "--engines", "arcadedb"])
    assert r.returncode != 0 and "--arcadedb-release" in (r.stdout + r.stderr)
    r = run(["--check", "--engines", "sqlite"] + _release_args())
    assert r.returncode != 0 and "ArcadeDB alone" in (r.stdout + r.stderr)


def test_check_refuses_another_instrument_in_the_environment():
    # refused by whichever layer sees it first: bench_common at import (it measures one instrument), or the generator's own check
    r = run(["--check"], env_extra={"BENCH_INSTRUMENT": "2026-10"})
    out = r.stdout + r.stderr
    assert r.returncode != 0 and ("mix" in out or "measures only" in out), out[-400:]


def test_second_list_lanes_need_the_flag():
    r = run(["--check", "--lanes", "sparse"])
    assert r.returncode != 0 and "--second-list" in (r.stdout + r.stderr)


def test_stage_problems_catch_an_arm_outside_the_subset():
    engines, lanes = G.parse_engines(None, "comparators"), ["l2"]
    stages = G.number(G.subset_specs(engines, lanes), "x")
    bad = list(stages[0])
    bad[8] = list(bad[8]) + ["falkordb_graph"]
    probs = G.stage_problems([tuple(bad)] + stages[1:], engines, lanes)
    assert any("falkordb_graph" in p and "not in the subset" in p for p in probs)


def test_lint_catches_an_unset_instrument_a_shared_rows_file_and_a_foreign_arm():
    good = ('export BENCH_INSTRUMENT=2026-11\nRF="runs_page_${PIN}_2611.jsonl"\nBACKENDS="sqlite duckdb"\n'
            'is not the wheel this chain was generated for\n')
    assert G.lint_draft(good, "s.sh") == []
    assert G.lint_draft(good.replace("export BENCH_INSTRUMENT=2026-11\n", ""), "s.sh")
    assert G.lint_draft(good.replace("_2611", ""), "s.sh")
    assert G.lint_draft(good.replace("sqlite", "falkordb_graph"), "s.sh")
    assert G.lint_draft(good + "say START instrument 2026-10\n", "s.sh")


# ---------------------------------------------------------------------------------------------- release mode
def _release_args(**over):
    a = {"--arcadedb-release": "26.11.1", "--engine-commit": "1" * 40, "--image-digest": DIGEST, "--wheel-name": REL_WHEEL,
         "--wheel-sha256": WSHA, "--wheel-url": "https://files.pythonhosted.org/packages/x/" + REL_WHEEL}
    a.update(over)
    return [x for kv in a.items() for x in kv if x is not None]


def test_release_mode_refuses_without_the_digests():
    r = run(["--check", "--arcadedb-release", "26.11.1"])
    assert r.returncode != 0 and "not given" in (r.stdout + r.stderr) and "--image-digest" in (r.stdout + r.stderr)
    for bad in ({"--image-digest": "sha256:abc"}, {"--wheel-sha256": "zz"}, {"--arcadedb-release": "26.11.1-SNAPSHOT"},
                {"--wheel-name": WHEEL}, {"--engine-commit": "abc"}):
        r = run(["--check"] + _release_args(**bad))
        assert r.returncode != 0 and "REFUSING" in (r.stdout + r.stderr), bad


def test_release_mode_writes_the_pair_install_and_arcadedb_only_stages(tmp_path):
    out = tmp_path / "rel"
    r = run(_release_args() + ["--after", "qS12", "--id-prefix", "qT", "--lanes", "graph,dense", "--out", str(out)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    pair = (out / "qT00.sh").read_text()
    assert DIGEST in pair and WSHA in pair and "build_matched_pair.sh" in pair and waits(out / "qT00.sh") == ["qS12"]
    assert waits(out / "qT01.sh") == ["qT00"]
    for f in sorted(out.glob("qT0[1-9].sh")):
        t = f.read_text()
        assert f'"{WSHA}"' in t or WSHA in t
        assert "export BENCH_INSTRUMENT=2026-11" in t
        assert all(b.startswith("arcadedb") for b in re.findall(r'^BACKENDS="([^"]*)"', t, re.M)[0].split())


def test_projection_prices_the_lane_cells_of_each_stage(tmp_path):
    engines, lanes = ["duckdb"], ["l2"]
    stages = G.number(G.subset_specs(engines, lanes, "paper"), "x")
    tsv = tmp_path / "h.tsv"
    rows = ["lane\tworkload\tscale\tbackend\tclass\th3\th5\tkind"]
    cells = [c for st in stages for c in G.stage_cells(st) if c.kind == "lane" and not c.arm]
    for c in cells[1:]:   # the first cell has no row
        rows.append(f"{c.lane}\t{c.workload}\t{c.scale}\t{c.backend}\t{c.cls}\t1.0\t2.0\tclean reps")
    tsv.write_text("\n".join(rows) + "\n")
    for reps, per in ((3, 1.0), (5, 2.0)):
        priced = G.project_hours(stages, G.load_hours(str(tsv), reps))
        assert sum(h for _s, h, _n, _m in priced) == pytest.approx(per * (len(cells) - 1))
        assert sum(m for _s, _h, _n, m in priced) == 1
    with pytest.raises(SystemExit):
        G.load_hours(str(tsv), 4)


# ------------------------------------------------------------------------------------ the ArcadeDB pair's guards
PAIR_GUARDS = ("wheels in dist/", "no server image", "ABORT: dbbench:arcadedb carries wheel",
               "ABORT: dbbench:arcadedb runs JPype", "ABORT: pair unverified at the pin")
WHEEL_GUARDS = ("is not in dist/", "is not the wheel this chain was generated for")


def test_a_comparator_only_stage_guards_the_wheel_it_bakes_and_nothing_of_the_arcadedb_arms(drafts):
    for f in sorted(drafts.glob("*.sh")):
        t = f.read_text()
        # what the image build needs: the pinned wheel at its path with its sha256, exported BEFORE build_images.sh
        for g in WHEEL_GUARDS:
            assert g in t, (f.name, g)
        assert t.index("is not the wheel this chain was generated for") < t.index("export ARCADEDB_WHEEL=") < t.index("./build_images.sh")
        assert re.search(r'^export ARCADEDB_WHEEL="\$W" ARCADEDB_SERVER_IMAGE="arcadedb-c25:e85469273"$', t, re.M), f.name
        # what concerns the ArcadeDB arms themselves
        for g in PAIR_GUARDS:
            assert g not in t, (f.name, g)
        assert "--entrypoint python3 dbbench:arcadedb" not in t
        assert "./verify_pair_c25.sh" not in t and "docker image inspect \"$ARCADEDB_SERVER_IMAGE\"" not in t
        assert "export ARCADEDB_ENGINE_COMMIT=$PIN" in t
        assert "arcadedb" not in re.findall(r"^BENCH_ALLOW_DEV=0 \./build_images\.sh (.*?) >>", t, re.M)[0].split()


def test_an_arcadedb_release_stage_keeps_every_guard_of_the_pair(tmp_path):
    out = tmp_path / "rel"
    r = run(_release_args() + ["--after", "none", "--id-prefix", "qT", "--lanes", "graph", "--out", str(out)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    stages = sorted(out.glob("qT0[1-9].sh"))
    assert stages
    for f in stages:
        t = f.read_text()
        for g in PAIR_GUARDS + WHEEL_GUARDS:
            assert g in t, (f.name, g)
        assert re.findall(r"^BENCH_ALLOW_DEV=0 \./build_images\.sh (.*?) >>", t, re.M)[0].split()[0] == "arcadedb"
        assert t.index("is not the wheel this chain was generated for") < t.index("./build_images.sh") < t.index("pair unverified")


def test_the_lint_demands_the_pair_guards_exactly_where_an_arcadedb_arm_runs(tmp_path):
    base = ('export BENCH_INSTRUMENT=2026-11\nRF="runs_page_${PIN}_2611.jsonl"\n')
    wheel = "is not the wheel this chain was generated for\n"
    guards = wheel + "wheels in dist/\nABORT: no server image\nABORT: dbbench:arcadedb carries wheel\nABORT: pair unverified at the pin\n"
    assert G.lint_draft(base + 'BACKENDS="arcadedb_graph_embedded"\n' + guards, "s.sh") == []
    assert G.lint_draft(base + 'BACKENDS="arcadedb_graph_embedded"\n' + wheel, "s.sh")
    assert G.lint_draft(base + 'BACKENDS="duckpgq_graph"\n' + wheel, "s.sh") == []
    assert G.lint_draft(base + 'BACKENDS="duckpgq_graph"\n', "s.sh")
    comp = G.lint_draft(base + 'BACKENDS="duckpgq_graph"\n' + guards, "s.sh")
    assert any("guards one wheel in dist/" in p for p in comp)


# ------------------------------------------------------------------------------- an ABORT hands on (CAMPAIGN rule)
def _abort_trap(text):
    return re.search(r"""^trap 'echo "\$ID ALL-DONE" >> "\$S"' EXIT$""", text, re.M)


def test_the_all_done_trap_is_set_before_the_first_guard_that_can_abort(drafts, tmp_path):
    rel = tmp_path / "rel"
    r = run(_release_args() + ["--after", "none", "--id-prefix", "qT", "--out", str(rel)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    for f in sorted(drafts.glob("*.sh")) + sorted(rel.glob("*.sh")):
        t = f.read_text()
        m = _abort_trap(t)
        assert m, f.name
        assert m.start() < t.index("$ID ABORT"), f.name
        assert t.index('ALL-DONE" "$S"') < m.start() if 'while ! grep -qx' in t else True   # set after the wait, never inside it


def test_a_pre_start_abort_writes_the_marker_so_the_chain_goes_on(tmp_path):
    out = tmp_path / "o"
    r = run(["--after", "none", "--lanes", "graph", "--out", str(out)], tmp_path)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    home = tmp_path / "home"
    home.mkdir()                       # no repo here: the first guard (git pull) fails, long before the START line
    p = subprocess.run(["bash", str(out / "qS01.sh")], env={"HOME": str(home), "PATH": os.environ["PATH"]},
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    lines = (home / "STATUS.txt").read_text().splitlines()
    assert "qS01 ABORT: pull" in lines[0] and "START" not in "".join(lines)
    assert lines[-1] == "qS01 ALL-DONE"


# ------------------------------------------------------------------------------------ the drafts, byte for byte
SHA_LIST = HERE / "stage_drafts_2611.sha256"
GENERATIONS = {
    # case: (arguments, whether the comparator pair comes from the environment)
    "comparators": (["--second-list", "--after", "qR20"], True),
    "comparators-paper-5reps": (["--second-list", "--order", "paper", "--reps", "5", "--after", "qR20", "--id-prefix", "qU"], True),
    "arcadedb-release": (None, False),
}


def drafts_sha256(tmp_path):
    """sha256 of every script three generations write: the comparators (default order, and paper order at 5 reps) and ArcadeDB
    alone on a release, all lanes and the second list. One line per script, `<sha256>  <case>/<name>`, sorted."""
    lines = []
    for case, (args, from_env) in GENERATIONS.items():
        out = tmp_path / case
        if args is None:
            args = _release_args() + ["--second-list", "--after", "none", "--id-prefix", "qV"]
        r = run(args + ["--out", str(out)], tmp_path if from_env else None)
        assert r.returncode == 0, case + r.stdout[-600:] + r.stderr[-600:]
        lines += [f"{sha256(f.read_bytes()).hexdigest()}  {case}/{f.name}" for f in sorted(out.glob("*.sh"))]
    return sorted(lines, key=lambda x: x.split("  ", 1)[1])


def test_the_drafts_are_the_ones_on_file(tmp_path):
    """A change to the template, the stage table, a pin the stages bake in or the cap rule moves a draft. That is allowed, but
    never silently: review the diff of the drafts, then `python3 test_stage_generator_2611.py --rewrite` and commit the list."""
    assert SHA_LIST.read_text().splitlines() == drafts_sha256(tmp_path)


if __name__ == "__main__":
    if sys.argv[1:] != ["--rewrite"]:
        raise SystemExit("usage: python3 test_stage_generator_2611.py --rewrite   (regenerates stage_drafts_2611.sha256)")
    with tempfile.TemporaryDirectory() as d:
        SHA_LIST.write_text("\n".join(drafts_sha256(Path(d))) + "\n")
    print(f"wrote {SHA_LIST.name}")
