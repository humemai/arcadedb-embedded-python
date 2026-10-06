"""`make_2610_stages.py --order tiers` (DECISIONS #163): every ArcadeDB arm first, the other engines already run second,
new versions and new arms last.

Run with `python -m pytest test_stage_tiers.py -q -rs` from this directory.

The order is the user's queue priority for the 26.10.1 measurement. What these tests hold fixed is what could silently go
wrong when a stage is split three ways: an arm that lands in no stage or two (the coverage proof), an ArcadeDB arm queued
behind a comparator, a tier-3 arm ahead of a tier-2 one, a split piece that loses the repetitions or the durability class
its arm declares, and ids that collide with the chain already in STATUS.txt (a killed stage writes ALL-DONE through its EXIT
trap, so a chain reusing qRA..qRO would start every stage at once).
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2610_stages as G  # noqa: E402
import runner  # noqa: E402


def _tiers_of(spec):
    return {G.tier_of(b) for b in G.stage_backends(spec)}


def test_every_registered_arm_has_exactly_one_tier_and_the_lists_name_real_arms():
    assert G.check_tiers() == []
    for lane, spec in runner.LANES.items():
        for be in spec[1]:
            assert G.tier_of(be) in (1, 2, 3), (lane, be)
    assert all(G.tier_of(b) == 1 for spec in runner.LANES.values() for b in spec[1] if b.startswith("arcadedb"))
    assert not set(G.TIER3_MOVED) & set(G.TIER3_NEW)


def test_a_typo_in_the_tier_list_is_a_problem(monkeypatch):
    monkeypatch.setattr(G, "TIER3", G.TIER3 + ("arangodb_graf",))
    assert any("arangodb_graf" in p for p in G.check_tiers())


def test_the_tiered_stages_still_cover_every_arm_exactly_once():
    problems, _excluded, _counts = G.check_coverage(G.tiered_stages())
    assert problems == []


def test_every_stage_holds_one_tier_and_the_tiers_come_in_order():
    seen = []
    for spec in G.tiered_stages():
        if spec[2] == "pycost":
            seen.append(1)
            continue
        tiers = _tiers_of(spec)
        assert len(tiers) == 1, (spec[0], spec[2], tiers)
        seen.append(tiers.pop())
    assert seen == sorted(seen), "a tier-2 stage ahead of a tier-1 stage, or tier 3 ahead of tier 2"
    assert {1, 2, 3} <= set(seen)


def test_no_arcadedb_arm_runs_behind_a_comparator():
    first_other = None
    for i, spec in enumerate(G.tiered_stages()):
        names = [] if spec[2] == "pycost" else G.stage_backends(spec)
        if any(not b.startswith("arcadedb") for b in names) and first_other is None:
            first_other = i
        if first_other is not None:
            assert not any(b.startswith("arcadedb") for b in names), (spec[0], names)
            assert spec[2] != "pycost", "the host-side Python-cost stage belongs to tier 1"


def test_ids_are_new_unique_and_numbered():
    ids = [s[0] for s in G.tiered_stages()]
    assert ids == [f"qT{i:02d}" for i in range(1, len(ids) + 1)]
    old = {s[0] for s in G.STAGES}
    assert not old & set(ids), "a reused id finds the old chain's ALL-DONE marker in STATUS.txt"


def test_a_split_piece_keeps_the_lane_guards_scales_and_workloads_of_its_stage():
    by_lane = {}
    for spec in G.STAGES:
        by_lane.setdefault((spec[2], tuple(spec[3]), tuple(spec[4])), spec)
    for piece in G.tiered_stages():
        if piece[2] == "pycost":
            continue
        base = by_lane[(piece[2], tuple(piece[3]), tuple(piece[4]))]
        assert list(piece[5]) == list(base[5]) and piece[6] == base[6] and list(piece[7]) == list(base[7])


def test_the_restricted_arm_keeps_its_repetitions_and_durability_class():
    pieces = [s for s in G.tiered_stages() if "arcadedb_imgdefaults_server" in (G.stage_backends(s) if s[2] != "pycost" else [])]
    assert len(pieces) == 1
    piece = pieces[0]
    cfg = runner.restricted_arms("l1tpc")["arcadedb_imgdefaults_server"]
    assert f"REPS={cfg['reps']}" in piece[7] and piece[9] == cfg["durability"]
    assert G.stage_backends(piece) == ["arcadedb_imgdefaults_server"]


def test_the_server_restart_comparators_of_moved_engines_are_tier_3():
    for be in ("arangodb_tpc", "falkordb_graph", "elasticsearch_dense"):
        assert G.tier_of(be) == 3
    for be in ("arcadedb_server", "arcadedb_graph_server", "arcadedb_dense_server", "arcadedb_ts_native_server"):
        assert G.tier_of(be) == 1
    for be in ("postgres", "mongodb", "neo4j_graph", "qdrant_dense", "questdb"):
        assert G.tier_of(be) == 2


def _generate(tmp_path, order, after="none"):
    wheel = tmp_path / "arcadedb_embedded-26.10.1-cp312-cp312-manylinux_2_34_x86_64.whl"
    wheel.write_bytes(b"not a real wheel, only its name and sha256 are read")
    env = dict(os.environ, ARCADEDB_WHEEL=str(wheel), ARCADEDB_SERVER_IMAGE="arcadedb-c25:26.10.1",
               ARCADEDB_ENGINE_COMMIT="d36b4ca3ae4c170abc73598e0dffa2bb58e06621")
    out = tmp_path / "stages"
    r = subprocess.run([sys.executable, str(HERE / "make_2610_stages.py"), "--out", str(out), "--order", order,
                        "--after", after], cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return out


def test_the_emitted_tier_chain_is_linear_parses_and_starts_without_a_wait(tmp_path):
    out = _generate(tmp_path, "tiers")
    ids = [s[0] for s in G.tiered_stages()]
    assert sorted(p.stem for p in out.glob("*.sh")) == ids
    for prev, sid in zip([None] + ids[:-1], ids):
        text = (out / f"{sid}.sh").read_text()
        waits = [l for l in text.splitlines() if l.startswith("while ! grep -q") and "ALL-DONE" in l]
        assert (waits == []) if prev is None else (len(waits) == 1 and f'"{prev} ALL-DONE"' in waits[0]), sid
        assert subprocess.run(["bash", "-n", str(out / f"{sid}.sh")], capture_output=True).returncode == 0, sid
    # the first stage is ArcadeDB only; the roster of a tier-2 stage names no ArcadeDB arm
    first = (out / f"{ids[0]}.sh").read_text()
    roster = [l for l in first.splitlines() if l.startswith('BACKENDS="')][0]
    assert "arcadedb_graph_embedded" in roster and "neo4j" not in roster
