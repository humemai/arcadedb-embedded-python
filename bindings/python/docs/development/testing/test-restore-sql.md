# RESTORE SQL Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_restore_sql.py){ .md-button }

These tests cover the `RESTORE` statement family, which puts a deleted record back at its original RID.

The count assertions ask the same question two ways: `SELECT count(*)` against a full scan. A wrong count comes back with an ordinary success and no warning, so nothing but comparing the two can tell it apart from a correct one. The intact-record test also checks the record itself (its RID and properties), and the index test checks its index entry.

## Covered Behavior

### 1) `RESTORE DOCUMENT` restores the record count

Inserts three documents, deletes one, restores it, and checks that `count(*)` agrees with a full scan at every step. Then reopens the database and checks again. The reopen is half the test, because the bug this pins survived close and reopen, which is what proved it was the stored count rather than a stale in-memory statistic.

### 2) the restored record is intact

Confirms the record comes back with its original RID and the properties given in the `SET` clause. Delete and restore run in **separate** transactions here; the same-transaction shape has its own test (same-transaction restore, below).

### 3) `RESTORE VERTEX` restores the record count

The same check for vertices. Kept as its own test rather than parametrized with the document case, because a vertex carries edge bookkeeping a document does not, so a future regression could plausibly hit one and not the other.

### 4) same-transaction restore

A plain assertion: after a same-transaction `DELETE` then `RESTORE`, `count(*)` and a full scan both return 1 ([#6096](https://github.com/ArcadeData/arcadedb/issues/6096)).

### 5) `RESTORE` re-adds index entries

[#6120](https://github.com/ArcadeData/arcadedb/issues/6120). The duplicate-insert assertion is the sharp one: a query on an indexed property could in principle be answered by a scan and pass with the index entry missing, but a UNIQUE index's own duplicate check cannot. If the entry is absent, the second insert is accepted and uniqueness has silently stopped holding.

## Upstream defects pinned

| Issue | Defect | Fixed by |
|---|---|---|
| [#6069](https://github.com/ArcadeData/arcadedb/issues/6069) | bucket record-count delta not folded | `86cb4673be` |
| [#6096](https://github.com/ArcadeData/arcadedb/issues/6096) | same-transaction restore wrote the record into the page header | `59e590aaa9` |
| [#6120](https://github.com/ArcadeData/arcadedb/issues/6120) | index entries never re-added | `d1c7494fc3` |
