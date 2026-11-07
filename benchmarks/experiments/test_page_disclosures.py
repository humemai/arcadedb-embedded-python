"""The two disclosures a served ArcadeDB row needs on the page (DECISIONS #256, #258, #259), generated from the rows and the registry.

(1) The native server image of a release reports the commit one version-strings-only commit after the pin: a sentence is written when a row
printed in a table carries `server_engine_commit_equiv`, from engine_commit_equiv.json for the release and the commits, and not otherwise.
(2) The client sentence under a table follows the row labels: the official driver the headline rows name, the lean twin and the PostgreSQL
wire only when their rows are there, and the statements that stay on the lean client in the headline rows too.

In-process: nothing is started and nothing is read from results/ except the one fixture build at the end.
Run with `python -m pytest test_page_disclosures.py -q` from this directory (needs numpy and pandas, as the exporter does).
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine_pin  # noqa: E402
import export_web as E  # noqa: E402
import page_check as PC  # noqa: E402

REG = engine_pin._equiv_registry()["26.11.1"]
PIN, EQ = REG["pin"], REG["equivalent"][0]
DRIVER = "arcadedb-driver 0.4.0 (sync, httpx)"
LEAN = "lean_http (http.client, keep-alive)"
TABLES = [{"id": "l1", "entries": [{"backend_key": "arcadedb_server", "backend": "ArcadeDB (served)"}]}]


def _row(**kw):
    return {"lane": "l1", "backend": "arcadedb_server", "engine_commit": PIN, **kw}


def _unsourced_numbers(sentences):
    """What page_check's condition gate reports for a list of GLOBAL sentences (the count of numbers it cannot place), against what _gen recorded."""
    payload = {"conditions": list(sentences), "tables": [], "condition_provenance": {"generated": list(E._GENERATED)}}
    return PC._check_conditions(payload, [])


# ------------------------------------------------------------------------------------------------ (1) the engine commit equivalence
def test_the_sentence_is_written_when_a_row_carries_the_equivalence_field():
    out = E._native_server_equiv_note(TABLES, [_row(server_engine_commit_equiv=EQ)])
    assert len(out) == 1
    text = out[0]
    assert "26.11.1" in text and EQ[:10] in text and PIN[:10] in text
    assert "native server image" in text and "version string" in text and "none of them source" in text
    assert f"{REG['files_changed']:,} files" in text and f"{REG['version_string_lines']:,} changed lines" in text
    assert "—" not in text and "–" not in text
    assert not E._REF_SCAN.search(text), "an internal citation would be stripped from the page"


def test_the_sentence_is_not_written_when_no_row_carries_the_field():
    assert E._native_server_equiv_note(TABLES, [_row()]) == []
    assert E._native_server_equiv_note(TABLES, [_row(server_engine_commit_equiv="")]) == []
    assert E._native_server_equiv_note(TABLES, [_row(server_engine_commit_equiv=None)]) == []
    assert E._native_server_equiv_note(TABLES, []) == []


def test_the_sentence_needs_a_row_that_is_printed_in_a_table():
    assert E._native_server_equiv_note(TABLES, [_row(backend="arcadedb_graph_server", server_engine_commit_equiv=EQ)]) == []
    assert E._native_server_equiv_note([], [_row(server_engine_commit_equiv=EQ)]) == []


def test_many_rows_of_one_pair_give_one_sentence():
    rows = [_row(server_engine_commit_equiv=EQ), _row(server_engine_commit_equiv=EQ, rep=2), _row(server_engine_commit_equiv=EQ[:9])]
    assert len(set(E._native_server_equiv_note(TABLES, rows))) == 1


@pytest.mark.parametrize("pin,reported", [(PIN, "deadbeef0" + "0" * 31), ("deadbeef0" + "0" * 31, EQ)])
def test_a_row_claiming_an_equivalence_the_registry_does_not_hold_is_refused(pin, reported):
    with pytest.raises(SystemExit) as why:
        E._native_server_equiv_note(TABLES, [_row(engine_commit=pin, server_engine_commit_equiv=reported)])
    assert "REFUSING" in str(why.value)


def test_no_number_in_the_sentence_is_unsourced(capsys):
    sentences = E._native_server_equiv_note(TABLES, [_row(server_engine_commit_equiv=EQ)])
    assert _unsourced_numbers(sentences) == 0, capsys.readouterr().out
    # the gate does see a typed number: a generated sentence with one more figure that _gen was not told about is reported
    capsys.readouterr()
    told = next(g["values"] for g in E._GENERATED if g["text"] == sentences[0])
    typed = E._gen(sentences[0] + " It took 7 minutes.", *told)
    assert _unsourced_numbers([typed]) >= 1
    assert "UNPINNED" in capsys.readouterr().out


