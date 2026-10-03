"""overrides.py and the three places it is held (CAMPAIGN section 7 row 21).

Run with `python -m pytest test_overrides.py -q` from this directory.

Each test names what it protects. The ones that matter most are the two that
prove a check can fail: the page gate on a table that lost its sentence, and the
row gate on a row that lost its stamp.
"""
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import overrides as OV  # noqa: E402

PROTOCOL = HERE / "PROTOCOL.md"

# PROTOCOL section 7 rows that still say NOWHERE, by a distinctive substring of
# their Setting cell, with the reason each is not done. Empty is the goal. A row
# may only be added here with a reason a reader of the report can act on.
NOT_DONE = {}


def _split_row(line):
    """Cells of one markdown table row, honouring backticks (a `|` inside code
    is not a separator)."""
    cells, cur, tick = [], [], False
    for ch in line.strip().strip("|"):
        if ch == "`":
            tick = not tick
        if ch == "|" and not tick:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    return cells


def _section7_rows():
    text = PROTOCOL.read_text(encoding="utf-8")
    sec = text.split("## 7. Defaults and sanctioned overrides", 1)[1]
    sec = re.split(r"\n## ", sec, maxsplit=1)[0]
    rows = []
    for line in sec.splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Engine |"):
            continue
        cells = _split_row(line)
        if len(cells) >= 5:
            rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# the registry, against the code that runs and the document that lists

def test_keys_are_unique_and_every_override_has_a_carrier():
    keys = [o.key for o in OV.OVERRIDES]
    assert len(keys) == len(set(keys))
    for o in OV.OVERRIDES:
        assert o.carriers, o.key
        assert o.says, o.key


def test_every_carrier_is_an_arm_the_runner_registers():
    import runner
    for o in OV.OVERRIDES:
        for c in o.carriers:
            assert c.lane in runner.LANES, (o.key, c)
            assert c.backend in runner.LANES[c.lane][1], (o.key, c)
            assert c.backend in runner.BACKENDS, (o.key, c)


def test_cap_carriers_are_exactly_the_served_arcadedb_arms_the_runner_launches():
    """A served ArcadeDB arm added by copying one of the runner's dicts must
    join the registry, or a table that shows it would carry no sentence."""
    from_runner = {(lane, be) for lane, be in OV.served_arcadedb_from_runner()
                   if lane not in ("l1", "e4")}
    assert from_runner == set(OV.CAP_CARRIERS)
    assert OV.runner_cap() == 5000000


def test_protocol_cites_every_key_once_and_none_of_those_rows_says_nowhere():
    rows = _section7_rows()
    cited = {}
    for cells in rows:
        for key in re.findall(r"`override: (\w+)`", cells[-1]):
            cited.setdefault(key, []).append(cells)
    for o in OV.OVERRIDES:
        assert len(cited.get(o.key, [])) == 1, f"PROTOCOL.md section 7 must cite `override: {o.key}` in exactly one row"
    for key in cited:
        assert key in OV.BY_KEY, f"PROTOCOL.md cites `override: {key}`, which overrides.py does not register"
    for key, hits in cited.items():
        for cells in hits:
            assert "NOWHERE" not in cells[-1], f"`override: {key}` is cited by a row that also says NOWHERE"


def test_no_other_row_says_nowhere():
    left = [cells for cells in _section7_rows() if "NOWHERE" in cells[-1]]
    for cells in left:
        assert any(frag in cells[1] or frag in cells[0] for frag in NOT_DONE), (
            f"a PROTOCOL.md section 7 row says NOWHERE and is neither disclosed nor listed in NOT_DONE: {cells[0]} | {cells[1][:60]}")
    for frag in NOT_DONE:
        assert any(frag in c[1] or frag in c[0] for c in left), f"NOT_DONE lists {frag!r}, which no longer says NOWHERE"


# ---------------------------------------------------------------------------
# the sentences

SAMPLE_ROWS = {
    "arcadedb_query_cap": [{"server_query_max_heap_elements": "5000000"}],
    "neo4j_checkpoint": [{"neo4j_checkpoint_interval": "5s", "neo4j_checkpoint_interval_default": "15m"}],
}


def test_every_sentence_says_what_its_gate_asks_for_and_registers_its_digits():
    for o in OV.OVERRIDES:
        text, values = o.sentence(SAMPLE_ROWS.get(o.key, []))
        for pat in o.says:
            assert re.search(pat, text), (o.key, pat, text)
        digits = re.findall(r"\d(?:[\d,]*\d)?(?:\.\d+)?", text.replace("Neo4j", "Neo"))
        for d in digits:
            assert d in values, f"{o.key}: the sentence carries {d!r} and registers no source for it: {text}"
        assert "\u2014" not in text and "--" not in text, o.key


