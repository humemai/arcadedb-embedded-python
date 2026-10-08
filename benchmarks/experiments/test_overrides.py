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
    "arcadedb_http_body_limit": [{"server_http_body_max_bytes": "68719476736", "server_http_body_max_default": "104857600"}],
    "neo4j_checkpoint": [{"neo4j_checkpoint_interval": "5s", "neo4j_checkpoint_interval_default": "15m"}],
    "arcadedb_query_ram": [{"arcadedb_query_max_heap_ram_mb": "12288"}],
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
# the HTTP body limit (CAMPAIGN section 7 row 75): the arms that POST to /api/v1/batch, one value, never binding

LANE_FILES_THAT_POST_TO_BATCH = {"e2_hybrid.py", "l2_graph.py"}


def _batch_adapter_names():
    """The `name` of every adapter class, in the lane files, whose own source posts to the batch endpoint."""
    import ast
    names = set()
    for fname in sorted(LANE_FILES_THAT_POST_TO_BATCH):
        text = (HERE / fname).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ClassDef) and "/batch/" in (ast.get_source_segment(text, node) or ""):
                found = [st.value.value for st in node.body if isinstance(st, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "name" for t in st.targets)
                         and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str)]
                assert found, f"{fname}: class {node.name} posts to /batch/ and has no `name` the registry can map"
                names.update(found)
    return names


def test_only_the_two_known_lane_files_post_to_the_batch_endpoint():
    """A new loader that posts to /api/v1/batch is a new arm that needs the flag: the test names the files so the next one fails here."""
    posting = {f.name for f in HERE.glob("*.py")
               if not f.name.startswith("test_") and "/batch/" in f.read_text(encoding="utf-8")}
    assert posting == LANE_FILES_THAT_POST_TO_BATCH, posting


def test_the_body_limit_is_on_exactly_the_arms_that_reach_the_batch_endpoint():
    import runner
    names = _batch_adapter_names()
    assert names == {"arcadedb_graph_server", "arcadedb_e2_server"}, names
    reached = {(lane, be) for lane, spec in runner.LANES.items() for be in spec[1] if be in names}
    assert reached == set(OV.BODY_LIMIT_CARRIERS), reached
    assert set(OV.batch_arcadedb_from_runner()) == set(OV.BODY_LIMIT_CARRIERS)
    assert set(runner.BATCH_ENDPOINT_BACKENDS) == names
    # the restart lane reaches it through the graph model's adapter, and no other restart arm does
    assert ("restart", "arcadedb_graph_server") in reached and ("restart", "arcadedb_server") not in reached


def test_every_batch_arm_carries_the_flag_once_with_the_one_runner_constant():
    import runner
    flag = re.compile(rf"-D{re.escape(runner.HTTP_BODY_MAX_PROPERTY)}=(\d+)")
    for be in runner.BATCH_ENDPOINT_BACKENDS:
        env = " ".join(str(x) for x in runner.BACKENDS[be]["server_env"])
        assert flag.findall(env) == [str(runner.HTTP_BODY_MAX_BYTES)], be
        assert env.count("JAVA_OPTS=") == 1 and "-Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000" in env, be
    # no other arm carries it (an arm added by copying a dict must not inherit it by accident), and the registry names the same property
    others = {be for be, cfg in runner.BACKENDS.items() if be not in runner.BATCH_ENDPOINT_BACKENDS
              and flag.search(" ".join(str(x) for x in cfg.get("server_env", [])))}
    assert others == set(), others
    assert OV.BODY_PROPERTY == runner.HTTP_BODY_MAX_PROPERTY == "arcadedb.server.httpBodyContentMaxSize"
    assert OV.runner_body_limit() == runner.HTTP_BODY_MAX_BYTES == 64 << 30
    for be in runner.BATCH_ENDPOINT_BACKENDS:
        assert "arcadedb_http_body_limit" in OV.keys_for_backend(be)
    assert "arcadedb_http_body_limit" not in OV.keys_for_backend("arcadedb_server")
    assert "arcadedb_http_body_limit" not in OV.keys_for_backend("arcadedb_graph_embedded")


