# Known Engine Issues

These are ArcadeDB engine bugs that can return a wrong answer, change the wrong rows, or
refuse a write. Each entry names the versions it was measured on, what you see, a workaround
that was checked on the same reproduction, and the release that fixes it once there is one.
Entries leave this page when the fix ships in a release these bindings package.

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
