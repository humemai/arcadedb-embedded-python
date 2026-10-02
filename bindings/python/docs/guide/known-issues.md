# Known Engine Issues

These are ArcadeDB engine bugs that can return a wrong answer, store a wrong value, change
the wrong rows, or refuse a read or a write. Each entry names the versions it was measured
on, what you see, a workaround that was checked on the same reproduction, and the release
that fixes it once there is one. Entries leave this page when the fix ships in a release
these bindings package.

## A SQL decimal literal keeps only the digits a double holds

ArcadeDB [#8872](https://github.com/ArcadeData/arcadedb/issues/8872); measured on a
26.10.1 snapshot.

An unquoted decimal literal in SQL loses the digits that a double cannot hold, even when the
property is `DECIMAL`. `INSERT INTO D SET dec = 12345678901234567890.123456789012345678`
stored `1.2345678901234567E+19`.

Quote the literal, or bind a `Decimal` as a named parameter; both stored the value exactly.
A positional `Decimal` (`?`) lost the same digits.

```python
from decimal import Decimal

with db.transaction():
    db.command("sql", "INSERT INTO D SET dec = '12345678901234567890.123456789012345678'")
    db.command(
        "sql",
        "INSERT INTO D SET dec = :dec",
        {"dec": Decimal("12345678901234567890.123456789012345678")},
    )
```

## An unindexed SQL `=` or `IN` on a `DECIMAL` misses a value written with another scale

ArcadeDB [#8885](https://github.com/ArcadeData/arcadedb/issues/8885); measured on 26.9.1
and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8893, verified on its merge).

With `Decimal("19.90")` stored in a `DECIMAL` property `b`, `SELECT FROM T WHERE b = :v`
with `{"v": Decimal("19.9")}` returned 0 rows when `b` had no index, and 1 row when it had
one. `b IN :v` with `[Decimal("19.9")]`, and the string literal `b = '19.9'`, also returned
0 rows without an index. The two values are equal; only their scale differs.

Compare with a closed range on the same value, or use openCypher; both returned the row with
and without an index:

```python
from decimal import Decimal

v = Decimal("19.9")
rows = db.query("sql", "SELECT FROM T WHERE b >= :v AND b <= :v", {"v": v}).to_list()
rows = db.query("opencypher", "MATCH (n:T) WHERE n.b = $v RETURN n.b AS b", {"v": v}).to_list()
```

A positional `Decimal` (`b = ?`) also found the row, but a positional `Decimal` loses the
digits a double cannot hold (see the previous entry).

## Comparing an indexed `BOOLEAN` with `1` or `'true'` raises

ArcadeDB [#8887](https://github.com/ArcadeData/arcadedb/issues/8887); measured on 26.9.1
and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8893, verified on its merge).

With a `NOTUNIQUE` or `NOTUNIQUE_HASH` index on a `BOOLEAN` property `a`,
`SELECT FROM T WHERE a = ?` with `1` raises `ArcadeDBError` (`ClassCastException: class
java.lang.Long cannot be cast to class java.lang.Boolean`), and with `'true'` it raises a
`ClassCastException` too. Without the index the same queries return the matching row. The
literals `a = 1` and `a = 'true'` fail the same way on the indexed property, and so does
openCypher `n.a = $v` with `1`.

Bind a Python `bool`, or write the literal `true`:

```python
rows = db.query("sql", "SELECT FROM T WHERE a = ?", True).to_list()
```

## openCypher compares a `LONG` above `2**53` with a float or `Decimal` in double precision

ArcadeDB [#8888](https://github.com/ArcadeData/arcadedb/issues/8888); measured on a
26.10.1 snapshot.

With two vertices whose `LONG` property `b` holds `2**53` and `2**53 + 1`,
`MATCH (n:C) WHERE n.b = $v RETURN n` returned both vertices for `{"v": float(2**53)}` and
for `{"v": Decimal(2**53 + 1)}` when `b` had no index. With an index it returned one, and
SQL returned one with or without the index. A Python `int` returned the one matching vertex
in both languages.

On an `INTEGER` property with an index, openCypher `n.i = $v` with the string `"7.0"`
raises `NumberFormatException`. Without the index it returns no rows, and SQL returns no
rows either way.

Bind integers as Python `int`, or compare in SQL, and do not bind numeric strings to integer
properties:

```python
rows = db.query(
    "opencypher", "MATCH (n:C) WHERE n.b = $v RETURN n.b AS b", {"v": 2**53 + 1}
).to_list()
```

## `CONTAINS` and `CONTAINSVALUE` miss an integer operand on a `LIST OF DOUBLE` or `MAP OF DOUBLE`

ArcadeDB [#8890](https://github.com/ArcadeData/arcadedb/issues/8890); measured on a
26.10.1 snapshot.

On a `LIST OF DOUBLE` property `l` holding `[7.0, 8.5]` with a `BY ITEM` index,
`SELECT FROM T WHERE l CONTAINS ?` with `7` returned 0 rows; on an unindexed twin it
returned 1. On an unindexed `MAP OF DOUBLE` property `m` holding `{"x": 7.0}`,
`WHERE m CONTAINSVALUE ?` returned 0 rows with `7` and 1 row with `7.0`. A Python `int`
crosses as a `Long`, and the literals `CONTAINS 7` and `CONTAINSVALUE 7` miss the same way.

Bind the operand as the declared item or value type, here a float:

```python
rows = db.query("sql", "SELECT FROM T WHERE l CONTAINS ?", 7.0).to_list()
rows = db.query("sql", "SELECT FROM T WHERE m CONTAINSVALUE ?", float(7)).to_list()
```

## `sysdate()` is off by the JVM's offset from UTC

ArcadeDB [#8892](https://github.com/ArcadeData/arcadedb/issues/8892); measured on a
26.10.1 snapshot.

`sysdate()` returns, and stores, the current time shifted by the JVM's offset from UTC. In a
JVM on Asia/Seoul time, `INSERT INTO T SET t = sysdate()` stored a time 9 hours ahead of the
real instant; on America/New_York time (UTC-4 when measured) it was 4 hours behind.
`sysdate('<zone>')` is right only when that zone is the JVM's own: `sysdate('UTC')` was
9 hours ahead on the Asia/Seoul JVM, and `sysdate('Asia/Seoul')` was 9 hours behind on a UTC
JVM. The JVM takes its zone from the operating system, or from the `TZ` environment
variable when it is set.

Start the JVM in UTC, or bind the time from Python as a named parameter. The JVM starts once
per process, so pass the setting with the first `create_database()` or `open_database()`
call, or set `ARCADEDB_JVM_ARGS="-Duser.timezone=UTC"` in the environment before it:

```python
from datetime import datetime, timezone

import arcadedb_embedded as arcadedb

db = arcadedb.create_database(
    "./mydb", jvm_kwargs={"jvm_args": "-Duser.timezone=UTC"}
)

with db.transaction():
    db.command("sql", "INSERT INTO T SET t = :t", {"t": datetime.now(timezone.utc)})
```

## A unique composite index read by its first property returns part of the rows

ArcadeDB [#8806](https://github.com/ArcadeData/arcadedb/issues/8806); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8821, verified on its merge).

With a `UNIQUE` index on `(host, ts)`, a query that filters on `host` alone can return only
some of that host's rows once the index has been compacted, which a batched load of a few
hundred thousand records does. In the reproduction, 300,000 records over 10 hosts
committed every 1,000, `SELECT count(*) FROM Point WHERE host = 'host_7'` returned 12,589
of 30,000. `DELETE` and `UPDATE` with the same `WHERE` act on those rows only, so a cleanup
or backfill leaves the rest untouched. A `NOTUNIQUE` index is not affected.

Bound the other properties of the index too. A lower bound that every row satisfies is
enough:

```python
# Every row of the host, through the same index
rows = db.query(
    "sql", "SELECT FROM Point WHERE host = ? AND ts >= ?", "host_7", -(2**63)
).to_list()

with db.transaction():
    db.command("sql", "DELETE FROM Point WHERE host = ? AND ts >= ?", "host_7", -(2**63))
```

`REBUILD INDEX` on the affected index also restored the full answer in the reproduction.

## A SQL `UPDATE` that moves an indexed key can update the same record many times

ArcadeDB [#8814](https://github.com/ArcadeData/arcadedb/issues/8814); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8825, verified on its merge):
the statement now fixes its set of records first, so it may update them in storage order,
which can change the row order of `RETURN BEFORE` and `RETURN AFTER`.

When a SQL `UPDATE` changes a property and its `WHERE` is a range on that same property
served by an index, a record moved forward within the range is met again and updated again.
`UPDATE V SET a = a + 10 WHERE a BETWEEN 0 AND 1000` over records with `a` = 0 to 1999
made 50,601 updates for 1,001 records: all of them ended past 1000, and 991 were updated
more than once. `WHERE a < 1001` does the same. On a range of 100,000 records the statement
ran out of a 6 GB heap.

Write the range so the index does not serve it, or use openCypher, whose `MATCH ... SET`
updates each record once:

```python
with db.transaction():
    db.command("sql", "UPDATE V SET a = a + 10 WHERE a + 0 BETWEEN 0 AND 1000")

with db.transaction():
    db.command("opencypher", "MATCH (v:V) WHERE v.a >= 0 AND v.a <= 1000 SET v.a = v.a + 10")
```

## Inside a transaction that has written, index range reads miss its own inserts

ArcadeDB [#8817](https://github.com/ArcadeData/arcadedb/issues/8817); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8825, verified on its merge).

Within an open transaction that has inserted records, a range read through an index, and
`min()` or `max()` read from an index end, can leave out those new records once the index
has been compacted (200,000 entries in the reproduction, not 100,000). Equality and `IN`
lookups, `count(*)` over a whole type, and every read after the commit are correct. A
`GEOSPATIAL` index shows the same behavior.

Run such reads after the commit, which these guides already recommend for analytical reads,
or, inside the transaction, use equality and `IN` lookups.

## Deleting records with a `NOTUNIQUE_HASH` index can fail at commit

ArcadeDB [#8829](https://github.com/ArcadeData/arcadedb/issues/8829); measured on 26.9.1 and
a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8831, verified on its merge).

When a key of a `NOTUNIQUE_HASH` index holds a few dozen records or more, a transaction that
deletes some of them can fail at commit with `ArrayIndexOutOfBoundsException` or
`Cannot write outside the page space`, and its deletes are rolled back. With 300,000 records
over 1,000 key values, about 300 per key, 8 of 30 transactions of 1,000 deletes failed; with
about 30 per key, all 30 failed. Keys holding about 3 records each were not affected.

Index a property with few distinct values, such as a status or a country, with `NOTUNIQUE`
(an `LSM_TREE` index) instead of `NOTUNIQUE_HASH`; the same deletes commit there. Hash
indexes remain a good fit for keys that hold one or a few records each, such as identifiers.

## With `NULL_STRATEGY INDEX`, a SQL range with only an upper bound returns records with no value

ArcadeDB [#8833](https://github.com/ArcadeData/arcadedb/issues/8833); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot. An index with the default null strategy (`SKIP`) is not
affected. **Fixed in 26.10.1** (PR #8839, verified on its merge), also for a composite index
whose range follows equalities (`k = ? AND p < ?`).

On an index created with `NULL_STRATEGY INDEX`, a SQL range that has an upper bound and no
lower bound (`p < ?`, `p <= ?`) also returns every record whose `p` is null or absent. Over
`p` = 0 to 9 plus 3 records without `p`, `SELECT count(*) FROM T WHERE p < 2` counted 5
instead of 2, and `SELECT p FROM T WHERE p <= 0 ORDER BY p LIMIT 1` returned null instead
of 0. A range with a lower bound, and openCypher, answer correctly.

Exclude the nulls in the `WHERE`, or give the range a lower bound. `p + 0 < ?` is not a
workaround: SQL evaluates `null + 0` to 0.

```python
rows = db.query("sql", "SELECT FROM T WHERE p < ? AND p IS NOT NULL", 2).to_list()
first = db.query(
    "sql", "SELECT p FROM T WHERE p <= ? AND p IS NOT NULL ORDER BY p LIMIT 1", 0
).to_list()
```

## An openCypher range under a subtype's label can return vertices of other types

ArcadeDB [#8834](https://github.com/ArcadeData/arcadedb/issues/8834); measured on 26.9.1 and
a 26.10.1 snapshot. 26.8.1 is not affected. **Fixed in 26.10.1** (PR #8839, verified on its
merge).

When an index is declared on a parent type, an openCypher range on the indexed property under
a subtype's label can also return vertices of the parent type and of sibling subtypes. With
`Q` and `R` extending `P` and an index on `P(a)`, `MATCH (n:Q) WHERE n.a > 500 RETURN n.a`
returned the matching `Q` vertex along with a `P` and an `R` vertex. Equality lookups and
SQL (`SELECT FROM Q WHERE a > 500`) are not affected.

Repeat the label in the `WHERE`; on 26.9.1 adding `ORDER BY` is not enough:

```python
rows = db.query(
    "opencypher", "MATCH (n:Q) WHERE n.a > $min AND n:Q RETURN n.a AS a", {"min": 500}
).to_list()
```

## An openCypher range on a property with only a hash index fails

ArcadeDB [#8835](https://github.com/ArcadeData/arcadedb/issues/8835); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8839, verified on its merge): the
range falls back to the label scan, and equality still uses the hash index.

When the only index on a property is `UNIQUE_HASH` or `NOTUNIQUE_HASH`, an openCypher range
on it (`<`, `<=`, `>`, `>=`) raises `Index '...' does not support ordered iterations`.
Equality lookups use the hash index and work, and SQL answers the same range by scanning.

Index a property that you query by range with `UNIQUE` or `NOTUNIQUE` (an `LSM_TREE` index),
which serves both equality and ranges; a property cannot hold a hash index and an `LSM_TREE`
index at once. Otherwise run the range in SQL.
