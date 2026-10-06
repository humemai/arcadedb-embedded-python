"""`make_2610_stages.py --rep-from 4 --roster ROSTER.json` (DECISIONS #164 item 5): pass 2, reps 4 and 5 of every arm whose
reps 1 to 3 are clean in the pin's rows, one lane at a time.

Run with `python -m pytest test_stage_top_up.py -q -rs` from this directory.

What these tests hold fixed: the roster is the only thing that decides what runs (a censored arm never repeats at its cap,
and a cell the roster does not list is skipped by name), every roster cell lands in exactly one stage, the ids cannot wake an
old chain, a stage that was stopped half way is regenerated without repeating a finished rep, the lanes come in the order the
rows ask for, and the emitted shell does what the plan says: the functions are run for real against a stub runner, because a
stage that passes `bash -n` can still run the wrong reps.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2610_stages as G  # noqa: E402
import make_october_stages as O  # noqa: E402
import pass2_roster as R  # noqa: E402

T0 = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
ARMS_HEADER = ("lane", "scale", "workload", "backend", "cls", "arm")


def synthetic_rows(minutes=6, upto=3):
    """Reps 1..upto of every lane cell every stage declares, one clean row each, `minutes` apart, ArcadeDB 10 ms and every
    other engine 11 ms on one metric (a ratio of 0.91, inside the band)."""
    rows, t = [], 0
    for spec in G.STAGES:
        if spec[2] == "pycost":
            continue
        for c in G.stage_cells(spec):
            if c.kind != "lane":
                continue
            for rep in range(1, upto + 1):
                r = {"lane": c.lane, "backend": c.backend, "workload": c.workload, "scale": c.scale, "rep": rep, "rc": 0,
                     "tier": "paper", "cpuset": "0-11", "durability_class": c.cls, "engine_commit": "d36b4ca3a",
                     "engine_version": "26.10.1", "ts_utc": (T0 + timedelta(minutes=t)).isoformat(),
                     "point_p50_ms": 10.0 if c.backend.startswith("arcadedb") else 11.0}
                if c.arm:
                    r["backend_arm"] = c.arm
                rows.append(r)
                t += minutes
    return rows


@pytest.fixture(scope="module")
def roster():
    return R.build_roster(synthetic_rows(), source="synthetic.jsonl")


@pytest.fixture(scope="module")
def plan(roster):
    return G.pass2_plan(roster)


def labels(plan, sid=None):
    return {c["label"] for s, cells in plan.cells.items() if sid in (None, s) for c in cells}


def block_of(plan, sid):
    return dict(line.split("|") for line in plan.blocks[sid].splitlines())


def test_every_roster_cell_of_the_tiers_runs_in_exactly_one_stage(plan, roster):
    assert G.check_coverage(plan.stages, plan=plan)[0] == []
    assert plan.problems(plan.stages)[0] == []
    want = {k for k in G.roster_index(roster) if G.tier_of(k[3]) in (1, 2)}
    assert set(plan.want) == want and plan.out_of_scope
    assert len(plan.scheduled()) + len(plan.complete) == len(want)
    assert all(v == 1 for v in plan.matched.values())


def test_the_stage_list_check_still_proves_every_arm_in_exactly_one_stage():
    assert G.check_coverage(G.STAGES)[0] == []


def test_tier_three_is_left_for_later_and_comes_back_with_tiers_1_2_3(roster):
    default = G.pass2_plan(roster)
    backends = {c["backend"] for c in default.scheduled()}
    assert backends and not backends & set(G.TIER3_NEW)
    everything = G.pass2_plan(roster, tiers=(1, 2, 3))
    assert {c["backend"] for c in everything.scheduled()} & set(G.TIER3_NEW)
    assert everything.problems(everything.stages)[0] == [] and everything.out_of_scope == []
    assert len(everything.scheduled()) == len(default.scheduled()) + len(default.out_of_scope)
    assert G.parse_tiers("1, 2") == (1, 2)
    for bad in ("", "4", "a"):
        with pytest.raises(SystemExit):
            G.parse_tiers(bad)


def test_an_arm_that_was_censored_in_pass_one_never_repeats_at_its_cap(roster):
    r = json.loads(json.dumps(roster))
    victim = next(be for be in r["lanes"]["l3d"] if not be.startswith("arcadedb"))
    r["ineligible"].setdefault("l3d", {})[victim] = r["lanes"]["l3d"].pop(victim)
    p = G.pass2_plan(r)
    assert not any(c["backend"] == victim and c["lane"] == "l3d" for c in p.scheduled())
    assert all(victim + "/" not in line.split("|")[0] for blk in p.blocks.values() for line in blk.splitlines()
               if line.startswith("l3d/"))
    assert p.problems(p.stages)[0] == [] and p.ineligible == len(r["ineligible"]["l3d"][victim]) == 2


def test_a_roster_cell_no_stage_enumerates_is_a_problem(roster):
    r = json.loads(json.dumps(roster))
    r["lanes"]["l2"]["no_such_arm"] = [{"scale": "sf1", "workload": "oltp", "durability_class": "relaxed", "arm": "",
                                        "clean_reps": [1, 2, 3], "wall_s_per_rep": 60.0}]
    problems = G.pass2_plan(r).problems()[0]
    assert any("l2/sf1/oltp/no_such_arm" in p and "0 stages" in p for p in problems)


def test_a_cell_in_two_stages_is_a_problem(roster):
    p = G.pass2_plan(roster, stages=G.STAGES + [G.STAGES[0]])
    problems = p.problems()[0]
    assert problems and all("2 stages" in x or "scheduled 2 times" in x for x in problems)


def test_a_stopped_pass_two_resumes_without_repeating_a_finished_rep(roster):
    r = json.loads(json.dumps(roster))
    cells = r["lanes"]["l2"]["arcadedb_graph_embedded"]
    cells[0]["clean_reps"] = [1, 2, 3, 4]
    done = next(c for c in cells if c["durability_class"] == "strict")
    done["clean_reps"] = [1, 2, 3, 4, 5]
    p = G.pass2_plan(r)
    sid = next(s for s, cs in p.cells.items() if any(c["lane"] == "l2" and c["workload"] == "oltp" for c in cs))
    blk = block_of(p, sid)
    assert blk["l2/sf1/arcadedb_graph_embedded/oltp"] == "5"
    assert "l2/sf1/arcadedb_graph_embedded/oltp strict" not in blk
    assert ("l2", "sf1", "oltp", "arcadedb_graph_embedded", "strict", "") in p.complete
    assert p.problems(p.stages)[0] == []


def test_the_arm_that_declares_three_reps_has_nothing_to_top_up(plan):
    arm = "arcadedb_imgdefaults_server"
    assert all(c["backend"] != arm for c in plan.scheduled())
    assert any(k[3] == arm for k in plan.complete)
    assert not any(arm in line for blk in plan.blocks.values() for line in blk.splitlines())


def test_rep_four_and_five_are_the_default_reps_of_a_five_rep_cell(plan):
    reps = {tuple(c["reps"]) for c in plan.scheduled()}
    assert reps == {(4, 5)}


def test_both_durability_classes_and_the_no_view_arm_have_their_own_roster_lines(plan):
    l2 = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l2" and c["workload"] == "oltp" for c in cs))
    blk = block_of(plan, l2)
    assert blk["l2/sf10/arcadedb_graph_server/oltp"] == "4,5" and blk["l2/sf10/arcadedb_graph_server/oltp strict"] == "4,5"
    olap = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l2" and c["workload"] == "olap" for c in cs))
    blk = block_of(plan, olap)
    assert blk["l2/sf1full/arcadedb_graph_embedded/olap"] == "4,5"
    assert blk["l2/sf1full/arcadedb_graph_embedded/olap BENCH_GAV=0"] == "4,5"
    assert ("l2", "sf1full", "olap", "arcadedb_graph_embedded", "relaxed", "nogav") in plan.want


def test_the_dense_overlay_follows_its_lane_cell_and_the_sparse_one_never_runs_again(plan):
    dense = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l3d" for c in cs))
    blk = block_of(plan, dense)
    assert blk["l3d/small/arcadedb_dense_embedded/search"] == "4,5"
    assert blk["l3d/small/arcadedb_dense_embedded/search multipass"] == "4,5"
    sparse = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l3s" for c in cs))
    assert not any(l.endswith("multipass") for l in plan.blocks[sparse].splitlines())
    assert any(c["kind"] == "overlay" for c in plan.cells[dense])
    assert all(c["kind"] == "lane" for c in plan.cells[sparse])


def test_an_overlay_is_only_rostered_with_its_lane_cell(roster):
    r = json.loads(json.dumps(roster))
    be = "arcadedb_dense_embedded"
    r["ineligible"].setdefault("l3d", {})[be] = r["lanes"]["l3d"].pop(be)
    p = G.pass2_plan(r)
    assert not any(be + "/" in l for l in labels(p) if l.startswith("l3d/"))


def test_stage_ids_are_qR_and_two_digits_and_cannot_wake_an_old_chain(plan):
    ids = [s[0] for s in plan.stages]
    assert ids == [f"qR{i:02d}" for i in range(1, len(ids) + 1)]
    old = {s[0] for s in G.STAGES} | {s[0] for s in O.STAGES}
    old |= {s[0] for s in G.tiered_stages()} | {s[0] for s in G.tiered_stages(prefix="qP", rep_pass=3)}
    assert not old & set(ids), "a reused id finds the old chain's ALL-DONE marker in STATUS.txt"
    assert all(re.fullmatch(r"qR\d\d", i) for i in ids)
    assert not any(re.fullmatch(r"qR\d\d", i) for i in old), "no old chain used qR followed by digits"


def test_the_stage_tuples_keep_their_lane_guards_environment_and_class(plan):
    for st in plan.stages:
        base = next(s for s in G.STAGES if s[2] == st[2] and set(st[3]) <= set(s[3]) and set(st[4]) <= set(s[4])
                    and set(st[8]) <= set(G.stage_backends(s)))
        assert list(st[5]) == list(base[5]) and list(st[7]) == list(base[7]) and st[6] == base[6]
        assert st[9] == (base[9] if len(base) > 9 else None)


def _closeness_for(roster, shares):
    """The roster with a hand-set closeness: {'lane|scale|workload': share of 10 ratios inside the band}."""
    r = json.loads(json.dumps(roster))
    r["closeness"] = {k: {"somebody": {"comparisons": 10, "within_band": int(round(v * 10)),
                                       "closest": {"ratio": 1.01, "arcadedb": "arcadedb_x", "metric": "m", "class": "relaxed"}}}
                      for k, v in shares.items()}
    return r


def test_the_lane_with_the_closest_ratios_goes_first_and_the_extras_go_last(roster):
    r = _closeness_for(roster, {"l3d|small|search": 0.9, "l3d|deep10m|search": 0.9, "l1tpc|tpch1|oltp": 0.5,
                                "l1tpc|tpch10|oltp": 0.5, "l2|sf1|oltp": 0.1, "l2|sf10|oltp": 0.1, "restart|tpch1|restart": 1.0})
    p = G.pass2_plan(r)
    lanes = [(o["lane"], tuple(o["workloads"])) for o in p.order]
    assert lanes[0][0] == "l3d" and lanes.index(("l1tpc", ("oltp", "olap"))) < lanes.index(("l2", ("oltp",)))
    scored = [o for o in p.order if o["share"] is not None and not o["extra"]]
    assert [o["share"] for o in scored] == sorted((o["share"] for o in scored), reverse=True)
    first_extra = next(i for i, o in enumerate(p.order) if o["extra"])
    assert all(o["extra"] for o in p.order[first_extra:]), "lifecycle, restart and the sensitivity arm after the core lanes"
    assert any(o["lane"] == "restart" for o in p.order[first_extra:]), "a restart stage with share 1.0 still waits behind the core lanes"
    unscored = [i for i, o in enumerate(p.order) if o["share"] is None and not o["extra"]]
    assert all(i > max(j for j, o in enumerate(p.order) if o["share"] is not None and not o["extra"]) for i in unscored)
    assert [o["id"] for o in p.order] == [s[0] for s in p.stages]


def test_the_paper_order_is_the_table_order(roster):
    p = G.pass2_plan(roster, lane_order="paper")
    base = [s[0] for s in G.STAGES]
    assert [o["base_id"] for o in p.order] == [b for b in base if b in {o["base_id"] for o in p.order}]
    with pytest.raises(SystemExit):
        G.pass2_plan(roster, lane_order="whatever")


def test_a_comparator_outside_the_tiers_does_not_move_the_order(roster):
    r = json.loads(json.dumps(roster))
    r["closeness"] = {"l3d|small|search": {"memgraph_dense": {"comparisons": 10, "within_band": 10,
                                                              "closest": {"ratio": 1.0, "arcadedb": "a", "metric": "m", "class": "relaxed"}}}}
    p = G.pass2_plan(r)
    assert next(o for o in p.order if o["lane"] == "l3d")["share"] is None
    assert next(o for o in G.pass2_plan(r, tiers=(1, 2, 3)).order if o["lane"] == "l3d")["share"] == 1.0


def _hand_roster(*cells):
    """cells: (lane, backend, scale, workload, class, arm, clean_reps, wall)."""
    lanes = {}
    for lane, be, sc, wl, cls, arm, clean, wall in cells:
        lanes.setdefault(lane, {}).setdefault(be, []).append(
            {"scale": sc, "workload": wl, "durability_class": cls, "arm": arm, "clean_reps": clean, "wall_s_per_rep": wall})
    return {"format": G.ROSTER_FORMAT, "source": "hand.jsonl", "n_rows": 9, "need_reps": [1, 2, 3], "band": 1.3,
            "lanes": lanes, "ineligible": {}, "closeness": {}}


def test_the_projection_is_cell_reps_times_wall_per_rep_and_says_it_is_a_projection():
    r = _hand_roster(("l2", "arcadedb_graph_embedded", "sf1", "oltp", "relaxed", "", [1, 2, 3], 3600.0),
                     ("l2", "neo4j_graph", "sf1", "oltp", "relaxed", "", [1, 2, 3], 1800.0))
    p = G.pass2_plan(r)
    assert len(p.order) == 1 and p.order[0]["hours"] == pytest.approx(2 * 1.0 + 2 * 0.5)
    text = G.describe_plan(p, r, 4, (1, 2), "closest")
    assert "PROJECTION, not measured" in text and "3.0 h projected" in text
    assert "total 3 h projected over 1 stages" in text


def test_a_cell_without_a_wall_time_takes_its_groups_median_or_is_counted_as_missing():
    r = _hand_roster(("l2", "arcadedb_graph_embedded", "sf1", "oltp", "relaxed", "", [1, 2, 3], 3600.0),
                     ("l2", "neo4j_graph", "sf1", "oltp", "relaxed", "", [1, 2, 3], None),
                     ("e4", "arcadedb_e4", "e2", "decomp", "relaxed", "", [1, 2, 3], None))
    p = G.pass2_plan(r)
    l2 = next(o for o in p.order if o["lane"] == "l2")
    assert l2["hours"] == pytest.approx(2 * 1.0 + 2 * 1.0) and l2["unestimated"] == 0
    e4 = next(o for o in p.order if o["lane"] == "e4")
    assert e4["hours"] == 0.0 and e4["unestimated"] == 1
    assert "a lower bound: 1 cells have no estimate" in G.describe_plan(p, r, 4, (1, 2), "closest")


# ------------------------------------------------------------------- the emitted scripts
def _generate(tmp_path, roster_doc, *extra, expect_ok=True, name="stages"):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    rp = tmp_path / "roster.json"
    rp.write_text(json.dumps(roster_doc))
    env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp_path / name
    cmd = [sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out), "--rep-from", "4", "--roster", str(rp), *extra]
    r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
    if expect_ok:
        assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    return out, r


@pytest.fixture(scope="module")
def emitted(tmp_path_factory, roster):
    tmp = tmp_path_factory.mktemp("topup")
    out, r = _generate(tmp, roster, "--after", "qP34")
    return out, r, tmp


def _script_labels(text, backends):
    """Every label the script's loops pass to run_cell or run_overlay, with $BE expanded over its roster."""
    out = []
    for m in re.finditer(r'^  (?:\[ "\$BE" = "([^"]+)" \] && )?run_(?:cell|overlay) "([^"]+)"', text, re.M):
        only, label = m.groups()
        for be in ([only] if only else backends):
            out.append(label.replace("$BE", be))
    return out


