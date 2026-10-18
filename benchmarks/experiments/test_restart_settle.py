"""l6_restart.settled_read: the vector model's fixed read is taken only once it stops changing."""
import pytest

import l6_restart


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def reader(answers):
    it = iter(answers)
    return lambda: next(it)


def test_a_stable_engine_settles_after_three_reads():
    c = Clock()
    got, n, s = l6_restart.settled_read(reader(["a", "a", "a", "x"]), reads=3, gap_s=1, within_s=600,
                                        clock=c, sleep=c.sleep)
    assert (got, n, s) == ("a", 3, 2.0)


def test_an_answer_that_changes_once_is_taken_after_it_settles():
    # the small tier's MongoDB rep 1 of 2026-10-18: two reads a moment apart differed
    c = Clock()
    got, n, s = l6_restart.settled_read(reader(["a", "b", "b", "b"]), reads=3, gap_s=1, within_s=600,
                                        clock=c, sleep=c.sleep)
    assert (got, n) == ("b", 4)


def test_an_answer_that_never_settles_refuses_the_cell():
    c = Clock()
    flip = iter(["a", "b"] * 1000)
    with pytest.raises(SystemExit, match="did not settle"):
        l6_restart.settled_read(lambda: next(flip), reads=3, gap_s=1, within_s=10, clock=c, sleep=c.sleep)
