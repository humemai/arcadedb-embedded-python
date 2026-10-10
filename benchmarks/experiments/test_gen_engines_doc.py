"""gen_engines_doc.py: the DBBench Engines page, generated from rows and the override registry.

Run with `uv run pytest benchmarks/experiments/test_gen_engines_doc.py -q` from the repo root.

What each test protects:
  * an arm with an override gets the registry's sentence, built from ITS rows; one without gets none;
  * a failed cell is on the page with its error;
  * a lane without rows says so, and an arm the runner registers without a row is named;
  * two runs give the same bytes, and the row-set identity is the sha256 of the sorted row ids;
  * no digit on the page is absent from the rows (the user's rule: no number is ever typed by hand);
  * the row selection is the one the published tables use, not a second one.
"""
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gen_engines_doc as G  # noqa: E402
import overrides as OV  # noqa: E402

LANES_TS = Path.home() / "repos" / "humemai" / "humem.ai" / "src" / "lib" / "dbbench" / "lanes.ts"
DATE = "2031-04-05"


def row(**kw):
    """A clean October row of the graph lane, with the fields the page reads."""
    r = {
        "run_id": "l2_x_r1", "ts_utc": "2026-10-01T00:00:00+00:00", "instrument": "2026-10",
        "lane": "l2", "scale": "sf1", "workload": "oltp", "backend": "falkordb_graph", "rep": 1,
        "rc": 0, "cpuset": "0-11", "error": None, "topology": "client_server",
        "engine_version": "falkordb:4.20.6 (redis 8.6.3)", "durability_class": "relaxed",
        "durability": "appendonly=no: nothing is synced at commit",
        "mem_cap": "8g", "heap": None, "server_image_ref": "falkordb/falkordb@sha256:0a9fe4d1ee0b",
        "server_image": "sha256:0a9fe4d1ee0b",
    }
    r.update(kw)
    return r


def neo4j_rows():
    out = []
    for scale, cache in (("sf1", "3.00GiB"), ("sf10", "11.00GiB")):
        for cls, text in (("relaxed", "fsync at commit"), ("strict", "fsync at commit")):
            out.append(row(run_id=f"n_{scale}_{cls}", backend="neo4j_graph", scale=scale, durability_class=cls,
                           durability=text, engine_version="neo4j:2026.08.1",
                           server_image_ref="neo4j@sha256:e702d6b535d9",
                           neo4j_pagecache=cache, neo4j_checkpoint_interval="5s",
                           neo4j_checkpoint_interval_default="15m", server_pagecache=cache.replace("GiB", "g")))
    return out


def fixture():
    clean = neo4j_rows() + [row(run_id="f1"), row(run_id="f2", scale="sf10", mem_cap="24g")]
    failed = [row(run_id="a1", backend="arangodb_graph", scale="sf10", rc=-1, error="timeout_after_7200s",
                  ts_utc="2026-10-02T00:00:00+00:00")]
    registered = {"l2": ("neo4j_graph", "falkordb_graph", "arangodb_graph", "ghost_graph")}
    return clean, failed, registered


def page():
    clean, failed, registered = fixture()
    return G.render(clean, failed, registered, DATE)


# ---------------------------------------------------------------------------
# what the page says

def test_banner_date_and_row_identity_are_at_the_top():
    clean, failed, _ = fixture()
    text = page()
    head = text.splitlines()[:8]
    assert head[0] == "# Engines"
    assert G.BANNER in "\n".join(head)
    n, digest = G.row_set_identity(clean + failed)
    assert f"Generated on {DATE}. Row set: {n} rows, sha256 {digest}" in "\n".join(head)
    ids = sorted(G.row_id(r) for r in clean + failed)
    import hashlib
    assert digest == hashlib.sha256("\n".join(ids).encode()).hexdigest()
    assert n == len(ids)


def test_an_arm_with_an_override_gets_the_registry_sentence_built_from_its_rows():
    text = page()
    block = text.split("#### Neo4j: `neo4j_graph`", 1)[1].split("#### ", 1)[0]
    rows = [r for r in neo4j_rows()]
    cp, _ = OV.BY_KEY["neo4j_checkpoint"].sentence(rows)
    pc, _ = OV.BY_KEY["neo4j_pagecache"].sentence(rows)
    assert cp in block and pc in block
    assert "Override `neo4j_checkpoint`" in block and "Override `neo4j_pagecache`" in block
    # the value the rows record sits beside it, per tier where it differs
    assert "`neo4j_pagecache`: `3.00GiB` (`sf1`); `11.00GiB` (`sf10`)" in block
    assert "`neo4j_checkpoint_interval`: `5s`" in block


def test_an_arm_without_an_override_gets_none():
    text = page()
    block = text.split("#### FalkorDB: `falkordb_graph`", 1)[1].split("#### ", 1)[0]
    assert "No override from the registry applies to this arm." in block
    assert "Override `" not in block