def test_the_cap_sentence_quotes_the_value_the_rows_stamped_and_never_a_typed_one():
    text, values = OV.BY_KEY["arcadedb_query_cap"].sentence([{"server_query_max_heap_elements": "7500000"}])
    assert "7,500,000" in text and values == ["7,500,000"]
    text, values = OV.BY_KEY["arcadedb_query_cap"].sentence([])
    assert not re.search(r"\d", text) and values == []


def test_the_checkpoint_sentence_takes_its_numbers_from_the_engine_and_degrades_without_them():
    text, values = OV.BY_KEY["neo4j_checkpoint"].sentence(SAMPLE_ROWS["neo4j_checkpoint"])
    assert "every 5 seconds" in text and "every 15 minutes" in text and values == ["5", "15"]
    text, values = OV.BY_KEY["neo4j_checkpoint"].sentence([])
    assert not re.search(r"\d", text.replace("Neo4j", "Neo")) and values == []


# ---------------------------------------------------------------------------
# page_check's half: a table that shows the arm and prints no sentence fails

def _table(tid, backend, conditions):
    return {"id": tid, "instrument": "2026-10", "entries": [{"backend_key": backend}],
            "conditions": conditions}


# page table id <-> lane, as export_web._TABLE_LANE has it for the tables that carry an arm
TABLE_OF_LANE = {"l3s": "l3s", "l3d": "l3d", "l2": "l2", "l4": "l4", "e2": "e2",
                 "l1tpc": "docs_oltp", "lifecycle": "lifecycle", "restart": "restart"}
LANE_OF = {v: k for k, v in TABLE_OF_LANE.items()}.get
CARRIERS = [(o, c) for o in OV.OVERRIDES for c in o.carriers]


def _sentences_owed(lane, backend):
    return {o.key: o.sentence(SAMPLE_ROWS.get(o.key, []))[0] for o in OV.OVERRIDES
            if any(c.lane == lane and c.backend == backend for c in o.carriers)}


@pytest.mark.parametrize("o,c", CARRIERS, ids=lambda x: x.key if hasattr(x, "key") else f"{x.lane}.{x.backend}")
def test_a_table_that_shows_the_arm_must_carry_the_sentence(o, c):
    tid = TABLE_OF_LANE[c.lane]
    owed = _sentences_owed(c.lane, c.backend)
    full = ["some other sentence"] + list(owed.values())
    # with every sentence the table owes: clean
    assert OV.sentence_findings([_table(tid, c.backend, full)], LANE_OF, None) == []
    # without this override's: the gate fails, and it names the override
    without = [x for x in full if x != owed[o.key]]
    found = OV.sentence_findings([_table(tid, c.backend, without)], LANE_OF, None)
    assert [f for f in found if f"`{o.key}`" in f], found
    # reworded until it no longer says the thing: also fails
    vague = without + ["This table runs some engines with settings."]
    assert [f for f in OV.sentence_findings([_table(tid, c.backend, vague)], LANE_OF, None) if f"`{o.key}`" in f]


def test_a_table_with_no_such_arm_owes_nothing():
    assert OV.sentence_findings([_table("l3s", "qdrant_sparse", [])], LANE_OF, None) == []


def test_the_artifact_backed_e4_table_owes_the_cap_sentence_from_the_runner_constant():
    e4 = {"id": "e4", "instrument": "2026-10", "entries": [{"backend": "1,000 documents"}], "conditions": []}
    assert any("arcadedb_query_cap" in f for f in OV.sentence_findings([e4], lambda tid: None, None))
    (text, values), = [n for n in OV.notes_for_table("e4", None, [], []) if "ArcadeDB server" in n[0]]
    assert "5,000,000" in text and values == ["5,000,000"]
    e4["conditions"] = [text]
    assert OV.sentence_findings([e4], lambda tid: None, None) == []


def test_notes_for_table_follow_the_arms_on_the_table_and_its_lane():
    keys = lambda notes: " ".join(n[0] for n in notes)    # noqa: E731
    es = keys(OV.notes_for_table("l3s", "l3s", ["elasticsearch_sparse", "qdrant_sparse"], []))
    assert "Elasticsearch" in es and "replica" in es and "DuckDB" not in es
    # the same backend on a lane it is not registered for gets nothing
    assert OV.notes_for_table("l3s", "l3s", ["neo4j_dense"], []) == []
    # a derived table has no lane and no entries
    assert OV.notes_for_table("durability", None, [], []) == []