def test_the_emitted_chain_is_linear_parses_and_waits_on_the_named_stage(emitted, plan):
    out, _r, _tmp = emitted
    ids = [s[0] for s in plan.stages]
    assert sorted(p.stem for p in out.glob("*.sh")) == ids
    for prev, sid in zip(["qP34"] + ids[:-1], ids):
        text = (out / f"{sid}.sh").read_text()
        waits = [l for l in text.splitlines() if l.startswith("while ! grep -q") and "ALL-DONE" in l]
        assert len(waits) == 1 and f'"{prev} ALL-DONE"' in waits[0], sid
        assert subprocess.run(["bash", "-n", str(out / f"{sid}.sh")], capture_output=True).returncode == 0, sid


def test_each_script_carries_exactly_its_stages_roster_and_backends(emitted, plan):
    out, _r, _tmp = emitted
    for st in plan.stages:
        text = (out / f"{st[0]}.sh").read_text()
        m = re.search(r"^ROSTER=\$\(cat <<'ROSTER_EOF'\n(.*?)\nROSTER_EOF\n\)$", text, re.S | re.M)
        assert m and m.group(1) == plan.blocks[st[0]], st[0]
        assert re.search(r'^BACKENDS="([^"]*)"$', text, re.M).group(1).split() == st[8]
        assert "top-up pass: reps 4 up" in text and "LAST_REP" not in text and "seq -s, 2" not in text