def test_version_image_durability_and_tiers_are_the_rows_values():
    text = page()
    block = text.split("#### FalkorDB: `falkordb_graph`", 1)[1].split("#### ", 1)[0]
    assert "| `sf1`, `sf10` | `falkordb:4.20.6 (redis 8.6.3)` | `falkordb/falkordb@sha256:0a9fe4d1ee0b` | `relaxed` |" in block
    assert "- Durability, `relaxed`: `appendonly=no: nothing is synced at commit`" in block
    assert "- Setting `mem_cap`: `8g` (`sf1`); `24g` (`sf10`)" in block
    assert "- Setting `topology`: `client_server`" in block


def test_a_failed_cell_is_listed_with_its_error_and_its_arm_is_on_the_page():
    text = page()
    block = text.split("#### ArangoDB: `arangodb_graph`", 1)[1].split("#### ", 1)[0]
    assert "No clean row yet" in block
    assert "- `sf10` / `oltp` / `relaxed` / rep 1: rc -1: `timeout_after_7200s`" in block
    assert "ArangoDB (arangodb_graph), lane l2" in text.split("## Gaps in the rows", 1)[1]


def test_a_lane_without_rows_says_so_and_an_unmeasured_registered_arm_is_named():
    text = page()
    for title in ("Tables", "Vectors", "Time series", "Cross-model", "Lifecycle"):
        sec = text.split(f"### {title}\n", 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
        assert "No rows yet for this lane." in sec, title
    gap = text.split("## Gaps in the rows", 1)[1]
    assert "- Lanes with no rows yet: Tables, Vectors, Time series, Cross-model, Lifecycle." in gap
    graphs = text.split("### Graphs\n", 1)[1].split("\n### ", 1)[0]
    assert "Registered for this lane, no row yet: ghost graph (`ghost_graph`, lane `l2`)." in graphs
    assert "lane l2: ghost_graph" in gap


def test_a_missing_stamp_is_a_gap_and_not_a_silent_sentence():
    clean, failed, registered = fixture()
    clean = [dict(r, neo4j_pagecache=None) if r["scale"] == "sf10" and r["backend"] == "neo4j_graph" else r for r in clean]
    text = G.render(clean, failed, registered, DATE)
    gap = text.split("## Gaps in the rows", 1)[1]
    assert "`neo4j_pagecache` for `neo4j_pagecache` is missing, tier sf10" in gap


def test_an_override_the_registry_cannot_render_is_a_gap(monkeypatch):
    broken = OV.BY_KEY["neo4j_pagecache"]._replace(sentence=lambda rows: 1 / 0)
    monkeypatch.setattr(OV, "OVERRIDES", tuple(broken if o.key == broken.key else o for o in OV.OVERRIDES))
    text = page()
    assert "`neo4j_pagecache` (ZeroDivisionError)" in text.split("## Gaps in the rows", 1)[1]
    block = text.split("#### Neo4j: `neo4j_graph`", 1)[1].split("#### ", 1)[0]
    assert "Override `neo4j_pagecache`" not in block and "Override `neo4j_checkpoint`" in block


def test_an_override_not_in_force_for_any_row_prints_no_sentence():
    """PRE_COMPACTION-style rule: `applies` is False for every row, so a sentence would be false."""
    clean = [row(lane="l4", scale="ts100", workload="ingest", backend="arcadedb_ts_native",
                 engine_version="26.9.1", engine_commit="417314c18", ts_compaction_interval_ms=None,
                 ts_mutable_at_ingest_end=5)]
    text = G.render(clean, [], {}, DATE)
    block = text.split("#### ArcadeDB: `arcadedb_ts_native`", 1)[1].split("#### ", 1)[0]
    assert "Override `arcadedb_ts_compaction_interval`" not in block
    assert "Override `arcadedb_ts_acceptance`" in block


def test_mixed_versions_inside_one_tier_are_a_gap():
    clean, failed, registered = fixture()
    clean = clean + [row(run_id="f3", engine_version="falkordb:6.0.1 (redis 8.10.2)", rep=2)]
    text = G.render(clean, failed, registered, DATE)
    assert "FalkorDB (falkordb_graph), lane l2: sf1" in text.split("Tiers whose rows mix versions:", 1)[1]


def test_internal_citations_are_taken_out_and_one_that_survives_refuses():
    clean, failed, registered = fixture()
    ok = [dict(r, query_language="Cypher (and SQL; DECISIONS #113)") if r["backend"] == "falkordb_graph" else r for r in clean]
    text = G.render(ok, failed, registered, DATE)
    assert "DECISIONS" not in text and "`Cypher (and SQL)`" in text
    bad = [dict(r, query_language="see DECISIONS") if r["backend"] == "falkordb_graph" else r for r in clean]
    with pytest.raises(SystemExit):
        G.render(bad, failed, registered, DATE)
    assert ".notes" not in text


def test_scaffold_sections_are_kept_and_there_is_no_prose_about_a_numbers_direction():
    text = page()
    assert "## What we run" in text
    assert "## How to tell us a setting is wrong" in text
    assert "(contribute.md)" in text
    assert not re.search(r"\b(faster|slower|improv|speeds? up|slows? down|favou?r)", text, re.I)


# ---------------------------------------------------------------------------
# determinism, and no number that no row carries

def test_output_is_deterministic_whatever_the_row_order():
    clean, failed, registered = fixture()
    a = G.render(clean, failed, registered, DATE)
    b = G.render(list(reversed(clean)), list(reversed(failed)), registered, DATE)
    assert a == b and a == page()


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _corpus(rows):
    parts = []
    for r in rows:
        parts.extend(str(v) for v in r.values())
    return "\n".join(parts).replace(",", "")


def _numbers_not_in_rows(text, rows):
    corpus = _corpus(rows)
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("Generated on "))
    return sorted({m.replace(",", "") for m in NUMBER.findall(body) if m.replace(",", "") not in corpus})


