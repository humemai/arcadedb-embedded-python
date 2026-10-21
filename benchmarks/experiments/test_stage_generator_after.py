"""`make_2611_stages.py --after none` is no wait; an empty id is never a wait (CAMPAIGN section 7, the re-pin start).

Run with `python -m pytest test_stage_generator_after.py -q` from this directory.

When the previous queue is cancelled the first stage must start when launched, and a chain that still waits on a marker nobody
will write idles forever with every script alive. The empty-string trap is the other way round: `grep -q " ALL-DONE"` matches
the first marker line in STATUS.txt, so a stage would start at once while reading as a wait. The chain itself (the first stage
without a wait, each other stage on its predecessor, `--after` required) is held by test_stage_generator_2611.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_2611_stages as G  # noqa: E402


def test_after_arg_none_and_empty_mean_no_wait():
    assert G._after_arg("none") is None and G._after_arg("None") is None and G._after_arg("") is None
    assert G._after_arg(" ") is None
    assert G._after_arg("qR20") == "qR20"
    assert G._wait(None) == "" and 'grep -qx "qR20 ALL-DONE"' in G._wait("qR20")