# ---------------------------------------------------------------------------
# fairness_check's half: a row without the engine's own answer fails

def _row(**kw):
    base = {"instrument": "2026-10", "scale": "micro", "workload": "search", "cpuset": "0-11"}
    base.update(kw)
    return base


def test_rows_of_a_carrier_arm_must_carry_the_stamp():
    r = _row(lane="l3s", backend="elasticsearch_sparse")
    found, judged = OV.stamp_findings([r])
    assert judged == 2 and {f["key"] for f in found} == {"es_security", "es_replicas"}
    assert all(f["kind"] == "NOT STAMPED" for f in found)
    r.update(es_security_enabled=False, es_replicas=0)
    assert OV.stamp_findings([r]) == ([], 2)


def test_a_stamp_that_contradicts_the_sentence_fails():
    r = _row(lane="l3s", backend="elasticsearch_sparse", es_security_enabled=True, es_replicas=1)
    found, _ = OV.stamp_findings([r])
    assert {f["kind"] for f in found} == {"WRONG"} and len(found) == 2


def test_a_failed_read_back_is_named_on_the_finding():
    r = _row(lane="l3s", backend="elasticsearch_sparse", es_readback_error="ConnectionError: refused")
    found, _ = OV.stamp_findings([r])
    assert all("ConnectionError" in f["text"] for f in found)


def test_september_rows_and_other_lanes_are_not_judged():
    assert OV.stamp_findings([_row(lane="l3s", backend="elasticsearch_sparse", instrument="2026-09")]) == ([], 0)
    assert OV.stamp_findings([_row(lane="l1", backend="duckdb")]) == ([], 0)


def test_duckdb_threads_are_held_to_the_cells_own_cpuset():
    ok = _row(lane="l4", backend="duckdb", cpuset="0-11", duckdb_threads=12)
    assert OV.stamp_findings([ok]) == ([], 1)
    # a PRAGMA that did not take: the host's 20 threads in a 12-CPU cell
    bad = _row(lane="l4", backend="duckdb", cpuset="0-11", duckdb_threads=20)
    found, _ = OV.stamp_findings([bad])
    assert found[0]["kind"] == "WRONG" and "20 threads in a 12-CPU cell" in found[0]["text"]
    # the cpuset spelling the page uses elsewhere
    assert OV.cpuset_size("0-5,8-11") == 10 and OV.cpuset_size("3") == 1


def test_the_duckpgq_arm_uses_its_own_field_name():
    r = _row(lane="l2", backend="duckpgq_graph", cpuset="0-11")
    assert [f["field"] for f in OV.stamp_findings([r])[0]] == ["duckpgq_threads"]
    r["duckpgq_threads"] = "12"            # a frozen csv row carries strings
    assert OV.stamp_findings([r]) == ([], 1)


def test_neo4j_page_cache_is_held_to_what_the_cell_passed():
    ok = _row(lane="l2", backend="neo4j_graph", neo4j_pagecache="1.50GiB", server_pagecache="1.5g",
              neo4j_checkpoint_interval="5s")
    assert OV.stamp_findings([ok]) == ([], 2)
    # the image's fixed default where the cell passed a fitted size
    bad = dict(ok, neo4j_pagecache="512.00MiB", server_pagecache="19.0g")
    found, _ = OV.stamp_findings([bad])
    assert [f["field"] for f in found] == ["neo4j_pagecache"] and found[0]["kind"] == "WRONG"
    assert OV.size_bytes("1.50GiB") == OV.size_bytes("1.5g") == 1.5 * (1 << 30)
    assert OV.duration_words("5s") == ("5", "seconds") and OV.duration_words("1m") == ("1", "minute")


def test_the_served_arcadedb_cap_is_the_runners_cap():
    ok = _row(lane="l1tpc", backend="arcadedb_server", server_query_max_heap_elements=5000000)
    assert OV.stamp_findings([ok]) == ([], 1)
    lower = dict(ok, server_query_max_heap_elements=500000)
    assert OV.stamp_findings([lower])[0][0]["kind"] == "WRONG"
    # an embedded arm sets nothing, so nothing is asked of it
    assert OV.stamp_findings([_row(lane="l1tpc", backend="arcadedb_embedded")]) == ([], 0)