def test_every_rostered_label_is_one_the_script_calls(emitted, plan):
    out, _r, _tmp = emitted
    for st in plan.stages:
        text = (out / f"{st[0]}.sh").read_text()
        called = _script_labels(text, st[8])
        assert len(called) == len(set(called)), st[0]
        assert set(called) == {c.label for c in G.stage_cells(st)}, "stage_cells no longer mirrors make_october_stages.emit"
        assert set(plan.blocks[st[0]].splitlines()) and labels(plan, st[0]) <= set(called)


def test_the_pass_one_and_default_generations_know_nothing_about_a_roster(tmp_path):
    for extra in (["--rep-pass", "3"], ["--order", "tiers"]):
        wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
        wheel.write_bytes(b"x")
        env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
                   ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
        out = tmp_path / ("o" + "".join(extra).replace("-", ""))
        r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out), "--after", "none", *extra],
                           cwd=HERE, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-400:]
        for p in out.glob("*.sh"):
            t = p.read_text()
            assert "ROSTER" not in t and "roster_reps" not in t, p.name


# the shell, for real, against a stub runner
def _function(text, name):
    m = re.search(rf"^{name}\(\) \{{.*?^\}}$", text, re.S | re.M)
    assert m, name
    return m.group(0)


def _stub(tmp_path, exit_codes=()):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    calls = tmp_path / "calls.txt"
    counter = tmp_path / "n"
    counter.write_text("0")
    codes = " ".join(str(c) for c in exit_codes) or "0"
    stub = bindir / "python3"
    stub.write_text(f'#!/bin/bash\necho "$*" >> {calls}\nn=$(cat {counter}); echo $((n+1)) > {counter}\n'
                    f'codes=({codes}); c=${{codes[$n]:-0}}; exit $c\n')
    stub.chmod(0o755)
    calls.write_text("")
    return bindir, calls


