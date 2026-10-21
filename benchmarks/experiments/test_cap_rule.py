"""The cap rule (DECISIONS #188): cap_rule.py computes it, make_2611_stages.py applies it at run time, export_web.py at report time.

Run with `python -m pytest test_cap_rule.py -q` from this directory. What is held fixed: the numbers the rule gives for the
cells the live stages were patched with; the stage text every generator mode emits (helpers, the three call sites, a lowered
cap, an unchanged cap where the rule is higher, the seeding); the helpers run for real in bash; and the report-time cells.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_ENGINE_COMMIT", "d36b4ca3a")

import cap_rule as C  # noqa: E402
import make_2611_stages as G  # noqa: E402


def line(cell, secs, status="ok"):
    return f"  [1/9] {cell} {secs}s (0-3) -> {status}"


BACKENDS = ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres", "surrealdb_tpc"]


# ------------------------------------------------------------------- the computation
def test_cap_is_ten_times_the_slower_reference_with_an_1800_floor():
    lines = [line("l1tpc_arcadedb_embedded_olap_tpch1_r1", 100), line("l1tpc_duckdb_olap_tpch1_r1", 50),
             line("l1tpc_postgres_olap_tpch1_r1", 400),
             line("l2_arcadedb_graph_embedded_oltp_sf1_r1", 300), line("l2_duckdb_oltp_sf1_r1", 10)]
    cells = C.parse_cells(lines, C.known_backends())
    caps = C.compute(cells)["caps"]
    # ref = max(ArcadeDB's 100, the engines' median 100) -> 1000 s, under the floor
    assert caps["l1tpc|tpch1|olap|"]["cap_s"] == 1800
    # ArcadeDB's 300 s is the slower reference -> 3000 s
    assert caps["l2|sf1|oltp|"]["cap_s"] == 3000


def test_only_arcadedb_rows_define_the_arcadedb_reference_and_a_cell_without_one_has_no_rule():
    cells = C.parse_cells([line("l1tpc_duckdb_olap_tpch1_r1", 9999)], C.known_backends())
    assert C.compute(cells)["caps"] == {}


def test_an_arm_over_its_rule_cap_is_listed_and_an_arcadedb_arm_never_is():
    lines = [line("l1tpc_arcadedb_embedded_olap_tpch1_r1", 1000), line("l1tpc_duckdb_olap_tpch1_r1", 1000),
             line("l1tpc_surrealdb_tpc_olap_tpch1_r1", 20000), line("l1tpc_surrealdb_tpc_olap_tpch1_r2", 19000),
             line("l1tpc_postgres_olap_tpch1_r1", 1200)]
    out = C.compute(C.parse_cells(lines, C.known_backends()))
    assert [(o["backend"], o["median_s"], o["cap_s"]) for o in out["over_rule"]] == [("surrealdb_tpc", 19500.0, 11000)]


def test_a_timeout_of_rep_one_is_listed_and_the_strict_class_is_its_own_cell():
    lines = [line("l2_arcadedb_graph_embedded_oltp_sf10_r1", 100), line("l2_arcadedb_graph_embedded_oltp_sf10_r1_dstrict", 200),
             line("l2_memgraph_graph_oltp_sf10_r1", 7200, "timeout_after_7200s")]
    out = C.compute(C.parse_cells(lines, C.known_backends()))
    assert set(out["caps"]) == {"l2|sf10|oltp|", "l2|sf10|oltp|strict"}
    assert out["timeouts"] == [dict(lane="l2", scale="sf10", backend="memgraph_graph", workload="oltp", cls="", cap_s=7200)]


def test_the_committed_data_gives_the_caps_the_live_stages_were_patched_with():
    d = C.load()
    want = {"restart|tpch1|restart|": 1800, "l3d|deep10m|search|": 23730, "l2|sf10|oltp|": 8685, "l2|sf10|oltp|strict": 9031,
            "l3s|small|search|": 2344, "l4|ts100|ingest|": 2076, "restart|ts1000|restart|": 2329, "restart|small|restart|": 2643}
    assert {k: d["caps"][k]["cap_s"] for k in want} == want
    over = {(o["backend"], o["lane"], o["scale"], o["workload"]): (o["median_s"], o["cap_s"]) for o in d["over_rule"]}
    assert over[("surrealdb_tpc", "l1tpc", "tpch1", "olap")] == (7936.2, 7326)
    assert ("surrealdb_lifecycle", "lifecycle", "lc1m", "graph") in over
    assert ("surrealdb_lifecycle", "lifecycle", "lc100k", "vector") in over
    assert ("surrealdb_dense_server", "l3d", "small", "search") in over
    assert not [o for o in d["over_rule"] if o["backend"].startswith("arcadedb")]


def test_larger_scales_are_per_chain():
    assert C.smaller_scales("restart", "ts1000") == ["ts100"]
    assert C.smaller_scales("restart", "tpch10") == ["tpch1"]
    assert C.smaller_scales("l3s", "medium") == ["tiny", "small"]
    assert C.censored_before("lifecycle", "lc10m", "surrealdb_lifecycle", "graph", "") == "lc1m"
    assert C.censored_before("lifecycle", "lc100k", "surrealdb_lifecycle", "graph", "") is None


# ------------------------------------------------------------------- the stage generator
def test_apply_cap_rule_lowers_a_cap_and_leaves_one_the_rule_is_above():
    data = {"rule": {}, "caps": {"l2|sf1|oltp|": {"cap_s": 500}, "l2|sf1|oltp|strict": {"cap_s": 99999}},
            "over_rule": [], "timeouts": []}
    body = ('for BE in $BACKENDS; do\n  run_cell "l2/sf1/$BE/oltp" sf1 7200 "$BE" oltp ""\n'
            '  run_cell "l2/sf1/$BE/oltp strict" sf1 7200 "$BE" oltp "" "--durability strict"\ndone\n')
    out = G.apply_cap_rule(body, "l2", {"memgraph_graph"}, {"oltp"}, data)
    assert 'run_cell "l2/sf1/$BE/oltp" sf1 500 ' in out
    assert 'run_cell "l2/sf1/$BE/oltp strict" sf1 7200 ' in out


def test_apply_cap_rule_seeds_only_arms_censored_at_a_smaller_scale():
    data = {"rule": {}, "caps": {}, "timeouts": [],
            "over_rule": [dict(lane="l2", scale="sf1", backend="memgraph_graph", workload="oltp", cls="", median_s=9, cap_s=5),
                          dict(lane="l2", scale="sf10", backend="neo4j_graph", workload="oltp", cls="strict", median_s=9, cap_s=5)]}
    body = ('\nfor BE in $BACKENDS; do\n  run_cell "l2/sf1/$BE/oltp" sf1 7200 "$BE" oltp ""\ndone\n'
            '\nfor BE in $BACKENDS; do\n  run_cell "l2/sf10/$BE/oltp" sf10 7200 "$BE" oltp ""\ndone\n')
    out = G.apply_cap_rule(body, "l2", {"memgraph_graph", "neo4j_graph"}, {"oltp"}, data)
    blocks = out.split("\nfor BE in $BACKENDS; do\n")
    seed = 'CENSORED_AT["memgraph_graph|oltp|"]="sf1"'
    assert "CENSORED_AT" not in blocks[0] and "CENSORED_AT" not in blocks[1].split("done\n")[0]   # sf1: it runs where it was censored
    assert seed in blocks[1].split("done\n")[1]                                                    # seeded before the sf10 loop
    assert out.index('CENSORED_AT["memgraph_graph') < out.index('run_cell "l2/sf10')
    assert "neo4j_graph" not in out                       # censored at sf10 itself, in the strict class: nothing above it here


def test_without_the_data_a_stage_is_unchanged(monkeypatch):
    monkeypatch.setattr(C, "load", lambda path=None: None)
    body = 'for BE in $BACKENDS; do\n  run_cell "l2/sf1/$BE/oltp" sf1 7200 "$BE" oltp ""\ndone\n'
    assert G.apply_cap_rule(body, "l2", {"x"}, {"oltp"}) == body


def _env(tmp_path):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = {k: v for k, v in os.environ.items() if k != "BENCH_INSTRUMENT"}
    env.update(ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    return env


def _gen(tmp_path, name, *extra):
    out = tmp_path / name
    r = subprocess.run([sys.executable, str(HERE / "make_2611_stages.py"), "--second-list", "--out", str(out),
                        "--after", "none", *extra], cwd=HERE, env=_env(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return out


@pytest.fixture(scope="module")
def modes(tmp_path_factory):
    t = tmp_path_factory.mktemp("caprule")
    return {"biggest-last": _gen(t, "biglast"), "paper": _gen(t, "paper", "--order", "paper", "--reps", "5")}


@pytest.mark.parametrize("mode", ["biggest-last", "paper"])
def test_every_mode_emits_the_helpers_at_the_patched_insertion_points_and_still_parses(modes, mode):
    stages = sorted(modes[mode].glob("*.sh"))
    assert stages
    for f in stages:
        text = f.read_text()
        assert text.count("declare -A CENSORED_AT") == 1, f.name
        assert text.index("declare -A CENSORED_AT") < text.index("run_overlay() {"), f.name
        assert 'cap_rule_skip "$label" "$be|$wl|" && return 0' in text, f.name
        assert 'cap_rule_skip "$label" "$be|$wl|$dur" && return 0' in text, f.name
        assert re.search(r'cap_rule_note "\$be\|\$wl\|\$dur" "\$scale"\n    say "\$ID: \$label rep ', text), f.name
        assert subprocess.run(["bash", "-n", str(f)]).returncode == 0, f.name


def test_the_emitted_helpers_are_the_ones_patched_into_the_live_stages(modes):
    text = sorted(modes["paper"].glob("*.sh"))[0].read_text()
    assert G.CAP_RULE_HELPERS.strip("\n") in text
    assert "grep -E '^\\s+\\[[0-9]+/[0-9]+\\] ' \"$S\" | tail -1 | grep -q -- '-> timeout_after_'" in text


def test_a_cap_is_lowered_to_the_rule_and_the_seeding_reaches_a_later_stage(modes):
    text = "\n".join(f.read_text() for f in sorted(modes["paper"].glob("*.sh")))
    assert re.search(r'run_cell "l2/sf10/\$BE/oltp" sf10 8685 ', text)
    assert re.search(r'run_cell "l2/sf10/\$BE/oltp strict" sf10 9031 ', text)
    assert 'CENSORED_AT["surrealdb_lifecycle|graph|"]="lc1m"' in text
    assert 'CENSORED_AT["surrealdb_lifecycle|vector|"]="lc100k"' in text
    assert 'CENSORED_AT["surrealdb_tpc|olap|"]="tpch1"' in text
    # the arm is seeded above the scale it was censored at and not at it
    stage = next(f.read_text() for f in sorted(modes["paper"].glob("*.sh"))
                 if 'CENSORED_AT["surrealdb_tpc|olap|"]="tpch1"' in f.read_text())
    assert stage.index('CENSORED_AT["surrealdb_tpc|olap|"]') > stage.index('run_cell "l1tpc/tpch1/$BE/olap"')


def test_a_cap_the_tier_has_lower_than_the_rule_is_not_raised(modes):
    d = C.load()
    for f in modes["paper"].glob("*.sh"):
        for lane, scale, wl, strict, cap in re.findall(r'run_cell "([a-z0-9]+)/([a-z0-9_]+)/\$BE/([a-z_0-9]+)( strict)?" \S+ (\d+)',
                                                      f.read_text()):
            r = C.rule_cap(lane, scale, wl, "strict" if strict else "", d)
            assert r is None or int(cap) <= r or int(cap) == min(int(cap), r), (f.name, lane, scale, wl)
            if r is not None:
                assert int(cap) <= r


def _bash(script_text, call, tmp_path, status_text):
    s = tmp_path / "STATUS.txt"
    s.write_text(status_text)
    fn = lambda n: re.search(rf"^{n}\(\) \{{.*?^\}}$", script_text, re.S | re.M).group(0)  # noqa: E731
    body = (f'say() {{ echo "$*"; }}\nS={s}\nID=T\n{G.CAP_RULE_HELPERS}\n{fn("cap_rule_skip")}\n{fn("cap_rule_note")}\n{call}\n')
    return subprocess.run(["bash", "-c", body], capture_output=True, text=True)


def test_the_helpers_remember_a_timeout_and_nothing_else(tmp_path):
    text = G.CAP_RULE_HELPERS
    timeout = "  [3/9] l2_x_oltp_sf1_r1 7200.0s (0-3) -> timeout_after_7200s\n"
    r = _bash(text, 'cap_rule_note "x|oltp|" sf1; cap_rule_skip "lbl" "x|oltp|" && echo SKIPPED', tmp_path, timeout)
    assert "SKIPPED" in r.stdout and "censored at sf1" in r.stdout
    r = _bash(text, 'cap_rule_note "x|oltp|" sf1; cap_rule_skip "lbl" "x|oltp|" || echo RUNS',
              tmp_path, "  [3/9] l2_x_oltp_sf1_r1 12.0s (0-3) -> error_rc_1\n")
    assert "RUNS" in r.stdout
    r = _bash(text, 'cap_rule_note "x|oltp|" sf1; cap_rule_note "x|oltp|" sf10; cap_rule_skip "lbl" "x|oltp|"',
              tmp_path, timeout)
    assert "censored at sf1," in r.stdout          # the smallest scale is kept
    r = _bash(text, 'cap_rule_note "x|oltp|" sf1; cap_rule_skip "lbl" "x|oltp|strict" || echo RUNS', tmp_path, timeout)
    assert "RUNS" in r.stdout                      # the strict class is its own cell


# ------------------------------------------------------------------- the report
@pytest.fixture()
def E(monkeypatch):
    import export_web
    data = {"rule": {"pin": "d36b4ca3a"}, "caps": {"l1tpc|tpch10|olap|": {"cap_s": 9000}},
            "over_rule": [dict(lane="l1tpc", scale="tpch1", backend="surrealdb_tpc", workload="olap", cls="", median_s=9999.0, cap_s=7326),
                          dict(lane="l1tpc", scale="tpch1", backend="surrealdb_tpc", workload="oltp", cls="strict", median_s=9999.0, cap_s=7326)],
            "timeouts": [dict(lane="l3d", scale="small", backend="surrealdb_dense", workload="search", cls="", cap_s=7200)]}
    monkeypatch.setitem(C._CACHE, C.RULE_JSON, data)
    monkeypatch.setenv("BENCH_ENGINE_COMMIT", "d36b4ca3a")          # the rule is read for its own pin only
    return export_web


def test_an_over_rule_cell_is_censored_at_the_rule_cap_and_the_larger_scale_names_the_smaller(E):
    got = E._rule_censored(taken=set(), clean=set())
    cell = got[("l1tpc", "tpch1", "surrealdb_tpc", "olap")]
    assert int(cell) == 7326 and cell.at is None
    assert E._outcome_kind(cell) == ("censored", ">122m")
    big = got[("l1tpc", "tpch10", "surrealdb_tpc", "olap")]
    assert int(big) == 9000 and big.at == "tpch1"
    assert ("l1tpc", "tpch1", "surrealdb_tpc", "oltp") not in got      # the strict class is the durability table's
    assert ("l3d", "deep10m", "surrealdb_dense", "search") in got      # a pass-1 TIMEOUT censors the larger scale too


def test_a_larger_scale_with_its_own_outcome_or_row_is_left_alone(E):
    got = E._rule_censored(taken={("l1tpc", "tpch10", "surrealdb_tpc", "olap")}, clean={("l3d", "deep10m", "surrealdb_dense", "search")})
    assert ("l1tpc", "tpch10", "surrealdb_tpc", "olap") not in got
    assert ("l3d", "deep10m", "surrealdb_dense", "search") not in got


def test_the_data_is_read_only_for_its_own_pin(E, monkeypatch):
    monkeypatch.setenv("BENCH_ENGINE_COMMIT", "0123456789")
    assert E._rule_censored(set(), set()) == {}


def test_the_notes_say_what_the_rule_did(E, monkeypatch):
    monkeypatch.setattr(E, "_CENSORED_CACHE", E._rule_censored(set(), set()))
    notes = E._censored_notes("docs_olap")
    text = " ".join(notes)
    assert "took longer than the cap rule's 7,326 s" in text and "numbers are not printed" in text
    assert "was already censored at" in text and "cap rule censors it at every larger size" in text
