"""land_stage.py names the build it lands: `--pin` defaults to the one engine commit the current payload was built from.

Run with `python -m pytest test_land_stage_pin.py -q` from this directory.

A landing pulls `runs_page_<pin>.jsonl` by exact name, so a guessed pin fetches another build's rows. The default comes from the
payload; a payload with no commit, or with several, has no pin to offer and the landing refuses.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import land_stage as L  # noqa: E402


def _payload(tmp_path, commits):
    p = tmp_path / "web_benchmarks.json"
    p.write_text(json.dumps({"arcadedb_commits": commits}))
    return p


def test_the_pin_is_the_one_commit_the_payload_carries(tmp_path):
    assert L.current_pin(_payload(tmp_path, ["261100fix"])) == "261100fix"


@pytest.mark.parametrize("commits", [[], ["a1b2c3d4e", "261100fix"], None])
def test_no_pin_when_the_payload_names_none_or_several(tmp_path, commits):
    assert L.current_pin(_payload(tmp_path, commits)) is None


def test_no_pin_when_there_is_no_payload(tmp_path):
    assert L.current_pin(tmp_path / "absent.json") is None


def test_a_landing_with_no_pin_refuses(monkeypatch, tmp_path):
    monkeypatch.delenv("BENCH_ENGINE_COMMIT", raising=False)
    monkeypatch.setattr(L, "PAYLOAD", tmp_path / "absent.json")
    monkeypatch.setattr(L, "PY", str(tmp_path / "no-venv-python"))
    monkeypatch.setattr(sys, "argv", ["land_stage.py", "--message", "x"])
    with pytest.raises(SystemExit) as exc:
        L.main()
    assert "no --pin" in str(exc.value)


def test_a_landing_refuses_another_instrument(monkeypatch, tmp_path):
    monkeypatch.setenv("BENCH_INSTRUMENT", "2026-10")
    monkeypatch.setattr(L, "PY", str(tmp_path / "no-venv-python"))
    monkeypatch.setattr(sys, "argv", ["land_stage.py", "--pin", "261100fix", "--message", "x"])
    with pytest.raises(SystemExit) as exc:
        L.main()
    assert "2026-11 rows only" in str(exc.value)


def test_there_is_no_preview_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "PY", str(tmp_path / "no-venv-python"))
    monkeypatch.setattr(sys, "argv", ["land_stage.py", "--preview", "--pin", "x", "--message", "x"])
    with pytest.raises(SystemExit) as exc:
        L.main()
    assert exc.value.code == 2