def _run_shell(tmp_path, text, call, reps=5, exit_codes=()):
    bindir, calls = _stub(tmp_path, exit_codes)
    roster = re.search(r"^ROSTER=\$\(cat <<'ROSTER_EOF'\n.*?\nROSTER_EOF\n\)$", text, re.S | re.M).group(0)
    body = (f'said=$(mktemp)\nsay() {{ echo "$*" >> "$said"; }}\nS=/dev/null\nRF=rf.jsonl\nID=T\nREPS={reps}\n{roster}\n'
            f'{_function(text, "roster_reps")}\n{_function(text, "run_overlay")}\n{_function(text, "run_cell")}\n{call}\ncat "$said" >&2\n')
    r = subprocess.run(["bash", "-c", body], env=dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}"), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return [l for l in calls.read_text().splitlines() if l.strip()], r.stderr


def _only(line):
    return re.search(r"--only-reps (\S+)", line).group(1)


@pytest.fixture(scope="module")
def dense_script(emitted, plan):
    out, _r, _tmp = emitted
    sid = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l3d" for c in cs))
    return (out / f"{sid}.sh").read_text()


def _with_block(text, lines):
    return re.sub(r"(?s)(ROSTER=\$\(cat <<'ROSTER_EOF'\n).*?(\nROSTER_EOF\n\))", lambda m: m.group(1) + "\n".join(lines) + m.group(2), text)


