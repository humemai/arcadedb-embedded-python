#!/usr/bin/env python3
"""Unit tests for bench_common.result_digest (DECISIONS #88).

RUN BY THE GATE, not by hand. equivalence_check.py calls main() before it
compares a single row, because a digest function nobody tests is a checksum of
whatever it happened to do that day, and because the last test file in this
directory (test_adapters.py) was deleted on 2026-09-14 having never once been
run (DECISIONS #85a). A test that only runs when someone remembers is a
comment.

    python3 test_result_digest.py         # standalone
    python3 equivalence_check.py          # runs these first, then the rows

What these pin down is the whole contract the gate rests on: two engines that
gave the same ANSWER must produce the same digest even though their drivers
disagree about tuples versus dicts, ints versus doubles, timezone-aware versus
naive, and trailing whitespace; and two engines that gave DIFFERENT answers
must produce different digests, including the case the decision was written
after, an adapter that quietly dropped a filter.
"""
import datetime as _dt
import decimal
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_common as B  # noqa: E402


FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def eq(name, a, b):
    check(name, a == b, f"\n         {a!r}\n         != {b!r}")


def ne(name, a, b):
    check(name, a != b, f"\n         both {a!r}")


def d(rows, **kw):
    return B.result_digest(rows, **kw)["digest"]


# --------------------------------------------------------------- driver shapes
def test_driver_shapes():
    print("driver shapes: the same answer through four drivers")
    cols = ("part", "rev")
    sql_tuples = [(1, 10.5), (2, 20.25)]                       # psycopg / duckdb / sqlite
    arcade_dicts = [{"part": 1, "rev": 10.5}, {"part": 2, "rev": 20.25}]
    mongo_group = [{"_id": 1, "rev": 10.5}, {"_id": 2, "rev": 20.25}]
    arango_named = [{"k": 1, "rev": 10.5}, {"k": 2, "rev": 20.25}]
    alias = (("part", "_id", "k"), "rev")
    eq("tuple == dict", d(sql_tuples, columns=cols), d(arcade_dicts, columns=cols))
    eq("tuple == mongo _id", d(sql_tuples, columns=alias), d(mongo_group, columns=alias))
    eq("tuple == arango RETURN {k}", d(sql_tuples, columns=alias), d(arango_named, columns=alias))

    print("driver shapes: a composite group key read through a dotted alias")
    mongo_q1 = [{"_id": {"f": "A", "s": "F"}, "n": 3}]
    sql_q1 = [("A", "F", 3)]
    q1cols = (("flag", "_id.f"), ("status", "_id.s"), "n")
    eq("mongo _id.f/_id.s == sql tuple", d(mongo_q1, columns=q1cols), d(sql_q1, columns=q1cols))


# ------------------------------------------------------------------ value rules
def test_value_rules():
    print("values: int and float spellings of the same count agree")
    eq("5 == 5.0", d([(5,)], columns=("n",)), d([(5.0,)], columns=("n",)))
    eq("60175 == 60175.0", d([(60175,)], columns=("n",)), d([(60175.0,)], columns=("n",)))
    eq("Decimal == float", d([(decimal.Decimal("10.5"),)], columns=("v",)),
       d([(10.5,)], columns=("v",)))

    print("values: two counts that differ do NOT collide under rounding")
    ne("1234567 != 1234568", d([(1234567,)], columns=("n",)), d([(1234568,)], columns=("n",)))

    print("values: strings are stripped, not otherwise touched")
    eq("' A ' == 'A'", d([(" A ",)], columns=("c",)), d([("A",)], columns=("c",)))
    ne("'A' != 'a'", d([("A",)], columns=("c",)), d([("a",)], columns=("c",)))

    print("values: dates and datetimes are ISO, aware lands in UTC")
    aware = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    naive = _dt.datetime(2026, 1, 1, 12, 0)
    offset = _dt.datetime(2026, 1, 1, 21, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=9)))
    eq("aware UTC == naive UTC", d([(aware,)], columns=("t",)), d([(naive,)], columns=("t",)))
    eq("+09:00 == the same instant in UTC", d([(offset,)], columns=("t",)),
       d([(naive,)], columns=("t",)))
    eq("date == its ISO string", d([(_dt.date(1994, 1, 1),)], columns=("t",)),
       d([("1994-01-01",)], columns=("t",)))

    print("values: None is a sentinel, a missing column is a different sentinel")
    ne("null != missing", d([{"a": None}], columns=("a",)), d([{"b": 1}], columns=("a",)))
    eq("null == null", d([(None,)], columns=("a",)), d([{"a": None}], columns=("a",)))

    print("values: booleans do not read as 1 and 0")
    ne("true != 1", d([(True,)], columns=("b",)), d([(1,)], columns=("b",)))


