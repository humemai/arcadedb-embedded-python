#!/usr/bin/env python3
"""Unit tests for queue_lint's wait graph and its container-path rule.

RUN BY THE GATE, not by hand: queue_lint.py calls main() before it lints a
single script, on the same reasoning as test_result_digest.py -- a test that
only runs when someone remembers is a comment.

Why this file exists. Twice on 2026-09-19 the lint reported a queue it could
not actually see:

  * a stage waiting on the previous stage's ALL-DONE MARKER read as waiting on
    NOTHING, because the graph only knew the `pgrep` form. A marker-chained
    queue therefore passed the lint while being invisible to its cycle and
    orphan checks.
  * inserting `qOA2` broke it again: the pattern was `q[A-Z]+`, so a stage id
    carrying a digit did not match, and the stage AFTER it read as free to
    start beside a running one -- which is the two-runners-on-one-host failure
    the lint exists to prevent.

Both times the scripts were correct and only the lint was blind, which is the
worst shape: it reports success about a thing it is not looking at. So the
wait graph gets pinned by fixtures rather than by another pattern fix.
"""
from __future__ import annotations

import os
import sys
import tempfile

import queue_lint

FAILURES = []


def _check(name, got, want):
    if got != want:
        FAILURES.append(name)
        print(f"  FAIL {name}\n       got  {got!r}\n       want {want!r}")
    else:
        print(f"  ok   {name}")


def _graph(scripts):
    """Run the wait-graph extraction over a dict of {name: body}."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for n, body in scripts.items():
            p = os.path.join(d, f"{n}.sh")
            with open(p, "w") as fh:
                fh.write(body)
            paths.append(p)
        edges, _cycles = queue_lint.check_cycles(queue_lint.read_scripts(paths))
        return edges


HEAD = "#!/bin/bash\nset -u\nS=$HOME/STATUS.txt\n"


def test_marker_wait():
    """The form October uses, including an id with a digit."""
    g = _graph({
        "qOA": HEAD,
        "qOA2": HEAD + 'while ! grep -q "qOA ALL-DONE" "$S"; do sleep 300; done\n',
        "qOB": HEAD + 'while ! grep -q "qOA2 ALL-DONE" "$S"; do sleep 300; done\n',
    })
    _check("marker wait, plain id", g.get("qOA2"), {"qOA"})
    _check("marker wait, id with a digit", g.get("qOB"), {"qOA2"})
    _check("no wait reads as none", g.get("qOA"), set())


def test_pgrep_wait():
    """The September form: still a wait EDGE (so a cycle through it is seen)."""
    g = _graph({
        "qEA": HEAD,
        "qEB": HEAD + 'while pgrep -x -f "/bin/bash /home/tk/qEA.sh" > /dev/null; do sleep 300; done\n',
    })
    _check("pgrep wait", g.get("qEB"), {"qEA"})


def test_pgrep_wait_is_flagged():
    """...but refused as a wait: it holds only for one exact launch line (BUGS F59)."""
    old = HEAD + 'while pgrep -x -f "/bin/bash /home/tk/qEA.sh" > /dev/null; do sleep 300; done\n'
    new = HEAD + 'while ! grep -q "qEA ALL-DONE" "$S"; do sleep 300; done\n'
    flag = lambda b: [p for p in queue_lint.check_paths_and_python("qEB", b) if "BUGS F59" in p[1]]
    _check("process-name wait is flagged", len(flag(old)), 1)
    _check("marker wait is not flagged", flag(new), [])


def test_cycle_is_visible():
    """A cycle can only be found if both edges are seen."""
    g = _graph({
        "qXA": HEAD + 'while ! grep -q "qXB ALL-DONE" "$S"; do sleep 300; done\n',
        "qXB": HEAD + 'while ! grep -q "qXA ALL-DONE" "$S"; do sleep 300; done\n',
    })
    _check("cycle edge A->B", g.get("qXA"), {"qXB"})
    _check("cycle edge B->A", g.get("qXB"), {"qXA"})


def test_container_path_through_a_helper():
    """A helper that wraps a cell runner is cell-bound; one that does not is not.

    The brace-DEPTH scan matters here: `say()` closes on its own line, and a
    non-greedy regex to the next column-zero brace swallowed the function
    after it, hiding run_cell and marking say as cell-bound.
    """
    good = HEAD + (
        'say() { echo "$*" >> "$S"; }\n'
        'run_cell() {\n  python3 runner.py --lanes l2 --scale "$1"\n}\n'
        'run_cell small "BENCH_DENSE_DATA=/data/dense"\n')
    bad = HEAD + (
        'say() { echo "$*" >> "$S"; }\n'
        'helper() {\n  echo not a cell\n}\n'
        'helper "BENCH_DENSE_DATA=/data/deep10m"\n')
    with tempfile.TemporaryDirectory() as d:
        for n, body in (("qGA", good), ("qGB", bad)):
            with open(os.path.join(d, f"{n}.sh"), "w") as fh:
                fh.write(body)
        probs = {n: [p for p in queue_lint.check_paths_and_python(n, b)
                     if "container path" in p[1]]
                 for n, b in (("qGA", good), ("qGB", bad))}
    _check("container path via a cell-runner helper is fine", probs["qGA"], [])
    _check("container path via a plain helper is flagged",
           len(probs["qGB"]) > 0, True)


def main():
    for t in (test_marker_wait, test_pgrep_wait, test_pgrep_wait_is_flagged, test_cycle_is_visible,
              test_container_path_through_a_helper):
        print(f"\n== {t.__name__}")
        t()
    if FAILURES:
        print(f"\n{len(FAILURES)} queue_lint test(s) failed: {FAILURES}")
        return 1
    print("\nqueue_lint: all tests pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