def test_the_body_limit_is_far_above_the_largest_request_the_lanes_plan_to_send():
    """The largest ONE-request body the lanes plan, derived from the lanes' line shapes and the corpus counts.

    Average line sizes in bytes, newline included, measured by streaming the lanes' own `lines()` (l2_graph.ArcadeGraphServer.build and
    build_messages over the LDBC SF1 corpus; e2_hybrid.ArcadeE2Server.build over the 500k-product catalog): Person vertex 142.0, KNOWS edge
    104.1, message-half vertex 91.2, message-half edge 94.3, Product vertex 1,477 (64 float32 values as JSON doubles), RELATED edge 75.2.

    * sf1full message half, the LARGEST: 3,163,871 vertices x 91.2 + 13,581,644 edges x 94.3 = 1,569,748,369 bytes, 1.46 GiB (measured
      exactly, to the byte, from the corpus; this estimate lands within 1%).
    * sf10 persons and KNOWS: 72,949 x 142.0 + 1,938,516 x 104.1 (the edge count is the campaign's own `expectedEdgeCount`) = about 212 MB,
      202 MiB: past the 100 MiB default, which is why the 26.10.1 sf10 cell died.
    * e2 at 500k products: 500,000 x 1,477 + 1,500,000 x 75.2 = about 851 MB, 812 MiB.
    """
    import e2_hybrid
    import ldbc_snb
    import runner
    full = ldbc_snb.FULL_NETWORK_COUNTS["sf1full"]
    sf1full_msg = full["msg_vertices"] * 91.2 + full["msg_edges"] * 94.3
    sf10 = ldbc_snb.SCALE_PERSONS["sf10"] * 142.0 + 1_938_516 * 104.1
    e2_big = (e2_hybrid.SCALE_PRODUCTS["e2_500k"] * 1477 + e2_hybrid.SCALE_PRODUCTS["e2_500k"] * e2_hybrid.EDGES_PER * 75.2)
    assert e2_hybrid.DIM == 64
    assert abs(sf1full_msg - 1_569_748_369) < 0.01 * 1_569_748_369, "the estimate drifted from the measured body"
    largest = max(sf1full_msg, sf10, e2_big)
    assert largest == sf1full_msg and 1.4 * 2**30 < largest < 1.6 * 2**30
    default = 100 << 20
    assert sf10 > default and sf1full_msg > default and e2_big > default           # the default refuses all three
    assert runner.HTTP_BODY_MAX_BYTES > 16 * largest                               # and the pinned value never binds
    assert runner.HTTP_BODY_MAX_BYTES == 64 << 30


def test_the_body_limit_sentence_quotes_the_values_the_rows_stamped_and_degrades_without_them():
    o = OV.BY_KEY["arcadedb_http_body_limit"]
    text, values = o.sentence(SAMPLE_ROWS["arcadedb_http_body_limit"])
    assert "raised to 64 GiB, where the engine's default is 100 MiB" in text and values == ["64", "100"]
    # the reason, plainly: the default refuses the one streamed request, the engine says to raise the limit or split the payload
    assert "refuses the single streamed request" in text and "raise the limit or split the payload" in text
    assert "stays one request" in text and "no speed setting" in text and "embedded arms have no HTTP body" in text
    # a read-back that failed stamps no default: the sentence keeps the value and drops the comparison
    text, values = o.sentence([{"server_http_body_max_bytes": "68719476736"}])
    assert "raised to 64 GiB, above the engine's default" in text and values == ["64"]
    text, values = o.sentence([])
    assert not re.search(r"\d", text) and values == [] and "above the engine's default" in text
    assert "\u2014" not in text and "--" not in text