def test_float_tolerance():
    print("floats: summation order changes the last bits and must not fail the gate")
    rng = random.Random(4242)
    # Extended price times one minus discount, spanning the magnitudes a real
    # line-item table spans. Summed with an explicit loop, not sum(), because
    # CPython 3.12's sum() compensates and would hide the very effect this
    # tolerance exists for; an engine's aggregate does not compensate.
    vals = [rng.uniform(0, 5000) * rng.choice([1, 1e-3, 1e3]) for _ in range(60_000)]

    def loop_sum(xs):
        t = 0.0
        for x in xs:
            t += x
        return t

    a, b = loop_sum(vals), loop_sum(list(reversed(vals)))
    check("the two sums really do differ in the raw bits", a != b, f"{a!r} {b!r}")
    eq("6 significant digits reconciles them",
       d([(a,)], columns=("rev",)), d([(b,)], columns=("rev",)))
    print("floats: a difference big enough to matter still fails")
    ne("a 0.1% difference is a disagreement",
       d([(a,)], columns=("rev",)), d([(a * 1.001,)], columns=("rev",)))


# ------------------------------------------------------------------------ order
def test_order():
    print("order: a query with no ORDER BY is compared as a set")
    rows = [(1, "a"), (2, "b"), (3, "c")]
    shuffled = [(3, "c"), (1, "a"), (2, "b")]
    eq("shuffled == sorted", d(rows, columns=("k", "v")), d(shuffled, columns=("k", "v")))

    print("order: with order_matters the engine's own order is kept")
    ne("reversed != forward",
       d(rows, columns=("k", "v"), order_matters=True),
       d(list(reversed(rows)), columns=("k", "v"), order_matters=True))

    print("order: a declared key normalises an arbitrary tie order")
    e1 = [("x", 10), ("a", 5), ("b", 5)]     # engine A broke the 5-tie a,b
    e2 = [("x", 10), ("b", 5), ("a", 5)]     # engine B broke it b,a
    kw = dict(columns=("name", "rev"), order_matters=True, order_key="rev", id_key="name")
    eq("tie order does not decide the digest", d(e1, **kw), d(e2, **kw))
    print("order: membership of an ORDER BY ... LIMIT still decides it")
    ne("a different top-2 is a disagreement",
       d([("x", 10), ("a", 5)], **kw), d([("x", 10), ("z", 6)], **kw))


# --------------------------------------------------------- the failure #88 names
def test_dropped_predicate():
    print("the case the decision was written after: an adapter drops a filter")
    all_rows = [(i, i * 1.5) for i in range(100)]
    filtered = [r for r in all_rows if r[0] < 24]
    ne("filtered != unfiltered",
       d(filtered, columns=("q", "p")), d(all_rows, columns=("q", "p")))
    print("and one that drops a GROUP BY level")
    grouped = [("A", "F", 3), ("A", "N", 4)]
    flattened = [("A", None, 7)]
    ne("two groups != one",
       d(grouped, columns=("f", "s", "n")), d(flattened, columns=("f", "s", "n")))


