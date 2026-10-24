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
    return re.findall(r'^while ! grep -qx "([^"]+?) ALL-DONE"', path.read_text(), re.M)


@pytest.fixture(scope="module")
def drafts(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("g")
    out = tmp / "stages"
    r = run(["--after", "qR20", "--status-file", "none", "--out", str(out)], tmp)   # the default profile: what ships
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
        assert re.search(r"^REPS=5 ", t, re.M)
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
    r = run(["--check", "--profile", "full", "--second-list", "--lanes", "timeseries", "--without-timescaledb"])
    assert r.returncode == 0 and "timescaledb" not in r.stdout.lower().replace("completes", "")


def test_the_new_engines_are_in_the_subset():
    for b, eng in (("neo4j_graph", "neo4j"), ("neo4j_dense_int8", "neo4j"), ("qdrant_dense", "qdrant"),
                   ("qdrant_sparse_uint8", "qdrant"), ("ladybug_graph", "ladybug"), ("ladybug_e2", "ladybug"),
                   ("timescaledb", "postgresql"), ("composed_qdrant_neo4j", "qdrant-neo4j"),
                   ("composed_embedded_sqlite_lance_ladybug", "composed-embedded")):
        assert G.engine_of(b) == eng, b
    assert G.engine_of("neo4j_e2") is None and G.is_outside("neo4j_e2")


def test_the_composed_embedded_arm_runs_in_tier_1_cross_model_beside_the_served_composed_stack():
    """The owner, 2026-10-25: SQLite + LanceDB + LadybugDB in one process joins the cross-model lanes (e2 and its atomicity workload)
    in Tier 1, in every pass, right after the composed Qdrant + Neo4j stack, with the same cells as any arm that has a durability
    setting: hybrid at both classes and atomicity at the relaxed one, at both sizes."""
    arm = "composed_embedded_sqlite_lance_ladybug"
    assert G.engine_of(arm) == "composed-embedded" and G.tier_of(arm) == 1 and not G.is_outside(arm)
    assert [lane for lane, spec in G.runner.LANES.items() if arm in spec[1]] == ["e2"]   # cross-model only
    assert G.runner.BACKENDS[arm]["topology"] == "embedded"
    stages, plan = tiered_plan(reps=3, second=False)
    e2 = [s for s in stages if s[2] == "e2" and G.stage_tier(s) == 1]
    assert len(e2) == 1
    names = G.stage_backends(e2[0])
    assert names.index(arm) == names.index("composed_qdrant_neo4j") + 1
    cells = {(c.workload, c.scale, c.cls) for c in G.stage_cells(e2[0]) if c.backend == arm}
    assert cells == {(w, sc, cl) for sc in ("e2", "e2_500k")
                     for w, cl in (("hybrid", "relaxed"), ("hybrid", "strict"), ("atomicity", "relaxed"))}
    # in every pass of Tier 1, and in no stage of Tier 2
    assert sorted(p for s, p in plan if arm in G.stage_backends(s)) == [1, 2, 3]
    assert all(G.stage_tier(s) == 1 for s, _p in plan if arm in G.stage_backends(s))


# ------------------------------------------------------------------------------------------- --check refusals
def test_check_passes_for_the_default_selection():
    for args in ([], ["--profile", "full", "--second-list"]):
        r = run(["--check"] + args)
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


def test_second_list_lanes_need_the_flag_and_the_full_profile():
    r = run(["--check", "--profile", "full", "--lanes", "sparse"])
    assert r.returncode != 0 and "--second-list" in (r.stdout + r.stderr)
    r = run(["--check", "--profile", "full", "--second-list", "--lanes", "sparse"])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]


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
    r = run(_release_args() + ["--after", "qS12", "--status-file", "none", "--id-prefix", "qT", "--lanes", "graph,dense", "--out", str(out)])
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
    gate = f"ABORT: no {G.GO_ARCADEDB_MARKER} (go-arcadedb-2611)\n"
    assert G.lint_draft(base + 'BACKENDS="arcadedb_graph_embedded"\n' + guards + gate, "s.sh") == []
    assert any("go-arcadedb-2611 gate" in p for p in G.lint_draft(base + 'BACKENDS="arcadedb_graph_embedded"\n' + guards, "s.sh"))
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