CELL = 'run_cell "l3d/small/b/search" small 7200 b search ""'
OVER = 'run_overlay "l3d/small/b/search multipass" small 7200 b search drv.py outdir orf.jsonl 5 ""'


def test_a_rostered_cell_runs_rep_four_alone_then_rep_five(tmp_path, dense_script):
    text = _with_block(dense_script, ["l3d/small/b/search|4,5"])
    calls, said = _run_shell(tmp_path, text, CELL)
    assert [_only(c) for c in calls] == ["4", "5"] and all("--reps 5" in c for c in calls)
    assert "not in the roster" not in said


def test_a_cell_the_roster_leaves_out_runs_nothing_and_says_so(tmp_path, dense_script):
    text = _with_block(dense_script, ["l3d/small/other/search|4,5"])
    calls, said = _run_shell(tmp_path, text, CELL)
    assert calls == [] and "l3d/small/b/search is not in the roster, skipped" in said


def test_a_resumed_cell_runs_only_the_missing_rep(tmp_path, dense_script):
    calls, _ = _run_shell(tmp_path, _with_block(dense_script, ["l3d/small/b/search|5"]), CELL)
    assert [_only(c) for c in calls] == ["5"]


def test_a_failed_first_rep_ends_the_cell(tmp_path, dense_script):
    text = _with_block(dense_script, ["l3d/small/b/search|4,5"])
    calls, said = _run_shell(tmp_path, text, CELL, exit_codes=(1,))
    assert [_only(c) for c in calls] == ["4"] and "rep 4 failed, not repeating it" in said


