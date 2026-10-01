# Known Engine Issues

These are open ArcadeDB engine bugs that can return a wrong answer or change the wrong
rows without an error. Each entry names the versions it was measured on, what you see,
and a workaround that was checked on the same reproduction. Entries leave this page when
the fix ships in a release these bindings package.

## A unique composite index read by its first property returns part of the rows

ArcadeDB [#8806](https://github.com/ArcadeData/arcadedb/issues/8806); measured on 26.8.1,
26.9.1, and a 26.10.1 snapshot.

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
26.9.1, and a 26.10.1 snapshot.

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
26.9.1, and a 26.10.1 snapshot.

Within an open transaction that has inserted records, a range read through an index, and
`min()` or `max()` read from an index end, can leave out those new records once the index
has been compacted (200,000 entries in the reproduction, not 100,000). Equality and `IN`
lookups, `count(*)` over a whole type, and every read after the commit are correct. A
`GEOSPATIAL` index shows the same behavior.

Run such reads after the commit, which these guides already recommend for analytical reads,
or, inside the transaction, use equality and `IN` lookups.