def test_a_row_of_a_batch_arm_must_stamp_the_limit_and_say_whether_it_was_read_or_requested():
    row = lambda **kw: _row(lane="l2", backend="arcadedb_graph_server", server_query_max_heap_elements=5000000, **kw)   # noqa: E731
    found, judged = OV.stamp_findings([row()])
    assert judged == 2 and [(f["key"], f["kind"]) for f in found] == [("arcadedb_http_body_limit", "NOT STAMPED")]
    # a value without its source cannot say whether the engine was asked
    no_src = OV.stamp_findings([row(server_http_body_max_bytes=64 << 30)])[0]
    assert [f["kind"] for f in no_src] == ["WRONG"] and "server_http_body_max_source" in no_src[0]["text"]
    ok = row(server_http_body_max_bytes=str(64 << 30), server_http_body_max_source="read from the engine over HTTP (server?mode=default)")
    assert OV.stamp_findings([ok]) == ([], 2)                                       # a frozen csv row carries a string
    # a server that still runs the 26.10.1 default is the defect this override exists to prevent
    bad = dict(ok, server_http_body_max_bytes=104857600)
    found, _ = OV.stamp_findings([bad])
    assert found[0]["kind"] == "WRONG" and "104,857,600 bytes where the runner launches it with 68,719,476,736" in found[0]["text"]
    # the three carrier lanes, and no lane that does not post to the batch endpoint
    for lane, be in OV.BODY_LIMIT_CARRIERS:
        assert [f["kind"] for f in OV.stamp_findings([_row(lane=lane, backend=be)])[0] if f["key"] == "arcadedb_http_body_limit"] == ["NOT STAMPED"], (lane, be)
    assert not [f for f in OV.stamp_findings([_row(lane="l3d", backend="arcadedb_dense_server", server_query_max_heap_elements=5000000,
                                                   arcadedb_add_hierarchy=True, arcadedb_add_hierarchy_source="requested")])[0]
                if f["key"] == "arcadedb_http_body_limit"]


def test_rows_on_the_pin_that_had_no_body_limit_are_not_judged_for_it():
    """The October pin (a September commit) has no `arcadedb.server.httpBodyContentMaxSize`: the override is not in force for its rows."""
    old = _row(lane="l2", backend="arcadedb_graph_server", server_query_max_heap_elements=5000000, engine_commit="417314c18abc")
    assert OV.stamp_findings([old]) == ([], 1)                                      # only the cap is judged
    new = dict(old, engine_commit="d36b4ca3a1")
    assert [f["key"] for f in OV.stamp_findings([new])[0]] == ["arcadedb_http_body_limit"]
    # and no sentence about it may stand under a table built only from such rows
    assert not [n for n in OV.notes_for_table("l2", "l2", ["arcadedb_graph_server"], [dict(old, lane="l2")]) if "request body" in n[0]]
    assert [n for n in OV.notes_for_table("l2", "l2", ["arcadedb_graph_server"], [dict(new, lane="l2")]) if "request body" in n[0]]


