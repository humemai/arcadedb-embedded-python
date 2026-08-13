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

### 4) same-transaction restore

`DELETE` and `RESTORE` inside one transaction. This shipped as `xfail(strict=True)` while [#6096](https://github.com/ArcadeData/arcadedb/issues/6096) was open, and the strict marker is what reported the fix: the suite went red on XPASS, with no comment on the issue and no release note to say so. Now a plain assertion.

### 5) `RESTORE` re-adds index entries

[#6120](https://github.com/ArcadeData/arcadedb/issues/6120). The duplicate-insert assertion is the sharp one: a query on an indexed property could in principle be answered by a scan and pass with the index entry missing, but a UNIQUE index's own duplicate check cannot. If the entry is absent, the second insert is accepted and uniqueness has silently stopped holding.

## Upstream history

Three defects in one statement family, all found within two days of each other, all now fixed:

| Issue | Defect | Fixed by |
|---|---|---|
| [#6069](https://github.com/ArcadeData/arcadedb/issues/6069) | bucket record-count delta not folded | `86cb4673be` |
| [#6096](https://github.com/ArcadeData/arcadedb/issues/6096) | same-transaction restore wrote the record into the page header | `59e590aaa9` |
| [#6120](https://github.com/ArcadeData/arcadedb/issues/6120) | index entries never re-added | `d1c7494fc3` |

The family was left untested while #6069 was open, deliberately: pinning the broken behaviour would have baked a bug into the suite, and pinning the correct behaviour would have failed until the fix landed.

**#6096 was found by verifying the #6069 fix rather than by a workload.** The count agreed with a scan in the separate-transaction shape the original repro used, and disagreed in the same-transaction shape, in the opposite direction. It was not a regression: `RESTORE` does not parse at all on the 26.8.1 release (`no viable alternative at input 'RESTORE'`), so the statement had never shipped.

**#6120 was spun off from #6096 by the maintainer**, who found it while fixing ours and kept it out of scope on purpose.

All three were closed with no comment. The strict xfail is what told us #6096 had landed.
