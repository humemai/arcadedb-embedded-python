# Known Engine Issues

These are ArcadeDB engine bugs that can return a wrong answer, store a wrong value, change
the wrong rows, or refuse a read or a write. The last entry is not an engine bug: it is a
race in JPype, the library that connects Python to the engine. Each entry names the versions
it was measured on, what you see, a workaround that was checked on the same reproduction, and
the release that fixes it once there is one. Entries leave this page when the fix ships in a
release these bindings package.
An entry with a `Tests:` line has a test of its workaround and a strict `xfail` test of the
engine behavior; the `xfail` starts failing the suite when a fix reaches the wheel, which is
the cue to remove the entry.

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
26.10.1 snapshot. **Fixed in 26.10.1** (PR #8894, verified on its merge).

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

ArcadeDB [#8890](https://github.com/ArcadeData/arcadedb/issues/8890); measured on 26.9.1
and a 26.10.1 snapshot. **Fixed in 26.10.1** (PR #8894, verified on its merge): a `BY ITEM`
index is keyed by the list's declared item type. An index built before the upgrade keeps its
old keys, and its old answers, until you rebuild it with `REBUILD INDEX <name>`; until then a
lookup through it can disagree with the same query without the index.

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
26.10.1 snapshot. **Fixed in 26.10.1** (PR #8894, verified on its merge).

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

## An `UPDATE` or `DELETE` with positional parameters can read its `WHERE` from the wrong parameter

ArcadeDB [#9245](https://github.com/ArcadeData/arcadedb/issues/9245); measured through the
bindings on a 26.10.1 snapshot (engine `ad42f5f32e`), and in Java on upstream main from the
merge of #9218 (`1addb51950`) on.
**Fixed in 26.10.1** (PR #9252, verified on upstream main 354396071e): the engine keys the
plan of the records an `UPDATE` or `DELETE` reads by the text of its statement, so statements
that differ only in the position of a `?` no longer share one. It affected only the 26.10.1
snapshots between #9218 and #9252. Named parameters were never affected, and neither were
26.9.1 and the snapshots before #9218.

Since #9218 the engine plans the records an `UPDATE` or `DELETE` reads as a `SELECT` with the
same `WHERE`, and keeps that plan in the plan cache for every statement whose `WHERE` reads
the same. A positional `?` reads the same at every position, so a statement whose `?` sits
at another position reads its `WHERE` from the wrong parameter, and the count it reports
does not show it. `UPDATE A SET brand = ? WHERE sku = ?` with `"NEW", "S2"`, run after
`SELECT FROM A WHERE sku = ?`, changed the record whose sku is `NEW`, left `S2` as it was,
and reported a count of 1. An earlier `UPDATE` or `DELETE` with the same type and `WHERE`
does the same, with or without an index on the property. In the other direction the
statement reads a parameter it does not have: after `UPDATE D SET brand = ? WHERE sku = ?`,
`DELETE FROM D WHERE sku = ?` with `"S2"` deleted nothing and reported a count of 0. The
same plan was shared by the statements of one SQL script (`UPDATE A SET brand = 'x1' WHERE
sku = ?; UPDATE A SET brand = 'x2' WHERE sku = ?;` with `"S1", "S2"` updated `S1` twice and
`S2` not at all), by `UPDATE ... UPSERT` after a `SELECT` with the same `WHERE` (it updated
the record named by the SET value instead of inserting), and by `:name` parameters given as
positional values.

On a snapshot between #9218 and #9252, bind the parameters of an `UPDATE` or `DELETE` by
name. A named parameter is read by its name, so a shared plan reads the right value:

```python
with db.transaction():
    db.command(
        "sql",
        "UPDATE A SET brand = :brand WHERE sku = :sku",
        {"brand": "NEW", "sku": "S2"},
    )
```

Tests: `tests/test_dml_plan_cache_known_issues.py` checks the workaround and asserts the
right answer on every engine (the test of the first case was a strict `xfail` tripwire,
keyed on the engine having #9218, until the fix reached the engine these tests run on).

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
(an `LSM_TREE` index) instead of `NOTUNIQUE_HASH`; the same deletes commit there. A key that
holds one or a few records, such as an identifier, is not affected; whether a hash index is
the right choice for it is a separate question, answered by
[Index choice for an id](core/queries.md#choosing-index-types-in-sql-dsl): a hash index
fits an id that is read by equality only and is not bulk-loaded in key order.

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

## `GraphBatch` edges with declared properties skip conversion and constraints

ArcadeDB [#9018](https://github.com/ArcadeData/arcadedb/issues/9018) and
[#9019](https://github.com/ArcadeData/arcadedb/issues/9019); measured through the bindings
on a 26.10.1 snapshot. The Java reproductions in the two issues show the same on 26.9.1.
**Fixed in 26.10.1** (#9018 by PR #9107, #9019 by PR #9108, both verified on their merges): a
`GraphBatch` edge now stores a null as null and refuses or converts a declared value as
`Vertex.new_edge(...)` does.

An edge written through `GraphBatch` (`batch.new_edge(...)` with properties, or
`batch.new_edges(..., properties=[...])`) is serialized without the declared property's
conversion or the type's constraints. With an edge type that declares `weight INTEGER`,
`small SHORT`, and `note STRING`:

- `weight=None, note="hello"` is stored as `weight = -1`: the null is written as a type tag
  with no value, so the bytes of the next property are read as the value. A null in the
  last property reads back as null but logs `Possible corrupted record` when the edge is read.
- `small=40000` is stored as `-25536`.
- `MANDATORY`, `MIN`, and `REGEXP` are not checked and `DEFAULT` is not applied.

`Vertex.new_edge(...)` converts and validates the same values: the null stays null and
40000 is refused. A batch that also holds an edge of a second type stores the null
correctly, which is not something to rely on.

Write edges that carry declared properties through the vertex API, in a transaction. Edge
types with no declared properties, or whose properties you give already converted and never
`None`, are not affected, and `GraphBatch` stays the fast path for those.

```python
with db.transaction():
    a = db.new_vertex("P").set("id", 1).save()
    b = db.new_vertex("P").set("id", 2).save()
    a.new_edge("Knows", b, weight=None, note="hello").save()  # null stays null
```

Tests: `test_vertex_new_edge_keeps_a_null_and_refuses_an_out_of_range_short` checks this
workaround, and the two `GraphBatch` tests next to it assert the fixed behavior (they were
strict `xfail` tripwires until the fix reached the engine these tests run on).

## `CREATE PROPERTY` with `mandatory` and `notnull` over records that lack the property makes `ORDER BY` drop them

ArcadeDB [#9017](https://github.com/ArcadeData/arcadedb/issues/9017); measured through the
bindings on a 26.10.1 snapshot. The `ORDER BY` answers are new on main: the same Java
reproduction returns every record on 26.9.1 and on the 2026-09-17 main snapshot.
**Fixed in 26.10.1** (PR #9116, verified on its merge): `CREATE PROPERTY` and `ALTER PROPERTY`
with `MANDATORY`, `NOTNULL`, `MIN`, `MAX`, or `REGEXP`, and the openCypher `NOT NULL` and
`NODE KEY` constraints, are refused over records that violate them, naming the first such
record, and leave no property behind.

`CREATE PROPERTY T.v INTEGER (mandatory true, notnull true)` is accepted over records that
have no `v`, and the planner then trusts the two flags to mean that an index on `v` holds
every record. With five records and a `NOTUNIQUE` index on `v`, where the fifth has no `v`,
`SELECT id FROM T ORDER BY v` returned `[1, 2, 3, 4]` while `count(*)` was 5 and
`ORDER BY id` returned all five. `ALTER PROPERTY ... MANDATORY true` refuses the same
records since upstream #8956; `CREATE PROPERTY` and the openCypher `CREATE CONSTRAINT`
statements do not.

Give every record the property before you declare the constraints, or declare them on a type
that is still empty; from 26.10.1 this is the only way, since the declaration over such
records is refused. On an earlier engine, a type already declared over such records answers
`ORDER BY` correctly again after `ALTER PROPERTY T.v MANDATORY false` and `ALTER PROPERTY T.v
NOTNULL false`; both ways returned all five records on the same reproduction.

```python
with db.transaction():
    db.command("sql", "UPDATE T SET v = 0 WHERE v IS NULL")
db.command("sql", "CREATE PROPERTY T.v INTEGER (mandatory true, notnull true)")
```

Tests: `tests/test_declared_type_known_issues.py` checks the workaround and asserts the fixed behavior (it was a strict `xfail` tripwire until the fix reached the engine these tests run on).


## An index on an `INTEGER` or `LONG` answers for a bound with a fraction as if it were rounded

ArcadeDB [#9021](https://github.com/ArcadeData/arcadedb/issues/9021); measured through the
bindings on a 26.10.1 snapshot, and in Java on 26.9.1 and the 2026-09-17 main snapshot.
**Fixed in 26.10.1** (PR #9126, verified on its merge): an index on an `INTEGER`, `LONG`, or
`SHORT` key answers for the exact bound, so SQL, openCypher, and the Java `select()` API return
the rows the unindexed scan returns.

On an indexed `INTEGER` holding 11, 12, and 13, a bound of `12.5` (a Python `float`, as a
parameter or a literal) gives other rows than the same query on an unindexed copy:
`i = :b` returned `[12]` against `[]`, `i >= :b` returned `[12, 13]` against `[13]`, and
`i < :b` returned `[11]` against `[11, 12]`. On an indexed `LONG`, a `float` of `1e19` finds
the record holding `Long.MAX_VALUE`. Other bounds that need no rounding are not affected.

Before 26.10.1, round the bound yourself, in the direction that keeps the same rows:
`math.ceil(b)` for `>=` and `<`, `math.floor(b)` for `>` and `<=`, and do not run an equality
query when `b != int(b)`, because no integer equals it. For all four range operators the
rounded integer bound returned the same rows as the unindexed scan.

```python
import math

b = 12.5
rows = db.query("sql", "SELECT i FROM T WHERE i >= :b", {"b": math.ceil(b)}).to_list()
```

Tests: `tests/test_declared_type_known_issues.py` checks the workaround and asserts the fixed behavior (it was a strict `xfail` tripwire until the fix reached the engine these tests run on).


## A value that cannot be converted is stored as `NULL`, and `''` as `0`, in a declared numeric property

ArcadeDB [#9014](https://github.com/ArcadeData/arcadedb/issues/9014) and
[#9027](https://github.com/ArcadeData/arcadedb/issues/9027); measured through the bindings
on a 26.10.1 snapshot, and in Java on 26.9.1 and the 2026-09-17 main snapshot.
**Fixed in 26.10.1** (PR #9121, verified on its merge): a write to a declared property now
refuses a value the type cannot hold, with an error naming the property, instead of storing
`NULL`, `0`, or a wrapped number.

Writing `True`, a `list`, or a `dict` to a declared `BYTE`, `SHORT`, `INTEGER`, `LONG`,
`FLOAT`, or `DOUBLE` property is accepted and stores `NULL`: `doc.set("i", True)`,
`doc.set("i", [1, 2])`, and `doc.set("i", {"a": 1})` followed by `save()` all read back
`None`, with no error (the string `'abc'` is refused). An empty string bound as a parameter
to a `SHORT`, `INTEGER`, `LONG`, `FLOAT`, or `DOUBLE` is stored as `0`, while `BYTE` and
`DECIMAL` refuse it.

Convert in Python before you write. `int(value)` raised `TypeError` for the list and the
dict, gave `1` for `True` and `7` for `"7"`, and an empty string is better mapped to `None`
explicitly than left to the engine.

```python
def to_int(value):
    return None if value == "" else int(value)


with db.transaction():
    doc = db.new_document("N").set("i", to_int(user_value))
    doc.save()
```

Tests: `tests/test_declared_type_known_issues.py` checks the workaround and asserts the fixed behavior (it was a strict `xfail` tripwire until the fix reached the engine these tests run on).

## SQL `p = ?` with `None` bound returns the records without a value through an index that stores null keys

ArcadeDB [#9238](https://github.com/ArcadeData/arcadedb/issues/9238); measured through the
bindings on 26.9.1 and a 26.10.1 snapshot, and in Java on the 2026-09-17 main snapshot and
on main of 2026-10-05.
**Fixed in 26.10.1**, in two steps: PR #9246 (verified on upstream main 111aa40457) for a
statement that is planned with the null, and PR #9276 (ArcadeData/arcadedb#9274, verified
on upstream main d36b4ca3ae) for a statement whose plan was cached by an earlier run with a
value. An equality with a null value now matches no record, as on a type without an
index, whichever run planned the statement. A `DELETE` or `UPDATE` with it changes nothing
and reports a count of 0, and an `LSM_TREE` index with `NULL_STRATEGY ERROR` no longer
raises. `p IS NULL` and `p <=> ?` are unchanged. The entry describes what earlier engines
and snapshots did.

In SQL an equality with a null value matches no record, and on a type without an index
`p = ?` with `None` returns none. Through an index that stores null keys it returned the
records whose `p` is null or absent instead. Over three records with `p = 1`, `p = null`,
and no `p`, all with `q = 7`, the last two came back for `p = ?` bound to `None` (and for
`p = :x` with `{"x": None}`):

- through a `NOTUNIQUE` or `NOTUNIQUE_HASH` index on `p` created with `NULL_STRATEGY INDEX`;
  through a `UNIQUE` or `UNIQUE_HASH` one, only one of them;
- for `q = 7 AND p = ?`, through a composite index on `(q, p)` or `(p, q)`, `LSM_TREE` or
  hash, and for `p = ?` alone through an `LSM_TREE` one on `(p, q)`. This includes indexes
  created with the default null strategy (`SKIP`), which keeps a key unless all of its
  properties are null.

`DELETE ... WHERE p = :x` and `UPDATE ... WHERE q = 7 AND p = :x` with `{"x": None}` deleted
and updated those records. Through an `LSM_TREE` index with `NULL_STRATEGY ERROR` the query
raised `ArcadeDBError` (`Indexed key ... cannot be NULL`) instead of matching nothing. The
literal `p = null` and openCypher `n.p = $x` with `None` matched nothing, as they should.

The first fix was made when the statement is planned, and the engine keeps the plan by the
text of the statement. A statement whose first run bound a value was planned through the
index, and its next run with `None` reused that plan. Through an index on one property
(`NOTUNIQUE`, `NOTUNIQUE_HASH`, or `UNIQUE`, positional or named) that run still returned
the records whose `p` is null or absent (`[1]`, then `[2, 3]` over the three records), and
through an `LSM_TREE` index with `NULL_STRATEGY ERROR` it raised again. A
`DELETE ... WHERE p = :x` run first with a value that matched nothing and then with `None`
removed those records. Indexes on several properties were not affected, and neither was a
statement whose first run bound `None`. Measured on upstream main 111aa40457; with
`arcadedb.sqlStatementCache` set to 0 the `SELECT` answered `[1]`, `[]`, `[1]`, so the cache
of plans was the cause (ArcadeData/arcadedb#9274). PR #9276 removes the dependence of the
plan on the parameter: the index lookup is skipped at execution when an equality slot is
null, as it already was for a null `IN` element and a null range bound.

On 26.9.1 and earlier, and on a snapshot before PR #9276, do not bind `None` to `=`. When `None` means "no value" and you want those
records, ask for them with `p IS NULL`, or with the null-safe `p <=> ?`, which takes a value
or `None`; both returned what the type without an index returns. An index on `p` does not
serve `<=>`, so it reads the whole type. When `None` should match nothing, as SQL defines
it, do not run the query, the `DELETE`, or the `UPDATE`. On 26.10.1 binding `None` to `=` is safe and matches nothing, but `p IS NULL` or `p <=> ?` is still the way to ask for the records without a value.

```python
def children_of(parent):
    if parent is None:
        return db.query("sql", "SELECT FROM T WHERE parent IS NULL").to_list()
    return db.query("sql", "SELECT FROM T WHERE parent = ?", parent).to_list()


# One query for a value or None; it reads every record of T
rows = db.query("sql", "SELECT FROM T WHERE parent <=> ?", parent).to_list()
```

On a `UNIQUE` or `UNIQUE_HASH` index with `NULL_STRATEGY INDEX`, `p IS NULL` had an issue of
its own before 26.10.1 (the next entry); use `p <=> ?` there on those engines.

Tests: `tests/test_null_index_known_issues.py` checks the workaround and asserts the fixed behavior, including the statement run with a value, then `None`, then the value (the cases of PR #9246 and PR #9276 were strict `xfail` tripwires until the fixes reached the engine these tests run on).

## SQL `p IS NULL` through a `UNIQUE` or `UNIQUE_HASH` index with `NULL_STRATEGY INDEX` returns one record

ArcadeDB [#9237](https://github.com/ArcadeData/arcadedb/issues/9237); measured through the
bindings on 26.9.1 and a 26.10.1 snapshot, and in Java on the 2026-09-17 main snapshot and
on main of 2026-10-05.
**Fixed in 26.10.1** (PR #9252, verified on upstream main 354396071e): `p IS NULL` through
such an index returns every record whose `p` is null or absent, and `count(*)` counts them,
as the type without an index does.

A unique index created with `NULL_STRATEGY INDEX` accepts any number of records whose key
is null, since a null key is exempt from uniqueness, and keeps an entry for each of them.
SQL `p IS NULL` answered through that index returns one of them, and `count(*)` counts one.
Over four records written in four transactions, with `p = 1`, `p = null`, no `p`, and
`p = null`, `SELECT id FROM T WHERE p IS NULL` returned `[4]` and `count(*)` returned 1,
where a `NOTUNIQUE` index and the type without an index return `[2, 3, 4]` and 3. Another
condition next to it (`p IS NULL AND id > 0`) returned the same one record.

Before 26.10.1, use the null-safe `p <=> null`, which returned all three records and
counted 3. The index does not serve it, so it reads the whole type. openCypher `n.p IS NULL`
also returned all three.

```python
rows = db.query("sql", "SELECT FROM T WHERE p <=> null").to_list()
n = db.query("sql", "SELECT count(*) AS n FROM T WHERE p <=> null").first().get("n")
```

Tests: `tests/test_null_index_known_issues.py` checks the workaround and asserts the fixed behavior (it was a strict `xfail` tripwire until the fix reached the engine these tests run on).

## An openCypher equality on the first property of a composite hash index fails

ArcadeDB [#9236](https://github.com/ArcadeData/arcadedb/issues/9236); measured through the
bindings on 26.9.1 and a 26.10.1 snapshot, and in Java on the 2026-09-17 main snapshot and
on main of 2026-10-05.
**Fixed in 26.10.1** (PR #9252, verified on upstream main 354396071e): the planner no longer
seeks a hash index with a part of its key. Such a `MATCH` reads the type and returns the rows
the type without an index returns, and a `None` for `q` matches nothing. With both properties
given, the hash index still answers.

With a `NOTUNIQUE_HASH` or `UNIQUE_HASH` index on `(p, q)`, an openCypher `MATCH` that gives
only `p` (`WHERE n.p = 1`, `{p: 1}`, or `WHERE n.p IN [1, 2]`), or gives `q` as a parameter
bound to `None`, fails when its rows are read with
`java.lang.UnsupportedOperationException: Index '...' does not support ordered iterations`.
The exception is the Java one that JPype raises, not `ArcadeDBError`. The planner seeks the
hash index with a part of its key, which only an ordered index can read. With both properties
given (`n.p = 1 AND n.q = 5`) the hash index answers, and SQL `WHERE p = 1` answers on the
same type. 26.10.1 also fixes the same failure for a range on a property whose only index is
a hash index (ArcadeDB [#8835](https://github.com/ArcadeData/arcadedb/issues/8835)).

Before 26.10.1, run the query in SQL, give every property of the key, or index the
properties with `NOTUNIQUE` (an `LSM_TREE` index), which serves a part of the key in
openCypher. A `None` for `q` makes the equality match nothing; do not run the query (see the
#9238 entry).

```python
rows = db.query("sql", "SELECT FROM T WHERE p = ?", 1).to_list()
rows = db.query(
    "opencypher",
    "MATCH (n:T) WHERE n.p = $p AND n.q = $q RETURN n",
    {"p": 1, "q": 5},
).to_list()
```

Tests: `tests/test_null_index_known_issues.py` checks the workaround and asserts the fixed behavior (it was a strict `xfail` tripwire until the fix reached the engine these tests run on).


## `GraphBatch` commits a transaction you opened, and its retry can roll yours back

ArcadeDB [#9242](https://github.com/ArcadeData/arcadedb/issues/9242); measured through the
bindings on 26.9.1 and on two 26.10.1 snapshots, with the same results on each.
**Fixed in 26.10.1** (PR #9270, verified through the bindings on upstream 5a90b0f52a, on
JDK 25): the calls below now refuse to run inside a transaction you opened and leave it
untouched. On 26.9.1 and earlier, and on a snapshot before 5a90b0f52a, they behave as
described next.

`GraphBatch.create_vertices()`, `flush()`, and `close()` joined a transaction that was
already open on the thread and committed it together with the batch's own work. So did
`new_edge()` and `new_edges()` when the buffer reached `batch_size` and they flushed, and so
did leaving a `with db.graph_batch()` block, which calls `close()`. After `db.begin()`,
saving a document, and `batch.create_vertices("V", 2)`:

- no transaction is active, and `db.rollback()` returns normally and leaves the document in
  place, also after the database is closed and reopened;
- `db.commit()`, or the end of a `with db.transaction():` block, raises `ArcadeDBError`
  (`Transaction not begun`), after the document has been committed;
- the document is committed with the batch's WAL setting, so with the default
  `use_wal=False` its commit writes no WAL record.

When the first commit attempt of `create_vertices()` fails with an error the engine retries,
such as a concurrent modification, the engine rolls back the open transaction, yours
included, then retries in a transaction of its own and commits only the vertices. The call
returns normally and your document is gone.

From 26.10.1 each of those calls raises `ArcadeDBError` (the cause is a
`java.lang.IllegalStateException`: `manages its own transactions and cannot run inside a
transaction the caller opened`) and your transaction stays open with your writes in it:
`db.rollback()` undoes them and `db.commit()` commits them. The rules the refusal follows:

- `flush()` with nothing buffered and `close()` with nothing pending still run inside your
  transaction, since there is nothing to commit.
- A `close()` that is refused releases nothing. The batch stays open with its edges pending,
  and the same `close()` after your transaction ends writes them. Until then
  `db.graph_batch()` on that database raises `A GraphBatch is already in progress`. Leaving a
  `with db.graph_batch()` block inside your transaction raises the refusal out of the block
  for the same reason: end your transaction before the block exits.
- `new_edges()` buffers the edges that fit before the one that fills the buffer, and the
  refusal comes at that edge, so a refused call may have buffered some of its edges. They
  stay buffered and the next flush outside your transaction writes them.
- The batch's WAL setting applies to the transaction of the batch's own call only, so a
  transaction of yours between two calls commits with the setting you chose.

Before this version of the bindings, a refused `close()` marked the `GraphBatch` closed,
which made the retry a no-op that wrote nothing and kept the database's batch guard held.
It is fixed here, and `close()` leaves the object open after a refusal.

`create_vertex()` is not affected: inside your transaction it saves the vertex without
committing, and your `rollback()` undoes both.

On 26.9.1 and earlier, commit your own writes before the batch's first call, or write them
after it closes, and call the batch outside any transaction of yours. That way each rollback
undoes only its own writes, and a retried vertex commit loses nothing of yours. It is the
right order on every version:

```python
with db.transaction():
    db.new_document("Note").set("text", "mine").save()

with db.graph_batch() as batch:
    rids = batch.create_vertices("Person", [{"id": i} for i in range(1000)])
    batch.new_edges(rids[:-1], "Knows", rids[1:])
```

Tests: `tests/test_graph_batch.py` asserts the refusal for each call, the retry of a refused
`close()`, and the WAL setting; `test_graph_batch_outside_the_callers_transactions` checks the
order above (it was strict `xfail` tripwires for the engine behavior until the fix reached the
engine these tests run on).


## A vector search misses recently added records while `COMPACT INDEX` runs

ArcadeDB [#9241](https://github.com/ArcadeData/arcadedb/issues/9241); measured through the
bindings on a 26.10.1 snapshot of 2026-10-04.
**Fixed in 26.10.1** (PR #9252, verified in Java on upstream main 354396071e, on JDK 21 and
25: no search pass missed a record during a compaction of about 45 s). It affected only the
26.10.1 snapshots between upstream PR #9132 (2026-10-03), which introduced it, and PR #9252.
26.9.1 is not affected, and neither are snapshots before #9132: the same run on 26.9.1 and
on a snapshot of 2026-10-03 from before it missed nothing.

While `COMPACT INDEX` rebuilds an `LSM_VECTOR` index, a search with a record's own vector does
not return that record when it was added after the index's graph was last built. With 20,000
vectors in the graph and 300 more added one per transaction, `vectorNeighbors(..., 10)` found
all 300 before the compaction and after it, and during the 8.4 s compaction it missed up to
all 300 of them in 47 of 48 search passes. Nothing is lost: once `COMPACT INDEX` returns,
every search finds them again. In the issue's reproduction, records deleted before the
compaction also make most of the older records unfindable for part of it.

The engine also runs this compaction on its own, through the same code, once an index's data
file is about three times the size its live vectors need
(`arcadedb.vectorIndex.compactionBloatFactor`, 3); repeated updates and deletes of vectors
get there. The graph rebuilds that run after a number of writes or a pause in writing, and
`build_graph_now()`, do not rewrite the file and are not affected.

On a snapshot between #9132 and #9252, run `COMPACT INDEX` on a vector index while nothing
searches it. To keep the engine from starting the compaction on its own, set the bloat factor
to 0 when the JVM starts; the index then compacts only when you run `COMPACT INDEX`:

```python
db = arcadedb.create_database(
    "./mydb", jvm_kwargs={"jvm_args": "-Darcadedb.vectorIndex.compactionBloatFactor=0"}
)
```

There is no test of this entry: the miss needs a compaction that runs for seconds and
searches that land inside it, too slow and too timing-dependent for the suite.


## Ctrl-C during an interruptible Java wait can raise `InterruptedException`, not `KeyboardInterrupt`

JPype 1.7.1, the version the wheel installs; measured through the bindings with a 26.10.1
snapshot of the engine. Open. This is a race in JPype, not in ArcadeDB; it is reported as
[jpype-project/jpype#1496](https://github.com/jpype-project/jpype/issues/1496).

With the default `interrupt=False`, JPype handles SIGINT in Java. Its handler first interrupts
the main thread with `Thread.interrupt()` and only then tells Python that Ctrl-C arrived. A
Java call that waits in an interruptible way wakes up between the two steps, and JPype finds
no Python interrupt yet. `Thread.sleep()` and `Object.wait()` do, and so does the engine's
`wait_completion()` on an async executor (its Java source handles `InterruptedException`;
this one was not measured). Instead of a `KeyboardInterrupt` from the call you see one of:

- `java.lang.InterruptedException` raised from the call, and the `KeyboardInterrupt` a
  moment later in whatever statement runs next: a `finally` block, an `atexit` hook such as
  the bindings' own close of open databases. The program ends with exit status 1 or by
  SIGINT, with a traceback that names `InterruptedException`.
- `RuntimeError: Fatal error occurred`, with `Fatal error in exception handling` and
  `Handling: java.lang.InterruptedException: sleep interrupted` on stderr. `finally` blocks
  and `atexit` hooks still ran.

SIGINT at a random moment of a 1.5 s `Thread.sleep()` on two pinned cores gave one of these in
14 of 400 interrupts (3.5%) with the cores idle, and in 26 of 200 (13%) with two busy loops
sharing the two cores. `Object.wait()` with the busy loops: 42 of 200 (21%). A Python loop,
and a Java call that ignores `Thread.interrupt()` (a socket `accept()` with a timeout, which
returns with its `KeyboardInterrupt` when it times out), had no failure in 150 interrupts each
with the busy loops.

Wait in Python instead, so the main thread is never inside the Java wait: run the call in a
daemon thread and poll it with `join`. Ctrl-C then raises `KeyboardInterrupt` in the main
thread within the poll interval, and 150 of 150 interrupts with the busy loops did, with a
`Thread.sleep()` in the worker:

```python
import threading

worker = threading.Thread(target=async_exec.wait_completion, daemon=True)
worker.start()
while worker.is_alive():
    worker.join(0.1)  # Ctrl-C raises KeyboardInterrupt here, never inside the Java wait
```

The worker keeps waiting after Ctrl-C and ends with the process. A Python wait loop such as
`while True: time.sleep(1)`, as in the server examples, is not affected.

The same handler has a second problem with `interrupt=False` when Python has no handler of its
own for SIGTERM, which is the normal state of a script: `kill -TERM` crashes the process with a
SIGSEGV in `PyErr_SetInterruptEx` (exit status -6 and an `hs_err_pid*.log`) instead of stopping
it ([jpype-project/jpype#1497](https://github.com/jpype-project/jpype/issues/1497); measured on
JPype 1.7.1 and master, Temurin 21 and 25, 10 of 10 attempts each, and through the bindings, 3
of 3). Register a handler after the first database is opened, which is after the JVM has
started; the process then stops at once, 3 of 3 through the bindings. A handler registered
before the JVM starts also avoids the crash, but runs only when the main thread next executes
Python code, so a blocking call such as `time.sleep(30)` delays it until the call returns:

```python
import signal
import sys

db = arcadedb.create_database("./mydb")
signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
```

Tests: `tests/test_sigint.py` covers a Python loop and a Java call that Ctrl-C cannot wake.
It has no test of the waits above, because the failure is random (humemai/arcadedb-embedded-python#179).


## An openCypher count with a negated pattern in a chain is wrong when the far end has another label or the pattern has a property map

ArcadeDB [#9277](https://github.com/ArcadeData/arcadedb/issues/9277) and
[#9278](https://github.com/ArcadeData/arcadedb/issues/9278); measured through the bindings on
a 26.10.1 snapshot of upstream d36b4ca3ae, and in Java on that build, on 26.9.1, and on
5a90b0f52a, on Temurin 21 and 25, with the same answers. Open.

A `MATCH` chain of two or more hops that ends in `RETURN count(*)` and has a negated pattern
predicate between two of its nodes (`WHERE NOT (a)-[:R]-(c)`, alone or with `AND a <> c` or
`AND id(a) <> id(c)`) is answered by a count push-down; `EXPLAIN` lists `COUNT ANTI-JOIN
CHAIN`. It counts wrong in two cases:

- **Another label at the far end (#9277).** On the single path
  `(x0:Person)-[:KNOWS]-(x1:Person)-[:KNOWS]-(y0:Employee)-[:HAS_INTEREST]->(t:Tag)`, in which
  `x0` and `y0` are not connected, the chain `(p1:Person)...(p2:Person)...(p3:Employee)...(t:Tag)`
  with `WHERE NOT (p1)-[:KNOWS]-(p3)` counted 0 where the answer is 1. The same holds with
  `AND p1 <> p3`. A chain whose nodes all have the same label, and a far end that is a sub type
  of the first labels, gave the right count in every case I ran. From the snapshot that carries
  upstream #9271, `id(p1) <> id(p3)` takes the same push-down, so that spelling, which counted 1
  before, now counts 0.
- **A property map on the pattern's relationship (#9278).** The push-down drops it. With an edge
  `x -[:K {w: 0}]-> z`, `WHERE NOT (x)-[:K {w: 1}]->(z)` counted 0 where the answer is 1,
  because no edge with `w = 1` connects them; it was counted as `NOT (x)-[:K]->(z)`.

Put the variables through a `WITH` before the `WHERE`. That keeps the query off the push-down,
and the row pipeline counted the right number in every case above. It gives up the push-down's
speed for that query:

```python
chain = "MATCH (p1:Person)-[:KNOWS]-(p2:Person)-[:KNOWS]-(p3:Employee)-[:HAS_INTEREST]->(t:Tag) "
n = (
    db.query(
        "opencypher",
        chain + "WITH p1, p2, p3, t WHERE NOT (p1)-[:KNOWS]-(p3) RETURN count(*) AS n",
    )
    .first()
    .get("n")
)
```

Tests: `tests/test_count_pushdown_known_issues.py` checks the `WITH` workaround and the cases
that are not affected, and has strict `xfail` tests of the wrong counts; they start failing the
suite when the engine fixes them, which is the cue to remove this entry.


## `sum()` and `avg()` over a `BYTE` property raise `IllegalArgumentException`

ArcadeDB [#9281](https://github.com/ArcadeData/arcadedb/issues/9281); measured through the
bindings on a 26.10.1 snapshot of upstream d36b4ca3ae, and in Java on that build, on 26.9.1, and
on 5a90b0f52a, on Temurin 21 and 25. Open.

Over a property declared `BYTE`, `SELECT sum(b) FROM T` and `SELECT avg(b) FROM T` in SQL and
`MATCH (n:V) RETURN sum(n.b)` in openCypher raise `ArcadeDBError` (`Query failed:
java.lang.IllegalArgumentException: Cannot increment value '100' (class java.lang.Byte) with
'50' (class java.lang.Byte)`) once the aggregate has two rows to add. The same values in a
`SHORT` or `INTEGER` property sum and average as expected.

Convert the value before the aggregate, `b.asInteger()` in SQL and `toInteger(n.b)` in
openCypher, or declare the property `SHORT`:

```python
total = db.query("sql", "SELECT sum(b.asInteger()) AS total FROM T").first().get("total")
average = db.query("sql", "SELECT avg(b.asInteger()) AS average FROM T").first().get("average")
```

Tests: `tests/test_count_pushdown_known_issues.py` checks the conversion workaround and has strict
`xfail` tests of the failing aggregates; they start failing the suite when the engine fixes them,
which is the cue to remove this entry.