# ------------------------------------------------------------- shape of the field
def test_record_fields():
    print("the fields a row carries")
    out = {}
    r = B.record_result(out, "q1", [(1, 2.5)], columns=("a", "b"))
    eq("digest field", sorted(out), ["res_q1_digest", "res_q1_n", "res_q1_sample"])
    eq("n is the row count", out["res_q1_n"], 1)
    eq("returned dict matches the row", out["res_q1_digest"], r["digest"])
    check("digest is 16 hex characters",
          len(out["res_q1_digest"]) == 16 and all(c in "0123456789abcdef" for c in out["res_q1_digest"]),
          out["res_q1_digest"])

    print("the sample is readable, bounded, and safe in a CSV cell")
    big = [(i, f"name {i}", i * 1.5) for i in range(500)]
    s = B.result_digest(big, columns=("i", "n", "v"))["sample"]
    check("no newline", "\n" not in s and "\r" not in s, repr(s))
    check("bounded", len(s) <= B.SAMPLE_MAX_CHARS, len(s))
    check("readable", s.startswith("("), repr(s))

    print("an engine that cannot express the query says so")
    out = {}
    B.record_unexpressible(out, "triangles", "no path pattern in the query language")
    check("digest carries the reason",
          out["res_triangles_digest"].startswith("unexpressible: "), out["res_triangles_digest"])
    check("is_unexpressible agrees", B.is_unexpressible(out["res_triangles_digest"]))
    eq("n is None, not 0", out["res_triangles_n"], None)
    check("a real digest is not mistaken for one",
          not B.is_unexpressible(B.result_digest([(1,)], columns=("a",))["digest"]))


def test_coercions():
    print("coercions: an instant is an instant, in whichever unit the engine keeps it")
    epoch_s = 1767225600                  # 2026-01-01T00:00:00Z
    kw = dict(columns=("h", "v"), coerce={"h": "epoch_s"})
    seconds = [(epoch_s, 1.5)]                                     # arcadedb doc, duckdb, sqlite
    millis = [(epoch_s * 1000, 1.5)]                               # arcadedb native (timeBucket ms)
    aware = [(_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc), 1.5)]   # mongo, timescaledb
    naive = [(_dt.datetime(2026, 1, 1), 1.5)]                      # questdb through pg-wire
    iso = [("2026-01-01T00:00:00Z", 1.5)]
    eq("seconds == milliseconds", d(seconds, **kw), d(millis, **kw))
    eq("seconds == aware datetime", d(seconds, **kw), d(aware, **kw))
    eq("seconds == naive datetime", d(seconds, **kw), d(naive, **kw))
    eq("seconds == ISO string", d(seconds, **kw), d(iso, **kw))
    print("coercions: and a different bucket is still a different answer")
    ne("the next hour disagrees", d(seconds, **kw), d([(epoch_s + 3600, 1.5)], **kw))

    print("coercions: a month key, truncated date or substring")
    mkw = dict(columns=("m", "rev"), coerce={"m": "month"})
    eq("date_trunc == substr",
       d([(_dt.date(1994, 1, 1), 10.0)], **mkw), d([("1994-01", 10.0)], **mkw))
    ne("a different month disagrees",
       d([("1994-01", 10.0)], **mkw), d([("1994-02", 10.0)], **mkw))

    print("coercions: a declared coercion is part of the digest")
    ne("coerced != uncoerced",
       d(seconds, columns=("h", "v")), d(seconds, **kw))


def test_stability():
    """The digest is a PUBLISHED value: pin it, so a silent normalisation change
    shows up as a failing test rather than as every engine disagreeing at once."""
    print("stability: the canonical form is pinned")
    rows = [("A", "F", 3, 10.5), ("N", "O", 4, 20.25)]
    eq("pinned digest", d(rows, columns=("f", "s", "n", "rev")), "6e42c35c57e68273")
    eq("pinned sample", B.result_digest(rows, columns=("f", "s", "n", "rev"))["sample"],
       "(A,F,3,10.5) ; (N,O,4,20.25)")


def test_empty_and_scalar():
    print("degenerate answers")
    eq("empty list has n=0", B.result_digest([], columns=("a",))["n"], 0)
    eq("None has n=0", B.result_digest(None, columns=("a",))["n"], 0)
    ne("empty != one null row",
       d([], columns=("a",)), d([(None,)], columns=("a",)))
    eq("a bare scalar is a one-row answer", B.result_digest(7, columns=("n",))["n"], 1)
    eq("a scalar equals the same value in a tuple",
       d(7, columns=("n",)), d([(7,)], columns=("n",)))


def main():
    for t in (test_driver_shapes, test_value_rules, test_float_tolerance, test_order,
              test_dropped_predicate, test_coercions, test_record_fields,
              test_stability, test_empty_and_scalar):
        t()
    if FAILURES:
        print(f"\n{len(FAILURES)} result_digest test(s) failed: {FAILURES}")
        return 1
    print("\nresult_digest: all tests pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
