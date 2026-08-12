# RESTORE SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_restore_sql.py){ .md-button }

These tests cover the `RESTORE` statement family, which puts a deleted record back at its original RID.

Every assertion asks the same question two ways: `SELECT count(*)` against a full scan. A wrong count comes back with an ordinary success and no warning, so nothing but comparing the two can tell it apart from a correct one.

## Covered Behavior

### 1) `RESTORE DOCUMENT` restores the record count

Inserts three documents, deletes one, restores it, and checks that `count(*)` agrees with a full scan at every step. Then reopens the database and checks again — the reopen is half the test, because the bug this pins survived close and reopen, which is what proved it was the stored count rather than a stale in-memory statistic.

### 2) the restored record is intact

Confirms the record comes back with its original RID and the properties given in the `SET` clause. Delete and restore run in **separate** transactions, which is the only shape that currently works.

### 3) `RESTORE VERTEX` restores the record count

The same check for vertices. Kept as its own test rather than parametrized with the document case, because a vertex carries edge bookkeeping a document does not, so a future regression could plausibly hit one and not the other.

### 4) same-transaction restore — `xfail(strict=True)`

`DELETE` and `RESTORE` inside one transaction leaves `count(*)` reporting 1 while a full scan returns 0, and the disagreement survives reopen. Marked strict, so the day upstream fixes it the test XPASSes and fails the suite, instead of sitting here green and unnoticed.

## Upstream history

This file exists because of [#6069](https://github.com/ArcadeData/arcadedb/issues/6069): `RESTORE` put the record back but did not fold the bucket's record-count delta, so `count(*)` returned one fewer than a full scan. Fixed upstream in `86cb4673be`.

The gap was left untested while that was open, deliberately. Pinning the broken behaviour would have baked a bug into the suite, and pinning the correct behaviour would have failed until the fix landed.

The same-transaction case in test 4 is a **separate, still-open** defect found while verifying that fix, filed as [#6096](https://github.com/ArcadeData/arcadedb/issues/6096). It is not a regression: `RESTORE` does not parse at all on the 26.8.1 release (`no viable alternative at input 'RESTORE'`), so the statement has never shipped in a release and there is no earlier behaviour it could have regressed from.