def test_the_global_conditions_carry_it_only_with_the_field(monkeypatch):
    monkeypatch.setattr(E, "_FROZEN_ROWS", [_row()])
    assert not [c for c in E._global_conditions(TABLES) if "native server image reports" in c]
    monkeypatch.setattr(E, "_FROZEN_ROWS", [_row(server_engine_commit_equiv=EQ)])
    assert len([c for c in E._global_conditions(TABLES) if "native server image reports" in c]) == 1


# ------------------------------------------------------------------------------------------------ (2) which client each served row used
def _client_note(monkeypatch, *, twin=None, pgwire=False, client=DRIVER):
    entry = {"backend_key": "arcadedb_server", **({"client_twin": {"client": twin, "metrics": {}}} if twin else {})}
    monkeypatch.setattr(E, "_FROZEN_ROWS", [{"backend": "arcadedb_server", "arcadedb_http_client": client,
                                             "arcadedb_http_client_role": "headline"}])
    monkeypatch.setattr(E, "_PG_TWIN_ROWS", [{"backend": "arcadedb_server"}] if pgwire else [])
    return E._arcadedb_client_note({"entries": [entry]})


def test_the_client_sentence_names_the_driver_the_rows_carry_as_the_headline(monkeypatch):
    note = _client_note(monkeypatch)
    assert DRIVER in note and "official Python client" in note and "headline" in note
    assert "labelled sensitivity" not in note and "PostgreSQL wire" not in note      # no twin rows, no twin sentence
    other = _client_note(monkeypatch, client="arcadedb-driver 9.9.9 (sync, httpx)")
    assert "arcadedb-driver 9.9.9 (sync, httpx)" in other and DRIVER not in other     # the version is the rows', not a constant


def test_the_client_sentence_says_what_stays_on_the_lean_client_in_the_headline_rows(monkeypatch):
    note = _client_note(monkeypatch)
    assert E._SERVED_LEAN_SCOPE in note
    for word in ("Bulk loads", "transactions", "streamed results", "server probe"):
        assert word in E._SERVED_LEAN_SCOPE


def test_the_lean_twin_and_the_wire_twin_follow_their_rows(monkeypatch):
    lean = _client_note(monkeypatch, twin=LEAN)
    assert "labelled sensitivity" in lean and LEAN in lean and "PostgreSQL wire" not in lean
    wire = _client_note(monkeypatch, pgwire=True)
    assert "PostgreSQL wire" in wire and "sensitivity" in wire and "labelled sensitivity" not in wire.split("PostgreSQL wire")[0]
    both = _client_note(monkeypatch, twin=LEAN, pgwire=True)
    assert "labelled sensitivity" in both and "PostgreSQL wire" in both
    assert "—" not in both and "–" not in both


def test_the_client_sentence_is_for_tables_with_a_served_row_only(monkeypatch):
    _client_note(monkeypatch)
    assert E._arcadedb_client_note({"entries": [{"backend_key": "qdrant_dense"}]}) is None


def test_no_number_in_the_client_sentence_is_unsourced(monkeypatch, capsys):
    note = _client_note(monkeypatch, twin=LEAN, pgwire=True)
    assert _unsourced_numbers([note]) == 0, capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ the fixture build
def test_the_fixture_build_has_no_equivalence_sentence_and_still_names_the_client(tmp_path):
    """The fixture rows carry no `server_engine_commit_equiv`, so the page they build says nothing about it (the fixture itself is unchanged)."""
    import test_publish_2611_e2e as E2E
    results = E2E._stage(tmp_path / "results")
    assert E2E._run("make_paper_tables.py", results).returncode == 0
    done = E2E._run("export_web.py", results)
    assert done.returncode == 0, done.stderr[-2000:]
    payload = json.loads((results / "web_benchmarks.json").read_text())
    every = list(payload["conditions"]) + [c for t in payload["tables"] for c in t.get("conditions") or []]
    assert not [c for c in every if "native server image reports" in c]
    served = " ".join(next(t for t in payload["tables"] if t["id"] == "docs_oltp")["conditions"])
    assert DRIVER in served and E._SERVED_LEAN_SCOPE in served
