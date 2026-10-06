"""fairness_check's section headers carry the numbers FAIRNESS.md gives the invariants (CAMPAIGN section 7 row 31).

Run with `python -m pytest test_fairness_headers.py -q -rs` from this directory.

`check_close_cost` printed its section as F11, which FAIRNESS.md numbers F13 (F11 there is "equivalent queries must return equivalent
answers"). A reader following a finding from the gate's output to FAIRNESS.md landed on the wrong invariant.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _fairness_titles():
    out = {}
    for m in re.finditer(r"^\*\*(F\d+[a-z]?)\. ([^.*]+)", (HERE / "FAIRNESS.md").read_text(), re.M):
        out[m.group(1)] = m.group(2).strip().lower()
    return out


def test_the_close_cost_section_is_numbered_as_fairness_md_numbers_it():
    titles = _fairness_titles()
    assert titles["F13"].startswith("close cost") and titles["F11"].startswith("equivalent queries")
    src = (HERE / "fairness_check.py").read_text()
    printed = re.findall(r'print\("\\n== (F\d+[a-z]?) session cost', src)
    assert printed and set(printed) == {"F13"}
    assert "== F11 session cost" not in src
