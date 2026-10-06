"""The October ingest sentences, their pins, and the l4 ANALYZE symmetry (re-pin rehearsal, 2026-10-06).

Run with `python -m pytest test_ingest_prose.py -q -rs` from this directory.

`structure_check` found five October ingest sentences that did not name an arm the re-pin adds (e2, l2,
l2olap, l3d, l4). The wording was approved and committed into `export_web.OCT_PROSE`; these tests hold
what makes it safe to say:

  * `structure_check`'s ingest check is clean ON DISK, not only with the sentences patched in memory;
  * every digit a sentence carries has a registered pin that evaluates to the printed number (a wrong
    constant is a DIFFER finding), including the one expression pin, `BATCH * 10`;
  * no number in the four sentences is left loose, which is what page_check's UNPINNED finding would say;
  * the house style (no dashes, no filing numbers) holds;
  * the l4 sentence says both PostgreSQL-family arms run ANALYZE inside the ingest timer (the adapters'
    own check is test_l4_analyze.py).
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


@pytest.fixture(scope="module")
def EW():
    """export_web, imported once (it refuses to import without a pin in the environment)."""
    import os
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    return export_web


@pytest.fixture(scope="module")
def PC(EW):
    import page_check
    return page_check


TABLES = ("e2", "l2", "l2olap", "l3d", "l4")


def _entry(EW, tid):
    v = EW.OCT_PROSE[tid]["ingest"]
    return (v[0], list(v[1])) if isinstance(v, tuple) else (v, [])


# ------------------------------------------------------------------ structure_check, on disk

def test_structure_check_finds_no_unnamed_arm_on_disk(EW):
    import structure_check as SC
    found = SC.check_ingest_sentences()
    assert not found, found


@pytest.mark.parametrize("tid,arms", [
    ("e2", ("DuckDB", "DuckPGQ", "LadybugDB", "Memgraph")),
    ("l2", ("PostgreSQL",)), ("l2olap", ("PostgreSQL",)),
    ("l3d", ("Elasticsearch", "FalkorDB", "LadybugDB", "Memgraph")),
    ("l4", ("PostgreSQL",)),
])
def test_each_sentence_names_the_arms_it_was_missing(EW, tid, arms):
    text, _ = _entry(EW, tid)
    for arm in arms:
        assert re.search(rf"\b{arm}\b", text), arm


def test_the_graph_analytics_table_says_what_the_graph_table_says(EW):
    assert EW.OCT_PROSE["l2olap"]["ingest"] == EW.OCT_PROSE["l2"]["ingest"]


# ------------------------------------------------------------------------------------- pins

def _pin_results(EW, PC, tid):
    text, pins = _entry(EW, tid)
    return text, [(pat, PC._pin_check(f"{tid}:{pat}", pat, fn, kind, text, P=None, rows=[]))
                  for pat, fn, kind in [(p[0], p[1], p[2] if len(p) > 2 else "cell") for p in pins]]


@pytest.mark.parametrize("tid", ["e2", "l2", "l3d"])
def test_every_pin_matches_its_sentence_and_the_code_constant(EW, PC, tid):
    text, results = _pin_results(EW, PC, tid)
    assert results
    for pat, (spans, finding) in results:
        assert spans, f"{tid}: the pin /{pat}/ matches nothing in its own sentence"
        assert finding is None, finding


def test_the_new_digits_are_pinned_to_the_constants_they_come_from(EW, PC):
    _, e2 = _pin_results(EW, PC, "e2")
    assert any("UNWIND batches of" in pat for pat, _ in e2)
    _, results = _pin_results(EW, PC, "l3d")
    pats = [pat for pat, _ in results]
    for must in ("bulk-indexes the vectors in batches of", "Memgraph loads UNWIND batches of",
                 "FalkorDB loads UNWIND batches of", "Arrow tables of up to"):
        assert any(must in pat for pat in pats), must
    assert EW._const("e2_hybrid", "BATCH") == 5000
    assert EW._const("l3d_dense", "CHROMA_BATCH") == 5000
    assert EW._const("l3d_dense", "BATCH") * 10 == 100000


def test_the_expression_pin_is_accepted_and_a_wrong_number_is_a_difference(EW, PC):
    """`_const("l3d_dense", "BATCH") * 10` is a lambda that returns a number, which is all _pin_check calls: no
    new mechanism is needed. It accepts the real value and reports DIFFER for a wrong one."""
    text, pins = _entry(EW, "l3d")
    pat = next(p[0] for p in pins if "Arrow tables of up to" in p[0])
    fn = next(p[1] for p in pins if "Arrow tables of up to" in p[0])
    assert fn(None, []) == 100000
    spans, finding = PC._pin_check("l3d:arrow", pat, fn, "const", text, P=None, rows=[])
    assert spans and finding is None
    spans, finding = PC._pin_check("l3d:arrow", pat, lambda P, rows: 99999, "const", text, P=None, rows=[])
    assert finding and finding.startswith("DIFFER")
    # and a constant that moves in the adapter moves the check
    spans, finding = PC._pin_check("l3d:arrow", pat, lambda P, rows: EW._const("l3d_dense", "BATCH") * 5,
                                   "const", text, P=None, rows=[])
    assert finding and finding.startswith("DIFFER")


@pytest.mark.parametrize("tid", ["e2", "l2", "l3d", "l4"])
def test_no_number_in_the_sentence_is_left_loose(EW, PC, tid):
    """page_check's UNPINNED rule: every number token must be covered by a pin span or an allowed pattern."""
    text, results = _pin_results(EW, PC, tid)
    spans = [s for _pat, (sp, _f) in results for s in sp]
    allowed = [p for p, _ in PC.CONDITION_ALLOWED] + [p for p, _ in PC.CONDITION_EXEMPT]
    spans += PC._spans(allowed, text)
    loose = [text[a:b] for a, b in (m.span() for m in PC.CONDITION_TOKEN.finditer(text))
             if not PC._covered((a, b), spans)]
    assert loose == [], loose


# ------------------------------------------------------------------------------ house style

@pytest.mark.parametrize("tid", TABLES)
def test_house_style(EW, tid):
    text, _ = _entry(EW, tid)
    assert "—" not in text and "–" not in text and " -- " not in text
    assert not re.search(r"#\d|DECISIONS|BUGS|\bF\d{2,3}\b|CAMPAIGN", text)


# ---------------------------------------------------------------------------------- the l4 sentence

def test_the_l4_sentence_says_both_arms_do_it(EW):
    text, _ = _entry(EW, "l4")
    assert ("TimescaleDB COPY into a hypertable and PostgreSQL COPY into an ordinary table, each as one stream "
            "followed by a (host, ts) index and an ANALYZE, all inside the ingest timer") in text