def test_the_runner_stamps_what_the_engine_lists_and_labels_a_request(monkeypatch):
    """observe_server's body-limit read-back, against a stub server that lists the setting, one that does not (a pre-26.10.1 build),
    and one that cannot be reached."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import runner

    served = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/v1/server?mode=default" and self.headers["Authorization"].startswith("Basic ")
            body = json.dumps({"settings": served["settings"]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(runner, "sh", lambda cmd, *a, **k: "127.0.0.1 ")
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    # the helper talks to port 2480; point it at the stub
    real = runner.urllib.request.Request
    monkeypatch.setattr(runner.urllib.request, "Request", lambda url, *a, **k: real(url.replace(":2480", f":{srv.server_address[1]}"), *a, **k))
    envs = "-Darcadedb.server.rootPassword=x"
    try:
        served["settings"] = [{"key": runner.HTTP_BODY_MAX_PROPERTY, "value": runner.HTTP_BODY_MAX_BYTES, "default": 104857600}]
        got = runner.arcadedb_body_limit_readback("cid", envs, runner.HTTP_BODY_MAX_BYTES)
        assert got == {"server_http_body_max_bytes": runner.HTTP_BODY_MAX_BYTES, "server_http_body_max_default": 104857600,
                       "server_http_body_max_source": "read from the engine over HTTP (server?mode=default)"}
        served["settings"] = [{"key": "arcadedb.other", "value": 1}]
        got = runner.arcadedb_body_limit_readback("cid", envs, runner.HTTP_BODY_MAX_BYTES)
        assert got["server_http_body_max_bytes"] == runner.HTTP_BODY_MAX_BYTES and "predates it" in got["server_http_body_max_source"]
        assert got["server_http_body_max_source"].startswith("requested") and "server_http_body_max_default" not in got
    finally:
        srv.shutdown()
        srv.server_close()
    got = runner.arcadedb_body_limit_readback("cid", envs, 7)
    assert got == {"server_http_body_max_bytes": 7,
                   "server_http_body_max_source": "requested in the container's JAVA_OPTS (the engine could not be asked from the host)"}
    # observe_server wires it in for a container whose environment carries the flag, and for no other
    monkeypatch.setattr(runner, "arcadedb_body_limit_readback", lambda cid, envs, n: {"server_http_body_max_bytes": n})
    env_json = json.dumps([f"JAVA_OPTS=-Darcadedb.server.rootPassword=x {runner.HTTP_BODY_MAX_OPT}"])
    monkeypatch.setattr(runner, "sh", lambda cmd, *a, **k: env_json if "{{json .Config.Env}}" in cmd else "")
    assert runner.observe_server("cid").get("server_http_body_max_bytes") == runner.HTTP_BODY_MAX_BYTES
    monkeypatch.setattr(runner, "sh", lambda cmd, *a, **k: json.dumps(["JAVA_OPTS=-Xmx1g"]) if "{{json .Config.Env}}" in cmd else "")
    assert "server_http_body_max_bytes" not in runner.observe_server("cid")


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
    assert OV.sentence_findings([_table("l3s", "qdrant_sparse", [])], LANE_OF, []) == []     # the sparse switches are judged from the rows (none stamped here)


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
    one_hour = OV.TS_COMPACTION_MS
    good = dict(ts_compaction_interval_ms=one_hour)
    assert OV.stamp_findings([_row(lane="l4", backend="arcadedb_ts_native", ts_mutable_at_ingest_end=0, **good)]) == ([], 2)
    # -1 is the lane's "could not read it"
    assert OV.stamp_findings([_row(lane="l4", backend="arcadedb_ts_native", ts_mutable_at_ingest_end=-1,
                                   **good)])[0][0]["kind"] == "WRONG"


@pytest.mark.parametrize("backend", ["arcadedb_ts_native", "arcadedb_ts_native_server"])
def test_the_ts_native_arms_must_say_what_compaction_interval_the_engine_reports(backend):
    """CAMPAIGN row 54: COMPACTION_INTERVAL 1 HOURS is read back from the engine, never the string we sent."""
    served = backend.endswith("_server")
    base = dict(ts_mutable_at_ingest_end=0, **({"server_query_max_heap_elements": 5000000} if served else {}))
    row = lambda **kw: _row(lane="l4", backend=backend, **base, **kw)
    judged_all = 3 if served else 2
    findings, _judged = OV.stamp_findings([row()])
    assert [f["key"] for f in findings] == ["arcadedb_ts_compaction_interval"] and findings[0]["kind"] == "NOT STAMPED"
    assert OV.stamp_findings([row(ts_compaction_interval_ms=OV.TS_COMPACTION_MS)]) == ([], judged_all)
    # an arm created without an interval reads back 0: the sentence would be false on this row
    wrong = OV.stamp_findings([row(ts_compaction_interval_ms=0)])[0]
    assert wrong[0]["kind"] == "WRONG" and "one-hour" in wrong[0]["text"]
    # a failed read-back is named on the finding
    named = OV.stamp_findings([row(ts_compaction_interval_readback_error="HTTP 500")])[0]
    assert named[0]["kind"] == "NOT STAMPED" and "HTTP 500" in named[0]["text"]


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
    assert any("httpBodyContentMaxSize=68719476736" in e for e in cfg["arcadedb_graph_server"]["server_env"])
    assert cfg["arcadedb_graph_server"]["overrides"] == ["arcadedb_http_body_limit", "arcadedb_query_cap"]
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
    assert c["durability_class"] == "strict" and c["durability_server_flags"] == "txWalFlush=1"
    assert any("-Darcadedb.txWalFlush=1" in e for e in c["server_env"])


# ---------------------------------------------------------------------------
# the query heap budget override (DECISIONS #175): OFF unless the environment asks

def test_the_query_budget_override_is_off_by_default_and_changes_nothing(monkeypatch):
    import bench_common
    monkeypatch.delenv(bench_common.QUERY_RAM_ENV, raising=False)
    assert bench_common.arcade_query_ram_mb() is None and bench_common.arcade_query_ram_opt() == ""
    assert bench_common.arcade_query_ram_readback() == {}
    assert "queryMaxHeapRAM" not in bench_common.arcade_jvm_args("-Xms4g")
    import runner
    for be in runner.QUERY_RAM_BACKENDS:
        assert "queryMaxHeapRAM" not in " ".join(str(x) for x in runner.BACKENDS[be]["server_env"]), be
    assert bench_common.QUERY_RAM_ENV in open(HERE_RUNNER).read()      # forwarded into the container, or the embedded arm never sees it


HERE_RUNNER = str(Path(__file__).resolve().parent / "runner.py")


def test_the_query_budget_option_reaches_the_embedded_jvm_and_exactly_one_served_java_opts_entry(monkeypatch):
    import bench_common
    import runner
    monkeypatch.setenv(bench_common.QUERY_RAM_ENV, "12288")
    assert bench_common.arcade_query_ram_mb() == 12288
    args = bench_common.arcade_jvm_args("-Xms16g")
    assert args.count("-Darcadedb.queryMaxHeapRAM=12288") == 1 and args.startswith("-Xms16g -Darcadedb.txWalFlush=")
    cfg = runner._with_query_ram(runner.BACKENDS["arcadedb_server"], 12288)
    envs = [e for e in cfg["server_env"] if isinstance(e, str) and e.startswith("JAVA_OPTS=")]
    assert len(envs) == 1 and envs[0].count("-Darcadedb.queryMaxHeapRAM=12288") == 1
    assert "queryMaxHeapRAM" not in " ".join(str(x) for x in runner.BACKENDS["arcadedb_server"]["server_env"])     # the original is untouched
    assert runner.arcadedb_query_ram_readback is not None


@pytest.mark.parametrize("bad", ["0", "-1", "twelve", "1.5"])
def test_a_budget_that_would_disable_the_engines_guard_ends_the_run(monkeypatch, bad):
    import bench_common
    monkeypatch.setenv(bench_common.QUERY_RAM_ENV, bad)
    with pytest.raises(SystemExit):
        bench_common.arcade_query_ram_mb()


def test_the_query_budget_stamp_is_judged_only_where_it_exists_and_needs_a_source():
    ram = lambda rows: [f for f in OV.stamp_findings(rows)[0] if f["key"] == "arcadedb_query_ram"]   # noqa: E731 - the served arm also carries the query-cap stamp
    for be in ("arcadedb_embedded", "arcadedb_server"):
        plain = _row(lane="l1tpc", backend=be)
        assert ram([plain]) == [], be                                      # the engine default ran: nothing to judge for this override
        ok = dict(plain, arcadedb_query_max_heap_ram_mb=12288, arcadedb_query_max_heap_ram_source="read from the engine over HTTP (server?mode=default)")
        assert ram([ok]) == [], be
        no_src = dict(ok)
        no_src.pop("arcadedb_query_max_heap_ram_source")
        assert [f["kind"] for f in ram([no_src])] == ["WRONG"]
        assert [f["kind"] for f in ram([dict(ok, arcadedb_query_max_heap_ram_mb=0)])] == ["WRONG"]


def test_the_query_budget_sentence_appears_only_under_a_table_with_a_stamped_row():
    stamped = _row(lane="l1tpc", backend="arcadedb_server", arcadedb_query_max_heap_ram_mb=12288,
                   arcadedb_query_max_heap_ram_source="requested via the container's JAVA_OPTS (the engine could not be asked from the host)")
    plain = _row(lane="l1tpc", backend="arcadedb_server")
    keys = ["arcadedb_server"]
    assert [o.key for o in OV.applicable("l1tpc", keys, [plain]) if o.key == "arcadedb_query_ram"] == []
    assert [o.key for o in OV.applicable("l1tpc", keys, [plain, stamped]) if o.key == "arcadedb_query_ram"] == ["arcadedb_query_ram"]
    notes = OV.notes_for_table("t", "l1tpc", keys, [plain, stamped])
    text = [t for t, _v in notes if "query heap budget" in t]
    assert len(text) == 1 and "12,288 MB" in text[0] and "no speed setting" in text[0]
    assert not [t for t, _v in OV.notes_for_table("t", "l1tpc", keys, [plain]) if "query heap budget" in t]
    assert "—" not in text[0] and "--" not in text[0]
