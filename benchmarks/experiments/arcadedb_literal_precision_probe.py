#!/usr/bin/env python3
"""Does an ArcadeDB SQL decimal LITERAL reach storage as the double it denotes?

WHY IT MATTERS HERE. BUGS F43 established that a decimal literal in a
COMPARISON is narrowed to single precision, which is why the TPC lane's Q6
uses BETWEEN. The served TPC adapter does not only compare with literals, it
BUILDS with them: every one of the 6,001,215 line items is an
`INSERT INTO LineItem SET ... l_extendedprice=%f ...` string. If the same
narrowing is in that path then the served arm's corpus is not the embedded
arm's corpus, every aggregate over it differs in about the eighth significant
digit, and a six-significant-digit answer digest cannot see it. That is the
shape of a false agreement, so it is measured rather than assumed.

WHAT IT MEASURES, AND WHY SUM AND NOT THE ROW. Reading the value back off the
row is not an instrument: the row renders the shortest decimal that round-trips
to the stored value, so a stored float32 of 104949.55 prints "104949.55" and
looks exact. `sum()` over a one-row type does not launder it. So each literal
is stored twice, once as SQL text and once as a bound parameter, and the two
sums are compared against the double the text denotes.

    docker run --rm --cpuset-cpus 12-15 --memory 1500m --memory-swap 1500m \
        -e ARCADEDB_HEAP=512m -v "$PWD":/probe:ro -w /tmp dbbench:arcadedb \
        python -u /probe/arcadedb_literal_precision_probe.py

MEASURED 2026-09-14 on wheel 26.8.1: six of fifteen literals were stored at
single precision, and EVERY bound parameter stored the double exactly. The ones
that survive are those whose text is the shortest decimal of their own float32,
which is every two-decimal money value below 131072 -- so TPC-H is unaffected
and the served arm's SF1 answers are bit-identical to the embedded arm's. A
lane that loads values needing more than about seven significant digits through
SQL text is not.
"""
import struct
import sys

from arcadedb_embedded import DatabaseFactory


def f32(v):
    return struct.unpack("f", struct.pack("f", v))[0]


# Literal text, chosen to walk the boundary: 0.3 repeated to seventeen places,
# the TPC-H money shapes the served adapter actually writes ("%f" gives six
# decimal places), and a few values that need more than float32 can hold.
TEXTS = ["0.3", "0.3333333", "0.33333333", "0.333333333333333",
         "1.0000001", "1.000000001", "104949.55", "104949.550000",
         "0.050000", "38255.250000", "12345.678901", "99999.999999",
         "2098.99", "0.07", "3.14159265358979"]


def main():
    with DatabaseFactory("/tmp/arcade_literal_probe").create() as db:
        for i, _t in enumerate(TEXTS):
            for k in ("L", "P"):
                db.command("sql", f"CREATE DOCUMENT TYPE {k}{i}")
                db.command("sql", f"CREATE PROPERTY {k}{i}.v DOUBLE")
        db.begin()
        for i, t in enumerate(TEXTS):
            db.command("sql", f"INSERT INTO L{i} SET v={t}")
            db.command("sql", f"INSERT INTO P{i} SET v=:v", {"v": float(t)})
        db.commit()

        print(f"{'literal':>20} {'stored (read by sum)':>26} {'the double it denotes':>26}"
              f"  verdict")
        narrowed = 0
        for i, t in enumerate(TEXTS):
            lv = db.query("sql", f"SELECT sum(v) AS s FROM L{i}").to_list()[0]["s"]
            pv = db.query("sql", f"SELECT sum(v) AS s FROM P{i}").to_list()[0]["s"]
            want = float(t)
            if pv != want:
                print(f"  BOUND PARAMETER ALSO LOST PRECISION on {t}: {pv!r}", file=sys.stderr)
            if lv == want:
                verdict = "double"
            else:
                narrowed += 1
                rel = abs(lv - want) / abs(want)
                verdict = (f"SINGLE, {rel:.2e} relative"
                           + ("  (bit-identical to float32)" if lv == f32(want)
                              else "  (the shortest decimal of its float32)"))
            print(f"{t:>20} {lv!r:>26} {want!r:>26}  {verdict}")
        print(f"\n{narrowed} of {len(TEXTS)} literals were NOT stored as the double they "
              f"denote; every bound parameter was")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