def test_every_number_on_the_page_is_in_a_row_or_the_generated_line():
    clean, failed, registered = fixture()
    text = G.render(clean, failed, registered, DATE)
    assert _numbers_not_in_rows(text, clean + failed) == []
    # the check can fail: a number the rows do not carry is found
    assert _numbers_not_in_rows(text + "\nIt takes 97 seconds.\n", clean + failed) == ["97"]


# ---------------------------------------------------------------------------
# the selection is the tables' selection

def test_selection_is_load_canonical_plus_failed_cells(tmp_path):
    rows = [
        row(run_id="old", ts_utc="2026-10-01T00:00:00+00:00", engine_version="falkordb:4.20.6"),
        row(run_id="new", ts_utc="2026-10-03T00:00:00+00:00", engine_version="falkordb:6.0.1"),         # supersedes `old`
        row(run_id="sept", instrument=None, backend="neo4j_graph"),                                      # the other campaign
        row(run_id="sweep", cpuset="0-5", backend="neo4j_graph"),                                        # a sharded sweep row
        row(run_id="rep9", rep=9, backend="neo4j_graph"),                                                # out of range
        row(run_id="bad-old", rc=1, error="boom", backend="neo4j_graph", scale="sf10",
            ts_utc="2026-10-01T00:00:00+00:00"),
        row(run_id="good", backend="neo4j_graph", scale="sf10", ts_utc="2026-10-02T00:00:00+00:00"),     # after the failure: not listed
        row(run_id="bad-new", rc=1, error="Trace\nValueError: nope", backend="duckpgq_graph",
            ts_utc="2026-10-04T00:00:00+00:00"),                                                         # a failed cell
        row(run_id="bad-scale", rc=1, error="x", backend="duckpgq_graph", scale="tiny"),                 # not a published tier
    ]
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    clean, failed, october = G.select_rows(p)
    assert sorted(r["run_id"] for r in clean) == ["good", "new"]
    assert [r["run_id"] for r in failed] == ["bad-new"]
    assert G.error_summary(failed[0]["error"]) == "ValueError: nope"
    assert all(r.get("instrument") == "2026-10" for r in october)
    # and the real module in this process is untouched by the private October copy
    import make_paper_tables as M
    assert M.OCTOBER is False or M.INSTRUMENT == "2026-10"


# ---------------------------------------------------------------------------
# names and lanes come from the exporter and lanes.ts

def test_names_and_lane_order_come_from_the_exporter():
    names = G.export_web_constants()
    assert names["display_name"]("arcadedb_graph_embedded") == "ArcadeDB (embedded)"
    assert names["display_name"]("ghost_graph") == "ghost graph"
    assert "postgres_tuned" in names["OFF_PAGE_ARMS"]
    order, page_of = G.lane_codes_in_page_order()
    seq = ["l1tpc", "l2", "l3d", "l3s", "l4", "e2", "lifecycle"]
    assert [c for c in order if c in seq] == seq
    assert [page_of[c] for c in seq] == ["tables", "graphs", "vectors", "vectors", "time-series", "cross-model", "lifecycle"]


def test_a_lane_code_in_the_rows_that_no_page_lane_shows_is_a_gap():
    clean = [row(lane="restart", scale="sf1", backend="neo4j_graph")]
    text = G.render(clean, [], {}, DATE)
    assert "Lane codes in the rows that no page lane shows:" in text and "`restart`" in text


@pytest.mark.skipif(not LANES_TS.exists(), reason="humem.ai checkout not on this machine")
def test_page_lanes_match_lanes_ts():
    src = LANES_TS.read_text(encoding="utf-8")
    body = src.split("export const dbbenchLanes", 1)[1].split("export function", 1)[0]
    lanes = re.split(r'\n  \{\n    slug: ', body)[1:]
    parsed = []
    for chunk in lanes:
        slug = re.match(r'"([^"]+)"', chunk).group(1)
        title = re.search(r'\n    title: "([^"]+)"', chunk).group(1)
        tables = re.findall(r'tableId: "([^"]+)"', chunk)
        parsed.append((slug, title, tuple(tables)))
    assert tuple(parsed) == G.PAGE_LANES