def test_hierarchy_must_say_whether_it_was_read_or_requested():
    r = _row(lane="l3d", backend="arcadedb_dense_embedded", arcadedb_add_hierarchy=True)
    found, _ = OV.stamp_findings([r])
    assert [(f["key"], f["kind"]) for f in found] == [("arcadedb_hierarchy", "WRONG")]
    r["arcadedb_add_hierarchy_source"] = "index metadata read back from the engine"
    assert OV.stamp_findings([r]) == ([], 1)
    # the served arm records a request, and carries the runner's other server stamps
    srv = _row(lane="l3d", backend="arcadedb_dense_server", arcadedb_add_hierarchy=True,
               arcadedb_add_hierarchy_source="requested in the CREATE INDEX statement",
               server_query_max_heap_elements=5000000)
    assert OV.stamp_findings([srv])[0] == []


def test_the_ts_native_arms_must_record_what_ingest_left_unsealed():
    assert OV.stamp_findings([_row(lane="l4", backend="arcadedb_ts_native")])[0][0]["kind"] == "NOT STAMPED"
    assert OV.stamp_findings([_row(lane="l4", backend="arcadedb_ts_native", ts_mutable_at_ingest_end=0)]) == ([], 1)
    # -1 is the lane's "could not read it"
    assert OV.stamp_findings([_row(lane="l4", backend="arcadedb_ts_native", ts_mutable_at_ingest_end=-1)])[0][0]["kind"] == "WRONG"


def test_every_stamp_field_is_a_declared_not_printed_field():
    """A numeric field a lane records must be printed or declared (page_check
    A2); each field an override stamps is declared with its reason."""
    import page_check
    for f in sorted(OV.STAMP_FIELDS):
        assert page_check._not_printed_reason(f), f"{f} is stamped for an override and declared nowhere in NOT_PRINTED"


# ---------------------------------------------------------------------------
# the manifest

def test_the_manifest_records_engine_configuration_and_the_overrides_in_force(monkeypatch):
    import runner
    monkeypatch.setattr(runner, "image_digest", lambda image: "sha256:test")
    monkeypatch.setenv("BENCH_ES_PRUNE", "1")
    monkeypatch.setenv("TS_NUMPY", "0")
    monkeypatch.setenv("HOME_UNRELATED", "x")
    args = SimpleNamespace(tier="paper", scale="micro", reps=5, seed=7)
    jobs = [{"backend": b} for b in ("elasticsearch_sparse", "neo4j_graph", "arcadedb_graph_server",
                                      "duckdb", "elasticsearch_sparse")]
    m = runner.build_manifest("20261003T000000Z", args, 1, ["0-11"], jobs)
    # what it always held
    for k in ("ts", "tier", "scale", "cpuset", "workers", "shards", "reps", "seed", "mem", "heap",
              "server_mem_fraction", "images"):
        assert k in m
    assert m["images"] and set(m["images"].values()) == {"sha256:test"}
    # what row 21 adds
    cfg = m["engine_config"]
    assert set(cfg) == {"elasticsearch_sparse", "neo4j_graph", "arcadedb_graph_server", "duckdb"}
    assert "xpack.security.enabled=false" in cfg["elasticsearch_sparse"]["server_env"]
    assert cfg["elasticsearch_sparse"]["overrides"] == ["es_replicas", "es_security"]
    assert "NEO4J_db_checkpoint_interval_time=5s" in cfg["neo4j_graph"]["server_env"]
    assert cfg["neo4j_graph"]["overrides"] == ["neo4j_checkpoint", "neo4j_pagecache"]
    assert any("queryMaxHeapElementsAllowedPerOp=5000000" in e for e in cfg["arcadedb_graph_server"]["server_env"])
    assert cfg["arcadedb_graph_server"]["overrides"] == ["arcadedb_query_cap"]
    assert cfg["duckdb"]["overrides"] == ["duckdb_threads"] and cfg["duckdb"]["server_env"] == []
    assert m["runner_env"]["BENCH_ES_PRUNE"] == "1" and m["runner_env"]["TS_NUMPY"] == "0"
    assert "HOME_UNRELATED" not in m["runner_env"]


def test_the_manifest_records_the_strict_class_patch_the_server_was_given(monkeypatch):
    import runner
    monkeypatch.setattr(runner, "image_digest", lambda image: "sha256:test")
    monkeypatch.setenv("BENCH_DURABILITY", "strict")
    args = SimpleNamespace(tier="paper", scale="micro", reps=5, seed=7)
    m = runner.build_manifest("20261003T000000Z", args, 1, ["0-11"], [{"backend": "arcadedb_graph_server"}])
    c = m["engine_config"]["arcadedb_graph_server"]
    assert c["durability_class"] == "strict" and c["durability_server_flags"] == "txWalFlush=2"
    assert any("-Darcadedb.txWalFlush=2" in e for e in c["server_env"])
