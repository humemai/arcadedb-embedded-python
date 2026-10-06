"""F10 asks a write cell for both durability classes, except an arm that runner.ARM_RUNS declares runs one (CAMPAIGN row 69).

Run with `python -m pytest test_f10_restricted_arm.py -q -rs` from this directory.

Found by feeding the gate this round's laptop rows: the image-defaults arm runs the documents OLTP cell in the relaxed class
only (`ARM_RUNS`, the generator stages it that way, and the user confirmed it), and F10 failed it for the strict cell it was
never asked to run, which would have failed the landing of the chain's last stage.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import fairness_check as F  # noqa: E402


def _row(backend, klass, scale="tpch10"):
    d = bench_common.DURABILITY_ARCADEDB if klass == "relaxed" else bench_common.DURABILITY_ARCADEDB_STRICT
    return {"instrument": "2026-10", "lane": "l1tpc", "scale": scale, "workload": "oltp", "backend": backend,
            "durability": d, "durability_class": klass}


def _failures(rows, capsys):
    bad = F.check_durability(rows)
    return bad, capsys.readouterr().out


def test_the_restricted_arm_needs_only_the_class_it_declares(capsys):
    bad, out = _failures([_row("arcadedb_imgdefaults_server", "relaxed")], capsys)
    assert bad == 0 and "only the" not in out


def test_a_main_arm_with_only_a_relaxed_cell_still_fails(capsys):
    bad, out = _failures([_row("arcadedb_server", "relaxed")], capsys)
    assert bad == 1 and "missing ['strict']" in out


def test_a_main_arm_with_both_classes_passes(capsys):
    bad, _ = _failures([_row("arcadedb_server", "relaxed"), _row("arcadedb_server", "strict")], capsys)
    assert bad == 0


def test_the_declared_class_is_read_from_the_runner_not_named_here():
    import runner
    assert runner.ARM_RUNS["arcadedb_imgdefaults_server"]["l1tpc"]["durability"] == "relaxed"
    assert F._durability_classes_required("l1tpc", "arcadedb_imgdefaults_server") == {"relaxed"}
    assert F._durability_classes_required("l1tpc", "arcadedb_server") == {"relaxed", "strict"}
    assert F._durability_classes_required("l2", "arcadedb_imgdefaults_server") == {"relaxed", "strict"}   # another lane: not declared