def test_the_overlay_follows_the_roster_and_a_label_it_lacks_never_runs(tmp_path, dense_script):
    text = _with_block(dense_script, ["l3d/small/b/search multipass|4,5"])
    calls, _ = _run_shell(tmp_path, text, OVER)
    assert [_only(c) for c in calls] == ["4", "5"] and all("--driver drv.py" in c and "--reps 5" in c for c in calls)
    none, said = _run_shell(tmp_path, _with_block(dense_script, ["l3d/small/b/search|4,5"]), OVER)
    assert none == [] and "multipass is not in the roster, skipped" in said


def test_an_overlay_that_repeats_inside_its_driver_has_no_roster_line_and_does_not_run(tmp_path, emitted, plan):
    out, _r, _tmp = emitted
    sid = next(s for s, cs in plan.cells.items() if any(c["lane"] == "l3s" for c in cs))
    text = (out / f"{sid}.sh").read_text()
    call = 'run_overlay "l3s/tiny/arcadedb_sparse_embedded/search multipass" tiny 1800 b search drv.py outdir orf.jsonl 1 ""'
    calls, said = _run_shell(tmp_path, text, call)
    assert calls == [] and "not in the roster" in said
    calls, _ = _run_shell(tmp_path, text, 'run_cell "l3s/tiny/arcadedb_sparse_embedded/search" tiny 1800 b search ""')
    assert [_only(c) for c in calls] == ["4", "5"]


