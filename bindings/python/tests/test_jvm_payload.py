"""A Python list must never be what crosses into the JVM.

JPype copies a NumPy array over in one crossing and marshals a list element by
element, so the cost scales with the length of every vector -- and the bulk
path declines a list SILENTLY, which is why three of these survived review,
tests and every publish gate:

    e2_hybrid.ArcadeE2.build      vecs[i].tolist() -> create_vertices    4.29x
    docs .../test-numpy-support   embedding.tolist() -> vertex.set()    18.40x
    examples/03_vector_search     .tolist() then to_java_float_array()   2.20x

(BUGS F116, F117; F118 records why the correct Java batching layer did not
prevent any of them.)

The analysis lives in benchmarks/experiments/jvm_payload_check.py and runs
from here so it rides the suite that already runs in CI, rather than needing a
workflow of its own.
"""

import os
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CHECK_DIR = os.path.join(_REPO, "benchmarks", "experiments")


def _load():
    """Import the checker, or skip when the benchmark tree is not checked out.

    The bindings are distributed without benchmarks/, so a user running the
    suite from an sdist must not see a failure for a file they do not have.
    """
    if not os.path.isdir(_CHECK_DIR):
        pytest.skip("benchmarks/experiments is not checked out")
    if _CHECK_DIR not in sys.path:
        sys.path.insert(0, _CHECK_DIR)
    try:
        import jvm_payload_check
    except ImportError:  # pragma: no cover
        pytest.skip("jvm_payload_check.py is not present")
    return jvm_payload_check


def test_the_check_has_not_gone_blind():
    """Asserted FIRST, because a check that quietly stops matching looks
    exactly like a clean tree -- and this one was wrong in both directions
    while it was written. It missed F116 itself (the .tolist() was bound to a
    local one statement before the sink), then flagged an unrelated SurrealDB
    arm (ast.walk does not stop at a scope boundary, so module-wide name
    scoping let one class's `rows` hit another class's create_vertices).
    """
    check = _load()
    assert check.selftest() == 0, (
        "jvm_payload_check no longer finds the defects it exists for, or has "
        "started flagging the comparator patterns it must ignore"
    )


def test_no_python_list_crosses_into_the_jvm():
    """The bindings and the benchmark adapters carry no list-into-the-JVM site.

    Narrow on purpose: the same `.tolist()` is CORRECT on the way to Qdrant,
    Milvus, Chroma, MongoDB or Neo4j, which serialise to JSON, BSON or protobuf
    and have no Java array to be handed.
    """
    check = _load()
    paths = [
        os.path.join(_REPO, p)
        for p in (
            "benchmarks/experiments",
            "bindings/python/src",
            "bindings/python/examples",
            "bindings/python/tests",
        )
    ]
    found = []
    for path in paths:
        if not os.path.exists(path):
            continue
        for f in check._iter_py([path]):
            found.extend(check.check_file(f))

    assert not found, "\n".join(
        f"{os.path.relpath(p, _REPO)}:{line}  {why}" for p, line, why in sorted(found)
    )