def test_the_arcadedb_chain_is_gated_on_the_go_marker_and_the_comparators_are_not(tmp_path):
    """DBBench: one ArcadeDB version per host. The ArcadeDB arms start only once CURRENT_PIN is 26.11.1, which the user or the agent
    says by touching the marker file; the comparator chain does not depend on the version and carries no gate."""
    out = tmp_path / "rel"
    r = run(_release_args() + ["--after", "qS12", "--status-file", "none", "--id-prefix", "qT", "--lanes", "graph,dense", "--out", str(out)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    pair = (out / "qT00.sh").read_text()
    marker = G.GO_ARCADEDB_MARKER
    assert marker.endswith("conf/go-arcadedb-2611")
    # the pair install waits for the comparator chain, THEN for the marker, and only then sets the ALL-DONE trap: a killed waiter hands nothing on
    i_after, i_go, i_trap = pair.index('grep -qx "qS12 ALL-DONE"'), pair.index(f'while [ ! -f "$GO" ]'), pair.index("trap 'echo")
    assert i_after < i_go < i_trap and f'GO="{marker}"' in pair
    assert "touch it when the benchmark pin" in pair
    # every ArcadeDB lane stage aborts without the marker (after the trap, so the abort still hands on) and lints clean
    for f in sorted(out.glob("qT0[1-9].sh")):
        text = f.read_text()
        assert f'[ -f "{marker}" ] || ' in text and f"ABORT: no {marker}" in text
        assert text.index("trap 'echo") < text.index(f"ABORT: no {marker}")
    assert G.lint_drafts(str(out), {"arcadedb"}) == []
    # a pair install or an ArcadeDB stage without the gate is a lint problem, and a comparator stage with it is too
    assert any("go-arcadedb-2611" in p for p in G.lint_draft(pair.replace("go-arcadedb-2611", "x"), "qT00.sh"))
    lane = (out / "qT01.sh").read_text()
    assert any("no go-arcadedb-2611 gate" in p for p in G.lint_draft(lane.replace(f"ABORT: no {marker}", "ABORT: no x"), "qT01.sh"))


def test_the_comparator_chain_carries_no_arcadedb_gate(drafts):
    assert all("go-arcadedb-2611" not in f.read_text() for f in drafts.glob("*.sh"))


def test_the_arcadedb_chain_runs_tier_1_passes_1_to_5_in_order(tmp_path):
    out = tmp_path / "rel"
    r = run(_release_args() + ["--after", "none", "--status-file", "none", "--id-prefix", "qT", "--lanes", "graph", "--out", str(out)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    passes = [int(m) for f in sorted(out.glob("qT0[1-9]*.sh")) for m in re.findall(r"^PASS=(\d+)", f.read_text(), re.M)]
    assert passes == sorted(passes) and set(passes) == {1, 2, 3, 4, 5}


# ------------------------------------------------------------------------------------ the drafts, byte for byte
SHA_LIST = HERE / "stage_drafts_2611.sha256"
GENERATIONS = {
    # case: (arguments, whether the comparator pair comes from the environment)
    # the default profile (paper-2611) is what ships; --profile full is covered by the selection tests, not by a hash list
    "comparators": (["--after", "qR20", "--status-file", "none"], True),   # engine tiers on, the default
    "comparators-no-tiers": (["--no-tiers", "--after", "qR20", "--status-file", "none"], True),
    "comparators-paper-5reps": (["--order", "paper", "--reps", "5", "--after", "qR20", "--status-file", "none", "--id-prefix", "qU"], True),
    "arcadedb-release": (None, False),
}


def drafts_sha256(tmp_path):
    """sha256 of every script four generations write, under the default profile (paper-2611): the comparators (default order with engine tiers, the same without
    them, and paper order at 5 reps) and ArcadeDB alone on a release, the core lanes. One line per script, `<sha256>  <case>/<name>`, sorted."""
    lines = []
    for case, (args, from_env) in GENERATIONS.items():
        out = tmp_path / case
        if args is None:
            args = _release_args() + ["--after", "none", "--id-prefix", "qV"]
        r = run(args + ["--out", str(out)], tmp_path if from_env else None)
        assert r.returncode == 0, case + r.stdout[-600:] + r.stderr[-600:]
        lines += [f"{sha256(f.read_bytes()).hexdigest()}  {case}/{f.name}" for f in sorted(out.glob("*.sh"))]
    return sorted(lines, key=lambda x: x.split("  ", 1)[1])


def test_the_drafts_are_the_ones_on_file(tmp_path):
    """A change to the template, the stage table, a pin the stages bake in or the cap rule moves a draft. That is allowed, but
    never silently: review the diff of the drafts, then `python3 test_stage_generator_2611.py --rewrite` and commit the list."""
    assert SHA_LIST.read_text().splitlines() == drafts_sha256(tmp_path)


# ------------------------------------------------------------------------------------------------------ engine tiers
# The user, 2026-10-24: "N=3 Tier 1 first, then Tier 2, then everything else later"; the exact order: n=1 T1, n=2 T1, n=3 T1, n=1 T2,
# n=2 T2, n=3 T2, n=4 T1, n=4 T2, n=5 T1, n=5 T2.
SCHEDULE_5 = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (1, 4), (2, 4), (1, 5), (2, 5)]
TIER1 = ("arcadedb_embedded", "arcadedb_server", "surrealdb_graph", "surrealdb_graph_server", "surrealdb_tpc", "arangodb_graph",
         "pgage_graph", "pgvector_dense", "pgvector_sparse", "postgres", "postgres_ts", "mongodb", "mongodb_dense",
         "composed_qdrant_neo4j", "composed_embedded_sqlite_lance_ladybug", "sqlite", "sqlite_vec_dense", "ladybug_dense", "duckdb",
         "duckdb_vss_dense", "duckpgq_graph")
TIER2 = ("memgraph_graph", "memgraph_dense", "neo4j_graph", "neo4j_dense", "qdrant_dense", "qdrant_sparse", "redis_dense",
         "cratedb_tpc", "timescaledb")


def tiered_plan(reps=5, second=True, tiers=True, order="biggest-last", engines=None):
    engines = G.parse_engines(engines, "comparators")
    lanes = G.parse_lanes(None, second)
    stages = G.number(G.subset_specs(engines, lanes, order, (), tiers), "qS")
    return stages, G.pass_plan(stages, reps, tiers)


def test_every_arm_has_the_tier_the_user_named_and_timescaledb_is_the_exception_in_its_engine():
    assert G.tier_table_problems() == []
    assert all(G.tier_of(b) == 1 for b in TIER1), [b for b in TIER1 if G.tier_of(b) != 1]
    assert all(G.tier_of(b) == 2 for b in TIER2), [b for b in TIER2 if G.tier_of(b) != 2]
    assert G.engine_of("timescaledb") == "postgresql" and G.tier_of("postgres") == 1   # an ARM_TIER entry, not a new engine
    # no registered arm of the subset is left without a tier
    assert all(G.tier_of(b) in (1, 2) for b in G.registered_arms() if not G.is_outside(b))


def groups_of(plan):
    """The plan collapsed into its (tier, pass) groups, in run order."""
    out = []
    for s, p in plan:
        if not out or out[-1] != (G.stage_tier(s), p):
            out.append((G.stage_tier(s), p))
    return out


def test_schedule_order_is_the_users_exact_order():
    assert G.schedule_order({1, 2}, 5) == SCHEDULE_5
    assert G.schedule_order({1, 2}, 3) == SCHEDULE_5[:6]              # N=3 stops after the first block
    assert G.schedule_order({1, 2}, 4) == SCHEDULE_5[:8]
    assert G.schedule_order({1}, 5) == [(1, p) for p in range(1, 6)]   # one tier: plain rep-major
    assert G.schedule_order({1, 2, 3}, 5)[:9] == [(t, p) for t in (1, 2, 3) for p in (1, 2, 3)]
    assert G.schedule_order({1, 2, 3}, 5)[9:] == [(1, 4), (2, 4), (3, 4), (1, 5), (2, 5), (3, 5)]


def test_a_stage_never_mixes_tiers_and_the_plan_follows_the_schedule():
    stages, plan = tiered_plan()
    assert all(len({G.tier_of(b) for b in G.stage_backends(s)}) == 1 for s, _ in plan)
    assert groups_of(plan) == SCHEDULE_5
    assert G.plan_problems(stages, 5, plan, True) == []
    stages3, plan3 = tiered_plan(reps=3)
    assert groups_of(plan3) == SCHEDULE_5[:6] and G.plan_problems(stages3, 3, plan3, True) == []


def test_every_prefix_of_the_schedule_is_a_complete_set_of_equal_replicates():
    stages, plan = tiered_plan()
    seen = {}   # tier -> {pass: cells run so far}
    last = None
    for k, (s, p) in enumerate(plan):
        t = G.stage_tier(s)
        if last is not None and last != (t, p):   # a group boundary: every pass the tier has finished holds all of its cells, once
            lt, lp = last
            want = sorted(c for x in stages if G.stage_tier(x) == lt and G.stage_reps(x, 5) >= lp for c in G.stage_cells(x))
            assert sorted(seen[lt][lp]) == want, (lt, lp)
            assert sorted(seen[lt]) == list(range(1, lp + 1))   # the tier ran passes 1..lp with none skipped
        seen.setdefault(t, {}).setdefault(p, []).extend(G.stage_cells(s))
        last = (t, p)


def test_all_reps_of_tier_1_up_to_3_run_before_tier_2_starts_and_each_tier_is_rep_major():
    stages, plan = tiered_plan()
    for t in (1, 2):
        passes = [p for s, p in plan if G.stage_tier(s) == t]
        assert passes == sorted(passes) and set(passes) == {1, 2, 3, 4, 5}, t   # pass 1 of the tier, then 2, ... 5
        per_pass = [passes.count(p) for p in range(1, 6)]
        assert all(a >= b for a, b in zip(per_pass, per_pass[1:]))   # a stage declaring fewer reps drops out of later passes
    first2 = next(i for i, (s, _) in enumerate(plan) if G.stage_tier(s) == 2)
    assert {p for _, p in plan[:first2]} == {1, 2, 3}      # rep 3 of Tier 1 is done before Tier 2 rep 1; rep 4 of Tier 1 is not
    after3 = [g for g in groups_of(plan)[6:]]
    assert after3 == [(1, 4), (2, 4), (1, 5), (2, 5)]      # then they alternate


def test_stage_ids_are_unique_consecutive_and_each_stage_waits_on_the_one_before(tmp_path):
    stages, plan = tiered_plan()
    ids = [s[0] for s, _ in plan]
    assert ids == [f"qS{i:03d}" for i in range(1, len(plan) + 1)] and len(set(ids)) == len(ids)
    assert all("[engine tier" in s[1] and "rep pass" in s[1] for s, _ in plan)
    out = tmp_path / "o"
    r = run(["--profile", "full", "--second-list", "--after", "none", "--status-file", "none", "--out", str(out)], tmp_path)   # the whole subset: past 99 stages
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    files = sorted(out.glob("*.sh"))
    assert [f.stem for f in files] == ids and len(ids) > 99 and ids[0] == "qS001"   # three digits past 99: qS100 must not sort before qS11
    for prev, cur in zip(files, files[1:]):
        assert waits(cur) == [prev.stem]
    assert "engine tier 1" in files[0].read_text() and "engine tier 2" in files[-1].read_text()


def test_inside_a_tier_the_old_rules_hold_core_first_large_last_biggest_last_and_priority_in_a_lane():
    stages, plan = tiered_plan()
    for t in (1, 2):
        one = [s for s, p in plan if G.stage_tier(s) == t and p == 1]
        lanes = [s[2] for s in one]
        core = [i for i, l in enumerate(lanes) if l in G.CORE_LANES]
        assert core == list(range(len(core)))                      # the core block, then the second list
        assert set(lanes[len(core):]) <= {"lifecycle", "l3s", "l4"}
        titles = [s[1] for s in one[:len(core)]]
        # a large-tier piece of a lane never comes before a small-tier piece of ANY lane; biggest cells come after the rest
        large = [i for i, s in enumerate(one[:len(core)]) if any(x in G.LARGE_SCALES for x in s[4]) and "biggest" not in s[1]]
        small = [i for i, s in enumerate(one[:len(core)]) if not any(x in G.LARGE_SCALES for x in s[4]) and "biggest" not in s[1]]
        assert not large or not small or max(small) < min(large), titles
        big = [i for i, s in enumerate(one[:len(core)]) if "biggest" in s[1]]
        assert not big or min(big) > max(large + small)
        for s in one:   # ENGINE_PRIORITY inside a stage's roster
            ranks = [G.engine_rank(b) for b in G.stage_backends(s)]
            assert ranks == sorted(ranks), (s[0], G.stage_backends(s))
    # the biggest cells of the user's tiers: SurrealDB documents (Tier 1) and Memgraph deep10m (Tier 2) each last in their own tier
    t1 = [s for s, p in plan if G.stage_tier(s) == 1 and p == 1]
    t2 = [s for s, p in plan if G.stage_tier(s) == 2 and p == 1]
    assert any("biggest" in s[1] and s[8][0].startswith("surrealdb_tpc") for s in t1)
    assert any("biggest" in s[1] and s[8][0].startswith("memgraph_dense") for s in t2)


def test_tiers_schedule_exactly_the_cells_the_tierless_list_does_in_every_pass():
    engines, lanes = G.parse_engines(None, "comparators"), G.parse_lanes(None, True)
    for order in ("biggest-last", "paper"):
        stages = G.number(G.subset_specs(engines, lanes, order, (), True), "x")
        assert G.stage_problems(stages, engines, lanes) == [], order
        for n in (3, 5):
            assert G.plan_problems(stages, n, G.pass_plan(stages, n, True), True) == [], (order, n)
    flat = G.number(G.subset_specs(engines, lanes), "x")
    tier = G.number(G.subset_specs(engines, lanes, tiers=True), "x")
    cells = lambda ss: sorted(c for s in ss for c in G.stage_cells(s))   # noqa: E731
    assert cells(flat) == cells(tier)


def test_without_tiers_the_chain_is_the_plain_rep_major_one(tmp_path):
    stages, plan = tiered_plan(tiers=False)
    assert all("engine tier" not in s[1] and s[1].endswith("of 5]") for s, _ in plan)
    assert plan == G.pass_plan(stages, 5)                                        # the default is the old behaviour
    assert any(len({G.tier_of(b) for b in G.stage_backends(s)}) > 1 for s, _ in plan)   # stages mix engines, as before
    assert G.plan_problems(stages, 5, plan, False) == []
    out = tmp_path / "o"
    r = run(["--no-tiers", "--after", "none", "--status-file", "none", "--out", str(out)], tmp_path)
    assert r.returncode == 0 and "engine tiers off" in r.stdout
    assert all("engine tier" not in f.read_text() for f in out.glob("*.sh"))
    assert G.lint_drafts(str(out)) == []   # the tier lint leaves a tier-less chain alone


def test_one_tier_alone_gives_the_same_chain_with_or_without_tiers():
    for engines in ("arangodb,duckdb", "neo4j,qdrant"):
        a_stages, a = tiered_plan(engines=engines, tiers=True)
        b_stages, b = tiered_plan(engines=engines, tiers=False)
        assert [(s, p) for s, p in a] == [(s, p) for s, p in b], engines
        assert all("engine tier" not in s[1] for s, _ in a)
    # ArcadeDB alone (the --arcadedb-release pass) is Tier 1 only
    specs = G.subset_specs(G.parse_engines(None, "arcadedb"), G.parse_lanes(None, True), tiers=True)
    assert {G.stage_tier(s) for s in specs} == {1}


def test_an_arm_with_no_tier_runs_after_tier_2_in_each_block(monkeypatch):
    monkeypatch.setitem(G.TIER_ENGINES, 1, tuple(e for e in G.TIER_ENGINES[1] if e != "duckdb"))
    assert G.tier_table_problems() != [] and G.tier_of("duckdb") == G.TIER_REST == 3
    stages, plan = tiered_plan()
    assert groups_of(plan) == G.schedule_order({1, 2, 3}, 5)
    assert all(G.tier_of(b) == 3 for s, _ in plan if G.stage_tier(s) == 3 for b in G.stage_backends(s))
    assert G.plan_problems(stages, 5, plan, True) == []


def test_the_check_catches_a_wrong_order_a_skipped_pass_a_split_pass_a_mixed_stage_and_a_repeated_id():
    stages, plan = tiered_plan()
    i = next(k for k, (s, _) in enumerate(plan) if G.stage_tier(s) == 2)
    swapped = list(plan)
    swapped[i - 1], swapped[i] = swapped[i], swapped[i - 1]       # the last stage of T1 pass 3 trades places with the first of T2 pass 1
    bad = G.plan_problems(stages, 5, swapped, True)
    assert any("the schedule has" in p for p in bad), bad
    # the old order (all five passes of Tier 1, then Tier 2) is not the schedule either
    old = sorted(plan, key=lambda x: (G.stage_tier(x[0]), x[1]))
    assert any("the schedule has" in p for p in G.plan_problems(stages, 5, old, True))
    # pass 4 of Tier 2 before pass 4 of Tier 1
    j4 = next(k for k, (s, p) in enumerate(plan) if p == 4 and G.stage_tier(s) == 1)
    k4 = next(k for k, (s, p) in enumerate(plan) if p == 4 and G.stage_tier(s) == 2)
    flipped = plan[:j4] + [x for x in plan[k4:k4 + sum(1 for s, p in plan if p == 4 and G.stage_tier(s) == 2)]] + \
        [x for x in plan[j4:k4]] + plan[k4 + sum(1 for s, p in plan if p == 4 and G.stage_tier(s) == 2):]
    assert any("the schedule has" in p for p in G.plan_problems(stages, 5, flipped, True))
    # a pass dropped from Tier 1 (pass 2 never runs) is a skipped pass and a missing cell
    skipped = [x for x in plan if not (x[1] == 2 and G.stage_tier(x[0]) == 1)]
    bad = G.plan_problems(stages, 5, skipped, True)
    assert any("the schedule has" in p for p in bad) and any("is in no stage" in p for p in bad)
    short = [x for x in plan[:-1]]
    assert any("is in no stage" in p for p in G.plan_problems(stages, 5, short, True))
    mixed = G.stage_backends(plan[0][0]) + [b for b in ("memgraph_graph",) if b not in G.stage_backends(plan[0][0])]
    spec = list(plan[0][0])
    spec[8] = mixed
    assert any("mixes engine tiers" in p for p in G.plan_problems(stages, 5, [(tuple(spec), 1)] + plan[1:], True))
    dup = [plan[0]] + [plan[0]] + plan[2:]
    assert any("not unique" in p for p in G.plan_problems(stages, 5, dup, True))


def test_check_on_the_default_selection_reports_the_tiers_and_lints_drafts_for_tier_order(drafts, tmp_path):
    r = run(["--check"])
    assert r.returncode == 0, r.stdout[-500:]
    assert "engine tiers on" in r.stdout and "engine tier 1:" in r.stdout and "engine tier 2:" in r.stdout
    assert "schedule: T1 p1, T1 p2, T1 p3, T2 p1, T2 p2, T2 p3, T1 p4, T2 p4, T1 p5, T2 p5" in r.stdout
    assert "the chain follows the schedule" in r.stdout
    assert G.lint_drafts(str(drafts)) == []
    # a draft folder whose first and last stages trade places: the tier lint says so
    bad = tmp_path / "bad"
    bad.mkdir()
    files = sorted(drafts.glob("*.sh"))
    for f in files:
        (bad / f.name).write_text(f.read_text())
    first, last = files[0].name, files[-1].name
    (bad / first).write_text(files[-1].read_text())
    (bad / last).write_text(files[0].read_text())
    assert any("not in the schedule's order" in p for p in G.lint_drafts(str(bad)))


def test_the_projection_splits_the_hours_by_tier(tmp_path):
    engines, lanes = G.parse_engines(None, "comparators"), ["l2"]
    stages = G.number(G.subset_specs(engines, lanes, "paper", (), True), "x")
    tsv = tmp_path / "cells.tsv"
    rows = ["lane\tworkload\tscale\tbackend\tclass\th3\th5"]
    for s in stages:
        for c in G.stage_cells(s):
            if c.kind == "lane" and not c.arm:
                rows.append(f"{c.lane}\t{c.workload}\t{c.scale}\t{c.backend}\t{c.cls}\t{1.0 if G.tier_of(c.backend) == 1 else 2.0}\t0")
    tsv.write_text("\n".join(rows) + "\n")
    hours = G.project_hours(stages, G.load_hours(str(tsv), 3))
    by = {t: sum(h for (sid, h, _, _), s in zip(hours, stages) if G.stage_tier(s) == t) for t in (1, 2)}
    assert by[1] > 0 and by[2] > 0
    r = run(["--check", "--lanes", "graph", "--reps", "3", "--project", str(tsv)])
    assert r.returncode == 0, r.stdout[-500:]
    assert f"engine tier 1: {by[1]:.1f} h" in r.stdout and f"engine tier 2: {by[2]:.1f} h" in r.stdout


# ------------------------------------------------------------------------------------------------- the paper-2611 profile
# The owner, 2026-10-25: the paper's experiments must finish by 2026-11-10. Core lanes only; fp32 dense only; Neo4j and Memgraph keep graph
# and cross-model but have no dense cell; the target is N=3 and the passes 4 and 5 stay after pass 3.
DROPPED_SECOND_LIST_LANES = {"l3s", "l4", "lifecycle"}
DROPPED_NEO4J_MEMGRAPH_DENSE = ["memgraph_dense", "memgraph_dense_int8", "neo4j_dense", "neo4j_dense_int8"]
DROPPED_QUANTIZED_DENSE = ["arangodb_dense_int8", "arcadedb_dense_embedded_int8", "arcadedb_dense_server_int8", "mongodb_dense_int8",
                           "qdrant_dense_int8", "sqlite_vec_dense_int8"]
RELEASE_FLAGS = ("--arcadedb-release", "26.11.1", "--engine-commit", COMMIT, "--image-digest", DIGEST, "--wheel-name", REL_WHEEL,
                 "--wheel-sha256", WSHA, "--wheel-url", "https://files.pythonhosted.org/packages/x/" + REL_WHEEL)


def test_the_profile_lists_exactly_what_it_drops():
    arms = G.dropped_arms("paper-2611")
    assert set(arms) == set(G.DROP_ORDER)
    assert arms[G.DROP_NEO4J_MEMGRAPH_DENSE] == DROPPED_NEO4J_MEMGRAPH_DENSE
    assert arms[G.DROP_QUANTIZED_DENSE] == DROPPED_QUANTIZED_DENSE
    cells = G.dropped_cells("paper-2611")
    assert {c.lane for c in cells[G.DROP_SECOND_LIST]} == DROPPED_SECOND_LIST_LANES
    assert {c.lane for c in cells[G.DROP_NEO4J_MEMGRAPH_DENSE] + cells[G.DROP_QUANTIZED_DENSE]} == {"l3d"}
    # no cell is counted under two reasons, and the full profile drops nothing
    seen = [c for why in G.DROP_ORDER for c in cells[why]]
    assert len(seen) == len(set(seen)) and G.dropped_cells("full") == {} and G.profile_skip("full") == ()
    assert set(G.profile_skip("paper-2611")) == set(DROPPED_NEO4J_MEMGRAPH_DENSE + DROPPED_QUANTIZED_DENSE)


def test_every_registered_quantized_dense_arm_is_classified_as_quantized():
    import runner
    quant = [b for b in runner.LANES["l3d"][1] if re.search(r"int8|_pq$", b)]
    assert quant and all(G.is_quantized_dense(b) for b in quant), [b for b in quant if not G.is_quantized_dense(b)]
    assert not any(G.is_quantized_dense(b) for b in ("arcadedb_dense_embedded", "arcadedb_dense_server", "qdrant_dense", "pgvector_dense"))


def test_the_default_profile_stages_the_core_lanes_fp32_dense_and_no_neo4j_or_memgraph_dense(drafts):
    seen_dense = set()
    for f in drafts.glob("*.sh"):
        text = f.read_text()
        lane = re.search(r"--lanes (\w+) ", text).group(1)
        bes = re.findall(r'^BACKENDS="([^"]*)"', text, re.M)[0].split()
        assert lane in G.CORE_LANES, (f.name, lane)
        if lane == "l3d":
            seen_dense |= set(bes)
            assert not any(re.search(r"int8|uint8|_pq|neo4j|memgraph", b) for b in bes), (f.name, bes)
    assert {"qdrant_dense", "pgvector_dense", "sqlite_vec_dense", "mongodb_dense", "arangodb_dense"} <= seen_dense


def test_the_arcadedb_chain_keeps_its_fp32_dense_pair_and_nothing_else_in_the_dense_lane(tmp_path):
    out = tmp_path / "rel"
    r = run(list(RELEASE_FLAGS) + ["--after", "none", "--status-file", "none", "--id-prefix", "qT", "--out", str(out)])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    dense, lanes = set(), set()
    for f in out.glob("qT0[1-9]*.sh"):
        text = f.read_text()
        lane = re.search(r"--lanes (\w+) ", text).group(1)
        lanes.add(lane)
        if lane == "l3d":
            dense |= set(re.findall(r'^BACKENDS="([^"]*)"', text, re.M)[0].split())
    assert dense == {"arcadedb_dense_embedded", "arcadedb_dense_server"} and lanes <= set(G.CORE_LANES)


def test_the_second_list_is_refused_by_the_default_profile_and_kept_by_full():
    r = run(["--check", "--second-list"])
    assert r.returncode != 0 and "--profile full" in (r.stdout + r.stderr)
    r = run(["--check", "--lanes", "lifecycle"])
    assert r.returncode != 0 and "--profile full" in (r.stdout + r.stderr)
    r = run(["--check", "--profile", "full", "--second-list"])
    assert r.returncode == 0 and "nothing dropped" in r.stdout
    full = G.number(G.subset_specs(G.parse_engines(None, "comparators"), G.parse_lanes(None, True, "full")), "x")
    assert {s[2] for s in full} >= DROPPED_SECOND_LIST_LANES and G.profile_problems("full", full) == []


def test_check_prints_what_the_default_profile_dropped_and_the_order_with_it():
    r = run(["--check"])
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    for needle in ("profile paper-2611", "dropped", "second-list", "neo4j-memgraph-dense", "quantized-dense", "arcadedb_dense_embedded_int8",
                   "schedule: T1 p1, T1 p2, T1 p3, T2 p1, T2 p2, T2 p3, T1 p4, T2 p4, T1 p5, T2 p5"):
        assert needle in r.stdout, needle
    # the chain still runs passes 4 and 5, after pass 3: N=3 is the target, not the end of the chain
    engines, lanes = G.parse_engines(None, "comparators"), G.parse_lanes(None, False, "paper-2611")
    stages = G.number(G.subset_specs(engines, lanes, "biggest-last", G.profile_skip("paper-2611"), True), "qS")
    plan = G.pass_plan(stages, G.DEFAULT_REPS, True)
    assert G.plan_problems(stages, G.DEFAULT_REPS, plan, True) == [] and G.profile_problems("paper-2611", stages) == []
    assert G.TARGET_REPS == 3 and G.PROFILES["paper-2611"]["target_reps"] == 3 and G.DEFAULT_REPS == 5
    groups = groups_of(plan)
    assert groups[:6] == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)] and groups[6:] == [(1, 4), (2, 4), (1, 5), (2, 5)]


def test_the_profile_proof_catches_a_dropped_lane_and_a_dropped_dense_arm():
    engines = G.parse_engines(None, "comparators")
    good = G.number(G.subset_specs(engines, G.parse_lanes(None, False, "paper-2611"), "biggest-last", G.profile_skip("paper-2611"), True), "x")
    assert G.profile_problems("paper-2611", good) == []
    dense = next(i for i, s in enumerate(good) if s[2] == "l3d")
    for extra, needle in (("qdrant_dense_int8", "quantized"), ("neo4j_dense", "Neo4j/Memgraph"), ("memgraph_dense_int8", "Neo4j/Memgraph")):
        bad = [list(s) for s in good]
        bad[dense][8] = list(G.stage_backends(good[dense])) + [extra]
        assert any(needle in p for p in G.profile_problems("paper-2611", bad)), extra
    lane_stage = G.number(G.subset_specs(engines, ["l3s"], "biggest-last"), "y")
    assert any("dropped by the paper-2611 profile" in p for p in G.profile_problems("paper-2611", lane_stage))
    arcade = G.number(G.subset_specs(["arcadedb"], ["l3d"], "biggest-last"), "z")   # unfiltered: ArcadeDB's int8 pair rides along
    assert any("fp32 pair" in p for p in G.profile_problems("paper-2611", arcade))


def test_the_draft_lint_refuses_a_dropped_arm_under_the_profile(drafts, tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    for f in drafts.glob("*.sh"):
        (bad / f.name).write_text(f.read_text())
    dense = next(f for f in sorted(bad.glob("*.sh")) if "--lanes l3d " in f.read_text())
    dense.write_text(re.sub(r'^BACKENDS="', 'BACKENDS="qdrant_dense_int8 ', dense.read_text(), count=1, flags=re.M))
    assert G.lint_drafts(str(drafts), None, None, "paper-2611") == []
    assert any("qdrant_dense_int8" in p and "paper-2611" in p for p in G.lint_drafts(str(bad), None, None, "paper-2611"))
    r = run(["--check", "--drafts", str(bad)])
    assert r.returncode != 0 and "qdrant_dense_int8" in r.stdout


def test_the_pq_arms_are_dropped_too_when_they_are_registered():
    r = run(["--check"], env_extra={"BENCH_DENSE_PQ": "1"})
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    assert "arcadedb_dense_embedded_pq" in r.stdout and "qdrant_dense_pq" in r.stdout   # listed as dropped, not staged
    assert not any(re.search(r"_pq\b", ln) for ln in r.stdout.splitlines() if ln.startswith("  qS"))


def test_the_projection_prices_the_target_repetitions_by_default(tmp_path):
    engines, lanes = G.parse_engines(None, "comparators"), ["l2"]
    stages = G.number(G.subset_specs(engines, lanes, "paper", (), True), "x")
    tsv = tmp_path / "cells.tsv"
    rows = ["lane\tworkload\tscale\tbackend\tclass\th3\th5"]
    n = 0
    for s in stages:
        for c in G.stage_cells(s):
            if c.kind == "lane" and not c.arm:
                rows.append(f"{c.lane}\t{c.workload}\t{c.scale}\t{c.backend}\t{c.cls}\t1.0\t10.0")
                n += 1
    tsv.write_text("\n".join(rows) + "\n")
    r = run(["--check", "--lanes", "graph", "--project", str(tsv)])
    assert r.returncode == 0 and "time for 3 repetitions" in r.stdout and f"total {n} h" in r.stdout, r.stdout[-500:]
    r = run(["--check", "--lanes", "graph", "--project", str(tsv), "--project-reps", "5"])
    assert "time for 5 repetitions" in r.stdout and f"total {10 * n} h" in r.stdout, r.stdout[-500:]


if __name__ == "__main__":
    if sys.argv[1:] != ["--rewrite"]:
        raise SystemExit("usage: python3 test_stage_generator_2611.py --rewrite   (regenerates stage_drafts_2611.sha256)")
    with tempfile.TemporaryDirectory() as d:
        SHA_LIST.write_text("\n".join(drafts_sha256(Path(d))) + "\n")
    print(f"wrote {SHA_LIST.name}")
