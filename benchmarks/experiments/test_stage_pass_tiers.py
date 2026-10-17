"""`make_2610_stages.py --pass-tiers` (DECISIONS #183, #184): the ArcadeDB-only pass on a new release emits tier 1 alone,
every declared rep, and its coverage proof holds for the tier-1 arms only.

Run with `python -m pytest test_stage_pass_tiers.py -q -rs` from this directory.

What these tests hold fixed: a filtered list that drops an ArcadeDB arm, or keeps a comparator, would either leave a
table without its ArcadeDB rows or re-measure a comparator on a pin that is ArcadeDB's alone; the unfiltered list must not
change; and the flag must refuse the combinations that would silently mean something else.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2610_stages as G  # noqa: E402
import runner  # noqa: E402


def _backends(stages):
    return {be for spec in stages for be in G.stage_backends(spec)}


def test_tier_one_alone_holds_every_arcadedb_arm_and_nothing_else():
    stages = G.tiered_stages(prefix="qA", tiers={1})
    assert stages, "the filter emitted nothing"
    assert all(G.tier_of(be) == 1 for be in _backends(stages))
    every_t1 = {be for spec in G.STAGES for be in G.stage_backends(spec) if G.tier_of(be) == 1}
    assert _backends(stages) == every_t1


def test_tier_one_alone_passes_its_coverage_proof():
    problems, _excluded, counts = G.check_coverage(G.tiered_stages(prefix="qA", tiers={1}), tiers={1})
    assert problems == []
    assert sum(counts.values()) > 0
    assert all(n <= sum(G.tier_of(be) == 1 for be in runner.LANES[lane][1]) for lane, n in counts.items())


def test_the_coverage_proof_still_catches_a_dropped_or_a_foreign_arm():
    stages = G.tiered_stages(prefix="qA", tiers={1})
    dropped = [s for s in stages if s[2] != stages[0][2] or s[2] == "pycost"]
    assert G.check_coverage(dropped, tiers={1})[0], "a lane's tier-1 arms left out must be a problem"
    tier2 = [s for s in G.tiered_stages(prefix="qX") if any(G.tier_of(be) == 2 for be in G.stage_backends(s))][:1]
    assert any("tier 2 arm" in p for p in G.check_coverage(stages + tier2, tiers={1})[0])


def test_the_python_cost_stage_rides_with_tier_one_and_ids_take_the_prefix():
    stages = G.tiered_stages(prefix="qA", tiers={1})
    assert sum(s[2] == "pycost" for s in stages) == sum(s[2] == "pycost" for s in G.STAGES)
    assert not any(s[2] == "pycost" for s in G.tiered_stages(prefix="qA", tiers={2}))
    assert [s[0] for s in stages] == [f"qA{i + 1:02d}" for i in range(len(stages))]


def test_no_filter_is_the_list_it_always_was():
    assert G.tiered_stages(prefix="qT") == G.tiered_stages(prefix="qT", tiers=None)
    assert G.tiered_stages(prefix="qT") == G.tiered_stages(prefix="qT", tiers={1, 2, 3})


def test_the_flag_refuses_the_top_up_and_the_paper_order(capsys):
    with pytest.raises(SystemExit, match="top-up pass takes --tiers"):
        G.main(["--rep-from", "4", "--roster", "unused.json", "--pass-tiers", "1"])
    with pytest.raises(SystemExit, match="needs --order tiers"):
        G.main(["--check", "--order", "paper", "--pass-tiers", "1"])