# ------------------------------------------------------------------- the command line
def test_dry_run_prints_the_order_and_the_projection_and_writes_nothing(tmp_path, roster):
    rp = tmp_path / "roster.json"
    rp.write_text(json.dumps(roster))
    r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--rep-from", "4", "--roster", str(rp), "--dry-run"],
                       cwd=HERE, env={k: v for k, v in os.environ.items() if not k.startswith("ARCADEDB_")},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    assert "PROJECTION, not measured" in r.stdout and "qR01" in r.stdout and "h cumulative" in r.stdout
    assert "coverage: every roster cell of the tiers this pass runs in exactly one stage" in r.stdout
    assert "PROBLEM" not in r.stdout
    assert [p.name for p in tmp_path.iterdir()] == ["roster.json"]


def _cli(tmp_path, *args, roster=None):
    rp = tmp_path / "roster.json"
    rp.write_text(json.dumps(roster or {"format": G.ROSTER_FORMAT, "n_rows": 0, "need_reps": [1, 2, 3], "lanes": {}, "ineligible": {},
                                       "engine_commits": {"000000000": 1}}))
    env = dict(os.environ, ARCADEDB_WHEEL="x", ARCADEDB_SERVER_IMAGE="y", ARCADEDB_ENGINE_COMMIT="0" * 40)
    r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), *args], cwd=HERE, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr, rp


def test_the_top_up_pass_is_refused_without_its_roster_and_with_a_bad_rep(tmp_path):
    rc, out, rp = _cli(tmp_path, "--check", "--rep-from", "4")
    assert rc != 0 and "needs --roster" in out
    for bad in ("1", "6"):
        rc, out, rp = _cli(tmp_path, "--check", "--rep-from", bad, "--roster", str(tmp_path / "roster.json"))
        assert rc != 0 and "--rep-from must be 2 to 5" in out
    rc, out, rp = _cli(tmp_path, "--check", "--rep-from", "4", "--rep-pass", "3", "--roster", str(tmp_path / "roster.json"))
    assert rc != 0 and "two different passes" in out
    rc, out, _ = _cli(tmp_path, "--dry-run")
    assert rc != 0 and "needs --rep-from and --roster" in out


def test_emitting_the_top_up_needs_an_explicit_after_and_a_real_roster(tmp_path, roster):
    rc, out, _ = _cli(tmp_path, "--rep-from", "4", "--roster", str(tmp_path / "roster.json"), "--out", str(tmp_path / "o"))
    assert rc != 0 and "explicit --after" in out
    rc, out, _ = _cli(tmp_path, "--check", "--rep-from", "4", "--roster", str(tmp_path / "roster.json"),
                      roster={"format": "something-else"})
    assert rc != 0 and "pass2-roster-1" in out


def test_an_empty_roster_plans_no_stage_and_fails_no_check(tmp_path):
    rc, out, rp = _cli(tmp_path, "--check", "--rep-from", "4", "--roster", str(tmp_path / "roster.json"))
    assert rc == 0, out
    rc, out, rp = _cli(tmp_path, "--rep-from", "4", "--roster", str(tmp_path / "roster.json"), "--dry-run")
    assert rc == 0 and "to run 0" in out and "total 0 h projected over 0 stages" in out


def test_a_roster_from_rows_of_two_pins_is_a_problem_and_the_stages_refuse_another_commit(tmp_path, roster):
    assert G.roster_pin_problems(roster) == []
    two = dict(roster, engine_commits={"d36b4ca3a": 5, "417314c18": 2})
    assert any("2 engine commits" in p for p in G.roster_pin_problems(two))
    assert any("0 engine commits" in p for p in G.roster_pin_problems(dict(roster, engine_commits={})))
    mixed = dict(roster, arcadedb_engine_versions={"26.10.1": 3, "26.9.1": 1})
    assert any("2 engine versions" in p for p in G.roster_pin_problems(mixed))
    rc, out, _ = _cli(tmp_path, "--check", "--rep-from", "4", "--roster", str(tmp_path / "roster.json"), roster=two)
    assert rc != 0 and "PROBLEM the roster's rows carry 2 engine commits" in out
    # generated for another commit than the rows were measured at
    other, r = _generate(tmp_path, dict(roster, engine_commits={"417314c18": 5}), "--after", "none", expect_ok=False, name="other")
    assert r.returncode != 0 and "REFUSING to emit: the roster was read from rows at engine commit 417314c18" in r.stdout + r.stderr
    assert not other.exists()
