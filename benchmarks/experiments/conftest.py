"""The cap rule's report-time data (cap_rule_2610.json, DECISIONS #188) describes one real pass; a test of anything else must
not meet it. test_cap_rule.py reads it on purpose."""
import pytest


@pytest.fixture(autouse=True)
def _no_cap_rule_data(request, monkeypatch):
    if request.module.__name__ == "test_cap_rule":
        return
    import cap_rule
    monkeypatch.setitem(cap_rule._CACHE, cap_rule.RULE_JSON, None)
